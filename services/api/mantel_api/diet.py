"""Which days the house eats vegetarian, worked out from the festival feeds.

The rule the family actually follows is "no meat on the festivals, and only on
certain weekdays otherwise". Festivals move with the moon, so settings.yaml
holds the rules and this holds the dates: it reads the observances the
calendar feeds produced and computes a blocked-date set six months out, cached
to content/.cache/diet-days.json so a feed outage cannot quietly put chicken
on the table during Navratri.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from datetime import date as Date
from datetime import timedelta
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .models import DayDiet, DietDay, Observance, Settings
from .observances import normalise
from .paths import cache_dir
from .today import WEEKDAYS

logger = logging.getLogger("mantel_api.diet")

HORIZON_DAYS = 183

#: Feeds name the opening day of a multi-day festival, not the festival. A
#: child reading "First Day of Sharad Navratri (day 3 of 10)" has to work out
#: that the third day is not the first day.
OPENERS = ("first day of ", "start of ", "beginning of ")


def festival_name(title: str) -> str:
    """The festival, out of the feed's name for its opening day."""
    lowered = title.strip().lower()
    for opener in OPENERS:
        if lowered.startswith(opener):
            return title.strip()[len(opener):].strip()
    return title.strip()


def reason_text(title: str, day: int, span: int) -> str:
    """One reason, as it is read on the wall.

    "Sharad Navratri · day 3 of 10" for something that runs, the name alone
    for something that does not.
    """
    name = festival_name(title)
    return f"{name} · day {day} of {span}" if span > 1 else name


WEEKDAY_NAMES = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}


class DietCache(BaseModel):
    """What was computed last, so startup does not wait for a fetch."""

    days: list[DietDay] = []
    computed_at: Date | None = None


def festival_reasons(
    day: Date, observances: Mapping[Date, Sequence[Observance]], settings: Settings
) -> list[str]:
    """Why this day is meatless, in words a nine-year-old would accept.

    A festival is named once in the feed, on its first day, so each rule
    carries how many days it runs and the reason says which one we are on.
    """
    reasons: list[str] = []
    for rule in settings.diet.no_non_veg_festivals:
        needle = normalise(rule.match)
        if not needle:
            continue
        for offset in range(rule.span_days):
            started = day - timedelta(days=offset)
            for observance in observances.get(started, ()):
                if needle not in normalise(observance.name):
                    continue
                reasons.append(reason_text(observance.name, offset + 1, rule.span_days))
    return reasons


def compute(
    settings: Settings,
    observances: Mapping[Date, Sequence[Observance]],
    start: Date,
    days: int = HORIZON_DAYS,
) -> list[DietDay]:
    """One entry per day from `start`, in order."""
    diet = settings.diet
    allowed_weekdays = set(diet.non_veg_days)
    exceptions = {entry.date for entry in diet.non_veg_ok_dates}

    out: list[DietDay] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        if day in exceptions:
            # A deliberate exception wins over every rule, and needs no reason:
            # somebody decided, and that is the whole reason.
            out.append(DietDay(date=day, non_veg_ok=True, reasons=[]))
            continue

        reasons: list[str] = []
        token = WEEKDAYS[day.weekday()]
        weekday_blocks = token not in allowed_weekdays

        reasons.extend(festival_reasons(day, observances, settings))
        for span in diet.no_non_veg_dates_extra:
            if span.covers(day):
                reasons.append(span.name)

        # The weekday rule only gets said when it is the whole story. On
        # Dussehra nobody needs telling it is also a Tuesday.
        if weekday_blocks and not reasons:
            reasons.append(WEEKDAY_NAMES[token])

        blocked = weekday_blocks or bool(reasons)
        out.append(DietDay(date=day, non_veg_ok=not blocked, reasons=reasons))
    return out


class DietService:
    """The computed diet calendar, cached across restarts."""

    def __init__(self, cache_path: Path | None = None) -> None:
        self.cache_path = cache_path if cache_path is not None else cache_dir() / "diet-days.json"
        self._days: dict[Date, DietDay] = {}
        self._computed_at: Date | None = None
        self._load()

    def _load(self) -> None:
        if not self.cache_path.is_file():
            return
        try:
            cached = DietCache.model_validate_json(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, ValidationError) as exc:
            logger.error("unreadable %s (%s); starting without it", self.cache_path, exc)
            return
        self._days = {entry.date: entry for entry in cached.days}
        self._computed_at = cached.computed_at

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache = DietCache(
            days=sorted(self._days.values(), key=lambda entry: entry.date),
            computed_at=self._computed_at,
        )
        temporary = self.cache_path.with_suffix(".json.tmp")
        temporary.write_text(cache.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, self.cache_path)

    def update(
        self,
        settings: Settings,
        observances: Mapping[Date, Sequence[Observance]],
        today: Date,
        days: int = HORIZON_DAYS,
    ) -> list[DietDay]:
        computed = compute(settings, observances, today, days)
        self._days = {entry.date: entry for entry in computed}
        self._computed_at = today
        try:
            self._save()
        except OSError:
            logger.exception("could not write %s", self.cache_path)
        return computed

    def day(self, day: Date) -> DayDiet:
        """Today's answer. An unknown day is allowed rather than guessed at."""
        entry = self._days.get(day)
        if entry is None:
            return DayDiet()
        return DayDiet(non_veg_ok=entry.non_veg_ok, reasons=list(entry.reasons))

    def window(self, start: Date, days: int) -> list[DietDay]:
        return [
            self._days[start + timedelta(days=offset)]
            for offset in range(days)
            if start + timedelta(days=offset) in self._days
        ]

    def status(self) -> str:
        if not self._days:
            return "not computed"
        blocked = sum(1 for entry in self._days.values() if not entry.non_veg_ok)
        return f"{len(self._days)} days, {blocked} vegetarian"
