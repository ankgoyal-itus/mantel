"""Claims: a child saying they did a thing, and waiting to be believed.

A claim is not points. It is a request, and it stays a request until a parent
decides — which is phase C's business. Nothing here writes to the ledger.

The 5 second undo the kiosk offers is a property of the button, not of the
database: a claim can be withdrawn for as long as nobody has decided on it,
which is the rule that actually matters. A child who taps the wrong row and
notices a minute later should not have to ask a parent to decline it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from datetime import date as Date
from datetime import datetime, timedelta

from .models import Claim, TaskItem, Tasks


class ClaimError(Exception):
    """Something the caller asked for that the rules do not allow."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def task_for(tasks: Tasks, kid_id: str, task_id: str) -> TaskItem:
    for task in tasks.of(kid_id):
        if task.id == task_id:
            return task
    raise ClaimError(404, f"{kid_id} has no task {task_id!r}")


def claim(
    connection: sqlite3.Connection,
    tasks: Tasks,
    *,
    kid_id: str,
    task_id: str,
    day: Date,
    now: datetime,
) -> Claim:
    """Record that a kid says they did this today.

    A task marked `claim: parent` is not refused quietly: a kid tapping one
    is either a bug in the kiosk or a child testing the rules, and both are
    better answered out loud than by a row that silently never appears.
    """
    task = task_for(tasks, kid_id, task_id)
    if task.claim != "kid":
        raise ClaimError(403, f"{task_id!r} is marked for a parent to tick off")

    # Once a week is once a week: Thursday's homework finds Tuesday's claim.
    existing = (
        find_in_week(connection, kid_id=kid_id, task_id=task_id, day=day)
        if task.every == "week"
        else find(connection, kid_id=kid_id, task_id=task_id, day=day)
    )
    if existing is not None and existing.status == "declined":
        # A decline puts the row back to looking untouched, so tapping it has
        # to work again. The child is asking a second time, which is a thing
        # for the family to settle rather than for the schema to forbid.
        connection.execute(
            """
            UPDATE claims
            SET status = 'claimed', date = ?, claimed_at = ?, decided_at = NULL, decided_by = NULL
            WHERE id = ?
            """,
            (day.isoformat(), now.isoformat(), existing.id),
        )
        found = by_id(connection, existing.id)
        assert found is not None  # noqa: S101 - the row was just updated
        return found
    if existing is not None:
        # Tapping a claimed row twice is the undo, which the kiosk sends as a
        # DELETE. Reaching here means it is already decided.
        when = "this week" if task.every == "week" else day.isoformat()
        raise ClaimError(409, f"{task_id!r} is already {existing.status} for {when}")

    cursor = connection.execute(
        """
        INSERT INTO claims (kid_id, task_id, date, status, claimed_at)
        VALUES (?, ?, ?, 'claimed', ?)
        """,
        (kid_id, task_id, day.isoformat(), now.isoformat()),
    )
    found = by_id(connection, int(cursor.lastrowid or 0))
    assert found is not None  # noqa: S101 - the row was just written
    return found


def undo(connection: sqlite3.Connection, claim_id: int) -> None:
    """Withdraw a claim nobody has decided on yet.

    The row goes: an undecided claim is not history, it is a child changing
    their mind. Only the ledger is append-only, and no ledger row exists yet.
    """
    found = by_id(connection, claim_id)
    if found is None:
        raise ClaimError(404, f"no claim {claim_id}")
    if found.status != "claimed":
        raise ClaimError(409, f"claim {claim_id} is already {found.status}")
    connection.execute("DELETE FROM claims WHERE id = ?", (claim_id,))


def by_id(connection: sqlite3.Connection, claim_id: int) -> Claim | None:
    row = connection.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    return Claim.model_validate(dict(row)) if row is not None else None


def find(
    connection: sqlite3.Connection, *, kid_id: str, task_id: str, day: Date
) -> Claim | None:
    row = connection.execute(
        "SELECT * FROM claims WHERE kid_id = ? AND task_id = ? AND date = ?",
        (kid_id, task_id, day.isoformat()),
    ).fetchone()
    return Claim.model_validate(dict(row)) if row is not None else None


def monday_of(day: Date) -> Date:
    return day - timedelta(days=day.weekday())


def find_in_week(
    connection: sqlite3.Connection, *, kid_id: str, task_id: str, day: Date
) -> Claim | None:
    """The one claim of a once-a-week task in the week holding `day`."""
    monday = monday_of(day)
    row = connection.execute(
        """
        SELECT * FROM claims WHERE kid_id = ? AND task_id = ? AND date >= ? AND date <= ?
        ORDER BY date DESC, id DESC LIMIT 1
        """,
        (kid_id, task_id, monday.isoformat(), (monday + timedelta(days=6)).isoformat()),
    ).fetchone()
    return Claim.model_validate(dict(row)) if row is not None else None


def _this_period(
    connection: sqlite3.Connection, kid_id: str, day: Date, weekly: Collection[str], columns: str,
    where: str = "",
) -> list[sqlite3.Row]:
    """Claims that count for `day`: that day's, and — for once-a-week
    tasks — any day of its week. Oldest first, so the latest wins a dict."""
    monday = monday_of(day)
    marks = ",".join("?" for _ in weekly) or "NULL"
    return list(
        connection.execute(
            f"""
            SELECT {columns} FROM claims
            WHERE kid_id = ? {where} AND (
              date = ? OR (task_id IN ({marks}) AND date >= ? AND date <= ?)
            )
            ORDER BY date, id
            """,  # noqa: S608 - the placeholders are built here, the values bound
            (
                kid_id,
                day.isoformat(),
                *weekly,
                monday.isoformat(),
                (monday + timedelta(days=6)).isoformat(),
            ),
        )
    )


def on_day(connection: sqlite3.Connection, day: Date) -> list[Claim]:
    """Every claim made for one date, whatever its state."""
    rows = connection.execute(
        "SELECT * FROM claims WHERE date = ? ORDER BY claimed_at DESC, id DESC",
        (day.isoformat(),),
    )
    return [Claim.model_validate(dict(row)) for row in rows]


def status_on(
    connection: sqlite3.Connection, kid_id: str, day: Date, weekly: Collection[str] = ()
) -> dict[str, str]:
    """task_id → status, for the rows the dashboard draws. A once-a-week
    task (in `weekly`) answers for its whole week."""
    rows = _this_period(connection, kid_id, day, weekly, "task_id, status")
    return {str(row["task_id"]): str(row["status"]) for row in rows}


def ids_on(
    connection: sqlite3.Connection, kid_id: str, day: Date, weekly: Collection[str] = ()
) -> dict[str, int]:
    """task_id → claim id, so a row on the dashboard can be approved in place.

    Only what is still waiting: an approved claim has nothing left to decide,
    and a declined one is answered until the child claims it again.
    """
    rows = _this_period(connection, kid_id, day, weekly, "task_id, id", "AND status = 'claimed'")
    return {str(row["task_id"]): int(row["id"]) for row in rows}


def pending(connection: sqlite3.Connection) -> list[Claim]:
    """Everything waiting on a parent, newest first."""
    rows = connection.execute(
        "SELECT * FROM claims WHERE status = 'claimed' ORDER BY claimed_at DESC, id DESC"
    )
    return [Claim.model_validate(dict(row)) for row in rows]
