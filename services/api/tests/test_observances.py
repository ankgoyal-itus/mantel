"""Holidays and festivals: collected, de-duplicated, kept off the agenda."""

from __future__ import annotations

from datetime import date as Date
from zoneinfo import ZoneInfo

from mantel_api.calendars import expand
from mantel_api.models import CalendarEvent, CalendarFeed
from mantel_api.observances import by_date, normalise

ZONE = ZoneInfo("America/Los_Angeles")

USA = CalendarFeed(id="us_holidays", kind="holiday", url="https://example.test/us.ics")
INDIA = CalendarFeed(id="india_holidays", kind="festival", url="https://example.test/in.ics")
HINDU = CalendarFeed(id="hindu_holidays", kind="festival", url="https://example.test/hi.ics")
KIDS = CalendarFeed(id="mira", kind="kid", kid="mira", url_env="MANTEL_CAL_MIRA")

KINDS = {"us_holidays": "holiday", "india_holidays": "festival",
         "hindu_holidays": "festival", "mira": "kid"}


def ics(*events: tuple[str, str, str]) -> str:
    body = "\n".join(
        f"BEGIN:VEVENT\nUID:{uid}\nSUMMARY:{summary}\n"
        f"DTSTART;VALUE=DATE:{start}\nDTEND;VALUE=DATE:{start}\nEND:VEVENT"
        for uid, summary, start in events
    )
    return f"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//test//EN\n{body}\nEND:VCALENDAR\n"


US_FEED = ics(("1", "Veterans Day", "20261111"), ("2", "Thanksgiving Day", "20261126"))
INDIA_FEED = ics(("3", "Diwali/Deepavali", "20261108"), ("4", "Dussehra", "20261020"))
HINDU_FEED = ics(("5", "Diwali/Deepavali", "20261108"), ("6", "Govardhan Puja", "20261109"))
KID_FEED = ics(("7", "Picture day", "20261108"))


def events_of(text: str, feed: CalendarFeed) -> list[CalendarEvent]:
    return expand(text, feed, Date(2026, 10, 1), Date(2026, 12, 31), ZONE)


def test_normalise() -> None:
    assert normalise("Diwali/Deepavali") == normalise("Diwali / Deepavali")
    assert normalise(" Dussehra ") == "dussehra"
    assert normalise("Diwali") != normalise("Dussehra")


def test_collects_by_day() -> None:
    found = by_date(events_of(US_FEED, USA), KINDS)
    assert [o.name for o in found[Date(2026, 11, 26)]] == ["Thanksgiving Day"]
    assert found[Date(2026, 11, 11)][0].kind == "holiday"


def test_de_dups_across_the_two_indian_feeds() -> None:
    # Diwali is in both, and must be one observance, not two.
    events = events_of(INDIA_FEED, INDIA) + events_of(HINDU_FEED, HINDU)
    found = by_date(events, KINDS)

    diwali = found[Date(2026, 11, 8)]
    assert [o.name for o in diwali] == ["Diwali/Deepavali"]
    assert diwali[0].calendar_id == "india_holidays", "the first feed listed wins"

    # A festival only one of them carries still comes through.
    assert [o.name for o in found[Date(2026, 11, 9)]] == ["Govardhan Puja"]


def test_a_kid_calendar_is_not_an_observance() -> None:
    found = by_date(events_of(KID_FEED, KIDS), KINDS)
    assert found == {}
