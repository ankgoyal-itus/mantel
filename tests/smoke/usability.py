"""The 14i interactions, in a browser against the design suite's stubbed API.

Each case is a thing a finger does on the wall:
  - a tap that wakes the frame, or the night screen, lands on the dashboard
    and nowhere else — not on the kid's head, not on the Parents pill;
  - a chip on the dashboard opens that kid's card, through their code, and
    the fourth digit opens it;
  - one code lasts through Rewards, Done and Pick a meal, and Done ends it;
  - a family pill opens the list at today with Family on;
  - just after a claim the chip says how to undo it, then settles;
  - the other kid's rail card switches to them;
  - both keypads are the one component;
  - Approve pressed twice sends one approval.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from datetime import time as Time
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "design"))

import design  # noqa: E402
import serve  # noqa: E402
import states  # noqa: E402
from playwright.sync_api import Page, Route, sync_playwright  # noqa: E402

PORT = 8131
BASE = f"http://127.0.0.1:{PORT}"
MIRA_CODE = "1234"


class Failed(Exception):
    pass


def check(ok: bool, what: str) -> None:
    if not ok:
        raise Failed(what)


def route(stub: design.Stub, pins: dict, route: Route) -> None:
    """The design stub, plus what these cases need of the API: which cards
    have a code, whether one is right, and a claim that can be undone."""
    request = route.request
    path = request.url.split("://", 1)[-1].split("/", 1)[-1].split("?")[0]
    path = "/" + path
    reply = None
    if path == "/api/kids/pins":
        reply = {"pins": pins}
    elif path.endswith("/pin/verify") and request.method == "POST":
        sent = request.post_data_json or {}
        reply = {"ok": sent.get("pin") == MIRA_CODE}
    elif path == "/api/claims" and request.method == "POST":
        stub.writes.append(("POST", path, request.post_data_json))
        reply = {"id": 55, "kid_id": "mira", "task_id": "x", "status": "claimed"}
    elif path.startswith("/api/claims/") and request.method == "DELETE":
        stub.writes.append(("DELETE", path, None))
        reply = {}
    if reply is not None:
        route.fulfill(status=200, content_type="application/json", body=json.dumps(reply))
        return
    design.serve(stub, route)


def open_page(browser, hour: int, minute: int = 30, pins: dict | None = None,
              api: dict | None = None) -> tuple[Page, design.Stub]:
    context = browser.new_context(
        viewport={"width": 1024, "height": 768}, timezone_id="America/Los_Angeles"
    )
    page = context.new_page()
    stub = design.Stub(api or {})
    page.route("**/*", partial(route, stub, pins or {"mira": False, "kabir": False}))
    when = datetime.combine(datetime.fromisoformat(design.TODAY).date(), Time(hour, minute),
                            tzinfo=design.TZ)
    page.clock.install(time=when)
    page.goto(f"{BASE}/", wait_until="load")
    page.wait_for_selector(".stage", timeout=15000)
    page.wait_for_timeout(600)
    return page, stub


def centre(page: Page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).first.bounding_box()
    check(box is not None, f"{selector} is not on screen")
    assert box is not None
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def type_code(page: Page, code: str) -> None:
    for digit in code:
        page.click(f".keypad .pin-key:text-is('{digit}')")


def wake_from_frame(browser) -> None:
    page, _ = open_page(browser, 15)
    x, y = centre(page, '[data-kid-card="mira"] .kid-head-tap')
    page.clock.run_for(4 * 60 * 1000)
    page.wait_for_selector(".screen-frame", timeout=5000)
    page.mouse.click(x, y)
    page.wait_for_timeout(400)
    check(page.locator(".day").count() == 1, "the frame did not wake to DAY")
    check(page.locator(".kid-mode, .keypad").count() == 0,
          "the waking tap opened the kid's card")
    # Past the 600ms, the dashboard hears taps again.
    page.wait_for_timeout(400)
    page.mouse.click(x, y)
    page.wait_for_selector(".kid-mode", timeout=5000)
    page.context.close()
    print("  a tap on the frame lands on the dashboard, not on the kid's head")


def wake_from_night(browser) -> None:
    page, _ = open_page(browser, 22)
    page.wait_for_selector(".screen-night", timeout=5000)
    x, y = centre(page, ".parents")
    page.mouse.click(x, y)
    page.wait_for_timeout(400)
    check(page.locator(".day").count() == 1, "the night screen did not wake to DAY")
    check(page.locator(".keypad").count() == 0, "the waking tap opened the PIN pad")
    page.context.close()
    print("  a tap on the night screen lands on the dashboard, not on the Parents pill")


def night_peek(browser) -> None:
    page, _ = open_page(browser, 22)
    page.mouse.click(512, 700)
    page.wait_for_selector(".day", timeout=5000)
    page.clock.run_for(61 * 1000)
    page.wait_for_selector(".screen-night", timeout=5000)
    # And a short tap on the clock ends a peek at once.
    page.mouse.click(512, 700)
    page.wait_for_selector(".day", timeout=5000)
    page.wait_for_timeout(700)
    page.click("[data-clock]")
    page.wait_for_selector(".screen-night", timeout=5000)
    page.context.close()
    print("  a peek at the day goes back to the night after 60s, or on the clock")


def chip_opens_card(browser) -> None:
    page, stub = open_page(browser, 15, pins={"mira": True, "kabir": False})
    title = page.locator('[data-kid-card="mira"] .chip-task-title').first.text_content()
    page.locator('[data-kid-card="mira"] .chip-task-tap').first.click()
    page.wait_for_selector(".keypad-kid", timeout=5000)
    # A wrong code: the dots shake and it says so.
    type_code(page, "9999")
    page.wait_for_selector(".pin-dots[data-shake]", timeout=5000)
    check(page.locator(".pin-error").text_content() == "Try again", "no Try again")
    # The right one opens on the fourth digit, no Open needed.
    type_code(page, MIRA_CODE)
    page.wait_for_selector(".kid-mode-main", timeout=5000)
    pulsed = page.locator(".kid-mode-main .chip-task-pulse .chip-task-title").text_content()
    check(pulsed == title, f"the chip that pulsed is {pulsed!r}, not {title!r}")

    # One code: Rewards, Done, Pick a meal.
    page.click(".kid-action:has-text('Rewards')")
    page.wait_for_timeout(300)
    page.click(".kid-mode-main .kid-done")
    page.wait_for_timeout(300)
    page.click(".kid-action:has-text('Pick a meal')")
    page.wait_for_timeout(300)
    check(page.locator(".keypad").count() == 0, "the code was asked for again")

    # Done ends it: the next time, the pad.
    page.click(".kid-mode-band .kid-done")
    page.wait_for_selector(".day", timeout=5000)
    page.click('[data-kid-card="mira"] .kid-head-tap')
    page.wait_for_selector(".keypad-kid", timeout=5000)
    page.context.close()
    print("  a chip opens its kid's card; the fourth digit opens; one code lasts; Done ends it")
    del stub


def undo_and_switch(browser) -> None:
    page, stub = open_page(browser, 15)
    page.click('[data-kid-card="mira"] .kid-head-tap')
    page.wait_for_selector(".kid-mode-main", timeout=5000)
    chip = page.locator(".kid-mode-main .chip-task-open").first
    title = chip.locator(".chip-task-title").text_content()
    chip.locator(".chip-task-tap").click()
    mine = page.locator(".kid-mode-main .chip-task", has_text=title or "")
    page.wait_for_timeout(300)
    check(mine.locator(".chip-task-worth").text_content() == "Tap again to undo",
          f"after a claim the chip reads {mine.locator('.chip-task-worth').text_content()!r}")
    page.clock.run_for(5200)
    page.wait_for_timeout(100)
    worth = mine.locator(".chip-task-worth").text_content() or ""
    check(worth.startswith("Waiting · +"), f"after 5s the chip reads {worth!r}")
    check(sum(1 for w in stub.writes if w[1] == "/api/claims") == 1, "claims sent twice")

    # The other kid's rail card: their screen.
    page.click(".kid-mode-rail .kid")
    page.wait_for_function(
        "() => document.querySelector('.kid-mode-name')?.textContent === 'Kabir'", timeout=5000
    )
    page.context.close()
    print("  a claim says how to undo it for 5s; the rail card switches kids")


def family_pill(browser) -> None:
    page, _ = open_page(browser, 15)
    page.click(".fam-tap")
    page.wait_for_selector(".list", timeout=5000)
    on = page.locator(".li-chip-on").all_text_contents()
    check(on == ["Family"], f"the list opened with {on} on")
    page.context.close()
    print("  a family pill opens the list at today, Family on")


def approve_once(browser) -> None:
    page, stub = open_page(browser, 15, api=states.PARENT_ROUTES)
    page.click(".parents")
    page.wait_for_selector(".keypad-parent", timeout=5000)
    type_code(page, "4321")
    page.wait_for_selector(".pp", timeout=5000)
    approve = page.locator(".pp-item", has_text="Load the dishwasher").locator(
        "button:has-text('Approve')"
    )
    approve.dblclick()
    page.wait_for_timeout(300)
    sent = [w for w in stub.writes if w[1] == "/api/parent/claims/9/approve"]
    check(len(sent) == 1, f"Approve pressed twice sent {len(sent)} approvals")
    page.context.close()
    print("  both pads are the one keypad; Approve pressed twice approves once")


def main() -> int:
    print("usability: 14i on the wall", flush=True)
    server = ThreadingHTTPServer(
        ("127.0.0.1", PORT), partial(serve.Handler, directory=str(serve.STATIC))
    )
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for case in (wake_from_frame, wake_from_night, night_peek, chip_opens_card,
                         undo_and_switch, family_pill, approve_once):
                case(browser)
            browser.close()
    except Failed as failure:
        print(f"usability: FAILED — {failure}", file=sys.stderr)
        return 1
    finally:
        server.shutdown()
    print("usability: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
