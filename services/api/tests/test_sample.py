"""content.sample/: the fictional family the demo, the smoke suite and the
tests all run on, and the one a new install starts from."""

from __future__ import annotations

import asyncio
import logging
from datetime import date as Date
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from mantel_api.calendars import expand, fetch_ics
from mantel_api.content import Content
from mantel_api.sample import SAMPLE_DIR, make_home, render

TODAY = Date(2026, 10, 6)  # a Tuesday


def test_it_renders_its_dates_from_today() -> None:
    assert render("{{today}} {{tomorrow}} {{today+4}} {{today-1}}", TODAY) == (
        "2026-10-06 2026-10-07 2026-10-10 2026-10-05"
    )


def test_every_file_loads_with_no_warnings(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    home = make_home(tmp_path / "home", TODAY)
    with caplog.at_level(logging.WARNING):
        content = Content(home / "content")
        content.load_all()
    assert set(content.status.model_dump().values()) == {"ok"}
    assert [record.getMessage() for record in caplog.records] == []
    assert sorted(path.name for path in SAMPLE_DIR.glob("*.yaml")) == sorted(
        path.name for path in (home / "content").glob("*.yaml")
    )


def test_it_is_the_fictional_family(tmp_path: Path) -> None:
    content = Content(make_home(tmp_path / "home", TODAY) / "content")
    content.load_all()
    family = content.family.current
    assert family is not None
    assert [(kid.id, kid.name) for kid in family.kids] == [("mira", "Mira"), ("kabir", "Kabir")]
    settings = content.settings.current
    assert settings is not None and settings.location.name == "Half Moon Bay"


def test_its_calendars_are_local_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = make_home(tmp_path / "home", TODAY)
    monkeypatch.setenv("MANTEL_CONTENT_DIR", str(home / "content"))
    content = Content(home / "content")
    content.load_all()
    settings = content.settings.current
    assert settings is not None
    titles = set()
    for feed in settings.calendars:
        assert feed.url is not None and "://" not in feed.url
        text = asyncio.run(fetch_ics(feed.url))
        events = expand(
            text, feed, TODAY, TODAY + timedelta(days=8), ZoneInfo(settings.timezone)
        )
        titles |= {event.title for event in events}
    assert {"Picture day", "Minimum day", "Band practice", "Diwali"} <= titles
