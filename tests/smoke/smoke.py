"""End-to-end smoke test of the built kiosk.

Serves the real build out of services/api/static/ with a fixture content/
directory, drives it in Playwright's bundled Chromium at the older iPad's
1024x768 landscape, and checks the three things that break silently:

    DAY renders the content, going idle reaches FRAME, and a tap comes back.

This is a layout and wiring check, not a Safari one. Chromium is not Safari
18, so the iPads stay the last word; docs/ipad-setup.md says how to check one.

Run it with `make smoke`. Screenshots land in docs/screens/.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from datetime import time as Time
from pathlib import Path
from shutil import rmtree
from zoneinfo import ZoneInfo

from mantel_api.sample import make_home
from playwright.sync_api import Page, sync_playwright

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "services" / "api" / "static"
SCREENS = REPO / "docs" / "screens"

#: Not 8000: an installed launchd agent or a container may be serving there.
PORT = 8123
BASE = f"http://127.0.0.1:{PORT}"

#: Must match content.sample/settings.yaml: the API resolves "today" in
#: this zone, and the browser is pinned to it so the night window agrees.
TZ = ZoneInfo("America/Los_Angeles")

#: The 9.7" iPad reports 1024x768 CSS pixels; the retina one does too, at 2x.
VIEWPORT = {"width": 1024, "height": 768}
SCALE = 2

#: Mid-morning, so the run never lands in the night window or the 20:00 switch.
AT = Time(hour=9, minute=30)
#: Comfortably past settings.idle_minutes (3) in the fixture.
IDLE = "00:10:00"

STARTUP_TIMEOUT = 30.0


class SmokeFailure(Exception):
    """Something the iPads would have shown us at bedtime instead."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def say(message: str) -> None:
    print(f"  {message}", flush=True)


def check_build() -> None:
    """The build, before a browser is involved: a half-built bundle is a white iPad."""
    index = STATIC / "index.html"
    check(index.is_file(), f"no build at {index} — run `make build`")
    html = index.read_text(encoding="utf-8")

    # Every script and stylesheet index.html names has to be on disk. A stale
    # index.html pointing at a hash from the last build is a white screen with
    # nothing in the API log to show for it.
    referenced = re.findall(r'(?:src|href)="/(assets/[^"]+)"', html)
    check(bool(referenced), "index.html references no bundle at all")
    missing = [name for name in referenced if not (STATIC / name).is_file()]
    check(not missing, f"index.html points at files the build does not have: {missing}")
    say(f"build ok, {len(referenced)} bundled file(s)")


def today_in_tz() -> date:
    """The date the API will call today, which is the one meals.yaml needs."""
    return datetime.now(TZ).date()


def write_content(root: Path) -> None:
    """A home rendered from content.sample/, dated from today — the same
    sample the demo and the API tests run on."""
    make_home(root / "home", today_in_tz())
    (root / "VERSION").write_text("smoke\n", encoding="utf-8")


def wait_for_api() -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)
    raise SmokeFailure(f"the API never answered on {BASE} within {STARTUP_TIMEOUT:.0f}s")


@contextmanager
def serving() -> Iterator[None]:
    """The real app: this build, the fixture content, one process on one port."""
    root = Path(tempfile.mkdtemp(prefix="mantel-smoke-"))
    write_content(root)
    environment = dict(
        os.environ,
        MANTEL_ROOT=str(root),
        MANTEL_HOME=str(root / "home"),
        MANTEL_STATIC=str(STATIC),
    )
    # No .env is read: the fixture configures no calendars, so no secret and no
    # feed fetch is involved. Weather is attempted and simply missing offline.
    for name in list(environment):
        if name.startswith("MANTEL_CAL_"):
            del environment[name]

    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "mantel_api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ],
        cwd=REPO / "services" / "api",
        env=environment,
    )
    try:
        wait_for_api()
        say(f"API up on {BASE} with fixture content")
        yield
    finally:
        api.terminate()
        try:
            api.wait(timeout=10)
        except subprocess.TimeoutExpired:
            api.kill()
        rmtree(root, ignore_errors=True)


def shot(page: Page, name: str) -> None:
    SCREENS.mkdir(parents=True, exist_ok=True)
    path = SCREENS / f"{name}.png"
    page.screenshot(path=str(path))
    say(f"screenshot {path.relative_to(REPO)}")


def text_of(page: Page) -> str:
    return page.locator("body").inner_text()


def run(page: Page) -> None:
    page.goto(f"{BASE}/", wait_until="load")
    page.wait_for_selector(".day", timeout=15000)

    # DAY shows the fixture content, not an empty shell.
    body = text_of(page)
    # Mira, Kabir, today's breakfast and dinner, and a chore on both lists.
    for expected in ("Mira", "Kabir", "Oatmeal with fruit", "Paneer tikka", "Read 20 minutes"):
        check(expected in body, f"DAY is missing {expected!r}")
    check(page.locator(".day-kids .kid").count() == 2, "DAY should show one column per kid")
    say("DAY renders the fixture content")
    shot(page, "day")

    # Idle long enough and the photo frame takes over.
    page.clock.fast_forward(IDLE)
    page.wait_for_selector(".screen-frame", timeout=5000)
    check(page.locator(".day").count() == 0, "DAY is still mounted underneath FRAME")
    say(f"idle {IDLE} switches to FRAME")
    shot(page, "frame")

    # A tap anywhere but the diagnostics corner brings the dashboard back.
    page.mouse.click(VIEWPORT["width"] // 2, VIEWPORT["height"] - 80)
    page.wait_for_selector(".day", timeout=5000)
    check(page.locator(".screen-frame").count() == 0, "FRAME did not go away on a tap")
    say("a tap returns to DAY")
    shot(page, "day-after-tap")


def main() -> int:
    print("smoke: the built kiosk at 1024x768", flush=True)
    check_build()

    errors: list[str] = []
    with serving(), sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport=VIEWPORT, device_scale_factor=SCALE, timezone_id=str(TZ)
        )
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        # A fixed mid-morning clock: idle is then fast-forwarded, not waited out.
        page.clock.install(time=datetime.combine(today_in_tz(), AT, tzinfo=TZ))
        try:
            run(page)
        finally:
            browser.close()

    check(not errors, "the page threw: " + "; ".join(errors))
    print("smoke: ok", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeFailure as failure:
        print(f"smoke: FAILED — {failure}", file=sys.stderr, flush=True)
        sys.exit(1)
