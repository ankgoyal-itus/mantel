"""Response shapes, written to services/api/schema/ so drift shows in diffs.

apps/kiosk/src/api/types.ts mirrors these by hand. When one of these files
changes in a commit, that mirror needs the same change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from mantel_api.models import Config, Day, Weather

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"


def write(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    SCHEMA_DIR.mkdir(exist_ok=True)
    path = SCHEMA_DIR / f"{name}.json"
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return schema


def test_schemas_are_written() -> None:
    today = write("today", Day.model_json_schema())
    agenda = write("agenda", TypeAdapter(list[Day]).json_schema())
    weather = write("weather", Weather.model_json_schema())
    config = write("config", Config.model_json_schema())

    # A rename on this side should fail here as well as show up in the diff.
    assert set(today["properties"]) == {
        "date",
        "weekday",
        "is_school_day",
        "school_note",
        "kids",
        "family_agenda",
        "meals",
        "observances",
        "diet",
        "weather",
    }
    assert agenda["type"] == "array"
    assert set(weather["properties"]) == {"now", "today", "tomorrow", "stale", "fetched_at"}
    assert set(config["properties"]) == {"family", "settings"}

    for name in ("today", "agenda", "weather", "config"):
        assert (SCHEMA_DIR / f"{name}.json").exists()
