"""Meals picked a week at a time, and what each slot comes to.

meals.yaml is the family's plan and nothing else. The children's choices are
rows in the picks table, and what a slot is — the plan, a child's dish, or
contested — is worked out every time it is read, in one place:
`resolve_slot`. Nothing here writes to the ledger: picks are free.

    no picks                      → the plan
    one child                     → their dish, with their face on it
    two children, the same dish   → that dish, with both faces
    two children, different dishes→ contested: the plan still stands, with
                                    both choices on it, until a parent
                                    decides or the slot locks

A child may change their own pick until the slot locks — breakfast and lunch
at 20:00 the evening before, dinner at 16:00 the same day — or until a parent
has decided it. A contested slot nobody decided in time falls back to the
plan, and both children's dishes move to the next day that slot is free and
the diet rules allow them, with a note saying so.

A treat is a dish like any other, except that it waits for a parent's OK
(status "proposed") before it counts, and a child has two a week.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import date as Date
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from ruamel.yaml.comments import CommentedMap

from .claims import ClaimError
from .models import (
    ApprovalItem,
    DayMeals,
    DayPicks,
    DecisionResult,
    MealChoice,
    MealsCatalog,
    MealSlot,
    PickChoice,
    PickDecision,
    PickRow,
    PickSlot,
    Protein,
    SlotView,
)
from .out import is_out
from .picks import MAX_TREATS_PER_WEEK, week_of
from .yaml_edit import load, serialize, write_atomic

logger = logging.getLogger("mantel_api.weekly")

SLOTS: tuple[PickSlot, ...] = ("breakfast", "lunch", "dinner")

#: When each slot stops taking changes: (days before the meal, time of day).
LOCKS: dict[str, tuple[int, time]] = {
    "breakfast": (1, time(20, 0)),
    "lunch": (1, time(20, 0)),
    "dinner": (0, time(16, 0)),
}

#: How far ahead a moved dish may be put before it is given up on.
MOVE_HORIZON_DAYS = 30

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

Validate = Callable[[str], None]
#: Whether meat, fish and egg are allowed on a date.
DietOk = Callable[[Date], bool]


def lock_time(day: Date, slot: str, now: datetime) -> datetime:
    days_before, at = LOCKS[slot]
    return datetime.combine(day - timedelta(days=days_before), at, tzinfo=now.tzinfo)


def is_locked(day: Date, slot: str, now: datetime) -> bool:
    return now >= lock_time(day, slot, now)


def said(day: Date, slot: str) -> str:
    """"Thursday dinner"."""
    return f"{WEEKDAYS[day.weekday()]} {slot}"


# -- reading --------------------------------------------------------------


def _row(record: sqlite3.Row, catalog: MealsCatalog | None) -> PickRow:
    dish_id = str(record["dish_id"])
    dish = next((one for one in catalog.dishes if one.id == dish_id), None) if catalog else None
    return PickRow(
        id=int(record["id"]),
        kid_id=str(record["kid_id"]),
        date=Date.fromisoformat(str(record["date"])),
        slot=record["slot"],
        dish_id=dish_id,
        kids_protein=record["kids_protein"],
        status=record["status"],
        decided_by=record["decided_by"],
        decided_at=record["decided_at"],
        moved_to=Date.fromisoformat(str(record["moved_to"])) if record["moved_to"] else None,
        created_at=str(record["created_at"]),
        note=record["note"],
        name=dish.name if dish is not None else dish_id,
        treat=dish.treat if dish is not None else False,
    )


def rows_between(
    connection: sqlite3.Connection, start: Date, end: Date, catalog: MealsCatalog | None
) -> list[PickRow]:
    found = connection.execute(
        "SELECT * FROM picks WHERE date BETWEEN ? AND ? ORDER BY created_at, id",
        (start.isoformat(), end.isoformat()),
    )
    return [_row(record, catalog) for record in found]


def by_id(
    connection: sqlite3.Connection, pick_id: int, catalog: MealsCatalog | None
) -> PickRow | None:
    record = connection.execute("SELECT * FROM picks WHERE id = ?", (pick_id,)).fetchone()
    return _row(record, catalog) if record is not None else None


def resolve_slot(
    day: Date,
    slot: PickSlot,
    plan: MealSlot | None,
    picks: list[PickRow],
    now: datetime,
) -> SlotView:
    """What one meal comes to. The one place this is decided."""
    mine = [pick for pick in picks if pick.date == day and pick.slot == slot]
    chosen = [pick for pick in mine if pick.status == "chosen"]
    decided = any(pick.decided_by is not None for pick in mine)
    dishes: list[str] = []
    for pick in chosen:
        if pick.dish_id not in dishes:
            dishes.append(pick.dish_id)

    resolved: MealSlot | None = plan
    contested = False
    if len(dishes) == 1:
        first = chosen[0]
        resolved = MealSlot(
            name=first.name,
            id=first.dish_id,
            # Dinner out carries its place; any other pick's note is history.
            note=first.note if is_out(first.dish_id) else None,
            kids_protein=first.kids_protein,
            picked_by=[pick.kid_id for pick in chosen],
            confirmed=True,
            plan=plan.id if plan is not None and plan.id != first.dish_id else None,
        )
    elif len(dishes) > 1:
        contested = True
        first = chosen[0]
        base = plan or MealSlot(name=first.name, id=first.dish_id)
        resolved = base.model_copy(
            update={
                "picked_by": [pick.kid_id for pick in chosen],
                "confirmed": False,
                "plan": plan.id if plan is not None else None,
                "picks": {
                    pick.kid_id: PickChoice(id=pick.dish_id, kids_protein=pick.kids_protein)
                    for pick in chosen
                },
            }
        )
    return SlotView(
        date=day,
        slot=slot,
        plan=plan,
        picks=mine,
        resolved=resolved,
        contested=contested,
        locked=is_locked(day, slot, now),
        decided=decided,
    )


class Week:
    """The plan and the picks for a stretch of days, resolved slot by slot.

    Has the `.on(day)` a Meals has, so everything that used to read the plan
    — the day builder, the picker's repeat rule, the parent grid — reads what
    the house is actually eating instead.
    """

    def __init__(self, plan: Any, picks: list[PickRow], now: datetime) -> None:
        self.plan = plan
        self.picks = picks
        self.now = now

    def slot(self, day: Date, slot: PickSlot) -> SlotView:
        return resolve_slot(day, slot, getattr(self.plan.on(day), slot, None), self.picks, self.now)

    def day(self, day: Date) -> DayPicks:
        return DayPicks(
            date=day,
            breakfast=self.slot(day, "breakfast"),
            lunch=self.slot(day, "lunch"),
            dinner=self.slot(day, "dinner"),
        )

    def on(self, day: Date) -> DayMeals:
        planned = self.plan.on(day)
        return DayMeals(
            breakfast=self.slot(day, "breakfast").resolved,
            lunch=self.slot(day, "lunch").resolved,
            dinner=self.slot(day, "dinner").resolved,
            snack=planned.snack,
        )


def week(
    connection: sqlite3.Connection,
    plan: Any,
    catalog: MealsCatalog | None,
    start: Date,
    end: Date,
    now: datetime,
) -> Week:
    # A margin either side, so the repeat rule can look four days around.
    picks = rows_between(connection, start - timedelta(days=7), end + timedelta(days=7), catalog)
    return Week(plan, picks, now)


# -- writing --------------------------------------------------------------


def _insert(
    connection: sqlite3.Connection,
    *,
    kid_id: str,
    day: Date,
    slot: str,
    dish_id: str,
    protein: Protein,
    status: str,
    now: datetime,
    decided_by: str | None = None,
    note: str | None = None,
) -> int:
    cursor = connection.execute(
        "INSERT INTO picks (kid_id, date, slot, dish_id, kids_protein, status, decided_by,"
        " decided_at, created_at, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            kid_id,
            day.isoformat(),
            slot,
            dish_id,
            protein,
            status,
            decided_by,
            now.isoformat() if decided_by else None,
            now.isoformat(),
            note,
        ),
    )
    return int(cursor.lastrowid or 0)


def treats_this_week(
    connection: sqlite3.Connection,
    catalog: MealsCatalog,
    kid_id: str,
    day: Date,
    *,
    except_slot: tuple[Date, str] | None = None,
) -> int:
    """A kid's treats that week, waiting or approved."""
    treat_ids = {dish.id for dish in catalog.dishes if dish.treat}
    start, end = week_of(day)
    count = 0
    for pick in rows_between(connection, start, end, catalog):
        if pick.kid_id != kid_id or pick.status not in ("chosen", "proposed"):
            continue
        if except_slot is not None and (pick.date, pick.slot) == except_slot:
            continue
        if pick.dish_id in treat_ids:
            count += 1
    return count


def choose(
    connection: sqlite3.Connection,
    catalog: MealsCatalog,
    *,
    kid_id: str,
    day: Date,
    slot: PickSlot,
    dish_id: str,
    protein: Protein,
    now: datetime,
    note: str | None = None,
) -> int:
    """A child's pick for one meal, replacing their own earlier pick for it.

    `note` is where, for Dinner out; nothing else carries one from a child.

    Refused once the slot has locked or a parent has decided it. Never
    touches another child's pick: each child has at most one per slot, and
    this only ever replaces the asker's.
    """
    if is_locked(day, slot, now):
        raise ClaimError(409, "Locked — too late to change")
    mine = [
        pick for pick in rows_between(connection, day, day, catalog) if pick.slot == slot
    ]
    if any(pick.decided_by is not None for pick in mine):
        raise ClaimError(409, "a parent has already decided this one")

    dish = next((one for one in catalog.dishes if one.id == dish_id), None)
    if dish is None:
        raise ClaimError(404, f"no dish {dish_id!r}")
    status = "chosen"
    if dish.treat:
        used = treats_this_week(connection, catalog, kid_id, day, except_slot=(day, slot))
        if used >= MAX_TREATS_PER_WEEK:
            raise ClaimError(409, "two treats a week is the deal")
        status = "proposed"

    connection.execute(
        "DELETE FROM picks WHERE kid_id = ? AND date = ? AND slot = ?"
        " AND status IN ('chosen', 'proposed')",
        (kid_id, day.isoformat(), slot),
    )
    return _insert(
        connection,
        kid_id=kid_id,
        day=day,
        slot=slot,
        dish_id=dish_id,
        protein=protein,
        status=status,
        now=now,
        note=note if is_out(dish_id) else None,
    )


def withdraw(
    connection: sqlite3.Connection,
    pick_id: int,
    *,
    kid_id: str,
    now: datetime,
) -> None:
    """A child taking their own pick back, while it can still change."""
    pick = by_id(connection, pick_id, None)
    if pick is None:
        raise ClaimError(404, f"no pick {pick_id}")
    if pick.kid_id != kid_id:
        raise ClaimError(403, "that is not your pick")
    if pick.status not in ("chosen", "proposed") or pick.decided_by is not None:
        raise ClaimError(409, "a parent has already decided this one")
    if is_locked(pick.date, pick.slot, now):
        raise ClaimError(409, "Locked — too late to change")
    connection.execute("DELETE FROM picks WHERE id = ?", (pick_id,))


def next_free_day(
    connection: sqlite3.Connection,
    catalog: MealsCatalog,
    *,
    slot: str,
    dish_id: str,
    protein: Protein,
    after: Date,
    diet_ok: DietOk,
    taken: set[Date] | None = None,
) -> Date | None:
    """The first day after `after` with nobody's pick in that slot, on which
    the diet rules allow the dish as the child wanted it."""
    dish = next((one for one in catalog.dishes if one.id == dish_id), None)
    taken = taken or set()
    for offset in range(1, MOVE_HORIZON_DAYS + 1):
        day = after + timedelta(days=offset)
        if day in taken:
            continue
        busy = connection.execute(
            "SELECT 1 FROM picks WHERE date = ? AND slot = ? AND status IN ('chosen', 'proposed')",
            (day.isoformat(), slot),
        ).fetchone()
        if busy is not None:
            continue
        if protein != "veg" and not diet_ok(day):
            continue
        if dish is not None and protein == "veg" and "veg" not in dish.protein and not diet_ok(day):
            continue
        return day
    return None


def _move(
    connection: sqlite3.Connection,
    catalog: MealsCatalog,
    pick: PickRow,
    *,
    diet_ok: DietOk,
    now: datetime,
    by: str,
    why: str,
    taken: set[Date],
) -> Date | None:
    """Mark a pick moved and stand it up again on the next free allowed day."""
    target = next_free_day(
        connection,
        catalog,
        slot=pick.slot,
        dish_id=pick.dish_id,
        protein=pick.kids_protein,
        after=pick.date,
        diet_ok=diet_ok,
        taken=taken,
    )
    if target is None:
        connection.execute(
            "UPDATE picks SET status = 'passed', decided_by = ?, decided_at = ?, note = ?"
            " WHERE id = ?",
            (by, now.isoformat(), f"{why}; no free day to move it to", pick.id),
        )
        return None
    taken.add(target)
    connection.execute(
        "UPDATE picks SET status = 'moved', moved_to = ?, decided_by = ?, decided_at = ?,"
        " note = ? WHERE id = ?",
        (target.isoformat(), by, now.isoformat(), why, pick.id),
    )
    _insert(
        connection,
        kid_id=pick.kid_id,
        day=target,
        slot=pick.slot,
        dish_id=pick.dish_id,
        protein=pick.kids_protein,
        status="chosen",
        now=now,
        decided_by=by,
        note=f"moved from {said(pick.date, pick.slot)}",
    )
    return target


def contested_slots(connection: sqlite3.Connection) -> list[tuple[Date, str]]:
    found = connection.execute(
        "SELECT date, slot FROM picks WHERE status = 'chosen'"
        " GROUP BY date, slot HAVING COUNT(DISTINCT dish_id) > 1 ORDER BY date, slot"
    )
    return [(Date.fromisoformat(str(row["date"])), str(row["slot"])) for row in found]


def settle_locked(
    connection: sqlite3.Connection,
    catalog: MealsCatalog,
    *,
    diet_ok: DietOk,
    now: datetime,
) -> int:
    """Contested slots that locked before anyone decided: back to the plan,
    and both dishes to the next free allowed day. Idempotent — a settled slot
    is no longer contested. Returns how many picks moved."""
    moved = 0
    for day, slot in contested_slots(connection):
        if not is_locked(day, slot, now):
            continue
        chosen = [
            pick
            for pick in rows_between(connection, day, day, catalog)
            if pick.slot == slot and pick.status == "chosen"
        ]
        taken: set[Date] = set()
        for pick in chosen:
            _move(
                connection,
                catalog,
                pick,
                diet_ok=diet_ok,
                now=now,
                by="lock",
                why=f"not decided before {said(day, slot)} locked",
                taken=taken,
            )
            moved += 1
        logger.info("%s %s locked undecided; %d picks moved", day, slot, len(chosen))
    return moved


def decide(
    connection: sqlite3.Connection,
    catalog: MealsCatalog,
    decision: PickDecision,
    *,
    diet_ok: DietOk,
    now: datetime,
) -> DecisionResult:
    """A parent settling a contested slot: one child's dish, and the other's
    passed — or, alternating, planned for the next day it can be."""
    chosen = [
        pick
        for pick in rows_between(connection, decision.date, decision.date, catalog)
        if pick.slot == decision.slot and pick.status == "chosen"
    ]
    winner = next((pick for pick in chosen if pick.kid_id == decision.winner_kid_id), None)
    if winner is None:
        raise ClaimError(404, f"{decision.winner_kid_id} has no pick for that meal")
    losers = [pick for pick in chosen if pick.dish_id != winner.dish_id]
    if not losers:
        raise ClaimError(409, "nothing to decide: that meal is not contested")

    connection.execute(
        "UPDATE picks SET decided_by = 'parent', decided_at = ? WHERE date = ? AND slot = ?"
        " AND status = 'chosen' AND dish_id = ?",
        (now.isoformat(), decision.date.isoformat(), decision.slot, winner.dish_id),
    )
    result = DecisionResult(
        slot=decision.slot, winner_kid_id=winner.kid_id, winner_date=decision.date
    )
    taken: set[Date] = set()
    for loser in losers:
        if decision.mode == "alternate":
            target = _move(
                connection,
                catalog,
                loser,
                diet_ok=diet_ok,
                now=now,
                by="parent",
                why=f"alternating with {winner.kid_id}",
                taken=taken,
            )
            result.loser_kid_id = loser.kid_id
            result.loser_date = target
        else:
            connection.execute(
                "UPDATE picks SET status = 'passed', decided_by = 'parent', decided_at = ?"
                " WHERE id = ?",
                (now.isoformat(), loser.id),
            )
    return result


def answer_treat(
    connection: sqlite3.Connection, pick_id: int, *, approve: bool, now: datetime
) -> PickRow:
    pick = by_id(connection, pick_id, None)
    if pick is None:
        raise ClaimError(404, f"no pick {pick_id}")
    if pick.status != "proposed":
        raise ClaimError(409, f"that pick is already {pick.status}")
    connection.execute(
        "UPDATE picks SET status = ?, decided_by = 'parent', decided_at = ? WHERE id = ?",
        ("chosen" if approve else "passed", now.isoformat(), pick_id),
    )
    answered = by_id(connection, pick_id, None)
    assert answered is not None  # noqa: S101 - just updated
    return answered


def override(connection: sqlite3.Connection, day: Date, slot: str, *, now: datetime) -> int:
    """A parent's pen: whatever the children picked for this meal gives way.
    Returns how many picks it passed."""
    cursor = connection.execute(
        "UPDATE picks SET status = 'passed', decided_by = 'parent', decided_at = ?"
        " WHERE date = ? AND slot = ? AND status IN ('chosen', 'proposed')",
        (now.isoformat(), day.isoformat(), slot),
    )
    return int(cursor.rowcount)


# -- the parent's queue ---------------------------------------------------


def waiting(
    connection: sqlite3.Connection,
    catalog: MealsCatalog,
    plan: Any,
    today: Date,
    now: datetime,
) -> list[ApprovalItem]:
    """What only a parent can settle: contested meals still open, soonest
    first, and treats waiting on an OK."""
    items: list[ApprovalItem] = []
    for day, slot in contested_slots(connection):
        if day < today or is_locked(day, slot, now):
            continue
        pick_slot: PickSlot = "dinner" if slot == "dinner" else (
            "lunch" if slot == "lunch" else "breakfast"
        )
        view = resolve_slot(
            day,
            pick_slot,
            getattr(plan.on(day), slot, None),
            rows_between(connection, day, day, catalog),
            now,
        )
        choices: dict[str, MealChoice] = {}
        for pick in view.picks:
            if pick.status != "chosen":
                continue
            choice = choices.setdefault(
                pick.dish_id, MealChoice(id=pick.dish_id, name=pick.name, kids=[])
            )
            choice.kids.append(pick.kid_id)
        items.append(
            ApprovalItem(
                kind="meal",
                id=0,
                kid_id=view.picks[0].kid_id,
                title=said(day, slot),
                points=0,
                when=f"{day.isoformat()}T00:00:00",
                date=day,
                slot=pick_slot,
                choices=list(choices.values()),
                plan_name=view.plan.name if view.plan is not None else None,
                contested=True,
            )
        )
    proposed = connection.execute(
        "SELECT * FROM picks WHERE status = 'proposed' AND date >= ? ORDER BY date, id",
        (today.isoformat(),),
    )
    for record in proposed:
        pick = _row(record, catalog)
        items.append(
            ApprovalItem(
                kind="treat",
                id=pick.id,
                pick_id=pick.id,
                kid_id=pick.kid_id,
                title=pick.name,
                note=pick.note if is_out(pick.dish_id) else None,
                points=0,
                when=pick.created_at,
                date=pick.date,
                slot=pick.slot,
            )
        )
    return items


# -- from meals.yaml ------------------------------------------------------


def _choices_in(cell: CommentedMap) -> dict[str, tuple[str, str]]:
    """Each child's (dish, protein) on a proposed or picked slot."""
    held = cell.get("picks")
    if isinstance(held, CommentedMap):
        return {
            str(kid): (str(one.get("id")), str(one.get("kids_protein") or "veg"))
            for kid, one in held.items()
            if isinstance(one, CommentedMap) and one.get("id")
        }
    names = cell.get("picked_by")
    dish = cell.get("id")
    if not isinstance(names, list) or not dish:
        return {}
    protein = str(cell.get("kids_protein") or "veg")
    return {str(name): (str(dish), protein) for name in names}


def migrate_from_yaml(
    path: Path, connection: sqlite3.Connection, *, now: datetime, validate: Validate
) -> int:
    """Move every pick written into meals.yaml into the picks table, and put
    each slot back to the family's plan. Idempotent: once moved, there is
    nothing left in the file to move. Returns how many picks moved."""
    if not path.exists():
        return 0
    doc = load(path)
    if not isinstance(doc, CommentedMap):
        return 0
    moved = 0
    for key in list(doc):
        slots = doc[key]
        if not isinstance(slots, CommentedMap):
            continue
        day = key if isinstance(key, Date) else Date.fromisoformat(str(key))
        for slot in SLOTS:
            cell = slots.get(slot)
            if not isinstance(cell, CommentedMap):
                continue
            choices = _choices_in(cell)
            if not choices:
                continue
            confirmed = cell.get("confirmed", True) is not False
            for kid_id, (dish_id, protein) in choices.items():
                _insert(
                    connection,
                    kid_id=kid_id,
                    day=day,
                    slot=slot,
                    dish_id=dish_id,
                    protein=protein,  # type: ignore[arg-type]
                    status="chosen",
                    now=now,
                    decided_by="parent" if confirmed else None,
                    note="from meals.yaml",
                )
                moved += 1
            plan = cell.get("plan")
            if plan:
                restored = CommentedMap()
                restored["id"] = str(plan)
                if cell.get("note"):
                    restored["note"] = cell["note"]
                slots[slot] = restored
            elif confirmed:
                for field in ("picked_by", "confirmed", "picks", "plan"):
                    cell.pop(field, None)
            else:
                del slots[slot]
    if moved:
        text = serialize(doc, now)
        validate(text)
        write_atomic(path, text)
        logger.info("moved %d picks out of meals.yaml into the picks table", moved)
    return moved
