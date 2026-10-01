"""Asking for a reward: what is held, what comes back, and what a parent
is left holding afterwards."""

from __future__ import annotations

import json
from datetime import date as Date
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from mantel_api import ledger, redemptions
from mantel_api.db import FAMILY, Database
from mantel_api.models import Allowance, Points, Rewards

TZ = ZoneInfo("America/Los_Angeles")
PARENT_PIN = "2468"
NOW = datetime(2026, 9, 29, 15, 30, tzinfo=TZ)


@pytest.fixture(autouse=True)
def parent_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PARENT_PIN)


def sign_in(client: TestClient) -> None:
    assert client.post("/api/parent/session", json={"pin": PARENT_PIN}).status_code == 200


def give(database: Database, kid_id: str, points: int) -> None:
    """Points already earned, a few minutes before whatever the test does
    next — so the history reads in the order the test made it."""
    with database.write() as connection:
        ledger.append(
            connection,
            kid_id=kid_id,
            delta=points,
            reason_kind="award",
            actor="parent",
            now=datetime.now(TZ) - timedelta(minutes=5),
        )


def balance(database: Database, kid_id: str) -> int:
    with database.connect() as connection:
        return ledger.balance(connection, kid_id)


class TestAskingAndBeingTold:
    def test_the_points_are_held_when_they_ask(
        self, client: TestClient, database: Database
    ) -> None:
        """A balance that still shows spoken-for points invites spending them
        twice."""
        give(database, "mira", 50)
        asked = client.post(
            "/api/redemptions", json={"kid_id": "mira", "reward_id": "ice_cream"}
        )
        assert asked.status_code == 201
        assert asked.json()["status"] == "requested"
        assert asked.json()["name"] == "Ice cream"
        assert balance(database, "mira") == 20

    def test_a_decline_puts_them_straight_back(
        self, client: TestClient, database: Database
    ) -> None:
        give(database, "mira", 50)
        asked = client.post(
            "/api/redemptions", json={"kid_id": "mira", "reward_id": "ice_cream"}
        )
        sign_in(client)
        said_no = client.post(f"/api/parent/redemptions/{asked.json()['id']}/decline")

        assert said_no.json()["status"] == "refunded"
        assert balance(database, "mira") == 50

        # And the history says what happened rather than hiding it.
        with database.connect() as connection:
            kinds = [row.reason_kind for row in ledger.entries(connection, "mira")]
        assert kinds == ["refund", "redeem", "award"]

    def test_asking_for_more_than_they_have_is_refused(self, client: TestClient) -> None:
        short = client.post("/api/redemptions", json={"kid_id": "mira", "reward_id": "ice_cream"})
        assert short.status_code == 409
        assert "30 points short" in short.json()["detail"]

    def test_a_disabled_reward_cannot_be_asked_for(
        self, client: TestClient, database: Database
    ) -> None:
        give(database, "mira", 500)
        soon = client.post("/api/redemptions", json={"kid_id": "mira", "reward_id": "roblox_1h"})
        assert soon.status_code == 409
        assert balance(database, "mira") == 500

    def test_a_family_reward_is_paid_from_the_jar(
        self, client: TestClient, database: Database
    ) -> None:
        """One child cannot spend what the family saved together."""
        give(database, "mira", 500)
        too_soon = client.post(
            "/api/redemptions", json={"kid_id": "mira", "reward_id": "dinner_out"}
        )
        assert too_soon.status_code == 409  # the jar is empty, whatever Mira has

        give(database, FAMILY, 200)
        asked = client.post("/api/redemptions", json={"kid_id": "mira", "reward_id": "dinner_out"})
        assert asked.status_code == 201
        assert balance(database, FAMILY) == 50
        assert balance(database, "mira") == 500


class TestTheWeeklyCap:
    """Enforced whether or not the rewards are enabled, so switching them on
    is one flag rather than a rule change."""

    def enabled_shop(self) -> Rewards:
        return Rewards.model_validate(
            {
                "version": 1,
                "rewards": [
                    {
                        "id": "roblox_1h",
                        "name": "Roblox +1 h",
                        "cost": 10,
                        "fulfilment": "policy",
                        "glyph": "game",
                        "minutes": 60,
                        "enabled": True,
                    }
                ],
            }
        )

    def test_the_third_ask_in_a_week_is_refused(self, database: Database) -> None:
        give(database, "mira", 500)
        shop = self.enabled_shop()
        points = Points(roblox_per_week=2)

        for _ in range(2):
            with database.write() as connection:
                redemptions.request(
                    connection, shop, points, kid_id="mira", reward_id="roblox_1h", now=NOW
                )

        with pytest.raises(Exception, match="which is the limit"):  # noqa: PT011, PT012
            with database.write() as connection:
                redemptions.request(
                    connection, shop, points, kid_id="mira", reward_id="roblox_1h", now=NOW
                )

    def test_next_week_starts_again(self, database: Database) -> None:
        give(database, "mira", 500)
        shop = self.enabled_shop()
        points = Points(roblox_per_week=2)

        for _ in range(2):
            with database.write() as connection:
                redemptions.request(
                    connection, shop, points, kid_id="mira", reward_id="roblox_1h", now=NOW
                )

        with database.write() as connection:
            later = redemptions.request(
                connection,
                shop,
                points,
                kid_id="mira",
                reward_id="roblox_1h",
                now=NOW + timedelta(days=7),
            )
        assert later.status == "requested"

    def test_the_cap_counts_a_disabled_reward_too(self, database: Database) -> None:
        """The rule is tested before anybody is relying on it."""
        with database.connect() as connection:
            assert (
                redemptions.policy_count_this_week(
                    connection, "mira", self.enabled_shop(), NOW.date()
                )
                == 0
            )


class TestFulfilment:
    def test_a_manual_reward_becomes_a_parent_todo(
        self, client: TestClient, database: Database
    ) -> None:
        """Approved is not done: the ice cream still has to be bought."""
        give(database, "mira", 50)
        asked = client.post("/api/redemptions", json={"kid_id": "mira", "reward_id": "ice_cream"})
        sign_in(client)
        approved = client.post(f"/api/parent/redemptions/{asked.json()['id']}/approve")
        assert approved.json()["status"] == "approved"

        todos = client.get("/api/parent/todos").json()
        assert [todo["title"] for todo in todos] == ["Ice cream"]
        assert todos[0]["kind"] == "manual"

        done = client.post("/api/parent/todos/done", json={"ref": todos[0]["ref"]})
        assert done.json() == []
        assert client.get("/api/redemptions/mira").json()[0]["status"] == "fulfilled"

    def test_an_allowance_creates_exactly_n_reminders(
        self, client: TestClient, database: Database
    ) -> None:
        give(database, "mira", 200)
        asked = client.post(
            "/api/redemptions", json={"kid_id": "mira", "reward_id": "allowance_5"}
        )
        sign_in(client)
        approved = client.post(f"/api/parent/redemptions/{asked.json()['id']}/approve")
        assert approved.json()["status"] == "scheduled"

        with database.connect() as connection:
            rows = connection.execute(
                "SELECT key, value FROM settings_runtime WHERE key LIKE 'allowance:%'"
            ).fetchall()
        assert len(rows) == 5
        held = json.loads(rows[0]["value"])
        assert held["kid_id"] == "mira"
        assert held["days"] == 5
        assert held["hour"] == 18

        # Only the days that have come round are shown to a parent.
        todos = client.get("/api/parent/todos").json()
        assert len(todos) == 1
        assert todos[0]["day"] == 1
        assert todos[0]["days"] == 5

    def test_paying_the_last_day_finishes_it(self, database: Database) -> None:
        give(database, "mira", 200)
        shop = Rewards.model_validate(
            {
                "version": 1,
                "rewards": [
                    {
                        "id": "allowance_2",
                        "name": "Allowance x 2",
                        "cost": 10,
                        "fulfilment": "allowance",
                        "glyph": "coin",
                        "days": 2,
                    }
                ],
            }
        )
        with database.write() as connection:
            asked = redemptions.request(
                connection, shop, Points(), kid_id="mira", reward_id="allowance_2", now=NOW
            )
            redemptions.approve(
                connection, shop, Allowance(), redemption_id=asked.id, now=NOW
            )

        with database.connect() as connection:
            waiting = redemptions.todos(connection, shop, NOW.date() + timedelta(days=1))
        assert [todo.day for todo in waiting] == [1, 2]

        for todo in waiting:
            with database.write() as connection:
                redemptions.finish(connection, todo.ref, now=NOW)

        with database.connect() as connection:
            assert redemptions.for_kid(connection, shop, "mira")[0].status == "fulfilled"


class TestTheJar:
    def test_a_transfer_is_two_rows_that_sum_to_zero(
        self, client: TestClient, database: Database
    ) -> None:
        give(database, "mira", 60)
        moved = client.post("/api/jar", json={"kid_id": "mira", "points": 25})
        assert moved.json()["balance"] == 35

        assert balance(database, FAMILY) == 25
        with database.connect() as connection:
            total = connection.execute(
                "SELECT SUM(delta) AS total FROM ledger WHERE reason_kind = 'jar'"
            ).fetchone()["total"]
        assert total == 0

    def test_a_kid_cannot_give_what_they_do_not_have(self, client: TestClient) -> None:
        assert client.post("/api/jar", json={"kid_id": "mira", "points": 25}).status_code == 409

    def test_the_jar_reads_like_any_other_balance(
        self, client: TestClient, database: Database
    ) -> None:
        give(database, "mira", 60)
        client.post("/api/jar", json={"kid_id": "mira", "points": 25})
        assert client.get("/api/points/family").json()["balance"] == 25


def test_my_rewards_lists_what_was_asked_for(client: TestClient, database: Database) -> None:
    give(database, "mira", 100)
    client.post("/api/redemptions", json={"kid_id": "mira", "reward_id": "ice_cream"})
    client.post("/api/redemptions", json={"kid_id": "mira", "reward_id": "meal_pick"})

    mine = client.get("/api/redemptions/mira").json()
    assert [row["name"] for row in mine] == ["Pick breakfast or lunch", "Ice cream"]
    assert all(row["status"] == "requested" for row in mine)
    assert Date.fromisoformat(mine[0]["requested_at"][:10]) == datetime.now(TZ).date()
