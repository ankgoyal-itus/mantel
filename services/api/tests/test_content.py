"""Loading, validating and reloading content/."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mantel_api.content import Content

BREAKFAST_DAY = "2026-09-23"
TUESDAY = "2026-09-29"


def breakfast(client: TestClient) -> str | None:
    meal = client.get(f"/api/today?date={BREAKFAST_DAY}").json()["meals"]["breakfast"]
    return None if meal is None else str(meal["name"])


def test_an_edit_is_picked_up_on_reload(
    client: TestClient, content: Content, content_dir: Path
) -> None:
    assert breakfast(client) == "Oatmeal"

    (content_dir / "meals.yaml").write_text(f"{BREAKFAST_DAY}:\n  breakfast: Idli\n")
    content.load_all()

    assert breakfast(client) == "Idli"


def test_broken_meals_keeps_the_last_good_version(
    client: TestClient, content: Content, content_dir: Path
) -> None:
    assert breakfast(client) == "Oatmeal"

    (content_dir / "meals.yaml").write_text(f"{BREAKFAST_DAY}:\n  breakfast: [unclosed\n")
    content.load_all()

    # The kiosk still gets a meal, and health explains why it may be stale.
    assert breakfast(client) == "Oatmeal"
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["content"]["meals"].startswith("error:")
    assert health["content"]["family"] == "ok"

    # And it recovers once the file is fixed.
    (content_dir / "meals.yaml").write_text(f"{BREAKFAST_DAY}:\n  breakfast: Idli\n")
    content.load_all()
    assert client.get("/api/health").json()["content"]["meals"] == "ok"
    assert breakfast(client) == "Idli"


def test_unknown_kid_in_schedule_fails_validation(
    client: TestClient, content: Content, content_dir: Path
) -> None:
    (content_dir / "schedule.yaml").write_text(
        'items:\n  - {kid: bobby, title: Chess, days: [tue], start: "15:00", end: "16:00"}\n'
    )
    content.load_all()

    assert content.schedule.status.startswith("error:")
    assert "bobby" in content.schedule.status

    # The last good schedule keeps serving, so Piano survives a bad edit.
    body = client.get(f"/api/today?date={TUESDAY}").json()
    mira = next(entry for entry in body["kids"] if entry["id"] == "mira")
    assert [item["title"] for item in mira["agenda"]] == ["Piano"]


def test_unknown_kid_in_tasks_fails_validation(content: Content, content_dir: Path) -> None:
    (content_dir / "tasks.yaml").write_text(
        "bobby:\n  weekdays:\n    - {id: hw, title: Homework}\n"
    )
    content.load_all()

    assert content.tasks.status.startswith("error:")
    assert "bobby" in content.tasks.status


def test_family_is_a_valid_schedule_owner(content: Content) -> None:
    schedule = content.schedule.current
    assert schedule is not None
    assert [item.title for item in schedule.items if item.kid == "family"] == ["Library"]
