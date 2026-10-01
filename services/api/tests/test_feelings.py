"""The bedtime check-in, and the things it deliberately does not do."""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mantel_api import feelings
from mantel_api.content import Content
from mantel_api.db import Database

MONDAY = Date(2026, 9, 21)


@pytest.fixture
def asking(content_dir: Path, content: Content) -> None:
    """The house with the check-in turned on."""
    path = content_dir / "settings.yaml"
    path.write_text(
        f"{path.read_text(encoding='utf-8')}\nfeelings: {{enabled: true}}\n", encoding="utf-8"
    )
    content.load_all()


class TestOffByDefault:
    def test_the_setting_is_off_in_the_shipped_content(self, client: TestClient) -> None:
        assert client.get("/api/config").json()["settings"]["feelings"]["enabled"] is False

    def test_recording_one_is_refused_while_it_is_off(self, client: TestClient) -> None:
        """A screen that is not asking should not be storing."""
        sent = client.post(
            "/api/feelings",
            json={"kid_id": "mira", "date": "2026-09-21", "feeling": "good"},
        )
        assert sent.status_code == 409

    def test_reading_them_back_says_nothing_while_it_is_off(self, client: TestClient) -> None:
        assert client.get("/api/feelings").json() == {}


class TestOnceItIsOn:
    def test_a_tap_is_taken_and_read_back(self, client: TestClient, asking: None) -> None:
        sent = client.post(
            "/api/feelings",
            json={"kid_id": "mira", "date": "2026-09-21", "feeling": "good"},
        )
        assert sent.status_code == 200
        assert client.get("/api/feelings?date=2026-09-21").json() == {"mira": "good"}

    def test_a_child_who_does_not_live_here_is_a_404(
        self, client: TestClient, asking: None
    ) -> None:
        sent = client.post(
            "/api/feelings",
            json={"kid_id": "nobody", "date": "2026-09-21", "feeling": "good"},
        )
        assert sent.status_code == 404

    def test_a_face_nobody_offered_is_a_422(self, client: TestClient, asking: None) -> None:
        sent = client.post(
            "/api/feelings",
            json={"kid_id": "mira", "date": "2026-09-21", "feeling": "furious"},
        )
        assert sent.status_code == 422


class TestRecording:
    def test_one_tap_is_stored_and_read_back(self, database: Database) -> None:
        with database.write() as connection:
            feelings.record(connection, kid_id="mira", day=MONDAY, feeling="great")
        with database.connect() as connection:
            assert feelings.on(connection, kid_id="mira", day=MONDAY) == "great"

    def test_tapping_again_replaces_it_without_comment(self, database: Database) -> None:
        """A child who thinks better of "rough" can change their mind."""
        with database.write() as connection:
            feelings.record(connection, kid_id="mira", day=MONDAY, feeling="rough")
            feelings.record(connection, kid_id="mira", day=MONDAY, feeling="okay")
        with database.connect() as connection:
            assert feelings.on(connection, kid_id="mira", day=MONDAY) == "okay"

    def test_a_night_nobody_answered_is_simply_absent(self, database: Database) -> None:
        # Not "unknown", not a gap to be filled: there is no row.
        with database.connect() as connection:
            assert feelings.on(connection, kid_id="kabir", day=MONDAY) is None

    def test_a_face_nobody_offered_is_refused(self, database: Database) -> None:
        with database.write() as connection:
            with pytest.raises(ValueError):
                feelings.record(connection, kid_id="mira", day=MONDAY, feeling="furious")

    def test_the_five_faces_are_worst_last(self) -> None:
        # The order is the row's order, and it matters: a child scanning left
        # to right should not have to read every word to find "fine".
        assert feelings.FACES == ("great", "good", "okay", "meh", "rough")


class TestTheWeek:
    def test_only_the_days_inside_the_week_come_back(self, database: Database) -> None:
        with database.write() as connection:
            feelings.record(connection, kid_id="mira", day=Date(2026, 9, 20), feeling="meh")
            feelings.record(connection, kid_id="mira", day=MONDAY, feeling="good")
            feelings.record(connection, kid_id="mira", day=Date(2026, 9, 27), feeling="great")
            feelings.record(connection, kid_id="kabir", day=MONDAY, feeling="okay")

        with database.connect() as connection:
            week = feelings.between(connection, MONDAY, Date(2026, 9, 27))

        assert week["mira"] == {"2026-09-21": "good", "2026-09-27": "great"}
        assert week["kabir"] == {"2026-09-21": "okay"}

    def test_the_digest_carries_them_and_the_dashboard_does_not(
        self, client: TestClient, database: Database
    ) -> None:
        """The one screen they appear on is the one only a parent opens."""
        with database.write() as connection:
            feelings.record(connection, kid_id="mira", day=MONDAY, feeling="rough")

        today = client.get("/api/today").json()
        assert "feelings" not in today
        assert all("feeling" not in kid for kid in today["kids"])

        week = client.get("/api/digest?week=2026-W39").json()
        mira = next(kid for kid in week["kids"] if kid["kid_id"] == "mira")
        assert mira["feelings"] == {"2026-09-21": "rough"}
