"""Holidays and festivals: what a day *is*, rather than what is on that day.

Thanksgiving is not an appointment and does not belong on anyone's agenda, so
these are collected into their own per-day list. Three feeds overlap heavily —
the Indian and Hindu calendars both carry Diwali, Holi and Navratri — so names
are de-duplicated on a normalised form, keeping the first spelling seen.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date as Date
from typing import cast

from .models import CalendarEvent, CalendarKind, Observance

#: Feed kinds that describe a day rather than fill it.
OBSERVANCE_KINDS = frozenset({"holiday", "festival"})

_PUNCTUATION = re.compile(r"[^a-z0-9]+")


def normalise(name: str) -> str:
    """A name reduced to what two feeds would have to agree on.

    "Diwali/Deepavali" and "Diwali / Deepavali" are the same festival; so are
    "Dussehra" and "Dussehra ". Nothing cleverer is attempted: two genuinely
    different names for one day show as two observances, which is honest.
    """
    return _PUNCTUATION.sub(" ", name.strip().lower()).strip()


def by_date(
    events: Iterable[CalendarEvent], kinds: Mapping[str, str]
) -> dict[Date, list[Observance]]:
    """Observances per day, de-duplicated by name across feeds."""
    found, _ = by_date_counted(events, kinds)
    return found


def by_date_counted(
    events: Iterable[CalendarEvent], kinds: Mapping[str, str]
) -> tuple[dict[Date, list[Observance]], dict[str, int]]:
    """As `by_date`, and how many each feed contributed after de-duplication.

    The second half is the diagnostic: a feed can fetch hundreds of events and
    contribute none, because a feed listed before it already carried every one
    of them under the same name. That is not an error, and without a count it
    is indistinguishable from one.
    """
    found: dict[Date, list[Observance]] = defaultdict(list)
    seen: dict[Date, set[str]] = defaultdict(set)
    unique: dict[str, int] = {}
    for event in events:
        kind = kinds.get(event.calendar_id)
        if kind not in OBSERVANCE_KINDS:
            continue
        unique.setdefault(event.calendar_id, 0)
        key = normalise(event.title)
        if not key or key in seen[event.date]:
            continue
        seen[event.date].add(key)
        unique[event.calendar_id] += 1
        found[event.date].append(
            Observance(
                name=event.title.strip(),
                kind=cast(CalendarKind, kind),
                calendar_id=event.calendar_id,
            )
        )
    return dict(found), unique
