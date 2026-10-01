"""What each festival feed actually contributes, once de-duplication is done."""

from __future__ import annotations

from datetime import date as Date
from zoneinfo import ZoneInfo

from mantel_api.calendars import FeedState, expand
from mantel_api.models import CalendarEvent, CalendarFeed
from mantel_api.observances import by_date_counted

ZONE = ZoneInfo("America/Los_Angeles")
INDIA = CalendarFeed(id="india_holidays", kind="festival", url="https://example.test/in.ics")
HINDU = CalendarFeed(id="hindu_holidays", kind="festival", url="https://example.test/hi.ics")
KINDS = {"india_holidays": "festival", "hindu_holidays": "festival"}


def ics(*events: tuple[str, str, str]) -> str:
    body = "\n".join(
        f"BEGIN:VEVENT\nUID:{uid}\nSUMMARY:{summary}\n"
        f"DTSTART;VALUE=DATE:{start}\nDTEND;VALUE=DATE:{start}\nEND:VEVENT"
        for uid, summary, start in events
    )
    return f"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//test//EN\n{body}\nEND:VCALENDAR\n"


#: What the live feeds look like: the second is a subset of the first.
INDIA_FEED = ics(
    ("1", "Diwali/Deepavali", "20261108"),
    ("2", "Naraka Chaturdasi", "20261108"),
    ("3", "Govardhan Puja", "20261109"),
    ("4", "Karaka Chaturthi", "20261029"),
)
HINDU_FEED = ics(("5", "Diwali/Deepavali", "20261108"), ("6", "Karaka Chaturthi", "20261029"))


def events_of(text: str, feed: CalendarFeed) -> list[CalendarEvent]:
    return expand(text, feed, Date(2026, 10, 1), Date(2026, 12, 31), ZONE)


def test_counts_what_each_feed_contributed() -> None:
    events = events_of(INDIA_FEED, INDIA) + events_of(HINDU_FEED, HINDU)
    found, unique = by_date_counted(events, KINDS)

    assert unique["india_holidays"] == 4
    # Not an error: everything it has, the feed before it already had.
    assert unique["hindu_holidays"] == 0
    assert [o.name for o in found[Date(2026, 11, 8)]] == ["Diwali/Deepavali", "Naraka Chaturdasi"]


def test_a_feed_that_adds_something_is_counted_for_it() -> None:
    extra = ics(("7", "Kojagiri Purnima", "20261025"))
    events = events_of(INDIA_FEED, INDIA) + events_of(extra, HINDU)
    _, unique = by_date_counted(events, KINDS)
    assert unique["hindu_holidays"] == 1


def test_health_says_how_many_and_how_many_unique() -> None:
    state = FeedState(configured=True, events=[1, 2, 3], unique=0)  # type: ignore[list-item]
    status = state.status()
    assert "3 events" in status
    assert "0 unique" in status


def test_an_unconfigured_feed_says_nothing_about_counts() -> None:
    assert FeedState().status() == "not configured"
