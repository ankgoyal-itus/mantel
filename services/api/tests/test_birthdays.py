"""Birthdays: a kind of day, not an appointment."""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mantel_api.content import Content
from mantel_api.models import Family
from mantel_api.today import birthday_today, birthdays_on

FAMILY = Family.model_validate(
    {
        "kids": [
            {"id": "mira", "name": "Mira", "color": "#1F8A8A", "birthday": "05-09"},
            {"id": "kabir", "name": "Kabir", "color": "#D97706"},
        ],
        "parents": [
            {"id": "dad", "name": "Dad", "birthday": "11-21"},
            {"id": "mom", "name": "Mum"},
        ],
    }
)


class TestWhoseDayItIs:
    def test_the_date_matches_whatever_the_year(self) -> None:
        kid = FAMILY.kids[0]
        assert birthday_today(kid, Date(2026, 5, 9))
        assert birthday_today(kid, Date(2031, 5, 9))
        assert not birthday_today(kid, Date(2026, 5, 8))

    def test_nobody_without_one_ever_has_one(self) -> None:
        assert not birthday_today(FAMILY.kids[1], Date(2026, 5, 9))

    def test_a_leap_day_falls_on_the_28th_in_a_common_year(self) -> None:
        """The convention the people who have one actually use."""
        leap = Family.model_validate(
            {
                "kids": [{"id": "x", "name": "X", "color": "#1F8A8A", "birthday": "02-29"}],
                "parents": [],
            }
        ).kids[0]
        assert birthday_today(leap, Date(2028, 2, 29))
        assert not birthday_today(leap, Date(2028, 2, 28))
        assert birthday_today(leap, Date(2026, 2, 28))

    def test_a_date_that_is_not_one_is_refused_by_the_model(self) -> None:
        for bad in ("21-11", "5-9", "2026-05-09", "02-30", ""):
            with pytest.raises(ValueError):
                Family.model_validate(
                    {
                        "kids": [
                            {"id": "x", "name": "X", "color": "#1F8A8A", "birthday": bad}
                        ],
                        "parents": [],
                    }
                )


class TestOnTheDay:
    def test_it_becomes_an_observance(self) -> None:
        found = birthdays_on(FAMILY, Date(2026, 5, 9))
        assert [one.name for one in found] == ["Mira's birthday"]
        assert found[0].calendar_id == "birthdays"

    def test_parents_have_them_too(self) -> None:
        # Which is how a parent's birthday reaches the night screen and the
        # tomorrow card: they are observances like any other kind of day.
        assert [one.name for one in birthdays_on(FAMILY, Date(2026, 11, 21))] == [
            "Dad's birthday"
        ]

    def test_an_ordinary_day_has_none(self) -> None:
        assert birthdays_on(FAMILY, Date(2026, 3, 15)) == []


@pytest.fixture
def birthday_house(content_dir: Path, content: Content) -> None:
    """Both children born on the two days the fixtures run across."""
    path = content_dir / "family.yaml"
    path.write_text(
        "kids:\n"
        '  - {id: mira, name: Mira, color: "#1F8A8A", avatar: fox, birthday: "09-29"}\n'
        '  - {id: kabir, name: Kabir, color: "#D97706", avatar: panda, birthday: "09-30"}\n'
        "parents:\n"
        '  - {id: dad, name: Dad, birthday: "09-30"}\n'
        "  - {id: mom, name: Mum}\n",
        encoding="utf-8",
    )
    content.load_all()


class TestOnTheScreen:
    def test_the_card_says_whose_day_it_is(
        self, client: TestClient, birthday_house: None
    ) -> None:
        body = client.get("/api/today?date=2026-09-29").json()
        whose = {kid["id"]: kid["birthday"] for kid in body["kids"]}
        assert whose == {"mira": True, "kabir": False}

    def test_it_is_on_the_day_like_any_other_kind_of_day(
        self, client: TestClient, birthday_house: None
    ) -> None:
        body = client.get("/api/today?date=2026-09-29").json()
        assert "Mira's birthday" in [one["name"] for one in body["observances"]]

    def test_a_parents_birthday_reaches_tomorrow_the_night_before(
        self, client: TestClient, birthday_house: None
    ) -> None:
        """Nothing special is needed: tomorrow is a day, and it has one."""
        tomorrow = client.get("/api/today?date=2026-09-30").json()
        names = [one["name"] for one in tomorrow["observances"]]
        assert "Dad's birthday" in names
        assert "Kabir's birthday" in names

    def test_nobody_else_gets_one(self, client: TestClient, birthday_house: None) -> None:
        body = client.get("/api/today?date=2026-10-01").json()
        assert not any("birthday" in one["name"] for one in body["observances"])
        assert all(kid["birthday"] is False for kid in body["kids"])
