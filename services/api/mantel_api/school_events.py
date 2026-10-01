"""Which school events reach a child's agenda.

The school feeds carry everything a school does: two hundred volleyball
fixtures, board meetings, coffee mornings, and the handful of things this
family actually needs to see. Showing all of it buries the four rows that
matter; hiding all of it loses picture day.

So: a few patterns are always shown, because they are about every child at
the school and some of them decide whether there is school at all. Everything
else is a choice a parent makes once per series, in the parent screen, and it
is kept in content/school-events.yaml where it can also be read and edited by
hand.

A series is a normalised title — case folded, grade markers and digits gone,
"@ somewhere" stripped — so the dozen spellings of the volleyball fixture are
one thing to decide about. A rule matches as a substring of that, so one rule
can cover a family of series without them being silently merged.
"""

from __future__ import annotations

import re
from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, Field

from .models import CalendarEvent, ContentModel

#: "@ Bayside Middle", "@ the high school" — where, not what.
AT_PLACE = re.compile(r"\s*@.*$")

#: "6th Grade", "7th/8th Grade", "Grade 6" — who, not what.
GRADES = re.compile(
    r"\b(?:\d+(?:st|nd|rd|th)?(?:\s*/\s*\d+(?:st|nd|rd|th)?)*\s*grades?|grades?\s*\d+[\w/]*)\b",
    re.IGNORECASE,
)

#: Anything else numeric: "Early Release 1:31 PM", "Week 3".
DIGITS = re.compile(r"\d+([:.]\d+)?")

PUNCTUATION = re.compile(r"[^a-z0-9]+")


def normalise(title: str) -> str:
    """A title reduced to the series it belongs to.

    "6th Grade Girls Volleyball @ NMS" and "7th/8th Grade Girls Volleyball @ WMS"
    are the same fixture as far as anyone deciding about it is concerned.
    """
    text = AT_PLACE.sub("", title)
    text = GRADES.sub(" ", text)
    text = DIGITS.sub(" ", text)
    text = PUNCTUATION.sub(" ", text.lower())
    return " ".join(text.split()).strip()


class EventRule(ContentModel):
    """One parent decision: who, if anyone, sees this series."""

    match: str
    kids: list[str] = Field(default_factory=list)


class AlwaysRule(ContentModel):
    """A pattern shown to every child the feed belongs to, whatever the rules
    say. These also decide is_school_day, which is why they cannot be turned
    off from the parent screen."""

    match: str


class SchoolEvents(ContentModel):
    """content/school-events.yaml."""

    always: list[AlwaysRule] = Field(default_factory=list)
    rules: list[EventRule] = Field(default_factory=list)
    #: What happens to a school event matching nothing above.
    default: Literal["hide", "show"] = "hide"

    def always_matches(self, title: str) -> bool:
        series = normalise(title)
        return any(re.search(rule.match, series, re.IGNORECASE) for rule in self.always)

    def rule_for(self, title: str) -> EventRule | None:
        """The first rule matching this title's series, as a substring."""
        series = normalise(title)
        for rule in self.rules:
            if normalise(rule.match) in series:
                return rule
        return None

    def audience(self, event: CalendarEvent, kid_ids: list[str]) -> list[str]:
        """Who sees this event. Empty means nobody, and it stays off the wall.

        An always pattern goes to whoever the feed is for — a district feed is
        for the whole family, so both children. A rule goes to exactly the
        children it names, whichever feed carried it, so a district-wide cross
        country meet can be one child's alone.
        """
        if self.always_matches(event.title):
            return list(kid_ids) if event.kid == FAMILY else [event.kid]
        rule = self.rule_for(event.title)
        if rule is not None:
            return [kid for kid in rule.kids if kid in kid_ids]
        return list(kid_ids) if self.default == "show" and event.kid == FAMILY else (
            [event.kid] if self.default == "show" else []
        )


FAMILY = "family"


class SeriesEvent(BaseModel):
    """One occurrence, as the parent screen lists it."""

    title: str
    date: Date
    start: str | None = None
    end: str | None = None
    where: str | None = None
    calendar_id: str


class Series(BaseModel):
    """A group of occurrences a parent decides about at once."""

    series: str
    #: The title as the school writes it, for the parent screen to show.
    title: str
    count: int
    next_date: Date | None = None
    #: The rule covering it, if a parent has already decided.
    rule: str | None = None
    always: bool = False
    shown_to: list[str] = Field(default_factory=list)
    events: list[SeriesEvent] = Field(default_factory=list)


def group(
    events: list[CalendarEvent], config: SchoolEvents, kid_ids: list[str]
) -> list[Series]:
    """School events as series, newest first within each, for the parent screen."""
    by_series: dict[str, list[CalendarEvent]] = {}
    for event in events:
        by_series.setdefault(normalise(event.title), []).append(event)

    found: list[Series] = []
    for series, occurrences in by_series.items():
        occurrences.sort(key=lambda e: (e.date, e.start or ""))
        first = occurrences[0]
        rule = config.rule_for(first.title)
        found.append(
            Series(
                series=series,
                title=first.title,
                count=len(occurrences),
                next_date=first.date,
                rule=rule.match if rule is not None else None,
                always=config.always_matches(first.title),
                shown_to=config.audience(first, kid_ids),
                events=[
                    SeriesEvent(
                        title=e.title,
                        date=e.date,
                        start=e.start,
                        end=e.end,
                        where=e.where,
                        calendar_id=e.calendar_id,
                    )
                    for e in occurrences
                ],
            )
        )
    found.sort(key=lambda s: (not s.always, s.next_date or Date.max, s.series))
    return found
