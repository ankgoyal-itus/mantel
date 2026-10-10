"""Each child's bank: cash and Roblox rewards go in when a parent says yes,
and come out when a parent has actually paid or given the time."""

from __future__ import annotations

import sqlite3
from datetime import date as Date
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mantel_api import backup, banks, ledger
from mantel_api.claims import ClaimError
from mantel_api.db import SCHEMA_VERSION, Database, ensure_schema
from mantel_api.models import Banks, Points, Reward

TZ = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 7, 18, 0, tzinfo=TZ)  # a Wednesday
PARENT_PIN = "2468"
SHOP = """\
  - {id: cash_5, name: $5 cash, cost: 50, fulfilment: bank, glyph: coin, dollars: 5}
  - {id: cash_10, name: $10 cash, cost: 95, fulfilment: bank, glyph: coin, dollars: 10}
  - {id: roblox_bank_1h, name: Roblox +1 h, cost: 100, fulfilment: bank, glyph: game, minutes: 60}
"""


@pytest.fixture(autouse=True)
def parent_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PARENT_PIN)


@pytest.fixture
def shop(client: TestClient, content_dir: Path) -> None:
    """The fixture's rewards, plus the bank ones, and a parent signed in."""
    path = content_dir / "rewards.yaml"
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n" + SHOP, encoding="utf-8")
    client.app.state.content.load_all()  # type: ignore[attr-defined]
    assert client.post("/api/parent/session", json={"pin": PARENT_PIN}).status_code == 200


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


def ask(client: TestClient, kid_id: str, reward_id: str) -> Any:
    return client.post("/api/redemptions", json={"kid_id": kid_id, "reward_id": reward_id})


def approve(client: TestClient, redemption_id: int) -> dict[str, Any]:
    answer = client.post(f"/api/parent/redemptions/{redemption_id}/approve")
    assert answer.status_code == 200, answer.text
    return dict(answer.json())


def points(client: TestClient, kid_id: str) -> dict[str, Any]:
    return dict(client.get(f"/api/points/{kid_id}").json())


def bank(client: TestClient, kid_id: str) -> dict[str, Any]:
    return dict(client.get(f"/api/banks/{kid_id}").json())


def bank_rows(database: Database, kid_id: str) -> list[sqlite3.Row]:
    with database.connect() as connection:
        return connection.execute(
            "SELECT * FROM bank WHERE kid_id = ? ORDER BY id", (kid_id,)
        ).fetchall()


def todo(client: TestClient, title: str) -> dict[str, Any]:
    todos = client.get("/api/parent/todos").json()
    found = [item for item in todos if item["title"] == title]
    assert len(found) == 1, todos
    return dict(found[0])


# -- deposits ----------------------------------------------------------------


def test_approving_deposits_and_leaves_nothing_to_do(
    client: TestClient, database: Database, shop: None
) -> None:
    give(database, "mira", 60)
    asked = ask(client, "mira", "cash_5")
    assert asked.status_code == 201
    assert points(client, "mira")["balance"] == 10

    approved = approve(client, asked.json()["id"])
    assert approved["status"] == "fulfilled"
    assert approved["fulfilment_ref"].startswith(banks.DEPOSIT)

    [row] = bank_rows(database, "mira")
    assert (row["account"], row["delta"], row["reason_kind"]) == ("cash", 500, "deposit")
    assert row["reason_ref"] == f"redemption:{asked.json()['id']}"
    assert row["actor"] == "parent"
    # The points were taken at the ask; approving moves none.
    assert points(client, "mira")["balance"] == 10
    assert points(client, "mira")["cash_cents"] == 500
    deposit = points(client, "mira")["last_deposit"]
    assert (deposit["id"], deposit["note"]) == (row["id"], "$5 cash")
    assert client.get("/api/parent/todos").json() == []


def test_declining_refunds_the_points_and_deposits_nothing(
    client: TestClient, database: Database, shop: None
) -> None:
    give(database, "mira", 60)
    asked = ask(client, "mira", "cash_5")
    declined = client.post(f"/api/parent/redemptions/{asked.json()['id']}/decline")
    assert declined.json()["status"] == "refunded"
    assert points(client, "mira")["balance"] == 60
    assert bank_rows(database, "mira") == []


def test_roblox_reward_deposits_minutes(
    client: TestClient, database: Database, shop: None
) -> None:
    give(database, "kabir", 100)
    asked = ask(client, "kabir", "roblox_bank_1h")
    approve(client, asked.json()["id"])
    assert points(client, "kabir")["roblox_minutes"] == 60
    assert bank(client, "kabir")["roblox"]["minutes"] == 60


# -- asking again --------------------------------------------------------------


def test_two_asks_hold_two_costs_and_a_third_is_refused(
    client: TestClient, database: Database, shop: None
) -> None:
    give(database, "mira", 149)
    first = ask(client, "mira", "cash_5")
    second = ask(client, "mira", "cash_5")
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    # Each ask holds its own fifty.
    assert points(client, "mira")["balance"] == 49

    third = ask(client, "mira", "cash_5")
    assert third.status_code == 409
    assert "1 points short" in third.json()["detail"]
    assert points(client, "mira")["balance"] == 49

    waiting = [
        item for item in client.get("/api/parent/approvals").json() if item["kind"] == "redemption"
    ]
    assert len(waiting) == 2


# -- cash-outs -----------------------------------------------------------------


def test_cash_out_below_the_minimum_is_refused(
    client: TestClient, database: Database, shop: None
) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="mira", account="cash", delta=1500, note="Gift", now=NOW)
    refused = client.post("/api/banks/mira/cashout", json={"cents": 1500})
    assert refused.status_code == 409
    assert "$20" in refused.json()["detail"]


def test_cash_out_above_what_is_there_is_refused(
    client: TestClient, database: Database, shop: None
) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="mira", account="cash", delta=2000, note="Gift", now=NOW)
    assert client.post("/api/banks/mira/cashout", json={"cents": 2500}).status_code == 409


def test_a_pending_cash_out_holds_its_amount(
    client: TestClient, database: Database, shop: None
) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="mira", account="cash", delta=4000, note="Gift", now=NOW)
    asked = client.post("/api/banks/mira/cashout", json={"cents": 2000})
    assert asked.status_code == 201
    cash = asked.json()["cash"]
    assert (cash["cents"], cash["available_cents"]) == (4000, 2000)
    assert [item["amount"] for item in cash["pending"]] == [2000]
    # The other half is not enough for a second one at $25.
    assert client.post("/api/banks/mira/cashout", json={"cents": 2500}).status_code == 409


def test_paid_writes_exactly_one_row(client: TestClient, database: Database, shop: None) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="mira", account="cash", delta=2000, note="Gift", now=NOW)
    client.post("/api/banks/mira/cashout", json={"cents": 2000})
    card = todo(client, "Pay Mira $20")
    assert (card["kind"], card["cents"]) == ("cashout", 2000)

    paid = client.post("/api/parent/todos/done", json={"ref": card["ref"]})
    assert paid.status_code == 200
    again = client.post("/api/parent/todos/done", json={"ref": card["ref"]})
    assert again.status_code == 409

    rows = bank_rows(database, "mira")
    assert [(row["reason_kind"], row["delta"]) for row in rows] == [
        ("adjust", 2000),
        ("cashout", -2000),
    ]
    assert rows[1]["reason_ref"] == card["ref"]
    assert bank(client, "mira")["cash"] == {"cents": 0, "available_cents": 0, "pending": []}


def test_declining_a_cash_out_returns_the_hold(
    client: TestClient, database: Database, shop: None
) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="mira", account="cash", delta=2000, note="Gift", now=NOW)
    client.post("/api/banks/mira/cashout", json={"cents": 2000})
    card = todo(client, "Pay Mira $20")
    declined = client.post(f"/api/parent/banks/requests/{card['request_id']}/decline")
    assert declined.status_code == 200
    assert declined.json() == []
    assert bank(client, "mira")["cash"]["available_cents"] == 2000
    assert len(bank_rows(database, "mira")) == 1
    again = client.post(f"/api/parent/banks/requests/{card['request_id']}/decline")
    assert again.status_code == 409


# -- Roblox uses ----------------------------------------------------------------


def test_a_use_must_be_one_of_the_sizes(client: TestClient, database: Database, shop: None) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="kabir", account="roblox", delta=120, note="Gift", now=NOW)
    assert client.post("/api/banks/kabir/roblox/use", json={"minutes": 45}).status_code == 400
    assert client.post("/api/banks/kabir/roblox/use", json={"minutes": 120}).status_code == 201


def test_a_use_above_the_weekly_cap_is_refused(
    client: TestClient, database: Database, shop: None
) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="kabir", account="roblox", delta=600, note="Gift", now=NOW)
    for _ in range(2):
        assert client.post("/api/banks/kabir/roblox/use", json={"minutes": 30}).status_code == 201
    third = client.post("/api/banks/kabir/roblox/use", json={"minutes": 30})
    assert third.status_code == 409
    assert "limit" in third.json()["detail"]
    assert bank(client, "kabir")["roblox"]["uses_this_week"] == 2


def test_the_cap_is_per_iso_week_and_a_decline_is_not_a_use(database: Database) -> None:
    settings, cap = Banks(), Points(roblox_per_week=1)
    with database.write() as connection:
        banks.adjust(connection, kid_id="kabir", account="roblox", delta=600, note="Gift", now=NOW)
        first = banks.use_roblox(connection, settings, cap, kid_id="kabir", minutes=30, now=NOW)
        with pytest.raises(ClaimError):
            banks.use_roblox(connection, settings, cap, kid_id="kabir", minutes=30, now=NOW)
        banks.decline(connection, first.id, now=NOW)
        banks.use_roblox(connection, settings, cap, kid_id="kabir", minutes=30, now=NOW)
        # The Monday after is a new week.
        monday = datetime(2026, 10, 12, 9, 0, tzinfo=TZ)
        banks.use_roblox(connection, settings, cap, kid_id="kabir", minutes=30, now=monday)
        assert banks.uses_this_week(connection, "kabir", Date(2026, 10, 7)) == 1


def test_done_writes_exactly_one_row(client: TestClient, database: Database, shop: None) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="kabir", account="roblox", delta=60, note="Gift", now=NOW)
    client.post("/api/banks/kabir/roblox/use", json={"minutes": 60})
    card = todo(client, "Give Kabir 60 min of Roblox today")
    assert (card["kind"], card["minutes"]) == ("roblox", 60)
    assert client.post("/api/parent/todos/done", json={"ref": card["ref"]}).status_code == 200
    assert client.post("/api/parent/todos/done", json={"ref": card["ref"]}).status_code == 409
    uses = [row for row in bank_rows(database, "kabir") if row["reason_kind"] == "use"]
    assert [row["delta"] for row in uses] == [-60]
    assert bank(client, "kabir")["roblox"]["minutes"] == 0


def test_a_waiting_request_counts_on_the_lock_screen(
    client: TestClient, database: Database, shop: None
) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="kabir", account="roblox", delta=60, note="Gift", now=NOW)
    before = client.get("/api/approvals/count").json()["pending"]
    client.post("/api/banks/kabir/roblox/use", json={"minutes": 60})
    assert client.get("/api/approvals/count").json()["pending"] == before + 1


# -- balances, adjustments, the rows themselves ----------------------------------


def test_balances_are_sums(database: Database) -> None:
    with database.write() as connection:
        for delta in (500, 1000, -300):
            banks.append(
                connection,
                kid_id="mira",
                account="cash",
                delta=delta,
                reason_kind="adjust",
                actor="parent",
                now=NOW,
            )
        banks.append(
            connection,
            kid_id="mira",
            account="roblox",
            delta=90,
            reason_kind="deposit",
            actor="parent",
            now=NOW,
        )
        assert banks.balance(connection, "mira", "cash") == 1200
        assert banks.balance(connection, "mira", "roblox") == 90
        assert banks.balance(connection, "kabir", "cash") == 0
        total = connection.execute(
            "SELECT SUM(delta) FROM bank WHERE kid_id = 'mira' AND account = 'cash'"
        ).fetchone()[0]
        assert total == 1200


@pytest.mark.parametrize(
    "statement", ["UPDATE bank SET delta = 1", "DELETE FROM bank"], ids=["update", "delete"]
)
def test_the_bank_is_append_only(database: Database, statement: str) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="mira", account="cash", delta=500, note="Gift", now=NOW)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"), database.write() as connection:
        connection.execute(statement)


def test_payouts_stay_append_only(database: Database) -> None:
    with database.write() as connection:
        connection.execute(
            "INSERT INTO payouts (kid_id, dollars, paid_at) VALUES ('mira', 5, '2026-09-24')"
        )
    with pytest.raises(sqlite3.IntegrityError), database.write() as connection:
        connection.execute("DELETE FROM payouts")


def test_adjust_rows_carry_the_note(client: TestClient, database: Database, shop: None) -> None:
    made = client.post(
        "/api/parent/banks/mira/adjust",
        json={"account": "cash", "delta": 2000, "note": "Birthday from Nani"},
    )
    assert made.status_code == 200
    [row] = bank_rows(database, "mira")
    assert (row["reason_kind"], row["delta"], row["note"]) == ("adjust", 2000, "Birthday from Nani")
    mira = next(kid for kid in made.json()["kids"] if kid["kid_id"] == "mira")
    assert mira["recent"][0]["note"] == "Birthday from Nani"


def test_adjust_needs_a_note_and_cannot_go_below_zero(
    client: TestClient, database: Database, shop: None
) -> None:
    blank = {"account": "cash", "delta": 500, "note": "  "}
    assert client.post("/api/parent/banks/mira/adjust", json=blank).status_code == 400
    under = {"account": "cash", "delta": -500, "note": "Oops"}
    assert client.post("/api/parent/banks/mira/adjust", json=under).status_code == 409


def test_adjust_is_for_parents(client: TestClient) -> None:
    body = {"account": "cash", "delta": 500, "note": "Gift"}
    assert client.post("/api/parent/banks/mira/adjust", json=body).status_code == 401
    assert client.get("/api/parent/banks").status_code == 401


def test_parent_banks_lists_both_kids_and_the_to_dos(
    client: TestClient, database: Database, shop: None
) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="mira", account="cash", delta=2000, note="Gift", now=NOW)
    client.post("/api/banks/mira/cashout", json={"cents": 2000})
    body = client.get("/api/parent/banks").json()
    assert [kid["kid_id"] for kid in body["kids"]] == ["mira", "kabir"]
    assert [item["title"] for item in body["todos"]] == ["Pay Mira $20"]


def test_recent_is_the_last_twenty_across_both_accounts(
    client: TestClient, database: Database, shop: None
) -> None:
    with database.write() as connection:
        for index in range(15):
            banks.adjust(
                connection, kid_id="mira", account="cash", delta=100, note=f"c{index}", now=NOW
            )
            banks.adjust(
                connection, kid_id="mira", account="roblox", delta=5, note=f"r{index}", now=NOW
            )
    recent = bank(client, "mira")["recent"]
    assert len(recent) == 20
    assert recent[0]["note"] == "r14"
    assert {row["account"] for row in recent} == {"cash", "roblox"}


# -- the whole story -------------------------------------------------------------


def test_done_when(client: TestClient, database: Database, shop: None) -> None:
    """Mira asks for $5 twice with 100 points; both are approved; she saves to
    $20 and cashes it out. Kabir buys an hour of Roblox and uses it, and a
    third use that week is refused."""
    give(database, "mira", 100)
    first, second = ask(client, "mira", "cash_5"), ask(client, "mira", "cash_5")
    queued = [i for i in client.get("/api/parent/approvals").json() if i["kind"] == "redemption"]
    assert len(queued) == 2
    approve(client, first.json()["id"])
    approve(client, second.json()["id"])
    summary = points(client, "mira")
    assert (summary["balance"], summary["cash_cents"]) == (0, 1000)

    give(database, "mira", 95)
    approve(client, ask(client, "mira", "cash_10").json()["id"])
    assert bank(client, "mira")["cash"]["cents"] == 2000
    assert client.post("/api/banks/mira/cashout", json={"cents": 2000}).status_code == 201
    card = todo(client, "Pay Mira $20")
    client.post("/api/parent/todos/done", json={"ref": card["ref"]})
    assert bank(client, "mira")["cash"]["cents"] == 0

    give(database, "kabir", 100)
    approve(client, ask(client, "kabir", "roblox_bank_1h").json()["id"])
    assert bank(client, "kabir")["roblox"]["minutes"] == 60
    assert client.post("/api/banks/kabir/roblox/use", json={"minutes": 60}).status_code == 201
    card = todo(client, "Give Kabir 60 min of Roblox today")
    client.post("/api/parent/todos/done", json={"ref": card["ref"]})
    assert bank(client, "kabir")["roblox"]["minutes"] == 0

    with database.write() as connection:
        banks.adjust(connection, kid_id="kabir", account="roblox", delta=120, note="Gift", now=NOW)
    assert client.post("/api/banks/kabir/roblox/use", json={"minutes": 30}).status_code == 201
    third = client.post("/api/banks/kabir/roblox/use", json={"minutes": 30})
    assert third.status_code == 409


# -- settings, the digest, the file, the move from owed cash -----------------------


def test_bank_settings_save_from_the_parent_screen(
    client: TestClient, content_dir: Path, shop: None
) -> None:
    current = client.get("/api/parent/settings").json()
    assert current["banks"] == {"cash_out_min_cents": 2000, "roblox_use_sizes": [30, 60, 120]}
    current["banks"] = {"cash_out_min_cents": 1500, "roblox_use_sizes": [15, 30, 60]}
    saved = client.put("/api/parent/settings", json=current)
    assert saved.status_code == 200, saved.text
    written = yaml.safe_load((content_dir / "settings.yaml").read_text(encoding="utf-8"))
    assert written["banks"] == {"cash_out_min_cents": 1500, "roblox_use_sizes": [15, 30, 60]}
    assert bank(client, "kabir")["roblox"]["sizes"] == [15, 30, 60]


def test_bank_settings_are_checked() -> None:
    with pytest.raises(ValidationError):
        Banks(cash_out_min_cents=1550)
    with pytest.raises(ValidationError):
        Banks(roblox_use_sizes=[])
    assert Banks(roblox_use_sizes=[120, 30, 60]).roblox_use_sizes == [30, 60, 120]


def test_a_bank_reward_says_what_it_is_worth() -> None:
    base = {"id": "x", "name": "X", "cost": 50, "fulfilment": "bank", "glyph": "coin"}
    with pytest.raises(ValidationError, match="dollars: or minutes:"):
        Reward.model_validate(base)
    with pytest.raises(ValidationError, match="dollars: or minutes:"):
        Reward.model_validate({**base, "dollars": 5, "minutes": 60})
    assert Reward.model_validate({**base, "dollars": 5}).account == "cash"
    assert Reward.model_validate({**base, "minutes": 60}).deposit == 60


def test_a_file_still_saying_cash_means_the_bank() -> None:
    reward = Reward.model_validate(
        {"id": "c", "name": "$5", "cost": 50, "fulfilment": "cash", "glyph": "coin", "dollars": 5}
    )
    assert (reward.fulfilment, reward.account, reward.deposit) == ("bank", "cash", 500)


def test_the_digest_lists_bank_movements(
    client: TestClient, database: Database, shop: None
) -> None:
    give(database, "mira", 50)
    approve(client, ask(client, "mira", "cash_5").json()["id"])
    with database.write() as connection:
        banks.adjust(
            connection,
            kid_id="mira",
            account="cash",
            delta=1500,
            note="Birthday",
            now=datetime.now(TZ),
        )
    client.post("/api/banks/mira/cashout", json={"cents": 2000})
    client.post("/api/parent/todos/done", json={"ref": todo(client, "Pay Mira $20")["ref"]})
    mira = next(kid for kid in client.get("/api/digest").json()["kids"] if kid["kid_id"] == "mira")
    assert mira["bank"] == ["+$5 · $5 cash", "+$15 · Birthday", "−$20 · cashed out"]


def test_owed_cash_moves_into_the_bank_once(database: Database) -> None:
    """A $5 approved before the bank, and never paid, is a deposit now."""
    with database.write() as connection:
        connection.execute(
            "INSERT INTO redemptions (kid_id, reward_id, points, status, requested_at,"
            " fulfilment_ref) VALUES ('mira', 'cash_5', 50, 'approved', ?, 'cash:5')",
            (NOW.isoformat(),),
        )
        assert banks.move_owed_cash(connection, now=NOW) == 1
        assert banks.move_owed_cash(connection, now=NOW) == 0
        assert banks.balance(connection, "mira", "cash") == 500
        row = connection.execute("SELECT status FROM redemptions").fetchone()
        assert row["status"] == "fulfilled"
        actor = connection.execute("SELECT actor FROM bank").fetchone()["actor"]
        assert actor == "system"


def test_the_nightly_backup_carries_the_bank(tmp_path: Path, database: Database) -> None:
    with database.write() as connection:
        banks.adjust(connection, kid_id="mira", account="cash", delta=500, note="Gift", now=NOW)
    made = backup.run(database, Date(2026, 10, 7), directory=tmp_path / "backup")
    copy = sqlite3.connect(made)
    try:
        assert copy.execute("SELECT SUM(delta) FROM bank").fetchone()[0] == 500
    finally:
        copy.close()


def test_an_existing_file_gains_the_bank(tmp_path: Path) -> None:
    """A v3 file on the Mac upgrades itself the first time this opens it."""
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.row_factory = sqlite3.Row
    ensure_schema(old)
    old.execute("DROP TABLE bank")
    old.execute("DROP TABLE bank_requests")
    old.execute("PRAGMA user_version = 3")
    old.commit()

    ensure_schema(old)
    tables = {row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"bank", "bank_requests", "payouts"} <= tables
    assert old.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    old.close()
