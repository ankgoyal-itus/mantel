"""The version the screens watch: once per write they would show, never on a
read, a refusal or a sign-in."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from mantel_api import ledger
from mantel_api.app import UNSEEN_WRITES, WRITE_METHODS
from mantel_api.db import Database
from mantel_api.version import StateVersion

TZ = ZoneInfo("America/Los_Angeles")
PARENT_PIN = "2468"


@pytest.fixture(autouse=True)
def parent_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PARENT_PIN)


def version(client: TestClient) -> int:
    return int(client.get("/api/version").json()["version"])


def moves(client: TestClient, write: Callable[[], httpx.Response]) -> int:
    """How far one write moves the version."""
    before = version(client)
    write()
    return version(client) - before


def give(database: Database, points: int) -> None:
    with database.write() as connection:
        ledger.append(
            connection,
            kid_id="mira",
            delta=points,
            reason_kind="award",
            actor="parent",
            now=datetime.now(TZ),
        )


def test_every_write_route_is_counted_or_named(client: TestClient) -> None:
    """The middleware sees every write under /api/; the only ones that do not
    move the version are the few listed as unseen, and each of those exists."""
    names = set()
    for route in client.app.routes:  # type: ignore[attr-defined]
        if not isinstance(route, APIRoute) or not (set(route.methods or ()) & WRITE_METHODS):
            continue
        assert route.path.startswith("/api/"), route.path
        names.add(route.endpoint.__name__)
    assert UNSEEN_WRITES <= names


def test_each_write_path_bumps_exactly_once(client: TestClient, database: Database) -> None:
    give(database, 100)
    assert client.post("/api/parent/session", json={"pin": PARENT_PIN}).status_code == 200

    claim = client.post("/api/claims", json={"kid_id": "mira", "task_id": "outside"})
    assert claim.status_code in (200, 201)
    claim_id = claim.json()["id"]

    writes: list[tuple[str, Callable[[], httpx.Response]]] = [
        ("approve", lambda: client.post(f"/api/parent/claims/{claim_id}/approve")),
        (
            "award",
            lambda: client.post(
                "/api/parent/awards", json={"kid_id": "mira", "points": 5, "note": "kind"}
            ),
        ),
        ("jar", lambda: client.post("/api/jar", json={"kid_id": "mira", "points": 5})),
        (
            "redemption",
            lambda: client.post(
                "/api/redemptions", json={"kid_id": "mira", "reward_id": "ice_cream"}
            ),
        ),
        (
            "meal",
            lambda: client.post(
                "/api/parent/meals/set",
                json={"date": "2026-09-30", "slot": "dinner", "dish_id": None},
            ),
        ),
    ]
    for name, write in writes:
        before = version(client)
        response = write()
        assert 200 <= response.status_code < 300, (name, response.text)
        assert version(client) - before == 1, name


def test_reads_refusals_and_sign_ins_do_not_move_it(client: TestClient) -> None:
    assert moves(client, lambda: client.get("/api/today")) == 0
    assert moves(client, lambda: client.get("/api/points/mira")) == 0
    # A write that fails changed nothing.
    refused = {"kid_id": "nobody", "task_id": "x"}
    assert moves(client, lambda: client.post("/api/claims", json=refused)) == 0
    # Signing in and out is no screen's business.
    assert moves(client, lambda: client.post("/api/parent/session", json={"pin": PARENT_PIN})) == 0
    assert moves(client, lambda: client.delete("/api/parent/session")) == 0


def test_it_survives_a_restart(database: Database) -> None:
    first = StateVersion(database)
    first.bump(datetime.now(TZ))
    first.bump(datetime.now(TZ))
    again = StateVersion(database)
    assert again.current().version == 2
    assert again.current().changed_at is not None
