"""Eating out: a meal that is a place rather than a dish.

"Dinner out" and "Lunch out" are catalog entries the house never has to
write: they are reserved here and always at the top of their pool, whatever
meals-catalog.yaml says, so a hand edit to the family's file can neither
lose them nor rename them. Each is a treat, so a child who picks one is
asking, and a parent says yes on Approvals like any other treat.

Where — "Taqueria Luna", "Corner Trattoria", "Grandma's house" — is optional and rides
in the `note` a meal or a pick already has: forty characters at most, and
the last ten distinct places used are kept for the chips above the field.
"""

from __future__ import annotations

import json
import sqlite3

from .models import Dish

DINNER_OUT = "dinner_out"
LUNCH_OUT = "lunch_out"
OUT_IDS = frozenset({DINNER_OUT, LUNCH_OUT})

#: The longest place a meal may carry.
MAX_PLACE = 40
#: How many recent places the chips offer.
RECENT = 10
KEY = "recent_places"

RESERVED: tuple[Dish, ...] = (
    Dish(
        id=LUNCH_OUT,
        name="Lunch out",
        slot="lunch",
        protein=["veg"],
        cuisine="Out",
        minutes=0,
        treat=True,
        glyph="storefront",
    ),
    Dish(
        id=DINNER_OUT,
        name="Dinner out",
        slot="dinner",
        protein=["veg"],
        cuisine="Out",
        minutes=0,
        treat=True,
        glyph="storefront",
    ),
)


def is_out(dish_id: str | None) -> bool:
    return dish_id in OUT_IDS


def with_reserved(dishes: list[Dish]) -> list[Dish]:
    """The catalog with Lunch out and Dinner out at the top of their pools.

    One the file already has is replaced by the reserved one, so its name,
    slot and treat flag can never drift from what the screens expect.
    """
    rest = [dish for dish in dishes if dish.id not in OUT_IDS]
    return [*RESERVED, *rest]


def clean_place(place: str | None) -> str | None:
    """A place as it is stored: trimmed, and nothing when there is nothing."""
    if place is None:
        return None
    text = " ".join(place.split())
    if len(text) > MAX_PLACE:
        raise ValueError(f"a place is at most {MAX_PLACE} characters")
    return text or None


def label(place: str | None) -> str:
    """"Out · Taqueria Luna", or just "Out"."""
    return f"Out · {place}" if place else "Out"


def recent(connection: sqlite3.Connection) -> list[str]:
    row = connection.execute(
        "SELECT value FROM settings_runtime WHERE key = ?", (KEY,)
    ).fetchone()
    if row is None:
        return []
    try:
        held = json.loads(str(row["value"]))
    except ValueError:
        return []
    return [str(place) for place in held if isinstance(place, str)][:RECENT]


def remember(connection: sqlite3.Connection, place: str | None) -> list[str]:
    """This place first, the same place (any case) only once, ten at most."""
    places = recent(connection)
    if place:
        places = [place, *(one for one in places if one.casefold() != place.casefold())]
        places = places[:RECENT]
        connection.execute(
            "INSERT INTO settings_runtime (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (KEY, json.dumps(places)),
        )
    return places
