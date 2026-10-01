"""The week, as data.

What a parent would want to know on a Sunday evening: what each child earned,
which chores they were approved for and on which days, what they spent it on,
and what they chose to eat. Counted from the ledger and the claims, which are
the only record of any of it.

Nothing here writes, nothing here judges, and nothing here is generated: it is
the rows, added up. A summary that made things up would be worse than none,
and this is the one thing in Mantel that anything else might ever read.
"""

from __future__ import annotations

import sqlite3
from datetime import date as Date
from datetime import datetime, timedelta

from . import feelings, ledger, out
from .models import Digest, DigestKid, Family, Rewards, Tasks
from .today import MealSource


def week_bounds(week: str, fallback: Date) -> tuple[Date, Date]:
    """"2026-W39" as the Monday and Sunday it names.

    An unparseable week is this week rather than an error: a digest is a thing
    somebody glances at, and a 422 on the settings tab helps nobody.
    """
    try:
        year_part, week_part = week.upper().split("-W")
        monday = Date.fromisocalendar(int(year_part), int(week_part), 1)
    except (ValueError, AttributeError):
        monday = fallback - timedelta(days=fallback.weekday())
    return monday, monday + timedelta(days=6)


def week_name(day: Date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def build(
    connection: sqlite3.Connection,
    family: Family,
    tasks: Tasks,
    rewards: Rewards,
    meals: MealSource,
    *,
    week: str,
    today: Date,
    zone: object = None,
) -> Digest:
    monday, sunday = week_bounds(week, today)
    start = datetime.combine(monday, datetime.min.time())
    if zone is not None:
        start = start.replace(tzinfo=zone)  # type: ignore[arg-type]
    end = start + timedelta(days=7)

    # The bedtime check-in, which is shown here and on no other screen.
    felt = feelings.between(connection, monday, sunday)

    kids = []
    for kid in family.kids:
        earned = ledger.earned_since(connection, kid.id, start)
        spent_rows = connection.execute(
            """
            SELECT COALESCE(SUM(delta), 0) AS total FROM ledger
            WHERE kid_id = ? AND delta < 0 AND created_at >= ? AND created_at < ?
            """,
            (kid.id, start.isoformat(), end.isoformat()),
        ).fetchone()

        titles = {task.id: task.title for task in tasks.of(kid.id)}
        approved: dict[str, list[str]] = {}
        rows = connection.execute(
            """
            SELECT date, task_id FROM claims
            WHERE kid_id = ? AND status = 'approved' AND date >= ? AND date <= ?
            ORDER BY date, task_id
            """,
            (kid.id, monday.isoformat(), sunday.isoformat()),
        )
        for row in rows:
            approved.setdefault(str(row["date"]), []).append(
                titles.get(str(row["task_id"]), str(row["task_id"]))
            )

        spent: list[str] = []
        for row in connection.execute(
            """
            SELECT reward_id, status FROM redemptions
            WHERE kid_id = ? AND requested_at >= ? AND requested_at < ?
            ORDER BY requested_at
            """,
            (kid.id, start.isoformat(), end.isoformat()),
        ):
            reward = rewards.by_id(str(row["reward_id"]))
            name = reward.name if reward is not None else str(row["reward_id"])
            spent.append(f"{name} ({row['status']})")

        picked: list[str] = []
        for offset in range(7):
            when = monday + timedelta(days=offset)
            planned = meals.on(when)
            for slot in ("breakfast", "lunch", "dinner"):
                cell = getattr(planned, slot, None)
                if cell is not None and kid.id in cell.picked_by:
                    picked.append(f"{when.isoformat()} {slot}: {cell.name}")

        kids.append(
            DigestKid(
                kid_id=kid.id,
                name=kid.name,
                earned=earned,
                spent=abs(int(spent_rows["total"])),
                approved=approved,
                redemptions=spent,
                picks=picked,
                feelings=felt.get(kid.id, {}),
            )
        )

    # The meals eaten out, for the whole house: "Sat dinner: Out · Taqueria Luna".
    eaten_out: list[str] = []
    for offset in range(7):
        when = monday + timedelta(days=offset)
        planned = meals.on(when)
        for slot in ("lunch", "dinner"):
            cell = getattr(planned, slot, None)
            if cell is not None and out.is_out(cell.id):
                eaten_out.append(f"{when.strftime('%a')} {slot}: {out.label(cell.note)}")

    return Digest(
        week=week_name(monday), start=monday, end=sunday, kids=kids, out=eaten_out
    )
