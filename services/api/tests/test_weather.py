"""The weather service and GET /api/weather."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient

from mantel_api.models import Settings
from mantel_api.weather import WMO_CODES, WeatherService, describe

ICONS = {"clear", "partly", "cloudy", "fog", "drizzle", "rain", "snow", "storm"}


def test_wmo_codes_map_to_the_eight_icons() -> None:
    assert describe(0) == ("Clear", "clear")
    assert describe(2) == ("Partly cloudy", "partly")
    assert describe(3) == ("Overcast", "cloudy")
    assert describe(45) == ("Fog", "fog")
    assert describe(53) == ("Drizzle", "drizzle")
    assert describe(63) == ("Rain", "rain")
    assert describe(73) == ("Snow", "snow")
    assert describe(95) == ("Thunderstorm", "storm")

    # Nothing in the table invents an icon the dashboard cannot draw.
    assert {icon for _, icon in WMO_CODES.values()} <= ICONS

    # And an unknown or missing code stays readable instead of raising.
    assert describe(1234) == ("Unknown", "cloudy")
    assert describe(None) == ("Unknown", "cloudy")


def test_weather_is_empty_and_stale_before_the_first_fetch(client: TestClient) -> None:
    body = client.get("/api/weather").json()

    assert body == {"now": None, "today": None, "tomorrow": None, "stale": True, "fetched_at": None}
    assert client.get("/api/health").json()["weather"] == "never fetched"


def test_weather_after_a_successful_fetch(
    client: TestClient, weather: WeatherService, settings: Settings
) -> None:
    asyncio.run(weather.refresh(settings))
    body = client.get("/api/weather").json()

    assert body["now"] == {"temp": 68, "label": "Partly cloudy", "icon": "partly", "is_day": True}
    assert body["today"]["high"] == 79
    assert body["today"]["low"] == 56
    assert body["today"]["precip_pct"] == 10
    assert body["today"]["sunrise"] == "2026-09-29T06:59"
    assert body["today"]["icon"] == "cloudy"
    assert body["tomorrow"]["icon"] == "rain"
    assert body["stale"] is False
    assert body["fetched_at"] is not None
    assert client.get("/api/health").json()["weather"] == "ok"


def test_weather_is_embedded_in_today(
    client: TestClient, weather: WeatherService, settings: Settings
) -> None:
    asyncio.run(weather.refresh(settings))

    body = client.get("/api/today?date=2026-09-29").json()
    assert body["weather"]["now"]["temp"] == 68
    assert body["weather"]["stale"] is False


def test_a_failed_fetch_serves_the_last_good_value_as_stale(settings: Settings) -> None:
    calls = {"n": 0}

    async def fetch(_: Settings) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] > 1:
            raise TimeoutError("open-meteo did not answer")
        return {
            "current": {"temperature_2m": 61.2, "weather_code": 0, "is_day": 0},
            "daily": {
                "temperature_2m_max": [70.0],
                "temperature_2m_min": [50.0],
                "weather_code": [0],
                "precipitation_probability_max": [0],
                "sunrise": ["2026-09-29T06:59"],
                "sunset": ["2026-09-29T18:55"],
            },
        }

    service = WeatherService(fetch=fetch)
    first = asyncio.run(service.refresh(settings))
    assert first.now is not None
    assert first.stale is False

    second = asyncio.run(service.refresh(settings, force=True))

    # Same reading as before, now flagged as old rather than thrown away.
    assert second.now is not None
    assert second.now.temp == 61
    assert second.stale is True
    assert second.fetched_at == first.fetched_at
    assert service.status.startswith("error:")


def test_the_cache_holds_for_its_ttl(settings: Settings) -> None:
    calls = {"n": 0}

    async def fetch(_: Settings) -> dict[str, Any]:
        calls["n"] += 1
        return {"current": {"temperature_2m": 60.0, "weather_code": 0, "is_day": 1}}

    service = WeatherService(fetch=fetch)
    asyncio.run(service.refresh(settings))
    asyncio.run(service.refresh(settings))
    asyncio.run(service.refresh(settings))

    assert calls["n"] == 1
