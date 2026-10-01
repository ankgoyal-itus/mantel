"""The ledger's own rules, checked the way the house would want them checked.

These are the evals for the data layer: not that the code runs, but that the
four properties everything else assumes actually hold.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date as Date
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from mantel_api import backup, ledger
from mantel_api.db import FAMILY, Database

TZ = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 9, 29, 15, 30, tzinfo=TZ)


def test_ledger_refuses_an_update(database: Database) -> None:
    """A wrong row is answered with another row, never with an eraser."""
    with database.write() as connection:
        row_id = ledger.append(
            connection, kid_id="mira", delta=10, reason_kind="task", actor="parent", now=NOW
        )

    with database.connect() as connection:  # noqa: SIM117 - the raise is the point
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE ledger SET delta = 999 WHERE id = ?", (row_id,))


def test_ledger_refuses_a_delete(database: Database) -> None:
    with database.write() as connection:
        row_id = ledger.append(
            connection, kid_id="mira", delta=10, reason_kind="task", actor="parent", now=NOW
        )

    with database.connect() as connection:  # noqa: SIM117 - the raise is the point
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM ledger WHERE id = ?", (row_id,))

    with database.connect() as connection:
        assert ledger.balance(connection, "mira") == 10


def test_balance_is_the_sum_of_a_thousand_rows(database: Database) -> None:
    """The property the whole design rests on, at a size no eye would check."""
    rng = random.Random(1729)
    kinds = ("task", "award", "redeem", "refund", "adjust")
    expected = 0
    with database.write() as connection:
        for index in range(1000):
            delta = rng.randint(-50, 50)
            expected += delta
            ledger.append(
                connection,
                kid_id="mira",
                delta=delta,
                reason_kind=rng.choice(kinds),
                actor=rng.choice(("kid", "parent")),
                now=NOW + timedelta(minutes=index),
            )
        # A second child's rows must not leak into the first one's balance.
        ledger.append(
            connection, kid_id="kabir", delta=10_000, reason_kind="award", actor="parent", now=NOW
        )

    with database.connect() as connection:
        assert ledger.balance(connection, "mira") == expected
        assert ledger.balance(connection, "kabir") == 10_000


def test_a_refund_exactly_reverses_a_hold(database: Database) -> None:
    """Asking and being told no leaves a child exactly where they started."""
    with database.write() as connection:
        ledger.append(
            connection, kid_id="mira", delta=50, reason_kind="task", actor="parent", now=NOW
        )
        before = ledger.balance(connection, "mira")
        ledger.hold(connection, kid_id="mira", points=30, reason_ref="redemption:1", now=NOW)

    with database.connect() as connection:
        assert ledger.balance(connection, "mira") == before - 30

    with database.write() as connection:
        ledger.refund(connection, kid_id="mira", points=30, reason_ref="redemption:1", now=NOW)

    with database.connect() as connection:
        assert ledger.balance(connection, "mira") == before
        # And the history says what happened, rather than hiding it.
        kinds = [row.reason_kind for row in ledger.entries(connection, "mira")]
        assert kinds == ["refund", "redeem", "task"]


def test_a_jar_transfer_is_two_rows_that_sum_to_zero(database: Database) -> None:
    with database.write() as connection:
        ledger.append(
            connection, kid_id="mira", delta=40, reason_kind="task", actor="parent", now=NOW
        )
        ledger.transfer_to_jar(connection, kid_id="mira", points=25, now=NOW)

    with database.connect() as connection:
        assert ledger.balance(connection, "mira") == 15
        assert ledger.balance(connection, FAMILY) == 25
        moved = connection.execute(
            "SELECT SUM(delta) AS total FROM ledger WHERE reason_kind = 'jar'"
        ).fetchone()
        assert moved["total"] == 0


def test_earned_this_week_counts_what_was_earned(database: Database) -> None:
    """Spending on Saturday must not make a good week read as a bad one."""
    monday = ledger.week_start(NOW)
    with database.write() as connection:
        ledger.append(
            connection, kid_id="mira", delta=20, reason_kind="task", actor="parent", now=monday
        )
        ledger.append(
            connection, kid_id="mira", delta=15, reason_kind="award", actor="parent", now=NOW
        )
        ledger.hold(connection, kid_id="mira", points=30, reason_ref="redemption:1", now=NOW)
        # Last week, which this week's number must not see.
        ledger.append(
            connection,
            kid_id="mira",
            delta=99,
            reason_kind="task",
            actor="parent",
            now=monday - timedelta(days=1),
        )

    with database.connect() as connection:
        assert ledger.earned_since(connection, "mira", monday) == 35
        assert ledger.balance(connection, "mira") == 104
        # The same week, a bar a day: Monday's twenty, today's fifteen, and
        # neither the spend nor last Sunday.
        days = ledger.earned_by_day(connection, "mira", NOW)
        assert len(days) == 7
        assert sum(days) == 35
        assert days[0] == 20
        assert days[NOW.weekday()] == (35 if NOW.weekday() == 0 else 15)


def test_backups_rotate(tmp_path: Path, database: Database) -> None:
    """Fourteen kept, the oldest dropped, and today's taken only once."""
    directory = tmp_path / "backup"
    with database.write() as connection:
        ledger.append(
            connection, kid_id="mira", delta=10, reason_kind="task", actor="parent", now=NOW
        )

    first = Date(2026, 9, 1)
    for offset in range(20):
        backup.run(database, first + timedelta(days=offset), directory=directory)

    kept = backup.copies(directory)
    assert len(kept) == backup.KEEP
    assert kept[0].name == "mantel-2026-09-07.db"
    assert kept[-1].name == "mantel-2026-09-20.db"

    # The copy is a real database, not an empty file.
    copied = sqlite3.connect(kept[-1])
    try:
        copied.row_factory = sqlite3.Row
        assert copied.execute("SELECT SUM(delta) AS total FROM ledger").fetchone()["total"] == 10
    finally:
        copied.close()


def test_todays_backup_is_taken_once(tmp_path: Path, database: Database) -> None:
    directory = tmp_path / "backup"
    today = Date(2026, 9, 29)
    made = backup.run(database, today, directory=directory)
    stamp = made.stat().st_mtime_ns

    with database.write() as connection:
        ledger.append(
            connection, kid_id="mira", delta=10, reason_kind="task", actor="parent", now=NOW
        )
    again = backup.run(database, today, directory=directory)

    assert again == made
    assert again.stat().st_mtime_ns == stamp
    assert len(backup.copies(directory)) == 1


def test_a_bad_reason_kind_is_refused(database: Database) -> None:
    """The set of reasons is the schema's business, not a convention."""
    with pytest.raises(sqlite3.IntegrityError):  # noqa: PT012 - the write is the subject
        with database.write() as connection:
            ledger.append(
                connection, kid_id="mira", delta=10, reason_kind="bribe", actor="parent", now=NOW
            )
