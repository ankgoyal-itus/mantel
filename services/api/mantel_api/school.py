"""School days, derived from the district's own calendar.

Nobody types a school holiday into content/. The district publishes an ICS
feed; this reads it and works out which days are school days, which are
minimum days, and where the year starts and ends. The answer is cached to
content/.cache/school-year.json and read back at startup, so a feed that is
down, slow or reorganised changes nothing on the wall.

Matching is deliberately loose — a district writes "No School - Thanksgiving
Break" one year and "Thanksgiving Recess" the next — and deliberately one-way:
a feed can add a day off, never take one away.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable, Sequence
from datetime import date as Date
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from .models import CalendarEvent, SchoolYear
from .paths import cache_dir

logger = logging.getLogger("mantel_api.school")

SCHOOL_WEEKDAYS = frozenset({0, 1, 2, 3, 4})  # Monday..Friday

#: A school year from its last day back to its first: late August to late May
#: is about 290 days. Used only when nothing better is known.
TYPICAL_YEAR_DAYS = 290

NO_SCHOOL = re.compile(
    r"no school|holiday|break|recess|staff development|professional development"
    r"|non-?student|teacher work day",
    re.IGNORECASE,
)
MINIMUM_DAY = re.compile(r"minimum day|early release|early dismissal", re.IGNORECASE)
FIRST_DAY = re.compile(r"first day of (school|classes)", re.IGNORECASE)
LAST_DAY = re.compile(r"last day of (school|classes)", re.IGNORECASE)

#: "Early Release (TK-5)" applies to some children and not others, and the
#: district says which in the title. Carried through rather than guessed at.
GRADE_SCOPE = re.compile(r"\b(TK\s*-\s*\d+|K\s*-\s*\d+|grades?\s+[\w\s-]+?)\b", re.IGNORECASE)

#: Noise to take out of a title before it is shown as a note.
NOISE = re.compile(r"no school|and district office closed|district office closed", re.IGNORECASE)


def note_from(title: str) -> str:
    """"No School - Thanksgiving Break" -> "Thanksgiving Break"."""
    cleaned = NOISE.sub("", title)
    cleaned = cleaned.strip(" -–—:()[]\t")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -–—:()[]")
    return cleaned or "No school"


def minimum_note(title: str) -> str:
    """"Fall Conference Days - Early Release (TK-5)" -> "Minimum day (TK-5)"."""
    scope = GRADE_SCOPE.search(title)
    if scope is None:
        return "Minimum day"
    tidy = re.sub(r"\s*-\s*", "-", scope.group(1).strip())
    return f"Minimum day ({tidy})"


def derive(events: Iterable[CalendarEvent], sources: Sequence[str]) -> SchoolYear:
    """Read a set of school-feed events into a school year.

    Everything is a union: any feed saying a day is off makes it off. A feed
    cannot say a day is on — that is what "only add" means, and it is why a
    school's own calendar can close for a fire drill day the district keeps.
    """
    no_school: dict[Date, str] = {}
    minimum_days: dict[Date, str] = {}
    first_day: Date | None = None
    last_day: Date | None = None

    for event in events:
        title = event.title
        if FIRST_DAY.search(title):
            first_day = event.date if first_day is None else min(first_day, event.date)
        if LAST_DAY.search(title):
            last_day = event.date if last_day is None else max(last_day, event.date)

        # A minimum day is still a school day, so it is checked first and does
        # not fall through into the no-school test on the word "release".
        if MINIMUM_DAY.search(title):
            minimum_days.setdefault(event.date, minimum_note(title))
            continue
        if event.all_day and NO_SCHOOL.search(title):
            no_school.setdefault(event.date, note_from(title))

    return SchoolYear(
        first_day=first_day,
        last_day=last_day,
        no_school=no_school,
        minimum_days=minimum_days,
        derived_at=datetime.now(),
        sources=list(sources),
    )


class SchoolService:
    """The current school year, and the only place school days are decided."""

    def __init__(self, cache_path: Path | None = None) -> None:
        self.cache_path = cache_path if cache_path is not None else cache_dir() / "school-year.json"
        self._year = SchoolYear()
        self._load()

    # -- the cache ---------------------------------------------------------

    def _load(self) -> None:
        if not self.cache_path.is_file():
            return
        try:
            self._year = SchoolYear.model_validate_json(
                self.cache_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError, ValidationError) as exc:
            # A cache we cannot read is a cache we do not have. The feeds will
            # rebuild it within the hour.
            logger.error("unreadable %s (%s); starting without it", self.cache_path, exc)

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(".json.tmp")
        temporary.write_text(self._year.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, self.cache_path)

    # -- deriving ----------------------------------------------------------

    def update(self, events: Sequence[CalendarEvent], sources: Sequence[str]) -> SchoolYear:
        """Re-derive from a fresh set of school events, and remember it.

        Bounds are kept when the new feed has none: a district that has
        published next year's calendar but not yet its first day should not
        turn the whole summer into term time.
        """
        if not events:
            return self._year
        derived = derive(events, sources)
        if derived.first_day is None:
            derived.first_day = self._year.first_day
            derived.first_day_derived = self._year.first_day_derived
        if derived.last_day is None:
            derived.last_day = self._year.last_day

        # A year with an end and no beginning makes every day before today
        # "Summer", so a first day is worked out rather than left empty. The
        # moment next year's feed carries a real one, it replaces this.
        if derived.first_day is None and derived.last_day is not None:
            derived.first_day = derived.last_day - timedelta(days=TYPICAL_YEAR_DAYS)
            derived.first_day_derived = True

        self._year = derived
        try:
            self._save()
        except OSError:
            logger.exception("could not write %s", self.cache_path)
        return derived

    # -- reading -----------------------------------------------------------

    @property
    def year(self) -> SchoolYear:
        return self._year

    def out_of_term(self, day: Date) -> bool:
        """Before the first day or after the last, where those are known."""
        year = self._year
        if year.last_day is not None and day > year.last_day:
            return True
        return year.first_day is not None and day < year.first_day

    def day(self, day: Date) -> tuple[bool, str | None]:
        """(is_school_day, note) for one date. The only answer on the subject."""
        year = self._year
        if self.out_of_term(day):
            return False, "Summer"
        if day.weekday() not in SCHOOL_WEEKDAYS:
            return False, None
        closed = year.no_school.get(day)
        if closed is not None:
            return False, closed
        return True, year.minimum_days.get(day)

    def status(self) -> str:
        year = self._year
        if not year.bounds_known:
            return "bounds unknown"
        first = year.first_day.isoformat() if year.first_day else "?"
        if year.first_day is not None and year.first_day_derived:
            first += " (derived)"
        last = year.last_day.isoformat() if year.last_day else "?"
        return f"{first}..{last}, {len(year.no_school)} days off"
