"""What a parent decides, and what it moves.

One queue, two kinds of thing in it: a child saying they did a chore, and a
child asking to spend what they earned. Both are answered the same way and
both write their consequence in the same transaction as the decision, so a
crash between the two is not a thing that can happen — no approval pays
twice, and none pays nothing.

Declining writes no ledger row at all. There is no such thing as a negative
row for a chore that was not done: the row simply never existed, and the task
goes back to looking untouched on the dashboard. Nothing turns red.
"""

from __future__ import annotations

import sqlite3
from datetime import date as Date
from datetime import datetime, timedelta

from . import claims, ledger, streaks
from .claims import ClaimError
from .models import ApprovalItem, Points, Rewards, Tasks


def queue(connection: sqlite3.Connection, tasks: Tasks, rewards: Rewards) -> list[ApprovalItem]:
    """Everything waiting on a parent, newest first.

    Claims and redemptions are interleaved by time rather than grouped: a
    parent works down one list and is finished, instead of remembering to
    check a second one.
    """
    items: list[ApprovalItem] = []

    for pending in claims.pending(connection):
        task = next(
            (item for item in tasks.of(pending.kid_id) if item.id == pending.task_id), None
        )
        items.append(
            ApprovalItem(
                kind="claim",
                id=pending.id,
                kid_id=pending.kid_id,
                title=task.title if task is not None else pending.task_id,
                points=task.points if task is not None else 0,
                when=pending.claimed_at,
            )
        )

    rows = connection.execute(
        "SELECT * FROM redemptions WHERE status = 'requested' ORDER BY requested_at DESC, id DESC"
    )
    for row in rows:
        reward = rewards.by_id(str(row["reward_id"]))
        items.append(
            ApprovalItem(
                kind="redemption",
                id=int(row["id"]),
                kid_id=str(row["kid_id"]),
                title=reward.name if reward is not None else str(row["reward_id"]),
                points=int(row["points"]),
                when=str(row["requested_at"]),
                note=row["note"],
            )
        )

    items.sort(key=lambda item: item.when, reverse=True)
    return items


def pending_count(connection: sqlite3.Connection) -> int:
    """How many things are waiting. The only number the lock screen shows."""
    claimed = connection.execute(
        "SELECT COUNT(*) AS n FROM claims WHERE status = 'claimed'"
    ).fetchone()["n"]
    asked = connection.execute(
        "SELECT COUNT(*) AS n FROM redemptions WHERE status = 'requested'"
    ).fetchone()["n"]
    return int(claimed) + int(asked)


def approve_claim(
    connection: sqlite3.Connection,
    tasks: Tasks,
    settings_points: Points,
    *,
    claim_id: int,
    decided_by: str,
    now: datetime,
    is_school_day: object = None,
) -> int:
    """Mark the claim and pay for it, in one transaction. Returns the ledger id."""
    found = claims.by_id(connection, claim_id)
    if found is None:
        raise ClaimError(404, f"no claim {claim_id}")
    if found.status != "claimed":
        raise ClaimError(409, f"claim {claim_id} is already {found.status}")

    task = next((item for item in tasks.of(found.kid_id) if item.id == found.task_id), None)
    points = task.points if task is not None else 0

    connection.execute(
        """
        UPDATE claims SET status = 'approved', decided_at = ?, decided_by = ?
        WHERE id = ? AND status = 'claimed'
        """,
        (now.isoformat(), decided_by, claim_id),
    )
    row_id = ledger.append(
        connection,
        kid_id=found.kid_id,
        delta=points,
        reason_kind="task",
        reason_ref=f"{found.kid_id}:{found.task_id}:{found.date.isoformat()}",
        note=task.title if task is not None else found.task_id,
        actor="parent",
        now=now,
    )

    if callable(is_school_day):
        pay_streak_bonus(
            connection,
            tasks,
            settings_points,
            kid_id=found.kid_id,
            today=found.date,
            is_school_day=is_school_day,
            now=now,
        )
    return row_id


def decline_claim(
    connection: sqlite3.Connection, *, claim_id: int, decided_by: str, now: datetime
) -> None:
    """Say no. Nothing is written to the ledger, because nothing happened."""
    found = claims.by_id(connection, claim_id)
    if found is None:
        raise ClaimError(404, f"no claim {claim_id}")
    if found.status != "claimed":
        raise ClaimError(409, f"claim {claim_id} is already {found.status}")
    connection.execute(
        """
        UPDATE claims SET status = 'declined', decided_at = ?, decided_by = ?
        WHERE id = ? AND status = 'claimed'
        """,
        (now.isoformat(), decided_by, claim_id),
    )


def award(
    connection: sqlite3.Connection,
    *,
    kid_id: str,
    points: int,
    note: str,
    decided_by: str,
    now: datetime,
    deductions: bool = False,
) -> int:
    """Points for something no task file will ever list.

    Being kind to a brother, or owning up to something. The note is the whole
    value of the row: "15 points" six weeks later means nothing without it.

    Negative only where the house has turned deductions on, and never below
    zero: a child in debt to a points system has stopped playing it.
    """
    if points == 0:
        raise ClaimError(400, "an award is worth more than nothing")
    if not note.strip():
        raise ClaimError(400, "an award needs to say what it was for")
    if points < 0:
        if not deductions:
            raise ClaimError(403, "deductions are off in settings")
        if ledger.balance(connection, kid_id) + points < 0:
            raise ClaimError(409, "that would take them below zero")
    return ledger.append(
        connection,
        kid_id=kid_id,
        delta=points,
        reason_kind="award" if points > 0 else "adjust",
        reason_ref=decided_by,
        note=note.strip(),
        actor="parent",
        now=now,
    )


def week_key(day: Date) -> str:
    """ISO year and week, which is what one bonus a week is counted against."""
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def bonus_ref(kid_id: str, day: Date) -> str:
    return f"streak:{kid_id}:{week_key(day)}"


def pay_streak_bonus(
    connection: sqlite3.Connection,
    tasks: Tasks,
    settings_points: Points,
    *,
    kid_id: str,
    today: Date,
    is_school_day: object,
    now: datetime,
) -> int | None:
    """Pay the weekly bonus if the run is long enough and it is not paid yet.

    Idempotent by construction: the row carries the kid and the ISO week as
    its reference, and this refuses to write a second one with the same
    reference. An approval that arrives twice cannot pay twice.
    """
    if settings_points.streak_bonus <= 0 or not callable(is_school_day):
        return None

    run = streaks.current_streak(connection, tasks, kid_id, today, is_school_day)
    if run < settings_points.streak_days:
        return None

    reference = bonus_ref(kid_id, today)
    already = connection.execute(
        "SELECT 1 FROM ledger WHERE reason_kind = 'adjust' AND reason_ref = ?",
        (reference,),
    ).fetchone()
    if already is not None:
        return None

    return ledger.append(
        connection,
        kid_id=kid_id,
        delta=settings_points.streak_bonus,
        reason_kind="adjust",
        reason_ref=reference,
        note=f"{run} days in a row",
        actor="parent",
        now=now,
    )


def week_of(moment: datetime) -> tuple[datetime, datetime]:
    start = ledger.week_start(moment)
    return start, start + timedelta(days=7)
