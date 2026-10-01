"""Meals picked a week at a time: what a slot resolves to, how a parent
settles two children who want different dinners, and the fences round it."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import yaml
from fastapi.testclient import TestClient

from mantel_api import ledger, weekly
from mantel_api.claims import ClaimError
from mantel_api.content import Content
from mantel_api.db import Database
from mantel_api.diet import DietCache, DietService
from mantel_api.models import DietDay, MealsCatalog

TZ = ZoneInfo("America/Los_Angeles")
PARENT_PIN = "2468"

#: A Thursday the family may have meat on, a Friday it may not, and the
#: Saturday after, which is allowed again. All well in the future, so
#: nothing locks during a test run.
THURSDAY = Date(2027, 1, 7)
FRIDAY = THURSDAY + timedelta(days=1)
SATURDAY = THURSDAY + timedelta(days=2)
TUESDAY = THURSDAY - timedelta(days=2)

CATALOG = """
version: 1
dishes:
  - {id: kanda_poha, name: Kanda poha, slot: breakfast, protein: [veg], cuisine: indian,
     minutes: 15}
  - {id: rajma, name: Rajma masala, slot: dinner, protein: [veg], cuisine: indian, minutes: 40}
  - {id: makhani, name: Makhani night, slot: dinner, protein: [veg, chicken], cuisine: indian,
     minutes: 40}
  - {id: egg_curry, name: Egg curry with rice, slot: dinner, protein: [egg], cuisine: indian,
     minutes: 40}
  - {id: pizza, name: Pizza night, slot: dinner, protein: [veg], cuisine: italian, minutes: 30,
     treat: true}
"""


@pytest.fixture(autouse=True)
def parent_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PARENT_PIN)


@pytest.fixture
def diet(tmp_path: Path) -> DietService:
    """Thursday allows meat, Friday does not; everything else is allowed."""
    cache = tmp_path / "diet-days.json"
    cache.write_text(
        DietCache(
            days=[
                DietDay(date=THURSDAY, non_veg_ok=True, reasons=[]),
                DietDay(date=FRIDAY, non_veg_ok=False, reasons=["not a meat day"]),
            ],
            computed_at=THURSDAY,
        ).model_dump_json(),
        encoding="utf-8",
    )
    return DietService(cache)


@pytest.fixture
def planned(client: TestClient, content_dir: Path) -> None:
    """The catalog above, and rajma as Thursday's planned dinner."""
    (content_dir / "meals-catalog.yaml").write_text(CATALOG, encoding="utf-8")
    (content_dir / "meals.yaml").write_text(
        f"{THURSDAY.isoformat()}:\n  dinner: {{id: rajma}}\n", encoding="utf-8"
    )
    client.app.state.content.load_all()  # type: ignore[attr-defined]


def sign_in(client: TestClient) -> None:
    assert client.post("/api/parent/session", json={"pin": PARENT_PIN}).status_code == 200


def pick(client: TestClient, kid: str, dish: str, *, day: Date = THURSDAY, **extra: Any) -> Any:
    return client.post(
        "/api/picks",
        json={"kid_id": kid, "date": day.isoformat(), "slot": "dinner", "dish_id": dish, **extra},
    )


def dinner(client: TestClient, day: Date = THURSDAY) -> dict[str, Any]:
    days = client.get("/api/picks", params={"from": day.isoformat(), "days": 1}).json()
    return dict(days[0]["dinner"])


def ledger_rows(database: Database) -> int:
    with database.connect() as connection:
        return int(connection.execute("SELECT COUNT(*) AS n FROM ledger").fetchone()["n"])


def catalog() -> MealsCatalog:
    return MealsCatalog.model_validate(yaml.safe_load(CATALOG))


# -- resolution -------------------------------------------------------------


def test_no_picks_is_the_plan(client: TestClient, planned: None) -> None:
    slot = dinner(client)
    assert slot["resolved"]["id"] == "rajma"
    assert slot["picks"] == []
    assert slot["contested"] is False


def test_one_pick_resolves_to_that_dish(client: TestClient, planned: None) -> None:
    assert pick(client, "kabir", "makhani").status_code == 200
    slot = dinner(client)
    assert slot["resolved"]["id"] == "makhani"
    assert slot["resolved"]["picked_by"] == ["kabir"]
    assert slot["contested"] is False


def test_the_same_dish_twice_is_not_a_contest(client: TestClient, planned: None) -> None:
    pick(client, "kabir", "makhani")
    pick(client, "mira", "makhani")
    slot = dinner(client)
    assert slot["contested"] is False
    assert slot["resolved"]["picked_by"] == ["kabir", "mira"]


def test_different_dishes_are_contested(client: TestClient, planned: None) -> None:
    pick(client, "kabir", "makhani")
    pick(client, "mira", "egg_curry", kids_protein="egg")
    slot = dinner(client)
    assert slot["contested"] is True
    # The plan still stands, with both choices on it until a parent decides.
    assert slot["resolved"]["id"] == "rajma"
    assert slot["resolved"]["confirmed"] is False
    assert set(slot["resolved"]["picks"]) == {"kabir", "mira"}

    # The wall reads the same resolution: /api/today is built through it.
    day = client.get("/api/today", params={"date": THURSDAY.isoformat()}).json()
    assert day["meals"]["dinner"]["confirmed"] is False
    assert set(day["meals"]["dinner"]["picks"]) == {"kabir", "mira"}


def test_a_week_is_monday_to_sunday(client: TestClient, planned: None) -> None:
    year, number, _ = THURSDAY.isocalendar()
    days = client.get("/api/picks", params={"week": f"{year}-W{number:02d}"}).json()
    assert len(days) == 7
    assert Date.fromisoformat(days[0]["date"]).weekday() == 0


# -- deciding ---------------------------------------------------------------


def contest(client: TestClient) -> None:
    pick(client, "kabir", "makhani")
    pick(client, "mira", "egg_curry", kids_protein="egg")
    sign_in(client)


def test_choose_plans_the_winner_and_passes_the_loser(
    client: TestClient, planned: None
) -> None:
    contest(client)
    decided = client.post(
        "/api/parent/picks/decide",
        json={"date": THURSDAY.isoformat(), "slot": "dinner", "winner_kid_id": "kabir"},
    )
    assert decided.status_code == 200
    slot = dinner(client)
    assert slot["contested"] is False
    assert slot["resolved"]["id"] == "makhani"
    statuses = {one["kid_id"]: one["status"] for one in slot["picks"]}
    assert statuses == {"kabir": "chosen", "mira": "passed"}


def test_alternate_moves_the_loser_to_the_next_allowed_day(
    client: TestClient, planned: None
) -> None:
    """Mira's egg curry cannot go to Friday, a veg day, so it goes to Saturday."""
    contest(client)
    decided = client.post(
        "/api/parent/picks/decide",
        json={
            "date": THURSDAY.isoformat(),
            "slot": "dinner",
            "winner_kid_id": "kabir",
            "mode": "alternate",
        },
    )
    assert decided.status_code == 200
    body = decided.json()
    assert body["winner_date"] == THURSDAY.isoformat()
    assert body["loser_kid_id"] == "mira"
    assert body["loser_date"] == SATURDAY.isoformat()

    assert dinner(client)["resolved"]["id"] == "makhani"
    saturday = dinner(client, SATURDAY)
    assert saturday["resolved"]["id"] == "egg_curry"
    assert saturday["resolved"]["picked_by"] == ["mira"]


def test_after_a_decision_the_children_cannot_change_it(
    client: TestClient, planned: None
) -> None:
    contest(client)
    client.post(
        "/api/parent/picks/decide",
        json={"date": THURSDAY.isoformat(), "slot": "dinner", "winner_kid_id": "kabir"},
    )
    again = pick(client, "mira", "rajma")
    assert again.status_code == 409


def test_deciding_needs_a_parent(client: TestClient, planned: None) -> None:
    refused = client.post(
        "/api/parent/picks/decide",
        json={"date": THURSDAY.isoformat(), "slot": "dinner", "winner_kid_id": "kabir"},
    )
    assert refused.status_code == 401


def test_the_approvals_queue_carries_the_contest(client: TestClient, planned: None) -> None:
    contest(client)
    queue = client.get("/api/parent/approvals").json()
    meal = next(item for item in queue if item["kind"] == "meal")
    assert meal["title"] == "Thursday dinner"
    assert meal["plan_name"] == "Rajma masala"
    assert {choice["id"]: choice["kids"] for choice in meal["choices"]} == {
        "makhani": ["kabir"],
        "egg_curry": ["mira"],
    }
    assert client.get("/api/approvals/count").json()["pending"] >= 1


# -- the fences -------------------------------------------------------------


def test_a_kid_replaces_only_their_own_pick(client: TestClient, planned: None) -> None:
    pick(client, "kabir", "makhani")
    pick(client, "mira", "makhani")
    pick(client, "mira", "rajma")
    picks_now = {one["kid_id"]: one["dish_id"] for one in dinner(client)["picks"]}
    assert picks_now == {"kabir": "makhani", "mira": "rajma"}

    kabir = next(one for one in dinner(client)["picks"] if one["kid_id"] == "kabir")
    refused = client.delete(f"/api/picks/{kabir['id']}", params={"kid_id": "mira"})
    assert refused.status_code == 403
    mine = client.delete(f"/api/picks/{kabir['id']}", params={"kid_id": "kabir"})
    assert mine.status_code == 204


def test_a_treat_waits_for_a_parent(client: TestClient, planned: None) -> None:
    made = pick(client, "kabir", "pizza")
    assert made.status_code == 200
    slot = dinner(client)
    assert slot["picks"][0]["status"] == "proposed"
    # Waiting: it does not count yet, so the plan still stands.
    assert slot["resolved"]["id"] == "rajma"

    sign_in(client)
    treat = next(
        item for item in client.get("/api/parent/approvals").json() if item["kind"] == "treat"
    )
    assert treat["title"] == "Pizza night"
    approved = client.post(f"/api/parent/picks/{treat['pick_id']}/approve")
    assert approved.status_code == 200
    assert dinner(client)["resolved"]["id"] == "pizza"


def test_two_treats_a_week(client: TestClient, planned: None) -> None:
    assert pick(client, "kabir", "pizza", day=TUESDAY).status_code == 200
    assert pick(client, "kabir", "pizza", day=TUESDAY + timedelta(days=1)).status_code == 200
    third = pick(client, "kabir", "pizza")
    assert third.status_code == 409
    assert "two treats" in third.json()["detail"]


def test_a_protein_the_day_forbids_is_refused(client: TestClient, planned: None) -> None:
    refused = pick(client, "mira", "makhani", day=FRIDAY, kids_protein="chicken")
    assert refused.status_code == 409


def test_picks_are_free(client: TestClient, planned: None, database: Database) -> None:
    before = ledger_rows(database)
    contest(client)
    pick(client, "kabir", "pizza", day=SATURDAY)
    client.post(
        "/api/parent/picks/decide",
        json={
            "date": THURSDAY.isoformat(),
            "slot": "dinner",
            "winner_kid_id": "kabir",
            "mode": "alternate",
        },
    )
    assert ledger_rows(database) == before


def test_a_repeat_is_a_warning_not_a_wall(client: TestClient, planned: None) -> None:
    """Rajma is Thursday's plan; Saturday's picker says so and still offers it."""
    offered = client.get(
        "/api/picks/options",
        params={"kid_id": "kabir", "slot": "dinner", "date": SATURDAY.isoformat()},
    ).json()
    rajma = next(one for one in offered if one["id"] == "rajma")
    assert rajma["pickable"] is True
    assert rajma["warning"] == "we had this Thursday"


# -- the lock ---------------------------------------------------------------


def test_after_the_lock_a_contest_falls_back_and_both_move(database: Database) -> None:
    """Nobody decided by 16:00: the plan stands, and both dishes go to the next
    day each can be — egg curry skips the veg Friday."""
    before_lock = datetime.combine(THURSDAY, time(9, 0), tzinfo=TZ)
    after_lock = datetime.combine(THURSDAY, time(16, 30), tzinfo=TZ)
    food = catalog()
    with database.write() as connection:
        weekly.choose(connection, food, kid_id="kabir", day=THURSDAY, slot="dinner",
                      dish_id="makhani", protein="veg", now=before_lock)
        weekly.choose(connection, food, kid_id="mira", day=THURSDAY, slot="dinner",
                      dish_id="egg_curry", protein="egg", now=before_lock)
        moved = weekly.settle_locked(
            connection, food, diet_ok=lambda day: day != FRIDAY, now=after_lock
        )
        assert moved == 2
        rows = weekly.rows_between(connection, THURSDAY, SATURDAY + timedelta(days=3), food)

    by_kid = {(row.kid_id, row.status, row.date): row for row in rows}
    assert by_kid[("kabir", "moved", THURSDAY)].moved_to == FRIDAY
    assert by_kid[("mira", "moved", THURSDAY)].moved_to == SATURDAY
    assert "locked" in (by_kid[("kabir", "moved", THURSDAY)].note or "")
    thursday = weekly.resolve_slot(THURSDAY, "dinner", None, rows, after_lock)
    assert thursday.contested is False
    assert thursday.resolved is None  # no plan in this test: back to nothing


def test_a_locked_slot_refuses_a_change(database: Database) -> None:
    late = datetime.combine(THURSDAY, time(16, 1), tzinfo=TZ)
    with database.write() as connection, pytest.raises(ClaimError) as refused:
        weekly.choose(connection, catalog(), kid_id="kabir", day=THURSDAY, slot="dinner",
                      dish_id="rajma", protein="veg", now=late)
    assert refused.value.status == 409
    assert "Locked" in refused.value.detail


def test_breakfast_locks_the_evening_before() -> None:
    now = datetime.combine(THURSDAY - timedelta(days=1), time(19, 59), tzinfo=TZ)
    assert not weekly.is_locked(THURSDAY, "breakfast", now)
    assert weekly.is_locked(THURSDAY, "breakfast", now + timedelta(minutes=1))


# -- from before ------------------------------------------------------------


def test_picks_in_meals_yaml_move_into_the_table(tmp_path: Path, database: Database) -> None:
    path = tmp_path / "meals.yaml"
    path.write_text(
        f"{THURSDAY.isoformat()}:\n"
        "  dinner:\n"
        "    id: makhani\n"
        "    picked_by: [kabir, mira]\n"
        "    confirmed: false\n"
        "    plan: rajma\n"
        "    picks:\n"
        "      kabir: {id: makhani}\n"
        "      mira: {id: egg_curry, kids_protein: egg}\n",
        encoding="utf-8",
    )
    now = datetime.combine(THURSDAY - timedelta(days=3), time(9, 0), tzinfo=TZ)
    with database.write() as connection:
        moved = weekly.migrate_from_yaml(path, connection, now=now, validate=lambda _: None)
        again = weekly.migrate_from_yaml(path, connection, now=now, validate=lambda _: None)
        rows = weekly.rows_between(connection, THURSDAY, THURSDAY, catalog())
    assert moved == 2
    assert again == 0
    assert {(row.kid_id, row.dish_id) for row in rows} == {
        ("kabir", "makhani"),
        ("mira", "egg_curry"),
    }
    written = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert written[THURSDAY]["dinner"] == {"id": "rajma"}


def test_meal_rewards_are_retired_with_a_refund(
    client: TestClient, content_dir: Path, database: Database
) -> None:
    """Held points for a meal reward come back as a refund row when the API
    starts, once rewards.yaml has switched meal rewards off."""
    now = datetime.now(TZ)
    with database.write() as connection:
        ledger.append(connection, kid_id="mira", delta=40, reason_kind="award",
                      actor="parent", now=now)
        ledger.append(connection, kid_id="mira", delta=-15, reason_kind="redeem",
                      actor="kid", now=now)
        connection.execute(
            "INSERT INTO redemptions (kid_id, reward_id, points, status, requested_at)"
            " VALUES ('mira', 'meal_pick', 15, 'requested', ?)",
            (now.isoformat(),),
        )
    path = content_dir / "rewards.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "fulfilment: meal, glyph: meal}", "fulfilment: meal, glyph: meal, enabled: false}"
        ),
        encoding="utf-8",
    )
    content: Content = client.app.state.content  # type: ignore[attr-defined]
    content.load_all()
    with client:
        pass
    assert client.get("/api/points/mira").json()["balance"] == 40
    assert client.get("/api/redemptions/mira").json()[0]["status"] == "refunded"


def test_lunch_and_dinner_share_one_menu(client: TestClient, planned: None) -> None:
    """Both are suitable at both times: a dinner dish is offered at lunch, and
    picking it there works. Breakfast keeps its own."""
    lunch = client.get(
        "/api/picks/options",
        params={"kid_id": "kabir", "slot": "lunch", "date": THURSDAY.isoformat()},
    ).json()
    assert "makhani" in {one["id"] for one in lunch}
    breakfast = client.get(
        "/api/picks/options",
        params={"kid_id": "kabir", "slot": "breakfast", "date": THURSDAY.isoformat()},
    ).json()
    assert {one["id"] for one in breakfast} == {"kanda_poha"}

    made = client.post(
        "/api/picks",
        json={"kid_id": "kabir", "date": THURSDAY.isoformat(), "slot": "lunch",
              "dish_id": "makhani"},
    )
    assert made.status_code == 200
    assert made.json()["resolved"]["id"] == "makhani"


def test_each_slot_leads_with_its_own_dishes() -> None:
    """The family's catalog (the session's copy): 14 breakfasts, 14 lunches,
    30 dinners. A slot's own dishes come first and are what it counts; lunch
    and dinner then offer each other's, marked, never mixed in."""
    from mantel_api import picks
    from mantel_api.paths import content_dir

    real = MealsCatalog.model_validate(
        yaml.safe_load((content_dir() / "meals-catalog.yaml").read_text(encoding="utf-8"))
    )

    class Nothing:
        def on(self, _day: Date) -> Any:
            return type("Empty", (), {"breakfast": None, "lunch": None, "dinner": None})()

    def offered(slot: str) -> list[Any]:
        return picks.options(real, Nothing(), slot=slot, day=THURSDAY, non_veg_ok=True)  # type: ignore[arg-type]

    counts = {
        slot: sum(1 for dish in real.dishes if dish.slot == slot)
        for slot in ("breakfast", "lunch", "dinner")
    }
    for slot, own in counts.items():
        listed = offered(slot)
        mine = [one for one in listed if not one.also]
        assert len(mine) == own, slot
        # Own first: nothing of the slot's own comes after a shared dish.
        first_shared = next((i for i, one in enumerate(listed) if one.also), len(listed))
        assert all(one.also for one in listed[first_shared:]), slot
    assert not any(one.also for one in offered("breakfast"))
    # Lunch out is the lunch pool's alone: the rest of lunch is shared.
    assert len(offered("dinner")) == counts["dinner"] + counts["lunch"] - 1
