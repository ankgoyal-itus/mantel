"""Reading and writing points.

Every function here takes an open connection, so a caller can put several
writes in one transaction — approving a claim is a ledger row and a claim
update together, and half of that would be worse than neither.

Times are stored as local ISO 8601 in the house's timezone. The day a claim
belongs to is the day the house was living in when it happened, not the day
UTC happened to be on, and every window here is worked out in those terms.
"""

from __future__ import annotations

import sqlite3
from datetime import date as Date
from datetime import datetime, timedelta

from .db import FAMILY
from .models import LedgerRow

__all__ = [
    "FAMILY",
    "append",
    "balance",
    "earned_since",
    "entries",
    "hold",
    "refund",
    "transfer_to_jar",
    "week_start",
]


def append(
    connection: sqlite3.Connection,
    *,
    kid_id: str,
    delta: int,
    reason_kind: str,
    actor: str,
    now: datetime,
    reason_ref: str | None = None,
    note: str | None = None,
) -> int:
    """Add one row and return its id. The only way points ever move."""
    cursor = connection.execute(
        """
        INSERT INTO ledger (kid_id, delta, reason_kind, reason_ref, note, actor, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (kid_id, delta, reason_kind, reason_ref, note, actor, now.isoformat()),
    )
    return int(cursor.lastrowid or 0)


def balance(connection: sqlite3.Connection, kid_id: str) -> int:
    """SUM(delta). Never stored, so it cannot disagree with the rows."""
    row = connection.execute(
        "SELECT COALESCE(SUM(delta), 0) AS total FROM ledger WHERE kid_id = ?",
        (kid_id,),
    ).fetchone()
    return int(row["total"])


def entries(
    connection: sqlite3.Connection, kid_id: str, *, since: datetime | None = None
) -> list[LedgerRow]:
    """The kid's rows, newest first."""
    sql = "SELECT * FROM ledger WHERE kid_id = ?"
    params: list[object] = [kid_id]
    if since is not None:
        sql += " AND created_at >= ?"
        params.append(since.isoformat())
    sql += " ORDER BY created_at DESC, id DESC"
    return [LedgerRow.from_row(dict(row)) for row in connection.execute(sql, params)]


def earned_since(connection: sqlite3.Connection, kid_id: str, since: datetime) -> int:
    """What was *earned* in a window, not the net change.

    "this week +35" is a number a child recognises as theirs. Netting what
    they spent against what they earned would make a good week of chores read
    as a bad one because they treated themselves on Saturday.
    """
    row = connection.execute(
        """
        SELECT COALESCE(SUM(delta), 0) AS total FROM ledger
        WHERE kid_id = ? AND delta > 0 AND created_at >= ?
        """,
        (kid_id, since.isoformat()),
    ).fetchone()
    return int(row["total"])


def earned_by_day(connection: sqlite3.Connection, kid_id: str, now: datetime) -> list[int]:
    """What was earned on each day of this week, Monday first: seven numbers.

    Earned, as in `earned_since`, and bucketed by the local date each row was
    written on, so a week that crosses the clocks changing still lands every
    row on its own day.
    """
    monday = week_start(now)
    days = [0] * 7
    rows = connection.execute(
        """
        SELECT delta, created_at FROM ledger
        WHERE kid_id = ? AND delta > 0 AND created_at >= ?
        """,
        (kid_id, (monday - timedelta(days=1)).isoformat()),
    ).fetchall()
    for row in rows:
        written = datetime.fromisoformat(row["created_at"])
        if written.tzinfo is not None and now.tzinfo is not None:
            written = written.astimezone(now.tzinfo)
        index = (written.date() - monday.date()).days
        if 0 <= index < 7:
            days[index] += int(row["delta"])
    return days


def week_start(moment: datetime) -> datetime:
    """Midnight on the Monday of this moment's week, in its own timezone."""
    midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=midnight.weekday())


def day_bounds(day: Date, moment: datetime) -> tuple[datetime, datetime]:
    """Midnight to midnight on a local date, carrying a moment's timezone."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=moment.tzinfo)
    return start, start + timedelta(days=1)


def hold(
    connection: sqlite3.Connection,
    *,
    kid_id: str,
    points: int,
    reason_ref: str,
    now: datetime,
    note: str | None = None,
) -> int:
    """Take the points out when a reward is asked for, not when it is given.

    A balance that still shows points already spoken for invites a child to
    spend them twice and a parent to be the one who says no.
    """
    return append(
        connection,
        kid_id=kid_id,
        delta=-abs(points),
        reason_kind="redeem",
        reason_ref=reason_ref,
        note=note,
        actor="kid",
        now=now,
    )


def refund(
    connection: sqlite3.Connection,
    *,
    kid_id: str,
    points: int,
    reason_ref: str,
    now: datetime,
    note: str | None = None,
) -> int:
    """Give a held amount back, as its own row. Exactly reverses `hold`."""
    return append(
        connection,
        kid_id=kid_id,
        delta=abs(points),
        reason_kind="refund",
        reason_ref=reason_ref,
        note=note,
        actor="parent",
        now=now,
    )


def transfer_to_jar(
    connection: sqlite3.Connection,
    *,
    kid_id: str,
    points: int,
    now: datetime,
    note: str | None = None,
) -> tuple[int, int]:
    """Move points from a kid to the family jar: two rows that sum to zero.

    Written as a movement rather than an adjustment on each side, so the jar
    can always say whose points are in it.
    """
    amount = abs(points)
    out_id = append(
        connection,
        kid_id=kid_id,
        delta=-amount,
        reason_kind="jar",
        reason_ref=FAMILY,
        note=note,
        actor="kid",
        now=now,
    )
    in_id = append(
        connection,
        kid_id=FAMILY,
        delta=amount,
        reason_kind="jar",
        reason_ref=kid_id,
        note=note,
        actor="kid",
        now=now,
    )
    return out_id, in_id
