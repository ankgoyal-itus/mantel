"""Live refresh, end to end: an approval on a phone reaches the wall.

The real API on the smoke suite's fixture content, two pages in one browser:
the wall at 1024x768 on DAY, and the parent screen at a phone's width. A
kid claims Read 20 minutes; a parent approves it on the phone; the wall must read
"Done · +10" and the new balance within two seconds, with no reload — by
way of /api/events and nothing else.

Run it with `make live` (and `make check` runs it).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from datetime import time as Time

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import smoke  # noqa: E402
from smoke import BASE, TZ, SmokeFailure, check, say, today_in_tz  # noqa: E402

PARENT_PIN = "2468"
#: The whole promise: under two seconds, wall to wall.
WITHIN_MS = 2000


def post(path: str, body: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return dict(json.loads(response.read()))


def balance(kid_id: str) -> int:
    with urllib.request.urlopen(f"{BASE}/api/points/{kid_id}", timeout=5) as response:
        return int(json.loads(response.read())["balance"])


def mira_card(wall: Page) -> str:
    return wall.locator('[data-kid-card="mira"]').inner_text()


def run(wall: Page, phone: Page) -> None:
    wall.goto(f"{BASE}/", wait_until="load")
    wall.wait_for_selector(".day", timeout=15000)
    wall.wait_for_selector('[data-kid-card="mira"] .chip-task', timeout=10000)
    # Read from the API: under ten points the wall says "Start earning"
    # rather than a number, and a chore here is worth five.
    before = balance("mira")

    # Mira taps Read 20 minutes, which is on both of her lists, so this runs
    # the same on a school day and a weekend. The wall hears about it.
    post("/api/claims", {"kid_id": "mira", "task_id": "read"})
    wall.wait_for_function(
        """() => document.querySelector('[data-kid-card="mira"]')
                   ?.innerText.includes('Waiting')""",
        timeout=WITHIN_MS,
    )
    say("a claim reached the wall as Waiting")

    # A parent, on a phone, approves it.
    phone.goto(f"{BASE}/?parent=1", wait_until="load")
    phone.wait_for_selector(".pin", timeout=15000)
    for key in PARENT_PIN:
        phone.click(f".pin-key:text-is('{key}')")
    # The fourth digit opens the pad on its own.
    phone.wait_for_selector(".pp", timeout=10000)
    phone.click("[data-section='approvals']")
    approve = phone.get_by_role("button", name="Approve").first
    approve.wait_for(timeout=10000)
    approve.click()
    started = time.monotonic()

    wall.wait_for_function(
        """() => [...document.querySelectorAll(
                     '[data-kid-card="mira"] .chip-task-approved .chip-task-title')]
                   .some((title) => title.textContent.includes('Read 20 minutes'))""",
        timeout=WITHIN_MS,
    )
    took = (time.monotonic() - started) * 1000
    after = balance("mira")
    check(after > before, f"the balance did not move: {before} then {after}")
    check(took < WITHIN_MS, f"the wall took {took:.0f}ms")
    say(f"the approval reached the wall in {took:.0f}ms: {before} then {after} points")


def main() -> int:
    print("live: an approval on a phone reaches the wall", flush=True)
    smoke.check_build()
    os.environ["MANTEL_PARENT_PIN"] = PARENT_PIN

    errors: list[str] = []
    with smoke.serving(), sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        wall_context = browser.new_context(viewport=smoke.VIEWPORT, timezone_id=str(TZ))
        phone_context = browser.new_context(
            viewport={"width": 390, "height": 844}, timezone_id=str(TZ)
        )
        wall = wall_context.new_page()
        phone = phone_context.new_page()
        wall.on("pageerror", lambda error: errors.append(str(error)))
        # Mid-morning on the wall, whatever the hour the suite runs at, so it
        # is DAY and not the night screen. Time flows on from there.
        wall.clock.install(time=datetime.combine(today_in_tz(), Time(9, 30), tzinfo=TZ))
        try:
            run(wall, phone)
        finally:
            browser.close()

    check(not errors, "the wall threw: " + "; ".join(errors))
    print("live: ok", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeFailure as failure:
        print(f"live: FAILED — {failure}", file=sys.stderr, flush=True)
        sys.exit(1)
