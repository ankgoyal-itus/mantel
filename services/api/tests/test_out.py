"""Dinner out: a meal that is a place, and the place it is."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_picks import CATALOG, PARENT_PIN, THURSDAY, dinner, pick, sign_in

from mantel_api import out
from mantel_api.db import Database
from mantel_api.models import MealsCatalog, MealSlot
from mantel_api.weekly import resolve_slot


@pytest.fixture(autouse=True)
def parent_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PARENT_PIN)


@pytest.fixture
def planned(client: TestClient, content_dir: Path) -> None:
    (content_dir / "meals-catalog.yaml").write_text(CATALOG, encoding="utf-8")
    (content_dir / "meals.yaml").write_text(
        f"{THURSDAY.isoformat()}:\n  dinner: {{id: rajma}}\n", encoding="utf-8"
    )
    client.app.state.content.load_all()  # type: ignore[attr-defined]


def set_out(client: TestClient, place: str | None, slot: str = "dinner") -> Any:
    return client.post(
        "/api/parent/meals/set",
        json={
            "date": THURSDAY.isoformat(),
            "slot": slot,
            "dish_id": f"{slot}_out",
            "place": place,
        },
    )


def test_the_catalog_always_has_them_at_the_top() -> None:
    catalog = MealsCatalog(version=1, dishes=[])
    assert [dish.id for dish in catalog.dishes] == ["lunch_out", "dinner_out"]
    dinner_out = catalog.dishes[1]
    assert (dinner_out.name, dinner_out.cuisine, dinner_out.treat, dinner_out.minutes) == (
        "Dinner out",
        "Out",
        True,
        0,
    )
    assert dinner_out.glyph == "storefront"


def test_a_place_longer_than_forty_is_refused(client: TestClient, planned: None) -> None:
    sign_in(client)
    assert set_out(client, "x" * 41).status_code == 422
    assert pick(client, "kabir", "dinner_out", place="y" * 41).status_code == 422
    assert set_out(client, "x" * 40).status_code == 200


def test_recent_places_hold_ten_and_do_not_repeat(database: Database) -> None:
    with database.write() as connection:
        for n in range(12):
            out.remember(connection, f"Place {n}")
        out.remember(connection, "place 3")
        held = out.recent(connection)
    assert len(held) == 10
    assert held[0] == "place 3"
    assert sum(1 for place in held if place.casefold() == "place 3") == 1


def test_an_out_cell_resolves_like_any_dish(client: TestClient, planned: None) -> None:
    sign_in(client)
    assert set_out(client, "Taqueria Luna").status_code == 200
    slot = dinner(client)
    assert slot["resolved"]["id"] == "dinner_out"
    assert slot["resolved"]["name"] == "Dinner out"
    assert slot["resolved"]["note"] == "Taqueria Luna"
    assert client.get("/api/places/recent").json() == ["Taqueria Luna"]
    # And through resolve_slot directly, as a plan with no picks.
    plan = MealSlot(name="Dinner out", id="dinner_out", note="Taqueria Luna")
    view = resolve_slot(THURSDAY, "dinner", plan, [], out_now())
    assert view.resolved == plan


def test_a_kids_dinner_out_waits_on_approvals_as_a_treat(
    client: TestClient, planned: None
) -> None:
    made = pick(client, "kabir", "dinner_out", place="Taqueria Luna")
    assert made.status_code == 200
    sign_in(client)
    treat = next(
        item for item in client.get("/api/parent/approvals").json() if item["kind"] == "treat"
    )
    assert (treat["kid_id"], treat["title"], treat["note"]) == (
        "kabir",
        "Dinner out",
        "Taqueria Luna",
    )
    assert client.post(f"/api/parent/picks/{treat['pick_id']}/approve").status_code == 200
    assert dinner(client)["resolved"]["note"] == "Taqueria Luna"


def test_the_kids_are_offered_dinner_out_but_not_lunch_out(
    client: TestClient, planned: None
) -> None:
    params = {"kid_id": "kabir", "date": THURSDAY.isoformat()}
    dinners = client.get("/api/picks/options", params={**params, "slot": "dinner"}).json()
    assert dinners[0]["id"] == "dinner_out" and dinners[0]["out"] is True
    lunches = client.get("/api/picks/options", params={**params, "slot": "lunch"}).json()
    assert "lunch_out" not in {one["id"] for one in lunches}


def test_the_digest_lists_the_days_out(client: TestClient, planned: None) -> None:
    sign_in(client)
    set_out(client, "Taqueria Luna")
    week = f"{THURSDAY.isocalendar()[0]}-W{THURSDAY.isocalendar()[1]:02d}"
    digest = client.get("/api/digest", params={"week": week}).json()
    assert "Thu dinner: Out · Taqueria Luna" in digest["out"]


def out_now() -> Any:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime(2026, 9, 24, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
