"""The bedtime check-in: five faces, one tap, and nothing that asks twice.

Stored in settings_runtime rather than a table of its own. It is one small
string per child per night and nothing joins against it — the weekly digest
reads it back and no other screen ever does. A table would be three migrations
and an index for a row nobody queries.

The deliberate absences are the design. There is no streak, because a child
who misses Tuesday has not failed at having feelings. There is no reminder,
because a screen that asks how you are until you answer is not asking. And it
appears on no screen but NIGHT and the digest, because what a seven-year-old
felt about a Tuesday is for the people who live there.
"""

from __future__ import annotations

import sqlite3
from datetime import date as Date

#: great, good, okay, meh, rough — in that order, worst last.
FACES = ("great", "good", "okay", "meh", "rough")

PREFIX = "feeling"


def key(kid_id: str, day: Date) -> str:
    return f"{PREFIX}:{day.isoformat()}:{kid_id}"


def record(connection: sqlite3.Connection, *, kid_id: str, day: Date, feeling: str) -> None:
    """One tap. Tapping again on the same night replaces it, silently.

    A child who taps "rough" and then thinks better of it should be able to
    change their mind without the screen making anything of it.
    """
    if feeling not in FACES:
        raise ValueError(f"unknown feeling {feeling!r}")
    connection.execute(
        """
        INSERT INTO settings_runtime (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key(kid_id, day), feeling),
    )


def on(connection: sqlite3.Connection, *, kid_id: str, day: Date) -> str | None:
    """What they said tonight, so the row can show which face is chosen."""
    row = connection.execute(
        "SELECT value FROM settings_runtime WHERE key = ?", (key(kid_id, day),)
    ).fetchone()
    return str(row["value"]) if row is not None else None


def between(connection: sqlite3.Connection, start: Date, end: Date) -> dict[str, dict[str, str]]:
    """kid_id → date → feeling, for the week the digest covers.

    Days nobody answered are simply absent. The digest says what was said, not
    what was missed: a gap there would turn a check-in into a chore.
    """
    rows = connection.execute(
        "SELECT key, value FROM settings_runtime WHERE key LIKE ? ORDER BY key",
        (f"{PREFIX}:%",),
    )
    found: dict[str, dict[str, str]] = {}
    for row in rows:
        parts = str(row["key"]).split(":")
        if len(parts) != 3:
            continue
        _, when, kid_id = parts
        try:
            day = Date.fromisoformat(when)
        except ValueError:
            continue
        if start <= day <= end:
            found.setdefault(kid_id, {})[when] = str(row["value"])
    return found
