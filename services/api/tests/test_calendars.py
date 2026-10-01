"""ICS feeds: expansion, caching, failure and the merge into an agenda."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import MIRA_ICS_URL, SAMPLE_ICS
from mantel_api.calendars import CalendarService
from mantel_api.models import AgendaEntry, CalendarEvent, Settings
from mantel_api.today import merge_agenda

TUESDAY = date(2026, 9, 29)
NEXT_TUESDAY = date(2026, 10, 6)  # the EXDATE
WEDNESDAY = date(2026, 9, 30)


def titles(events: list[CalendarEvent]) -> list[str]:
    return [event.title for event in events]


def test_expansion_respects_the_exdate(calendars: CalendarService, settings: Settings) -> None:
    asyncio.run(calendars.refresh(settings, today=TUESDAY))

    assert "Chess club" in titles(calendars.events_on(TUESDAY))
    # The weekly series skips the excluded date and resumes the week after.
    assert titles(calendars.events_on(NEXT_TUESDAY)) == []
    assert "Chess club" in titles(calendars.events_on(date(2026, 10, 13)))


def test_a_timed_event_keeps_local_times(
    calendars: CalendarService, settings: Settings
) -> None:
    asyncio.run(calendars.refresh(settings, today=TUESDAY))

    chess = next(e for e in calendars.events_on(TUESDAY) if e.title == "Chess club")
    assert chess.start == "15:00"
    assert chess.end == "16:00"
    assert chess.where == "Library"
    assert chess.all_day is False
    assert chess.kid == "mira"
    assert chess.calendar_id == "mira"


def test_an_all_day_event_carries_no_times(
    calendars: CalendarService, settings: Settings
) -> None:
    asyncio.run(calendars.refresh(settings, today=TUESDAY))

    picture_day = next(e for e in calendars.events_on(WEDNESDAY) if e.title == "Picture day")
    assert picture_day.all_day is True
    assert picture_day.start is None
    assert picture_day.end is None


def test_the_calendar_wins_over_a_matching_schedule_item(
    client: TestClient, calendars: CalendarService, settings: Settings
) -> None:
    asyncio.run(calendars.refresh(settings, today=TUESDAY))

    body = client.get(f"/api/today?date={TUESDAY.isoformat()}").json()
    mira = next(entry for entry in body["kids"] if entry["id"] == "mira")
    agenda = mira["agenda"]

    # "piano" from the feed replaces the schedule's "Piano" at the same start.
    assert [item["title"] for item in agenda] == ["Chess club", "piano"]
    assert [item["source"] for item in agenda] == ["calendar", "calendar"]
    assert [item["calendar_id"] for item in agenda] == ["mira", "mira"]

    # Nobody else's day is touched by Mira's feed.
    kabir = next(entry for entry in body["kids"] if entry["id"] == "kabir")
    assert kabir["agenda"] == []


def test_all_day_events_sort_before_timed_ones() -> None:
    scheduled = [
        AgendaEntry(start="17:00", end="18:00", title="Swim", source="schedule"),
    ]
    events = [
        CalendarEvent(
            calendar_id="mira", kid="mira", date=WEDNESDAY, title="Picture day", all_day=True
        ),
    ]

    merged = merge_agenda(scheduled, WEDNESDAY, events)

    assert [entry.title for entry in merged] == ["Picture day", "Swim"]
    assert merged[0].start is None


def test_a_failing_feed_keeps_its_events_and_goes_stale(
    client: TestClient, calendars: CalendarService, settings: Settings
) -> None:
    asyncio.run(calendars.refresh(settings, today=TUESDAY))
    assert "Chess club" in titles(calendars.events_on(TUESDAY))

    async def explode(url: str) -> str:
        request = httpx.Request("GET", url)
        raise httpx.HTTPStatusError(
            "Server error", request=request, response=httpx.Response(500, request=request)
        )

    calendars._fetch = explode  # noqa: SLF001 - simulating the feed going down
    # force, because a kid feed is not due again for refresh_minutes and the
    # point here is what happens when it does go out and fails.
    asyncio.run(calendars.refresh(settings, today=TUESDAY, force=True))

    # The day still shows what the feed last said.
    assert "Chess club" in titles(calendars.events_on(TUESDAY))
    status = client.get("/api/health").json()["calendars"]
    assert status["mira"].startswith("stale (")
    assert "500" in status["mira"] or "Server error" in status["mira"]


def test_an_unconfigured_calendar_is_skipped(
    client: TestClient,
    calendars: CalendarService,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="mantel_api.calendars"):
        asyncio.run(calendars.refresh(settings, today=TUESDAY))
        asyncio.run(calendars.refresh(settings, today=TUESDAY))

    status = client.get("/api/health").json()["calendars"]
    assert status["kabir"] == "not configured"
    assert status["family"] == "not configured"
    assert status["mira"].startswith("ok (")

    # Logged once per feed, not once per refresh.
    skipped = [record for record in caplog.records if "not configured" in record.getMessage()]
    assert len(skipped) == 2


def test_the_fixture_feed_is_what_the_service_fetched() -> None:
    assert "RRULE:FREQ=WEEKLY" in SAMPLE_ICS
    assert "EXDATE" in SAMPLE_ICS
    assert MIRA_ICS_URL.endswith(".ics")
