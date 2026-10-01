"""Putting a wrong row right: undo it, or move it to the other child."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from mantel_api.db import Database

TZ = ZoneInfo("America/Los_Angeles")
PARENT_PIN = "2468"
#: In both of the fixture's lists, so it is claimable whatever today is.
DAILY = "outside"


@pytest.fixture(autouse=True)
def parent_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PARENT_PIN)


@pytest.fixture
def parent(client: TestClient) -> TestClient:
    assert client.post("/api/parent/session", json={"pin": PARENT_PIN}).status_code == 200
    return client


def balance(client: TestClient, kid_id: str) -> int:
    return int(client.get(f"/api/points/{kid_id}").json()["balance"])


def rows(client: TestClient) -> list[dict[str, object]]:
    return list(client.get("/api/parent/ledger").json())


def award(client: TestClient, kid_id: str, points: int) -> dict[str, object]:
    made = client.post(
        "/api/parent/awards", json={"kid_id": kid_id, "points": points, "note": "Kind to a sister"}
    )
    assert made.status_code == 200
    return next(row for row in rows(client) if row["kid_id"] == kid_id)


def correct(client: TestClient, row_id: object, **body: object):  # type: ignore[no-untyped-def]
    return client.post(f"/api/parent/ledger/{row_id}/correct", json=body)


def test_an_award_to_the_wrong_child_moves_to_the_right_one(parent: TestClient) -> None:
    row = award(parent, "mira", 15)
    assert row["can"] == ["undo", "move"]

    moved = correct(parent, row["id"], action="move", to_kid="kabir")
    assert moved.status_code == 200
    written = moved.json()
    assert [(r["kid_id"], r["delta"]) for r in written] == [("mira", -15), ("kabir", 15)]
    assert balance(parent, "mira") == 0
    assert balance(parent, "kabir") == 15

    # The original row says it has been dealt with, and so do the new ones.
    after = {r["id"]: r for r in rows(parent)}
    assert after[row["id"]]["can"] == []
    assert all(after[r["id"]]["can"] == [] for r in written)


def test_a_row_is_corrected_once(parent: TestClient) -> None:
    row = award(parent, "mira", 10)
    assert correct(parent, row["id"], action="undo").status_code == 200
    assert correct(parent, row["id"], action="undo").status_code == 409
    assert balance(parent, "mira") == 0


def test_undoing_a_chore_reopens_it(parent: TestClient) -> None:
    claim = parent.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY}).json()
    assert parent.post(f"/api/parent/claims/{claim['id']}/approve").status_code == 200
    row = next(r for r in rows(parent) if r["reason_kind"] == "task")
    # A chore can be undone but not moved: the other child never claimed it.
    assert row["can"] == ["undo"]
    assert correct(parent, row["id"], action="move", to_kid="kabir").status_code == 400

    assert correct(parent, row["id"], action="undo").status_code == 200
    assert balance(parent, "mira") == 0
    today = parent.get("/api/today").json()
    mira = next(kid for kid in today["kids"] if kid["id"] == "mira")
    assert next(t for t in mira["tasks"] if t["id"] == DAILY)["status"] == "none"
    # And it can be claimed again.
    assert parent.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY}).status_code == 201


def test_points_already_spent_cannot_be_taken_back(
    parent: TestClient, database: Database
) -> None:
    row = award(parent, "mira", 10)
    with database.write() as connection:
        connection.execute(
            """
            INSERT INTO ledger (kid_id, delta, reason_kind, reason_ref, note, actor, created_at)
            VALUES ('mira', -8, 'redeem', 'r1', 'Ice cream', 'kid', ?)
            """,
            (datetime.now(TZ).isoformat(),),
        )
    refused = correct(parent, row["id"], action="undo")
    assert refused.status_code == 409
    assert "spent" in refused.json()["detail"]


def test_a_reward_is_not_corrected_here(parent: TestClient) -> None:
    row = award(parent, "mira", 10)
    correct(parent, row["id"], action="undo")
    undo_row = next(r for r in rows(parent) if r["reason_ref"] == f"correct:{row['id']}")
    assert correct(parent, undo_row["id"], action="undo").status_code == 400


def test_it_is_for_parents(client: TestClient) -> None:
    assert client.post("/api/parent/ledger/1/correct", json={"action": "undo"}).status_code == 401
