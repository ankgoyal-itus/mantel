"""Claiming a task, taking it back, and the tasks a kid may not claim."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from mantel_api.db import Database

TZ = ZoneInfo("America/Los_Angeles")
PARENT_PIN = "2468"

#: tasks.yaml in the fixture gives both kids a daily "30 min outside".
DAILY = "outside"


def today() -> Date:
    return datetime.now(TZ).date()


@pytest.fixture(autouse=True)
def parent_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PARENT_PIN)


def sign_in(client: TestClient) -> None:
    assert client.post("/api/parent/session", json={"pin": PARENT_PIN}).status_code == 200


def test_a_claim_and_an_undo_round_trip(client: TestClient) -> None:
    made = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
    assert made.status_code == 201
    claim = made.json()
    assert claim["status"] == "claimed"
    assert claim["date"] == today().isoformat()

    assert [row["id"] for row in client.get("/api/claims").json()] == [claim["id"]]

    assert client.delete(f"/api/claims/{claim['id']}").status_code == 204
    assert client.get("/api/claims").json() == []

    # And it can be claimed again afterwards, which is the point of an undo.
    assert client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY}).status_code == 201


def test_a_claim_shows_on_the_dashboard(client: TestClient) -> None:
    """A parent walking past sees what was claimed without opening anything."""
    client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})

    day = client.get("/api/today").json()
    mira = next(kid for kid in day["kids"] if kid["id"] == "mira")
    outside = next(task for task in mira["tasks"] if task["id"] == DAILY)
    assert outside["status"] == "claimed"
    assert outside["points"] == 10

    # The other child's identically-named task is untouched: task ids repeat
    # across kids, so the kid belongs in the key.
    kabir = next(kid for kid in day["kids"] if kid["id"] == "kabir")
    assert next(task for task in kabir["tasks"] if task["id"] == DAILY)["status"] == "none"


def test_a_parent_only_task_refuses_a_kid_claim(
    client: TestClient, content_dir: object
) -> None:
    """Answered out loud rather than by a row that silently never appears."""
    from pathlib import Path

    assert isinstance(content_dir, Path)
    (content_dir / "tasks.yaml").write_text(
        "mira:\n"
        "  weekdays:\n"
        "    - {id: hw, title: Homework, points: 10, claim: parent}\n"
        "    - {id: outside, title: 30 min outside, points: 10}\n"
        "kabir:\n"
        "  weekdays:\n"
        "    - {id: hw, title: Homework, points: 10}\n",
        encoding="utf-8",
    )
    client.app.state.content.load_all()  # type: ignore[attr-defined]

    refused = client.post("/api/claims", json={"kid_id": "mira", "task_id": "hw"})
    assert refused.status_code == 403
    assert "parent" in refused.json()["detail"]

    # The same task, for the kid whose file does not mark it, is fine.
    assert client.post("/api/claims", json={"kid_id": "kabir", "task_id": "hw"}).status_code == 201


def test_an_unknown_task_or_kid_is_a_404(client: TestClient) -> None:
    moon = client.post("/api/claims", json={"kid_id": "mira", "task_id": "moon"})
    assert moon.status_code == 404
    assert client.post("/api/claims", json={"kid_id": "zoe", "task_id": DAILY}).status_code == 404


def test_the_same_task_cannot_be_claimed_twice(client: TestClient) -> None:
    client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
    again = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
    assert again.status_code == 409


def test_only_todays_tasks_may_be_claimed(client: TestClient) -> None:
    yesterday = (today() - timedelta(days=1)).isoformat()
    late = client.post(
        "/api/claims", json={"kid_id": "mira", "task_id": DAILY, "date": yesterday}
    )
    assert late.status_code == 400


class TestTheKidPads:
    def test_no_pin_set_means_the_card_opens(self, client: TestClient) -> None:
        assert client.get("/api/kids/pins").json() == {"pins": {"mira": False, "kabir": False}}
        opened = client.post("/api/kids/mira/pin/verify", json={"pin": ""})
        assert opened.json() == {"ok": True}

    def test_a_parent_sets_and_clears_a_pin(self, client: TestClient) -> None:
        sign_in(client)
        state = client.put("/api/kids/mira/pin", json={"pin": "1234"})
        assert state.json() == {"pins": {"mira": True, "kabir": False}}

        assert client.post("/api/kids/mira/pin/verify", json={"pin": "1234"}).json()["ok"] is True
        assert client.post("/api/kids/mira/pin/verify", json={"pin": "9999"}).json()["ok"] is False
        # The other card is not latched by it.
        assert client.post("/api/kids/kabir/pin/verify", json={"pin": ""}).json()["ok"] is True

        cleared = client.put("/api/kids/mira/pin", json={"pin": ""})
        assert cleared.json() == {"pins": {"mira": False, "kabir": False}}

    def test_a_kid_cannot_set_their_own_pin(self, client: TestClient) -> None:
        assert client.put("/api/kids/mira/pin", json={"pin": "1234"}).status_code == 401

    def test_a_pin_is_four_digits(self, client: TestClient) -> None:
        sign_in(client)
        assert client.put("/api/kids/mira/pin", json={"pin": "12"}).status_code == 400
        assert client.put("/api/kids/mira/pin", json={"pin": "abcd"}).status_code == 400

    def test_the_pin_is_not_stored_as_itself(self, client: TestClient, database: Database) -> None:
        sign_in(client)
        client.put("/api/kids/mira/pin", json={"pin": "1234"})
        with database.connect() as connection:
            stored = connection.execute("SELECT pin_hash FROM kid_pins").fetchone()["pin_hash"]
        assert "1234" not in stored
        assert stored.startswith("pbkdf2$")
