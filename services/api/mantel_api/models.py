"""Pydantic models for the YAML content files and the API responses."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationInfo,
    field_validator,
    model_validator,
)

HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
ClockTime = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]

Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

#: Schedule items and tasks may belong to a kid or to the whole family.
FAMILY_ID = "family"


def known_kid_ids(info: ValidationInfo) -> set[str] | None:
    """Kid ids the loader passed in, or None when nothing was passed.

    Cross-file checks only run when the loader supplies the roster; a model
    validated on its own has no way to know who exists.
    """
    context = info.context
    if isinstance(context, dict):
        ids = context.get("kid_ids")
        if isinstance(ids, (set, frozenset, list, tuple)):
            return {str(kid_id) for kid_id in ids}
    return None


def check_kid_id(value: str, info: ValidationInfo, *, allow_family: bool) -> str:
    known = known_kid_ids(info)
    if known is None:
        return value
    if allow_family and value == FAMILY_ID:
        return value
    if value not in known:
        allowed = sorted(known | ({FAMILY_ID} if allow_family else set()))
        raise ValueError(f"unknown kid id {value!r}; family.yaml has {allowed}")
    return value


def known_person_ids(info: ValidationInfo) -> set[str] | None:
    """Everyone in family.yaml, kids and parents, when the loader supplied them."""
    context = info.context
    if isinstance(context, dict):
        ids = context.get("person_ids")
        if isinstance(ids, (set, frozenset, list, tuple)):
            return {str(person_id) for person_id in ids}
    return None


def check_person_id(value: str, info: ValidationInfo) -> str:
    known = known_person_ids(info)
    if known is None or value in known:
        return value
    raise ValueError(f"unknown person id {value!r}; family.yaml has {sorted(known)}")


class ContentModel(BaseModel):
    """Base for anything parsed out of content/: unknown keys are a mistake."""

    model_config = ConfigDict(extra="forbid")


#: The avatars bundled with the kiosk, drawn in apps/kiosk/src/avatars.
AVATARS = frozenset({
    "bear", "cat", "deer", "dog", "elephant", "fox", "frog", "giraffe", "hedgehog",
    "koala", "lion", "monkey", "octopus", "owl", "panda", "parrot", "penguin",
    "rabbit", "seal", "tiger", "turtle", "whale", "wolf", "zebra",
})


#: "MM-DD". No year: the screen says whose birthday it is, never how old.
BIRTHDAY = r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"


def _a_real_day(value: str) -> str:
    """The pattern allows 02-30, which is not a day anybody was born on.

    Checked against a leap year, so 02-29 is a birthday and 02-30 is a typo
    caught when the file loads rather than on the wall in February.
    """
    month, day = (int(part) for part in value.split("-"))
    Date(2024, month, day)
    return value


Birthday = Annotated[str, Field(pattern=BIRTHDAY), AfterValidator(_a_real_day)]


class Kid(ContentModel):
    id: str
    name: str
    color: HexColor
    #: One of the bundled animals. None keeps the initial the columns had
    #: before anyone chose one.
    avatar: str | None = None
    #: MM-DD, and optional: a family that would rather not have it on the
    #: wall simply leaves it out.
    birthday: Birthday | None = None

    @field_validator("avatar")
    @classmethod
    def _avatar_exists(cls, value: str | None) -> str | None:
        if value is not None and value not in AVATARS:
            raise ValueError(f"unknown avatar {value!r}; have {', '.join(sorted(AVATARS))}")
        return value


class Parent(ContentModel):
    id: str
    name: str
    birthday: Birthday | None = None


class Family(ContentModel):
    kids: list[Kid]
    parents: list[Parent]


class Location(ContentModel):
    name: str
    lat: float
    lon: float


class Units(ContentModel):
    temp: Literal["F", "C"]


class Night(ContentModel):
    start: ClockTime
    end: ClockTime
    idle_minutes: int
    frame: bool


class DateRange(ContentModel):
    """An inclusive span of days, written `from`/`to` in YAML.

    "from" is a keyword, so the YAML spelling lives in the alias. Responses
    use the alias too, so the kiosk sees the same shape as the file.
    """

    model_config = ConfigDict(populate_by_name=True)

    start: Date = Field(alias="from")
    end: Date = Field(alias="to")
    name: str

    @model_validator(mode="after")
    def _ordered(self) -> DateRange:
        if self.end < self.start:
            raise ValueError(f"{self.name!r} ends before it starts")
        return self

    def covers(self, day: Date) -> bool:
        return self.start <= day <= self.end


CalendarKind = Literal["kid", "family", "holiday", "festival", "school"]

#: Kinds whose URL is a secret: anyone holding it can read the calendar.
PRIVATE_KINDS: frozenset[str] = frozenset({"kid", "family"})


class CalendarFeed(ContentModel):
    """One ICS feed.

    A private calendar names an environment variable, because its URL is a
    password. A public one carries the URL itself: a holiday calendar or a
    school district's feed is nobody's secret, and keeping it in settings.yaml
    means the feed list is reviewable in the repo.
    """

    id: str
    kind: CalendarKind
    kid: str | None = None
    url: str | None = None
    url_env: str | None = None
    #: What the parent screen calls it ("District", "Elementary"). Without
    #: one, a child's feed is their name and anything else its id.
    name: str | None = None

    @field_validator("kid")
    @classmethod
    def _kid_exists(cls, value: str | None, info: ValidationInfo) -> str | None:
        return None if value is None else check_kid_id(value, info, allow_family=True)

    @model_validator(mode="after")
    def _one_source(self) -> CalendarFeed:
        if (self.url is None) == (self.url_env is None):
            raise ValueError(f"calendar {self.id!r} needs exactly one of url or url_env")
        # A file on disk (the sample family's calendars) is nobody's secret:
        # only a web address for a private calendar has to live in .env.
        on_the_web = self.url is not None and "://" in self.url and not self.url.startswith(
            "file://"
        )
        if self.kind in PRIVATE_KINDS:
            if self.url_env is None and on_the_web:
                raise ValueError(
                    f"calendar {self.id!r} is {self.kind}, so its URL must be a secret"
                )
            if self.kid is None:
                raise ValueError(f"calendar {self.id!r} is {self.kind} and needs a kid")
        elif self.url is None:
            raise ValueError(f"calendar {self.id!r} is {self.kind}, so it needs a public url")
        return self

    @property
    def owner(self) -> str:
        """Whose agenda this feed's events belong on."""
        return self.kid or FAMILY_ID


class FestivalRule(ContentModel):
    """Match an observance by name; block that day and the ones after it."""

    match: str
    #: Festivals that run for days are named once, on the first of them.
    span_days: int = Field(default=1, ge=1, le=31)


class DateException(ContentModel):
    date: Date
    reason: str = ""


class Diet(ContentModel):
    """Who eats what, and the rules that decide when the house is vegetarian.

    No dates here: every blocked day is computed from the festival feeds by
    the diet service, so a calendar that moves with the moon stays right
    without anyone editing this file.
    """

    vegetarian: list[str] = Field(default_factory=list)
    non_veg_ok: list[str] = Field(default_factory=list)
    non_veg_days: list[Weekday] = Field(default_factory=list)
    no_non_veg_festivals: list[FestivalRule] = Field(default_factory=list)
    #: Escape hatches. Both are empty by default and should stay that way.
    no_non_veg_dates_extra: list[DateRange] = Field(default_factory=list)
    non_veg_ok_dates: list[DateException] = Field(default_factory=list)

    @field_validator("vegetarian", "non_veg_ok")
    @classmethod
    def _people_exist(cls, value: list[str], info: ValidationInfo) -> list[str]:
        return [check_person_id(person_id, info) for person_id in value]


class Panchang(ContentModel):
    """How the almanac is presented. The maths does not vary; the naming does."""

    #: purnimanta is the North Indian reckoning, where a month turns at the
    #: full moon; amanta turns at the new moon.
    masa_scheme: Literal["purnimanta", "amanta"] = "purnimanta"
    show_yoga_karana: bool = False


class Points(ContentModel):
    """How points behave. Every number the house might want to argue about."""

    #: Paid once for a full streak_days run of every task the day required.
    streak_bonus: int = Field(default=20, ge=0)
    streak_days: int = Field(default=7, ge=1, le=31)
    #: How many Roblox rewards may be redeemed in one week, once they are
    #: enabled at all. Enforced whether they are enabled or not, so turning
    #: them on is one flag and not a rule change.
    roblox_per_week: int = Field(default=2, ge=0)
    #: Whether a parent may take points away. Off: the ledger only goes up
    #: except when something is bought, which is the whole design.
    deductions: bool = False
    parent_idle_minutes: int = Field(default=2, ge=1, le=60)


class Allowance(ContentModel):
    """Pocket money paid by hand; Mantel only remembers to ask."""

    #: Deliberately not an amount. What a day of allowance is worth is a
    #: conversation between parents, not a number this app should hold.
    amount_note: str = "set in settings"
    reminder_hour: int = Field(default=18, ge=0, le=23)


class FrameChip(ContentModel):
    """The clock and weather over the photo frame: on unless turned off, and
    a size for the far side of the room (large is 1.25 times regular)."""

    chip: bool = True
    size: Literal["regular", "large"] = "regular"


class Feelings(ContentModel):
    """The bedtime check-in, off until somebody decides they want it.

    Deliberately the smallest thing that could work: five faces, one tap, on
    the night screen only, and nothing anywhere ever asks for it again. No
    streak, no reminder, no empty day showing as a gap. What a child felt
    about a Tuesday is for the people in the house, so it is shown in the
    weekly digest and on no screen a visitor might see.
    """

    enabled: bool = False


class Settings(ContentModel):
    timezone: str
    location: Location
    units: Units
    night: Night
    idle_minutes: int
    slide_seconds: int
    refresh_minutes: int
    daily_reload: ClockTime
    calendars: list[CalendarFeed] = Field(default_factory=list)
    diet: Diet = Field(default_factory=Diet)
    panchang: Panchang = Field(default_factory=Panchang)
    points: Points = Field(default_factory=Points)
    allowance: Allowance = Field(default_factory=Allowance)
    feelings: Feelings = Field(default_factory=Feelings)
    frame: FrameChip = Field(default_factory=FrameChip)


class ScheduleItem(ContentModel):
    kid: str
    title: str
    days: list[Weekday]
    start: ClockTime
    end: ClockTime
    where: str | None = None
    note: str | None = None

    @field_validator("kid")
    @classmethod
    def _kid_exists(cls, value: str, info: ValidationInfo) -> str:
        return check_kid_id(value, info, allow_family=True)


class ScheduleException(ContentModel):
    """Changes a single occurrence, matched on date and title."""

    date: Date
    title: str
    action: Literal["skip", "move"]
    start: ClockTime | None = None
    end: ClockTime | None = None

    @model_validator(mode="after")
    def _move_has_times(self) -> ScheduleException:
        if self.action == "move" and (self.start is None or self.end is None):
            raise ValueError(f"move exception for {self.title!r} needs start and end")
        return self


class Schedule(ContentModel):
    items: list[ScheduleItem] = Field(default_factory=list)
    exceptions: list[ScheduleException] = Field(default_factory=list)


DishSlot = Literal["breakfast", "lunch", "dinner", "snack", "salad"]
Protein = Literal["veg", "egg", "chicken", "fish"]


class Dish(ContentModel):
    """One dish in the catalog. `protein` lists every way it is cooked."""

    id: str
    name: str
    slot: DishSlot
    protein: list[Protein] = Field(min_length=1)
    cuisine: str
    minutes: int
    lunchbox: bool = False
    weekend: bool = False
    treat: bool = False
    two_ways: str = ""
    recipe_url: str = ""
    #: A glyph from the kiosk's set, for the dishes that are not dishes:
    #: "storefront" on Lunch out and Dinner out.
    glyph: str = ""


class MealsCatalog(ContentModel):
    version: int
    dishes: list[Dish] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> MealsCatalog:
        seen: set[str] = set()
        for dish in self.dishes:
            if dish.id in seen:
                raise ValueError(f"duplicate dish id {dish.id!r}")
            seen.add(dish.id)
        return self

    @model_validator(mode="after")
    def _reserved_out(self) -> MealsCatalog:
        """Lunch out and Dinner out, always, at the top of their pools."""
        from .out import with_reserved

        self.dishes = with_reserved(self.dishes)
        return self

    @property
    def names(self) -> dict[str, str]:
        return {dish.id: dish.name for dish in self.dishes}

    def for_slot(self, slot: DishSlot | None) -> list[Dish]:
        if slot is None:
            return list(self.dishes)
        return [dish for dish in self.dishes if dish.slot == slot]


def _catalog_names(info: ValidationInfo) -> dict[str, str] | None:
    context = info.context
    if isinstance(context, dict):
        names = context.get("dish_names")
        if isinstance(names, dict):
            return {str(key): str(value) for key, value in names.items()}
    return None


class PickChoice(ContentModel):
    """One child's choice for a slot, while it is still a proposal."""

    id: str
    kids_protein: Protein = "veg"
    #: The meal reward this pick spent, so it can be given back if a parent
    #: decides for the other child's dish instead.
    reward: int | None = None


class MealSlot(ContentModel):
    name: str
    note: str | None = None
    kids_protein: Protein = "veg"
    #: The catalog id, which the picker writes and the parent tab reads back.
    id: str | None = None
    #: Whose choice this was. A kid who picked a meal should see their name
    #: on it: that is most of the reward.
    picked_by: list[str] = Field(default_factory=list)
    #: A pick is a proposal until a parent says yes. Anything a parent wrote
    #: by hand is confirmed the moment it is written.
    confirmed: bool = True
    #: The catalog dish a parent planned, when a pick replaced it: what "Use
    #: the plan" goes back to.
    plan: str | None = None
    #: Each child's own choice while the slot is a proposal. Two children who
    #: chose different dishes for the one family dinner is a slot a parent
    #: decides — "Parents decide" on the wall, a row in Approvals.
    picks: dict[str, PickChoice] = Field(default_factory=dict)

    @property
    def contested(self) -> bool:
        return not self.confirmed and len({pick.id for pick in self.picks.values()}) > 1

    @model_validator(mode="before")
    @classmethod
    def _resolve(cls, data: Any, info: ValidationInfo) -> Any:
        """A slot is a bare string, {name, note}, or {id, note, kids_protein}."""
        if isinstance(data, str):
            return {"name": data}
        if not isinstance(data, dict) or "id" not in data:
            return data
        if "name" in data:
            return data

        dish_id = str(data["id"])
        names = _catalog_names(info)
        if names is None:
            # Validated without the catalog (a bare model_validate); the id is
            # the best name available.
            return {**data, "name": dish_id}
        if dish_id not in names:
            raise ValueError(f"unknown dish id {dish_id!r}; not in meals-catalog.yaml")
        return {**data, "name": names[dish_id]}


class DayMeals(ContentModel):
    breakfast: MealSlot | None = None
    lunch: MealSlot | None = None
    dinner: MealSlot | None = None
    snack: MealSlot | None = None


class Meals(RootModel[dict[Date, DayMeals]]):
    """The planned week, keyed by ISO date."""

    root: dict[Date, DayMeals] = Field(default_factory=dict)

    def on(self, day: Date) -> DayMeals:
        return self.root.get(day, DayMeals())


Routine = Literal["morning", "afternoon", "evening"]


class TaskItem(ContentModel):
    id: str
    title: str
    points: int = 0
    #: How often it is done. `day`: every day its set is up. `week`: once a
    #: week (Monday to Sunday) — claimable on any day of its set until a
    #: parent approves it, then done for the rest of the week. Math homework
    #: spread over three evenings is one task, paid once.
    every: Literal["day", "week"] = "day"
    #: Who taps it done. A kid claims their own work and a parent approves it;
    #: `parent` is for the things a child cannot honestly report on themselves,
    #: which show a lock in kid mode and do not respond to a tap.
    claim: Literal["kid", "parent"] = "kid"
    #: Which part of the day it belongs to, which orders the chips.
    routine: Routine = "afternoon"


class KidTasks(ContentModel):
    """One child's two lists: school days, and days without school."""

    #: Monday to Friday, when there is school.
    weekdays: list[TaskItem] = Field(default_factory=list)
    #: Saturday and Sunday — and any weekday with no school, which is a day
    #: off whatever the calendar says.
    weekend: list[TaskItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_meaning_per_id(self) -> KidTasks:
        """A task in both lists is one task: the same title, worth and
        cadence in each, or a claim could not say which it was for."""
        seen: dict[str, TaskItem] = {}
        for listed in (self.weekdays, self.weekend):
            ids = [task.id for task in listed]
            repeated = {task_id for task_id in ids if ids.count(task_id) > 1}
            if repeated:
                raise ValueError(f"task {sorted(repeated)[0]!r} is listed twice in one set")
            for task in listed:
                other = seen.setdefault(task.id, task)
                if other != task:
                    raise ValueError(
                        f"task {task.id!r} differs between weekdays and weekend; "
                        "give it one meaning or two ids"
                    )
        return self


class Tasks(RootModel[dict[str, KidTasks]]):
    """Each kid's weekday and weekend lists, keyed by kid id."""

    root: dict[str, KidTasks] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _kids_exist(self, info: ValidationInfo) -> Tasks:
        for kid_id in self.root:
            check_kid_id(kid_id, info, allow_family=False)
        return self

    def of(self, kid_id: str) -> list[TaskItem]:
        """Every task this kid has, once each: for looking one up by id."""
        both = self.root.get(kid_id, KidTasks())
        seen: dict[str, TaskItem] = {}
        for task in [*both.weekdays, *both.weekend]:
            seen.setdefault(task.id, task)
        return list(seen.values())

    def on(self, kid_id: str, *, weekend: bool) -> list[TaskItem]:
        """The list a day uses: the weekend's, or the weekdays'."""
        both = self.root.get(kid_id, KidTasks())
        return list(both.weekend if weekend else both.weekdays)


class PinAttempt(BaseModel):
    pin: str


class FestivalGroup(BaseModel):
    """One festival as the parent screen shows it: its aliases folded in."""

    name: str
    span_days: int = Field(ge=1, le=31)
    #: The `match:` entries in settings.yaml it stands for. Never drawn.
    matches: list[str]


class DietEdit(BaseModel):
    """The parts of the diet rules the iPad may change. Who is vegetarian is
    not one of them: that is a conversation, not a toggle.

    `festivals` is the file's own list, alias by alias, and is what a write
    carries. `groups` is the same list said once per festival, for the
    screen; it is derived on every read and ignored on write.
    """

    non_veg_days: list[Weekday]
    festivals: list[FestivalRule]
    extra_dates: list[DateRange]
    groups: list[FestivalGroup] = Field(default_factory=list)


class KidEdit(BaseModel):
    """A child as the parent screen edits them. Birthdays stay in the file."""

    id: str
    name: str = Field(min_length=1, max_length=24)
    avatar: str | None = None
    color: HexColor


class ParentSettings(BaseModel):
    """What the iPad may change.

    The flat fields are the originals and always present. The groups are
    optional so that a write naming only some of them leaves the rest of the
    file exactly as it was; the parent screen always sends all of them.
    """

    night_start: ClockTime
    night_end: ClockTime
    idle_minutes: int = Field(ge=1, le=240)
    night_idle_minutes: int = Field(ge=1, le=240)
    night_frame: bool
    slide_seconds: int = Field(ge=3, le=600)
    refresh_minutes: int | None = Field(default=None, ge=1, le=240)
    #: Settings → Photos: the clock and weather chip on the frame, and its size.
    frame_chip: bool | None = None
    frame_chip_size: Literal["regular", "large"] | None = None
    diet: DietEdit | None = None
    points: Points | None = None
    kids: list[KidEdit] | None = None


class MealChoice(BaseModel):
    id: str
    name: str
    kids: list[str]


class MealCell(BaseModel):
    name: str = ""
    note: str = ""
    #: The catalog dish, when the parent picked one from the list. Writing the
    #: id rather than the name keeps the plan linked to the catalog, so a dish
    #: renamed there stays the same dish here.
    id: str = ""
    #: Whose pick this was, so the parent tab can show a dot in their colour.
    picked_by: list[str] = Field(default_factory=list)
    #: False while a kid's pick is still a proposal.
    confirmed: bool = True
    #: The dish a parent planned, by name, when a pick replaced it.
    plan_name: str = ""
    #: True when the children chose different dishes and a parent decides.
    contested: bool = False
    #: Each dish chosen and who chose it, while the slot is a proposal.
    choices: list[MealChoice] = Field(default_factory=list)


class MealDecision(BaseModel):
    """A parent settling a slot: one dish, or back to the plan (None)."""

    date: Date
    slot: Literal["breakfast", "lunch", "dinner"]
    dish_id: str | None = None


class MealDay(BaseModel):
    date: Date
    breakfast: MealCell = Field(default_factory=MealCell)
    lunch: MealCell = Field(default_factory=MealCell)
    dinner: MealCell = Field(default_factory=MealCell)


class MealsEdit(BaseModel):
    days: list[MealDay]


class ContentStatus(BaseModel):
    # The catalog's file is meals-catalog.yaml, and health reports it by name.
    model_config = ConfigDict(populate_by_name=True)

    family: str
    settings: str
    schedule: str
    meals: str
    # Split aliases so the constructor still takes meals_catalog=...
    meals_catalog: str = Field(
        validation_alias="meals-catalog", serialization_alias="meals-catalog"
    )
    tasks: str
    school_events: str = Field(
        default="ok",
        validation_alias="school-events",
        serialization_alias="school-events",
    )
    rewards: str = "ok"


class Photo(BaseModel):
    """One photo as the kiosk sees it. The file itself is at `url`."""

    id: str
    url: str
    w: int
    h: int
    taken_at: Date | None = None
    #: The nearest town, when the photo carried a fix. Resolved once from a
    #: bundled gazetteer; the coordinates themselves are never stored.
    place: str | None = None
    #: When it arrived, which is what the parent screen reports.
    added_at: datetime | None = None
    #: The stored file's size, for the total on the parent screen.
    bytes: int = 0


class Health(BaseModel):
    status: str
    version: str
    time: str
    content: ContentStatus
    weather: str
    calendars: dict[str, str]
    school_year: str = "unknown"
    diet_days: str = "unknown"
    #: The ledger: its schema version and how many rows it holds, or why not.
    ledger: str = "unknown"
    #: Set when a parent asks both iPads to reload; each reloads once it sees
    #: a value different from the one it started with.
    reload_at: str | None = None


CalendarState = Literal["ok", "stale", "error", "not_configured", "never"]


class CalendarRow(BaseModel):
    """One feed as the parent screen shows it. Never the URL."""

    id: str
    kind: str
    kid: str | None = None
    #: The feed's own name from settings.yaml, when it has one.
    name: str | None = None
    state: CalendarState
    fetched_at: datetime | None = None
    #: Events counted, or the error, in words.
    detail: str = ""
    #: For a private feed: the .env variable that holds its URL.
    env: str | None = None


class About(BaseModel):
    """What the About section needs beyond /api/health."""

    version: str
    lan_url: str
    launchd: str
    upload_token: bool


class Config(BaseModel):
    family: Family
    settings: Settings


class AgendaEntry(BaseModel):
    start: str | None = None  # None for an all-day calendar event
    end: str | None = None
    title: str
    where: str | None = None
    note: str | None = None
    source: str
    #: Which kind of feed it came from, so the list view can filter without
    #: asking the API again: kid, family, school, holiday or festival.
    source_kind: str | None = None
    all_day: bool = False
    calendar_id: str | None = None


class CalendarEvent(BaseModel):
    """One expanded occurrence from an ICS feed."""

    calendar_id: str
    kid: str
    #: Where it belongs on the dashboard: "calendar" or "school".
    source: str = "calendar"
    date: Date
    title: str
    start: str | None = None
    end: str | None = None
    where: str | None = None
    all_day: bool = False


class WeatherNow(BaseModel):
    temp: float
    label: str
    icon: str
    is_day: bool


class WeatherDay(BaseModel):
    high: float
    low: float
    precip_pct: int | None = None
    sunrise: str
    sunset: str
    label: str
    icon: str


class Weather(BaseModel):
    """Empty and stale until the first fetch succeeds; never an error."""

    now: WeatherNow | None = None
    today: WeatherDay | None = None
    tomorrow: WeatherDay | None = None
    stale: bool = True
    fetched_at: str | None = None


class TaskEntry(BaseModel):
    id: str
    title: str
    #: Who ticks it off. A kid taps their own; a parent's shows a lock.
    claim: Literal["kid", "parent"] = "kid"
    #: What has happened to it today. "none" is a row nobody has touched.
    status: Literal["none", "claimed", "approved", "declined"] = "none"
    #: What approving it is worth, so the kiosk can say so without a lookup.
    points: int = 0
    #: Which container it sits in on the card.
    routine: Routine = "afternoon"
    #: `week`: once a week, and its status is the week's, not the day's.
    every: Literal["day", "week"] = "day"
    #: The waiting claim's id, so a parent can approve the row where it is
    #: rather than going to find it again on the parent screen. Null unless
    #: something is actually waiting.
    claim_id: int | None = None


class KidDay(BaseModel):
    id: str
    name: str
    color: str
    avatar: str | None = None
    agenda: list[AgendaEntry]
    tasks: list[TaskEntry]
    #: True on their birthday, which the card says out loud.
    birthday: bool = False


class Observance(BaseModel):
    """A holiday or festival falling on a day. Not an appointment."""

    name: str
    kind: CalendarKind
    calendar_id: str


class DayDiet(BaseModel):
    """Whether the kids may eat meat, and why not when they may not."""

    non_veg_ok: bool = True
    reasons: list[str] = Field(default_factory=list)


class DietDay(BaseModel):
    date: Date
    non_veg_ok: bool
    reasons: list[str] = Field(default_factory=list)


class SchoolYear(BaseModel):
    """What the school feeds say, cached so an outage changes nothing."""

    first_day: Date | None = None
    last_day: Date | None = None
    #: True when first_day was worked out rather than read from a feed. The
    #: district stops publishing "First Day of School" once term is under way,
    #: so from about September the year has an end and no beginning.
    first_day_derived: bool = False
    #: date -> the note to show, e.g. "Thanksgiving Break"
    no_school: dict[Date, str] = Field(default_factory=dict)
    minimum_days: dict[Date, str] = Field(default_factory=dict)
    derived_at: datetime | None = None
    sources: list[str] = Field(default_factory=list)

    @property
    def bounds_known(self) -> bool:
        return self.first_day is not None or self.last_day is not None


class Day(BaseModel):
    date: Date
    weekday: Weekday
    is_school_day: bool
    school_note: str | None
    kids: list[KidDay]
    family_agenda: list[AgendaEntry]
    meals: DayMeals
    observances: list[Observance] = Field(default_factory=list)
    diet: DayDiet = Field(default_factory=DayDiet)
    weather: Weather = Field(default_factory=Weather)


class PanchangLimb(BaseModel):
    name: str
    index: int
    ends_at: datetime | None = None


class PanchangTithi(PanchangLimb):
    paksha: str


class PanchangMasa(BaseModel):
    name: str
    adhika: bool = False


class PanchangSamvat(BaseModel):
    vikram: int
    shaka: int


class PanchangSchool(BaseModel):
    is_school_day: bool
    note: str | None = None


class PanchangDay(BaseModel):
    """One day of the almanac, with the family's day folded into it."""

    date: Date
    sunrise: datetime | None = None
    sunset: datetime | None = None
    moonrise: datetime | None = None
    moonset: datetime | None = None
    vaara: str
    tithi: PanchangTithi
    nakshatra: PanchangLimb
    yoga: PanchangLimb
    karana: PanchangLimb
    masa: PanchangMasa
    samvat: PanchangSamvat
    flags: list[str] = Field(default_factory=list)
    observances: list[Observance] = Field(default_factory=list)
    school: PanchangSchool
    diet: DayDiet = Field(default_factory=DayDiet)
    meals: dict[str, str | None] = Field(default_factory=dict)


class MonthDay(BaseModel):
    """One cell of the month grid: everything it draws, nothing more."""

    date: Date
    weekday: Weekday
    tithi_short: str
    #: "Dwadashi": what the cell says in panchang mode, with the paksha's
    #: glyph beside it. The short form stays for anything that still reads it.
    tithi_name: str = ""
    paksha: str
    nakshatra: str
    masa: str
    flags: list[str] = Field(default_factory=list)
    observances: list[str] = Field(default_factory=list)
    school: PanchangSchool
    #: Kids with a school event that day — one dot each, in their colour. Not
    #: "school is open", which would dot four days in five and mean nothing.
    school_kids: list[str] = Field(default_factory=list)
    #: Kids with anything on that day, from any feed — the bar in their colour
    #: under the day number.
    kids: list[str] = Field(default_factory=list)
    #: The first observance is a holiday (purple) rather than a festival
    #: (amber), which is the colour its name and dot take.
    holiday: bool = False
    #: Something on the family's own calendars that day: the grey dot.
    family: bool = False
    non_veg_ok: bool = True
    has_meals: bool = False


class PanchangMonth(BaseModel):
    ym: str
    days: list[MonthDay] = Field(default_factory=list)


class SeriesEdit(BaseModel):
    """One parent decision from the Events tab.

    Either who sees a series, or a flip of what happens to everything nobody
    has decided about. Both in one shape because the tab sends one or the
    other and never both at once.
    """

    series: str | None = None
    kids: list[str] = Field(default_factory=list)
    default: Literal["hide", "show"] | None = None


#: The glyphs a reward may carry, drawn by the kiosk's bundled icon set. A
#: name outside this set is a content mistake rather than a blank card.
REWARD_GLYPHS = frozenset({
    "ice-cream", "cake", "cup", "meal", "dinner", "coin", "game", "star",
})


class Reward(ContentModel):
    """One thing points can be turned into."""

    id: str
    name: str
    cost: int = Field(ge=1)
    #: What approving it actually does. `manual` is a parent doing a thing in
    #: the world and ticking it off; the rest are handled by the fulfilment
    #: engine.
    fulfilment: Literal["manual", "allowance", "meal", "policy", "cash"]
    glyph: str = "star"
    #: Paid out of the family jar rather than one child's balance.
    family: bool = False
    #: A reward that exists in the file but cannot be asked for yet. It shows
    #: greyed with "Coming soon" rather than being hidden, because a child who
    #: cannot see it cannot save towards it.
    enabled: bool = True
    #: fulfilment-specific: days of allowance, minutes of screen time.
    days: int | None = Field(default=None, ge=1, le=31)
    minutes: int | None = Field(default=None, ge=1, le=600)
    #: For cash: what one of these adds to the child's savings, in dollars.
    dollars: int | None = Field(default=None, ge=1, le=1000)

    @field_validator("glyph")
    @classmethod
    def _glyph_exists(cls, value: str) -> str:
        if value not in REWARD_GLYPHS:
            raise ValueError(f"unknown glyph {value!r}; have {', '.join(sorted(REWARD_GLYPHS))}")
        return value

    @model_validator(mode="after")
    def _needs_its_own_fields(self) -> Reward:
        if self.fulfilment == "allowance" and self.days is None:
            raise ValueError(f"reward {self.id!r} is an allowance and needs days:")
        if self.fulfilment == "policy" and self.minutes is None:
            raise ValueError(f"reward {self.id!r} is a policy and needs minutes:")
        if self.fulfilment == "cash" and self.dollars is None:
            raise ValueError(f"reward {self.id!r} is cash and needs dollars:")
        return self


class Rewards(ContentModel):
    """rewards.yaml: the shop, in the order it is shown."""

    version: int = 1
    rewards: list[Reward] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> Rewards:
        seen: set[str] = set()
        for reward in self.rewards:
            if reward.id in seen:
                raise ValueError(f"duplicate reward id {reward.id!r}")
            seen.add(reward.id)
        return self

    def by_id(self, reward_id: str) -> Reward | None:
        for reward in self.rewards:
            if reward.id == reward_id:
                return reward
        return None


class LedgerRow(BaseModel):
    """One line of history, as the kiosk reads it."""

    id: int
    kid_id: str
    delta: int
    reason_kind: Literal["task", "award", "redeem", "refund", "adjust", "jar"]
    reason_ref: str | None = None
    note: str | None = None
    actor: Literal["kid", "parent"]
    created_at: str
    #: What the parent screen may do to put it right (corrections.py): undo
    #: it, or move it to the other child. Empty once it has been corrected.
    can: list[Literal["undo", "move"]] = Field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> LedgerRow:
        return cls.model_validate(row)


class SavingFor(BaseModel):
    """A reward a kid has marked, and how far along they are."""

    reward_id: str
    name: str
    glyph: str
    cost: int


class VersionInfo(BaseModel):
    """What the screens show, as one number that only goes up."""

    version: int
    changed_at: str | None = None


class PointsSummary(BaseModel):
    """What a kid's card shows: the number, the week, and the run of days."""

    kid_id: str
    balance: int
    this_week: int
    #: Earned on each day of this week, Monday first — the bars on the kid's
    #: own card. Adds up to `this_week`.
    week_days: list[int] = Field(default_factory=lambda: [0] * 7)
    streak_days: int
    #: Up to two rewards they are saving towards, in the order they chose
    #: them. A balance on its own is a number; a balance against something
    #: they want is a reason to do the washing up.
    saving_for: list[SavingFor] = Field(default_factory=list)
    #: Dollars their cash rewards are worth that a parent has not handed over
    #: yet. It only goes up by a cash reward approved, and only down by a
    #: payout recorded.
    dollars_owed: int = 0


class Payout(BaseModel):
    id: int
    kid_id: str
    dollars: int
    paid_at: str
    note: str | None = None


class Feeling(BaseModel):
    """How a day was, in one tap, at bedtime."""

    kid_id: str
    date: Date
    #: great, good, okay, meh, rough — in that order, worst last.
    feeling: Literal["great", "good", "okay", "meh", "rough"]


class Claim(BaseModel):
    """A child saying they did a thing, and waiting to be believed."""

    id: int
    kid_id: str
    task_id: str
    date: Date
    status: Literal["claimed", "approved", "declined"]
    claimed_at: str
    decided_at: str | None = None
    decided_by: str | None = None


class ClaimRequest(BaseModel):
    """What the kiosk sends when a kid taps a to-do row."""

    kid_id: str
    task_id: str
    #: Defaults to the house's today, which is the only day a kid may claim.
    date: Date | None = None


class KidPin(BaseModel):
    """Setting or clearing one kid's pad code. An empty pin clears it."""

    pin: str = ""


class PinState(BaseModel):
    """Which kids have a PIN, which is all the kiosk needs to know up front."""

    pins: dict[str, bool] = Field(default_factory=dict)


class PinResult(BaseModel):
    ok: bool


class ApprovalItem(BaseModel):
    """One row of the parent queue: a chore claimed, a reward asked for, or a
    meal a child picked that a parent has not settled."""

    kind: Literal["claim", "redemption", "meal", "treat"]
    id: int
    kid_id: str
    title: str
    points: int
    #: When it was claimed or asked for, as stored: local ISO 8601.
    when: str
    note: str | None = None
    #: For a meal: which slot, the dishes chosen and by whom, and the plan
    #: they replaced. Contested when there is more than one choice.
    date: Date | None = None
    slot: Literal["breakfast", "lunch", "dinner"] | None = None
    choices: list[MealChoice] = Field(default_factory=list)
    plan_name: str | None = None
    contested: bool = False
    #: A treat pick waiting on a parent: the picks row to approve.
    pick_id: int | None = None


class CorrectionRequest(BaseModel):
    """A wrong row put right: taken back, or moved to the other child."""

    action: Literal["undo", "move"]
    to_kid: str | None = None


class AwardRequest(BaseModel):
    """Points for something no task file will ever list — or, when the house
    has turned deductions on, taken away for something it will."""

    kid_id: str
    points: int = Field(ge=-100, le=100)
    note: str

    @field_validator("points")
    @classmethod
    def _not_nothing(cls, value: int) -> int:
        if value == 0:
            raise ValueError("an award is worth more than nothing")
        return value


class PendingCount(BaseModel):
    """How many things wait on a parent. Read by the lock screen, so it
    carries nothing about who or what."""

    pending: int


class Redemption(BaseModel):
    """A child asking to spend what they earned."""

    id: int
    kid_id: str
    reward_id: str
    points: int
    status: Literal["requested", "approved", "scheduled", "fulfilled", "declined", "refunded"]
    requested_at: str
    decided_at: str | None = None
    fulfilment_ref: str | None = None
    note: str | None = None
    #: Filled in for the kiosk from rewards.yaml, so a list of these reads
    #: without a second lookup.
    name: str = ""
    glyph: str = "star"


class RedemptionRequest(BaseModel):
    kid_id: str
    reward_id: str


class JarRequest(BaseModel):
    """Moving points from one child to the family."""

    kid_id: str
    points: int = Field(ge=1, le=1000)


class Todo(BaseModel):
    """Something approved that a parent still has to actually do.

    A reward is not finished when it is approved — the ice cream has not been
    bought and the allowance has not been handed over. These are what is left.
    """

    #: "redemption:12" or "allowance:12:2"
    ref: str
    kind: Literal["manual", "allowance", "cash"]
    kid_id: str
    title: str
    #: For an allowance, which day of how many.
    day: int | None = None
    days: int | None = None
    due: Date | None = None
    #: For cash, what to hand over: "Give Sam $5".
    dollars: int | None = None
    #: The reward a redemption to-do is for: "dinner_out" offers "Plan it".
    reward_id: str | None = None


class TodoDone(BaseModel):
    """A parent ticking off something they have now actually done."""

    ref: str


class PickOption(BaseModel):
    """One dish a kid may choose, and what stands in the way if it cannot."""

    id: str
    name: str
    treat: bool = False
    #: What it costs in points. Zero for everyday dishes, which are free.
    cost: int = 0
    #: The ways it could be cooked on that day, after the diet rules.
    proteins: list[Protein] = Field(default_factory=list)
    pickable: bool = True
    #: Said plainly, in the child's terms, when it is not pickable.
    why: str | None = None
    #: What kind of food it is. Thirty dinners scroll past the fold, and the
    #: cuisine is what gives that scroll landmarks.
    cuisine: str = ""
    #: Said, not enforced: a dinner the house had inside four days ("we had
    #: this Tuesday"). The dish is still pickable.
    warning: str | None = None
    #: The weekday of that repeat ("Tuesday"), for the kiosk to say in its own words.
    repeat_day: str | None = None
    #: From the menu this slot shares (a lunch dish offered at dinner): listed
    #: after the slot's own dishes, under one header, never mixed in.
    also: bool = False
    #: Lunch out or Dinner out: a place, not a dish. The kid picker draws it
    #: as a tile of its own above the list rather than in it.
    out: bool = False
    #: True when this is what the house ate in that slot the day before, so
    #: the picker can offer it as one tap. For dinner it never is: the
    #: four-day repeat rule has already ruled yesterday's dinner out, which
    #: is the rule working rather than a gap in this one.
    yesterday: bool = False


class PickRequest(BaseModel):
    kid_id: str
    date: Date
    slot: Literal["breakfast", "lunch", "dinner"]
    dish_id: str
    kids_protein: Protein = "veg"
    #: For Dinner out: where, if they said. Forty characters at most.
    place: str | None = Field(default=None, max_length=40)


PickStatus = Literal["proposed", "chosen", "moved", "passed"]
PickSlot = Literal["breakfast", "lunch", "dinner"]


class PickRow(BaseModel):
    """One child's choice for one meal, as stored (the picks table)."""

    id: int
    kid_id: str
    date: Date
    slot: PickSlot
    dish_id: str
    kids_protein: Protein = "veg"
    status: PickStatus
    decided_by: str | None = None
    decided_at: str | None = None
    moved_to: Date | None = None
    created_at: str
    note: str | None = None
    #: The dish's name from the catalog, filled in on the way out.
    name: str = ""
    treat: bool = False


class SlotView(BaseModel):
    """One meal as it resolves: the plan, the picks on it, and what it comes to."""

    date: Date
    slot: PickSlot
    plan: MealSlot | None = None
    picks: list[PickRow] = Field(default_factory=list)
    #: What the house is eating: the plan, a pick, or — contested — the plan
    #: still, with both children's choices on it until a parent decides.
    resolved: MealSlot | None = None
    contested: bool = False
    #: Past the time a child may change it.
    locked: bool = False
    #: A parent has decided this slot; the children cannot change it now.
    decided: bool = False


class DayPicks(BaseModel):
    date: Date
    breakfast: SlotView
    lunch: SlotView
    dinner: SlotView


class PickDecision(BaseModel):
    """A parent settling a contested slot. `alternate` gives the other child
    their dish on the next day it is free and allowed."""

    date: Date
    slot: PickSlot
    winner_kid_id: str
    mode: Literal["choose", "alternate"] = "choose"


class DecisionResult(BaseModel):
    slot: PickSlot
    winner_kid_id: str
    winner_date: Date
    #: Alternate only: where the other child's dish went.
    loser_kid_id: str | None = None
    loser_date: Date | None = None


class MealOverride(BaseModel):
    """A parent's pen on a cell: this dish, or the plan (dish_id null)."""

    date: Date
    slot: PickSlot
    dish_id: str | None = None
    #: For Lunch out or Dinner out: where, if anywhere. At most 40 characters.
    place: str | None = Field(default=None, max_length=40)


class ConfirmPick(BaseModel):
    date: Date
    slot: Literal["breakfast", "lunch", "dinner"]


class DigestKid(BaseModel):
    """One child's week, counted from the rows."""

    kid_id: str
    name: str
    earned: int
    spent: int
    #: ISO date → the chores approved that day.
    approved: dict[str, list[str]] = Field(default_factory=dict)
    redemptions: list[str] = Field(default_factory=list)
    picks: list[str] = Field(default_factory=list)
    #: ISO date → how that day felt, on the nights they said. Only here: the
    #: check-in is for the people in the house, not for the wall.
    feelings: dict[str, str] = Field(default_factory=dict)


class Digest(BaseModel):
    week: str
    start: Date
    end: Date
    kids: list[DigestKid] = Field(default_factory=list)
    #: The meals eaten out that week: "Sat dinner: Out · Taqueria Luna".
    out: list[str] = Field(default_factory=list)
