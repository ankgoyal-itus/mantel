"""GET /api/agenda"""

from __future__ import annotations

from fastapi.testclient import TestClient


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
