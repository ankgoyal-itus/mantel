"""The tests never touch the family's own files."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from mantel_api import paths
from mantel_api.app import app
from mantel_api.backup import backup_path

#: Where the family's own state lives in a checkout (MANTEL_HOME's default).
REPO_HOME = Path(__file__).resolve().parents[3] / "home"


def outside_the_repo(path: Path) -> bool:
    return not path.resolve().is_relative_to(REPO_HOME.resolve())


def test_the_session_points_at_a_copy() -> None:
    assert outside_the_repo(paths.content_dir())
    assert outside_the_repo(paths.db_path())
    assert outside_the_repo(paths.backup_dir())
    assert outside_the_repo(paths.photos_dir())


def test_the_module_level_app_reads_the_copy() -> None:
    """`mantel_api.app:app` is built on import; it must be built on the copy."""
    store = app.state.content
    assert outside_the_repo(store.directory)


def test_no_fixture_resolves_to_the_repo(content_dir: Path, tmp_path: Path) -> None:
    assert outside_the_repo(content_dir)
    assert outside_the_repo(tmp_path)


def test_the_backup_runs_when_the_api_starts(client: TestClient) -> None:
    """Checked hourly, and first at start: a Mac that sleeps through the hour
    the loop would have run still gets today's copy when the API comes up."""
    zone = ZoneInfo("America/Los_Angeles")
    today = datetime.now(zone).date()
    target = backup_path(today)
    with client:
        pass
    assert target.exists()
    assert outside_the_repo(target)
