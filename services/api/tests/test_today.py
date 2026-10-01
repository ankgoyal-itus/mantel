"""GET /api/today"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

TUESDAY = "2026-09-29"
TUESDAY_PIANO_SKIPPED = "2026-10-06"
TUESDAY_PIANO_MOVED = "2026-10-13"  # also a no_school date
WEDNESDAY_WITH_MEALS = "2026-09-23"
INSIDE_THANKSGIVING = "2026-11-25"
NO_SCHOOL_WEDNESDAY = "2026-11-11"


def kid(body: dict[str, Any], kid_id: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = body["kids"]
    return next(entry for entry in entries if entry["id"] == kid_id)


def test_tuesday_agenda_includes_piano(client: TestClient) -> None:
    body = client.get(f"/api/today?date={TUESDAY}").json()

    assert body["weekday"] == "tue"
    assert body["is_school_day"] is True
    assert body["school_note"] is None

    piano = kid(body, "mira")["agenda"]
    assert piano == [
        {
            "start": "16:00",
            "end": "16:45",
            "title": "Piano",
            "where": "Ms. Lee's",
            "note": "bring the blue book",
            "source": "schedule",
            "source_kind": None,
            "all_day": False,
            "calendar_id": None,
        }
    ]
    # Tuesday is not a swim day.
    assert kid(body, "kabir")["agenda"] == []


def test_tuesday_tasks_for_both_kids(client: TestClient) -> None:
    body = client.get(f"/api/today?date={TUESDAY}").json()

    assert [task["id"] for task in kid(body, "mira")["tasks"]] == ["hw", "outside"]
    assert [task["id"] for task in kid(body, "kabir")["tasks"]] == ["hw", "outside", "dishes"]


def test_skip_exception_removes_the_occurrence(client: TestClient) -> None:
    body = client.get(f"/api/today?date={TUESDAY_PIANO_SKIPPED}").json()

    assert body["weekday"] == "tue"
    assert kid(body, "mira")["agenda"] == []


def test_move_exception_moves_the_occurrence(client: TestClient) -> None:
    body = client.get(f"/api/today?date={TUESDAY_PIANO_MOVED}").json()

    agenda = kid(body, "mira")["agenda"]
    assert len(agenda) == 1
    assert agenda[0]["title"] == "Piano"
    assert agenda[0]["start"] == "17:00"
    assert agenda[0]["end"] == "17:45"
    # Everything else about the occurrence survives the move.
    assert agenda[0]["where"] == "Ms. Lee's"


def test_meals_and_family_agenda(client: TestClient) -> None:
    body = client.get(f"/api/today?date={WEDNESDAY_WITH_MEALS}").json()

    assert body["meals"]["breakfast"] == {
        "name": "Oatmeal",
        "note": None,
        "kids_protein": "veg",
        "id": None,
        # Written by a parent, so it is somebody's plan rather than a proposal.
        "picked_by": [],
        "confirmed": True,
        "plan": None,
        "picks": {},
    }
    assert body["meals"]["lunch"] == {
        "name": "Turkey wrap",
        "note": "Mira: no tomato",
        "kids_protein": "veg",
        "id": None,
        "picked_by": [],
        "confirmed": True,
        "plan": None,
        "picks": {},
    }
    assert body["meals"]["snack"] is None

    # Wednesday is a swim day, and the family item belongs to nobody's list.
    assert [item["title"] for item in kid(body, "kabir")["agenda"]] == ["Swim"]
    assert body["family_agenda"] == []


def test_saturday_family_agenda_and_tasks(client: TestClient) -> None:
    body = client.get("/api/today?date=2026-09-26").json()

    assert body["is_school_day"] is False
    assert [item["title"] for item in body["family_agenda"]] == ["Library"]
    assert [task["id"] for task in kid(body, "mira")["tasks"]] == ["outside", "room"]


def test_is_school_day_false_inside_a_break(client: TestClient) -> None:
    body = client.get(f"/api/today?date={INSIDE_THANKSGIVING}").json()

    assert body["is_school_day"] is False
    assert body["school_note"] == "Thanksgiving break"


def test_is_school_day_false_on_a_no_school_date(client: TestClient) -> None:
    body = client.get(f"/api/today?date={NO_SCHOOL_WEDNESDAY}").json()

    assert body["is_school_day"] is False
    # Derived from the district feed, which says what the day off is for.
    assert body["school_note"] == "Veterans Day"


def test_school_tasks_disappear_on_a_break_day(client: TestClient) -> None:
    body = client.get(f"/api/today?date={INSIDE_THANKSGIVING}").json()

    for kid_id in ("mira", "kabir"):
        ids = [task["id"] for task in kid(body, kid_id)["tasks"]]
        assert "hw" not in ids
        assert "outside" in ids  # daily tasks still apply


def test_defaults_to_today(client: TestClient) -> None:
    body = client.get("/api/today").json()

    assert body["date"] == client.get("/api/today").json()["date"]
    assert body["weekday"] in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
