"""The vegetarian calendar, computed from the festival feeds."""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from mantel_api.calendars import expand
from mantel_api.diet import DietService, compute, reason_text
from mantel_api.models import CalendarFeed, DietDay, Observance, Settings
from mantel_api.observances import by_date

ZONE = ZoneInfo("America/Los_Angeles")

Observed = dict[Date, list[Observance]]
Table = dict[Date, DietDay]
FESTIVALS = CalendarFeed(id="india_holidays", kind="festival", url="https://example.test/in.ics")

RAW: dict[str, Any] = {
        "timezone": "America/Los_Angeles",
        "location": {"name": "Half Moon Bay", "lat": 37.4636, "lon": -122.4286},
        "units": {"temp": "F"},
        "night": {"start": "21:00", "end": "06:30", "idle_minutes": 10, "frame": False},
        "idle_minutes": 3,
        "slide_seconds": 20,
        "refresh_minutes": 5,
        "daily_reload": "04:00",
        "calendars": [],
        "diet": {
            "non_veg_days": ["mon", "thu", "fri", "sun"],
            "no_non_veg_festivals": [
                {"match": "navratri", "span_days": 10},
                {"match": "dussehra"},
                {"match": "diwali", "span_days": 4},
                {"match": "karaka chaturthi"},
                {"match": "naraka chaturdasi", "span_days": 4},
                {"match": "govardhan"},
                {"match": "bhai d"},
            ],
        },
}


def settings_with(**diet_overrides: Any) -> Settings:
    """Settings with the diet block adjusted, through validation.

    model_copy(update=...) skips validation and would leave plain dicts where
    the models are expected, which is a confusing way to learn it.
    """
    raw = {**RAW, "diet": {**RAW["diet"], **diet_overrides}}
    return Settings.model_validate(raw)


SETTINGS = Settings.model_validate(RAW)

#: The real Google feed names Navratri once, on its first day.
FEED = """BEGIN:VCALENDAR
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
SUMMARY:Diwali/Deepavali
DTSTART;VALUE=DATE:20261108
DTEND;VALUE=DATE:20261109
END:VEVENT
BEGIN:VEVENT
UID:4
SUMMARY:Karaka Chaturthi
DTSTART;VALUE=DATE:20261029
DTEND;VALUE=DATE:20261030
END:VEVENT
BEGIN:VEVENT
UID:5
SUMMARY:Naraka Chaturdasi
DTSTART;VALUE=DATE:20261108
DTEND;VALUE=DATE:20261109
END:VEVENT
BEGIN:VEVENT
UID:6
SUMMARY:Govardhan Puja
DTSTART;VALUE=DATE:20261109
DTEND;VALUE=DATE:20261110
END:VEVENT
BEGIN:VEVENT
UID:7
SUMMARY:Bhai Duj
DTSTART;VALUE=DATE:20261111
DTEND;VALUE=DATE:20261112
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture
def observed() -> Observed:
    events = expand(FEED, FESTIVALS, Date(2026, 10, 1), Date(2027, 1, 1), ZONE)
    return by_date(events, {"india_holidays": "festival"})


OBSERVED_FOR_TEXT: Observed = {
    Date(2026, 10, 11): [
        Observance(
            name="First Day of Sharad Navratri",
            kind="festival",
            calendar_id="india_holidays",
        )
    ]
}


def days(observed: Observed, start: Date = Date(2026, 10, 1), span: int = 120) -> Table:
    return {entry.date: entry for entry in compute(SETTINGS, observed, start, span)}


class TestTheRules:
    def test_navratri_blocks_ten_days(self, observed: Observed) -> None:
        table = days(observed)
        for day in range(11, 21):
            entry = table[Date(2026, 10, day)]
            assert not entry.non_veg_ok, day
        # The day before is a Saturday: blocked by the weekday rule alone.
        assert table[Date(2026, 10, 10)].reasons == ["Saturday"]

    def test_a_monday_inside_navratri_gives_both_reasons(self, observed: Observed) -> None:
        # 2026-10-12 is a Monday, which is otherwise a meat day.
        entry = days(observed)[Date(2026, 10, 12)]
        assert not entry.non_veg_ok
        assert entry.reasons == ["Sharad Navratri · day 2 of 10"]

    def test_a_tuesday_is_blocked_by_the_weekday_alone(self, observed: Observed) -> None:
        entry = days(observed)[Date(2026, 12, 1)]
        assert not entry.non_veg_ok
        assert entry.reasons == ["Tuesday"]

    def test_a_tuesday_inside_a_festival_says_both(self, observed: Observed) -> None:
        # 2026-10-13 is a Tuesday inside Navratri.
        entry = days(observed)[Date(2026, 10, 13)]
        # The weekday is dropped: the festival is the reason a child cares
        # about, and "Tuesday" as well only makes the line longer.
        assert entry.reasons == ["Sharad Navratri · day 3 of 10"]

    def test_dussehra_is_named_in_its_own_right(self, observed: Observed) -> None:
        reasons = days(observed)[Date(2026, 10, 20)].reasons
        assert "Dussehra" in reasons

    def test_diwali_runs_four_days(self, observed: Observed) -> None:
        table = days(observed)
        assert not table[Date(2026, 11, 8)].non_veg_ok
        assert not table[Date(2026, 11, 11)].non_veg_ok
        # 2026-11-12 is a Thursday: back to a meat day once Diwali is over.
        assert table[Date(2026, 11, 12)].non_veg_ok

    def test_a_monday_outside_everything_is_fine(self, observed: Observed) -> None:
        entry = days(observed)[Date(2026, 12, 7)]
        assert entry.non_veg_ok and entry.reasons == []

    def test_an_exception_unblocks_a_day(self, observed: Observed) -> None:
        with_exception = settings_with(
            non_veg_ok_dates=[{"date": Date(2026, 10, 13), "reason": "birthday"}]
        )
        table = {e.date: e for e in compute(with_exception, observed, Date(2026, 10, 1), 60)}
        assert table[Date(2026, 10, 13)].non_veg_ok
        assert table[Date(2026, 10, 13)].reasons == []
        # Its neighbours are untouched.
        assert not table[Date(2026, 10, 14)].non_veg_ok

    def test_the_festivals_the_feed_names_differently(self, observed: Observed) -> None:
        # The feed says "Karaka Chaturthi"; the family says Karwa Chauth. The
        # rule has to match what the feed actually carries.
        table = days(observed)
        assert not table[Date(2026, 10, 29)].non_veg_ok
        assert "Karaka Chaturthi" in table[Date(2026, 10, 29)].reasons[-1]

    def test_choti_diwali_opens_four_days(self, observed: Observed) -> None:
        table = days(observed, Date(2026, 11, 1), 30)
        for day in range(8, 12):
            assert not table[Date(2026, 11, day)].non_veg_ok, day
        assert any("Govardhan" in r for r in table[Date(2026, 11, 9)].reasons)
        assert any("Bhai Duj" in r for r in table[Date(2026, 11, 11)].reasons)

    def test_an_extra_range_blocks_by_hand(self, observed: Observed) -> None:
        with_extra = settings_with(
            no_non_veg_dates_extra=[
                {"from": Date(2026, 12, 7), "to": Date(2026, 12, 8), "name": "Fast"}
            ]
        )
        table = {e.date: e for e in compute(with_extra, observed, Date(2026, 12, 1), 30)}
        assert table[Date(2026, 12, 7)].reasons == ["Fast"]


class TestTheService:
    def test_round_trips_through_the_cache(self, observed: Observed, tmp_path: Path) -> None:
        service = DietService(tmp_path / "diet-days.json")
        service.update(SETTINGS, observed, Date(2026, 10, 1), 120)
        assert not service.day(Date(2026, 10, 13)).non_veg_ok

        reopened = DietService(tmp_path / "diet-days.json")
        assert not reopened.day(Date(2026, 10, 13)).non_veg_ok
        assert reopened.day(Date(2026, 10, 13)).reasons[0] == "Sharad Navratri · day 3 of 10"

    def test_an_unknown_day_is_allowed_rather_than_guessed(self, tmp_path: Path) -> None:
        service = DietService(tmp_path / "none.json")
        assert service.day(Date(2030, 1, 1)).non_veg_ok

    def test_the_window_is_in_order(self, observed: Observed, tmp_path: Path) -> None:
        service = DietService(tmp_path / "diet-days.json")
        service.update(SETTINGS, observed, Date(2026, 10, 1), 30)
        window = service.window(Date(2026, 10, 1), 10)
        assert [entry.date for entry in window] == [
            Date(2026, 10, day) for day in range(1, 11)
        ]


class TestHowAReasonReads:
    """The text a nine-year-old sees, not the feed's name for the day."""

    def test_a_running_festival_names_itself_and_the_day(self) -> None:
        # Not "First Day of Sharad Navratri (day 3 of 10)", which asks the
        # reader to work out that the third day is not the first day.
        assert (
            reason_text("First Day of Sharad Navratri", 3, 10) == "Sharad Navratri · day 3 of 10"
        )

    def test_a_one_day_festival_is_just_its_name(self) -> None:
        assert reason_text("Dussehra", 1, 1) == "Dussehra"
        assert reason_text("Karaka Chaturthi", 1, 1) == "Karaka Chaturthi"

    def test_other_openers_are_stripped_too(self) -> None:
        assert reason_text("Start of Chaturmas", 2, 4) == "Chaturmas · day 2 of 4"

    def test_a_name_with_no_opener_is_left_alone(self) -> None:
        assert reason_text("Diwali/Deepavali", 2, 4) == "Diwali/Deepavali · day 2 of 4"

    def test_the_weekday_is_the_reason_only_when_it_is_the_whole_reason(self) -> None:
        observed: Observed = {}
        table = {e.date: e for e in compute(SETTINGS, observed, Date(2026, 12, 1), 3)}
        # A plain Tuesday with nothing else on it.
        assert table[Date(2026, 12, 1)].reasons == ["Tuesday"]

    def test_a_festival_on_a_veg_weekday_does_not_say_both(self) -> None:
        # Blocked either way; the festival is what anyone would ask about.
        computed = compute(SETTINGS, OBSERVED_FOR_TEXT, Date(2026, 10, 13), 1)
        entry = {e.date: e for e in computed}
        assert entry[Date(2026, 10, 13)].reasons == ["Sharad Navratri · day 3 of 10"]
        assert not entry[Date(2026, 10, 13)].non_veg_ok
