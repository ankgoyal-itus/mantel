"""GET /api/health"""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from mantel_api.app import app
from mantel_api.paths import read_version

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == read_version()
    assert body["content"] == {
        "family": "ok",
        "settings": "ok",
        "schedule": "ok",
        "meals": "ok",
        "meals-catalog": "ok",
        "tasks": "ok",
        "school-events": "ok",
        "rewards": "ok",
    }

    # Nothing is fetched during tests, so both outside sources report honestly.
    assert body["weather"] == "never fetched"

    # Which feeds exist is the family's to change in settings.yaml, so health
    # is checked for reporting on exactly those, rather than on a fixed three.
    config = client.get("/api/config").json()
    declared = [feed["id"] for feed in config["settings"]["calendars"]]
    assert sorted(body["calendars"]) == sorted(declared)
    assert set(body["calendars"].values()) == {"not configured"}

    when = datetime.fromisoformat(body["time"])
    offset = when.utcoffset()
    assert offset is not None
    # Pacific: -8 in winter, -7 in summer.
    assert offset.total_seconds() in (-28800.0, -25200.0)
