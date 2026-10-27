"""Parent mode: a PIN, a short-lived session, and a lockout.

The PIN lives in MANTEL_PARENT_PIN and is read per request, so changing it takes
a restart of nothing. The kiosk never sees it, stores it, or compares it.

The session is a random token. The browser gets it as a cookie, and since 0.3.2
the sign-in answer carries it too, for the kiosk to send back in a header: a
kiosk framed by Turing Machine from another address is a third party to Safari,
which then drops our cookie, and a parent who typed the right PIN was told so
and still shut out of every parent route.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field

logger = logging.getLogger("mantel_api.parent")

COOKIE_NAME = "mantel_parent"
#: The same token, sent by the kiosk itself (held in memory for the session).
HEADER_NAME = "x-mantel-parent"
SESSION_SECONDS = 10 * 60
#: An action inside the last minute of a session buys another ten: a parent
#: halfway through the meals is not thrown out for being thorough.
EXTEND_WITHIN_SECONDS = 60
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 60


class NotConfigured(Exception):
    """MANTEL_PARENT_PIN is empty, so parent mode cannot be entered at all."""


class BadPin(Exception):
    """Wrong PIN. `remaining` is how many tries are left before the lockout."""

    def __init__(self, remaining: int) -> None:
        super().__init__("wrong pin")
        self.remaining = remaining


class LockedOut(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("too many attempts")
        self.retry_after = retry_after


@dataclass
class Attempts:
    count: int = 0
    locked_until: float = 0.0


@dataclass
class ParentAuth:
    """Sessions and failed attempts, both in memory: a restart logs you out."""

    sessions: dict[str, float] = field(default_factory=dict)
    attempts: dict[str, Attempts] = field(default_factory=dict)

    @staticmethod
    def pin() -> str:
        return os.environ.get("MANTEL_PARENT_PIN", "").strip()

    def configured(self) -> bool:
        return bool(self.pin())

    def locked_for(self, client: str, now: float) -> int:
        """Seconds still to wait, or 0."""
        record = self.attempts.get(client)
        if record is None or record.locked_until <= now:
            return 0
        return int(record.locked_until - now) + 1

    def open_session(self, supplied: str, client: str, now: float) -> str:
        expected = self.pin()
        if not expected:
            raise NotConfigured

        waiting = self.locked_for(client, now)
        if waiting:
            raise LockedOut(waiting)

        record = self.attempts.setdefault(client, Attempts())
        if not secrets.compare_digest(supplied.strip(), expected):
            record.count += 1
            if record.count >= MAX_ATTEMPTS:
                record.locked_until = now + LOCKOUT_SECONDS
                record.count = 0
                logger.warning("parent pin locked out %s for %ss", client, LOCKOUT_SECONDS)
                raise LockedOut(LOCKOUT_SECONDS)
            raise BadPin(MAX_ATTEMPTS - record.count)

        # A good PIN clears the slate and starts the clock.
        self.attempts.pop(client, None)
        token = secrets.token_urlsafe(32)
        self.sessions[token] = now + SESSION_SECONDS
        self._forget_expired(now)
        return token

    def valid(self, token: str | None, now: float) -> bool:
        if not token:
            return False
        expiry = self.sessions.get(token)
        if expiry is None:
            return False
        if expiry <= now:
            self.sessions.pop(token, None)
            return False
        return True

    def remaining(self, token: str | None, now: float) -> int:
        """Whole seconds left on this session, or 0."""
        if not self.valid(token, now) or token is None:
            return 0
        return max(0, int(self.sessions[token] - now))

    def extend(self, token: str | None, now: float) -> bool:
        """Another full session, for a parent still working in the last
        minute of this one. True when it was extended."""
        left = self.remaining(token, now)
        if token is None or left == 0 or left > EXTEND_WITHIN_SECONDS:
            return False
        self.sessions[token] = now + SESSION_SECONDS
        return True

    def close_session(self, token: str | None) -> None:
        if token:
            self.sessions.pop(token, None)

    def _forget_expired(self, now: float) -> None:
        for token in [token for token, expiry in self.sessions.items() if expiry <= now]:
            self.sessions.pop(token, None)
