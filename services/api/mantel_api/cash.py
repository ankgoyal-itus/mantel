"""Cash handed over before the bank.

Before each child had a piggy bank (banks.py), an approved cash reward was a
parent's "Give Sam $5" to-do, and Paid on it wrote a row here. Nothing writes
here now; the rows stay, append-only, as the record of what was handed over.
"""

from __future__ import annotations

import sqlite3

from .models import Payout


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
