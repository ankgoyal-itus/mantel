"""Parent mode: the PIN, the lockout, and writing content files back."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from mantel_api.parent import (
    LOCKOUT_SECONDS,
    SESSION_SECONDS,
    BadPin,
    LockedOut,
    NotConfigured,
    ParentAuth,
)

PIN = "4321"
PARENT_ROUTES = (
    ("get", "/api/parent/settings"),
    ("put", "/api/parent/settings"),
    ("post", "/api/parent/refresh"),
    ("get", "/api/parent/meals"),
    ("put", "/api/parent/meals"),
)


@pytest.fixture(autouse=True)
def pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PIN)


def sign_in(client: TestClient) -> None:
    assert client.post("/api/parent/session", json={"pin": PIN}).status_code == 200


class TestTheLock:
    def test_five_wrong_pins_lock_the_pad_for_a_minute(self) -> None:
        auth = ParentAuth()
        now = 1000.0

        for remaining in (4, 3, 2, 1):
            with pytest.raises(BadPin) as wrong:
                auth.open_session("0000", "ipad", now)
            assert wrong.value.remaining == remaining

        with pytest.raises(LockedOut) as locked:
            auth.open_session("0000", "ipad", now)
        assert locked.value.retry_after == LOCKOUT_SECONDS

        # The right PIN is refused too: the lock is on the pad, not the guess.
        with pytest.raises(LockedOut):
            auth.open_session(PIN, "ipad", now + 30)

    def test_the_lock_releases_after_sixty_seconds(self) -> None:
        auth = ParentAuth()
        now = 1000.0
        for _ in range(5):
            with pytest.raises((BadPin, LockedOut)):
                auth.open_session("0000", "ipad", now)

        token = auth.open_session(PIN, "ipad", now + LOCKOUT_SECONDS + 1)
        assert auth.valid(token, now + LOCKOUT_SECONDS + 1)

    def test_one_ipad_locked_out_does_not_lock_the_other(self) -> None:
        auth = ParentAuth()
        now = 1000.0
        for _ in range(5):
            with pytest.raises((BadPin, LockedOut)):
                auth.open_session("0000", "kitchen", now)

        assert auth.open_session(PIN, "living-room", now)

    def test_a_session_expires(self) -> None:
        auth = ParentAuth()
        token = auth.open_session(PIN, "ipad", 1000.0)

        assert auth.valid(token, 1000.0 + SESSION_SECONDS - 1)
        assert not auth.valid(token, 1000.0 + SESSION_SECONDS + 1)

    def test_no_pin_configured_means_no_way_in(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MANTEL_PARENT_PIN", "")
        with pytest.raises(NotConfigured):
            ParentAuth().open_session("", "ipad", 1000.0)


class TestTheDoor:
    def test_every_parent_route_refuses_without_the_cookie(self, client: TestClient) -> None:
        for method, path in PARENT_ROUTES:
            call = getattr(client, method)
            response = call(path) if method == "get" else call(path, json={"days": []})
            assert response.status_code == 401, f"{method} {path}"

    def test_a_wrong_pin_says_how_many_tries_are_left(self, client: TestClient) -> None:
        response = client.post("/api/parent/session", json={"pin": "0000"})

        assert response.status_code == 401
        assert response.json()["detail"]["remaining"] == 4

    def test_the_lockout_comes_back_as_429_with_retry_after(self, client: TestClient) -> None:
        for _ in range(4):
            client.post("/api/parent/session", json={"pin": "0000"})
        response = client.post("/api/parent/session", json={"pin": "0000"})

        assert response.status_code == 429
        assert response.json()["detail"]["retry_after"] == LOCKOUT_SECONDS
        assert response.headers["Retry-After"] == str(LOCKOUT_SECONDS)

    def test_done_closes_the_session(self, client: TestClient) -> None:
        sign_in(client)
        assert client.get("/api/parent/settings").status_code == 200

        client.delete("/api/parent/session")
        assert client.get("/api/parent/settings").status_code == 401


class TestWritingSettings:
    def test_the_write_keeps_comments_and_untouched_keys(
        self, client: TestClient, content_dir: Path
    ) -> None:
        path = content_dir / "settings.yaml"
        original = path.read_text(encoding="utf-8")
        path.write_text("# the house rules, hand-written\n" + original, encoding="utf-8")
        sign_in(client)

        response = client.put(
            "/api/parent/settings",
            json={
                "night_start": "20:30",
                "night_end": "06:00",
                "idle_minutes": 4,
                "night_idle_minutes": 7,
                "night_frame": True,
                "slide_seconds": 25,
            },
        )
        assert response.status_code == 200

        written = path.read_text(encoding="utf-8")
        assert "# the house rules, hand-written" in written
        assert "# edited from iPad " in written

        after = yaml.safe_load(written)
        assert after["night"]["start"] == "20:30"
        assert after["night"]["frame"] is True
        assert after["idle_minutes"] == 4
        assert after["slide_seconds"] == 25
        # Everything the parent screen does not offer survives untouched.
        assert after["timezone"] == "America/Los_Angeles"
        assert after["calendars"][0]["url_env"] == "MANTEL_CAL_MIRA"
        assert after["location"]["name"] == "Half Moon Bay"

    def test_a_second_save_replaces_the_stamp_rather_than_stacking_it(
        self, client: TestClient, content_dir: Path
    ) -> None:
        sign_in(client)
        body = {
            "night_start": "21:00",
            "night_end": "06:30",
            "idle_minutes": 3,
            "night_idle_minutes": 5,
            "night_frame": False,
            "slide_seconds": 20,
        }
        client.put("/api/parent/settings", json=body)
        client.put("/api/parent/settings", json=body)

        written = (content_dir / "settings.yaml").read_text(encoding="utf-8")
        assert written.count("# edited from iPad ") == 1

    def test_an_edit_that_would_break_the_file_is_refused(
        self, client: TestClient, content_dir: Path
    ) -> None:
        sign_in(client)
        before = (content_dir / "settings.yaml").read_text(encoding="utf-8")

        response = client.put(
            "/api/parent/settings",
            json={
                "night_start": "25:00",  # not a time
                "night_end": "06:30",
                "idle_minutes": 3,
                "night_idle_minutes": 5,
                "night_frame": False,
                "slide_seconds": 20,
            },
        )

        assert response.status_code == 422
        assert (content_dir / "settings.yaml").read_text(encoding="utf-8") == before


class TestWritingMeals:
    def test_an_edit_round_trips_and_leaves_other_dates_alone(
        self, client: TestClient, content_dir: Path
    ) -> None:
        sign_in(client)

        response = client.put(
            "/api/parent/meals",
            json={
                "days": [
                    {
                        "date": "2026-09-24",
                        "breakfast": {"name": "Toast and eggs", "note": ""},
                        "lunch": {"name": "Pasta box", "note": ""},
                        "dinner": {"name": "Pizza from the freezer", "note": "easy night"},
                    }
                ]
            },
        )
        assert response.status_code == 200
        assert response.json()[0]["dinner"]["name"] == "Pizza from the freezer"

        written = yaml.safe_load((content_dir / "meals.yaml").read_text(encoding="utf-8"))
        assert written[date(2026, 9, 24)]["dinner"] == {
            "name": "Pizza from the freezer",
            "note": "easy night",
        }
        # The days either side are untouched, ids and all.
        assert written[date(2026, 9, 23)]["lunch"] == {
            "name": "Turkey wrap",
            "note": "Mira: no tomato",
        }
        assert written[date(2026, 9, 25)]["dinner"] == {
            "id": "makhani_night",
            "kids_protein": "chicken",
            "note": "two ways",
        }

    def test_saving_an_unchanged_cell_keeps_its_catalog_id(
        self, client: TestClient, content_dir: Path
    ) -> None:
        sign_in(client)
        shown = client.get("/api/parent/meals?from=2026-09-25&days=1").json()
        assert shown[0]["dinner"]["name"] == "Makhani night"

        assert client.put("/api/parent/meals", json={"days": shown}).status_code == 200

        written = yaml.safe_load((content_dir / "meals.yaml").read_text(encoding="utf-8"))
        kept = written[date(2026, 9, 25)]["dinner"]
        assert kept["id"] == "makhani_night"
        assert kept["kids_protein"] == "chicken"

    def test_clearing_a_cell_removes_the_slot(self, client: TestClient, content_dir: Path) -> None:
        sign_in(client)

        client.put(
            "/api/parent/meals",
            json={
                "days": [
                    {
                        "date": "2026-09-23",
                        "breakfast": {"name": "", "note": ""},
                        "lunch": {"name": "Turkey wrap", "note": "Mira: no tomato"},
                        "dinner": {"name": "Dal and rice", "note": ""},
                    }
                ]
            },
        )

        written = yaml.safe_load((content_dir / "meals.yaml").read_text(encoding="utf-8"))
        assert "breakfast" not in written[date(2026, 9, 23)]
        assert written[date(2026, 9, 23)]["lunch"]["name"] == "Turkey wrap"

    def test_a_new_date_can_be_planned(self, client: TestClient, content_dir: Path) -> None:
        sign_in(client)

        client.put(
            "/api/parent/meals",
            json={
                "days": [
                    {
                        "date": "2026-10-20",
                        "breakfast": {"name": "Poha", "note": ""},
                        "lunch": {"name": "", "note": ""},
                        "dinner": {"name": "Khichdi", "note": "light"},
                    }
                ]
            },
        )

        written = yaml.safe_load((content_dir / "meals.yaml").read_text(encoding="utf-8"))
        assert written[date(2026, 10, 20)] == {
            "breakfast": {"name": "Poha"},
            "dinner": {"name": "Khichdi", "note": "light"},
        }
