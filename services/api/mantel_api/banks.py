"""Each child's bank: a piggy bank in cents and a Roblox bank in minutes.

Points buy a deposit. A cash or Roblox reward, once a parent says yes, puts
its dollars or minutes in the child's bank in the same transaction as the
yes, and there is nothing left for a parent to do about it.

Taking something out is the other way round. A child asks — cash out $20,
or use an hour of Roblox — and the ask holds that amount, so it cannot be
asked for twice, and becomes a parent's to-do: "Pay Mira $20". Nothing
leaves the bank until the parent taps Paid or Done, because until then the
money has not been handed over and the time has not been given.

The bank is append-only like the ledger, and for the same reason: a balance
is SUM(delta) per kid and account, so a wrong row is answered with an
`adjust`, never an edit. When the policy plane arrives (v4), a Roblox use
becomes a grant it makes rather than a to-do; the row and the weekly cap
stay as they are.
"""

from __future__ import annotations

import sqlite3
from datetime import date as Date
from datetime import datetime

from .claims import ClaimError
from .models import (
    BankAccount,
    BankRequest,
    BankRow,
    Banks,
    CashAccount,
    KidBank,
    Points,
    RobloxAccount,
    Todo,
)

#: How a to-do names the request behind it: "bank:3".
PREFIX = "bank:"
#: How a banked redemption names the deposit it made: "deposit:7".
DEPOSIT = "deposit:"


def append(
    connection: sqlite3.Connection,
    *,
    kid_id: str,
    account: BankAccount,
    delta: int,
    reason_kind: str,
    actor: str,
    now: datetime,
    reason_ref: str | None = None,
    note: str | None = None,
) -> int:
    """Add one row and return its id. The only way a bank ever moves."""
    cursor = connection.execute(
        """
        INSERT INTO bank (kid_id, account, delta, reason_kind, reason_ref, note, actor, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (kid_id, account, delta, reason_kind, reason_ref, note, actor, now.isoformat()),
    )
    return int(cursor.lastrowid or 0)


def balance(connection: sqlite3.Connection, kid_id: str, account: BankAccount) -> int:
    """SUM(delta). Never stored, so it cannot disagree with the rows."""
    row = connection.execute(
        "SELECT COALESCE(SUM(delta), 0) AS total FROM bank WHERE kid_id = ? AND account = ?",
        (kid_id, account),
    ).fetchone()
    return int(row["total"])


def held(connection: sqlite3.Connection, kid_id: str, account: BankAccount) -> int:
    """What pending cash-outs or uses are holding."""
    row = connection.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM bank_requests"
        " WHERE kid_id = ? AND account = ? AND status = 'requested'",
        (kid_id, account),
    ).fetchone()
    return int(row["total"])


def available(connection: sqlite3.Connection, kid_id: str, account: BankAccount) -> int:
    return balance(connection, kid_id, account) - held(connection, kid_id, account)


def rows(
    connection: sqlite3.Connection,
    kid_id: str,
    *,
    limit: int = 20,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[BankRow]:
    """This child's rows across both accounts, newest first."""
    sql = "SELECT * FROM bank WHERE kid_id = ?"
    params: list[object] = [kid_id]
    if since is not None:
        sql += " AND created_at >= ?"
        params.append(since.isoformat())
    if until is not None:
        sql += " AND created_at < ?"
        params.append(until.isoformat())
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    return [BankRow.model_validate(dict(row)) for row in connection.execute(sql, params)]


def _request(row: sqlite3.Row) -> BankRequest:
    return BankRequest.model_validate(dict(row))


def pending(
    connection: sqlite3.Connection, kid_id: str | None = None, account: BankAccount | None = None
) -> list[BankRequest]:
    """Requests still waiting on a parent, oldest first."""
    sql = "SELECT * FROM bank_requests WHERE status = 'requested'"
    params: list[object] = []
    if kid_id is not None:
        sql += " AND kid_id = ?"
        params.append(kid_id)
    if account is not None:
        sql += " AND account = ?"
        params.append(account)
    sql += " ORDER BY requested_at, id"
    return [_request(row) for row in connection.execute(sql, params)]


def week_key(day: Date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def uses_this_week(connection: sqlite3.Connection, kid_id: str, day: Date) -> int:
    """Roblox uses asked for or given in this ISO week. A declined one is not a use."""
    wanted = week_key(day)
    count = 0
    for row in connection.execute(
        "SELECT requested_at FROM bank_requests"
        " WHERE kid_id = ? AND account = 'roblox' AND status IN ('requested', 'done')",
        (kid_id,),
    ):
        try:
            when = datetime.fromisoformat(str(row["requested_at"])).date()
        except ValueError:
            continue
        if week_key(when) == wanted:
            count += 1
    return count


def deposit_for_redemption(
    connection: sqlite3.Connection,
    *,
    kid_id: str,
    account: BankAccount,
    amount: int,
    redemption_id: int,
    note: str,
    now: datetime,
    actor: str = "parent",
) -> int:
    """An approved cash or Roblox reward, in the bank."""
    return append(
        connection,
        kid_id=kid_id,
        account=account,
        delta=amount,
        reason_kind="deposit",
        reason_ref=f"redemption:{redemption_id}",
        note=note,
        actor=actor,
        now=now,
    )


def _ask(
    connection: sqlite3.Connection,
    *,
    kid_id: str,
    account: BankAccount,
    amount: int,
    now: datetime,
) -> BankRequest:
    cursor = connection.execute(
        "INSERT INTO bank_requests (kid_id, account, amount, status, requested_at)"
        " VALUES (?, ?, ?, 'requested', ?)",
        (kid_id, account, amount, now.isoformat()),
    )
    found = by_id(connection, int(cursor.lastrowid or 0))
    assert found is not None  # noqa: S101 - just written
    return found


def cash_out(
    connection: sqlite3.Connection, banks: Banks, *, kid_id: str, cents: int, now: datetime
) -> BankRequest:
    """Ask to take money out. Holds it until a parent pays."""
    if cents < banks.cash_out_min_cents:
        raise ClaimError(409, f"the least you can take out is ${banks.cash_out_min_cents // 100}")
    if cents > available(connection, kid_id, "cash"):
        raise ClaimError(409, "there is not that much in the piggy bank")
    return _ask(connection, kid_id=kid_id, account="cash", amount=cents, now=now)


def use_roblox(
    connection: sqlite3.Connection,
    banks: Banks,
    points: Points,
    *,
    kid_id: str,
    minutes: int,
    now: datetime,
) -> BankRequest:
    """Ask to use Roblox time. Holds it until a parent gives it.

    v4: the policy plane grants the time here instead of a parent; the
    request row, the hold and the weekly cap stay exactly as they are.
    """
    if minutes not in banks.roblox_use_sizes:
        sizes = ", ".join(str(size) for size in banks.roblox_use_sizes)
        raise ClaimError(400, f"Roblox comes in {sizes} minutes")
    if minutes > available(connection, kid_id, "roblox"):
        raise ClaimError(409, "there is not that much in the Roblox bank")
    already = uses_this_week(connection, kid_id, now.date())
    if already >= points.roblox_per_week:
        raise ClaimError(409, f"that is {already} this week already, which is the limit")
    return _ask(connection, kid_id=kid_id, account="roblox", amount=minutes, now=now)


def by_id(connection: sqlite3.Connection, request_id: int) -> BankRequest | None:
    row = connection.execute("SELECT * FROM bank_requests WHERE id = ?", (request_id,)).fetchone()
    return _request(row) if row is not None else None


def _waiting(connection: sqlite3.Connection, request_id: int) -> BankRequest:
    found = by_id(connection, request_id)
    if found is None:
        raise ClaimError(404, f"no bank request {request_id}")
    if found.status != "requested":
        raise ClaimError(409, f"bank request {request_id} is already {found.status}")
    return found


def complete(connection: sqlite3.Connection, request_id: int, *, now: datetime) -> int:
    """Paid, or Done: the money or the time has been handed over. One row, once."""
    found = _waiting(connection, request_id)
    row_id = append(
        connection,
        kid_id=found.kid_id,
        account=found.account,
        delta=-found.amount,
        reason_kind="cashout" if found.account == "cash" else "use",
        reason_ref=f"{PREFIX}{request_id}",
        note="cashed out" if found.account == "cash" else "Roblox",
        actor="parent",
        now=now,
    )
    connection.execute(
        "UPDATE bank_requests SET status = 'done', decided_at = ?, bank_id = ? WHERE id = ?",
        (now.isoformat(), row_id, request_id),
    )
    return row_id


def decline(connection: sqlite3.Connection, request_id: int, *, now: datetime) -> BankRequest:
    """Not this time. Nothing moved, so nothing is written to the bank: the
    hold simply ends."""
    _waiting(connection, request_id)
    connection.execute(
        "UPDATE bank_requests SET status = 'declined', decided_at = ? WHERE id = ?",
        (now.isoformat(), request_id),
    )
    found = by_id(connection, request_id)
    assert found is not None  # noqa: S101 - just updated
    return found


def adjust(
    connection: sqlite3.Connection,
    *,
    kid_id: str,
    account: BankAccount,
    delta: int,
    note: str,
    now: datetime,
) -> int:
    """Birthday money, or a correction. Never an edit, and never below what
    pending requests are holding."""
    if not note.strip():
        raise ClaimError(400, "an adjustment needs to say what it was for")
    if delta < 0 and available(connection, kid_id, account) + delta < 0:
        raise ClaimError(409, "that would take the bank below zero")
    return append(
        connection,
        kid_id=kid_id,
        account=account,
        delta=delta,
        reason_kind="adjust",
        reason_ref="parent",
        note=note.strip(),
        actor="parent",
        now=now,
    )


def view(
    connection: sqlite3.Connection, kid_id: str, banks: Banks, points: Points, today: Date
) -> KidBank:
    cash_pending = pending(connection, kid_id, "cash")
    roblox_pending = pending(connection, kid_id, "roblox")
    cents = balance(connection, kid_id, "cash")
    minutes = balance(connection, kid_id, "roblox")
    return KidBank(
        kid_id=kid_id,
        cash=CashAccount(
            cents=cents,
            available_cents=cents - sum(item.amount for item in cash_pending),
            pending=cash_pending,
        ),
        roblox=RobloxAccount(
            minutes=minutes,
            available_minutes=minutes - sum(item.amount for item in roblox_pending),
            pending=roblox_pending,
            uses_this_week=uses_this_week(connection, kid_id, today),
            per_week=points.roblox_per_week,
            sizes=list(banks.roblox_use_sizes),
        ),
        cash_out_min_cents=banks.cash_out_min_cents,
        recent=rows(connection, kid_id, limit=20),
    )


def todos(connection: sqlite3.Connection, names: dict[str, str]) -> list[Todo]:
    """Every pending request, as the parent's to-do it is."""
    items = []
    for item in pending(connection):
        who = names.get(item.kid_id, item.kid_id)
        if item.account == "cash":
            title = f"Pay {who} {dollars(item.amount)}"
        else:
            title = f"Give {who} {item.amount} min of Roblox today"
        items.append(
            Todo(
                ref=f"{PREFIX}{item.id}",
                kind="cashout" if item.account == "cash" else "roblox",
                kid_id=item.kid_id,
                title=title,
                cents=item.amount if item.account == "cash" else None,
                minutes=item.amount if item.account == "roblox" else None,
                request_id=item.id,
            )
        )
    return items


def pending_count(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS n FROM bank_requests WHERE status = 'requested'"
    ).fetchone()
    return int(row["n"])


def dollars(cents: int) -> str:
    """$20, or $20.50 when there are cents to say."""
    whole, part = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}${whole}" if part == 0 else f"{sign}${whole}.{part:02d}"


def duration(minutes: int) -> str:
    """2 h 30 min, 1 h, 45 min."""
    hours, rest = divmod(abs(minutes), 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    return f"{hours} h" if hours else f"{rest} min"


def describe(row: BankRow) -> str:
    """One row for the digest: "+$5 · $5 cash", "−1 h · Roblox"."""
    amount = dollars(abs(row.delta)) if row.account == "cash" else duration(row.delta)
    sign = "+" if row.delta > 0 else "−"
    return f"{sign}{amount} · {row.note}" if row.note else f"{sign}{amount}"


def move_owed_cash(connection: sqlite3.Connection, *, now: datetime) -> int:
    """Cash rewards approved before the bank and never paid go into it.

    Before the bank, an approved cash reward waited as a parent's "Give Sam
    $5" to-do, its dollars written on the redemption as "cash:5". Each one
    still waiting becomes a deposit and is marked fulfilled — once, since the
    status change is what this looks for. Returns how many moved.
    """
    waiting = connection.execute(
        "SELECT id, kid_id, fulfilment_ref FROM redemptions"
        " WHERE status = 'approved' AND fulfilment_ref LIKE 'cash:%'"
    ).fetchall()
    moved = 0
    for row in waiting:
        try:
            whole = int(str(row["fulfilment_ref"]).removeprefix("cash:"))
        except ValueError:
            continue
        if whole <= 0:
            continue
        row_id = deposit_for_redemption(
            connection,
            kid_id=str(row["kid_id"]),
            account="cash",
            amount=whole * 100,
            redemption_id=int(row["id"]),
            note=f"${whole} cash",
            now=now,
            actor="system",
        )
        connection.execute(
            "UPDATE redemptions SET status = 'fulfilled', fulfilment_ref = ? WHERE id = ?",
            (f"{DEPOSIT}{row_id}", int(row["id"])),
        )
        moved += 1
    return moved
