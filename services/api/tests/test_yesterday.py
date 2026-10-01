"""The flag behind the picker's "Same as yesterday" tile.

The tile is the one tap that answers "the usual": a child who wants what they
had this morning should not have to find it in thirty rows. It was drawn but
never appeared, and nothing here covered the flag it reads, so this is that
cover — including the slot where it correctly never fires.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

from mantel_api import picks
from mantel_api.models import Dish, MealsCatalog

DAY = Date(2026, 10, 7)

CATALOG = MealsCatalog(
    version=1,
    dishes=[
        Dish(
            id="poha", name="Poha", slot="breakfast", protein=["veg"], cuisine="indian", minutes=15
        ),
        Dish(
            id="idli",
            name="Idli",
            slot="breakfast",
            protein=["veg"],
            cuisine="south_indian",
            minutes=20,
        ),
        Dish(
            id="dal_rice",
            name="Dal rice",
            slot="lunch",
            protein=["veg"],
            cuisine="indian",
            minutes=25,
        ),
        Dish(
            id="makhani",
            name="Makhani night",
            slot="dinner",
            protein=["veg", "chicken"],
            cuisine="indian",
            minutes=40,
        ),
    ],
)


class Meals:
    """Just enough of the plan for `options`: what was in each slot, by date."""

    def __init__(self, **by_slot: str | None) -> None:
        self._by_slot = by_slot

    def on(self, _day: Date) -> Any:
        return SimpleNamespace(
            **{
                slot: SimpleNamespace(id=value) if value else None
                for slot, value in {
                    "breakfast": None,
                    "lunch": None,
                    "dinner": None,
                    **self._by_slot,
                }.items()
            }
        )


def offered(meals: Meals, slot: Any) -> list[Any]:
    return picks.options(CATALOG, meals, slot=slot, day=DAY, non_veg_ok=True)


def test_yesterdays_breakfast_comes_back_as_one_tap() -> None:
    options = offered(Meals(breakfast="poha"), "breakfast")
    marked = [option for option in options if option.yesterday]

    assert [option.id for option in marked] == ["poha"]
    # The tile only draws from what is pickable, so the flag is worth nothing
    # on a row the day's rules have already closed.
    assert marked[0].pickable


def test_it_marks_one_dish_and_not_the_rest() -> None:
    options = offered(Meals(breakfast="poha"), "breakfast")

    assert {option.id: option.yesterday for option in options} == {"poha": True, "idli": False}


def test_nothing_is_marked_when_the_plan_has_no_yesterday() -> None:
    # A slot a parent left empty, or one written as free text with no dish id.
    assert not any(option.yesterday for option in offered(Meals(), "breakfast"))


def test_yesterdays_dinner_is_offered_with_a_word_about_it() -> None:
    """The four-day rule is a warning now, not a wall: yesterday's dinner is
    still pickable, and says when the house last had it."""
    options = offered(Meals(dinner="makhani"), "dinner")
    makhani = next(option for option in options if option.id == "makhani")

    assert makhani.pickable
    assert makhani.yesterday
    assert makhani.warning == "we had this Tuesday"


def test_it_reads_the_day_before_the_one_being_planned() -> None:
    """The picker plans tomorrow, so "yesterday" is today, not actually yesterday."""
    seen: list[Date] = []

    class Recording(Meals):
        def on(self, day: Date) -> Any:
            seen.append(day)
            return super().on(day)

    offered(Recording(breakfast="poha"), "breakfast")

    assert DAY - timedelta(days=1) in seen
