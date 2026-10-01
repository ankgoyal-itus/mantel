"""`make demo`'s history, written into an empty ledger."""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from mantel_api import ledger, pins
from mantel_api.content import Content
from mantel_api.db import Database
from mantel_api.demo import seed
from mantel_api.sample import make_home

ZONE = ZoneInfo("America/Los_Angeles")


@pytest.mark.parametrize("today", [Date(2026, 10, 6), Date(2026, 10, 10)], ids=["tue", "sat"])
def test_the_seed_runs_on_an_empty_database(tmp_path: Path, today: Date) -> None:
    home = make_home(tmp_path / "home", today)
    content = Content(home / "content")
    content.load_all()
    books = Database(home / "mantel.db")
    try:
        with books.write() as connection:
            seed(connection, content, today, ZONE)

        with books.connect() as connection:
            assert ledger.balance(connection, "mira") == 37
            assert ledger.balance(connection, "kabir") == 52
            assert ledger.balance(connection, ledger.FAMILY) == 210

            statuses = {
                (str(row["kid_id"]), str(row["status"]))
                for row in connection.execute(
                    "SELECT kid_id, status FROM claims WHERE date = ?", (today.isoformat(),)
                )
            }
            assert statuses == {
                ("mira", "approved"),
                ("mira", "claimed"),
                ("kabir", "approved"),
                ("kabir", "claimed"),
                ("kabir", "declined"),
            }
            ice = connection.execute(
                "SELECT kid_id, status FROM redemptions WHERE reward_id = 'ice_cream'"
            ).fetchone()
            assert (ice["kid_id"], ice["status"]) == ("kabir", "approved")
            dinners = connection.execute(
                "SELECT kid_id, dish_id FROM picks WHERE slot = 'dinner'"
            ).fetchall()
            assert {(row["kid_id"], row["dish_id"]) for row in dinners} == {
                ("mira", "tacos"),
                ("kabir", "pizza_night"),
            }
            assert pins.check(connection, "mira", "1111")
            assert pins.check(connection, "kabir", "2222")
    finally:
        books.close()


def test_the_seed_refuses_a_ledger_that_is_not_empty(tmp_path: Path) -> None:
    today = Date(2026, 10, 6)
    home = make_home(tmp_path / "home", today)
    content = Content(home / "content")
    content.load_all()
    books = Database(home / "mantel.db")
    try:
        with books.write() as connection:
            seed(connection, content, today, ZONE)
        with books.write() as connection, pytest.raises(RuntimeError):
            seed(connection, content, today, ZONE)
    finally:
        books.close()
