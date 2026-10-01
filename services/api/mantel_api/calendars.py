"""Google Calendar ICS feeds, fetched on a timer and cached.

Each feed's secret URL lives in .env under the name given in settings.yaml. A
feed whose variable is empty is skipped and reported as "not configured"; a
feed that fails to fetch keeps serving the events it last had.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import icalendar
import recurring_ical_events

from . import paths
from .models import CalendarEvent, CalendarFeed, CalendarRow, CalendarState, Settings

logger = logging.getLogger("mantel_api.calendars")

TIMEOUT_SECONDS = 10.0

#: How far *back* each kind is expanded. A ten-day festival is named once, on
#: its first day, so a restart on day nine has to be able to see that day or
#: the diet service would decide the fast was over. 31 is the longest span a
#: festival rule may ask for.
WINDOW_BEFORE_DAYS: dict[str, int] = {
    "kid": 1,
    "family": 1,
    "holiday": 31,
    "festival": 31,
    "school": 31,
}

#: How far ahead each kind is worth expanding. A family calendar changes daily
#: and is read a day at a time; a holiday calendar is read six months out to
#: answer "when is Diwali" and to give the diet service something to chew on.
WINDOW_AFTER_DAYS: dict[str, int] = {
    "kid": 14,
    "family": 14,
    "holiday": 183,
    "festival": 183,
    # A school year is longer than six months: read in September, a 183-day
    # window ends in March and cannot see May's last day of school, so the
    # year would have no end and June would never read as Summer.
    "school": 365,
}

#: And how often each is worth re-fetching. Public holidays do not move.
REFRESH_MINUTES: dict[str, int | None] = {
    "kid": None,  # None means "whatever settings.refresh_minutes says"
    "family": None,
    "holiday": 24 * 60,
    "festival": 24 * 60,
    "school": 60,
}

IcsFetch = Callable[[str], Awaitable[str]]


def window_for(kind: str) -> int:
    return WINDOW_AFTER_DAYS.get(kind, 14)


def lookback_for(kind: str) -> int:
    return WINDOW_BEFORE_DAYS.get(kind, 1)


def refresh_minutes_for(kind: str, default_minutes: int) -> int:
    configured = REFRESH_MINUTES.get(kind)
    return default_minutes if configured is None else configured


def local_path(url: str) -> Path | None:
    """A feed on disk rather than on the web: `file:///abs/path.ics`, or a
    plain path, read from the content folder (`calendars/family.ics`). The
    sample family's calendars are files, so the demo needs no network."""
    if url.startswith("file://"):
        return Path(urllib.parse.unquote(urllib.parse.urlparse(url).path))
    if "://" in url:
        return None
    path = Path(url).expanduser()
    return path if path.is_absolute() else paths.content_dir() / path


async def fetch_ics(url: str) -> str:
    on_disk = local_path(url)
    if on_disk is not None:
        return on_disk.read_text(encoding="utf-8")
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def _local(value: datetime, zone: ZoneInfo) -> datetime:
    """A floating time means local time; anything else is converted."""
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


MAX_SPAN_DAYS = 60

#: A school event is marked as such so the dashboard can draw it differently.
SOURCE_OF_KIND = {"school": "school"}


def _events(occurrence: Any, feed: CalendarFeed, zone: ZoneInfo) -> list[CalendarEvent]:
    """One occurrence as one event per day it covers.

    A week of "No School - Winter Break" arrives as a single all-day event with
    an exclusive end date. Every day it spans has to be a day the school
    service can see, so the span is expanded here rather than carried around as
    a range that every reader would have to remember to check.
    """
    title = str(occurrence.get("SUMMARY", "")).strip() or "(untitled)"
    where = str(occurrence.get("LOCATION", "")).strip() or None
    raw_start = occurrence["DTSTART"].dt
    raw_end = occurrence["DTEND"].dt if occurrence.get("DTEND") is not None else None

    # An all-day event is a plain date in ICS, and carries no clock time here.
    if not isinstance(raw_start, datetime):
        last = raw_start
        if isinstance(raw_end, Date) and not isinstance(raw_end, datetime):
            # DTEND is exclusive for an all-day event: 21st to 26th is the 25th.
            last = max(raw_start, raw_end - timedelta(days=1))
        span = min((last - raw_start).days, MAX_SPAN_DAYS)
        return [
            CalendarEvent(
                calendar_id=feed.id,
                kid=feed.owner,
                source=SOURCE_OF_KIND.get(feed.kind, "calendar"),
                date=raw_start + timedelta(days=offset),
                title=title,
                where=where,
                all_day=True,
            )
            for offset in range(span + 1)
        ]

    start = _local(raw_start, zone)
    end = _local(raw_end, zone) if isinstance(raw_end, datetime) else None
    return [
        CalendarEvent(
            calendar_id=feed.id,
            kid=feed.owner,
            source=SOURCE_OF_KIND.get(feed.kind, "calendar"),
            date=start.date(),
            title=title,
            start=start.strftime("%H:%M"),
            end=end.strftime("%H:%M") if end is not None else None,
            where=where,
            all_day=False,
        )
    ]


def expand(
    text: str, feed: CalendarFeed, start: Date, end: Date, zone: ZoneInfo
) -> list[CalendarEvent]:
    """Every occurrence between start and end, recurrences and EXDATEs applied.

    Both ends are inclusive: `between` stops at midnight, so the last day is
    extended to cover events later in that day.
    """
    calendar = icalendar.Calendar.from_ical(text)
    occurrences = recurring_ical_events.of(calendar).between(start, end + timedelta(days=1))
    return [
        event
        for occurrence in occurrences
        for event in _events(occurrence, feed, zone)
        if start <= event.date <= end
    ]


def _age(since: datetime | None, now: datetime) -> str:
    if since is None:
        return "never fetched"
    minutes = int((now - since).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    return f"{hours}h ago" if hours < 48 else f"{hours // 24}d ago"


@dataclass
class FeedState:
    configured: bool = False
    events: list[CalendarEvent] = field(default_factory=list)
    fetched_at: datetime | None = None
    error: str | None = None
    #: How many of this feed's events survive de-duplication against the feeds
    #: listed before it. A festival feed that fetches hundreds and contributes
    #: none is not broken, but it is worth being able to see that it is doing
    #: nothing without reading the code.
    unique: int | None = None

    def status(self, now: datetime | None = None) -> str:
        """What /api/health says about this feed, age included.

        The age is the point: a feed that fetched cleanly three days ago is a
        different problem from one that fetched a minute ago, and neither shows
        up as an error.
        """
        if not self.configured:
            return "not configured"
        if now is None and self.fetched_at is not None:
            now = datetime.now(tz=self.fetched_at.tzinfo)
        age = _age(self.fetched_at, now) if now is not None else "never fetched"
        counted = f", {len(self.events)} events"
        if self.unique is not None:
            counted += f", {self.unique} unique"
        if self.error is None:
            return f"ok ({age}){counted}"
        if self.events:
            return f"stale ({age}){counted}: {self.error}"
        return f"error: {self.error}"


class CalendarService:
    """Holds the last good events per feed. `fetch` is injectable for tests."""

    def __init__(self, fetch: IcsFetch | None = None, env: Mapping[str, str] | None = None) -> None:
        self._fetch = fetch if fetch is not None else fetch_ics
        self._env = env if env is not None else os.environ
        self._feeds: dict[str, FeedState] = {}
        self._announced: set[str] = set()  # unconfigured feeds are logged once

    def events_on(self, day: Date, exclude: frozenset[str] | None = None) -> list[CalendarEvent]:
        """Events on one day, optionally minus some feeds.

        Holiday and festival feeds are excluded by the caller: an observance is
        not an appointment, and belongs in its own array.
        """
        skip = exclude or frozenset()
        return [
            event
            for feed_id, state in self._feeds.items()
            if feed_id not in skip
            for event in state.events
            if event.date == day
        ]

    def status(self, settings: Settings) -> dict[str, str]:
        now = datetime.now(_zone(settings.timezone))
        return {
            feed.id: self._feeds.get(feed.id, FeedState()).status(now)
            for feed in settings.calendars
        }

    def rows(self, settings: Settings) -> list[CalendarRow]:
        """Each feed for the parent screen: its state, when it last answered,
        and for a private feed the variable its URL lives in. Never the URL.

        A feed that has not been asked yet is judged by whether it could be:
        a kid calendar with nothing in .env is not configured, and should say
        where the URL goes rather than look like an error.
        """
        found: list[CalendarRow] = []
        for feed in settings.calendars:
            state = self._feeds.get(feed.id)
            configured = bool(self._url_for(feed)) if state is None else state.configured
            if not configured:
                kind: CalendarState = "not_configured"
            elif state is None or (state.fetched_at is None and state.error is None):
                kind = "never"
            elif state.error is not None:
                kind = "stale" if state.events else "error"
            else:
                kind = "ok"
            detail = ""
            if state is not None and state.error:
                detail = state.error
            elif state is not None and configured:
                detail = f"{len(state.events)} events"
            found.append(
                CalendarRow(
                    id=feed.id,
                    kind=feed.kind,
                    kid=feed.kid,
                    name=feed.name,
                    state=kind,
                    fetched_at=state.fetched_at if state is not None else None,
                    detail=detail,
                    env=feed.url_env,
                )
            )
        return found

    def events_of_kind(self, settings: Settings, *kinds: str) -> list[CalendarEvent]:
        """Every cached event from the feeds of these kinds, in feed order."""
        wanted = {feed.id for feed in settings.calendars if feed.kind in kinds}
        return [
            event
            for feed_id, state in self._feeds.items()
            if feed_id in wanted
            for event in state.events
        ]

    def note_unique(self, counts: Mapping[str, int]) -> None:
        """Record how many observances each feed actually contributed."""
        for feed_id, count in counts.items():
            state = self._feeds.get(feed_id)
            if state is not None:
                state.unique = count

    def kind_of(self, settings: Settings, calendar_id: str) -> str | None:
        for feed in settings.calendars:
            if feed.id == calendar_id:
                return feed.kind
        return None

    def due(self, feed: CalendarFeed, settings: Settings, now: datetime) -> bool:
        """Whether this feed has waited out its own interval.

        Every kind is offered a refresh on the same tick; the ones that do not
        move — public holidays, a school year — decline most of them.
        """
        state = self._feeds.get(feed.id)
        if state is None or state.fetched_at is None or state.error is not None:
            return True
        minutes = refresh_minutes_for(feed.kind, settings.refresh_minutes)
        return now - state.fetched_at >= timedelta(minutes=minutes)

    async def refresh(
        self, settings: Settings, *, today: Date | None = None, force: bool = False
    ) -> None:
        """Re-fetch whichever feeds are due. Never raises into a request.

        `today` anchors the expansion window; it defaults to the real date and
        is passed explicitly by tests.
        """
        zone = _zone(settings.timezone)
        now = datetime.now(zone)
        anchor = today if today is not None else now.date()
        for feed in settings.calendars:
            if not force and not self.due(feed, settings, now):
                continue
            start = anchor - timedelta(days=lookback_for(feed.kind))
            end = anchor + timedelta(days=window_for(feed.kind))
            await self._refresh_feed(feed, start, end, zone)

    def _url_for(self, feed: CalendarFeed) -> str:
        """A public feed carries its URL; a private one names a variable.

        DISCOVER is the placeholder for a school feed nobody has found yet: it
        reads as "not configured" rather than being fetched.
        """
        if feed.url is not None:
            return "" if feed.url.strip().upper() == "DISCOVER" else feed.url.strip()
        return self._env.get(feed.url_env or "", "").strip()

    async def _refresh_feed(
        self, feed: CalendarFeed, start: Date, end: Date, zone: ZoneInfo
    ) -> None:
        state = self._feeds.setdefault(feed.id, FeedState())
        url = self._url_for(feed)
        if not url:
            state.configured = False
            state.events = []
            state.error = None
            if feed.id not in self._announced:
                self._announced.add(feed.id)
                missing = feed.url_env if feed.url_env else "its url"
                logger.info("calendar %r not configured: %s is empty", feed.id, missing)
            return

        state.configured = True
        self._announced.discard(feed.id)
        try:
            text = await self._fetch(url)
            events = expand(text, feed, start, end, zone)
        except Exception as exc:  # noqa: BLE001 - a bad feed must not break a request
            state.error = f"{type(exc).__name__}: {exc}".strip()
            logger.warning(
                "calendar %r failed, keeping %d cached event(s): %s",
                feed.id,
                len(state.events),
                state.error,
            )
            return
        state.events = events
        state.fetched_at = datetime.now(zone)
        state.error = None


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - a bad timezone must not break the fetch
        return ZoneInfo("America/Los_Angeles")
