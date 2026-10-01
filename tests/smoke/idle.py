"""Idle, end to end, with the live stream connected.

The real API on the smoke fixture: the wall on DAY with /api/events open,
and a write every ten seconds so the version — and the wall's refetch —
never stops moving. None of that is a hand on the screen, so DAY must reach
the photo frame at idle_minutes (3) exactly; and with night.frame on, NIGHT
must reach it at night.idle_minutes (10).

The wall's clock is Playwright's, run forward ten seconds at a time; the
writes are real, and the page is given a moment of real time after each to
hear about it.

Run it with `make idle` (and `make check` runs it).
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import urllib.request
from datetime import datetime
from datetime import time as Time

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import smoke  # noqa: E402
from smoke import BASE, TZ, SmokeFailure, check, say, today_in_tz  # noqa: E402

PARENT_PIN = "2468"
TICK_S = 10


def request(opener: urllib.request.OpenerDirector, method: str, path: str,
            body: object | None = None) -> object:
    data = None if body is None else json.dumps(body).encode()
    call = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with opener.open(call, timeout=5) as response:
        text = response.read()
        return json.loads(text) if text else None


def version(opener: urllib.request.OpenerDirector) -> int:
    answer = request(opener, "GET", "/api/version")
    assert isinstance(answer, dict)
    return int(answer["version"])


def live_until(page: Page, opener: urllib.request.OpenerDirector, seconds: int) -> None:
    """Run the wall's clock on `seconds`, a write (a star toggled) every ten."""
    for _ in range(seconds // TICK_S):
        request(opener, "PUT", "/api/kids/mira/saving/ice_cream")
        page.wait_for_timeout(150)  # real time, for the stream to deliver it
        page.clock.run_for(TICK_S * 1000)


def mode_of(page: Page) -> str:
    if page.locator(".screen-frame").count():
        return "FRAME"
    if page.locator(".screen-night").count():
        return "NIGHT"
    if page.locator(".day").count():
        return "DAY"
    return "other"


def run_day(page: Page, opener: urllib.request.OpenerDirector) -> None:
    page.clock.install(time=datetime.combine(today_in_tz(), Time(9, 30), tzinfo=TZ))
    page.goto(f"{BASE}/", wait_until="load")
    page.wait_for_selector(".day", timeout=15000)
    before = version(opener)

    live_until(page, opener, 170)
    check(mode_of(page) == "DAY", f"DAY left early for {mode_of(page)}")
    check(version(opener) >= before + 17, "the version did not keep moving")
    live_until(page, opener, 20)
    page.wait_for_selector(".screen-frame", timeout=3000)
    say("DAY reached FRAME at three minutes, with a version bump every ten seconds")


def run_night(page: Page, opener: urllib.request.OpenerDirector) -> None:
    page.clock.install(time=datetime.combine(today_in_tz(), Time(22, 30), tzinfo=TZ))
    page.goto(f"{BASE}/", wait_until="load")
    page.wait_for_selector(".screen-night", timeout=15000)

    live_until(page, opener, 590)
    check(mode_of(page) == "NIGHT", f"NIGHT left early for {mode_of(page)}")
    live_until(page, opener, 20)
    page.wait_for_selector(".screen-frame", timeout=3000)
    say("NIGHT reached FRAME at ten minutes, with the frame allowed at night")


def main() -> int:
    print("idle: the frame arrives on time with the stream connected", flush=True)
    smoke.check_build()
    os.environ["MANTEL_PARENT_PIN"] = PARENT_PIN

    errors: list[str] = []
    with smoke.serving(), sync_playwright() as playwright:
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        browser = playwright.chromium.launch()
        try:
            day = browser.new_context(viewport=smoke.VIEWPORT, timezone_id=str(TZ)).new_page()
            day.on("pageerror", lambda error: errors.append(str(error)))
            run_day(day, opener)

            # The night frame on, the way a parent turns it on.
            request(opener, "POST", "/api/parent/session", {"pin": PARENT_PIN})
            settings = request(opener, "GET", "/api/parent/settings")
            assert isinstance(settings, dict)
            request(opener, "PUT", "/api/parent/settings", {**settings, "night_frame": True})

            night = browser.new_context(viewport=smoke.VIEWPORT, timezone_id=str(TZ)).new_page()
            night.on("pageerror", lambda error: errors.append(str(error)))
            run_night(night, opener)
        finally:
            browser.close()

    check(not errors, "the wall threw: " + "; ".join(errors))
    print("idle: ok", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeFailure as failure:
        print(f"idle: FAILED — {failure}", file=sys.stderr, flush=True)
        sys.exit(1)
