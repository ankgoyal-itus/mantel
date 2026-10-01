"""The catalog, as a child may choose from it.

The picker offers the catalog narrowed two ways: to the slot, and to what the
diet rules allow on that date — a dish with no veg way to cook it is not
offered on a veg day, and its egg, chicken or fish versions only on the days
they are allowed. Beyond that everything is choosable. Two rules stay, said
rather than enforced silently: a treat needs a parent's OK and there are two
a week per child, and a dinner the house had inside four days is a warning
("we had this Tuesday"), not a wall.

Picks are free. Choosing what the house eats was once a reward bought with
points; it is now simply a thing children do, planned a week at a time and
settled by a parent when two of them want different dinners (weekly.py).
"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta
from typing import Any

from .models import Dish, DishSlot, MealsCatalog, PickOption, Protein
from .out import LUNCH_OUT, is_out

#: A kid's treats per week, whoever approved them.
MAX_TREATS_PER_WEEK = 2

#: A dinner inside this many days either side is worth a word.
NO_REPEAT_DINNER_DAYS = 4

#: Slots whose dishes are one menu: the family eats any of these at either
#: time, so a lunch dish is offered at dinner and a dinner dish at lunch. The
#: catalog still says where each dish was written, so they can be split
#: again with one line here.
SHARED_MENU: frozenset[str] = frozenset({"lunch", "dinner"})

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def allowed_proteins(dish: Dish, non_veg_ok: bool) -> list[Protein]:
    """What this dish could be on that day.

    Veg is always one of them. The rest are the kids' versions, and they are
    only on the table on the days the diet rules allow.
    """
    if non_veg_ok:
        return list(dish.protein)
    return [protein for protein in dish.protein if protein == "veg"]


def serves(dish: Dish, slot: str) -> bool:
    """Whether a dish may fill this slot: its own, or one it shares a menu with.
    Lunch out and Dinner out are each their own slot's only."""
    if is_out(dish.id):
        return dish.slot == slot
    return dish.slot == slot or (dish.slot in SHARED_MENU and slot in SHARED_MENU)


def week_of(day: Date) -> tuple[Date, Date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def recent_dinners(meals: Any, day: Date, days: int = NO_REPEAT_DINNER_DAYS) -> dict[str, Date]:
    """Dinner ids within `days` either side of a date, and the nearest day each
    was had on."""
    found: dict[str, Date] = {}
    for offset in sorted(range(-days, days + 1), key=abs):
        if offset == 0:
            continue
        other = day + timedelta(days=offset)
        cell = meals.on(other).dinner
        if cell is not None and cell.id and cell.id not in found:
            found[cell.id] = other
    return found


def eaten_before(meals: Any, day: Date, slot: DishSlot) -> str | None:
    """What was in that slot the day before, if anything."""
    cell = getattr(meals.on(day - timedelta(days=1)), slot, None)
    return str(cell.id) if cell is not None and cell.id else None


def options(
    catalog: MealsCatalog,
    meals: Any,
    *,
    slot: DishSlot,
    day: Date,
    non_veg_ok: bool,
    treats_used: int = 0,
    for_kid: bool = False,
) -> list[PickOption]:
    """Every dish this slot could be on that day, with anything worth saying.

    `meals` is the week as it resolves — plan and picks — so a repeat is
    judged against what the house is actually eating. `treats_used` is how
    many treats this child already has that week.
    """
    repeats = recent_dinners(meals, day) if slot == "dinner" else {}
    before = eaten_before(meals, day, slot)

    # The slot's own dishes first, then — for lunch and dinner, which share a
    # menu — the other one's, marked so the picker can put them under their
    # own header at the end rather than mixing the two lists.
    own = [dish for dish in catalog.dishes if dish.slot == slot]
    shared = [dish for dish in catalog.dishes if dish.slot != slot and serves(dish, slot)]

    offered: list[PickOption] = []
    for dish in [*own, *shared]:
        # A child may ask for dinner out; lunch out is the grown-ups' call.
        if for_kid and dish.id == LUNCH_OUT:
            continue
        proteins = allowed_proteins(dish, non_veg_ok)
        if not proteins:
            # An egg-only dish on a day with no eggs is not a choice, it is a
            # thing to be told no about.
            continue

        why: str | None = None
        if dish.treat and treats_used >= MAX_TREATS_PER_WEEK:
            why = "two treats a week is the deal"
        warning: str | None = None
        repeat_day: str | None = None
        if dish.id in repeats:
            repeat_day = WEEKDAY_NAMES[repeats[dish.id].weekday()]
            warning = f"we had this {repeat_day}"

        offered.append(
            PickOption(
                id=dish.id,
                name=dish.name,
                cuisine=dish.cuisine,
                treat=dish.treat,
                cost=0,
                proteins=proteins,
                pickable=why is None,
                why=why,
                warning=warning,
                repeat_day=repeat_day,
                yesterday=dish.id == before,
                also=dish.slot != slot,
                out=is_out(dish.id),
            )
        )
    return offered
