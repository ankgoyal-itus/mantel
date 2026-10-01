"""Two lists a kid, and the tasks done once a week."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from mantel_api import approvals, claims, streaks
from mantel_api.db import Database
from mantel_api.models import Points, Tasks
from mantel_api.today import tasks_for, uses_weekend

TZ = ZoneInfo("America/Los_Angeles")

TASKS = Tasks.model_validate(
    {
        "mira": {
            "weekdays": [
                {"id": "shw", "title": "School Homework", "points": 2},
                {"id": "math", "title": "Math homework", "points": 5, "every": "week"},
            ],
            "weekend": [
                {"id": "draw", "title": "Make a sketch", "points": 5},
                {"id": "room", "title": "Tidy room", "points": 5, "every": "week"},
            ],
        }
    }
)

MONDAY = Date(2026, 9, 21)
TUESDAY = MONDAY + timedelta(days=1)
THURSDAY = MONDAY + timedelta(days=3)
SATURDAY = MONDAY + timedelta(days=5)
NEXT_MONDAY = MONDAY + timedelta(days=7)


def at(day: Date) -> datetime:
    return datetime(day.year, day.month, day.day, 17, 0, tzinfo=TZ)


def school(day: Date) -> bool:
    return day.weekday() < 5


def claim(database: Database, task_id: str, day: Date) -> int:
    with database.write() as connection:
        return claims.claim(
            connection, TASKS, kid_id="mira", task_id=task_id, day=day, now=at(day)
        ).id


def approve(database: Database, claim_id: int, day: Date) -> None:
    with database.write() as connection:
        approvals.approve_claim(
            connection, TASKS, Points(), claim_id=claim_id, decided_by="parent", now=at(day)
        )


def status(database: Database, day: Date) -> dict[str, str]:
    with database.connect() as connection:
        return claims.status_on(connection, "mira", day, {"math", "room"})


class TestTheTwoLists:
    def test_a_school_day_uses_the_weekday_list(self) -> None:
        ids = [task.id for task in tasks_for(TASKS, "mira", TUESDAY, True)]
        assert ids == ["shw", "math"]

    def test_a_weekend_uses_the_weekend_list(self) -> None:
        ids = [task.id for task in tasks_for(TASKS, "mira", SATURDAY, False)]
        assert ids == ["draw", "room"]

    def test_a_weekday_without_school_is_a_weekend(self) -> None:
        """A holiday is a day off, whatever the calendar calls it."""
        assert uses_weekend(TUESDAY, school_day=False)
        ids = [task.id for task in tasks_for(TASKS, "mira", TUESDAY, False)]
        assert ids == ["draw", "room"]

    def test_the_cadence_travels_to_the_kiosk(self) -> None:
        weekly = next(t for t in tasks_for(TASKS, "mira", TUESDAY, True) if t.id == "math")
        assert weekly.every == "week"


class TestOnceAWeek:
    def test_it_is_claimed_once_and_paid_once(self, database: Database) -> None:
        approve(database, claim(database, "math", TUESDAY), TUESDAY)
        with pytest.raises(claims.ClaimError) as refused:
            claim(database, "math", THURSDAY)
        assert refused.value.status == 409
        with database.connect() as connection:
            paid = connection.execute(
                "SELECT COUNT(*) AS n FROM ledger WHERE reason_kind = 'task'"
            ).fetchone()["n"]
        assert paid == 1

    def test_it_shows_done_for_the_rest_of_the_week(self, database: Database) -> None:
        approve(database, claim(database, "math", TUESDAY), TUESDAY)
        assert status(database, THURSDAY)["math"] == "approved"
        # And a daily task claimed on Tuesday is Tuesday's only.
        claim(database, "shw", TUESDAY)
        assert "shw" not in status(database, THURSDAY)

    def test_next_week_it_is_open_again(self, database: Database) -> None:
        approve(database, claim(database, "math", TUESDAY), TUESDAY)
        assert "math" not in status(database, NEXT_MONDAY)
        claim(database, "math", NEXT_MONDAY)
        assert status(database, NEXT_MONDAY)["math"] == "claimed"

    def test_a_declined_claim_can_be_made_again_later_in_the_week(
        self, database: Database
    ) -> None:
        first = claim(database, "math", TUESDAY)
        with database.write() as connection:
            approvals.decline_claim(
                connection, claim_id=first, decided_by="parent", now=at(TUESDAY)
            )
        again = claim(database, "math", THURSDAY)
        assert again == first
        with database.connect() as connection:
            found = claims.by_id(connection, again)
        assert found is not None and found.date == THURSDAY and found.status == "claimed"

    def test_it_is_waiting_all_week_until_decided(self, database: Database) -> None:
        made = claim(database, "math", TUESDAY)
        with database.connect() as connection:
            assert claims.ids_on(connection, "mira", THURSDAY, {"math"}) == {"math": made}


class TestStreaks:
    def test_a_weekly_task_does_not_break_a_run(self, database: Database) -> None:
        """Homework spread over three evenings is a week's job: the evenings
        it was not touched are not days the child failed."""
        for offset in range(5):
            day = MONDAY + timedelta(days=offset)
            approve(database, claim(database, "shw", day), day)
        with database.connect() as connection:
            run = streaks.current_streak(connection, TASKS, "mira", MONDAY + timedelta(days=4),
                                         school)
        assert run == 5


class TestTheFile:
    def test_one_id_means_one_task(self) -> None:
        with pytest.raises(ValidationError, match="differs between weekdays and weekend"):
            Tasks.model_validate(
                {
                    "mira": {
                        "weekdays": [{"id": "tidy", "title": "Tidy", "points": 2}],
                        "weekend": [{"id": "tidy", "title": "Tidy", "points": 5}],
                    }
                }
            )

    def test_a_task_in_both_lists_is_one_task(self) -> None:
        both = Tasks.model_validate(
            {
                "mira": {
                    "weekdays": [{"id": "tidy", "title": "Tidy", "points": 2}],
                    "weekend": [{"id": "tidy", "title": "Tidy", "points": 2}],
                }
            }
        )
        assert [task.id for task in both.of("mira")] == ["tidy"]

    def test_a_list_names_a_task_once(self) -> None:
        with pytest.raises(ValidationError, match="listed twice"):
            Tasks.model_validate(
                {"mira": {"weekdays": [{"id": "a", "title": "A"}, {"id": "a", "title": "A"}]}}
            )

    def test_the_old_shape_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            Tasks.model_validate({"mira": [{"id": "a", "title": "A", "days": "daily"}]})
