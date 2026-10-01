"""A complete content/ directory, written to a temp path for each test."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date as Date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from mantel_api.app import create_app
from mantel_api.calendars import CalendarService, expand
from mantel_api.content import Content
from mantel_api.db import Database
from mantel_api.diet import DietService
from mantel_api.models import Settings
from mantel_api.photos import PhotoStore
from mantel_api.school import SchoolService
from mantel_api.weather import WeatherService

FAMILY = """
kids:
  - {id: mira, name: Mira, color: "#1F8A8A", avatar: fox}
  - {id: kabir, name: Kabir, color: "#D97706", avatar: panda}
parents:
  - {id: dad, name: Dad}
  - {id: mom, name: Mum}
"""

SETTINGS = """
timezone: America/Los_Angeles
location: {name: Half Moon Bay, lat: 37.4636, lon: -122.4286}
units: {temp: F}
night: {start: "21:00", end: "06:30", idle_minutes: 10, frame: false}
idle_minutes: 3
slide_seconds: 20
refresh_minutes: 5
daily_reload: "04:00"
panchang: {masa_scheme: purnimanta, show_yoga_karana: false}
calendars:
  - {id: mira,  kind: kid,      kid: mira,  url_env: MANTEL_CAL_MIRA}
  - {id: kabir,  kind: kid,      kid: kabir,  url_env: MANTEL_CAL_KABIR}
  - {id: family, kind: family,   kid: family, url_env: MANTEL_CAL_FAMILY}
  - {id: usa,    kind: holiday,  url: "https://example.test/usa.ics"}
  - {id: india,  kind: festival, url: "https://example.test/india.ics"}
  - {id: district, kind: school,   kid: family, url: "https://example.test/district.ics"}
diet:
  vegetarian: [dad, mom]
  non_veg_ok: [mira, kabir]
  non_veg_days: [mon, thu, fri, sun]
  no_non_veg_festivals:
    - {match: navratri, span_days: 10}
    - {match: diwali, span_days: 4}
"""

SCHEDULE = """
items:
  - kid: mira
    title: Piano
    days: [tue]
    start: "16:00"
    end: "16:45"
    where: "Ms. Lee's"
    note: "bring the blue book"
  - kid: kabir
    title: Swim
    days: [mon, wed]
    start: "17:00"
    end: "18:00"
    where: "Aquatic center"
  - {kid: family, title: Library, days: [sat], start: "10:30", end: "11:30"}
exceptions:
  - {date: 2026-10-06, title: Piano, action: skip}
  - {date: 2026-10-13, title: Piano, action: move, start: "17:00", end: "17:45"}
"""

CATALOG = """
version: 1
dishes:
  - id: kanda_poha
    name: Kanda poha
    slot: breakfast
    protein: [veg]
    cuisine: indian
    minutes: 15
  - id: dal_rice
    name: Dal and jeera rice
    slot: lunch
    protein: [veg]
    cuisine: indian
    minutes: 30
    lunchbox: true
  - id: makhani_night
    name: Makhani night
    slot: dinner
    protein: [veg, chicken]
    cuisine: indian
    minutes: 50
"""

MEALS = """
2026-09-23:
  breakfast: Oatmeal
  lunch: {name: Turkey wrap, note: "Mira: no tomato"}
  dinner: Dal and rice
2026-09-24:
  breakfast: Toast and eggs
  lunch: Pasta box
  dinner: Tacos
2026-09-25:
  breakfast: {id: kanda_poha}
  lunch: {id: dal_rice, note: lunchbox}
  dinner: {id: makhani_night, kids_protein: chicken, note: two ways}
"""

TASKS = """
mira:
  weekdays:
    - {id: hw, title: Homework, points: 10}
    - {id: outside, title: 30 min outside, points: 10}
  weekend:
    - {id: outside, title: 30 min outside, points: 10}
    - {id: room, title: Tidy room, points: 5, every: week}
kabir:
  weekdays:
    - {id: hw, title: Homework, points: 10}
    - {id: outside, title: 30 min outside, points: 10}
    - {id: dishes, title: Load the dishwasher, points: 5}
  weekend:
    - {id: outside, title: 30 min outside, points: 10}
"""

REWARDS = """
version: 1
rewards:
  - {id: ice_cream, name: Ice cream, cost: 30, fulfilment: manual, glyph: ice-cream}
  - {id: meal_pick, name: Pick breakfast or lunch, cost: 15, fulfilment: meal, glyph: meal}
  - {id: dinner_out, name: Dinner out, cost: 150, fulfilment: manual, glyph: dinner, family: true}
  - id: allowance_5
    name: Allowance x 5 days
    cost: 100
    fulfilment: allowance
    glyph: coin
    days: 5
  - id: roblox_1h
    name: Roblox +1 h
    cost: 50
    fulfilment: policy
    glyph: game
    minutes: 60
    enabled: false
"""

SCHOOL_EVENTS = """
always:
  - {match: "no school|holiday|break|teacher work day"}
  - {match: "minimum day|early release"}
rules:
  - {match: cross country, kids: [mira]}
  - {match: girls volleyball, kids: []}
default: hide
"""

FILES = {
    "family.yaml": FAMILY,
    "settings.yaml": SETTINGS,
    "schedule.yaml": SCHEDULE,
    "meals.yaml": MEALS,
    "meals-catalog.yaml": CATALOG,
    "tasks.yaml": TASKS,
    "school-events.yaml": SCHOOL_EVENTS,
    "rewards.yaml": REWARDS,
}


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    for name, text in FILES.items():
        (tmp_path / name).write_text(text.lstrip(), encoding="utf-8")
    return tmp_path


@pytest.fixture
def content(content_dir: Path) -> Content:
    store = Content(content_dir)
    store.load_all()
    return store



MIRA_ICS_URL = "https://example.test/mira.ics"
SAMPLE_ICS = (Path(__file__).parent / "fixtures" / "sample.ics").read_text(encoding="utf-8")

#: One Open-Meteo response, trimmed to the fields the service reads.
OPEN_METEO = {
    "current": {"temperature_2m": 68.4, "weather_code": 2, "is_day": 1},
    "daily": {
        "temperature_2m_max": [79.1, 88.6, 84.0],
        "temperature_2m_min": [55.9, 51.2, 53.4],
        "weather_code": [3, 61, 0],
        "precipitation_probability_max": [10, 65, 0],
        "sunrise": ["2026-09-29T06:59", "2026-09-30T07:00", "2026-10-01T07:01"],
        "sunset": ["2026-09-29T18:55", "2026-09-30T18:53", "2026-10-01T18:52"],
    },
}


@pytest.fixture
def settings(content: Content) -> Settings:
    current = content.settings.current
    assert current is not None
    return current


@pytest.fixture
def weather() -> WeatherService:
    """A weather service that never touches the network."""

    async def fetch(_: Settings) -> dict[str, Any]:
        return OPEN_METEO

    return WeatherService(fetch=fetch)


@pytest.fixture
def calendars() -> CalendarService:
    """Mira's feed is configured and serves the fixture; the others are not."""

    empty = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//test//EN\nEND:VCALENDAR\n"

    async def fetch(url: str) -> str:
        if url == MIRA_ICS_URL:
            return SAMPLE_ICS
        if url == "https://example.test/district.ics":
            return DISTRICT_ICS
        # The public holiday and festival feeds: present, and quiet.
        return empty

    return CalendarService(fetch=fetch, env={"MANTEL_CAL_MIRA": MIRA_ICS_URL})


#: A district feed with the days the day-building tests lean on. School days
#: are derived from this, exactly as they are from a real district feed.
DISTRICT_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:d1
SUMMARY:First Day of School
DTSTART;VALUE=DATE:20260819
DTEND;VALUE=DATE:20260820
END:VEVENT
BEGIN:VEVENT
UID:d2
SUMMARY:No School (Teacher Work Day)
DTSTART;VALUE=DATE:20261013
DTEND;VALUE=DATE:20261014
END:VEVENT
BEGIN:VEVENT
UID:d3
SUMMARY:No School and District Office Closed - Veterans Day
DTSTART;VALUE=DATE:20261111
DTEND;VALUE=DATE:20261112
END:VEVENT
BEGIN:VEVENT
UID:d4
SUMMARY:No School - Thanksgiving break
DTSTART;VALUE=DATE:20261123
DTEND;VALUE=DATE:20261128
END:VEVENT
BEGIN:VEVENT
UID:d5
SUMMARY:No School - Winter break
DTSTART;VALUE=DATE:20261221
DTEND;VALUE=DATE:20270103
END:VEVENT
BEGIN:VEVENT
UID:d6
SUMMARY:Last Day of School
DTSTART;VALUE=DATE:20270603
DTEND;VALUE=DATE:20270604
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture
def school(tmp_path: Path, settings: Settings) -> SchoolService:
    """The school year, derived from the district fixture into a temp cache."""
    service = SchoolService(tmp_path / "school-year.json")
    feed = next(feed for feed in settings.calendars if feed.kind == "school")
    zone = ZoneInfo(settings.timezone)
    events = expand(DISTRICT_ICS, feed, Date(2026, 8, 1), Date(2027, 7, 31), zone)
    service.update(events, [feed.id])
    return service


@pytest.fixture
def diet(tmp_path: Path) -> DietService:
    """Empty by default: a test that cares seeds it itself."""
    return DietService(tmp_path / "diet-days.json")


@pytest.fixture
def photos(tmp_path: Path) -> PhotoStore:
    return PhotoStore(tmp_path / "photos")


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    """A real file rather than :memory:, so the backup tests have something
    to copy and the append-only triggers are exercised as they ship."""
    books = Database(tmp_path / "mantel.db")
    try:
        yield books
    finally:
        books.close()


@pytest.fixture
def client(
    content: Content,
    weather: WeatherService,
    calendars: CalendarService,
    photos: PhotoStore,
    school: SchoolService,
    diet: DietService,
    database: Database,
) -> TestClient:
    return TestClient(create_app(content, weather, calendars, photos, school, diet, database))
