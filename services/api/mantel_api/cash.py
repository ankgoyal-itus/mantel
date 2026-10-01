"""Points turned into dollars, and dollars handed over.

A cash reward is bought with points like any other. Approving it writes what
it is worth on the redemption and makes it a parent's to-do — "Give Sam
$5" — and Paid on that card records the payout for that reward and nothing
else. What is owed is derived every time, never stored: the dollars written
on each approved cash redemption, less every payout recorded.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from .claims import ClaimError
from .models import Payout

#: How a banked cash redemption says what it was worth: "cash:5".
PREFIX = "cash:"


def dollars_of(ref: object) -> int:
    """What "cash:5" was worth; nothing, for anything else."""
    text = str(ref or "")
    if not text.startswith(PREFIX):
        return 0
    try:
        return int(text.removeprefix(PREFIX))
    except ValueError:
        return 0


def earned(connection: sqlite3.Connection, kid_id: str) -> int:
    """Every dollar this child's approved cash rewards were worth, paid or not."""
    rows = connection.execute(
        "SELECT fulfilment_ref FROM redemptions"
        " WHERE kid_id = ? AND status IN ('approved', 'fulfilled') AND fulfilment_ref LIKE ?",
        (kid_id, f"{PREFIX}%"),
    )
    return sum(dollars_of(row["fulfilment_ref"]) for row in rows)


def paid(connection: sqlite3.Connection, kid_id: str) -> int:
    row = connection.execute(
        "SELECT COALESCE(SUM(dollars), 0) AS total FROM payouts WHERE kid_id = ?", (kid_id,)
    ).fetchone()
    return int(row["total"])


def owed(connection: sqlite3.Connection, kid_id: str) -> int:
    """What a parent still has to hand over. Never below zero."""
    return max(0, earned(connection, kid_id) - paid(connection, kid_id))


def pay_for(connection: sqlite3.Connection, redemption_id: int, *, now: datetime) -> int:
    """Paid, on one cash reward's to-do: its dollars handed over, recorded
    against it, and the reward done. Twice is refused, not paid twice."""
    row = connection.execute(
        "SELECT kid_id, status, fulfilment_ref FROM redemptions WHERE id = ?", (redemption_id,)
    ).fetchone()
    if row is None:
        raise ClaimError(404, f"no redemption {redemption_id}")
    dollars = dollars_of(row["fulfilment_ref"])
    if dollars <= 0:
        raise ClaimError(400, f"redemption {redemption_id} is not cash")
    if str(row["status"]) != "approved":
        raise ClaimError(409, f"redemption {redemption_id} is already {row['status']}")
    cursor = connection.execute(
        "INSERT INTO payouts (kid_id, dollars, paid_at, note) VALUES (?, ?, ?, ?)",
        (str(row["kid_id"]), dollars, now.isoformat(), f"redemption:{redemption_id}"),
    )
    connection.execute(
        "UPDATE redemptions SET status = 'fulfilled' WHERE id = ?", (redemption_id,)
    )
    return int(cursor.lastrowid or 0)


def history(connection: sqlite3.Connection, kid_id: str, limit: int = 10) -> list[Payout]:
    rows = connection.execute(
        "SELECT * FROM payouts WHERE kid_id = ? ORDER BY paid_at DESC, id DESC LIMIT ?",
        (kid_id, limit),
    )
    return [
        Payout(
            id=int(row["id"]),
            kid_id=str(row["kid_id"]),
            dollars=int(row["dollars"]),
            paid_at=str(row["paid_at"]),
            note=row["note"],
        )
        for row in rows
    ]
