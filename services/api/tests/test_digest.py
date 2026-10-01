"""The week, added up. Nothing here is generated; it is the rows."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from mantel_api import ledger
from mantel_api.db import Database
from mantel_api.digest import week_bounds, week_name

TZ = ZoneInfo("America/Los_Angeles")
PARENT_PIN = "2468"
#: Monday to Sunday of ISO week 2026-W39.
MONDAY = Date(2026, 9, 21)


@pytest.fixture(autouse=True)
def parent_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PARENT_PIN)


def test_a_week_is_its_monday_and_sunday() -> None:
    start, end = week_bounds("2026-W39", Date(2026, 1, 1))
    assert (start, end) == (MONDAY, Date(2026, 9, 27))
    assert week_name(start) == "2026-W39"


def test_an_unreadable_week_is_this_one(client: TestClient) -> None:
    """A 422 on the settings tab helps nobody."""
    start, _end = week_bounds("last tuesday", Date(2026, 9, 29))
    assert start == Date(2026, 9, 28)
    assert client.get("/api/digest", params={"week": "nonsense"}).status_code == 200


def test_the_digest_counts_what_happened(client: TestClient, database: Database) -> None:
    when = datetime(2026, 9, 22, 17, 0, tzinfo=TZ)
    with database.write() as connection:
        ledger.append(
            connection,
            kid_id="mira",
            delta=10,
            reason_kind="task",
            note="Homework",
            actor="parent",
            now=when,
        )
        ledger.hold(connection, kid_id="mira", points=30, reason_ref="redemption:1", now=when)
        connection.execute(
            """
            INSERT INTO claims (kid_id, task_id, date, status, claimed_at, decided_at, decided_by)
            VALUES ('mira', 'hw', '2026-09-22', 'approved', ?, ?, 'parent')
            """,
            (when.isoformat(), when.isoformat()),
        )
        connection.execute(
            """
            INSERT INTO redemptions (kid_id, reward_id, points, status, requested_at)
            VALUES ('mira', 'ice_cream', 30, 'approved', ?)
            """,
            (when.isoformat(),),
        )

    body = client.get("/api/digest", params={"week": "2026-W39"}).json()
    assert body["week"] == "2026-W39"
    assert body["start"] == MONDAY.isoformat()

    mira = next(kid for kid in body["kids"] if kid["kid_id"] == "mira")
    assert mira["earned"] == 10
    assert mira["spent"] == 30
    assert mira["approved"] == {"2026-09-22": ["Homework"]}
    assert mira["redemptions"] == ["Ice cream (approved)"]

    # Both children are reported, including the one with a quiet week.
    kabir = next(kid for kid in body["kids"] if kid["kid_id"] == "kabir")
    assert kabir["earned"] == 0
    assert kabir["approved"] == {}


def test_another_week_sees_none_of_it(client: TestClient, database: Database) -> None:
    with database.write() as connection:
        ledger.append(
            connection,
            kid_id="mira",
            delta=10,
            reason_kind="task",
            actor="parent",
            now=datetime(2026, 9, 22, 17, 0, tzinfo=TZ),
        )
    body = client.get("/api/digest", params={"week": "2026-W40"}).json()
    assert body["kids"][0]["earned"] == 0
