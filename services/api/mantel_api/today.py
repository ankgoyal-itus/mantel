"""Turning validated content into one day, the way the dashboard reads it."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date as Date
from datetime import timedelta
from typing import Protocol

from .models import (
    FAMILY_ID,
    AgendaEntry,
    CalendarEvent,
    Day,
    DayDiet,
    DayMeals,
    Family,
    Kid,
    KidDay,
    Observance,
    Parent,
    Schedule,
    ScheduleException,
    ScheduleItem,
    Settings,
    TaskEntry,
    TaskItem,
    Tasks,
    Weather,
    Weekday,
)

WEEKDAYS: tuple[Weekday, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
SCHOOL_WEEKDAYS = frozenset({"mon", "tue", "wed", "thu", "fri"})


def weekday_of(day: Date) -> Weekday:
    return WEEKDAYS[day.weekday()]


def _exception_for(schedule: Schedule, day: Date, title: str) -> ScheduleException | None:
    """Exceptions are matched on date and title, so a title covers every kid."""
    for change in schedule.exceptions:
        if change.date == day and change.title == title:
            return change
    return None


def _entry(item: ScheduleItem, start: str, end: str) -> AgendaEntry:
    return AgendaEntry(
        start=start,
        end=end,
        title=item.title,
        where=item.where,
        note=item.note,
        source="schedule",
    )


def scheduled_agenda(schedule: Schedule, day: Date, owner: str) -> list[AgendaEntry]:
    """Recurring items for this weekday and owner, with exceptions applied."""
    token = weekday_of(day)
    entries: list[AgendaEntry] = []
    for item in schedule.items:
        if item.kid != owner or token not in item.days:
            continue
        change = _exception_for(schedule, day, item.title)
        if change is None:
            entries.append(_entry(item, item.start, item.end))
        elif change.action == "move":
            entries.append(_entry(item, change.start or item.start, change.end or item.end))
        # action == "skip": the occurrence simply does not happen.
    return entries


def entry_from_event(
    event: CalendarEvent, source: str = "calendar", kind: str | None = None
) -> AgendaEntry:
    return AgendaEntry(
        start=event.start,
        end=event.end,
        title=event.title,
        where=event.where,
        source=source,
        source_kind=kind,
        all_day=event.all_day,
        calendar_id=event.calendar_id,
    )


def _order(entry: AgendaEntry) -> tuple[int, str, str]:
    """All-day first, then by start time."""
    return (0 if entry.all_day else 1, entry.start or "", entry.title.lower())


def _same(title: str) -> str:
    """A title as two feeds would agree on it: case and spacing aside."""
    return " ".join(title.split()).lower()


def merge_agenda(
    scheduled: list[AgendaEntry],
    day: Date,
    events: Sequence[CalendarEvent] | None = None,
    kinds: Mapping[str, str] | None = None,
) -> list[AgendaEntry]:
    """The one place a day's agenda is assembled.

    The calendar wins: a schedule item with the same title (case-insensitive)
    and the same start is dropped in favour of the calendar's copy, so an
    activity that lives in both places is shown once.

    And a calendar event is shown once however many feeds carry it: a
    district's "Conference Days - Early Release" arrives from the district's
    feed and again from the school's own, on the same day, under the same
    title. The first feed listed in settings.yaml keeps it.
    """
    lookup = kinds or {}
    from_calendar: list[AgendaEntry] = []
    seen: set[tuple[str, str | None]] = set()
    for event in events or ():
        entry = entry_from_event(event, event.source, lookup.get(event.calendar_id))
        key = (_same(entry.title), entry.start)
        if key in seen:
            continue
        seen.add(key)
        from_calendar.append(entry)
    claimed = {(_same(entry.title), entry.start) for entry in from_calendar}
    kept = [item for item in scheduled if (_same(item.title), item.start) not in claimed]
    return sorted(kept + from_calendar, key=_order)


def uses_weekend(day: Date, school_day: bool) -> bool:
    """Whether a day runs on the weekend list: Saturday, Sunday, or any
    weekday with no school — a holiday is a day off, whatever it is called."""
    return day.weekday() >= 5 or not school_day


def tasks_on(tasks: Tasks, kid_id: str, day: Date, school_day: bool) -> list[TaskItem]:
    """The list this day asks of a kid."""
    return tasks.on(kid_id, weekend=uses_weekend(day, school_day))


def week_of(day: Date) -> tuple[Date, Date]:
    """Monday to Sunday: the span a once-a-week task is done once in."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def birthday_today(person: Kid | Parent, day: Date) -> bool:
    """Whether MM-DD from family.yaml is this date.

    No year is stored and none is wanted: the screen says whose birthday it
    is, never how old they are. A 29 February birthday falls on the 28th in
    a common year, which is the convention the people who have one use.
    """
    when = person.birthday
    if not when:
        return False
    if when == "02-29" and day.month == 2 and day.day == 28:
        try:
            Date(day.year, 2, 29)
        except ValueError:
            return True
    return when == f"{day.month:02d}-{day.day:02d}"


def birthdays_on(family: Family, day: Date) -> list[Observance]:
    """Everyone's birthday that day, as observances the calendar can carry.

    They join the festivals rather than living in their own field: a birthday
    is a kind of day, which is exactly what an observance is, and every screen
    that already draws observances then draws these too — the month grid, the
    night screen, the list, tomorrow's card.
    """
    found: list[Observance] = []
    people: list[Kid | Parent] = [*family.kids, *family.parents]
    for person in people:
        if birthday_today(person, day):
            found.append(
                Observance(
                    name=f"{person.name}'s birthday",
                    kind="family",
                    calendar_id="birthdays",
                )
            )
    return found


def tasks_for(
    tasks: Tasks,
    kid_id: str,
    day: Date,
    school_day: bool,
    claimed: Mapping[str, str] | None = None,
    claim_ids: Mapping[str, int] | None = None,
) -> list[TaskEntry]:
    """The day's tasks, each carrying what has already happened to it.

    The status travels with the row so a parent walking past the dashboard
    sees what a child claimed without opening anything. A once-a-week task
    carries its week's status, so homework approved on Tuesday is done on
    Thursday too.
    """
    status = claimed or {}
    waiting = claim_ids or {}
    return [
        TaskEntry(
            id=task.id,
            title=task.title,
            claim=task.claim,
            points=task.points,
            routine=task.routine,
            every=task.every,
            status=status.get(task.id, "none"),  # type: ignore[arg-type]
            claim_id=waiting.get(task.id),
        )
        for task in tasks_on(tasks, kid_id, day, school_day)
    ]


class MealSource(Protocol):
    """The plan, or the plan with the children's picks resolved onto it
    (weekly.Week): anything that can say what a day's meals are."""

    def on(self, day: Date) -> DayMeals: ...


def build_day(
    day: Date,
    family: Family,
    settings: Settings,
    schedule: Schedule,
    meals: MealSource,
    tasks: Tasks,
    events: Sequence[CalendarEvent] | None = None,
    weather: Weather | None = None,
    *,
    school_day: bool = True,
    school_note: str | None = None,
    observances: Sequence[Observance] | None = None,
    diet: DayDiet | None = None,
    kinds: Mapping[str, str] | None = None,
    claimed: Mapping[str, Mapping[str, str]] | None = None,
    claim_ids: Mapping[str, Mapping[str, int]] | None = None,
) -> Day:
    """One day as the dashboard reads it.

    School days and diet days arrive already decided: both are derived from
    live feeds by their own services, and this assembles rather than judges.
    """
    by_owner: dict[str, list[CalendarEvent]] = {}
    for event in events or ():
        by_owner.setdefault(event.kid, []).append(event)
    return Day(
        date=day,
        weekday=weekday_of(day),
        is_school_day=school_day,
        school_note=school_note,
        kids=[
            KidDay(
                id=kid.id,
                name=kid.name,
                color=kid.color,
                avatar=kid.avatar,
                agenda=merge_agenda(
                    scheduled_agenda(schedule, day, kid.id), day, by_owner.get(kid.id), kinds
                ),
                tasks=tasks_for(
                    tasks,
                    kid.id,
                    day,
                    school_day,
                    (claimed or {}).get(kid.id),
                    (claim_ids or {}).get(kid.id),
                ),
                birthday=birthday_today(kid, day),
            )
            for kid in family.kids
        ],
        family_agenda=merge_agenda(
            scheduled_agenda(schedule, day, FAMILY_ID), day, by_owner.get(FAMILY_ID), kinds
        ),
        meals=meals.on(day),
        observances=[*(observances or ()), *birthdays_on(family, day)],
        diet=diet if diet is not None else DayDiet(),
        weather=weather if weather is not None else Weather(),
    )
