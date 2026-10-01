"""The demo's history: a fortnight of the sample family, written into a
fresh ledger so every screen has something true to show.

    Mira 37 points, Kabir 52, the family jar 210.
    Today: Mira two chores done and one waiting; Kabir one done, one waiting
    and one declined.
    Kabir's Ice cream approved and waiting for a parent to hand it over.
    The coming week's meal picks half filled, with Thursday's dinner
    contested: Mira tacos, Kabir pizza night.
    Last week's chores approved, so the digest has a week to read.

Everything is written through the modules that own it — claims, the ledger,
redemptions, picks, kid codes — so the demo is the app's own data, not a
picture of it. `seed` runs on an empty database and on nothing else.
"""

from __future__ import annotations

import sqlite3
from datetime import date as Date
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import ledger, out, pins, redemptions, weekly
from .content import Content
from .models import TaskItem
from .today import tasks_on

#: Where the demo's balances land.
BALANCES = {"mira": 37, "kabir": 52}
#: What each child has put in the family jar, which comes to 210.
JAR = {"mira": 100, "kabir": 110}
#: The kid codes the demo prints.
CODES = {"mira": "1111", "kabir": "2222"}
PLACES = ("Corner Trattoria", "Taqueria Luna")


def _at(day: Date, hour: int, zone: ZoneInfo, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=zone)


def _school(day: Date) -> bool:
    return day.weekday() < 5


def _claimable(content: Content, kid_id: str, day: Date) -> list[TaskItem]:
    tasks = content.tasks.current
    assert tasks is not None  # noqa: S101 - the sample always loads
    return [
        task
        for task in tasks_on(tasks, kid_id, day, _school(day))
        if task.claim == "kid" and task.every == "day"
    ]


def _claim(
    connection: sqlite3.Connection,
    kid_id: str,
    task: TaskItem,
    day: Date,
    status: str,
    zone: ZoneInfo,
    hour: int,
) -> None:
    claimed = _at(day, hour, zone)
    decided = claimed + timedelta(minutes=40) if status != "claimed" else None
    connection.execute(
        """
        INSERT INTO claims (kid_id, task_id, date, status, claimed_at, decided_at, decided_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kid_id,
            task.id,
            day.isoformat(),
            status,
            claimed.isoformat(),
            decided.isoformat() if decided else None,
            "parent" if decided else None,
        ),
    )
    if status == "approved":
        ledger.append(
            connection,
            kid_id=kid_id,
            delta=task.points,
            reason_kind="task",
            reason_ref=f"{kid_id}:{task.id}:{day.isoformat()}",
            note=task.title,
            actor="parent",
            now=decided or claimed,
        )


def seed(connection: sqlite3.Connection, content: Content, today: Date, zone: ZoneInfo) -> None:
    """Write the demo's fortnight into an empty ledger."""
    if connection.execute("SELECT COUNT(*) AS n FROM ledger").fetchone()["n"]:
        raise RuntimeError("the demo seeds an empty database, and this one is not")

    # Today, as the brief has it.
    earned_today: dict[str, int] = {}
    mira = _claimable(content, "mira", today)
    kabir = _claimable(content, "kabir", today)
    for task, status, hour in (
        (mira[0], "approved", 7),
        (mira[1], "approved", 8),
        (mira[2], "claimed", 9),
    ):
        _claim(connection, "mira", task, today, status, zone, hour)
    for task, status, hour in (
        (kabir[0], "approved", 7),
        (kabir[1], "claimed", 8),
        (kabir[2], "declined", 9),
    ):
        _claim(connection, "kabir", task, today, status, zone, hour)
    earned_today["mira"] = mira[0].points + mira[1].points
    earned_today["kabir"] = kabir[0].points

    # The fortnight before, walked backwards: approved chores until each
    # child has earned what their balance, the jar and the ice cream need.
    held = {"mira": 0, "kabir": 25}
    for kid_id, balance in BALANCES.items():
        remaining = balance + JAR[kid_id] + held[kid_id] - earned_today[kid_id]
        day = today - timedelta(days=1)
        while remaining > 0 and day > today - timedelta(days=21):
            for index, task in enumerate(_claimable(content, kid_id, day)):
                if task.points <= remaining:
                    _claim(connection, kid_id, task, day, "approved", zone, 16 + index % 4)
                    remaining -= task.points
            day -= timedelta(days=1)
        if remaining > 0:
            ledger.append(
                connection,
                kid_id=kid_id,
                delta=remaining,
                reason_kind="award",
                reason_ref="parent",
                note="Helped carry the groceries in",
                actor="parent",
                now=_at(today - timedelta(days=2), 18, zone),
            )

    # Into the family jar, three days ago.
    for kid_id, points in JAR.items():
        ledger.transfer_to_jar(
            connection,
            kid_id=kid_id,
            points=points,
            now=_at(today - timedelta(days=3), 19, zone),
            note="For dinner out",
        )

    # Kabir's ice cream: asked for and approved yesterday, not yet handed over.
    rewards = content.rewards.current
    settings = content.settings.current
    assert rewards is not None and settings is not None  # noqa: S101
    asked = redemptions.request(
        connection,
        rewards,
        settings.points,
        kid_id="kabir",
        reward_id="ice_cream",
        now=_at(today - timedelta(days=1), 17, zone),
    )
    redemptions.approve(
        connection,
        rewards,
        settings.allowance,
        redemption_id=asked.id,
        now=_at(today - timedelta(days=1), 19, zone),
    )

    # The coming week, half picked, with Thursday's dinner contested.
    catalog = content.catalog.current
    assert catalog is not None  # noqa: S101
    # Picked this morning: every day picked for is after today, so none of
    # them has locked, whenever the demo is run.
    now = _at(today, 7, zone)
    thursday = today + timedelta(days=(3 - today.weekday()) % 7 or 7)
    picks = [
        ("mira", thursday, "dinner", "tacos"),
        ("kabir", thursday, "dinner", "pizza_night"),
        ("mira", today + timedelta(days=1), "breakfast", "pancakes"),
        ("kabir", today + timedelta(days=2), "lunch", "grilled_cheese"),
        ("mira", today + timedelta(days=3), "lunch", "pesto_pasta"),
        ("kabir", today + timedelta(days=5), "breakfast", "oatmeal"),
    ]
    for kid_id, day, slot, dish in picks:
        weekly.choose(
            connection,
            catalog,
            kid_id=kid_id,
            day=day,
            slot=slot,  # type: ignore[arg-type]
            dish_id=dish,
            protein="veg",
            now=now,
        )

    for kid_id, code in CODES.items():
        pins.set_pin(connection, kid_id, code)
    for place in PLACES:
        out.remember(connection, place)
