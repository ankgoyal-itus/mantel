"""FastAPI application."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date as Date
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

import yaml
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from . import (
    approvals,
    backup,
    banks,
    cash,
    claims,
    corrections,
    digest,
    feelings,
    ledger,
    out,
    picks,
    pins,
    redemptions,
    saving,
    system,
    weekly,
)
from .calendars import CalendarService
from .content import Content, watch
from .db import Database
from .diet import HORIZON_DAYS, DietService
from .editors import (
    edit_family,
    edit_meals,
    edit_school_default,
    edit_school_events,
    edit_settings,
    meals_view,
    meals_window,
    set_plan_slot,
    settings_view,
)
from .kiosk import mount_kiosk
from .models import (
    FAMILY_ID,
    About,
    Allowance,
    ApprovalItem,
    AwardRequest,
    BankAdjust,
    Banks,
    CalendarEvent,
    CalendarRow,
    CashoutRequest,
    Claim,
    ClaimRequest,
    Config,
    CorrectionRequest,
    Day,
    DayPicks,
    DecisionResult,
    DietDay,
    Digest,
    Dish,
    DishSlot,
    Family,
    Feeling,
    Health,
    JarRequest,
    KidBank,
    KidPin,
    LedgerRow,
    MealDay,
    MealOverride,
    Meals,
    MealsCatalog,
    MealsEdit,
    MonthDay,
    Observance,
    PanchangLimb,
    PanchangMasa,
    PanchangMonth,
    PanchangSamvat,
    PanchangSchool,
    PanchangTithi,
    ParentBanks,
    ParentSettings,
    Payout,
    PendingCount,
    Photo,
    PickDecision,
    PickOption,
    PickRequest,
    PickRow,
    PinAttempt,
    PinResult,
    PinState,
    Points,
    PointsSummary,
    Redemption,
    RedemptionRequest,
    Reward,
    Rewards,
    RobloxUseRequest,
    Schedule,
    SeriesEdit,
    Settings,
    SlotView,
    Tasks,
    Todo,
    TodoDone,
    VersionInfo,
    Weather,
)
from .models import (
    PanchangDay as PanchangDayModel,
)
from .observances import OBSERVANCE_KINDS, by_date, by_date_counted
from .panchang import PanchangService, Place
from .parent import (
    COOKIE_NAME,
    SESSION_SECONDS,
    BadPin,
    LockedOut,
    NotConfigured,
    ParentAuth,
)
from .paths import read_version
from .photos import MAX_BYTES, PhotoError, PhotoStore
from .school import SchoolService
from .school_events import SchoolEvents, Series, group
from .streaks import current_streak
from .today import build_day, weekday_of
from .version import StateVersion
from .weather import CACHE_MINUTES, WeatherService, fetch_demo

logger = logging.getLogger("mantel_api.app")

FALLBACK_TIMEZONE = "America/Los_Angeles"
MAX_AGENDA_DAYS = 14

MAX_MEALS_DAYS = 14

#: A hashed filename never changes what it points at, so it is cached for good.
PHOTO_CACHE = "public, max-age=31536000, immutable"
UPLOAD_CHUNK = 1 << 20


def check_upload_token(supplied: str | None) -> None:
    """X-Mantel-Token against MANTEL_UPLOAD_TOKEN, read per request so a restart
    is the only thing a changed .env needs.

    An unset token disables writing altogether rather than matching the empty
    string, which would leave the upload endpoint open to the whole LAN.
    """
    expected = os.environ.get("MANTEL_UPLOAD_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="uploads are not configured")
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="bad upload token")


async def read_capped(upload: UploadFile) -> bytes:
    """Read one upload, refusing anything over MAX_BYTES before it is stored."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(UPLOAD_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_BYTES:
            megabytes = MAX_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=413, detail=f"{upload.filename} is larger than {megabytes} MB"
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - a bad timezone must not break an endpoint
        return ZoneInfo(FALLBACK_TIMEZONE)


def _now(timezone_name: str) -> str:
    return datetime.now(_zone(timezone_name)).isoformat()


def _today(timezone_name: str) -> Date:
    return datetime.now(_zone(timezone_name)).date()


async def run_periodically(
    action: Callable[[], Awaitable[None]],
    interval_seconds: Callable[[], float],
    stop: asyncio.Event,
) -> None:
    """Run `action` now and then every interval, until the app shuts down."""
    while not stop.is_set():
        try:
            await action()
        except Exception:  # noqa: BLE001 - a refresh must never kill the loop
            logger.exception("background refresh failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds())
        except TimeoutError:
            continue


#: The methods that write.
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Writes no screen shows: they do not move the version.
UNSEEN_WRITES = frozenset({"parent_open", "parent_close", "verify_kid_pin", "parent_reload"})

#: /api/events: how often it looks, how often it says it is alive, and how
#: long one stream lives before the browser is left to reconnect.
EVENTS_TICK_S = 0.25
EVENTS_HEARTBEAT_S = 25.0
EVENTS_LIFETIME_S = 300.0


def create_app(
    content: Content | None = None,
    weather: WeatherService | None = None,
    calendars: CalendarService | None = None,
    photos: PhotoStore | None = None,
    school: SchoolService | None = None,
    diet: DietService | None = None,
    database: Database | None = None,
) -> FastAPI:
    store = content if content is not None else Content()
    store.load_all()
    # The demo (MANTEL_DEMO=1) has a forecast of its own and asks nobody.
    demo = os.environ.get("MANTEL_DEMO") == "1"
    forecast = (
        weather
        if weather is not None
        else WeatherService(fetch=fetch_demo if demo else None)
    )
    feeds = calendars if calendars is not None else CalendarService()
    album = photos if photos is not None else PhotoStore()
    term = school if school is not None else SchoolService()
    table = diet if diet is not None else DietService()
    books = database if database is not None else Database()

    def almanac() -> PanchangService:
        """The panchang service for the current settings.

        Rebuilt when the place or the naming scheme changes, which is what
        makes a cached month invalid; holding it here keeps the memory cache
        alive for as long as those stay put.
        """
        settings = store.settings.current
        place = Place(
            lat=settings.location.lat if settings else 37.4636,
            lon=settings.location.lon if settings else -122.4286,
            timezone=settings.timezone if settings else FALLBACK_TIMEZONE,
        )
        scheme = settings.panchang.masa_scheme if settings else "purnimanta"
        held = getattr(app.state, "panchang", None)
        if held is None or held.place != place or held.scheme != scheme:
            held = PanchangService(place, scheme)
            app.state.panchang = held
        return held

    async def refresh_weather() -> None:
        settings = store.settings.current
        if settings is not None:
            await forecast.refresh(settings)

    async def refresh_calendars() -> None:
        """Fetch whatever is due, then re-derive everything that reads a feed.

        Both derivations are cheap and idempotent, and both write a cache, so
        running them after every refresh keeps the two in step with the feeds
        that fed them.
        """
        settings = store.settings.current
        if settings is None:
            return
        await feeds.refresh(settings)

        school_events = feeds.events_of_kind(settings, "school")
        sources = [feed.id for feed in settings.calendars if feed.kind == "school"]
        term.update(school_events, sources)

        kinds = {feed.id: feed.kind for feed in settings.calendars}
        observed, unique = by_date_counted(
            feeds.events_of_kind(settings, *OBSERVANCE_KINDS), kinds
        )
        feeds.note_unique(unique)
        for feed_id, count in sorted(unique.items()):
            fetched = len(
                [e for e in feeds.events_of_kind(settings, *OBSERVANCE_KINDS)
                 if e.calendar_id == feed_id]
            )
            logger.info("observances %s: %d fetched, %d unique", feed_id, fetched, count)
        table.update(settings, observed, _today(settings.timezone))

    async def take_backup() -> None:
        """Make sure today's copy of the ledger exists.

        Checked hourly rather than scheduled for a time, because the Mac is
        asleep at some hours and a backup that only happens when the house is
        awake at 3am is not a backup.
        """
        settings = store.settings.current
        zone = settings.timezone if settings is not None else FALLBACK_TIMEZONE
        await run_in_threadpool(backup.run, books, _today(zone))

    def calendar_interval() -> float:
        settings = store.settings.current
        return 60.0 * (settings.refresh_minutes if settings is not None else 5)

    def prepare_picks() -> None:
        """Once, as the API starts. Picks written into meals.yaml before the
        picks table existed move into it, and a meal reward still held since
        picks became free gives its points back. Both are idempotent, and
        neither may stop the API starting."""
        settings = store.settings.current
        now = datetime.now(_zone(settings.timezone if settings else FALLBACK_TIMEZONE))
        try:
            with books.write() as connection:
                weekly.migrate_from_yaml(
                    store.directory / "meals.yaml", connection, now=now, validate=meals_validator
                )
                shop_now = store.rewards.current
                if shop_now is not None:
                    redemptions.retire_meal_rewards(connection, shop_now, now=now)
                # Cash rewards approved before the bank and never paid.
                banks.move_owed_cash(connection, now=now)
            store.load_all()
        except Exception:  # noqa: BLE001 - never block start-up on this
            logger.exception("could not prepare the picks table")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        stop = asyncio.Event()
        await run_in_threadpool(prepare_picks)
        # Both sources refresh in the background; requests only read the cache.
        tasks = [
            asyncio.create_task(watch(store, stop)),
            asyncio.create_task(
                run_periodically(refresh_weather, lambda: 60.0 * CACHE_MINUTES, stop)
            ),
            asyncio.create_task(run_periodically(refresh_calendars, calendar_interval, stop)),
            asyncio.create_task(run_periodically(take_backup, lambda: 60.0 * 60.0, stop)),
        ]
        try:
            yield
        finally:
            stop.set()
            for task in tasks:
                await task

    app = FastAPI(title="Mantel API", version=read_version(), lifespan=lifespan)
    app.state.content = store
    app.state.weather = forecast
    app.state.calendars = feeds
    app.state.photos = album
    app.state.school = term
    app.state.diet = table
    app.state.db = books
    versions = StateVersion(books)
    app.state.versions = versions

    @app.middleware("http")
    async def bump_on_write(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Every write that changes a screen moves the version, once.

        Done here rather than at each write site so that no write can forget:
        a successful POST, PUT or DELETE under /api/ bumps it exactly once,
        however many rows it touched. The few writes no screen shows —
        signing in and out, checking a kid's PIN, and the reload, which is
        its own event — are listed and skip it.
        """
        response = await call_next(request)
        endpoint = request.scope.get("endpoint")
        if (
            request.method in WRITE_METHODS
            and request.url.path.startswith("/api/")
            and 200 <= response.status_code < 300
            and getattr(endpoint, "__name__", "") not in UNSEEN_WRITES
        ):
            await run_in_threadpool(versions.bump, local_now())
        return response

    @app.get("/api/version", response_model=VersionInfo)
    def state_version() -> VersionInfo:
        """The number the screens watch. From memory: no database read."""
        return versions.current()

    @app.get("/api/events")
    async def events(request: Request) -> StreamingResponse:
        """Server-sent events: `version` whenever it moves, `reload` when a
        parent asks both iPads to reload, and a comment every 25 seconds so
        nothing between here and the iPad decides the line is dead.

        A stream ends after a few minutes and the browser reconnects on its
        own, so a stopping server is never held open by a sleeping iPad.
        """

        async def stream() -> AsyncIterator[str]:
            seen = versions.current()
            reload_seen = getattr(app.state, "reload_at", None)
            yield "retry: 2000\n"
            yield f"event: version\ndata: {seen.model_dump_json()}\n\n"
            started = time.monotonic()
            beat = started
            while time.monotonic() - started < EVENTS_LIFETIME_S:
                if await request.is_disconnected():
                    return
                now = versions.current()
                if now.version != seen.version:
                    seen = now
                    yield f"event: version\ndata: {now.model_dump_json()}\n\n"
                reload_at = getattr(app.state, "reload_at", None)
                if reload_at != reload_seen:
                    reload_seen = reload_at
                    yield f"event: reload\ndata: {reload_at}\n\n"
                if time.monotonic() - beat >= EVENTS_HEARTBEAT_S:
                    beat = time.monotonic()
                    yield ": heartbeat\n\n"
                await asyncio.sleep(EVENTS_TICK_S)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def agenda_feeds(settings: Settings) -> frozenset[str]:
        """Feeds whose events never become agenda rows.

        Holidays and festivals are observances, not appointments. School feeds
        do reach agendas now, but only through the rules in
        content/school-events.yaml — see school_events_for().
        """
        return frozenset(
            feed.id for feed in settings.calendars if feed.kind in OBSERVANCE_KINDS
        )

    def school_config() -> SchoolEvents:
        return store.school_events.current or SchoolEvents()

    def school_events_for(date: Date, family: Family, school_day: bool) -> list[CalendarEvent]:
        """School events for one day, routed to whoever is meant to see them.

        One occurrence can become two rows — a district event both children
        are shown — or none, which is the default for anything nobody has
        decided about.
        """
        config = school_config()
        kid_ids = [kid.id for kid in family.kids]
        routed: list[CalendarEvent] = []
        for event in feeds.events_on(date):
            if event.source != "school":
                continue
            # A closure is said once, through is_school_day; it is not a row.
            if event.all_day and not school_day:
                continue
            for kid_id in config.audience(event, kid_ids):
                routed.append(event.model_copy(update={"kid": kid_id}))
        return routed

    def day_for(date: Date, settings: Settings, *rest: Any) -> Day:
        family, schedule, meals, tasks = rest
        school_day, note = term.day(date)
        # Once-a-week tasks answer for their whole week, not just this date.
        weekly = {
            kid.id: {task.id for task in tasks.of(kid.id) if task.every == "week"}
            for kid in family.kids
        }
        with books.connect() as connection:
            claimed = {
                kid.id: claims.status_on(connection, kid.id, date, weekly[kid.id])
                for kid in family.kids
            }
            # The id of whatever is still waiting, so a parent can decide the
            # row on the dashboard rather than going to look for it again.
            claim_ids = {
                kid.id: claims.ids_on(connection, kid.id, date, weekly[kid.id])
                for kid in family.kids
            }
        events = [
            event
            for event in feeds.events_on(date, exclude=agenda_feeds(settings))
            if event.source != "school"
        ]
        events += school_events_for(date, family, school_day)
        return build_day(
            date,
            family,
            settings,
            schedule,
            picks_week(date, date),
            tasks,
            events=events,
            weather=forecast.current,
            school_day=school_day,
            school_note=note,
            observances=observances_on(date, settings),
            diet=table.day(date),
            kinds={feed.id: feed.kind for feed in settings.calendars},
            claimed=claimed,
            claim_ids=claim_ids,
        )

    def observances_on(date: Date, settings: Settings) -> list[Observance]:
        kinds = {feed.id: feed.kind for feed in settings.calendars}
        return by_date(feeds.events_on(date), kinds).get(date, [])

    def snapshot() -> tuple[Family, Settings, Schedule, Meals, Tasks]:
        """The current good version of everything a day is built from."""
        family = store.family.current
        settings = store.settings.current
        if family is None or settings is None:
            raise HTTPException(status_code=503, detail="content unavailable")
        return (
            family,
            settings,
            store.schedule.current or Schedule(),
            store.meals.current or Meals(),
            store.tasks.current or Tasks(),
        )

    def ledger_status() -> str:
        """Schema version and row count, or why neither could be read."""
        try:
            with books.connect() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                rows = connection.execute("SELECT COUNT(*) AS n FROM ledger").fetchone()["n"]
        except Exception as exc:  # noqa: BLE001 - health never raises
            return f"error: {type(exc).__name__}: {exc}"
        return f"ok (schema {version}, {rows} rows)"

    @app.get("/api/health", response_model=Health)
    def health() -> Health:
        settings = store.settings.current
        return Health(
            status="ok",
            version=read_version(),
            time=_now(settings.timezone if settings else FALLBACK_TIMEZONE),
            content=store.status,
            weather=forecast.status,
            calendars=feeds.status(settings) if settings is not None else {},
            school_year=term.status(),
            diet_days=table.status(),
            ledger=ledger_status(),
            reload_at=getattr(app.state, "reload_at", None),
        )

    @app.get("/api/config", response_model=Config)
    def config() -> Config:
        family, settings, *_ = snapshot()
        return Config(family=family, settings=settings)

    @app.get("/api/meals/catalog", response_model=list[Dish])
    def meals_catalog(slot: Annotated[DishSlot | None, Query()] = None) -> list[Dish]:
        catalog = store.catalog.current
        if catalog is None:
            raise HTTPException(status_code=503, detail="meals catalog unavailable")
        return catalog.for_slot(slot)

    @app.get("/api/weather", response_model=Weather)
    def weather_now() -> Weather:
        return forecast.current

    @app.get("/api/today", response_model=Day)
    def today(date: Annotated[Date | None, Query()] = None) -> Day:
        family, settings, schedule, meals, tasks = snapshot()
        day = date if date is not None else _today(settings.timezone)
        return day_for(day, settings, family, schedule, meals, tasks)

    @app.get("/api/agenda", response_model=list[Day])
    def agenda(
        start: Annotated[Date | None, Query(alias="from")] = None,
        days: Annotated[int, Query(ge=1)] = 7,
    ) -> list[Day]:
        family, settings, schedule, meals, tasks = snapshot()
        first = start if start is not None else _today(settings.timezone)
        span = min(days, MAX_AGENDA_DAYS)  # a long range is clamped, never refused
        return [
            day_for(first + timedelta(days=offset), settings, family, schedule, meals, tasks)
            for offset in range(span)
        ]

    @app.get("/api/observances", response_model=dict[str, list[Observance]])
    def observances(
        start: Annotated[Date | None, Query(alias="from")] = None,
        days: Annotated[int, Query(ge=1, le=HORIZON_DAYS)] = HORIZON_DAYS,
    ) -> dict[str, list[Observance]]:
        """Holidays and festivals by date, six months out. Days with none are
        left out rather than sent as empty lists."""
        settings = store.settings.current
        if settings is None:
            raise HTTPException(status_code=503, detail="content unavailable")
        first = start if start is not None else _today(settings.timezone)
        kinds = {feed.id: feed.kind for feed in settings.calendars}
        found = by_date(feeds.events_of_kind(settings, *OBSERVANCE_KINDS), kinds)
        return {
            day.isoformat(): found[day]
            for offset in range(days)
            if (day := first + timedelta(days=offset)) in found
        }

    @app.get("/api/diet", response_model=list[DietDay])
    def diet_days(
        start: Annotated[Date | None, Query(alias="from")] = None,
        days: Annotated[int, Query(ge=1, le=HORIZON_DAYS)] = HORIZON_DAYS,
    ) -> list[DietDay]:
        settings = store.settings.current
        if settings is None:
            raise HTTPException(status_code=503, detail="content unavailable")
        first = start if start is not None else _today(settings.timezone)
        return table.window(first, days)

    @app.get("/api/photos", response_model=list[Photo])
    def photo_list() -> list[Photo]:
        """Newest first. Anything that failed to process is simply not here."""
        found: list[Photo] = []
        for photo in album.photos():
            path = album.file_for(photo.id)
            size = path.stat().st_size if path is not None else 0
            found.append(photo.model_copy(update={"bytes": size}))
        return found

    @app.get("/api/photos/{photo_id}.jpg", include_in_schema=False)
    def photo_file(photo_id: str) -> FileResponse:
        path = album.file_for(photo_id)
        if path is None:
            raise HTTPException(status_code=404, detail="no such photo")
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": PHOTO_CACHE})

    @app.post("/api/photos")
    async def photo_upload(
        file: Annotated[list[UploadFile], File()],
        x_mantel_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, list[str]]:
        """One or many files from the Shortcut. A repeat is skipped, not an error."""
        check_upload_token(x_mantel_token)
        added: list[str] = []
        skipped: list[str] = []
        for upload in file:
            data = await read_capped(upload)
            try:
                # Pillow is slow enough to matter: 50 photos would otherwise
                # hold the event loop, and with it every kiosk poll.
                photo_id, was_added = await run_in_threadpool(
                    album.add, data, upload.filename or "upload.jpg"
                )
            except PhotoError as exc:
                # Already in failed/ and logged. The rest of the batch goes on.
                logger.error("upload %s rejected: %s", upload.filename, exc)
                continue
            (added if was_added else skipped).append(photo_id)
        return {"added": added, "skipped": skipped}

    @app.delete("/api/photos/{photo_id}")
    def photo_delete(
        photo_id: str,
        request: Request,
        x_mantel_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, str]:
        # A signed-in parent may delete from the iPad; everyone else needs the
        # upload token, which the kiosk deliberately does not have.
        if not auth.valid(request.cookies.get(COOKIE_NAME), time.time()):
            check_upload_token(x_mantel_token)
        if not album.delete(photo_id):
            raise HTTPException(status_code=404, detail="no such photo")
        return {"deleted": photo_id}

    # ---- parent mode -------------------------------------------------------

    auth = ParentAuth()

    def client_key(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def require_parent(request: Request, response: Response) -> None:
        token = request.cookies.get(COOKIE_NAME)
        now = time.time()
        if not auth.valid(token, now):
            raise HTTPException(status_code=401, detail="parent session required")
        # Working in the last minute buys another ten, and the cookie has to
        # be told so too or the browser drops it on the old schedule.
        if auth.extend(token, now) and token is not None:
            response.set_cookie(
                COOKIE_NAME,
                token,
                max_age=SESSION_SECONDS,
                httponly=True,
                samesite="strict",
                path="/",
            )

    def local_now() -> datetime:
        settings = store.settings.current
        return datetime.now(_zone(settings.timezone if settings else FALLBACK_TIMEZONE))

    def roster() -> dict[str, Any]:
        family = store.family.current
        kids = {kid.id for kid in family.kids} if family else set()
        parents = {parent.id for parent in family.parents} if family else set()
        return {"kid_ids": kids, "person_ids": kids | parents}

    @app.post("/api/parent/session")
    def parent_open(attempt: PinAttempt, request: Request, response: Response) -> dict[str, int]:
        try:
            token = auth.open_session(attempt.pin, client_key(request), time.time())
        except NotConfigured:
            raise HTTPException(
                status_code=503, detail="MANTEL_PARENT_PIN is not set"
            ) from None
        except LockedOut as locked:
            raise HTTPException(
                status_code=429,
                detail={"error": "too many attempts", "retry_after": locked.retry_after},
                headers={"Retry-After": str(locked.retry_after)},
            ) from None
        except BadPin as bad:
            raise HTTPException(
                status_code=401, detail={"error": "wrong pin", "remaining": bad.remaining}
            ) from None

        # No Secure flag: the kiosk is plain http on the LAN, and a cookie the
        # browser refuses to send is worse than one it only sends to us.
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=SESSION_SECONDS,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return {"expires_in": SESSION_SECONDS}

    @app.put("/api/kids/{kid_id}/saving/{reward_id}", response_model=PointsSummary)
    def mark_saving(kid_id: str, reward_id: str) -> PointsSummary:
        """Star a reward, or unstar it. A third pick pushes the oldest off.

        Not behind the parent PIN: what to save towards is the one decision in
        this system that is entirely the child's, and asking a parent to
        approve a wish would be the whole point missed.
        """
        _family, _settings, _schedule, _meals, tasks = snapshot()
        if kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {kid_id!r}")
        if shop().by_id(reward_id) is None:
            raise HTTPException(status_code=404, detail=f"unknown reward {reward_id!r}")
        with books.write() as connection:
            saving.toggle(connection, kid_id, reward_id)
        return summary_for(kid_id, tasks, now_here())

    @app.post("/api/feelings", response_model=Feeling)
    def record_feeling(entry: Feeling) -> Feeling:
        """How a day was, in one tap, at bedtime.

        Refused outright when the setting is off rather than accepted and
        ignored: a screen that is not asking should not be storing.
        """
        _family, settings, *_ = snapshot()
        if not settings.feelings.enabled:
            raise HTTPException(status_code=409, detail="the bedtime check-in is off")
        if entry.kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {entry.kid_id!r}")
        with books.write() as connection:
            feelings.record(
                connection, kid_id=entry.kid_id, day=entry.date, feeling=entry.feeling
            )
        return entry

    @app.get("/api/feelings", response_model=dict[str, str])
    def feelings_on(date: Date | None = None) -> dict[str, str]:
        """kid_id → face, so a night row shows what was already tapped."""
        _family, settings, *_ = snapshot()
        if not settings.feelings.enabled:
            return {}
        day = date or now_here().date()
        with books.connect() as connection:
            found: dict[str, str] = {}
            for kid_id in kid_ids():
                said = feelings.on(connection, kid_id=kid_id, day=day)
                if said is not None:
                    found[kid_id] = said
            return found

    @app.get("/api/parent/session")
    def parent_session(request: Request) -> dict[str, object]:
        """Whether the cookie in hand is still good.

        The dashboard asks before offering Approve and Decline on a row: a
        parent who signed in two minutes ago should not be made to type the
        PIN again, and one who did not should not be shown buttons that will
        fail. Unauthenticated on purpose — the answer is a boolean about a
        cookie the asker already holds, and it says nothing about anything.
        """
        left = auth.remaining(request.cookies.get(COOKIE_NAME), time.time())
        return {"open": left > 0, "expires_in": left}

    @app.get(
        "/api/parent/ledger",
        response_model=list[LedgerRow],
        dependencies=[Depends(require_parent)],
    )
    def parent_ledger(
        kid_id: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> list[LedgerRow]:
        """Every point that moved, newest first.

        The balance says where a child is; this says how they got there, which
        is the question a parent actually asks — usually "when did that get
        approved" or "where did thirty points go". Parent-gated: it is a
        child's whole history in one list.
        """
        family, *_ = snapshot()
        wanted = [kid.id for kid in family.kids] if kid_id is None else [kid_id]

        rows: list[LedgerRow] = []
        with books.connect() as connection:
            for one in wanted:
                rows.extend(ledger.entries(connection, one))
            fixed = corrections.corrected_ids(connection)
        rows.sort(key=lambda row: (row.created_at, row.id), reverse=True)
        return [row.model_copy(update={"can": corrections.can(row, fixed)}) for row in rows[:limit]]

    @app.post(
        "/api/parent/ledger/{row_id}/correct",
        response_model=list[LedgerRow],
        dependencies=[Depends(require_parent)],
    )
    def correct_row(row_id: int, request: CorrectionRequest) -> list[LedgerRow]:
        """Put a wrong row right: undo it, or move it to the other child.

        New rows, never an edit (corrections.py). Undoing a chore reopens it.
        """
        family, *_ = snapshot()
        names = {kid.id: kid.name for kid in family.kids}
        try:
            with books.write() as connection:
                ids = corrections.correct(
                    connection,
                    row_id=row_id,
                    action=request.action,
                    to_kid=request.to_kid,
                    names=names,
                    now=now_here(),
                )
                written = [
                    LedgerRow.from_row(dict(found))
                    for one in ids
                    if (found := connection.execute(
                        "SELECT * FROM ledger WHERE id = ?", (one,)
                    ).fetchone()) is not None
                ]
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        return written

    @app.delete("/api/parent/session")
    def parent_close(request: Request, response: Response) -> dict[str, str]:
        auth.close_session(request.cookies.get(COOKIE_NAME))
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"closed": "ok"}

    @app.get(
        "/api/parent/settings",
        response_model=ParentSettings,
        dependencies=[Depends(require_parent)],
    )
    def parent_settings() -> ParentSettings:
        family, settings, *_ = snapshot()
        return settings_view(settings, family)

    @app.put(
        "/api/parent/settings",
        response_model=ParentSettings,
        dependencies=[Depends(require_parent)],
    )
    def parent_settings_save(edit: ParentSettings) -> ParentSettings:

        def validate(text: str) -> None:
            try:
                Settings.model_validate(yaml.safe_load(text), context=roster())
            except ValidationError as exc:
                raise HTTPException(
                    status_code=422, detail=f"settings.yaml would be invalid: {exc}"
                ) from exc

        def validate_family(text: str) -> None:
            try:
                Family.model_validate(yaml.safe_load(text))
            except ValidationError as exc:
                raise HTTPException(
                    status_code=422, detail=f"family.yaml would be invalid: {exc}"
                ) from exc

        # The family first: it is the smaller file and the likelier to be
        # refused, and a refusal there must not leave settings half-written.
        if edit.kids is not None:
            edit_family(store.directory / "family.yaml", edit.kids, local_now(), validate_family)
        edit_settings(store.directory / "settings.yaml", edit, local_now(), validate)
        store.load_all()
        family, settings, *_ = snapshot()
        return settings_view(settings, family)

    @app.get(
        "/api/parent/school-events",
        response_model=list[Series],
        dependencies=[Depends(require_parent)],
    )
    def parent_school_events(days: Annotated[int, Query(ge=1, le=180)] = 60) -> list[Series]:
        return school_events(days)

    @app.put(
        "/api/parent/school-events",
        response_model=list[Series],
        dependencies=[Depends(require_parent)],
    )
    def parent_school_events_save(edit: SeriesEdit) -> list[Series]:
        def validate(text: str) -> None:
            try:
                SchoolEvents.model_validate(yaml.safe_load(text))
            except ValidationError as exc:
                raise HTTPException(
                    status_code=422, detail=f"school-events.yaml would be invalid: {exc}"
                ) from exc

        path = store.directory / "school-events.yaml"
        if edit.default is not None:
            edit_school_default(path, edit.default, local_now(), validate)
        if edit.series is not None:
            edit_school_events(path, edit.series, edit.kids, local_now(), validate)
        store.load_all()
        return school_events(60)

    @app.post("/api/parent/refresh", dependencies=[Depends(require_parent)])
    async def parent_refresh() -> dict[str, str]:
        settings = store.settings.current
        if settings is None:
            raise HTTPException(status_code=503, detail="content unavailable")
        await forecast.refresh(settings, force=True)
        await feeds.refresh(settings)
        store.load_all()
        return {"weather": forecast.status, "content": store.status.family}

    @app.get(
        "/api/parent/calendars",
        response_model=list[CalendarRow],
        dependencies=[Depends(require_parent)],
    )
    def parent_calendars() -> list[CalendarRow]:
        _, settings, *_ = snapshot()
        return feeds.rows(settings)

    @app.get(
        "/api/parent/about",
        response_model=About,
        dependencies=[Depends(require_parent)],
    )
    def parent_about(request: Request) -> About:
        """The machine, for the About section. Never the upload token itself:
        only whether one is set."""
        return About(
            version=read_version(),
            lan_url=system.lan_url(request.url.port),
            launchd=system.launchd_status(),
            upload_token=bool(os.environ.get("MANTEL_UPLOAD_TOKEN", "").strip()),
        )

    @app.post(
        "/api/parent/reload",
        response_model=Health,
        dependencies=[Depends(require_parent)],
    )
    def parent_reload() -> Health:
        """Ask both iPads to reload. Each one sees reload_at change in /api/health
        on its next poll and reloads then; there is no push."""
        app.state.reload_at = local_now().isoformat(timespec="seconds")
        return health()

    @app.get(
        "/api/parent/meals",
        response_model=list[MealDay],
        dependencies=[Depends(require_parent)],
    )
    def parent_meals(
        start: Annotated[Date | None, Query(alias="from")] = None,
        days: Annotated[int, Query(ge=1)] = 7,
    ) -> list[MealDay]:
        _, settings, _, _meals, _ = snapshot()
        first = start if start is not None else _today(settings.timezone)
        span = min(days, MAX_MEALS_DAYS)
        catalog = store.catalog.current
        names = catalog.names if catalog is not None else {}
        resolved = picks_week(first, first + timedelta(days=span - 1))
        return meals_window(resolved.on, first, span, names)

    @app.put(
        "/api/parent/meals",
        response_model=list[MealDay],
        dependencies=[Depends(require_parent)],
    )
    def parent_meals_save(edit: MealsEdit) -> list[MealDay]:
        catalog = store.catalog.current
        names = catalog.names if catalog is not None else {}

        def validate(text: str) -> None:
            try:
                Meals.model_validate(yaml.safe_load(text), context={"dish_names": names})
            except ValidationError as exc:
                raise HTTPException(
                    status_code=422, detail=f"meals.yaml would be invalid: {exc}"
                ) from exc

        edit_meals(store.directory / "meals.yaml", edit.days, names, local_now(), validate)
        store.load_all()
        _, _, _, meals, _ = snapshot()
        return [meals_view(meals.on(day.date), day.date, names) for day in edit.days]

    def _limb(name: str, index: int, ends_at: object) -> PanchangLimb:
        return PanchangLimb(name=name, index=index, ends_at=ends_at)  # type: ignore[arg-type]

    @app.get("/api/panchang", response_model=PanchangDayModel)
    def panchang_day(date: Annotated[Date | None, Query()] = None) -> PanchangDayModel:
        """The almanac for one day, with the family's day folded into it."""
        family, settings, schedule, meals, tasks = snapshot()
        when = date if date is not None else _today(settings.timezone)
        computed = almanac().day(when)
        school_day, note = term.day(when)
        planned = meals.on(when)
        return PanchangDayModel(
            date=when,
            sunrise=computed.sunrise,
            sunset=computed.sunset,
            moonrise=computed.moonrise,
            moonset=computed.moonset,
            vaara=computed.vaara,
            tithi=PanchangTithi(
                name=computed.tithi.name,
                index=computed.tithi.index,
                ends_at=computed.tithi.ends_at,
                paksha=computed.paksha,
            ),
            nakshatra=_limb(
                computed.nakshatra.name, computed.nakshatra.index, computed.nakshatra.ends_at
            ),
            yoga=_limb(computed.yoga.name, computed.yoga.index, computed.yoga.ends_at),
            karana=_limb(computed.karana.name, computed.karana.index, computed.karana.ends_at),
            masa=PanchangMasa(name=computed.masa.name, adhika=computed.masa.adhika),
            samvat=PanchangSamvat(vikram=computed.vikram, shaka=computed.shaka),
            flags=computed.flags,
            observances=observances_on(when, settings),
            school=PanchangSchool(is_school_day=school_day, note=note),
            diet=table.day(when),
            meals={
                slot: getattr(planned, slot).name if getattr(planned, slot) else None
                for slot in ("breakfast", "lunch", "dinner")
            },
        )

    @app.get("/api/panchang/month", response_model=PanchangMonth)
    def panchang_month(ym: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")]) -> PanchangMonth:
        """A month of cells. The astronomy is cached; the rest is read live.

        Observances, school days, diet and meals all move with the feeds and
        the content, so they are folded in per request rather than frozen into
        the cache file beside the sky.
        """
        settings = store.settings.current
        if settings is None:
            raise HTTPException(status_code=503, detail="content unavailable")
        content_meals = store.meals.current or Meals()
        kinds = {feed.id: feed.kind for feed in settings.calendars}
        observed = by_date(feeds.events_of_kind(settings, *OBSERVANCE_KINDS), kinds)

        ours = set(kid_ids())
        days: list[MonthDay] = []
        for cached in almanac().month(ym):
            school_day, note = term.day(cached.date)
            planned = content_meals.on(cached.date)
            events = feeds.events_on(cached.date)
            days.append(
                MonthDay(
                    date=cached.date,
                    weekday=weekday_of(cached.date),
                    tithi_short=cached.tithi_short,
                    tithi_name=cached.tithi_name,
                    paksha=cached.paksha,
                    nakshatra=cached.nakshatra_name,
                    masa=cached.masa_name,
                    flags=cached.flags,
                    observances=[
                        observance.name for observance in observed.get(cached.date, [])
                    ],
                    holiday=any(
                        observance.kind == "holiday"
                        for observance in observed.get(cached.date, [])[:1]
                    ),
                    family=any(
                        event.kid == FAMILY_ID and kinds.get(event.calendar_id) == "family"
                        for event in events
                    ),
                    school=PanchangSchool(is_school_day=school_day, note=note),
                    school_kids=sorted(
                        {
                            event.kid
                            for event in events
                            if event.source == "school" and event.kid != FAMILY_ID
                        }
                    ),
                    kids=sorted(
                        {event.kid for event in events if event.kid in ours}
                    ),
                    non_veg_ok=table.day(cached.date).non_veg_ok,
                    has_meals=any(
                        getattr(planned, slot) for slot in ("breakfast", "lunch", "dinner")
                    ),
                )
            )
        return PanchangMonth(ym=ym, days=days)

    def kid_ids() -> list[str]:
        family, *_ = snapshot()
        return [kid.id for kid in family.kids]

    def today_here() -> Date:
        settings = store.settings.current
        return _today(settings.timezone if settings is not None else FALLBACK_TIMEZONE)

    def now_here() -> datetime:
        settings = store.settings.current
        zone = settings.timezone if settings is not None else FALLBACK_TIMEZONE
        return datetime.now(_zone(zone))

    @app.post("/api/claims", response_model=Claim, status_code=201)
    def make_claim(request: ClaimRequest) -> Claim:
        """A kid says they did a task. Points move when a parent agrees."""
        _family, _settings, _schedule, _meals, tasks = snapshot()
        if request.kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {request.kid_id!r}")

        today = today_here()
        day = request.date if request.date is not None else today
        # Yesterday's chores are yesterday's. Claiming into the future is the
        # kind of thing a bug does, and a child would notice it worked.
        if day != today:
            raise HTTPException(status_code=400, detail="a task is claimed on the day it is done")

        try:
            with books.write() as connection:
                return claims.claim(
                    connection,
                    tasks,
                    kid_id=request.kid_id,
                    task_id=request.task_id,
                    day=day,
                    now=now_here(),
                )
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc

    @app.delete("/api/claims/{claim_id}", status_code=204)
    def undo_claim(claim_id: int) -> Response:
        """Take it back. Allowed until a parent has decided, not for 5 seconds:
        a child who notices a minute later should not need to ask."""
        try:
            with books.write() as connection:
                claims.undo(connection, claim_id)
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        return Response(status_code=204)

    @app.get("/api/claims", response_model=list[Claim])
    def list_claims(date: Annotated[Date | None, Query()] = None) -> list[Claim]:
        with books.connect() as connection:
            return claims.on_day(connection, date if date is not None else today_here())

    @app.get("/api/kids/pins", response_model=PinState)
    def pin_state() -> PinState:
        """Which cards are latched. Not which codes they are."""
        with books.connect() as connection:
            return PinState(pins=pins.which_have_pins(connection, kid_ids()))

    @app.post("/api/kids/{kid_id}/pin/verify", response_model=PinResult)
    def verify_kid_pin(kid_id: str, attempt: KidPin) -> PinResult:
        if kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {kid_id!r}")
        with books.connect() as connection:
            return PinResult(ok=pins.check(connection, kid_id, attempt.pin))

    @app.put(
        "/api/kids/{kid_id}/pin",
        response_model=PinState,
        dependencies=[Depends(require_parent)],
    )
    def set_kid_pin(kid_id: str, body: KidPin) -> PinState:
        """Set or clear one kid's code. Parents only, and an empty pin clears."""
        if kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {kid_id!r}")
        pin = body.pin.strip()
        if pin and not (pin.isdigit() and len(pin) == 4):
            raise HTTPException(status_code=400, detail="a kid pin is four digits")
        with books.write() as connection:
            pins.set_pin(connection, kid_id, pin)
            return PinState(pins=pins.which_have_pins(connection, kid_ids()))

    def shop() -> Rewards:
        current = store.rewards.current
        if current is None:
            raise HTTPException(status_code=503, detail="rewards unavailable")
        return current

    def points_settings() -> Points:
        settings = store.settings.current
        return settings.points if settings is not None else Points()

    def school_day_of(day: Date) -> bool:
        return bool(term.day(day)[0])

    @app.get("/api/approvals/count", response_model=PendingCount)
    def approvals_waiting() -> PendingCount:
        """How many things wait on a parent.

        Read by the lock screen, so it says how many and nothing else: a
        badge a child can see must not tell them whose or what.
        """
        with books.connect() as connection:
            waiting = approvals.pending_count(connection)
        return PendingCount(pending=waiting + len(meals_waiting()))

    @app.get(
        "/api/parent/approvals",
        response_model=list[ApprovalItem],
        dependencies=[Depends(require_parent)],
    )
    def approval_queue() -> list[ApprovalItem]:
        _family, _settings, _schedule, _meals, tasks = snapshot()
        with books.connect() as connection:
            queued = approvals.queue(connection, tasks, shop())
        # Meals a child picked come first: they have a date, and the date is
        # usually tomorrow.
        return [*meals_waiting(), *queued]

    def meals_waiting() -> list[ApprovalItem]:
        """Contested meals still open, and treats waiting on an OK."""
        catalog = store.catalog.current
        if catalog is None:
            return []
        now = local_now()
        with books.write() as connection:
            weekly.settle_locked(connection, catalog, diet_ok=diet_ok, now=now)
            return weekly.waiting(connection, catalog, the_meals(), today_here(), now)

    @app.post(
        "/api/parent/claims/{claim_id}/approve",
        response_model=PointsSummary,
        dependencies=[Depends(require_parent)],
    )
    def approve(claim_id: int) -> PointsSummary:
        """Believe them, and pay for it, in one transaction."""
        _family, settings, _schedule, _meals, tasks = snapshot()
        now = now_here()
        try:
            with books.write() as connection:
                approvals.approve_claim(
                    connection,
                    tasks,
                    settings.points,
                    claim_id=claim_id,
                    decided_by="parent",
                    now=now,
                    is_school_day=school_day_of,
                )
                found = claims.by_id(connection, claim_id)
                kid_id = found.kid_id if found is not None else ""
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        return summary_for(kid_id, tasks, now)

    @app.post(
        "/api/parent/claims/{claim_id}/decline",
        response_model=PointsSummary,
        dependencies=[Depends(require_parent)],
    )
    def decline(claim_id: int) -> PointsSummary:
        """Say no. Nothing is written to the ledger, because nothing happened."""
        _family, _settings, _schedule, _meals, tasks = snapshot()
        now = now_here()
        try:
            with books.write() as connection:
                found = claims.by_id(connection, claim_id)
                kid_id = found.kid_id if found is not None else ""
                approvals.decline_claim(
                    connection, claim_id=claim_id, decided_by="parent", now=now
                )
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        return summary_for(kid_id, tasks, now)

    @app.post(
        "/api/parent/awards",
        response_model=PointsSummary,
        dependencies=[Depends(require_parent)],
    )
    def make_award(request: AwardRequest) -> PointsSummary:
        _family, _settings, _schedule, _meals, tasks = snapshot()
        if request.kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {request.kid_id!r}")
        now = now_here()
        try:
            with books.write() as connection:
                approvals.award(
                    connection,
                    kid_id=request.kid_id,
                    points=request.points,
                    note=request.note,
                    decided_by="parent",
                    now=now,
                    deductions=points_settings().deductions,
                )
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        return summary_for(request.kid_id, tasks, now)

    def summary_for(kid_id: str, tasks: Tasks, now: datetime) -> PointsSummary:
        """The three numbers, read back after a write so the kiosk can bounce."""
        with books.connect() as connection:
            return PointsSummary(
                kid_id=kid_id,
                balance=ledger.balance(connection, kid_id),
                this_week=ledger.earned_since(connection, kid_id, ledger.week_start(now)),
                week_days=ledger.earned_by_day(connection, kid_id, now),
                streak_days=(
                    0
                    if kid_id in ("", ledger.FAMILY)
                    else current_streak(
                        connection, tasks, kid_id, now.date(), school_day_of
                    )
                ),
                saving_for=(
                    []
                    if kid_id in ("", ledger.FAMILY)
                    else saving.summary(connection, kid_id, shop())
                ),
                cash_cents=banks.balance(connection, kid_id, "cash"),
                roblox_minutes=banks.balance(connection, kid_id, "roblox"),
                last_deposit=banks.last_deposit(connection, kid_id),
            )

    @app.get(
        "/api/parent/payouts",
        response_model=list[Payout],
        dependencies=[Depends(require_parent)],
    )
    def payout_history(kid_id: Annotated[str, Query()]) -> list[Payout]:
        with books.connect() as connection:
            return cash.history(connection, kid_id)

    def allowance_settings() -> Allowance:
        settings = store.settings.current
        return settings.allowance if settings is not None else Allowance()

    @app.post("/api/redemptions", response_model=Redemption, status_code=201)
    def ask_for_reward(request: RedemptionRequest) -> Redemption:
        """A child asking to spend what they earned. The points are held now."""
        if request.kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {request.kid_id!r}")
        try:
            with books.write() as connection:
                return redemptions.request(
                    connection,
                    shop(),
                    points_settings(),
                    kid_id=request.kid_id,
                    reward_id=request.reward_id,
                    now=now_here(),
                )
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc

    @app.get("/api/redemptions/{kid_id}", response_model=list[Redemption])
    def my_rewards(kid_id: str) -> list[Redemption]:
        with books.connect() as connection:
            return redemptions.for_kid(connection, shop(), kid_id)

    @app.post("/api/jar", response_model=PointsSummary)
    def put_in_the_jar(request: JarRequest) -> PointsSummary:
        """Move points from one child to the family. Two rows, summing to zero."""
        _family, _settings, _schedule, _meals, tasks = snapshot()
        if request.kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {request.kid_id!r}")
        now = now_here()
        with books.write() as connection:
            if ledger.balance(connection, request.kid_id) < request.points:
                raise HTTPException(status_code=409, detail="not that many points")
            ledger.transfer_to_jar(
                connection, kid_id=request.kid_id, points=request.points, now=now
            )
        return summary_for(request.kid_id, tasks, now)

    @app.post(
        "/api/parent/redemptions/{redemption_id}/approve",
        response_model=Redemption,
        dependencies=[Depends(require_parent)],
    )
    def approve_reward(redemption_id: int) -> Redemption:
        try:
            with books.write() as connection:
                return redemptions.approve(
                    connection,
                    shop(),
                    allowance_settings(),
                    redemption_id=redemption_id,
                    now=now_here(),
                )
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc

    @app.post(
        "/api/parent/redemptions/{redemption_id}/decline",
        response_model=Redemption,
        dependencies=[Depends(require_parent)],
    )
    def decline_reward(redemption_id: int) -> Redemption:
        """Say no, and put the points straight back."""
        try:
            with books.write() as connection:
                return redemptions.decline(
                    connection, shop(), redemption_id=redemption_id, now=now_here()
                )
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc

    @app.get(
        "/api/parent/todos",
        response_model=list[Todo],
        dependencies=[Depends(require_parent)],
    )
    def parent_todos() -> list[Todo]:
        """Approved is not done: the ice cream still has to be bought."""
        with books.connect() as connection:
            return all_todos(connection)

    def kid_names() -> dict[str, str]:
        family, *_ = snapshot()
        return {kid.id: kid.name for kid in family.kids}

    def all_todos(connection: Any) -> list[Todo]:
        """Rewards to deliver, allowance to pay, and bank requests to hand over."""
        return [
            *redemptions.todos(connection, shop(), today_here()),
            *banks.todos(connection, kid_names()),
        ]

    @app.post(
        "/api/parent/todos/done",
        response_model=list[Todo],
        dependencies=[Depends(require_parent)],
    )
    def finish_todo(body: TodoDone) -> list[Todo]:
        try:
            with books.write() as connection:
                redemptions.finish(connection, body.ref, now=now_here())
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        with books.connect() as connection:
            return all_todos(connection)

    def bank_settings() -> Banks:
        settings = store.settings.current
        return settings.banks if settings is not None else Banks()

    def known_kid(kid_id: str) -> None:
        if kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {kid_id!r}")

    def bank_of(kid_id: str) -> KidBank:
        with books.connect() as connection:
            return banks.view(connection, kid_id, bank_settings(), points_settings(), today_here())

    @app.get("/api/banks/{kid_id}", response_model=KidBank)
    def kid_bank(kid_id: str) -> KidBank:
        """A child's piggy bank and Roblox bank, and what is waiting."""
        known_kid(kid_id)
        return bank_of(kid_id)

    @app.post("/api/banks/{kid_id}/cashout", response_model=KidBank, status_code=201)
    def ask_to_cash_out(kid_id: str, body: CashoutRequest) -> KidBank:
        """Ask for money out. It is held until a parent taps Paid."""
        known_kid(kid_id)
        try:
            with books.write() as connection:
                banks.cash_out(
                    connection, bank_settings(), kid_id=kid_id, cents=body.cents, now=now_here()
                )
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        return bank_of(kid_id)

    @app.post("/api/banks/{kid_id}/roblox/use", response_model=KidBank, status_code=201)
    def ask_to_use_roblox(kid_id: str, body: RobloxUseRequest) -> KidBank:
        """Ask for Roblox time. Held until a parent taps Done (v4: the policy
        plane grants it instead)."""
        known_kid(kid_id)
        try:
            with books.write() as connection:
                banks.use_roblox(
                    connection,
                    bank_settings(),
                    points_settings(),
                    kid_id=kid_id,
                    minutes=body.minutes,
                    now=now_here(),
                )
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        return bank_of(kid_id)

    def parent_banks_view() -> ParentBanks:
        with books.connect() as connection:
            return ParentBanks(
                kids=[
                    banks.view(
                        connection, kid_id, bank_settings(), points_settings(), today_here()
                    )
                    for kid_id in kid_ids()
                ],
                todos=banks.todos(connection, kid_names()),
            )

    @app.get(
        "/api/parent/banks",
        response_model=ParentBanks,
        dependencies=[Depends(require_parent)],
    )
    def parent_banks() -> ParentBanks:
        return parent_banks_view()

    @app.post(
        "/api/parent/banks/{kid_id}/adjust",
        response_model=ParentBanks,
        dependencies=[Depends(require_parent)],
    )
    def adjust_bank(kid_id: str, body: BankAdjust) -> ParentBanks:
        """Birthday money, or a correction: a row of its own, never an edit."""
        known_kid(kid_id)
        try:
            with books.write() as connection:
                banks.adjust(
                    connection,
                    kid_id=kid_id,
                    account=body.account,
                    delta=body.delta,
                    note=body.note,
                    now=now_here(),
                )
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        return parent_banks_view()

    @app.post(
        "/api/parent/banks/requests/{request_id}/decline",
        response_model=list[Todo],
        dependencies=[Depends(require_parent)],
    )
    def decline_bank_request(request_id: int) -> list[Todo]:
        """Not this time: the hold ends and nothing leaves the bank."""
        try:
            with books.write() as connection:
                banks.decline(connection, request_id, now=now_here())
        except claims.ClaimError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        with books.connect() as connection:
            return all_todos(connection)

    def the_catalog() -> MealsCatalog:
        current = store.catalog.current
        if current is None:
            raise HTTPException(status_code=503, detail="meals catalog unavailable")
        return current

    def the_meals() -> Meals:
        return store.meals.current or Meals()

    def meals_validator(text: str) -> None:
        catalog = store.catalog.current
        try:
            Meals.model_validate(
                yaml.safe_load(text),
                context={"dish_names": catalog.names if catalog else {}},
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail=f"meals.yaml would be invalid: {exc}"
            ) from exc

    def diet_ok(day: Date) -> bool:
        """Whether meat, fish and egg are allowed that day."""
        return bool(table.day(day).non_veg_ok)

    def picks_week(start: Date, end: Date) -> weekly.Week:
        """The plan and the picks for these days, resolved. Anything contested
        whose lock has passed is settled first, so no reader ever sees a
        contest nobody can decide any more."""
        catalog = store.catalog.current
        now = local_now()
        with books.write() as connection:
            if catalog is not None:
                weekly.settle_locked(connection, catalog, diet_ok=diet_ok, now=now)
            return weekly.week(connection, the_meals(), catalog, start, end, now)

    def pick_error(exc: claims.ClaimError) -> HTTPException:
        return HTTPException(status_code=exc.status, detail=exc.detail)

    @app.get("/api/picks", response_model=list[DayPicks])
    def week_of_picks(
        week: Annotated[str | None, Query(pattern=r"^\d{4}-W\d{2}$")] = None,
        start: Annotated[Date | None, Query(alias="from")] = None,
        days: Annotated[int, Query(ge=1, le=28)] = 7,
    ) -> list[DayPicks]:
        """Each day's three meals: the plan, the picks on it, what it comes
        to, and whether it is contested or locked. `week=2026-W39` is Monday
        to Sunday; `from=` is that many days from a date."""
        if week is not None:
            year, number = week.split("-W")
            first = Date.fromisocalendar(int(year), int(number), 1)
            days = 7
        else:
            first = start if start is not None else today_here()
        last = first + timedelta(days=days - 1)
        resolved = picks_week(first, last)
        return [resolved.day(first + timedelta(days=offset)) for offset in range(days)]

    @app.get("/api/picks/options", response_model=list[PickOption])
    def pick_options(
        kid_id: Annotated[str, Query()],
        slot: Annotated[Literal["breakfast", "lunch", "dinner"], Query()],
        date: Annotated[Date | None, Query()] = None,
    ) -> list[PickOption]:
        """The slot's dishes on that day, with the diet applied and anything
        worth saying said."""
        if kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {kid_id!r}")
        day = date if date is not None else today_here() + timedelta(days=1)
        catalog = the_catalog()
        with books.connect() as connection:
            used = weekly.treats_this_week(
                connection, catalog, kid_id, day, except_slot=(day, slot)
            )
        return picks.options(
            catalog,
            picks_week(day, day),
            slot=slot,
            day=day,
            non_veg_ok=diet_ok(day),
            treats_used=used,
            for_kid=True,
        )

    @app.post("/api/picks", response_model=SlotView)
    def make_pick(request: PickRequest) -> SlotView:
        """A child's pick for one meal, replacing their own earlier one. Free:
        nothing is spent and nothing is written to the ledger."""
        if request.kid_id not in kid_ids():
            raise HTTPException(status_code=404, detail=f"unknown kid {request.kid_id!r}")
        catalog = the_catalog()
        dish = next((one for one in catalog.dishes if one.id == request.dish_id), None)
        if dish is None or not picks.serves(dish, request.slot):
            raise HTTPException(status_code=404, detail=f"no {request.slot} {request.dish_id!r}")
        if request.kids_protein not in picks.allowed_proteins(dish, diet_ok(request.date)):
            raise HTTPException(status_code=409, detail=f"no {request.kids_protein} that day")
        place = checked_place(request.place) if out.is_out(dish.id) else None
        try:
            with books.write() as connection:
                if place:
                    out.remember(connection, place)
                weekly.choose(
                    connection,
                    catalog,
                    kid_id=request.kid_id,
                    day=request.date,
                    slot=request.slot,
                    dish_id=request.dish_id,
                    protein=request.kids_protein,
                    now=local_now(),
                    note=place,
                )
        except claims.ClaimError as exc:
            raise pick_error(exc) from exc
        return picks_week(request.date, request.date).slot(request.date, request.slot)

    def checked_place(place: str | None) -> str | None:
        try:
            return out.clean_place(place)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/places/recent", response_model=list[str])
    def recent_places() -> list[str]:
        """The last ten distinct places eaten out, most recent first: the chips
        above "Where? (optional)"."""
        with books.connect() as connection:
            return out.recent(connection)

    @app.delete("/api/picks/{pick_id}", status_code=204)
    def take_back_pick(pick_id: int, kid_id: Annotated[str, Query()]) -> Response:
        """A child taking their own pick back while it can still change."""
        try:
            with books.write() as connection:
                weekly.withdraw(connection, pick_id, kid_id=kid_id, now=local_now())
        except claims.ClaimError as exc:
            raise pick_error(exc) from exc
        return Response(status_code=204)

    @app.post(
        "/api/parent/picks/decide",
        response_model=DecisionResult,
        dependencies=[Depends(require_parent)],
    )
    def decide_pick(body: PickDecision) -> DecisionResult:
        """A parent settling a contested meal: one child's dish, or alternate
        — that dish now and the other on the next day it can be."""
        try:
            with books.write() as connection:
                return weekly.decide(
                    connection, the_catalog(), body, diet_ok=diet_ok, now=local_now()
                )
        except claims.ClaimError as exc:
            raise pick_error(exc) from exc

    @app.post(
        "/api/parent/picks/{pick_id}/approve",
        response_model=PickRow,
        dependencies=[Depends(require_parent)],
    )
    def approve_treat(pick_id: int) -> PickRow:
        try:
            with books.write() as connection:
                return weekly.answer_treat(connection, pick_id, approve=True, now=local_now())
        except claims.ClaimError as exc:
            raise pick_error(exc) from exc

    @app.post(
        "/api/parent/picks/{pick_id}/decline",
        response_model=PickRow,
        dependencies=[Depends(require_parent)],
    )
    def decline_treat(pick_id: int) -> PickRow:
        try:
            with books.write() as connection:
                return weekly.answer_treat(connection, pick_id, approve=False, now=local_now())
        except claims.ClaimError as exc:
            raise pick_error(exc) from exc

    @app.post(
        "/api/parent/meals/set",
        response_model=list[MealDay],
        dependencies=[Depends(require_parent)],
    )
    def set_meal(body: MealOverride) -> list[MealDay]:
        """A parent's pen on one meal: this dish as the plan, or the plan as it
        stands (dish_id null). Either way the children's picks give way."""
        catalog = the_catalog()
        if body.dish_id is not None:
            dish = next((one for one in catalog.dishes if one.id == body.dish_id), None)
            if dish is None or not picks.serves(dish, body.slot):
                raise HTTPException(status_code=404, detail=f"no {body.slot} {body.dish_id!r}")
            place = checked_place(body.place) if out.is_out(dish.id) else None
            set_plan_slot(
                store.directory / "meals.yaml",
                body.date,
                body.slot,
                body.dish_id,
                local_now(),
                meals_validator,
                place=place,
            )
            store.load_all()
            if place:
                with books.write() as connection:
                    out.remember(connection, place)
        with books.write() as connection:
            weekly.override(connection, body.date, body.slot, now=local_now())
        resolved = picks_week(body.date, body.date)
        return meals_window(resolved.on, body.date, 1, catalog.names)

    @app.get(
        "/api/parent/meals/options",
        response_model=list[PickOption],
        dependencies=[Depends(require_parent)],
    )
    def parent_meal_options(
        slot: Annotated[Literal["breakfast", "lunch", "dinner"], Query()],
        date: Annotated[Date, Query()],
    ) -> list[PickOption]:
        """The whole catalog for the slot, with the reasons a child could not
        choose a dish left on as warnings. A parent may choose any of it."""
        return picks.options(
            the_catalog(), picks_week(date, date), slot=slot, day=date, non_veg_ok=diet_ok(date)
        )

    @app.get("/api/digest", response_model=Digest)
    def week_digest(week: Annotated[str | None, Query()] = None) -> Digest:
        """The week, added up. The only thing in Mantel anything else may read."""
        family, settings, _schedule, _meals, tasks = snapshot()
        today = today_here()
        resolved = picks_week(today - timedelta(days=14), today + timedelta(days=7))
        with books.connect() as connection:
            return digest.build(
                connection,
                family,
                tasks,
                shop(),
                resolved,
                week=week or "",
                today=today_here(),
                zone=_zone(settings.timezone),
            )

    @app.get("/api/points/{kid_id}", response_model=PointsSummary)
    def points_for(kid_id: str) -> PointsSummary:
        """What a kid's card shows. All derived, none stored.

        The same builder the write paths return, rather than a second copy of
        the arithmetic: this endpoint had its own, and the saving-for picks
        reached the one and not the other — so a bar appeared the moment a
        child starred it and vanished on the next poll.
        """
        family, _settings, _schedule, _meals, tasks = snapshot()
        known = {kid.id for kid in family.kids} | {ledger.FAMILY}
        if kid_id not in known:
            raise HTTPException(status_code=404, detail=f"unknown kid {kid_id!r}")
        return summary_for(kid_id, tasks, now_here())

    @app.get("/api/ledger/{kid_id}", response_model=list[LedgerRow])
    def ledger_for(
        kid_id: str, days: Annotated[int, Query(ge=1, le=365)] = 30
    ) -> list[LedgerRow]:
        """The kid's history, newest first. The jar is read the same way."""
        _family, settings, *_ = snapshot()
        now = datetime.now(_zone(settings.timezone))
        since = now - timedelta(days=days)
        with books.connect() as connection:
            return ledger.entries(connection, kid_id, since=since)

    @app.get("/api/rewards", response_model=list[Reward])
    def rewards() -> list[Reward]:
        """The shop, in file order. Disabled rewards are included on purpose:
        a child who cannot see a reward cannot save towards it."""
        shop = store.rewards.current
        if shop is None:
            raise HTTPException(status_code=503, detail="rewards unavailable")
        return shop.rewards

    @app.get("/api/school/events", response_model=list[Series])
    def school_events(days: Annotated[int, Query(ge=1, le=180)] = 60) -> list[Series]:
        """Every school event ahead, grouped into the series a parent decides
        about. Includes the ones nobody has decided about, which is the point:
        this is the list the parent screen offers."""
        family, settings, *_ = snapshot()
        first = _today(settings.timezone)
        upcoming = [
            event
            for offset in range(days)
            for event in feeds.events_on(first + timedelta(days=offset))
            if event.source == "school"
        ]
        return group(upcoming, school_config(), [kid.id for kid in family.kids])

    # Last, so every /api route is matched before the kiosk's catch-all.
    mount_kiosk(app)

    return app


app = create_app()
