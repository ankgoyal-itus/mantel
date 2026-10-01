"""What a kid is saving for: up to two rewards, marked in the shop.

A balance on its own is a number. A balance against something they want is a
reason to load the dishwasher, and it is the difference between a points
system a child tolerates and one they use. So the card carries a bar per pick
rather than a second number.

Two, not one and not all of them: one is a wish and nine is a catalogue. Two
is a choice, which is the part worth teaching.

Kept in settings_runtime, like the allowance reminders: it is a short list of
reward ids per child, read on every dashboard poll and written when a child
taps a star in the shop. Nothing joins against it.
"""

from __future__ import annotations

import json
import sqlite3

from .models import Rewards, SavingFor

#: One is a wish, nine is a catalogue.
MAX_PICKS = 2

PREFIX = "saving"


def key(kid_id: str) -> str:
    return f"{PREFIX}:{kid_id}"


def ids(connection: sqlite3.Connection, kid_id: str) -> list[str]:
    """The reward ids this kid has marked, oldest first."""
    row = connection.execute(
        "SELECT value FROM settings_runtime WHERE key = ?", (key(kid_id),)
    ).fetchone()
    if row is None:
        return []
    try:
        held = json.loads(str(row["value"]))
    except json.JSONDecodeError:
        return []
    return [str(one) for one in held] if isinstance(held, list) else []


def set_ids(connection: sqlite3.Connection, kid_id: str, chosen: list[str]) -> list[str]:
    """Replace the list, keeping the order and the cap.

    Duplicates collapse rather than erroring: a child double-tapping a star is
    not a thing to be told off about.
    """
    seen: list[str] = []
    for one in chosen:
        if one not in seen:
            seen.append(one)
    seen = seen[:MAX_PICKS]
    connection.execute(
        """
        INSERT INTO settings_runtime (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key(kid_id), json.dumps(seen)),
    )
    return seen


def toggle(connection: sqlite3.Connection, kid_id: str, reward_id: str) -> list[str]:
    """Star it, or unstar it. A third pick pushes the oldest one off.

    Pushing rather than refusing: a child who has changed their mind should
    not have to work out which of the two to give up first, and the one they
    marked longest ago is the one they have gone off.
    """
    held = ids(connection, kid_id)
    if reward_id in held:
        held.remove(reward_id)
    else:
        held.append(reward_id)
        held = held[-MAX_PICKS:]
    return set_ids(connection, kid_id, held)


def summary(connection: sqlite3.Connection, kid_id: str, rewards: Rewards) -> list[SavingFor]:
    """The picks with their names and costs, for the card to draw bars from.

    A reward that has been taken out of rewards.yaml since it was marked is
    dropped rather than shown as a blank bar.
    """
    found: list[SavingFor] = []
    for reward_id in ids(connection, kid_id):
        reward = rewards.by_id(reward_id)
        if reward is None:
            continue
        found.append(
            SavingFor(
                reward_id=reward.id, name=reward.name, glyph=reward.glyph, cost=reward.cost
            )
        )
    return found
