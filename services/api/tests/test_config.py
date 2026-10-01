"""GET /api/config"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient


def test_config(client: TestClient) -> None:
    response = client.get("/api/config")
    assert response.status_code == 200

    body = response.json()
    assert [kid["id"] for kid in body["family"]["kids"]] == ["mira", "kabir"]
    assert [kid["name"] for kid in body["family"]["kids"]] == ["Mira", "Kabir"]
    assert [parent["id"] for parent in body["family"]["parents"]] == ["dad", "mom"]
    assert [parent["name"] for parent in body["family"]["parents"]] == ["Dad", "Mum"]

    settings = body["settings"]
    assert settings["timezone"] == "America/Los_Angeles"
    assert settings["location"]["name"] == "Half Moon Bay"
    assert settings["units"]["temp"] == "F"
    # The window itself is the family's to change, so this checks the shape
    # rather than the hour: a night that starts at 21:00 or at 22:00 is not a
    # broken API, and a test that says otherwise fails the day someone edits
    # settings.yaml.
    assert re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", settings["night"]["start"])
    assert re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", settings["night"]["end"])
    assert settings["night"]["start"] != settings["night"]["end"]
    assert settings["slide_seconds"] > 0

    # No secret ever reaches the kiosk.
    assert not any("pin" in key.lower() or "token" in key.lower() for key in settings)
