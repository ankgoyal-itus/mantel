"""Which school events reach a child's agenda, and the file that decides it."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from pathlib import Path

import pytest
import yaml as pyyaml

from mantel_api.editors import edit_school_default, edit_school_events
from mantel_api.models import CalendarEvent
from mantel_api.school_events import SchoolEvents, group, normalise

KIDS = ["mira", "kabir"]

#: A district feed's long titles.
LIVE_TITLES = [
    "Science Olympiad",
    "Cross Country meet @ Bayside Middle",
    "6th Grade Girls Volleyball @ NMS",
    "League Cross Country meet @ Bayside Middle",
]

CONFIG = SchoolEvents.model_validate(
    {
        "always": [
            {"match": "no school|holiday|break|teacher work day"},
            {"match": "minimum day|early release"},
            {"match": "picture day|back to school|conference"},
        ],
        "rules": [
            {"match": "cross country", "kids": ["mira"]},
            {"match": "girls volleyball", "kids": []},
        ],
        "default": "hide",
    }
)


def event(title: str, kid: str = "mira", day: int = 30, feed: str = "bayside") -> CalendarEvent:
    return CalendarEvent(
        calendar_id=feed,
        kid=kid,
        source="school",
        date=Date(2026, 9, day),
        title=title,
        all_day=False,
    )


class TestTheNormaliser:
    def test_the_four_live_titles(self) -> None:
        series = {normalise(title) for title in LIVE_TITLES}
        # The two volleyball spellings are one series; the two cross country
        # titles stay their own, and one rule covers both by substring.
        assert series == {
            "science olympiad",
            "cross country meet",
            "girls volleyball",
            "league cross country meet",
        }

    def test_grade_markers_go(self) -> None:
        assert normalise("6th Grade Girls Volleyball @ NMS") == "girls volleyball"
        assert normalise("7th/8th Grade Girls Volleyball @ WMS") == "girls volleyball"
        assert normalise("Grade 5 Swim Gala") == "swim gala"

    def test_the_place_goes(self) -> None:
        assert normalise("Cross Country meet @ Bayside Middle") == "cross country meet"
        assert normalise("Science @ Stockmen's Park") == "science"

    def test_case_and_spacing_do_not_make_a_new_series(self) -> None:
        assert normalise("Science Olympiad") == normalise("Science olympiad") == "science olympiad"

    def test_a_time_in_the_title_does_not(self) -> None:
        assert normalise("Early Release 1:31 PM") == "early release pm"


class TestWhoSeesWhat:
    def test_a_rule_puts_a_meet_in_one_kids_agenda(self) -> None:
        meet = event("Cross Country meet @ Bayside Middle")
        assert CONFIG.audience(meet, KIDS) == ["mira"]

    def test_and_the_other_kid_does_not_get_it(self) -> None:
        assert "kabir" not in CONFIG.audience(event("Cross Country meet @ Bayside Middle"), KIDS)

    def test_one_rule_covers_both_spellings(self) -> None:
        # Which is the whole point of matching the rule as a substring.
        league = event("League Cross Country meet @ Bayside Middle")
        assert CONFIG.audience(league, KIDS) == ["mira"]

    def test_a_rule_with_nobody_hides_it(self) -> None:
        assert CONFIG.audience(event("6th Grade Girls Volleyball @ NMS"), KIDS) == []

    def test_an_always_match_ignores_the_rules(self) -> None:
        # Even with a rule saying nobody, a closure is everybody's business.
        config = SchoolEvents.model_validate(
            {
                "always": [{"match": "no school"}],
                "rules": [{"match": "no school", "kids": []}],
                "default": "hide",
            }
        )
        closure = event("No School - Thanksgiving Break", kid="family", feed="district")
        assert config.audience(closure, KIDS) == KIDS

    def test_a_district_event_can_be_one_kids_own(self) -> None:
        # The district publishes it for everyone; the rule narrows it.
        district = event("Cross Country meet", kid="family", feed="district")
        assert CONFIG.audience(district, KIDS) == ["mira"]

    def test_default_hide_drops_what_nobody_decided(self) -> None:
        assert CONFIG.audience(event("Coffee Chat with the Principal"), KIDS) == []

    def test_default_show_keeps_it_for_the_feeds_kid(self) -> None:
        config = CONFIG.model_copy(update={"default": "show"})
        assert config.audience(event("Coffee Chat with the Principal"), KIDS) == ["mira"]


class TestTheSeriesList:
    def test_hidden_events_are_still_listed(self) -> None:
        # Hidden from the wall, not from the parent deciding about it.
        events = [event(title) for title in LIVE_TITLES] + [event("Coffee Chat")]
        series = group(events, CONFIG, KIDS)
        names = {s.series for s in series}
        assert "girls volleyball" in names
        assert "coffee chat" in names
        assert next(s for s in series if s.series == "girls volleyball").shown_to == []

    def test_counts_the_occurrences(self) -> None:
        events = [
            event("6th Grade Girls Volleyball @ NMS", day=23),
            event("7th/8th Grade Girls Volleyball @ WMS", day=29),
            event("6th Grade Girls Volleyball @ WMS", day=30),
        ]
        volleyball = group(events, CONFIG, KIDS)[0]
        assert volleyball.count == 3
        assert volleyball.next_date == Date(2026, 9, 23)
        assert volleyball.title == "6th Grade Girls Volleyball @ NMS"

    def test_always_series_are_marked_and_come_first(self) -> None:
        events = [
            event("Science Olympiad", day=24),
            event("No School - Break", kid="family", day=25),
        ]
        series = group(events, CONFIG, KIDS)
        assert series[0].always is True
        assert series[1].always is False


class TestTheFile:
    @pytest.fixture
    def path(self, tmp_path: Path) -> Path:
        target = tmp_path / "school-events.yaml"
        target.write_text(
            "# Which school events reach a child's agenda.\n"
            "always:\n"
            '  - {match: "no school"}\n'
            "rules:\n"
            "  # Mira runs, Kabir does not.\n"
            "  - {match: cross country, kids: [mira]}\n"
            "default: hide\n",
            encoding="utf-8",
        )
        return target

    def test_a_write_keeps_the_comments(self, path: Path) -> None:
        edit_school_events(
            path, "girls volleyball", [], datetime(2026, 9, 30, 9, 0), lambda _: None
        )
        text = path.read_text(encoding="utf-8")

        assert "# Which school events reach a child's agenda." in text
        assert "# Mira runs, Kabir does not." in text
        assert "girls volleyball" in text

        parsed = SchoolEvents.model_validate(pyyaml.safe_load(text))
        assert [r.match for r in parsed.rules] == ["cross country", "girls volleyball"]

    def test_a_write_moves_the_rule_that_governs_the_series(self, path: Path) -> None:
        # The file holds a broad "cross country"; the screen is showing
        # "Cross Country meet @ Bayside Middle". Tapping has to move the broad
        # rule, because a narrower one beside it would be shadowed by it.
        edit_school_events(
            path, "Cross Country meet @ Bayside Middle", ["mira", "kabir"],
            datetime(2026, 9, 30, 9, 0), lambda _: None,
        )
        parsed = SchoolEvents.model_validate(pyyaml.safe_load(path.read_text(encoding="utf-8")))
        assert len(parsed.rules) == 1
        assert parsed.rules[0].match == "cross country"
        assert parsed.rules[0].kids == ["mira", "kabir"]

    def test_a_series_nothing_governs_gets_its_own_rule(self, path: Path) -> None:
        edit_school_events(
            path, "Science Olympiad", ["kabir"], datetime(2026, 9, 30, 9, 0), lambda _: None
        )
        parsed = SchoolEvents.model_validate(pyyaml.safe_load(path.read_text(encoding="utf-8")))
        assert [r.match for r in parsed.rules] == ["cross country", "science olympiad"]

    def test_the_default_flips(self, path: Path) -> None:
        edit_school_default(path, "show", datetime(2026, 9, 30, 9, 0), lambda _: None)
        text = path.read_text(encoding="utf-8")
        assert SchoolEvents.model_validate(pyyaml.safe_load(text)).default == "show"
        assert "# Mira runs, Kabir does not." in text
