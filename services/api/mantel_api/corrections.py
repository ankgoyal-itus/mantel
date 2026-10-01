"""Putting a wrong row right.

The ledger is append-only, by trigger, and that does not change here: a
mistake is answered with rows that undo it, never with an eraser. Two ways:

* **Undo** — one row taking the points back ("Undo · Tidy room"). If the row
  paid for a chore, the chore reopens: its claim goes, and the kid can claim
  it again, as if it had never been approved.
* **Move** — for an award or an adjustment given to the wrong child: the
  undo, and the same points to the right one.

Every correction row carries `correct:<id>` as its reference, which is how a
row is known to be corrected already (it cannot be corrected twice) and how a
correction is known not to be correctable itself.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import datetime
from typing import Literal

from . import ledger
from .claims import ClaimError
from .db import FAMILY
from .models import LedgerRow

#: What a parent can put right: what a parent wrote. A reward asked for, a
#: refund and a jar move each have their own way back.
UNDOABLE = ("task", "award", "adjust")
#: Moving a chore to another child would pay them for a claim they never
#: made; approve theirs instead.
MOVABLE = ("award", "adjust")

Action = Literal["undo", "move"]


def ref(row_id: int) -> str:
    return f"correct:{row_id}"


def corrected_ids(connection: sqlite3.Connection) -> set[int]:
    """Every row some correction answers."""
    rows = connection.execute(
        "SELECT reason_ref FROM ledger WHERE reason_ref LIKE 'correct:%'"
    ).fetchall()
    found: set[int] = set()
    for row in rows:
        try:
            found.add(int(str(row["reason_ref"]).split(":", 1)[1]))
        except ValueError:  # noqa: PERF203 - a stray reference is not a crash
            continue
    return found


def can(row: LedgerRow, corrected: set[int]) -> list[Action]:
    """What the parent screen may offer on a row."""
    if row.id in corrected or row.kid_id == FAMILY or (row.reason_ref or "").startswith("correct:"):
        return []
    actions: list[Action] = []
    if row.reason_kind in UNDOABLE:
        actions.append("undo")
    if row.reason_kind in MOVABLE:
        actions.append("move")
    return actions


def correct(
    connection: sqlite3.Connection,
    *,
    row_id: int,
    action: Action,
    to_kid: str | None,
    names: Mapping[str, str],
    now: datetime,
) -> list[int]:
    """Write the correction and return the new rows' ids. One transaction:
    the caller's connection."""
    found = connection.execute("SELECT * FROM ledger WHERE id = ?", (row_id,)).fetchone()
    if found is None:
        raise ClaimError(404, f"no ledger row {row_id}")
    row = LedgerRow.from_row(dict(found))
    allowed = can(row, corrected_ids(connection))
    if row_id in corrected_ids(connection):
        raise ClaimError(409, "that row has already been corrected")
    if action not in allowed:
        raise ClaimError(400, f"a {row.reason_kind} row cannot be {action}d")

    what = row.note or row.reason_kind
    # Taking points back must not leave a child owing: if they have spent
    # them, the conversation is theirs to have, not the ledger's.
    if ledger.balance(connection, row.kid_id) - row.delta < 0:
        raise ClaimError(409, f"{names.get(row.kid_id, row.kid_id)} has already spent those points")

    written: list[int] = []
    if action == "move":
        if to_kid is None or to_kid not in names or to_kid == row.kid_id:
            raise ClaimError(400, "move it to the other child")
        if ledger.balance(connection, to_kid) + row.delta < 0:
            raise ClaimError(409, f"{names[to_kid]} does not have the points to take")

    written.append(
        ledger.append(
            connection,
            kid_id=row.kid_id,
            delta=-row.delta,
            reason_kind="adjust",
            reason_ref=ref(row_id),
            note=(
                f"Undo · {what}"
                if action == "undo"
                else f"Moved to {names[to_kid or '']} · {what}"
            ),
            actor="parent",
            now=now,
        )
    )
    if action == "move" and to_kid is not None:
        written.append(
            ledger.append(
                connection,
                kid_id=to_kid,
                delta=row.delta,
                reason_kind="award" if row.delta > 0 else "adjust",
                reason_ref=ref(row_id),
                note=f"{what} · from {names.get(row.kid_id, row.kid_id)}",
                actor="parent",
                now=now,
            )
        )

    # A chore's points taken back: the chore is not done after all.
    if row.reason_kind == "task" and row.reason_ref:
        parts = row.reason_ref.split(":")
        if len(parts) == 3:
            kid_id, task_id, day = parts
            connection.execute(
                """
                DELETE FROM claims
                WHERE kid_id = ? AND task_id = ? AND date = ? AND status = 'approved'
                """,
                (kid_id, task_id, day),
            )
    return written
