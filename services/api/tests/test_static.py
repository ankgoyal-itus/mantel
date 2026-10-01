"""The API serves the built kiosk from / and keeps /api underneath it."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mantel_api.app import create_app
from mantel_api.calendars import CalendarService
from mantel_api.content import Content
from mantel_api.kiosk import _file_in
from mantel_api.weather import WeatherService

INDEX = """<!doctype html>
<html><head><title>Mantel</title></head>
<body><div id="root"></div>
<link rel="stylesheet" href="/assets/index-abc123.css">
<script type="module" src="/assets/index-abc123.js"></script>
</body></html>
"""


@pytest.fixture
def build(tmp_path: Path) -> Path:
    """A stand-in for `make build`: index.html, the bundle, and the icon."""
    assets = tmp_path / "assets"
    assets.mkdir()
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "apple-touch-icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (assets / "index-abc123.js").write_text("export const bundled = 1\n", encoding="utf-8")
    (assets / "index-abc123.css").write_text(".day { color: red }\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def served(
    build: Path,
    content: Content,
    weather: WeatherService,
    calendars: CalendarService,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    monkeypatch.setenv("MANTEL_STATIC", str(build))
    yield TestClient(create_app(content, weather, calendars))


@pytest.fixture
def unbuilt(
    tmp_path: Path,
    content: Content,
    weather: WeatherService,
    calendars: CalendarService,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """The API as it runs before anyone has built the kiosk."""
    monkeypatch.setenv("MANTEL_STATIC", str(tmp_path / "never-built"))
    yield TestClient(create_app(content, weather, calendars))


def test_root_serves_the_kiosk(served: TestClient) -> None:
    response = served.get("/")
    assert response.status_code == 200
    assert "<div id=\"root\">" in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_index_is_never_cached(served: TestClient) -> None:
    # An iPad holding a stale index.html would never find the next build.
    assert served.get("/").headers["cache-control"] == "no-store"


def test_the_bundle_is_served(served: TestClient) -> None:
    script = served.get("/assets/index-abc123.js")
    styles = served.get("/assets/index-abc123.css")
    assert script.status_code == 200
    assert styles.status_code == 200
    assert "bundled" in script.text
    assert script.headers["content-type"].startswith("text/javascript")


def test_hashed_assets_are_cached_hard(served: TestClient) -> None:
    assert "immutable" in served.get("/assets/index-abc123.css").headers["cache-control"]


def test_public_files_are_served(served: TestClient) -> None:
    assert served.get("/apple-touch-icon.png").status_code == 200


def test_spa_fallback(served: TestClient) -> None:
    # /diag is a browser route; reloading it on the iPad must still load the app.
    response = served.get("/diag")
    assert response.status_code == 200
    assert "<div id=\"root\">" in response.text


def test_api_still_wins(served: TestClient) -> None:
    response = served.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_api_path_is_not_the_kiosk(served: TestClient) -> None:
    # JSON.parse of an HTML page is a mystifying way to learn about a typo.
    response = served.get("/api/nope")
    assert response.status_code == 404
    assert "text/html" not in response.headers["content-type"]


def test_missing_asset_is_a_404(served: TestClient) -> None:
    assert served.get("/assets/index-gone.js").status_code == 404


def test_missing_file_is_a_404_not_the_kiosk(served: TestClient) -> None:
    # iOS asks for both of these on every load. index.html back would be HTML
    # where Safari asked for an image.
    for path in ("/favicon.ico", "/apple-touch-icon-precomposed.png", "/robots.txt"):
        assert served.get(path).status_code == 404, path


def test_routes_without_an_extension_still_reach_the_app(served: TestClient) -> None:
    for path in ("/diag", "/parent", "/some/deep/route"):
        assert served.get(path).status_code == 200, path


def test_no_climbing_out_of_the_build(build: Path) -> None:
    # Checked directly: an HTTP client normalises ../ away before we see it.
    (build.parent / "secret.txt").write_text("secrets", encoding="utf-8")
    assert _file_in(build, "index.html") is not None
    assert _file_in(build, "../secret.txt") is None
    assert _file_in(build, "assets/../../secret.txt") is None
    assert _file_in(build, "assets") is None  # a directory is not a file


def test_without_a_build_the_api_still_runs(unbuilt: TestClient) -> None:
    assert unbuilt.get("/api/health").status_code == 200
    page = unbuilt.get("/")
    assert page.status_code == 503
    assert "make build" in page.text
