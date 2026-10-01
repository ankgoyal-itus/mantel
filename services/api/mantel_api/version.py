"""What the screens show, as one number that goes up.

Every write that changes a screen — a ledger row, a claim, a redemption, a
pick or a decision, a meal set, a setting, a school-event choice, a photo —
bumps `state_version` once. The iPads and the parents' phones watch it
(GET /api/version, or the /api/events stream) and refetch when it moves, so
an approval on a phone reaches the wall in a second rather than at the next
five-minute poll.

The number lives in memory, so reading it costs no database; it is written
through to settings_runtime so a restart does not send it backwards and make
a screen think nothing has changed.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime

from .db import Database
from .models import VersionInfo

KEY = "state_version"


class StateVersion:
    def __init__(self, books: Database) -> None:
        self._books = books
        self._lock = threading.Lock()
        self._version = 0
        self._changed_at: str | None = None
        with books.connect() as connection:
            row = connection.execute(
                "SELECT value FROM settings_runtime WHERE key = ?", (KEY,)
            ).fetchone()
        if row is not None:
            try:
                held = json.loads(str(row["value"]))
                self._version = int(held["version"])
                self._changed_at = held.get("changed_at")
            except (ValueError, KeyError, TypeError):
                pass

    def current(self) -> VersionInfo:
        return VersionInfo(version=self._version, changed_at=self._changed_at)

    def bump(self, now: datetime) -> int:
        """One more change. Written through, so it never goes backwards."""
        with self._lock:
            self._version += 1
            self._changed_at = now.isoformat(timespec="seconds")
            value = json.dumps({"version": self._version, "changed_at": self._changed_at})
            with self._books.write() as connection:
                connection.execute(
                    "INSERT INTO settings_runtime (key, value) VALUES (?, ?)"
                    " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (KEY, value),
                )
            return self._version
