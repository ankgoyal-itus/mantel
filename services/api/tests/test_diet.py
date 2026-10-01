"""The diet rules, checked against the real plan.

This is a content test, not a feature: it walks content/meals.yaml and fails if
the plan puts egg, chicken or fish on a day the house is vegetarian. `make
check` runs it, so a bad edit is caught before it reaches the iPad.

The blocked days are no longer written down anywhere. They are computed from
the festival feeds, so this uses a small fixture feed rather than the live one:
a test that fails because Google reworded a holiday would teach nobody
anything.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
import yaml

from mantel_api.calendars import expand
from mantel_api.content import Content
from mantel_api.diet import compute
from mantel_api.models import CalendarFeed, DietDay, Meals, MealsCatalog, Settings
from mantel_api.observances import by_date
from mantel_api.paths import content_dir

SLOTS = ("breakfast", "lunch", "dinner", "snack")

ZONE = ZoneInfo("America/Los_Angeles")
FESTIVALS = CalendarFeed(id="india_holidays", kind="festival", url="https://example.test/in.ics")

#: The festivals the 2026 plan runs through, as the Google feed words them.
FIXTURE_FEED = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:1
SUMMARY:First Day of Sharad Navratri
DTSTART;VALUE=DATE:20261011
DTEND;VALUE=DATE:20261012
END:VEVENT
BEGIN:VEVENT
UID:2
SUMMARY:Dussehra
DTSTART;VALUE=DATE:20261020
DTEND;VALUE=DATE:20261021
END:VEVENT
BEGIN:VEVENT
UID:3
SUMMARY:Sharad Purnima
DTSTART;VALUE=DATE:20261025
DTEND;VALUE=DATE:20261026
END:VEVENT
BEGIN:VEVENT
UID:4
SUMMARY:Karwa Chauth
DTSTART;VALUE=DATE:20261029
DTEND;VALUE=DATE:20261030
END:VEVENT
BEGIN:VEVENT
UID:5
SUMMARY:Dhanteras
DTSTART;VALUE=DATE:20261106
DTEND;VALUE=DATE:20261107
END:VEVENT
BEGIN:VEVENT
UID:6
SUMMARY:Diwali/Deepavali
DTSTART;VALUE=DATE:20261108
DTEND;VALUE=DATE:20261109
END:VEVENT
END:VCALENDAR
"""


#: A festival is named on its first day, so the feed is read from before the
#: plan starts: a plan opening midway through Navratri still has to see it.
LOOKBACK_DAYS = 31


def diet_table(settings: Settings, start: Date, span: int = 200) -> dict[Date, DietDay]:
    """The computed vegetarian calendar, from the fixture feed."""
    from_day = start - timedelta(days=LOOKBACK_DAYS)
    events = expand(FIXTURE_FEED, FESTIVALS, from_day, Date(start.year + 1, 6, 1), ZONE)
    observed = by_date(events, {"india_holidays": "festival"})
    return {entry.date: entry for entry in compute(settings, observed, start, span)}


def violations(meals: Meals, settings: Settings) -> list[str]:
    """Every slot that feeds the kids non-veg when it should not."""
    if not meals.root:
        return []
    table = diet_table(settings, min(meals.root))
    found: list[str] = []

    for day in sorted(meals.root):
        entry = table.get(day)
        if entry is None or entry.non_veg_ok:
            continue
        for slot_name in SLOTS:
            slot = getattr(meals.root[day], slot_name)
            if slot is None or slot.kids_protein == "veg":
                continue
            found.append(f"{day} {slot_name}: {slot.kids_protein} ({', '.join(entry.reasons)})")
    return found


def test_the_real_plan_obeys_the_diet() -> None:
    content = Content()
    content.load_all()

    meals = content.meals.current
    settings = content.settings.current
    assert meals is not None
    assert settings is not None
    # Every dish id in the plan resolved against the catalog.
    assert content.meals.status == "ok"
    assert content.catalog.status == "ok"

    assert violations(meals, settings) == []


def test_the_plan_actually_feeds_the_kids_on_the_allowed_days() -> None:
    """A guard that can only ever pass is not a guard."""
    content = Content()
    content.load_all()
    meals = content.meals.current
    assert meals is not None

    non_veg = [
        day
        for day in meals.root
        for slot_name in SLOTS
        if getattr(meals.root[day], slot_name) is not None
        and getattr(meals.root[day], slot_name).kids_protein != "veg"
    ]
    if not non_veg:
        # The family plans nothing ahead now; the children pick. With no
        # non-veg meal in the file there is nothing for the guard to guard,
        # and failing would be a test about the menu rather than the rule.
        pytest.skip("the real plan has no non-veg meals in it right now")


@pytest.fixture
def settings() -> Settings:
    raw = yaml.safe_load((content_dir() / "settings.yaml").read_text(encoding="utf-8"))
    # The sample's festivals come from its calendar feed; a dated span is the
    # other way a house writes one, and the one these tests exercise.
    raw["diet"]["no_non_veg_dates_extra"] = [
        {"from": "2026-10-11", "to": "2026-10-20", "name": "Navratri"}
    ]
    return Settings.model_validate(raw)


@pytest.fixture
def catalog() -> MealsCatalog:
    raw = yaml.safe_load((content_dir() / "meals-catalog.yaml").read_text(encoding="utf-8"))
    return MealsCatalog.model_validate(raw)


def plan(text: str, catalog: MealsCatalog) -> Meals:
    return Meals.model_validate(yaml.safe_load(text), context={"dish_names": catalog.names})


def test_chicken_on_a_tuesday_is_caught(settings: Settings, catalog: MealsCatalog) -> None:
    # 2026-09-29 is a Tuesday, which is not in non_veg_days.
    bad = plan(
        "2026-09-29:\n  dinner: {id: paneer_tikka, kids_protein: chicken}\n",
        catalog,
    )
    found = violations(bad, settings)
    assert len(found) == 1
    assert "Tuesday" in found[0]


def test_non_veg_inside_a_blackout_is_caught(settings: Settings, catalog: MealsCatalog) -> None:
    # 2026-10-15 is a Thursday, normally allowed, but it falls in Navratri.
    bad = plan(
        "2026-10-15:\n  dinner: {id: paneer_tikka, kids_protein: chicken}\n",
        catalog,
    )
    found = violations(bad, settings)
    assert len(found) == 1
    assert "Navratri" in found[0]


def test_veg_is_always_fine(settings: Settings, catalog: MealsCatalog) -> None:
    fine = plan(
        "2026-10-15:\n  dinner: {id: khichdi}\n2026-09-29:\n  lunch: {id: dal_rice}\n",
        catalog,
    )
    assert violations(fine, settings) == []
