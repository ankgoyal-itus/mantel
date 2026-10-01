"""The three read endpoints the kid cards are built on."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from mantel_api import ledger
from mantel_api.db import Database

TZ = ZoneInfo("America/Los_Angeles")


def seed(database: Database, *, kid_id: str = "mira") -> None:
    now = datetime.now(TZ)
    with database.write() as connection:
        ledger.append(
            connection,
            kid_id=kid_id,
            delta=10,
            reason_kind="task",
            reason_ref=f"{kid_id}:hw:2026-09-29",
            actor="parent",
            now=ledger.week_start(now),
        )
        ledger.append(
            connection, kid_id=kid_id, delta=25, reason_kind="award", actor="parent", now=now
        )


def test_points_are_balance_week_and_streak(client: TestClient, database: Database) -> None:
    seed(database)
    body = client.get("/api/points/mira").json()
    # Seven days, Monday first, adding up to the week.
    week_days = body.pop("week_days")
    assert len(week_days) == 7
    assert sum(week_days) == 35
    assert body == {
        "kid_id": "mira",
        "balance": 35,
        "this_week": 35,
        "streak_days": 0,
        "dollars_owed": 0,
        # Nothing marked yet: the bars only exist once a child has chosen.
        "saving_for": [],
    }


def test_points_for_an_unknown_kid_are_a_404(client: TestClient) -> None:
    assert client.get("/api/points/nobody").status_code == 404


def test_the_family_jar_reads_like_a_kid(client: TestClient, database: Database) -> None:
    seed(database)
    with database.write() as connection:
        ledger.transfer_to_jar(connection, kid_id="mira", points=20, now=datetime.now(TZ))

    jar = client.get("/api/points/family").json()
    assert jar["balance"] == 20
    # The jar has no chores, so it has no streak to speak of.
    assert jar["streak_days"] == 0
    assert client.get("/api/points/mira").json()["balance"] == 15


def test_ledger_returns_history_newest_first(client: TestClient, database: Database) -> None:
    seed(database)
    rows = client.get("/api/ledger/mira").json()
    assert [row["reason_kind"] for row in rows] == ["award", "task"]
    assert rows[0]["delta"] == 25
    assert rows[1]["reason_ref"] == "mira:hw:2026-09-29"


def test_ledger_window_is_clamped_not_refused(client: TestClient, database: Database) -> None:
    seed(database)
    assert client.get("/api/ledger/mira", params={"days": 1}).status_code == 200
    assert client.get("/api/ledger/mira", params={"days": 4000}).status_code == 422


def test_rewards_include_the_disabled_ones(client: TestClient) -> None:
    """A child who cannot see a reward cannot save towards it."""
    rewards = client.get("/api/rewards").json()
    ids = [reward["id"] for reward in rewards]
    assert "roblox_1h" in ids

    roblox = next(reward for reward in rewards if reward["id"] == "roblox_1h")
    assert roblox["enabled"] is False
    assert roblox["minutes"] == 60

    jar_reward = next(reward for reward in rewards if reward["id"] == "dinner_out")
    assert jar_reward["family"] is True


def test_health_reports_the_ledger(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["ledger"].startswith("ok (schema 3")
    assert body["content"]["rewards"] == "ok"
