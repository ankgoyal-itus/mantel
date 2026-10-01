"""School days derived from a district feed, never from content/."""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from mantel_api.calendars import expand
from mantel_api.models import CalendarFeed, SchoolYear
from mantel_api.school import SchoolService, derive, minimum_note, note_from

ZONE = ZoneInfo("America/Los_Angeles")

DISTRICT = CalendarFeed(id="district", kind="school", kid="family", url="https://example.test/d.ics")
SCHOOL = CalendarFeed(id="sunset", kind="school", kid="kabir", url="https://example.test/s.ics")


def ics(*events: str) -> str:
    body = "\n".join(events)
    return f"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//test//EN\n{body}\nEND:VCALENDAR\n"


def all_day(uid: str, summary: str, start: str, end: str) -> str:
    """An all-day event, with the exclusive DTEND a real feed sends."""
    return (
        f"BEGIN:VEVENT\nUID:{uid}\nSUMMARY:{summary}\n"
        f"DTSTART;VALUE=DATE:{start}\nDTEND;VALUE=DATE:{end}\nEND:VEVENT"
    )


def timed(uid: str, summary: str, start: str, end: str) -> str:
    return (
        f"BEGIN:VEVENT\nUID:{uid}\nSUMMARY:{summary}\n"
        f"DTSTART:{start}\nDTEND:{end}\nEND:VEVENT"
    )


#: An invented 2026-27 district year, in the shape a Finalsite feed sends it:
#: the bounds, a single day off, an early-release week, three breaks, a board
#: meeting and a high-school-only evening.
DISTRICT_YEAR = ics(
    all_day("1", "First Day of School", "20260819", "20260820"),
    all_day("2", "No School - Staff Development Day", "20261016", "20261017"),
    all_day("3", "Conference Week - Early Release (TK-5)", "20261012", "20261017"),
    all_day("4", "No School - Thanksgiving Break", "20261123", "20261128"),
    all_day("5", "No School - Winter Break", "20261221", "20270102"),
    all_day("6", "No School - Spring Break", "20270329", "20270403"),
    all_day("7", "Last Day of School", "20270603", "20270604"),
    timed("8", "School Board Meeting", "20260902T180000", "20260902T200000"),
    all_day("9", "Back to School Night - High Schools", "20260827", "20260828"),
)


@pytest.fixture
def year() -> SchoolYear:
    events = expand(DISTRICT_YEAR, DISTRICT, Date(2026, 8, 1), Date(2027, 7, 1), ZONE)
    return derive(events, ["district"])


class TestDeriving:
    def test_finds_the_year_bounds(self, year: SchoolYear) -> None:
        assert year.first_day == Date(2026, 8, 19)
        assert year.last_day == Date(2027, 6, 3)

    def test_a_break_blocks_every_day_it_spans(self, year: SchoolYear) -> None:
        # DTEND is exclusive: 23rd to 28th is the 23rd through the 27th.
        for day in range(23, 28):
            assert Date(2026, 11, day) in year.no_school, day
        assert Date(2026, 11, 28) not in year.no_school

    def test_names_the_break(self, year: SchoolYear) -> None:
        assert year.no_school[Date(2026, 11, 25)] == "Thanksgiving Break"
        assert year.no_school[Date(2026, 10, 16)] == "Staff Development Day"
        assert year.no_school[Date(2026, 12, 31)] == "Winter Break"
        assert year.no_school[Date(2027, 4, 1)] == "Spring Break"

    def test_a_minimum_day_is_still_a_school_day(self, year: SchoolYear) -> None:
        assert Date(2026, 10, 12) in year.minimum_days
        assert Date(2026, 10, 12) not in year.no_school
        # The district says which grades, so the note does too.
        assert year.minimum_days[Date(2026, 10, 12)] == "Minimum day (TK-5)"

    def test_ordinary_events_are_not_days_off(self, year: SchoolYear) -> None:
        assert Date(2026, 9, 2) not in year.no_school  # a board meeting
        assert Date(2026, 8, 27) not in year.no_school  # back to school night

    def test_note_and_minimum_note(self) -> None:
        assert note_from("No School - Winter Break") == "Winter Break"
        assert note_from("No School") == "No school"
        assert minimum_note("Early Release TK-8") == "Minimum day (TK-8)"
        assert minimum_note("Early Release") == "Minimum day"


class TestTheService:
    @pytest.fixture
    def service(self, tmp_path: Path) -> SchoolService:
        service = SchoolService(tmp_path / "school-year.json")
        service.update(
            expand(DISTRICT_YEAR, DISTRICT, Date(2026, 8, 1), Date(2027, 7, 1), ZONE), ["district"]
        )
        return service

    def test_the_acceptance_days(self, service: SchoolService) -> None:
        assert service.day(Date(2026, 11, 25)) == (False, "Thanksgiving Break")
        assert service.day(Date(2027, 6, 15)) == (False, "Summer")
        assert service.day(Date(2026, 10, 16)) == (False, "Staff Development Day")

    def test_an_ordinary_wednesday_is_a_school_day(self, service: SchoolService) -> None:
        assert service.day(Date(2026, 9, 16)) == (True, None)

    def test_a_weekend_is_not(self, service: SchoolService) -> None:
        assert service.day(Date(2026, 9, 19)) == (False, None)

    def test_a_minimum_day_reads_as_a_school_day_with_a_note(
        self, service: SchoolService
    ) -> None:
        assert service.day(Date(2026, 10, 13)) == (True, "Minimum day (TK-5)")

    def test_before_the_first_day_is_summer(self, service: SchoolService) -> None:
        assert service.day(Date(2026, 8, 3)) == (False, "Summer")

    def test_the_cache_round_trips(self, service: SchoolService, tmp_path: Path) -> None:
        assert service.cache_path.is_file()
        reopened = SchoolService(tmp_path / "school-year.json")
        assert reopened.day(Date(2026, 11, 25)) == (False, "Thanksgiving Break")
        assert reopened.year.first_day == Date(2026, 8, 19)

    def test_a_feed_outage_changes_nothing(self, service: SchoolService, tmp_path: Path) -> None:
        # A 500 means no events at all; the cached year has to survive it.
        service.update([], ["district"])
        assert service.day(Date(2026, 11, 25)) == (False, "Thanksgiving Break")

        reopened = SchoolService(tmp_path / "school-year.json")
        assert reopened.day(Date(2026, 11, 25)) == (False, "Thanksgiving Break")

    def test_bounds_are_kept_when_a_later_feed_drops_them(
        self, service: SchoolService
    ) -> None:
        # Next year's feed, published before its first-day event exists.
        partial = ics(all_day("90", "No School - Some Day", "20271115", "20271116"))
        service.update(expand(partial, DISTRICT, Date(2027, 1, 1), Date(2028, 1, 1), ZONE), ["x"])
        assert service.year.first_day == Date(2026, 8, 19)
        assert service.year.last_day == Date(2027, 6, 3)

    def test_a_school_can_add_a_day_off_but_not_remove_one(self, service: SchoolService) -> None:
        both = expand(DISTRICT_YEAR, DISTRICT, Date(2026, 8, 1), Date(2027, 7, 1), ZONE)
        own = ics(all_day("50", "No School - Site Closure", "20260916", "20260917"))
        both += expand(own, SCHOOL, Date(2026, 8, 1), Date(2027, 7, 1), ZONE)
        service.update(both, ["district", "sunset"])

        assert service.day(Date(2026, 9, 16)) == (False, "Site Closure")
        # And the district's own days off are untouched.
        assert service.day(Date(2026, 11, 25))[0] is False

    def test_without_any_feed_every_weekday_is_a_school_day(self, tmp_path: Path) -> None:
        empty = SchoolService(tmp_path / "none.json")
        assert empty.status() == "bounds unknown"
        assert empty.day(Date(2026, 9, 16)) == (True, None)
        assert empty.day(Date(2026, 9, 19)) == (False, None)


class TestDerivingTheFirstDay:
    """A year with an end and no beginning.

    The district stops publishing "First Day of School" once term is under
    way, so from about September the feed has a last day and no first — and
    without a first day, every date before today reads as Summer.
    """

    @pytest.fixture
    def partial(self, tmp_path: Path) -> SchoolService:
        # The same year, with the opening event already out of the window.
        feed = ics(
            all_day("2", "No School - Thanksgiving Break", "20261123", "20261128"),
            all_day("3", "Last Day of School", "20270603", "20270604"),
        )
        service = SchoolService(tmp_path / "school-year.json")
        service.update(
            expand(feed, DISTRICT, Date(2026, 9, 1), Date(2027, 9, 1), ZONE), ["district"]
        )
        return service

    def test_works_a_first_day_back_from_the_last(self, partial: SchoolService) -> None:
        assert partial.year.last_day == Date(2027, 6, 3)
        assert partial.year.first_day == Date(2026, 8, 17)
        assert partial.year.first_day_derived is True

    def test_says_so_in_health(self, partial: SchoolService) -> None:
        assert partial.status().startswith("2026-08-17 (derived)..2027-06-03")

    def test_term_time_is_not_summer(self, partial: SchoolService) -> None:
        # The bug this fixes: with no first day, September read as Summer.
        assert partial.day(Date(2026, 9, 16)) == (True, None)
        assert partial.day(Date(2026, 11, 25))[0] is False
        assert partial.day(Date(2027, 7, 15)) == (False, "Summer")

    def test_a_real_first_day_replaces_the_derived_one(self, partial: SchoolService) -> None:
        # Next July, when the new year's calendar is published.
        following = ics(
            all_day("9", "First Day of School", "20270818", "20270819"),
            all_day("10", "Last Day of School", "20280601", "20280602"),
        )
        partial.update(
            expand(following, DISTRICT, Date(2027, 6, 1), Date(2028, 6, 1), ZONE), ["district"]
        )
        assert partial.year.first_day == Date(2027, 8, 18)
        assert partial.year.first_day_derived is False
        assert "(derived)" not in partial.status()

    def test_a_derived_day_survives_a_feed_outage(
        self, partial: SchoolService, tmp_path: Path
    ) -> None:
        partial.update([], ["district"])
        reopened = SchoolService(tmp_path / "school-year.json")
        assert reopened.year.first_day == Date(2026, 8, 17)
        assert reopened.year.first_day_derived is True

    def test_nothing_is_derived_without_a_last_day(self, tmp_path: Path) -> None:
        feed = ics(all_day("1", "No School - Some Day", "20261115", "20261116"))
        service = SchoolService(tmp_path / "none.json")
        service.update(expand(feed, DISTRICT, Date(2026, 9, 1), Date(2027, 1, 1), ZONE), ["x"])
        assert service.year.first_day is None
        assert service.status() == "bounds unknown"
