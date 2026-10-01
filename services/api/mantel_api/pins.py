"""Kid pad codes.

What this is for: one child opening a sibling's card and claiming their chores. It is a
lock on a sibling, not on an attacker — a four digit code has ten thousand
values and anyone who can reach the iPad can try them all. So the honest
description is a latch, and the storage is chosen to match: PBKDF2 from the
standard library, per-row salt, no new dependency and no pretence that this
would survive somebody who took the file.

The parent PIN is a different thing and stays in .env where it was.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3

#: Enough that a wrong guess costs a moment on the Mac, and few enough that
#: the right one is instant on an iPad's patience.
ITERATIONS = 200_000
SALT_BYTES = 16
DIGEST = "sha256"


def hash_pin(pin: str, *, salt: bytes | None = None) -> str:
    """"pbkdf2$<iterations>$<salt hex>$<hash hex>", which carries its own cost."""
    used = salt if salt is not None else os.urandom(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(DIGEST, pin.encode("utf-8"), used, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${used.hex()}${derived.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    """Constant-time check against a stored hash. A malformed row is a no."""
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$")
        if scheme != "pbkdf2":
            return False
        derived = hashlib.pbkdf2_hmac(
            DIGEST, pin.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived.hex(), digest_hex)


def set_pin(connection: sqlite3.Connection, kid_id: str, pin: str) -> None:
    """Set a kid's code, or clear it when the pin is empty."""
    if not pin:
        connection.execute("DELETE FROM kid_pins WHERE kid_id = ?", (kid_id,))
        return
    connection.execute(
        """
        INSERT INTO kid_pins (kid_id, pin_hash) VALUES (?, ?)
        ON CONFLICT (kid_id) DO UPDATE SET pin_hash = excluded.pin_hash
        """,
        (kid_id, hash_pin(pin)),
    )


def has_pin(connection: sqlite3.Connection, kid_id: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM kid_pins WHERE kid_id = ?", (kid_id,)
    ).fetchone()
    return row is not None


def which_have_pins(connection: sqlite3.Connection, kid_ids: list[str]) -> dict[str, bool]:
    held = {
        str(row["kid_id"]) for row in connection.execute("SELECT kid_id FROM kid_pins")
    }
    return {kid_id: kid_id in held for kid_id in kid_ids}


def check(connection: sqlite3.Connection, kid_id: str, pin: str) -> bool:
    """Whether this code opens this kid's card. No code set means yes."""
    row = connection.execute(
        "SELECT pin_hash FROM kid_pins WHERE kid_id = ?", (kid_id,)
    ).fetchone()
    if row is None:
        return True
    return verify_pin(pin, str(row["pin_hash"]))
