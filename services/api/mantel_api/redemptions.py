"""Asking for a reward, and what happens after a parent says yes.

Points are taken when a child asks, not when they are given. A balance that
still shows points already spoken for invites a child to spend them twice and
makes a parent the one who has to say no a second time. A decline puts them
straight back, as its own row.

Approving is not the end of it. The ice cream has not been bought and the
allowance has not been handed over, so approving a reward produces a to-do
for a parent rather than marking itself done. `fulfilled` means somebody
actually did the thing.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date as Date
from datetime import datetime, timedelta

from . import cash, ledger
from .claims import ClaimError
from .models import Allowance, Points, Redemption, Rewards, Todo

#: settings_runtime keys for the allowance reminders a redemption schedules.
ALLOWANCE_PREFIX = "allowance:"


def _row(connection: sqlite3.Connection, redemption_id: int) -> sqlite3.Row | None:
    found: sqlite3.Row | None = connection.execute(
        "SELECT * FROM redemptions WHERE id = ?", (redemption_id,)
    ).fetchone()
    return found


def _model(row: sqlite3.Row, rewards: Rewards) -> Redemption:
    reward = rewards.by_id(str(row["reward_id"]))
    return Redemption.model_validate(
        {
            **dict(row),
            "name": reward.name if reward is not None else str(row["reward_id"]),
            "glyph": reward.glyph if reward is not None else "star",
        }
    )


def week_key(day: Date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def policy_count_this_week(
    connection: sqlite3.Connection, kid_id: str, rewards: Rewards, day: Date
) -> int:
    """How many screen-time rewards this kid has already asked for this week.

    Counted whether or not the rewards are enabled, so turning them on is one
    flag rather than a rule change — and so the cap is tested before anybody
    is relying on it.
    """
    policy_ids = {reward.id for reward in rewards.rewards if reward.fulfilment == "policy"}
    if not policy_ids:
        return 0
    rows = connection.execute(
        """
        SELECT reward_id, requested_at FROM redemptions
        WHERE kid_id = ? AND status NOT IN ('declined', 'refunded')
        """,
        (kid_id,),
    )
    wanted = week_key(day)
    count = 0
    for row in rows:
        if str(row["reward_id"]) not in policy_ids:
            continue
        try:
            when = datetime.fromisoformat(str(row["requested_at"])).date()
        except ValueError:
            continue
        if week_key(when) == wanted:
            count += 1
    return count


def request(
    connection: sqlite3.Connection,
    rewards: Rewards,
    settings_points: Points,
    *,
    kid_id: str,
    reward_id: str,
    now: datetime,
) -> Redemption:
    """Ask for a reward, and hold the points for it."""
    reward = rewards.by_id(reward_id)
    if reward is None:
        raise ClaimError(404, f"no reward {reward_id!r}")
    if not reward.enabled:
        raise ClaimError(409, f"{reward.name} is not available yet")

    if reward.fulfilment == "policy":
        already = policy_count_this_week(connection, kid_id, rewards, now.date())
        if already >= settings_points.roblox_per_week:
            raise ClaimError(
                409, f"that is {already} this week already, which is the limit"
            )

    # A family reward is paid out of the jar, so it is the jar that has to
    # afford it. One child cannot spend what the family saved together.
    payer = ledger.FAMILY if reward.family else kid_id
    balance = ledger.balance(connection, payer)
    if balance < reward.cost:
        short = reward.cost - balance
        raise ClaimError(409, f"{short} points short")

    cursor = connection.execute(
        """
        INSERT INTO redemptions (kid_id, reward_id, points, status, requested_at)
        VALUES (?, ?, ?, 'requested', ?)
        """,
        (kid_id, reward_id, reward.cost, now.isoformat()),
    )
    redemption_id = int(cursor.lastrowid or 0)
    ledger.hold(
        connection,
        kid_id=payer,
        points=reward.cost,
        reason_ref=f"redemption:{redemption_id}",
        note=reward.name,
        now=now,
    )
    row = _row(connection, redemption_id)
    assert row is not None  # noqa: S101 - just written
    return _model(row, rewards)


def decline(
    connection: sqlite3.Connection,
    rewards: Rewards,
    *,
    redemption_id: int,
    now: datetime,
) -> Redemption:
    """Say no, and put the points straight back."""
    row = _row(connection, redemption_id)
    if row is None:
        raise ClaimError(404, f"no redemption {redemption_id}")
    if str(row["status"]) != "requested":
        raise ClaimError(409, f"redemption {redemption_id} is already {row['status']}")

    reward = rewards.by_id(str(row["reward_id"]))
    payer = ledger.FAMILY if reward is not None and reward.family else str(row["kid_id"])
    connection.execute(
        "UPDATE redemptions SET status = 'refunded', decided_at = ? WHERE id = ?",
        (now.isoformat(), redemption_id),
    )
    ledger.refund(
        connection,
        kid_id=payer,
        points=int(row["points"]),
        reason_ref=f"redemption:{redemption_id}",
        note=reward.name if reward is not None else None,
        now=now,
    )
    updated = _row(connection, redemption_id)
    assert updated is not None  # noqa: S101 - just updated
    return _model(updated, rewards)


def approve(
    connection: sqlite3.Connection,
    rewards: Rewards,
    allowance: Allowance,
    *,
    redemption_id: int,
    now: datetime,
) -> Redemption:
    """Say yes, and start whatever actually delivers it.

    The points were already taken when the child asked, so nothing moves here.
    What changes is whose job it is next.
    """
    row = _row(connection, redemption_id)
    if row is None:
        raise ClaimError(404, f"no redemption {redemption_id}")
    if str(row["status"]) != "requested":
        raise ClaimError(409, f"redemption {redemption_id} is already {row['status']}")

    reward = rewards.by_id(str(row["reward_id"]))
    if reward is None:
        raise ClaimError(404, f"no reward {row['reward_id']!r}")

    if reward.fulfilment == "allowance":
        schedule_allowance(
            connection,
            allowance,
            redemption_id=redemption_id,
            kid_id=str(row["kid_id"]),
            days=reward.days or 1,
            today=now.date(),
        )
        status = "scheduled"
    elif reward.fulfilment == "cash":
        # A parent's to-do — "Give Sam $5" — until Paid. What it was worth
        # is written on the row, so a rate changed in rewards.yaml later
        # cannot rewrite what was already earned.
        connection.execute(
            "UPDATE redemptions SET status = 'approved', decided_at = ?, fulfilment_ref = ?"
            " WHERE id = ?",
            (now.isoformat(), f"{cash.PREFIX}{reward.dollars or 0}", redemption_id),
        )
        owing = _row(connection, redemption_id)
        assert owing is not None  # noqa: S101 - just updated
        return _model(owing, rewards)
    elif reward.fulfilment == "meal":
        # The kid picks next, in kid mode. Until they do, it is theirs to do,
        # not a parent's.
        status = "scheduled"
    else:
        # manual, and policy if it is ever switched on: a parent does the
        # thing in the world and ticks it off.
        status = "approved"

    connection.execute(
        "UPDATE redemptions SET status = ?, decided_at = ? WHERE id = ?",
        (status, now.isoformat(), redemption_id),
    )
    updated = _row(connection, redemption_id)
    assert updated is not None  # noqa: S101 - just updated
    return _model(updated, rewards)


def schedule_allowance(
    connection: sqlite3.Connection,
    allowance: Allowance,
    *,
    redemption_id: int,
    kid_id: str,
    days: int,
    today: Date,
) -> list[str]:
    """One reminder a day for N days, starting today.

    Kept in settings_runtime rather than a table of its own: they are notes to
    a parent, they disappear when they are paid, and nothing else ever reads
    them.
    """
    keys = []
    for index in range(days):
        key = f"{ALLOWANCE_PREFIX}{redemption_id}:{index + 1}"
        value = json.dumps(
            {
                "kid_id": kid_id,
                "day": index + 1,
                "days": days,
                "due": (today + timedelta(days=index)).isoformat(),
                "hour": allowance.reminder_hour,
            }
        )
        connection.execute(
            """
            INSERT INTO settings_runtime (key, value) VALUES (?, ?)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        keys.append(key)
    return keys


def todos(connection: sqlite3.Connection, rewards: Rewards, today: Date) -> list[Todo]:
    """What a parent still has to actually do."""
    items: list[Todo] = []

    rows = connection.execute(
        "SELECT * FROM redemptions WHERE status = 'approved' ORDER BY decided_at, id"
    )
    for row in rows:
        reward = rewards.by_id(str(row["reward_id"]))
        dollars = cash.dollars_of(row["fulfilment_ref"])
        items.append(
            Todo(
                ref=f"redemption:{int(row['id'])}",
                kind="cash" if dollars > 0 else "manual",
                kid_id=str(row["kid_id"]),
                title=reward.name if reward is not None else str(row["reward_id"]),
                dollars=dollars or None,
                reward_id=str(row["reward_id"]),
            )
        )

    reminders = connection.execute(
        "SELECT key, value FROM settings_runtime WHERE key LIKE ? ORDER BY key",
        (f"{ALLOWANCE_PREFIX}%",),
    )
    for row in reminders:
        try:
            held = json.loads(str(row["value"]))
            due = Date.fromisoformat(str(held["due"]))
        except (ValueError, KeyError, TypeError):
            continue
        if due > today:
            continue  # not yet owed
        items.append(
            Todo(
                ref=str(row["key"]),
                kind="allowance",
                kid_id=str(held["kid_id"]),
                title="Allowance",
                day=int(held["day"]),
                days=int(held["days"]),
                due=due,
            )
        )
    return items


def finish(connection: sqlite3.Connection, ref: str, *, now: datetime) -> None:
    """A parent ticking off something they have now actually done."""
    if ref.startswith(ALLOWANCE_PREFIX):
        removed = connection.execute("DELETE FROM settings_runtime WHERE key = ?", (ref,))
        if removed.rowcount == 0:
            raise ClaimError(404, f"no reminder {ref!r}")
        # The last day paid finishes the redemption it came from.
        redemption_id = ref.split(":")[1]
        left = connection.execute(
            "SELECT COUNT(*) AS n FROM settings_runtime WHERE key LIKE ?",
            (f"{ALLOWANCE_PREFIX}{redemption_id}:%",),
        ).fetchone()["n"]
        if int(left) == 0:
            connection.execute(
                "UPDATE redemptions SET status = 'fulfilled' WHERE id = ?", (redemption_id,)
            )
        return

    if not ref.startswith("redemption:"):
        raise ClaimError(400, f"not something to tick off: {ref!r}")
    redemption_id = ref.split(":")[1]
    row = _row(connection, int(redemption_id))
    if row is None:
        raise ClaimError(404, f"no redemption {redemption_id}")
    if cash.dollars_of(row["fulfilment_ref"]) > 0:
        # Paid: the money handed over is a payout against this reward.
        cash.pay_for(connection, int(redemption_id), now=now)
        return
    connection.execute(
        "UPDATE redemptions SET status = 'fulfilled', fulfilment_ref = ? WHERE id = ?",
        (now.isoformat(), redemption_id),
    )


def for_kid(connection: sqlite3.Connection, rewards: Rewards, kid_id: str) -> list[Redemption]:
    """Everything this kid has asked for, newest first."""
    rows = connection.execute(
        "SELECT * FROM redemptions WHERE kid_id = ? ORDER BY requested_at DESC, id DESC",
        (kid_id,),
    )
    return [_model(row, rewards) for row in rows]


def retire_meal_rewards(
    connection: sqlite3.Connection, rewards: Rewards, *, now: datetime
) -> int:
    """Meal picks are free now; a meal reward still held gives its points back.

    Any redemption of a meal reward that rewards.yaml has switched off, and
    that was asked for or approved but not yet spent on a pick, is refunded —
    as its own ledger row, never an edit — and marked refunded. Idempotent.
    Returns how many were refunded.
    """
    retired = {
        reward.id
        for reward in rewards.rewards
        if reward.fulfilment == "meal" and not reward.enabled
    }
    if not retired:
        return 0
    held = connection.execute(
        "SELECT * FROM redemptions WHERE status IN ('requested', 'approved', 'scheduled')"
        f" AND reward_id IN ({', '.join('?' for _ in retired)})",
        tuple(sorted(retired)),
    ).fetchall()
    for row in held:
        ledger.refund(
            connection,
            kid_id=str(row["kid_id"]),
            points=int(row["points"]),
            reason_ref=f"redemption:{int(row['id'])}",
            now=now,
            note="Meal picks are free now",
        )
        connection.execute(
            "UPDATE redemptions SET status = 'refunded', decided_at = ? WHERE id = ?",
            (now.isoformat(), int(row["id"])),
        )
    return len(held)
