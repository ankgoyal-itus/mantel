"""What the rebuilt parent screen asks of the API: every setting round-trips
through one PUT, the session stretches for a parent still working, and the
About section tells the truth without telling secrets."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from mantel_api.parent import SESSION_SECONDS, ParentAuth

PIN = "4321"


@pytest.fixture(autouse=True)
def pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PIN)


def sign_in(client: TestClient) -> None:
    assert client.post("/api/parent/session", json={"pin": PIN}).status_code == 200


class TestSettings:
    def test_everything_the_screen_shows_comes_back_from_one_get(
        self, client: TestClient
    ) -> None:
        sign_in(client)
        body = client.get("/api/parent/settings").json()
        assert body["refresh_minutes"] >= 1
        assert set(body["diet"]) == {"non_veg_days", "festivals", "extra_dates", "groups"}
        assert body["points"]["deductions"] is False
        assert [kid["id"] for kid in body["kids"]] == ["mira", "kabir"]

    def test_a_change_round_trips_through_put(
        self, client: TestClient, content_dir: Path
    ) -> None:
        sign_in(client)
        body = client.get("/api/parent/settings").json()
        body["idle_minutes"] = 9
        body["refresh_minutes"] = 20
        body["diet"]["non_veg_days"] = ["tue", "sat"]
        body["points"]["deductions"] = True
        body["points"]["streak_days"] = 5
        body["kids"][1]["name"] = "Nainu"
        body["kids"][1]["color"] = "#e0457b"
        # The frame's chip: on by default, and now off and large.
        assert (body["frame_chip"], body["frame_chip_size"]) == (True, "regular")
        body["frame_chip"] = False
        body["frame_chip_size"] = "large"

        saved = client.put("/api/parent/settings", json=body)
        assert saved.status_code == 200
        again = client.get("/api/parent/settings").json()
        assert again["idle_minutes"] == 9
        assert again["refresh_minutes"] == 20
        assert again["diet"]["non_veg_days"] == ["tue", "sat"]
        assert again["points"]["deductions"] is True
        assert again["points"]["streak_days"] == 5
        assert again["kids"][1]["name"] == "Nainu"
        assert again["kids"][1]["color"] == "#E0457B"
        assert (again["frame_chip"], again["frame_chip_size"]) == (False, "large")
        assert client.get("/api/config").json()["settings"]["frame"] == {
            "chip": False,
            "size": "large",
        }

        family = yaml.safe_load((content_dir / "family.yaml").read_text(encoding="utf-8"))
        assert family["kids"][1]["name"] == "Nainu"
        # The parents are nobody's form field.
        assert [one["id"] for one in family["parents"]] == ["dad", "mom"]

    def test_a_bad_write_is_refused_and_the_old_value_stays(
        self, client: TestClient
    ) -> None:
        sign_in(client)
        body = client.get("/api/parent/settings").json()
        body["kids"][0]["avatar"] = "unicorn-that-does-not-exist"
        refused = client.put("/api/parent/settings", json=body)
        assert refused.status_code == 422
        assert "family.yaml" in refused.json()["detail"]
        assert client.get("/api/parent/settings").json()["kids"][0]["avatar"] == "fox"


class TestTheSession:
    def test_a_parent_working_in_the_last_minute_gets_another_ten(self) -> None:
        auth = ParentAuth()
        token = auth.open_session(PIN, "ipad", 1000.0)
        # Early on, nothing changes.
        assert auth.extend(token, 1100.0) is False
        # Inside the last minute, a full session again.
        last = 1000.0 + SESSION_SECONDS - 30
        assert auth.extend(token, last) is True
        assert auth.remaining(token, last) == SESSION_SECONDS

    def test_the_session_reports_what_is_left(self, client: TestClient) -> None:
        sign_in(client)
        left = client.get("/api/parent/session").json()["expires_in"]
        assert SESSION_SECONDS - 5 <= left <= SESSION_SECONDS


class TestDeductions:
    def test_off_by_default(self, client: TestClient) -> None:
        sign_in(client)
        taken = client.post(
            "/api/parent/awards", json={"kid_id": "mira", "points": -5, "note": "shouted"}
        )
        assert taken.status_code == 403

    def test_on_they_take_points_but_never_below_zero(self, client: TestClient) -> None:
        sign_in(client)
        body = client.get("/api/parent/settings").json()
        body["points"]["deductions"] = True
        client.put("/api/parent/settings", json=body)

        client.post("/api/parent/awards", json={"kid_id": "mira", "points": 10, "note": "kind"})
        taken = client.post(
            "/api/parent/awards", json={"kid_id": "mira", "points": -4, "note": "shouted"}
        )
        assert taken.status_code == 200
        assert taken.json()["balance"] == 6
        too_far = client.post(
            "/api/parent/awards", json={"kid_id": "mira", "points": -20, "note": "again"}
        )
        assert too_far.status_code == 409


class TestAbout:
    def test_says_whether_the_token_is_set_and_never_what_it_is(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MANTEL_UPLOAD_TOKEN", "sekrit-token-value")
        sign_in(client)
        about = client.get("/api/parent/about")
        assert about.status_code == 200
        assert about.json()["upload_token"] is True
        assert "sekrit" not in about.text
        assert about.json()["lan_url"].startswith("http://")
        assert about.json()["launchd"]

    def test_a_kid_calendar_with_no_url_says_where_it_goes(self, client: TestClient) -> None:
        sign_in(client)
        rows = {row["id"]: row for row in client.get("/api/parent/calendars").json()}
        assert rows["kabir"]["state"] == "not_configured"
        assert rows["kabir"]["env"] == "MANTEL_CAL_KABIR"
        # A public feed never shows a URL here either.
        assert "example.test" not in client.get("/api/parent/calendars").text

    def test_reload_both_ipads_is_a_flag_in_health(self, client: TestClient) -> None:
        assert client.get("/api/health").json()["reload_at"] is None
        sign_in(client)
        client.post("/api/parent/reload")
        assert client.get("/api/health").json()["reload_at"]

    def test_new_routes_need_the_cookie(self, client: TestClient) -> None:
        decision = {"date": "2026-10-08", "slot": "dinner", "dish_id": None}
        calls = (
            client.get("/api/parent/about"),
            client.get("/api/parent/calendars"),
            client.post("/api/parent/reload"),
            client.post("/api/parent/picks/decide", json=decision),
            client.get(
                "/api/parent/meals/options", params={"slot": "dinner", "date": "2026-10-08"}
            ),
        )
        assert [call.status_code for call in calls] == [401] * len(calls)


def test_a_diet_toggle_keeps_the_festival_comments(client: TestClient, content_dir: Path) -> None:
    """The file's own notes live on the festival entries; a toggle elsewhere
    in the diet block must not rewrite them away."""
    path = content_dir / "settings.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc.setdefault("diet", {})["no_non_veg_festivals"] = [{"match": "navratri", "span_days": 10}]
    body = yaml.safe_dump(doc, sort_keys=False).replace(
        "- match: navratri", "- match: navratri  # Navratri through Dussehra"
    )
    path.write_text(body, encoding="utf-8")
    client.app.state.content.load_all()  # type: ignore[attr-defined]

    sign_in(client)
    settings = client.get("/api/parent/settings").json()
    settings["diet"]["non_veg_days"] = ["mon"]
    assert client.put("/api/parent/settings", json=settings).status_code == 200
    assert "# Navratri through Dussehra" in path.read_text(encoding="utf-8")


def test_the_diet_card_gets_one_row_per_festival(client: TestClient, content_dir: Path) -> None:
    """Aliases are for matching the feeds; a parent reads each festival once."""
    path = content_dir / "settings.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc.setdefault("diet", {})["no_non_veg_festivals"] = [
        {"match": "navaratri", "span_days": 10},
        {"match": "navratri", "span_days": 10},
        {"match": "karwa chauth", "span_days": 1},
        {"match": "karaka chaturthi", "span_days": 1},
        {"match": "dussehra", "span_days": 1},
    ]
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    client.app.state.content.load_all()  # type: ignore[attr-defined]

    sign_in(client)
    groups = client.get("/api/parent/settings").json()["diet"]["groups"]
    assert [group["name"] for group in groups] == ["Navratri", "Karwa Chauth", "Dussehra"]
    assert groups[0]["matches"] == ["navaratri", "navratri"]
    assert groups[0]["span_days"] == 10


def test_a_save_keeps_the_file_looking_like_the_file(
    client: TestClient, content_dir: Path
) -> None:
    """What the first save from the iPad did to settings.yaml: every list
    re-indented, the comment after non_veg_days gone, the file made 0600."""
    path = content_dir / "settings.yaml"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "non_veg_days: [mon, thu, fri, sun]",
        "non_veg_days: [mon, thu, fri, sun]\n  # Matched as a substring of an observance name.",
    )
    path.write_text(text, encoding="utf-8")
    path.chmod(0o644)
    client.app.state.content.load_all()  # type: ignore[attr-defined]

    sign_in(client)
    body = client.get("/api/parent/settings").json()
    body["diet"]["non_veg_days"] = ["mon", "wed", "sat"]
    assert client.put("/api/parent/settings", json=body).status_code == 200

    after = path.read_text(encoding="utf-8")
    assert "non_veg_days: [mon, wed, sat]" in after
    assert "# Matched as a substring of an observance name." in after
    assert "\n  - {id: mira" in after  # the calendars list, still two in
    assert path.stat().st_mode & 0o777 == 0o644
