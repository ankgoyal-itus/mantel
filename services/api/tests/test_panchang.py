"""The almanac, checked where it is checkable.

These are sanity fixtures, not exact-time assertions: two panchang sources
rarely agree to the minute, and pinning a minute here would only record what
this ephemeris said on the day the test was written. What must hold is the
naming — which tithi, which paksha, which month — because that is what a
family reads off the wall, and what drikpanchang.com can be compared against.
"""

from __future__ import annotations

import time
from datetime import date as Date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mantel_api.panchang import (
    PanchangService,
    Place,
    compute,
    fingerprint,
    karana_name,
    month_dates,
)

HOME = Place(lat=37.4636, lon=-122.4286, timezone="America/Los_Angeles", altitude=150)


class TestTheFixtures:
    def test_navratri_opens_in_ashwin(self) -> None:
        # Navratri day one: Shukla Pratipada. Every panchang agrees on this.
        day = compute(Date(2026, 10, 11), HOME)
        assert day.tithi.name == "Pratipada"
        assert day.paksha == "shukla"
        assert day.masa.name == "Ashwin"
        assert day.tithi_short == "S1"

    def test_diwali_is_kartik_amavasya(self) -> None:
        # Under purnimanta the dark fortnight belongs to the following month,
        # which is why Diwali's new moon is Kartik and not Ashwin.
        day = compute(Date(2026, 11, 8), HOME)
        assert day.tithi.name == "Amavasya"
        assert day.paksha == "krishna"
        assert day.masa.name == "Kartik"
        assert "amavasya" in day.flags

    def test_amanta_names_the_same_day_differently(self) -> None:
        day = compute(Date(2026, 11, 8), HOME, scheme="amanta")
        assert day.masa.name == "Ashwin", "amanta keeps the dark fortnight in its own month"

    def test_a_full_moon_carries_the_purnima_flag(self) -> None:
        # Sharad Purnima 2026.
        day = compute(Date(2026, 10, 25), HOME)
        assert day.tithi.name == "Purnima"
        assert "purnima" in day.flags
        assert day.tithi.index == 15

    def test_sunrise_is_within_five_minutes_of_the_almanac(self) -> None:
        day = compute(Date(2026, 9, 22), HOME)
        assert day.sunrise is not None
        minutes = day.sunrise.hour * 60 + day.sunrise.minute
        expected = 6 * 60 + 55
        assert abs(minutes - expected) <= 5, f"sunrise was {day.sunrise:%H:%M}"

    def test_the_sun_sets_after_it_rises(self) -> None:
        day = compute(Date(2026, 9, 22), HOME)
        assert day.sunrise is not None and day.sunset is not None
        assert day.sunset > day.sunrise
        assert day.moonrise is not None and day.moonset is not None


class TestTheLimbs:
    def test_every_limb_ends_within_two_days(self) -> None:
        day = compute(Date(2026, 10, 11), HOME)
        for limb in (day.tithi, day.nakshatra, day.yoga, day.karana):
            assert limb.ends_at is not None, limb.name
            assert 0 <= (limb.ends_at.date() - day.date).days <= 2, limb.name

    def test_a_limb_ends_after_the_sunrise_that_read_it(self) -> None:
        day = compute(Date(2026, 10, 11), HOME)
        assert day.sunrise is not None
        for limb in (day.tithi, day.nakshatra, day.yoga):
            assert limb.ends_at is not None and limb.ends_at > day.sunrise, limb.name

    def test_the_karana_cycle(self) -> None:
        # The first and the last three of the sixty are the fixed ones.
        assert karana_name(1) == "Kimstughna"
        assert karana_name(58) == "Shakuni"
        assert karana_name(59) == "Chatushpada"
        assert karana_name(60) == "Naga"
        # Everything between cycles through the seven moving karanas.
        assert karana_name(2) == "Bava"
        assert karana_name(9) == "Bava"

    def test_the_vaara_is_the_weekday(self) -> None:
        assert compute(Date(2026, 9, 22), HOME).vaara == "Mangalavara"  # a Tuesday

    def test_ekadashi_is_flagged_in_both_fortnights(self) -> None:
        day = compute(Date(2026, 9, 22), HOME)
        assert day.tithi.index == 11
        assert "ekadashi" in day.flags

    def test_the_samvat_years(self) -> None:
        day = compute(Date(2026, 10, 11), HOME)
        assert day.vikram == 2083
        assert day.shaka == day.vikram - 135


class TestTheMonthCache:
    def test_a_month_has_every_day(self) -> None:
        assert len(month_dates("2026-10")) == 31
        assert len(month_dates("2027-02")) == 28
        assert len(month_dates("2028-02")) == 29, "a leap year"
        assert month_dates("2026-12")[-1] == Date(2026, 12, 31)

    def test_a_month_computes_in_under_two_seconds(self, tmp_path: Path) -> None:
        service = PanchangService(HOME, cache=tmp_path)
        started = time.perf_counter()
        days = service.month("2026-10")
        elapsed = time.perf_counter() - started
        assert len(days) == 31
        assert elapsed < 2.0, f"a month took {elapsed:.2f}s"

    def test_the_second_read_comes_from_the_cache(self, tmp_path: Path) -> None:
        PanchangService(HOME, cache=tmp_path).month("2026-10")
        assert (tmp_path / "panchang-2026-10.json").is_file()

        reopened = PanchangService(HOME, cache=tmp_path)
        started = time.perf_counter()
        days = reopened.month("2026-10")
        assert time.perf_counter() - started < 0.2, "a cached month should not recompute"
        assert days[10].tithi_short == "S1"  # the 11th

    def test_moving_house_invalidates_the_cache(self, tmp_path: Path) -> None:
        PanchangService(HOME, cache=tmp_path).month("2026-10")
        before = (tmp_path / "panchang-2026-10.json").read_text(encoding="utf-8")

        # The same calendar month, seen from Bengaluru: different sunrises, and
        # a tithi that turns on a different day.
        elsewhere = Place(lat=12.9716, lon=77.5946, timezone="Asia/Kolkata")
        PanchangService(elsewhere, cache=tmp_path).month("2026-10")
        after = (tmp_path / "panchang-2026-10.json").read_text(encoding="utf-8")

        assert fingerprint(elsewhere, "purnimanta") != fingerprint(HOME, "purnimanta")
        assert after != before, "the cache must be rebuilt for a new place"

    def test_the_scheme_is_part_of_the_fingerprint(self) -> None:
        assert fingerprint(HOME, "amanta") != fingerprint(HOME, "purnimanta")

    def test_an_unreadable_cache_is_recomputed(self, tmp_path: Path) -> None:
        (tmp_path).mkdir(exist_ok=True)
        (tmp_path / "panchang-2026-10.json").write_text("{ not json", encoding="utf-8")
        days = PanchangService(HOME, cache=tmp_path).month("2026-10")
        assert len(days) == 31


@pytest.mark.parametrize(
    ("when", "expected"),
    [
        (Date(2026, 10, 11), ("S1", "Ashwin")),
        (Date(2026, 10, 20), ("S10", "Ashwin")),
        (Date(2026, 11, 8), ("K15", "Kartik")),
    ],
)
def test_the_days_the_family_will_look_up(when: Date, expected: tuple[str, str]) -> None:
    day = compute(when, HOME)
    assert (day.tithi_short, day.masa.name) == expected


def test_the_month_cells_carry_the_tithi_by_name(client: TestClient) -> None:
    """The grid says "Dwadashi", never "S12", and names whose day each is."""
    body = client.get("/api/panchang/month?ym=2026-10").json()
    days = body["days"]
    assert len(days) == 31
    for day in days:
        assert day["tithi_name"], day["date"]
        assert not day["tithi_name"][1:].isdigit()
        assert set(day["kids"]) <= {"mira", "kabir"}
    assert any(day["tithi_name"] == "Dwadashi" for day in days)
