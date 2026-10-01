"""Turning a parent's edits into content files, without trampling the rest.

Every write validates the candidate text first: a rejected edit leaves the
file exactly as it was, and the API keeps serving what it already had.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date as Date
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .festivals import groups as festival_groups
from .models import (
    DayMeals,
    DietEdit,
    Family,
    KidEdit,
    MealCell,
    MealChoice,
    MealDay,
    MealSlot,
    ParentSettings,
    PickChoice,
    Settings,
)
from .out import is_out
from .school_events import normalise
from .yaml_edit import load, serialize, write_atomic

SLOTS = ("breakfast", "lunch", "dinner")

Validate = Callable[[str], None]


def settings_view(settings: Settings, family: Family | None = None) -> ParentSettings:
    return ParentSettings(
        night_start=settings.night.start,
        night_end=settings.night.end,
        idle_minutes=settings.idle_minutes,
        night_idle_minutes=settings.night.idle_minutes,
        night_frame=settings.night.frame,
        slide_seconds=settings.slide_seconds,
        refresh_minutes=settings.refresh_minutes,
        frame_chip=settings.frame.chip,
        frame_chip_size=settings.frame.size,
        diet=DietEdit(
            non_veg_days=list(settings.diet.non_veg_days),
            festivals=list(settings.diet.no_non_veg_festivals),
            extra_dates=list(settings.diet.no_non_veg_dates_extra),
            groups=festival_groups(list(settings.diet.no_non_veg_festivals)),
        ),
        points=settings.points,
        kids=[
            KidEdit(id=kid.id, name=kid.name, avatar=kid.avatar, color=kid.color)
            for kid in family.kids
        ]
        if family is not None
        else None,
    )


def _set_list(mapping: CommentedMap, key: str, values: list[Any]) -> None:
    """Change a list's items without replacing the list.

    A new sequence is a new node, and a comment ruamel attached to the old one
    — "# Matched as a case-insensitive substring …" after non_veg_days — goes
    with it, as does its [flow, style]. Emptying and refilling the node the
    file already has keeps both.
    """
    existing = mapping.get(key)
    if isinstance(existing, CommentedSeq):
        del existing[:]
        existing.extend(values)
    else:
        mapping[key] = CommentedSeq(values)


def _map(doc: Any, key: str) -> CommentedMap:
    """The mapping under `key`, made if the file does not have one yet."""
    found = doc.get(key)
    if not isinstance(found, CommentedMap):
        found = CommentedMap()
        doc[key] = found
    return found


def edit_settings(path: Path, edit: ParentSettings, when: datetime, validate: Validate) -> None:
    """Write what the parent screen changed into settings.yaml.

    Key by key, into the document as loaded, so every comment and every key
    the screen does not offer survives. A group the edit leaves out is not
    touched at all.
    """
    doc = load(path)
    night = _map(doc, "night")
    night["start"] = edit.night_start
    night["end"] = edit.night_end
    night["idle_minutes"] = edit.night_idle_minutes
    night["frame"] = edit.night_frame
    doc["idle_minutes"] = edit.idle_minutes
    doc["slide_seconds"] = edit.slide_seconds

    if edit.refresh_minutes is not None:
        doc["refresh_minutes"] = edit.refresh_minutes

    if edit.frame_chip is not None or edit.frame_chip_size is not None:
        frame = _map(doc, "frame")
        if edit.frame_chip is not None:
            frame["chip"] = edit.frame_chip
        if edit.frame_chip_size is not None:
            frame["size"] = edit.frame_chip_size

    if edit.diet is not None:
        diet = _map(doc, "diet")
        # Each list is rewritten only when it changed, and a festival's span
        # in place when only that changed: the file's own comments ("Navratri
        # through Dussehra") live on these entries and must survive a toggle.
        if list(diet.get("non_veg_days") or []) != edit.diet.non_veg_days:
            _set_list(diet, "non_veg_days", edit.diet.non_veg_days)
        festivals = diet.get("no_non_veg_festivals")
        wanted = edit.diet.festivals
        same_rules = isinstance(festivals, list) and [
            str(one.get("match")) for one in festivals
        ] == [rule.match for rule in wanted]
        if same_rules and isinstance(festivals, list):
            for entry, rule in zip(festivals, wanted, strict=True):
                if int(entry.get("span_days", 1)) != rule.span_days:
                    entry["span_days"] = rule.span_days
        else:
            rewritten = CommentedSeq()
            for rule in wanted:
                one = CommentedMap()
                one["match"] = rule.match
                one["span_days"] = rule.span_days
                rewritten.append(one)
            diet["no_non_veg_festivals"] = rewritten
        current = [
            (str(one.get("from")), str(one.get("to")), str(one.get("name")))
            for one in diet.get("no_non_veg_dates_extra") or []
        ]
        spans = [
            (span.start.isoformat(), span.end.isoformat(), span.name)
            for span in edit.diet.extra_dates
        ]
        if current != spans:
            extra = CommentedSeq()
            for start, end, name in spans:
                one = CommentedMap()
                one["from"] = start
                one["to"] = end
                one["name"] = name
                extra.append(one)
            diet["no_non_veg_dates_extra"] = extra

    if edit.points is not None:
        points = _map(doc, "points")
        for key, value in edit.points.model_dump().items():
            if points.get(key) != value:
                points[key] = value

    text = serialize(doc, when)
    validate(text)
    write_atomic(path, text)


def edit_family(path: Path, kids: list[KidEdit], when: datetime, validate: Validate) -> None:
    """A child's name, animal and colour. Nobody is added or removed here:
    a new child is a new id in every content file, which is not a form."""
    doc = load(path)
    listed = doc.get("kids") if doc is not None else None
    if not isinstance(listed, list):
        raise ValueError("family.yaml has no kids")
    wanted = {kid.id: kid for kid in kids}
    for entry in listed:
        edit = wanted.get(str(entry.get("id")))
        if edit is None:
            continue
        entry["name"] = edit.name.strip()
        entry["color"] = edit.color.upper()
        if edit.avatar:
            entry["avatar"] = edit.avatar
        elif "avatar" in entry:
            del entry["avatar"]

    text = serialize(doc, when)
    validate(text)
    write_atomic(path, text)


def meal_choices(slot: MealSlot, names: dict[str, str]) -> list[MealChoice]:
    """Each dish the children chose for a proposed slot, and who chose it,
    in the order they chose."""
    if slot.confirmed:
        return []
    picks = slot.picks or {kid: PickChoice(id=slot.id or "") for kid in slot.picked_by}
    found: dict[str, list[str]] = {}
    for kid_id, pick in picks.items():
        found.setdefault(pick.id, []).append(kid_id)
    return [
        MealChoice(id=dish_id, name=names.get(dish_id, dish_id), kids=kids)
        for dish_id, kids in found.items()
    ]


def _cell(slot: MealSlot | None, names: dict[str, str]) -> MealCell:
    if slot is None:
        return MealCell()
    return MealCell(
        name=slot.name,
        note=slot.note or "",
        id=slot.id or "",
        picked_by=list(slot.picked_by),
        confirmed=slot.confirmed,
        plan_name=names.get(slot.plan, slot.plan) if slot.plan else "",
        contested=slot.contested,
        choices=meal_choices(slot, names),
    )


def meals_view(meals: DayMeals, day: Date, names: dict[str, str] | None = None) -> MealDay:
    names = names or {}
    return MealDay(
        date=day,
        breakfast=_cell(meals.breakfast, names),
        lunch=_cell(meals.lunch, names),
        dinner=_cell(meals.dinner, names),
    )


def meals_window(
    on: Callable[[Date], DayMeals],
    start: Date,
    days: int,
    names: dict[str, str] | None = None,
) -> list[MealDay]:
    window = [start + timedelta(days=offset) for offset in range(days)]
    return [meals_view(on(day), day, names) for day in window]


def _find_key(doc: Any, day: Date) -> Any | None:
    """meals.yaml keys parse as dates, but a hand-written file may hold strings."""
    for key in doc:
        if key == day or (isinstance(key, str) and key == day.isoformat()):
            return key
    return None


def _slot_value(existing: Any, cell: MealCell, dish_names: dict[str, str]) -> Any | None:
    """Keep the catalog id when the name still matches it; otherwise plain text."""
    if not cell.name.strip():
        return None

    note = cell.note.strip()

    # Picked from the list: write the id, and keep how the kids eat it when the
    # dish has not changed.
    if cell.id:
        chosen = CommentedMap()
        chosen["id"] = cell.id
        if isinstance(existing, CommentedMap) and existing.get("id") == cell.id:
            # Same dish: keep how the kids eat it, and keep whose pick it was.
            # A parent straightening the week must not quietly undo a child's
            # choice, which is a thing they were promised a say in.
            for key in ("kids_protein", "picked_by", "confirmed", "plan", "picks"):
                if key in existing:
                    chosen[key] = existing[key]
        if note:
            chosen["note"] = note
        return chosen

    if isinstance(existing, CommentedMap) and "id" in existing:
        dish_id = str(existing["id"])
        if dish_names.get(dish_id, "").strip() == cell.name.strip():
            kept = existing
            if note:
                kept["note"] = note
            else:
                kept.pop("note", None)
            return kept

    written = CommentedMap()
    written["name"] = cell.name.strip()
    if note:
        written["note"] = note
    return written


def edit_meals(
    path: Path,
    edits: list[MealDay],
    dish_names: dict[str, str],
    when: datetime,
    validate: Validate,
) -> None:
    doc = load(path)
    if doc is None:
        doc = CommentedMap()

    for day in edits:
        key = _find_key(doc, day.date)
        if key is None:
            # A date object, not its isoformat: ruamel quotes a string that
            # looks like a date, and the file would end up with two key styles.
            key = day.date
            doc[key] = CommentedMap()
        slots = doc[key]
        if not isinstance(slots, CommentedMap):
            slots = CommentedMap()
            doc[key] = slots

        for name in SLOTS:
            value = _slot_value(slots.get(name), getattr(day, name), dish_names)
            if value is None:
                slots.pop(name, None)
            else:
                slots[name] = value

        # A day with nothing in it is a day with no entry.
        if not slots:
            doc.pop(key, None)

    text = serialize(doc, when)
    validate(text)
    write_atomic(path, text)


def edit_school_events(
    path: Path,
    series: str,
    kids: list[str],
    when: datetime,
    validate: Validate,
) -> None:
    """Set who sees one series, keeping the file's comments and order.

    The rule is matched on its normalised form, so the file can hold "cross
    country" while the parent screen is showing "Cross Country meet @ East
    Avenue" — one decision, however the school spells it next week.
    """
    doc = load(path)
    rules = doc.get("rules")
    if rules is None:
        rules = CommentedSeq()
        doc["rules"] = rules

    # Edit whichever rule already governs this series, not one that merely
    # spells it the same. A broad "cross country" rule covers both the meet
    # and the championship, so a tap on either has to move that rule — adding
    # a narrower one beside it would be shadowed by the first and do nothing.
    wanted = normalise(series)
    for rule in rules:
        existing = normalise(str(rule.get("match", "")))
        if existing and existing in wanted:
            rule["kids"] = CommentedSeq(kids)
            break
    else:
        fresh = CommentedMap()
        fresh["match"] = wanted
        fresh["kids"] = CommentedSeq(kids)
        fresh.fa.set_flow_style()
        rules.append(fresh)

    validate(serialize(doc, when))
    write_atomic(path, serialize(doc, when))


def edit_school_default(path: Path, default: str, when: datetime, validate: Validate) -> None:
    """Flip what happens to a series nobody has decided about."""
    doc = load(path)
    doc["default"] = default
    validate(serialize(doc, when))
    write_atomic(path, serialize(doc, when))


def set_plan_slot(
    path: Path,
    day: Date,
    slot: str,
    dish_id: str,
    when: datetime,
    validate: Validate,
    place: str | None = None,
) -> None:
    """A parent's pen on one meal of the plan. A note already on the slot, and
    how the kids eat it if the dish has not changed, stay.

    Lunch out and Dinner out write their place as the note (or none), and a
    place never outlives the out it belonged to."""
    doc = load(path)
    if doc is None:
        doc = CommentedMap()
    key = _find_key(doc, day)
    if key is None:
        key = day
        doc[key] = CommentedMap()
    slots = doc[key]
    if not isinstance(slots, CommentedMap):
        slots = CommentedMap()
        doc[key] = slots
    existing = slots.get(slot)
    written = CommentedMap()
    written["id"] = dish_id
    if isinstance(existing, CommentedMap):
        if existing.get("id") == dish_id and existing.get("kids_protein"):
            written["kids_protein"] = existing["kids_protein"]
        if existing.get("note") and not is_out(dish_id) and not is_out(existing.get("id")):
            written["note"] = existing["note"]
    if is_out(dish_id) and place:
        written["note"] = place
    slots[slot] = written
    text = serialize(doc, when)
    validate(text)
    write_atomic(path, text)
