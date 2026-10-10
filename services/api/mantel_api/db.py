"""The ledger's database: schema, connections and the append-only rule.

Everything v2 writes lives here rather than in YAML. YAML is what the house
edits by hand, and a ledger nobody edits by hand is the whole point of one.

Two rules are worth stating because the rest of the code depends on them:

* **The ledger is append-only, and SQLite enforces it.** The triggers below
  refuse UPDATE and DELETE on `ledger` rows, so the rule holds against a
  stray `sqlite3` session on the Mac, not only against this module. A mistake
  is corrected by appending its opposite, which is what `refund` and `adjust`
  are for — the history of a balance is as real as the balance.
* **A balance is always `SUM(delta)`.** It is never a column and never a
  cache, so it cannot drift from the rows that produced it.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .paths import db_path

logger = logging.getLogger("mantel_api.db")

#: Bumped when the schema below changes. `ensure_schema` applies everything
#: above the file's current `user_version`, so opening an old file upgrades it.
SCHEMA_VERSION = 4

#: The kid_id the family jar's rows carry. It is a ledger like any other, so
#: the jar's balance is SUM(delta) over these rows and needs no table.
FAMILY = "family"

REASON_KINDS = ("task", "award", "redeem", "refund", "adjust", "jar")
ACTORS = ("kid", "parent")
CLAIM_STATUSES = ("claimed", "approved", "declined")
PICK_SLOTS = ("breakfast", "lunch", "dinner")
PICK_STATUSES = ("proposed", "chosen", "moved", "passed")
BANK_ACCOUNTS = ("cash", "roblox")
BANK_REASONS = ("deposit", "cashout", "use", "adjust")
BANK_ACTORS = ("kid", "parent", "system")
BANK_REQUEST_STATUSES = ("requested", "done", "declined")
REDEMPTION_STATUSES = (
    "requested",
    "approved",
    "scheduled",
    "fulfilled",
    "declined",
    "refunded",
)


def _in(column: str, allowed: tuple[str, ...]) -> str:
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS ledger (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id      TEXT    NOT NULL,
  delta       INTEGER NOT NULL,
  reason_kind TEXT    NOT NULL CHECK ({_in("reason_kind", REASON_KINDS)}),
  reason_ref  TEXT,
  note        TEXT,
  actor       TEXT    NOT NULL CHECK ({_in("actor", ACTORS)}),
  created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ledger_by_kid ON ledger (kid_id, created_at);

-- Append-only, enforced by the database rather than by convention. A wrong
-- row is answered with another row, never with an eraser.
CREATE TRIGGER IF NOT EXISTS ledger_no_update
BEFORE UPDATE ON ledger
BEGIN
  SELECT RAISE(ABORT, 'ledger is append-only');
END;

CREATE TRIGGER IF NOT EXISTS ledger_no_delete
BEFORE DELETE ON ledger
BEGIN
  SELECT RAISE(ABORT, 'ledger is append-only');
END;

CREATE TABLE IF NOT EXISTS claims (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id     TEXT NOT NULL,
  task_id    TEXT NOT NULL,
  date       TEXT NOT NULL,
  status     TEXT NOT NULL CHECK ({_in("status", CLAIM_STATUSES)}),
  claimed_at TEXT NOT NULL,
  decided_at TEXT,
  decided_by TEXT
);

-- One claim per kid, per task, per day. Task ids repeat across kids — both
-- children have "hw" — so the kid belongs in the key.
CREATE UNIQUE INDEX IF NOT EXISTS claims_once
  ON claims (kid_id, task_id, date);

CREATE TABLE IF NOT EXISTS redemptions (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id         TEXT    NOT NULL,
  reward_id      TEXT    NOT NULL,
  points         INTEGER NOT NULL,
  status         TEXT    NOT NULL CHECK ({_in("status", REDEMPTION_STATUSES)}),
  requested_at   TEXT    NOT NULL,
  decided_at     TEXT,
  fulfilment_ref TEXT,
  note           TEXT
);

CREATE INDEX IF NOT EXISTS redemptions_by_kid ON redemptions (kid_id, requested_at);

CREATE TABLE IF NOT EXISTS kid_pins (
  kid_id   TEXT PRIMARY KEY,
  pin_hash TEXT NOT NULL
);

-- Money handed over for cash rewards (v2). What a child is owed is never
-- stored: it is the dollars their approved cash rewards were worth, less
-- these rows, so like a balance it cannot drift from what produced it. And
-- like the ledger it is append-only: a payment recorded in error is
-- corrected by a parent recording what actually happened, not by erasing.
CREATE TABLE IF NOT EXISTS payouts (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id   TEXT    NOT NULL,
  dollars  INTEGER NOT NULL CHECK (dollars > 0),
  paid_at  TEXT    NOT NULL,
  note     TEXT
);

CREATE INDEX IF NOT EXISTS payouts_by_kid ON payouts (kid_id, paid_at);

CREATE TRIGGER IF NOT EXISTS payouts_no_update
BEFORE UPDATE ON payouts
BEGIN
  SELECT RAISE(ABORT, 'payouts are append-only');
END;

CREATE TRIGGER IF NOT EXISTS payouts_no_delete
BEFORE DELETE ON payouts
BEGIN
  SELECT RAISE(ABORT, 'payouts are append-only');
END;

-- A child's choice for one meal (v3). Picks used to be written into
-- meals.yaml beside the plan; they live here now, and meals.yaml is the
-- family's plan and nothing else. What a slot comes to is worked out when it
-- is read (weekly.resolve_slot), from the plan and these rows.
--   chosen   counts: the slot is this dish, or contested if another child's
--            chosen dish differs
--   proposed a treat, waiting on a parent's OK before it counts
--   passed   lost a decision, was declined, or a parent overrode the slot
--   moved    went to another day (moved_to), where a chosen row now stands
-- Picks are free: nothing here ever writes to the ledger.
CREATE TABLE IF NOT EXISTS picks (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id       TEXT    NOT NULL,
  date         TEXT    NOT NULL,
  slot         TEXT    NOT NULL CHECK ({_in("slot", PICK_SLOTS)}),
  dish_id      TEXT    NOT NULL,
  kids_protein TEXT    NOT NULL DEFAULT 'veg',
  status       TEXT    NOT NULL CHECK ({_in("status", PICK_STATUSES)}),
  decided_by   TEXT,
  decided_at   TEXT,
  moved_to     TEXT,
  created_at   TEXT    NOT NULL,
  note         TEXT
);

CREATE INDEX IF NOT EXISTS picks_by_slot ON picks (date, slot);

-- Each child's bank (v3): dollars, in cents, and Roblox, in minutes. The
-- same rules as the ledger — append-only, enforced here, and a balance that
-- is SUM(delta) per kid and account and never a column. A deposit is an
-- approved reward; a cashout or a use is a parent's Paid or Done on a
-- request; an adjust is a parent's birthday money or correction.
CREATE TABLE IF NOT EXISTS bank (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id      TEXT    NOT NULL,
  account     TEXT    NOT NULL CHECK ({_in("account", BANK_ACCOUNTS)}),
  delta       INTEGER NOT NULL CHECK (delta != 0),
  reason_kind TEXT    NOT NULL CHECK ({_in("reason_kind", BANK_REASONS)}),
  reason_ref  TEXT,
  note        TEXT,
  actor       TEXT    NOT NULL CHECK ({_in("actor", BANK_ACTORS)}),
  created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS bank_by_kid ON bank (kid_id, account, created_at);

CREATE TRIGGER IF NOT EXISTS bank_no_update
BEFORE UPDATE ON bank
BEGIN
  SELECT RAISE(ABORT, 'bank is append-only');
END;

CREATE TRIGGER IF NOT EXISTS bank_no_delete
BEFORE DELETE ON bank
BEGIN
  SELECT RAISE(ABORT, 'bank is append-only');
END;

-- A child asking to take something out: a cash-out or a Roblox use. It
-- holds its amount while it waits, and becomes a bank row only when a parent
-- has actually handed over the money or the time. Like a redemption, its
-- status moves; the money only ever moves in `bank`.
CREATE TABLE IF NOT EXISTS bank_requests (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id       TEXT    NOT NULL,
  account      TEXT    NOT NULL CHECK ({_in("account", BANK_ACCOUNTS)}),
  amount       INTEGER NOT NULL CHECK (amount > 0),
  status       TEXT    NOT NULL CHECK ({_in("status", BANK_REQUEST_STATUSES)}),
  requested_at TEXT    NOT NULL,
  decided_at   TEXT,
  bank_id      INTEGER
);

CREATE INDEX IF NOT EXISTS bank_requests_by_kid ON bank_requests (kid_id, account, status);

CREATE TABLE IF NOT EXISTS settings_runtime (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def ensure_schema(connection: sqlite3.Connection) -> None:
    """Create what is missing and record the version. Safe to call on every open."""
    current: int = connection.execute("PRAGMA user_version").fetchone()[0]
    if current >= SCHEMA_VERSION:
        return
    connection.executescript(SCHEMA)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    connection.commit()
    if current == 0:
        logger.info("ledger created at %s", _describe(connection))
    else:
        logger.info("ledger upgraded from schema %d to %d", current, SCHEMA_VERSION)


def _describe(connection: sqlite3.Connection) -> str:
    row = connection.execute("PRAGMA database_list").fetchone()
    return str(row["file"]) if row is not None and row["file"] else "memory"


def open_connection(path: Path | None = None) -> sqlite3.Connection:
    """A configured connection with the schema applied.

    WAL so a parent approving something never blocks the dashboard's reads,
    and a five second busy timeout so two writes a second apart on the same
    Mac queue rather than raise.
    """
    target = path if path is not None else db_path()
    if str(target) != ":memory:":
        target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target, timeout=5.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    ensure_schema(connection)
    return connection


class Database:
    """The ledger file, opened per operation.

    SQLite is happiest with short-lived connections and WAL handles the
    concurrency this house produces — two iPads and a Mac — so there is no
    pool here and no connection held across a request.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else db_path()
        #: An in-memory database disappears when its connection closes, so
        #: tests that ask for one get a single connection kept open.
        self._memory: sqlite3.Connection | None = None
        if str(self.path) == ":memory:":
            self._memory = open_connection(self.path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if self._memory is not None:
            yield self._memory
            return
        connection = open_connection(self.path)
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """A transaction that commits on success and rolls back on anything else.

        Approving a claim writes the ledger row and marks the claim; either
        both land or neither does, so no approval can pay twice and none can
        pay nothing.
        """
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            connection.execute("COMMIT")

    def close(self) -> None:
        if self._memory is not None:
            self._memory.close()
            self._memory = None
