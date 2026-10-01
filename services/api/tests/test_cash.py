"""Points into dollars: an approved cash reward is a parent's to-do, and Paid
on it records the payout for that reward."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mantel_api import ledger
from mantel_api.db import SCHEMA_VERSION, Database, ensure_schema
from mantel_api.models import Reward

TZ = ZoneInfo("America/Los_Angeles")
PARENT_PIN = "2468"
CASH = "  - {id: cash_5, name: $5 cash, cost: 50, fulfilment: cash, glyph: coin, dollars: 5}\n"


@pytest.fixture(autouse=True)
def parent_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PARENT_PIN)


@pytest.fixture
def shop(client: TestClient, content_dir: Path) -> None:
    """The fixture's rewards, plus a cash one."""
    path = content_dir / "rewards.yaml"
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n" + CASH, encoding="utf-8")
    client.app.state.content.load_all()  # type: ignore[attr-defined]


def give(database: Database, kid_id: str, points: int) -> None:
    with database.write() as connection:
        ledger.append(
            connection,
            kid_id=kid_id,
            delta=points,
            reason_kind="award",
            actor="parent",
            now=datetime.now(TZ),
        )


def cash_in(client: TestClient) -> dict[str, Any]:
    """Mira asks for $5 and a parent says yes."""
    asked = client.post("/api/redemptions", json={"kid_id": "mira", "reward_id": "cash_5"})
    assert asked.status_code == 201
    approved = client.post(f"/api/parent/redemptions/{asked.json()['id']}/approve")
    assert approved.status_code == 200
    return dict(approved.json())


def owed(client: TestClient) -> int:
    return int(client.get("/api/points/mira").json()["dollars_owed"])


def paid_off(client: TestClient, redemption_id: int) -> list[dict[str, Any]]:
    """Paid, on the to-do card."""
    done = client.post("/api/parent/todos/done", json={"ref": f"redemption:{redemption_id}"})
    assert done.status_code == 200
    return list(done.json())


def test_asking_holds_the_points(client: TestClient, database: Database, shop: None) -> None:
    give(database, "mira", 60)
    asked = client.post("/api/redemptions", json={"kid_id": "mira", "reward_id": "cash_5"})
    assert asked.status_code == 201
    assert asked.json()["status"] == "requested"
    # The fifty are spoken for the moment the child asks, and nothing is owed.
    assert client.get("/api/points/mira").json()["balance"] == 10
    assert owed(client) == 0


def test_approving_makes_a_to_do_for_that_reward(
    client: TestClient, database: Database, shop: None
) -> None:
    give(database, "mira", 150)
    assert client.post("/api/parent/session", json={"pin": PARENT_PIN}).status_code == 200

    first = cash_in(client)
    assert first["status"] == "approved"
    assert first["fulfilment_ref"] == "cash:5"
    assert owed(client) == 5

    # One card per reward: "Give Mira $5", with Paid on it.
    todos = client.get("/api/parent/todos").json()
    assert [(todo["kind"], todo["dollars"]) for todo in todos] == [("cash", 5)]

    cash_in(client)
    cash_in(client)
    assert owed(client) == 15
    assert len(client.get("/api/parent/todos").json()) == 3
    assert client.get("/api/points/mira").json()["balance"] == 0


def test_paid_records_the_payout_and_clears_what_is_owed(
    client: TestClient, database: Database, shop: None
) -> None:
    give(database, "mira", 50)
    client.post("/api/parent/session", json={"pin": PARENT_PIN})
    approved = cash_in(client)

    assert paid_off(client, approved["id"]) == []
    assert owed(client) == 0

    # The payout is recorded against the reward it paid for.
    paid = client.get("/api/parent/payouts", params={"kid_id": "mira"}).json()
    assert [(row["dollars"], row["note"]) for row in paid] == [(5, f"redemption:{approved['id']}")]
    # And the kid's list reads it as paid.
    mine = client.get("/api/redemptions/mira").json()
    assert mine[0]["status"] == "fulfilled"

    # Twice is refused rather than paid twice.
    again = client.post("/api/parent/todos/done", json={"ref": f"redemption:{approved['id']}"})
    assert again.status_code == 409
    assert owed(client) == 0


def test_declining_gives_the_points_back(
    client: TestClient, database: Database, shop: None
) -> None:
    give(database, "mira", 50)
    client.post("/api/parent/session", json={"pin": PARENT_PIN})
    asked = client.post("/api/redemptions", json={"kid_id": "mira", "reward_id": "cash_5"})
    declined = client.post(f"/api/parent/redemptions/{asked.json()['id']}/decline")
    assert declined.status_code == 200
    assert declined.json()["status"] == "refunded"
    assert client.get("/api/points/mira").json()["balance"] == 50
    assert owed(client) == 0
    assert client.get("/api/parent/todos").json() == []


def test_a_rate_changed_later_does_not_rewrite_what_was_earned(
    client: TestClient, database: Database, content_dir: Path, shop: None
) -> None:
    give(database, "mira", 50)
    client.post("/api/parent/session", json={"pin": PARENT_PIN})
    cash_in(client)

    path = content_dir / "rewards.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("dollars: 5", "dollars: 8"),
                    encoding="utf-8")
    client.app.state.content.load_all()  # type: ignore[attr-defined]
    assert owed(client) == 5


def test_payouts_are_append_only(database: Database) -> None:
    with database.write() as connection:
        connection.execute(
            "INSERT INTO payouts (kid_id, dollars, paid_at) VALUES ('mira', 5, '2026-09-24')"
        )
    with pytest.raises(sqlite3.IntegrityError), database.write() as connection:
        connection.execute("DELETE FROM payouts")


def test_a_cash_reward_says_what_it_is_worth() -> None:
    with pytest.raises(ValidationError, match="needs dollars"):
        Reward.model_validate(
            {"id": "cash", "name": "Cash", "cost": 50, "fulfilment": "cash", "glyph": "coin"}
        )


def test_an_existing_ledger_gains_the_payouts_table(tmp_path: Path) -> None:
    """A v1 file on the Mac upgrades itself the first time v2 opens it."""
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.row_factory = sqlite3.Row
    ensure_schema(old)
    # What a v1 file is: everything but the payouts, at version 1.
    old.execute("DROP TABLE payouts")
    old.execute("PRAGMA user_version = 1")
    old.commit()

    ensure_schema(old)
    tables = {row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "payouts" in tables
    assert old.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    old.close()

