"""What a parent decides: what it writes, and what it does not."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from mantel_api import approvals, ledger, streaks
from mantel_api.db import Database
from mantel_api.models import Points, Tasks

TZ = ZoneInfo("America/Los_Angeles")
PARENT_PIN = "2468"
DAILY = "outside"

#: A kid whose only rhythm is homework, so a weekend asks nothing at all.
SCHOOL_ONLY = Tasks.model_validate(
    {"mira": {"weekdays": [{"id": "hw", "title": "Homework", "points": 10}]}}
)

#: Monday to Friday of one week in term, and the weekend after it.
MONDAY = Date(2026, 9, 21)


def weekday(day: Date) -> bool:
    return day.weekday() < 5


@pytest.fixture(autouse=True)
def parent_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_PARENT_PIN", PARENT_PIN)


def sign_in(client: TestClient) -> None:
    assert client.post("/api/parent/session", json={"pin": PARENT_PIN}).status_code == 200


def rows(database: Database, kid_id: str = "mira") -> list[object]:
    with database.connect() as connection:
        return list(ledger.entries(connection, kid_id))


def approved_on(database: Database, day: Date, task_id: str = "hw") -> None:
    """An approved claim for a past day, as the tables would hold it."""
    with database.write() as connection:
        connection.execute(
            """
            INSERT INTO claims (kid_id, task_id, date, status, claimed_at, decided_at, decided_by)
            VALUES ('mira', ?, ?, 'approved', ?, ?, 'parent')
            """,
            (task_id, day.isoformat(), day.isoformat(), day.isoformat()),
        )


class TestDeciding:
    def test_approving_writes_exactly_one_row(
        self, client: TestClient, database: Database
    ) -> None:
        made = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
        claim_id = made.json()["id"]
        sign_in(client)

        summary = client.post(f"/api/parent/claims/{claim_id}/approve")
        assert summary.status_code == 200
        assert summary.json()["balance"] == 10

        history = rows(database)
        assert len(history) == 1
        entry = history[0]
        assert entry.delta == 10  # type: ignore[attr-defined]
        assert entry.reason_kind == "task"  # type: ignore[attr-defined]
        assert entry.actor == "parent"  # type: ignore[attr-defined]
        # The reference carries the kid, because task ids repeat across kids.
        assert entry.reason_ref.startswith("mira:outside:")  # type: ignore[attr-defined]

    def test_approving_twice_pays_once(self, client: TestClient, database: Database) -> None:
        made = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
        claim_id = made.json()["id"]
        sign_in(client)

        assert client.post(f"/api/parent/claims/{claim_id}/approve").status_code == 200
        assert client.post(f"/api/parent/claims/{claim_id}/approve").status_code == 409
        assert len(rows(database)) == 1

    def test_declining_writes_nothing(self, client: TestClient, database: Database) -> None:
        """There is no negative row for a chore that was not done."""
        made = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
        claim_id = made.json()["id"]
        sign_in(client)

        declined = client.post(f"/api/parent/claims/{claim_id}/decline")
        assert declined.status_code == 200
        assert declined.json()["balance"] == 0
        assert rows(database) == []

    def test_a_declined_task_looks_untouched_and_can_be_asked_again(
        self, client: TestClient
    ) -> None:
        made = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
        sign_in(client)
        client.post(f"/api/parent/claims/{made.json()['id']}/decline")

        day = client.get("/api/today").json()
        mira = next(kid for kid in day["kids"] if kid["id"] == "mira")
        assert next(t for t in mira["tasks"] if t["id"] == DAILY)["status"] == "declined"

        # The row reads as empty again, so tapping it has to work again.
        again = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
        assert again.status_code == 201
        assert again.json()["status"] == "claimed"

    def test_the_dashboard_carries_the_claim_it_would_approve(
        self, client: TestClient
    ) -> None:
        """A waiting row on /api/today knows its own claim id.

        This is what lets a parent decide the row where it stands instead of
        walking to the parent screen: without it the dashboard would have the
        status and no way to name what it is the status of.
        """
        made = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
        claim_id = made.json()["id"]

        body = client.get("/api/today").json()
        mira = next(kid for kid in body["kids"] if kid["id"] == "mira")
        waiting = next(task for task in mira["tasks"] if task["id"] == DAILY)
        assert waiting["status"] == "claimed"
        assert waiting["claim_id"] == claim_id

        # Nothing is waiting on the others, so there is nothing to offer.
        for task in mira["tasks"]:
            if task["id"] != DAILY:
                assert task["claim_id"] is None

    def test_deciding_from_the_dashboard_is_the_same_as_from_the_tab(
        self, client: TestClient, database: Database
    ) -> None:
        """One endpoint, one ledger row, whichever screen called it.

        The inline approval is deliberately not a second path: it reads the
        claim id off the row and posts to the endpoint the approvals tab
        posts to. This asserts that the row it writes is identical.
        """
        made = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
        claim_id = made.json()["id"]
        sign_in(client)

        # What the tab would have sent, taken from the queue it renders.
        queue = client.get("/api/parent/approvals").json()
        assert [(item["kind"], item["id"]) for item in queue] == [("claim", claim_id)]

        # What the dashboard sends, taken from the row it renders.
        body = client.get("/api/today").json()
        mira = next(kid for kid in body["kids"] if kid["id"] == "mira")
        from_row = next(task for task in mira["tasks"] if task["id"] == DAILY)["claim_id"]
        assert from_row == claim_id

        assert client.post(f"/api/parent/claims/{from_row}/approve").status_code == 200
        history = rows(database)
        assert len(history) == 1
        assert history[0].delta == 10  # type: ignore[attr-defined]
        assert history[0].actor == "parent"  # type: ignore[attr-defined]
        assert history[0].reason_kind == "task"  # type: ignore[attr-defined]

    def test_the_dashboard_asks_whether_the_session_is_still_open(
        self, client: TestClient
    ) -> None:
        """The ten minutes a PIN buys, as the dashboard sees them.

        The row offers Yes and Not yet only when this says so, which is what
        stops a second approval inside the window asking for the PIN again —
        and what stops the buttons appearing for anyone who never typed it.
        """
        closed = client.get("/api/parent/session")
        assert closed.status_code == 200
        assert closed.json()["open"] is False
        assert closed.json()["expires_in"] == 0

        sign_in(client)
        opened = client.get("/api/parent/session").json()
        assert opened["open"] is True
        # What is actually left, not the length of a session: the rail counts
        # it down, so a second in, it is a second short.
        assert 10 * 60 - 5 <= opened["expires_in"] <= 10 * 60

        # And the cookie it reports on is the one that actually works.
        made = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
        assert (
            client.post(f"/api/parent/claims/{made.json()['id']}/approve").status_code == 200
        )

        client.delete("/api/parent/session")
        assert client.get("/api/parent/session").json()["open"] is False

    def test_the_queue_holds_what_is_waiting(self, client: TestClient) -> None:
        client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
        client.post("/api/claims", json={"kid_id": "kabir", "task_id": DAILY})
        assert client.get("/api/approvals/count").json() == {"pending": 2}

        sign_in(client)
        queue = client.get("/api/parent/approvals").json()
        assert [item["kid_id"] for item in queue] == ["kabir", "mira"]  # newest first
        assert queue[0]["title"] == "30 min outside"
        assert queue[0]["points"] == 10
        assert queue[0]["kind"] == "claim"

    def test_a_kid_cannot_approve_their_own_claim(self, client: TestClient) -> None:
        made = client.post("/api/claims", json={"kid_id": "mira", "task_id": DAILY})
        assert client.post(f"/api/parent/claims/{made.json()['id']}/approve").status_code == 401


class TestAwards:
    def test_an_award_writes_a_row_that_says_what_it_was_for(
        self, client: TestClient, database: Database
    ) -> None:
        sign_in(client)
        given = client.post(
            "/api/parent/awards",
            json={"kid_id": "mira", "points": 15, "note": "Helped Kabir with his reading"},
        )
        assert given.json()["balance"] == 15

        entry = rows(database)[0]
        assert entry.reason_kind == "award"  # type: ignore[attr-defined]
        assert entry.note == "Helped Kabir with his reading"  # type: ignore[attr-defined]

    def test_an_award_needs_a_reason(self, client: TestClient) -> None:
        """"15 points" six weeks later means nothing without the note."""
        sign_in(client)
        blank = client.post(
            "/api/parent/awards", json={"kid_id": "mira", "points": 15, "note": " "}
        )
        assert blank.status_code == 400

    def test_an_award_is_worth_something(self, client: TestClient) -> None:
        sign_in(client)
        nothing = client.post(
            "/api/parent/awards", json={"kid_id": "mira", "points": 0, "note": "nice"}
        )
        assert nothing.status_code == 422


class TestStreaks:
    def test_a_run_of_complete_days_counts(self, database: Database) -> None:
        for offset in range(5):
            approved_on(database, MONDAY + timedelta(days=offset))
        with database.connect() as connection:
            run = streaks.current_streak(
                connection, SCHOOL_ONLY, "mira", MONDAY + timedelta(days=4), weekday
            )
        assert run == 5

    def test_a_weekend_does_not_break_it(self, database: Database) -> None:
        """A day that asked nothing of anyone cannot be a day they failed."""
        # Thu, Fri, then the weekend, then Mon and Tue.
        for day in (
            Date(2026, 9, 17),
            Date(2026, 9, 18),
            Date(2026, 9, 21),
            Date(2026, 9, 22),
        ):
            approved_on(database, day)

        with database.connect() as connection:
            run = streaks.current_streak(
                connection, SCHOOL_ONLY, "mira", Date(2026, 9, 22), weekday
            )
        # Four school days, with the weekend stepped over rather than counted.
        assert run == 4

    def test_a_missed_school_day_breaks_it(self, database: Database) -> None:
        approved_on(database, Date(2026, 9, 21))
        # Tuesday missed.
        approved_on(database, Date(2026, 9, 23))
        approved_on(database, Date(2026, 9, 24))

        with database.connect() as connection:
            run = streaks.current_streak(
                connection, SCHOOL_ONLY, "mira", Date(2026, 9, 24), weekday
            )
        assert run == 2

    def test_today_is_not_counted_against_them(self, database: Database) -> None:
        """A streak checked at breakfast must not be broken by the evening's
        homework."""
        for day in (Date(2026, 9, 21), Date(2026, 9, 22)):
            approved_on(database, day)
        with database.connect() as connection:
            run = streaks.current_streak(
                connection, SCHOOL_ONLY, "mira", Date(2026, 9, 23), weekday
            )
        assert run == 2


class TestTheWeeklyBonus:
    def pay(self, database: Database, today: Date) -> int | None:
        with database.write() as connection:
            return approvals.pay_streak_bonus(
                connection,
                SCHOOL_ONLY,
                Points(streak_bonus=20, streak_days=5),
                kid_id="mira",
                today=today,
                is_school_day=weekday,
                now=datetime(2026, 9, 25, 18, 0, tzinfo=TZ),
            )

    def test_it_is_paid_once_a_week(self, database: Database) -> None:
        for offset in range(5):
            approved_on(database, MONDAY + timedelta(days=offset))
        friday = MONDAY + timedelta(days=4)

        assert self.pay(database, friday) is not None
        # A second approval the same week must not pay a second bonus.
        assert self.pay(database, friday) is None

        with database.connect() as connection:
            bonuses = [
                row for row in ledger.entries(connection, "mira") if row.reason_kind == "adjust"
            ]
        assert len(bonuses) == 1
        assert bonuses[0].delta == 20
        assert bonuses[0].reason_ref == f"streak:mira:{approvals.week_key(friday)}"

    def test_a_short_run_is_not_paid(self, database: Database) -> None:
        approved_on(database, MONDAY)
        assert self.pay(database, MONDAY) is None
