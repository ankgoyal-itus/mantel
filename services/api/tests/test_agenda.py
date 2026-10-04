"""GET /api/agenda"""

from __future__ import annotations

from datetime import date as Date

from fastapi.testclient import TestClient

from mantel_api.models import CalendarEvent
from mantel_api.today import merge_agenda


def test_agenda_returns_the_requested_range(client: TestClient) -> None:
    body = client.get("/api/agenda?from=2026-09-28&days=3").json()

    assert [day["date"] for day in body] == ["2026-09-28", "2026-09-29", "2026-09-30"]
    assert [day["weekday"] for day in body] == ["mon", "tue", "wed"]

    tuesday = body[1]
    mira = next(entry for entry in tuesday["kids"] if entry["id"] == "mira")
    assert [item["title"] for item in mira["agenda"]] == ["Piano"]


def test_agenda_is_capped_at_fourteen_days(client: TestClient) -> None:
    body = client.get("/api/agenda?from=2026-09-28&days=30").json()

    assert len(body) == 14
    assert body[0]["date"] == "2026-09-28"
    assert body[-1]["date"] == "2026-10-11"


def test_agenda_defaults_to_a_week_from_today(client: TestClient) -> None:
    body = client.get("/api/agenda").json()

    assert len(body) == 7


class TestOneEventFromTwoFeeds:
    """A district's early-release week, carried by the district's feed and
    again by the school's own: one row per child per day, not two."""

    @staticmethod
    def event(feed: str, title: str, start: str | None = None) -> CalendarEvent:
        return CalendarEvent(
            calendar_id=feed,
            kid="kabir",
            source="school",
            date=Date(2026, 10, 12),
            title=title,
            start=start,
            all_day=start is None,
        )

    def test_the_same_all_day_event_is_shown_once(self) -> None:
        merged = merge_agenda(
            [],
            Date(2026, 10, 12),
            [
                self.event("district", "Conference Week - Early Release (TK-5)"),
                self.event("bayside", "Conference week -  early release (TK-5)"),
            ],
        )
        assert [entry.title for entry in merged] == ["Conference Week - Early Release (TK-5)"]

    def test_the_first_feed_keeps_it(self) -> None:
        merged = merge_agenda(
            [],
            Date(2026, 10, 12),
            [self.event("district", "Picture day"), self.event("bayside", "Picture day")],
        )
        assert [entry.calendar_id for entry in merged] == ["district"]

    def test_the_same_title_at_another_time_is_another_event(self) -> None:
        merged = merge_agenda(
            [],
            Date(2026, 10, 12),
            [
                self.event("bayside", "Band practice", "15:15"),
                self.event("bayside", "Band practice", "17:00"),
            ],
        )
        assert [entry.start for entry in merged] == ["15:15", "17:00"]
