"""Open-Meteo, fetched on a timer and cached.

Requests only ever read the cache, so weather can never slow down or fail
/api/today. A failed fetch leaves the last good value in place, marked stale.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .models import Settings, Weather, WeatherDay, WeatherNow

logger = logging.getLogger("mantel_api.weather")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 5.0
CACHE_MINUTES = 15

CURRENT_FIELDS = "temperature_2m,weather_code,is_day"
DAILY_FIELDS = (
    "temperature_2m_max,temperature_2m_min,weather_code,"
    "precipitation_probability_max,sunrise,sunset"
)
FORECAST_DAYS = 3

#: WMO weather codes, collapsed to the eight icons the dashboard draws.
WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear", "clear"),
    1: ("Mainly clear", "clear"),
    2: ("Partly cloudy", "partly"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Drizzle", "drizzle"),
    55: ("Heavy drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"),
    57: ("Freezing drizzle", "drizzle"),
    61: ("Light rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"),
    67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Light showers", "rain"),
    81: ("Showers", "rain"),
    82: ("Heavy showers", "rain"),
    85: ("Snow showers", "snow"),
    86: ("Snow showers", "snow"),
    95: ("Thunderstorm", "storm"),
    96: ("Thunderstorm with hail", "storm"),
    99: ("Thunderstorm with hail", "storm"),
}
UNKNOWN_CODE = ("Unknown", "cloudy")

WeatherFetch = Callable[[Settings], Awaitable[dict[str, Any]]]


def describe(code: Any) -> tuple[str, str]:
    """A WMO code as (label, icon key). Anything unrecognised stays readable."""
    try:
        return WMO_CODES.get(int(code), UNKNOWN_CODE)
    except (TypeError, ValueError):
        return UNKNOWN_CODE


async def fetch_open_meteo(settings: Settings) -> dict[str, Any]:
    params: dict[str, str | float | int] = {
        "latitude": settings.location.lat,
        "longitude": settings.location.lon,
        "timezone": settings.timezone,
        "temperature_unit": "fahrenheit" if settings.units.temp == "F" else "celsius",
        "current": CURRENT_FIELDS,
        "daily": DAILY_FIELDS,
        "forecast_days": FORECAST_DAYS,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.get(OPEN_METEO_URL, params=params)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return payload


async def fetch_demo(settings: Settings) -> dict[str, Any]:
    """The demo's forecast: a mild few days, dated from today in the house's
    timezone, in the shape Open-Meteo sends. Used when MANTEL_DEMO=1, so
    `make demo` shows weather with no network and no request to anyone."""
    today = datetime.now(_zone(settings.timezone)).date()
    days = [today + timedelta(days=offset) for offset in range(FORECAST_DAYS)]
    return {
        "current": {"temperature_2m": 64, "weather_code": 2, "is_day": 1},
        "daily": {
            "time": [day.isoformat() for day in days],
            "weather_code": [2, 3, 61][:FORECAST_DAYS],
            "temperature_2m_max": [68, 66, 61][:FORECAST_DAYS],
            "temperature_2m_min": [54, 53, 52][:FORECAST_DAYS],
            "precipitation_probability_max": [10, 20, 60][:FORECAST_DAYS],
            "sunrise": [f"{day.isoformat()}T07:02" for day in days],
            "sunset": [f"{day.isoformat()}T18:51" for day in days],
        },
    }


def _now_block(payload: dict[str, Any]) -> WeatherNow | None:
    current = payload.get("current")
    if not isinstance(current, dict):
        return None
    label, icon = describe(current.get("weather_code"))
    return WeatherNow(
        temp=round(float(current["temperature_2m"])),
        label=label,
        icon=icon,
        is_day=bool(current.get("is_day", 1)),
    )


def _day_block(payload: dict[str, Any], index: int) -> WeatherDay | None:
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        return None
    try:
        label, icon = describe(daily["weather_code"][index])
        precip = daily.get("precipitation_probability_max", [])
        return WeatherDay(
            high=round(float(daily["temperature_2m_max"][index])),
            low=round(float(daily["temperature_2m_min"][index])),
            precip_pct=_as_int(precip[index]) if index < len(precip) else None,
            sunrise=str(daily["sunrise"][index]),
            sunset=str(daily["sunset"][index]),
            label=label,
            icon=icon,
        )
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class WeatherService:
    """Holds the last good forecast. `fetch` is injectable so tests stay offline."""

    def __init__(self, fetch: WeatherFetch | None = None, ttl_minutes: int = CACHE_MINUTES) -> None:
        self._fetch = fetch if fetch is not None else fetch_open_meteo
        self._ttl = timedelta(minutes=ttl_minutes)
        self._weather = Weather()
        self._fetched_at: datetime | None = None
        self._error: str | None = None

    @property
    def current(self) -> Weather:
        return self._weather

    @property
    def status(self) -> str:
        if self._error is not None:
            return f"error: {self._error}"
        if self._fetched_at is None:
            return "never fetched"
        return "ok"

    def is_fresh(self, now: datetime) -> bool:
        return self._fetched_at is not None and now - self._fetched_at < self._ttl

    async def refresh(self, settings: Settings, *, force: bool = False) -> Weather:
        """Fetch unless the cache is still warm. Never raises into a request."""
        zone = _zone(settings.timezone)
        now = datetime.now(zone)
        if not force and self.is_fresh(now):
            return self._weather
        try:
            payload = await self._fetch(settings)
            today = _day_block(payload, 0)
            tomorrow = _day_block(payload, 1)
            current = _now_block(payload)
        except Exception as exc:  # noqa: BLE001 - weather must never break a request
            self._error = f"{type(exc).__name__}: {exc}".strip()
            logger.warning("weather fetch failed, serving last good value: %s", self._error)
            self._weather = self._weather.model_copy(update={"stale": True})
            return self._weather
        self._fetched_at = now
        self._error = None
        self._weather = Weather(
            now=current,
            today=today,
            tomorrow=tomorrow,
            stale=False,
            fetched_at=now.isoformat(),
        )
        return self._weather


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - a bad timezone must not break the fetch
        return ZoneInfo("America/Los_Angeles")
