"""Design checks: what the screens must be true of, at both iPad sizes.

Run by `make check`. These are not screenshot-diff tests — they assert the
rules the design language sets, so they keep holding as the content changes:

    nothing overflows the stage, and nothing scrolls
    every text node a kid reads is 20px or larger
    everything with a tap handler is at least 44x44
    contrast clears AA on paper — 4.5 for body, 3 for large — and AA-large
      against the night palette
    no word is written in white on a tint
    the only things that move are the ones we chose
    nothing is requested from anywhere but the API
    on the dashboard, in both orientations: text fits, is marked .clamp-1,
      or is not drawn; no word is squeezed under 40px; nothing reaches past
      its card; and every meal name is whole or visibly ellipsised

Every state is measured under both palettes. The screens the family opens
after ten at night — the calendar, the list, the frame, a kid's card — are the
same components under html[data-theme='night'], and before this pass nothing
looked at them there. The palette is forced after the steps have run and the
page has settled, which holds because the clock is frozen: nothing re-renders
to put it back.

A screenshot per state and palette is written to docs/screens/ at 1024x768,
and for the dashboard at 768x1024 too (suffixed -portrait), and committed, so
a design change shows up as a picture in the diff.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from datetime import time as Time
from functools import partial
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mantel_api.sample import sample_photo  # noqa: E402
from playwright.sync_api import Page, Route, sync_playwright  # noqa: E402
from states import (  # noqa: E402
    ANSWERED_DAY,
    BROKE,
    DARK_KIDS_CONFIG,
    DARK_PHOTO,
    DAY,
    FAMILY_FIVE,
    FOUR_ROWS,
    HOUSE_CONFIG,
    LIGHT_PHOTO,
    MIRA_BANK_20,
    MIRA_BANK_CAPPED,
    NEARLY,
    OCTOBER_MONTH,
    PARENT_ROUTES,
    PARENT_SETTINGS,
    SAT_DAY,
    THU_DAY,
    TOMORROW_DAY,
    TOMORROW_OUT,
    TWENTY_FIVE,
    WEATHER,
    WED_DAY,
    WED_WEATHER,
    WEDNESDAY,
    WEEKLY_DAY,
    body_for,
    day_api,
    later,
    tasks_day,
    with_shared_school_day,
)

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "services" / "api" / "static"
SCREENS = REPO / "docs" / "screens"
AXE = REPO / "apps" / "kiosk" / "node_modules" / "axe-core" / "axe.min.js"

TZ = ZoneInfo("America/Los_Angeles")
TODAY = "2026-09-29"

#: The older iPad, and the retina one. Both report 1024x768 CSS pixels; the
#: second differs only in device pixel ratio, which is where hairlines and
#: glyph hinting go wrong. Then the same iPad held upright, which only the
#: dashboard is laid out for: everything else asks to be turned sideways, so
#: only the states marked `portrait` are run there.
VIEWPORTS = [
    ("1024x768", 1024, 768, 1),
    ("2048x1536", 1024, 768, 2),
    ("768x1024", 768, 1024, 1),
    ("390x844", 390, 844, 1),
]
PORTRAIT = "768x1024"
#: A phone, where only the parent screen is drawn: the rail becomes a bar of
#: glyphs along the bottom, and nothing may scroll sideways.
PHONE = "390x844"
LANDSCAPE = ("1024x768", "2048x1536")

#: The type scale in theme.css: every piece of text is one of these five
#: sizes, and the smallest of them, the caption, is the floor everywhere.
TYPE_SCALE_PX = (96, 32, 20, 18, 14)
#: The frame chip is the one exception, drawn to be read across the room:
#: its time must be the 44px it was specified at, not a step of the scale.
FRAME_CHIP_TIME_PX = 44
MIN_TEXT_PX = 14
MIN_PARENT_TEXT_PX = MIN_TEXT_PX
MIN_TAB_LABEL_PX = MIN_TEXT_PX
MIN_SMALL_LABEL_PX = MIN_TEXT_PX
MIN_CHIP_TEXT_PX = MIN_TEXT_PX
MIN_TAP_PX = 44

#: The only things allowed to move. Everything else on a wall display is a
#: distraction, and on an old iPad it is also dropped frames.
#:
#: balance-bump is v2's: one 600ms bounce when a number changes. avatar-nod is
#: one 400ms turn of the head as a card opens into kid mode, never on a loop.
#: The confetti is a canvas rather than an animation, so it does not appear
#: here — it is bounded by its own 900ms and draws nothing until a parent
#: says yes.
ALLOWED_ANIMATIONS = {
    "frame-fade",
    "frame-drift",
    "pin-shake",
    "balance-bump",
    "avatar-nod",
    # One 250ms slide, shared by the month panel, the shop and the picker, so
    # there is one way things open in Mantel.
    "mo-panel-in",
    # A decided approval fading out of the list, once, in 200ms.
    "pp-leave",
    # A week-strip cell a child just filled, washed once in their colour.
    "pick-tint",
    # The frame chip, once, as the frame starts.
    "frame-chip-in",
    # 14g: every change of screen fades in; a claimed task washes with the
    # kid's tint; a kid's card grows from its DAY position (Web Animations,
    # named by its id).
    "mode-in",
    "task-wash",
    "kid-grow",
    # 14i: a keypad fading into the screen behind it on a right code, and
    # the chip a kid tapped on the wall pulsing once in their own screen.
    "keypad-leave",
    "chip-pulse",
    # v3: "+$5 in your piggy bank" on a kid's card after a yes, 200ms in and
    # out over four seconds.
    "bank-toast",
}


class DesignFailure(Exception):
    """A rule of the design language, broken."""


#: Both palettes, measured on every state that can have both.
THEMES = ("day", "night")


@dataclass
class State:
    name: str
    at: Time
    #: What to do once the page has loaded, before anything is measured.
    steps: tuple[str, ...] = ()
    #: The palette this state has in life, and the one its screenshot keeps.
    theme: str = "day"
    #: True where the app fixes the palette itself rather than following the
    #: hour. Sweeping such a screen measures a pairing it can never have.
    pinned: bool = False
    #: API paths this state answers differently from the shared fixture.
    api: dict = field(default_factory=dict)
    #: The day the clock is frozen on, when it is not the shared fixture's.
    day: str = TODAY
    #: The viewports this state is drawn at. The dashboard is laid out
    #: upright too; the parent screen is also a phone app.
    viewports: tuple[str, ...] = LANDSCAPE
    #: False for the variants that are measured and not pictured: a picture
    #: per edge case would bury the ones that show the design.
    shots: bool = True


WED = WEDNESDAY.isoformat()
DASHBOARD = (*LANDSCAPE, PORTRAIT)


def parent(name: str, *steps: str, shots: bool = True, phone: bool = False) -> State:
    """The parent screen, reached the way a parent reaches it: the pill, then
    the PIN. On a phone there is no pill; the screen is the app."""
    lead = () if phone else ("pill", "unlock")
    return State(name, Time(15, 30), steps=(*lead, *steps), api=PARENT_ROUTES,
                 viewports=(PHONE,) if phone else LANDSCAPE, shots=shots)


def budget(name: str, family: list, four: bool = False, wed: bool = False) -> State:
    """One dashboard at the edge of its budget, measured and not pictured."""
    if wed:
        api = day_api(WED_DAY, THU_DAY, WED_WEATHER, family, FOUR_ROWS if four else None)
    else:
        api = day_api(DAY, TOMORROW_DAY, WEATHER, family, FOUR_ROWS if four else None)
    return State(name, Time(15, 30), api=api, day=WED if wed else TODAY, viewports=DASHBOARD,
                 shots=False)


STATES = [
    State("day-morning", Time(7, 30), viewports=DASHBOARD),
    State("day-afternoon", Time(15, 30), viewports=DASHBOARD),
    State("day-evening", Time(20, 30), viewports=DASHBOARD),
    # The family's own Wednesday, pictured: two pills on the strip, Kabir's
    # swim, and the dinner she picked.
    State("day-wednesday", Time(15, 30), viewports=DASHBOARD, day=WED,
          api=day_api(WED_DAY, THU_DAY, WED_WEATHER, WED_DAY["family_agenda"])),
    # Five and seven to-dos at 5 pm: every one drawn with its worth, none
    # behind a "+N more", and the kids' row down to the day cards.
    # 8 am on a Saturday: Mira's five to-dos as chips in every state a chip
    # has, three rows of them, each at 4.5:1 in both palettes.
    State("day-saturday", Time(8, 0), steps=("chip-states",), viewports=DASHBOARD,
          day=SAT_DAY["date"],
          api=day_api(SAT_DAY, later(SAT_DAY, 1), WEATHER, [])),
    # Once-a-week jobs: one done earlier in the week (green, plain worth),
    # one still to do (its worth says "· week").
    State("day-weekly", Time(17, 0), steps=("weekly-chips",), viewports=DASHBOARD,
          api={"/api/today": WEEKLY_DAY}),
    # Coming up with a school day both children share: drawn once, no face.
    State("day-coming-up-shared", Time(15, 30), steps=("coming-up-once",),
          viewports=(PORTRAIT,),
          api={"/api/agenda": [DAY, TOMORROW_DAY, with_shared_school_day(later(DAY, 2)),
                               later(DAY, 3)]}),
    State("day-two-tasks", Time(17, 0), steps=("all-tasks-2",),
          api={"/api/today": tasks_day(2)}, viewports=DASHBOARD),
    State("day-five-tasks", Time(17, 0), steps=("all-tasks-5",),
          api={"/api/today": tasks_day(5)}, viewports=DASHBOARD),
    State("day-seven-tasks", Time(17, 0), steps=("all-tasks-7",),
          api={"/api/today": tasks_day(7)}, viewports=DASHBOARD),
    budget("day-tue-family-0", []),
    budget("day-tue-family-2", FAMILY_FIVE[:2]),
    budget("day-tue-family-5", FAMILY_FIVE),
    budget("day-tue-agenda-4", FAMILY_FIVE[:2], four=True),
    budget("day-wed-family-0", [], wed=True),
    budget("day-wed-family-5", FAMILY_FIVE, wed=True),
    budget("day-wed-agenda-4", FAMILY_FIVE[:2], four=True, wed=True),
    State("night", Time(22, 30), theme="night", viewports=DASHBOARD),
    # Tomorrow eaten out: "Dinner · Out · Taqueria Luna" with the storefront and,
    # on a veg day, the leaf; and at night on the pack list.
    State("day-out", Time(15, 30), viewports=DASHBOARD, steps=("out-on-tomorrow",),
          api={"/api/agenda": [DAY, TOMORROW_OUT, TOMORROW_OUT, TOMORROW_OUT]}),
    # The sample family's colours at night: every kid name at 4.5:1 or better.
    State("night-house", Time(22, 30), theme="night", steps=("kid-names-45",),
          api={"/api/config": HOUSE_CONFIG}, viewports=DASHBOARD),
    # And the hard case: a forest green on the black, which needs its shade.
    State("night-dark-kids", Time(22, 30), theme="night", steps=("kid-names-45",),
          api={"/api/config": DARK_KIDS_CONFIG}, viewports=DASHBOARD),
    State("night-out", Time(22, 30), theme="night", steps=("out-on-pack",),
          api={"/api/agenda": [DAY, TOMORROW_OUT, TOMORROW_OUT, TOMORROW_OUT]},
          viewports=DASHBOARD),
    State("frame", Time(15, 30), steps=("frame",), viewports=DASHBOARD),
    # The chip over a white photo and a black one: the pill, not the photo,
    # carries the contrast — deeper over the white, frosted over the black.
    State("frame-light", Time(17, 12), steps=("frame", "chip-contrast-f5f2ea"),
          api={"/api/photos": [LIGHT_PHOTO]}, viewports=DASHBOARD),
    State("frame-dark", Time(17, 12), steps=("frame", "chip-contrast-0b0b0d"),
          api={"/api/photos": [DARK_PHOTO]}, viewports=DASHBOARD),
    State("pin", Time(15, 30), steps=("pin", "pad-parent")),
    # Two digits in: two dots filled and Open still waiting for the fourth.
    State("pin-typed", Time(15, 30), steps=("pin", "pin-two")),
    State("month-family", Time(15, 30), steps=("month",), viewports=DASHBOARD),
    State("month-panchang", Time(15, 30), steps=("month", "panchang"), viewports=DASHBOARD),
    State("month-panel", Time(15, 30), steps=("month", "pick-11"), viewports=DASHBOARD),
    # Panchang with the panel open: the panel floats over the grid, whose
    # cells keep their width — every tithi whole, with its glyph.
    State("month-panel-panchang", Time(15, 30),
          steps=("month", "panchang", "pick-11", "tithi-short"), viewports=DASHBOARD),
    # October 2026 opens on a Thursday and runs 31 days: five rows, not six.
    State("month-october", Time(15, 30), steps=("month", "next-month", "five-rows"),
          api={"/api/panchang/month": OCTOBER_MONTH}, viewports=DASHBOARD),
    # October with the panel open on the 11th, Navratri's first day: grid and
    # panel from the same month.
    State("month-october-panel", Time(15, 30), steps=("month", "next-month", "pick-11"),
          api={"/api/panchang/month": OCTOBER_MONTH}, viewports=DASHBOARD),
    State("month-october-panchang", Time(15, 30),
          steps=("month", "next-month", "panchang", "dwadashi"),
          api={"/api/panchang/month": OCTOBER_MONTH}, viewports=DASHBOARD),
    State("list", Time(15, 30), steps=("month", "list"), viewports=DASHBOARD),
    State("list-filtered", Time(15, 30), steps=("month", "list", "filter-mira"),
          viewports=DASHBOARD),
    State("kid", Time(15, 30), steps=("kid",)),
    # The card after a parent answered: "Done · +10" in the good ink, and a
    # "Not today" on an empty ring.
    State("kid-approved", Time(15, 30), steps=("kid", "approved-chip"),
          api={"/api/today": ANSWERED_DAY}),
    # A card with a code on it: the kid's own pad, in their colour.
    State("kid-pad", Time(15, 30), steps=("kid", "pad-kid"),
          api={"/api/kids/pins": {"pins": {"mira": True, "kabir": False}}}),
    # $5 asked for twice and still lit for a third, and where each bank
    # reward goes: "$10 → piggy bank", "1 h → Roblox bank".
    State("kid-shop", Time(15, 30), steps=("kid", "shop", "shop-banks")),
    # Everything in the shop, the Roblox rows among it.
    State("kid-shop-all", Time(15, 30), steps=("kid", "shop", "shop-all")),
    # v3, the banks. The two chips under her points, and the piggy bank at
    # $15: "Cash out $20" held back, "Save $5 more" under it, the balance in
    # her colour at the contrast it has to clear.
    State("kid-bank-cash", Time(15, 30),
          steps=("kid", "kid-chips", "bank-cash", "bank-short", "bank-balance-contrast")),
    # At $20 the button offers it; a tap asks in place and the sheet then
    # says it is waiting.
    State("kid-bank-asked", Time(15, 30), steps=("kid", "bank-cash", "bank-ask"),
          api={"/api/banks/mira": MIRA_BANK_20}),
    # The Roblox bank with both uses this week gone: every size held back.
    State("kid-bank-roblox", Time(15, 30),
          steps=("kid", "bank-roblox", "bank-capped", "bank-balance-contrast"),
          api={"/api/banks/mira": MIRA_BANK_CAPPED}),
    # The same two values on the wall, as one caption under each balance.
    State("day-banks", Time(15, 30), steps=("day-bank-caption",), viewports=DASHBOARD,
          shots=False),
    # The two ends of the shop. At zero the grid is a shortlist of three in
    # full colour with a line above it naming the cheapest chore and the
    # cheapest reward; at fifteen exactly one thing is affordable, which is
    # the filtered shop with the toggle as the way to the rest.
    State("kid-shop-broke", Time(15, 30), steps=("kid", "shop"), api={"/api/points/mira": BROKE}),
    State("kid-shop-nearly", Time(15, 30), steps=("kid", "shop"),
          api={"/api/points/mira": NEARLY}),
    State("kid-shop-25", Time(15, 30), steps=("kid", "shop"),
          api={"/api/points/mira": TWENTY_FIVE}),
    State("kid-picker", Time(15, 30), steps=("kid", "picker")),
    # Dinner out, asked for: "Mom or Dad decide", the recent places, where.
    State("kid-dinner-out", Time(15, 30), steps=("kid", "picker", "kid-out")),
    # The week strip, opened from the dots on the wall: a locked breakfast,
    # a pick of Kabir's, and a contested dinner, in both palettes.
    State("kid-week", Time(15, 30), steps=("week", "strip-labels")),
    # The parent screen: paper by day and the dark after hours, like the rest
    # of the kiosk, so every section is measured under both palettes.
    parent("parent-approvals"),
    parent("parent-meals", "section-meals", "meals-today"),
    parent("parent-meals-sheet", "section-meals", "open-cell"),
    parent("parent-meals-out", "section-meals", "open-out"),
    # The house's colours on the night parent screen: kid names at 4.5:1.
    State("parent-house-night", Time(15, 30), theme="night",
          steps=("pill", "unlock", "kid-names-45"),
          api={**PARENT_ROUTES, "/api/config": HOUSE_CONFIG}),
    parent("parent-meals-out-set", "section-meals", "out-in-three", shots=False),
    parent("parent-events", "section-events"),
    parent("parent-photos", "section-photos", shots=False),
    parent("parent-points", "section-points"),
    parent("parent-settings", "section-settings", "diet-rows"),
    parent("parent-about", "section-about"),
    # The done criteria, as steps that fail loudly: every section one tap
    # from the rail; idle minutes changed, written through PUT and "Saved";
    # a contested dinner decided from Approvals.
    parent("parent-reach", "reach-all", shots=False),
    parent("parent-saved", "section-settings", "bump-idle", shots=False),
    parent("parent-decide", "decide-dinner", shots=False),
    # And the same screen on a phone.
    parent("phone-approvals", "seven-labels", phone=True),
    parent("phone-meals", "section-meals", phone=True),
    parent("phone-settings", "section-settings", phone=True),
    parent("phone-reach", "reach-all", phone=True, shots=False),
]

#: The screens allowed to scroll, and only downwards. Sixty days of agenda is
#: a list, and a list is read by scrolling it; the parent screen is a form
#: with a queue at the top of it, and forms are longer than they are tall.
#: Neither is a screen the kids read.
SCROLLABLE = {"li-scroll", "pp-pane", "pp-sheet-body", "pick-scroll", "tasks-scroll"}


@dataclass
class Stub:
    """The API for one page: the state's answers, whether a parent has typed
    the PIN yet, and every write the page made, for the steps to check."""

    overrides: dict
    signed_in: bool = False
    writes: list[tuple[str, str, object]] = field(default_factory=list)


def serve(stub: Stub, route: Route) -> None:
    """The API, stubbed. Anything else is a failure, not a fallback."""
    url = route.request.url
    method = route.request.method
    path = re.sub(r"^https?://[^/]+", "", url).split("?")[0]
    overrides = stub.overrides

    if path == "/api/parent/session":
        # Closed until the PIN is posted, as the real one is; a state that
        # has no parent session override never opens at all.
        if method == "POST":
            stub.signed_in = True
            answer: object = {"expires_in": 600}
        elif method == "DELETE":
            stub.signed_in = False
            answer = {"closed": "ok"}
        elif stub.signed_in and path in overrides:
            answer = overrides[path]
        else:
            answer = {"open": False, "expires_in": 0}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(answer))
        return

    if path == "/api/events":
        # One version and the end of the stream: the page falls back to
        # asking /api/version, which never moves here, so nothing refetches.
        route.fulfill(
            status=200,
            content_type="text/event-stream",
            body='event: version\ndata: {"version": 1, "changed_at": null}\n\n',
        )
        return

    if method in ("PUT", "POST", "DELETE") and path.startswith("/api/"):
        try:
            sent = route.request.post_data_json
        except Exception:  # noqa: BLE001 - a multipart upload is not JSON
            sent = None
        stub.writes.append((method, path, sent))
        if path == "/api/parent/settings":
            # A write that is read back as written, which is what the real
            # one does when the file validates.
            route.fulfill(status=200, content_type="application/json", body=json.dumps(sent))
            return
        if path == "/api/parent/picks/decide" and isinstance(sent, dict):
            decided = {"slot": sent.get("slot"), "winner_kid_id": sent.get("winner_kid_id"),
                       "winner_date": sent.get("date"), "loser_kid_id": None, "loser_date": None}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(decided))
            return

    body = body_for(path, overrides)
    if body is not None:
        route.fulfill(status=200, content_type="application/json", body=body)
        return
    if path.startswith("/design-photo-"):
        n = path.split("-")[-1].split(".")[0]
        # The frame's ordinary photos are the sample family's placeholders —
        # a sky over a horizon — so the frame looks like a frame in the
        # published screenshots.
        if n in {"1", "2", "3"}:
            route.fulfill(status=200, content_type="image/jpeg", body=sample_photo(int(n) - 1))
            return
        # The light and dark ones stay flat: the chip's contrast is measured
        # against exactly that colour.
        colour = {"1": "#3E5C76", "2": "#6B4E71", "3": "#2F5D50", "4": "#F5F2EA",
                  "5": "#0B0B0D"}.get(n, "#333")
        route.fulfill(
            status=200,
            content_type="image/svg+xml",
            body=f'<svg xmlns="http://www.w3.org/2000/svg" width="2048" height="1536">'
            f'<rect width="2048" height="1536" fill="{colour}"/></svg>',
        )
        return
    route.continue_()


#: What each rail row opens on, from copy.ts.
SECTION_TITLES = {
    "approvals": "Approvals",
    "meals": "Meals",
    "events": "Events",
    "photos": "Photos",
    "points": "Points",
    "settings": "Settings",
    "about": "About",
}


#: The to-do chips as drawn — Mira's, or with `all` every one on the page:
#: each one's state, height and marks, and the contrast of its title and
#: worth against what it is actually painted on (its own fill over every
#: ancestor's, since the night chip is a translucent one).
CHIP_READ_JS = """(all) => {
  const rgba = (v) => {
    const p = (v.match(/[\\d.]+/g) ?? []).map(Number);
    // color(srgb r g b / a) is on a 0-1 scale; rgb() is 0-255.
    const scale = v.startsWith('color(') ? 255 : 1;
    return [p[0] * scale, p[1] * scale, p[2] * scale, p[3] ?? 1];
  };
  const over = (top, bottom) => [
    ...top.slice(0, 3).map((c, i) => c * top[3] + bottom[i] * (1 - top[3])), 1];
  const ground = (el) => {
    const layers = [];
    for (let at = el; at; at = at.parentElement) {
      layers.push(rgba(getComputedStyle(at).backgroundColor));
    }
    return layers.reverse().reduce((under, top) => over(top, under), [255, 255, 255, 1]);
  };
  const ch = (v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const lum = ([r, g, b]) => 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
  const ratio = (a, b) => {
    const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m);
    return Math.round(((x + 0.05) / (y + 0.05)) * 100) / 100;
  };
  const card = all ? document : document.querySelector('[data-kid-card="mira"]');
  const chips = [...card.querySelectorAll('.chips .chip-task')];
  return {
    headers: card.querySelectorAll('.task-group, .routine-head, .kid-section').length,
    rows: new Set(chips.map((c) => Math.round(c.getBoundingClientRect().top))).size,
    landscape: innerWidth > innerHeight,
    chips: chips.map((chip) => {
      const bg = ground(chip);
      const read = (sel) => {
        const el = chip.querySelector(sel);
        return el ? ratio(over(rgba(getComputedStyle(el).color), bg), bg) : null;
      };
      const tick = chip.querySelector('.chip-task-tick');
      const ring = chip.querySelector('.chip-task-ring');
      return {
        title: chip.querySelector('.chip-task-title').textContent,
        state: [...chip.classList].find(
          (c) => c.startsWith('chip-task-') && c !== 'chip-task-long'),
        height: Math.round(chip.getBoundingClientRect().height),
        titleRatio: read('.chip-task-title'),
        worthRatio: read('.chip-task-worth'),
        worth: chip.querySelector('.chip-task-worth')?.textContent ?? null,
        tick: tick ? getComputedStyle(tick).backgroundColor : null,
        ring: ring ? getComputedStyle(ring).boxShadow : null,
        lock: !!chip.querySelector('.chip-task-lock'),
      };
    }),
  };
}"""


def check_chip_contrast(page: Page, where: str, failures: list[str]) -> None:
    """Every to-do chip, in every state, at 4.5:1 in both palettes: stricter
    than the night floor axe is held to, because a chip is read from across
    the room by a child."""
    if not page.locator(".chips .chip-task").count():
        return
    for chip in page.evaluate(CHIP_READ_JS, True)["chips"]:
        for part in ("titleRatio", "worthRatio"):
            if chip[part] is not None and chip[part] < 4.5:
                failures.append(
                    f"{where}: chip {chip['title']!r} ({chip['state']}) "
                    f"{part} {chip[part]} under 4.5"
                )


def run_steps(page: Page, state: State, stub: Stub) -> None:
    for step in state.steps:
        if step == "frame":
            # Past idle_minutes, so the photo frame takes over.
            page.clock.fast_forward("00:05:00")
            page.wait_for_selector(".frame", timeout=15000)
            page.wait_for_timeout(1800)  # the crossfade runs on real time
        elif step == "kid-names-45":
            # Kid names on the night background: 4.5:1, not the night's 3.
            ratios = page.evaluate(
                """() => {
                  // color-mix() comes back as color(srgb r g b / a), in 0..1.
                  const rgba = (v) => { const p = (v.match(/[\\d.]+/g) ?? []).map(Number);
                    const unit = v.startsWith('color(') ? 255 : 1;
                    return [p[0] * unit, p[1] * unit, p[2] * unit, p[3] ?? 1]; };
                  const ch = (v) => { const c = v / 255;
                    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
                  const lum = ([r, g, b]) => 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
                  const bg = rgba(getComputedStyle(document.body).backgroundColor);
                  const names = [...document.querySelectorAll(
                    '.night-who-kid, .kid-name, .pp-group-head span')];
                  return names.filter(e => e.getClientRects().length).map(e => {
                    const fg = rgba(getComputedStyle(e).color);
                    const over = fg.slice(0, 3).map((c, i) => c * fg[3] + bg[i] * (1 - fg[3]));
                    const [a, b] = [lum(over), lum(bg)].sort((x, y) => y - x);
                    return [e.textContent, Math.round((a + 0.05) / (b + 0.05) * 100) / 100];
                  });
                }"""
            )
            short = [one for one in ratios if one[1] < 4.5]
            if not ratios or short:
                raise DesignFailure(f"kid names at night: {ratios}")
        elif step.startswith("chip-contrast-"):
            photo = step.removeprefix("chip-contrast-")
            page.wait_for_selector(".frame-chip", timeout=5000)
            page.wait_for_timeout(600)  # the chip's 400ms fade
            size = page.evaluate(
                "() => parseFloat(getComputedStyle(document.querySelector('.frame-chip-time'))"
                ".fontSize)"
            )
            if round(size) != FRAME_CHIP_TIME_PX:
                raise DesignFailure(f"the chip's time is {size}px, not {FRAME_CHIP_TIME_PX}")
            ratios = page.evaluate(
                """(hex) => {
                  const rgba = (v) => {
                    const p = (v.match(/[\\d.]+/g) ?? []).map(Number);
                    return [p[0], p[1], p[2], p[3] ?? 1];
                  };
                  const over = (top, bottom) => top.slice(0, 3).map(
                    (c, i) => c * top[3] + bottom[i] * (1 - top[3]));
                  const ch = (v) => { const c = v / 255;
                    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
                  const lum = ([r, g, b]) => 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
                  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m);
                    return (x + 0.05) / (y + 0.05); };
                  const photo = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
                  const chip = document.querySelector('.frame-chip');
                  const pill = over(rgba(getComputedStyle(chip).backgroundColor), photo);
                  const out = {};
                  for (const part of ['time', 'temp', 'range']) {
                    const el = chip.querySelector(`.frame-chip-${part}`);
                    out[part] = ratio(over(rgba(getComputedStyle(el).color), pill), pill);
                  }
                  out.bright = chip.classList.contains('frame-chip-bright');
                  return out;
                }""",
                photo,
            )
            floors = {"time": 3.0, "temp": 3.0, "range": 4.5}
            short = {part: round(ratios[part], 2) for part in floors if ratios[part] < floors[part]}
            if short:
                raise DesignFailure(f"the chip over #{photo} reads {short} ({ratios})")
        elif step == "pin":
            # A long press on the clock, which is how a parent gets in.
            clock = page.locator("[data-clock]").first.bounding_box()
            assert clock is not None
            page.mouse.move(clock["x"] + clock["width"] / 2, clock["y"] + clock["height"] / 2)
            page.mouse.down()
            page.wait_for_timeout(2000)
            page.mouse.up()
            page.wait_for_selector(".pin", timeout=10000)
        elif step in ("pad-parent", "pad-kid"):
            # One keypad, two variants: whose it is, what it wants, four dots.
            want = {
                "pad-parent": ("keypad-parent", "Parents only", "Enter the PIN"),
                "pad-kid": ("keypad-kid", "Mira", "Your code"),
            }[step]
            pad = page.evaluate(
                """() => {
                  const pad = document.querySelector('.keypad');
                  return pad && {
                    cls: pad.className,
                    title: pad.querySelector('.pin-title').textContent,
                    caption: pad.querySelector('.pin-prompt').textContent,
                    dots: pad.querySelectorAll('.pin-dot').length,
                    keys: pad.querySelectorAll('.pin-key').length,
                    avatar: !!pad.querySelector('.pin-title .avatar'),
                    lock: !!pad.querySelector('.pin-title .pin-lock'),
                    open: pad.querySelector('.pin-go').textContent,
                  };
                }"""
            )
            if (
                not pad
                or want[0] not in pad["cls"]
                or want[1] not in pad["title"]
                or pad["caption"] != want[2]
                or pad["dots"] != 4
                or pad["keys"] != 11
                or pad["open"] != "Open"
                or (step == "pad-kid") != pad["avatar"]
                or (step == "pad-parent") != pad["lock"]
            ):
                raise DesignFailure(f"the {step} keypad is {pad}")
        elif step == "month":
            page.click(".day-date, .night-date")
            page.wait_for_selector(".month", timeout=10000)
            page.wait_for_timeout(400)
        elif step == "next-month":
            page.click(".mo-button:text-is('›')")
            page.wait_for_selector(".mo-month:text-is('October 2026')", timeout=10000)
            page.wait_for_timeout(300)
        elif step == "five-rows":
            rows = page.evaluate(
                "() => getComputedStyle(document.querySelector('.mo-grid'))"
                ".gridTemplateRows.split(' ').length"
            )
            cells = page.locator(".mo-cell").count()
            if rows != 5 or cells != 35:
                raise DesignFailure(f"October has {rows} rows and {cells} cells")
            if page.locator(".mo-legend").count() != 1:
                raise DesignFailure("the month has no legend")
        elif step == "tithi-short":
            # Measured to the cell's inner edge: a glyph over the padding is
            # already cut by the ring beside it.
            cells = page.eval_on_selector_all(
                ".mo-tithi > span",
                """els => els.filter(e => e.getClientRects().length).map(e => {
                  const cell = e.closest('.mo-cell');
                  const style = getComputedStyle(cell);
                  const edge = cell.getBoundingClientRect().right
                    - parseFloat(style.paddingRight) - parseFloat(style.borderRightWidth);
                  const range = document.createRange();
                  range.selectNodeContents(e);
                  return [e.textContent, range.getBoundingClientRect().right, edge];
                })""",
            )
            bad = [name for name, right, edge in cells
                   if "…" in name or name[-1] not in "◑◐" or right > edge + 0.5]
            if not cells or bad:
                raise DesignFailure(f"narrow tithi cells: {[c for c in cells if c[0] in bad][:4]}")
        elif step == "dwadashi":
            names = page.eval_on_selector_all(
                ".mo-tithi", "els => els.map(e => e.getAttribute('aria-label'))"
            )
            if "Dwadashi ◑" not in names or any(name[:1] in "SK" and name[1:2].isdigit()
                                                 for name in names):
                raise DesignFailure(f"the panchang cells read {names[:5]}")
        elif step == "panchang":
            page.click(".mo-toggle")
            page.wait_for_timeout(200)
        elif step == "list":
            page.click(".mo-segments .li-segment:not(.li-segment-on)")
            page.wait_for_selector(".list", timeout=10000)
            page.wait_for_timeout(400)
        elif step == "filter-mira":
            page.click(".li-chip >> nth=1")
            page.wait_for_timeout(200)
        elif step == "kid":
            # A tap on a kid's face, which is how their own card opens.
            page.click(".kid-head-tap")
            page.wait_for_selector(".kid-mode", timeout=10000)
            page.wait_for_timeout(300)
        elif step == "week":
            # The dots on a child's card: their week of meals.
            page.click(".kid-week >> nth=0")
            page.wait_for_selector(".week-strip", timeout=10000)
            page.wait_for_timeout(300)
        elif step == "shop":
            page.click(".kid-action >> nth=0")
            page.wait_for_selector(".shop-grid", timeout=10000)
            page.wait_for_timeout(300)
        elif step == "coming-up-once":
            page.wait_for_selector(".cu-card", timeout=5000)
            found = page.evaluate(
                """() => [...document.querySelectorAll('.cu-item')]
                  .filter((item) => item.textContent.includes('Conference Week'))
                  .map((item) => !!item.querySelector('.avatar'))"""
            )
            if found != [False]:
                raise DesignFailure(f"the shared school day is drawn {found} in Coming up")
        elif step == "shop-banks":
            tiles = page.evaluate(
                """() => Object.fromEntries([...document.querySelectorAll('.shop-card')]
                  .map((tile) => [tile.querySelector('.shop-name').textContent,
                    [tile.querySelector('.shop-state')?.textContent ?? '',
                     tile.classList.contains('shop-card-open'), tile.disabled]]))"""
            )
            wanted = {
                "$5 cash": ["Asked · 2", True, False],
                "$10 cash": ["$10 → piggy bank", True, False],
                "Roblox +1 h": ["1 h → Roblox bank", True, False],
            }
            wrong = {name: tiles.get(name) for name, want in wanted.items()
                     if tiles.get(name) != want}
            if wrong:
                raise DesignFailure(f"bank tiles in the shop: {wrong}")
        elif step == "kid-chips":
            chips = page.locator(".kid-mode-main .bank-chip").all_inner_texts()
            if [chip.strip() for chip in chips] != ["$15", "2 h 30 min"]:
                raise DesignFailure(f"bank chips under the balance: {chips}")
        elif step in ("bank-cash", "bank-roblox"):
            page.click(f".bank-chip >> nth={0 if step == 'bank-cash' else 1}")
            page.wait_for_selector(".bank-sheet .bank-rows", timeout=10000)
            page.wait_for_timeout(300)
        elif step == "bank-short":
            button = page.locator(".bank-out")
            text = page.locator(".bank-sheet").inner_text()
            if button.inner_text() != "Cash out $20" or button.is_enabled() \
                    or "Save $5 more" not in text:
                raise DesignFailure(f"cash out under the minimum: {text!r}")
        elif step == "bank-ask":
            page.click(".bank-out")
            question = page.locator(".bank-question").inner_text()
            if question != "Ask Mom or Dad for $20?":
                raise DesignFailure(f"the confirm in place says {question!r}")
            page.click(".bank-ask .decide-yes")
            page.wait_for_selector(".bank-waiting", timeout=5000)
            page.wait_for_timeout(200)
            sent = [w for w in stub.writes if w[1] == "/api/banks/mira/cashout"]
            if sent != [("POST", "/api/banks/mira/cashout", {"cents": 2000})]:
                raise DesignFailure(f"cash out sent {sent}")
            if page.locator(".bank-waiting").inner_text() != "Asked · waiting for Mom or Dad":
                raise DesignFailure("the sheet does not say it is waiting")
            sheet = page.locator(".bank-sheet").inner_text()
            if page.locator(".bank-out").count() or "more" in sheet:
                raise DesignFailure("the sheet still offers a cash-out it is holding")
        elif step == "bank-capped":
            sizes = page.evaluate(
                """() => [...document.querySelectorAll('.bank-size')]
                  .map((b) => [b.textContent, b.disabled])"""
            )
            text = page.locator(".bank-sheet").inner_text()
            if sizes != [["30 min", True], ["1 h", True], ["2 h", True]] \
                    or "2 of 2 this week" not in text:
                raise DesignFailure(f"Roblox at the weekly cap: {sizes} {text!r}")
        elif step == "bank-balance-contrast":
            # The balance in the kid's colour, on the sheet: 4.5:1 in both
            # palettes, though it is large enough to need only 3.
            ratio = page.evaluate(
                """() => {
                  const rgba = (v) => { const p = (v.match(/[\\d.]+/g) ?? []).map(Number);
                    const unit = v.startsWith('color(') ? 255 : 1;
                    return [p[0] * unit, p[1] * unit, p[2] * unit, p[3] ?? 1]; };
                  const ch = (v) => { const c = v / 255;
                    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
                  const lum = ([r, g, b]) => 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
                  const el = document.querySelector('.bank-balance');
                  const bg = rgba(getComputedStyle(el.closest('.confirm-card')).backgroundColor);
                  const fg = rgba(getComputedStyle(el).color);
                  const over = fg.slice(0, 3).map((c, i) => c * fg[3] + bg[i] * (1 - fg[3]));
                  const [a, b] = [lum(over), lum(bg)].sort((x, y) => y - x);
                  return Math.round((a + 0.05) / (b + 0.05) * 100) / 100;
                }"""
            )
            if ratio < 4.5:
                raise DesignFailure(f"the bank balance is {ratio}:1 on its sheet")
        elif step == "day-bank-caption":
            captions = page.evaluate(
                """() => Object.fromEntries(['mira', 'kabir'].map((kid) => [kid,
                  document.querySelector(`[data-kid-card="${kid}"] .bank-caption`)
                    ?.textContent ?? null]))"""
            )
            if captions != {"mira": "$15 saved · 2 h 30 min Roblox", "kabir": "1 h Roblox"}:
                raise DesignFailure(f"bank captions on the wall: {captions}")
        elif step == "shop-all":
            page.click(".shop-toggle")
            page.wait_for_timeout(300)
            text = page.locator(".shop-grid").inner_text()
            if "Roblox +1 h" not in text or "Roblox +2 h" not in text:
                raise DesignFailure("Show everything does not show the Roblox rows")
        elif step == "picker":
            # "Pick a meal" opens the week strip now; a cell opens the list.
            page.click(".kid-action >> nth=1")
            page.wait_for_selector(".week-strip", timeout=10000)
            page.wait_for_timeout(300)
        elif step == "pill":
            # The visible way in: the Parents pill in the corner of DAY.
            page.click(".parents")
            page.wait_for_selector(".pin", timeout=10000)
        elif step == "unlock":
            # The stub says any PIN opens the door; the parent screen is what
            # is being measured, not the lock.
            # The fourth digit opens the pad on its own (14i): no Open.
            for key in ("1", "2", "3", "4"):
                page.click(f".pin-key:text-is('{key}')")
            page.wait_for_selector(".pp", timeout=10000)
            page.wait_for_selector(".pp-badge", timeout=10000)
            page.wait_for_timeout(400)
        elif step.startswith("section-"):
            section = step.removeprefix("section-")
            page.click(f"[data-section='{section}']")
            page.wait_for_selector(
                f"[data-section='{section}'][aria-current='page']", timeout=10000
            )
            page.wait_for_timeout(500)
        elif step == "diet-rows":
            # One row per festival, never one per alias.
            names = page.eval_on_selector_all(
                ".pp-compact .pp-row .pp-row-label", "els => els.map(e => e.textContent)"
            )
            if names != ["Navratri", "Dussehra", "Karwa Chauth"]:
                raise DesignFailure(f"the Diet card drew {names}, not one row per festival")
        elif step == "meals-today":
            first = page.eval_on_selector(".pp-week-day", "e => e.className")
            if "pp-week-today" not in first:
                raise DesignFailure(f"the Meals grid does not start on today: {first}")
        elif step.startswith("all-tasks-"):
            want = int(step.removeprefix("all-tasks-"))
            found = page.evaluate(
                """() => {
                  const card = document.querySelector('[data-kid-card="mira"]');
                  const kids = document.querySelector('.day-kids').getBoundingClientRect();
                  const bottom = document.querySelector('.day-bottom').getBoundingClientRect();
                  return {
                    tasks: card.querySelectorAll('.chips .chip-task').length,
                    more: card.querySelectorAll('.task-more, .tasks-scroll').length,
                    gap: Math.round(bottom.top - kids.bottom),
                    card: Math.round(card.getBoundingClientRect().height),
                    band: Math.round(kids.height),
                  };
                }"""
            )
            if found["tasks"] != want or found["more"]:
                raise DesignFailure(f"Mira's to-dos: {found}")
            # Filled, unless the Coming up card has the rest of the screen.
            coming_up = page.locator(".cu-card").count() > 0
            if not coming_up and (found["card"] != found["band"] or found["gap"] > 16):
                raise DesignFailure(f"the kids' row is not filled: {found}")
        elif step == "weekly-chips":
            worths = page.evaluate(
                """() => Object.fromEntries(['mira', 'kabir'].map((kid) => [kid,
                  [...document.querySelectorAll(`[data-kid-card="${kid}"] .chip-task`)]
                    .map((chip) => [chip.querySelector('.chip-task-title').textContent,
                      chip.className, chip.querySelector('.chip-task-worth').textContent])]))"""
            )
            done = next(c for c in worths["mira"] if c[0] == "Math homework")
            todo = next(c for c in worths["kabir"] if c[0] == "Math homework")
            if "chip-task-approved" not in done[1] or done[2] != "+10":
                raise DesignFailure(f"Mira's weekly job is not done: {done}")
            if todo[2] != "+10 · week":
                raise DesignFailure(f"Kabir's weekly job does not say week: {todo}")
        elif step == "chip-states":
            found = page.evaluate(CHIP_READ_JS, False)
            chips = {c["title"]: c for c in found["chips"]}
            states = sorted(c["state"] for c in found["chips"])
            want = sorted(
                f"chip-task-{s}" for s in ("open", "claimed", "approved", "declined", "parent")
            )
            if states != want:
                raise DesignFailure(f"the Saturday chips are {states}, not {want}")
            if found["headers"]:
                raise DesignFailure(f"routine headers over the chips: {found['headers']}")
            if found["landscape"] and found["rows"] != 3:
                raise DesignFailure(f"five chips in {found['rows']} rows, not 3")
            room, outside = chips["Tidy room"], chips["30 min outside"]
            if room["state"] != "chip-task-approved" or not room["tick"]:
                raise DesignFailure(f"Tidy room is not green with a tick: {room}")
            if outside["state"] != "chip-task-claimed" or outside["worth"] != "Waiting · +10":
                raise DesignFailure(f"30 min outside is not waiting: {outside}")
            plants = chips["Water the plants"]
            if not plants["lock"] or plants["ring"]:
                raise DesignFailure(f"the parent's chip has no lock, or a ring: {plants}")
            for chip in found["chips"]:
                if chip["height"] < 44:
                    raise DesignFailure(f"{chip['title']} is {chip['height']}px tall")
        elif step == "out-on-tomorrow":
            card = page.locator(".dp-card").nth(1).inner_text()
            if "Out · Taqueria Luna" not in card:
                raise DesignFailure(f"Tomorrow does not say it is out: {card!r}")
        elif step == "out-on-pack":
            pack = page.locator(".night-pack").inner_text()
            if "Dinner out · Taqueria Luna" not in pack:
                raise DesignFailure(f"the pack list does not say it: {pack!r}")
        elif step == "open-out":
            # The out dinner in the grid, reopened with its place filled.
            page.click(".pp-cell:has-text('Out · Taqueria Luna')")
            page.wait_for_selector(".pp-out-where .place-input", timeout=10000)
            if page.input_value(".pp-out-where .place-input") != "Taqueria Luna":
                raise DesignFailure("the out cell reopened without its place")
            page.wait_for_timeout(300)
        elif step == "pin-two":
            for key in ("1", "2"):
                page.click(f".pin-key:text-is('{key}')")
            filled = page.locator(".pin-dot-on").count()
            if filled != 2:
                raise DesignFailure(f"two digits filled {filled} dots")
            # Open is live from the first digit (a shorter code); the fourth
            # submits on its own.
            if not page.locator(".pin-go").is_enabled():
                raise DesignFailure("Open is not live after two digits")
        elif step == "approved-chip":
            # A yes is green with a tick; a no is dimmed, its worth struck.
            chips = page.eval_on_selector_all(
                ".kid-mode-main .chip-task",
                """els => els.map(e => ({
                  state: e.className,
                  tick: !!e.querySelector('.chip-task-tick'),
                  struck: getComputedStyle(e.querySelector('.chip-task-worth'))
                    .textDecorationLine,
                }))""",
            )
            approved = [c for c in chips if "chip-task-approved" in c["state"]]
            declined = [c for c in chips if "chip-task-declined" in c["state"]]
            if not approved or not approved[0]["tick"]:
                raise DesignFailure(f"no approved chip with a tick: {chips}")
            if not declined or declined[0]["struck"] != "line-through":
                raise DesignFailure(f"no declined chip with its worth struck: {chips}")
        elif step == "strip-labels":
            labels = page.eval_on_selector_all(
                ".week-label", "els => els.map(e => e.textContent)"
            )
            if labels != ["Breakfast", "Lunch", "Dinner"]:
                raise DesignFailure(f"the week strip's rows read {labels}")
        elif step == "seven-labels":
            labels = page.eval_on_selector_all(
                ".pp-section-label",
                "els => els.filter(e => e.getClientRects().length).map(e => e.textContent)",
            )
            if len(labels) != 7:
                raise DesignFailure(f"the tab bar shows {len(labels)} labels: {labels}")
        elif step == "open-cell":
            page.click(".pp-cell-contested")
            page.wait_for_selector(".pp-sheet .pick", timeout=10000)
            page.wait_for_timeout(300)
        elif step == "reach-all":
            # Every section, one tap each from wherever the rail is.
            for section, title in SECTION_TITLES.items():
                page.click(f"[data-section='{section}']")
                page.wait_for_selector(
                    f"[data-section='{section}'][aria-current='page']", timeout=5000
                )
                shown = page.inner_text(".pp-title")
                if shown != title:
                    raise DesignFailure(f"{section} opened on {shown!r}, not {title!r}")
        elif step == "bump-idle":
            before = PARENT_SETTINGS["idle_minutes"]
            page.click("[aria-label='More: Idle minutes']")
            page.wait_for_selector(".pp-toast:has-text('Saved')", timeout=5000)
            put = [sent for method, path, sent in stub.writes
                   if method == "PUT" and path == "/api/parent/settings"]
            last = put[-1] if put and isinstance(put[-1], dict) else {}
            if last.get("idle_minutes") != before + 1:
                raise DesignFailure(f"idle minutes did not round-trip through PUT: {put}")
        elif step == "decide-dinner":
            # [Kabir's]: the first child's dish, and the card says so.
            page.click(".pp-decide-choices .pp-button-accent >> nth=0")
            page.wait_for_selector(".pp-decided", timeout=5000)
            decided = [sent for method, path, sent in stub.writes
                       if path == "/api/parent/picks/decide"]
            if not decided or not isinstance(decided[-1], dict) or decided[-1].get(
                "winner_kid_id"
            ) != "kabir":
                raise DesignFailure(f"the contested dinner was not decided: {decided}")
        elif step == "kid-out":
            # A dinner cell of the week strip, then the Dinner out tile.
            page.click(".week-day >> nth=3 >> .week-cell >> nth=2")
            page.wait_for_selector(".fast-tile-out", timeout=10000)
            page.click(".fast-tile-out")
            page.wait_for_selector(".out-ask .place-input", timeout=10000)
            page.wait_for_timeout(300)
        elif step == "out-in-three":
            # Three taps from the grid: a dinner, Dinner out, a recent place.
            page.click(".pp-week-day >> nth=5 >> .pp-cell >> nth=2")
            page.click(".pp-out-row")
            page.click(".place-chip:text-is('Taqueria Luna')")
            page.wait_for_timeout(300)
            sent = [body for method, path, body in stub.writes if path == "/api/parent/meals/set"]
            if not sent or not isinstance(sent[-1], dict) or (
                sent[-1].get("dish_id"), sent[-1].get("place")
            ) != ("dinner_out", "Taqueria Luna"):
                raise DesignFailure(f"three taps did not set dinner out: {sent}")
        elif step == "pick-11":
            page.click(".mo-cell:has(.mo-number:text-is('11'))")
            page.wait_for_selector(".mo-panel", timeout=10000)
            page.wait_for_timeout(300)


# -- the rules --------------------------------------------------------------


def check_no_overflow(page: Page, where: str, failures: list[str]) -> None:
    result = page.evaluate(
        """(allowedScroll) => {
      const ALLOWED_SCROLL = allowedScroll;
      const stage = document.querySelector('.stage') ?? document.querySelector('.parent-app')
        ?? document.body;
      const box = stage.getBoundingClientRect();
      const out = [];
      const scrolls = [];
      // An element clipped by an ancestor cannot spill off the screen, and
      // several are oversized on purpose — the blurred backdrop behind a
      // photo is scaled past the edges so its blur has nothing to sample.
      const clipped = (el) => {
        for (let p = el.parentElement; p; p = p.parentElement) {
          const o = getComputedStyle(p).overflow;
          if (o === 'hidden' || o === 'clip') return true;
        }
        return false;
      };
      for (const el of document.querySelectorAll('.stage *, .parent-app *')) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        if (!clipped(el) && (r.right > box.right + 1 || r.bottom > box.bottom + 1 ||
            r.left < box.left - 1 || r.top < box.top - 1)) {
          out.push(`${el.className || el.tagName} ${Math.round(r.left)},${Math.round(r.top)} ` +
                   `${Math.round(r.width)}x${Math.round(r.height)}`);
        }
        // Only what a finger could actually scroll. Text that is ellipsised
        // overflows its box by design and cannot be moved.
        const style = getComputedStyle(el);
        const scrollable = ['auto', 'scroll'].includes(style.overflowY) ||
                           ['auto', 'scroll'].includes(style.overflowX);
        const allowed = ALLOWED_SCROLL.some((name) => el.classList.contains(name));
        if (!allowed && scrollable && (el.scrollHeight > el.clientHeight + 2 ||
                           el.scrollWidth > el.clientWidth + 2)) {
          scrolls.push(`${el.className || el.tagName}`);
        }
        // What may scroll may only scroll down.
        if (allowed && el.scrollWidth > el.clientWidth + 2) {
          scrolls.push(`${el.className} scrolls sideways`);
        }
      }
      return {out: out.slice(0, 6), scrolls: [...new Set(scrolls)].slice(0, 6)};
    }""",
        sorted(SCROLLABLE),
    )
    for item in result["out"]:
        failures.append(f"{where}: overflows the stage — {item}")
    for item in result["scrolls"]:
        failures.append(f"{where}: scrolls — {item}")


#: The boxes that hold content rather than lay it out. Nothing inside one of
#: these may be cut off, whether it hangs out of the bottom or is squeezed
#: inside it.
CONTENT_BOXES = ".kid, .mo-panel, .dp-card, .card, .pp-card"


def check_no_clipping(page: Page, where: str, failures: list[str]) -> None:
    """Text cut off by the box it sits in.

    Overflow past the stage is caught above, but a row clipped out of the
    bottom of a card is invisible in exactly the same way and does not
    register as an overflow — it was this that hid a child's second task.
    """
    lost = page.evaluate(
        """(boxes) => {
      const out = [];
      for (const box of document.querySelectorAll(boxes)) {
        const outer = box.getBoundingClientRect();
        for (const el of box.querySelectorAll('li, p, dd, .meal-name, .row-title')) {
          const text = (el.textContent ?? '').trim();
          if (!text) continue;
          const r = el.getBoundingClientRect();
          if (r.height === 0) continue;
          if (r.bottom > outer.bottom + 1 || r.right > outer.right + 1) {
            out.push(`${box.className.split(' ')[0]} clips "${text.slice(0, 28)}"`);
          }
        }
        // A line of text crushed to a few pixels. A flex child shrinks by
        // default, so a card with too much in it can squeeze one of its own
        // rows to nothing and still measure as fitting — a kid's headline
        // was 3px tall, present and invisible, and every other check on this
        // page passed. Anything holding words is at least most of one line.
        for (const el of box.querySelectorAll('p, h1, h2, h3, li, dd, span, div')) {
          const text = (el.textContent ?? '').trim();
          if (!text || el.children.length > 0) continue;
          const r = el.getBoundingClientRect();
          if (r.width === 0) continue;
          const size = parseFloat(getComputedStyle(el).fontSize);
          if (r.height > 0 && r.height < size * 0.8) {
            out.push(`${box.className.split(' ')[0]} squashes "${text.slice(0, 24)}" ` +
                     `to ${Math.round(r.height)}px of ${Math.round(size)}px`);
          }
        }
        // And the same loss from the other direction. A flex child can be
        // squeezed rather than pushed out: its own box then fits, and the
        // text inside it is cut off mid-line, which is how a dinner came to
        // read "Paneer tik" with a name half over it. Nothing here scrolls,
        // so wanting more room than there is means something is not visible.
        if (box.scrollHeight > box.clientHeight + 2) {
          out.push(
            `${box.className.split(' ')[0]} holds ${box.scrollHeight}px ` +
            `in ${box.clientHeight}px`
          );
        }
      }
      return [...new Set(out)].slice(0, 8);
    }""",
        CONTENT_BOXES,
    )
    for item in lost:
        failures.append(f"{where}: {item}")


def check_single_line_rows(page: Page, where: str, failures: list[str]) -> None:
    """An agenda row is one line. A row that wraps takes the next row's space
    and the card silently loses whatever was at the bottom of it."""
    tall = page.evaluate(
        """() => {
      const out = [];
      for (const row of document.querySelectorAll('.row, .li-row')) {
        // The row is a fixed height with overflow hidden, so a wrap does not
        // make it taller — it makes its content taller than it is, and the
        // second line is cut off where nobody can see it went missing.
        if (row.scrollHeight > row.clientHeight + 2) {
          const text = (row.textContent ?? '').trim().slice(0, 30);
          out.push(`${text} needs ${row.scrollHeight}px in ${row.clientHeight}px`);
        }
      }
      return out.slice(0, 6);
    }"""
    )
    for item in tall:
        failures.append(f"{where}: agenda row wraps — {item}")


#: What counts as a card on the dashboard, for the rule that nothing inside
#: one reaches past its edge.
DAY_CARDS = ".kid, .dp-card"

#: Under this, a piece of text has been squeezed rather than laid out. "S"
#: for "Swim" was 14px wide and every other check on the page passed.
MIN_TEXT_WIDTH = 40


def check_header_baseline(page: Page, where: str, failures: list[str]) -> None:
    """The DAY header's one baseline: the date-and-greeting stack, the clock
    and the weather block on it, and the Parents pill centred on the clock's
    x-height (half of 0.48em above the baseline), in both orientations."""
    found = page.evaluate(
        """() => {
      const base = (el) => {
        if (!el || !el.getClientRects().length) return null;
        const probe = document.createElement('span');
        probe.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
        el.appendChild(probe);
        const y = probe.getBoundingClientRect().top;
        probe.remove();
        return y;
      };
      const header = document.querySelector('.day-header');
      if (!header) return null;
      const sub = header.querySelector('.day-sub .pill') ?? header.querySelector('.day-hello');
      const clock = header.querySelector('.day-clock');
      const pill = header.querySelector('.parents')?.getBoundingClientRect();
      const size = parseFloat(getComputedStyle(clock).fontSize);
      return {sub: base(sub), clock: base(clock), weather: base(header.querySelector('.wx-detail')),
              pill: pill ? (pill.top + pill.bottom) / 2 : null, xMid: base(clock) - size * 0.24};
    }"""
    )
    if not found:
        return
    for part in ("sub", "weather"):
        if found[part] is not None and abs(found[part] - found["clock"]) > 1:
            failures.append(f"{where}: header {part} off the clock's baseline by "
                            f"{found[part] - found['clock']:.1f}px")
    if found["pill"] is not None and abs(found["pill"] - found["xMid"]) > 2:
        failures.append(f"{where}: Parents pill {found['pill'] - found['xMid']:.1f}px off "
                        "the clock's x-height")


def check_day_budgets(page: Page, where: str, failures: list[str]) -> None:
    """The dashboard's budget rules, which only hold where a budget is kept.

    Text either fits, or is marked as ellipsised with .clamp-1, or is not
    drawn at all; a word is never squeezed into a sliver; nothing inside a
    card reaches past its edge; and every meal name is either whole or
    visibly cut, never cut silently.
    """
    found = page.evaluate(
        """([cards, minWidth]) => {
      const day = document.querySelector('.day');
      if (!day) return null;
      const out = [];
      const label = (el) => `${(typeof el.className === 'string' && el.className) || el.tagName}`;
      const shown = (el) => el.getClientRects().length > 0;
      const inClamp = (el) => !!el.closest('.clamp-1');

      for (const el of day.querySelectorAll('*')) {
        if (!(el instanceof HTMLElement) || !shown(el)) continue;
        // Wider inside than out, and not saying so.
        if (el.scrollWidth > el.clientWidth + 1 && !el.classList.contains('clamp-1') &&
            !inClamp(el)) {
          out.push(`${label(el)} overflows sideways, ${el.scrollWidth}px in ` +
                   `${el.clientWidth}px, without .clamp-1`);
        }
      }

      // Text squeezed narrower than a word. Initials, counts and "+N" are
      // short on purpose and are exempt by length rather than by name, so a
      // real word cut down to one letter is still caught: its textContent is
      // the whole word.
      const walk = document.createTreeWalker(day, NodeFilter.SHOW_TEXT);
      for (let node = walk.nextNode(); node; node = walk.nextNode()) {
        const text = node.textContent.trim();
        const el = node.parentElement;
        if (!text || !el || !shown(el) || text.length <= 3) continue;
        const r = el.getBoundingClientRect();
        if (r.width < minWidth) {
          out.push(`"${text.slice(0, 24)}" is ${Math.round(r.width)}px wide`);
        }
      }

      // Nothing inside a card reaches past it. Inside a clamp is the clamp's
      // business, and it clips.
      for (const card of day.querySelectorAll(cards)) {
        const box = card.getBoundingClientRect();
        for (const el of card.querySelectorAll('*')) {
          if (!shown(el) || inClamp(el.parentElement ?? el)) continue;
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          if (r.left < box.left - 1 || r.right > box.right + 1 ||
              r.top < box.top - 1 || r.bottom > box.bottom + 1) {
            out.push(`${label(el)} reaches past its card ` +
                     `(${Math.round(r.left)},${Math.round(r.top)} ` +
                     `${Math.round(r.width)}x${Math.round(r.height)})`);
          }
        }
      }

      // The kids' row is as tall as the taller card and no taller: the rows
      // under it follow the cards, and the spare height is the screen's end.
      const band = day.querySelector('.day-kids');
      const kidCards = [...day.querySelectorAll('.day-kids > .kid')];
      if (band && kidCards.length) {
        const tallest = Math.max(...kidCards.map((c) => c.getBoundingClientRect().height));
        const height = band.getBoundingClientRect().height;
        if (Math.abs(height - tallest) > 1) {
          out.push(`the kids' row is ${Math.round(height)}px for a ${Math.round(tallest)}px card`);
        }
      }
      // Coming up only when 160px or more is left over; otherwise that room
      // is the kids'. So with no Coming up card, nothing is empty under the
      // cards — the kids' row runs down to the day cards.
      const bottomBand = day.querySelector('.day-bottom');
      if (band && bottomBand && !day.querySelector('.cu-card')) {
        const gap = bottomBand.getBoundingClientRect().top - band.getBoundingClientRect().bottom;
        if (gap > 17) {
          out.push(`${Math.round(gap)}px empty under the kids with no Coming up card`);
        }
      }

      // A meal name is whole, or ellipsised where it stops, and inside its
      // row either way.
      for (const name of day.querySelectorAll('.meal-name')) {
        if (!shown(name)) {
          out.push(`meal "${name.textContent.trim()}" is not drawn`);
          continue;
        }
        const style = getComputedStyle(name);
        const cut = name.scrollWidth > name.clientWidth + 1;
        if (cut && !(style.textOverflow === 'ellipsis' && style.whiteSpace === 'nowrap')) {
          out.push(`meal "${name.textContent.trim()}" is cut without an ellipsis`);
        }
        const row = name.parentElement.getBoundingClientRect();
        const r = name.getBoundingClientRect();
        if (r.right > row.right + 1 || r.width < minWidth) {
          out.push(`meal "${name.textContent.trim()}" is not inside its row`);
        }
      }
      return [...new Set(out)].slice(0, 8);
    }""",
        [DAY_CARDS, MIN_TEXT_WIDTH],
    )
    for item in found or []:
        failures.append(f"{where}: {item}")


def check_text_size(page: Page, where: str, failures: list[str]) -> None:
    small = page.evaluate(
        f"""() => {{
      const found = [];
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let node = walk.nextNode(); node; node = walk.nextNode()) {{
        const text = node.textContent.trim();
        if (!text) continue;
        const el = node.parentElement;
        if (!el || !el.getClientRects().length) continue;
        const size = parseFloat(getComputedStyle(el).fontSize);
        // The phone tab bar's labels are the one exception, agreed: seven
        // words under seven glyphs in 390px.
        const floor = el.classList.contains('pp-section-label')
          ? {MIN_TAB_LABEL_PX}
          : el.classList.contains('week-label') || el.closest('.mo-tithi')
            ? {MIN_SMALL_LABEL_PX}
            : el.closest('.frame-chip')
              ? {MIN_CHIP_TEXT_PX}
              : el.closest('.pp') ? {MIN_PARENT_TEXT_PX} : {MIN_TEXT_PX};
        if (size < floor) {{
          found.push(`${{el.className || el.tagName}} ${{size}}px "${{text.slice(0, 24)}}"`);
        }} else if (!el.closest('.frame-chip') &&
                   !{list(TYPE_SCALE_PX)}.includes(Math.round(size))) {{
          const what = el.className || el.tagName;
          found.push(`off the type scale: ${{what}} ${{size}}px "${{text.slice(0, 24)}}"`);
        }}
      }}
      return [...new Set(found)].slice(0, 8);
    }}"""
    )
    for item in small:
        failures.append(f"{where}: text under the floor — {item}")


def check_tap_targets(page: Page, where: str, failures: list[str]) -> None:
    small = page.evaluate(
        f"""() => {{
      const found = [];
      for (const el of document.querySelectorAll('button, [role=button], a')) {{
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        if (r.width < {MIN_TAP_PX} || r.height < {MIN_TAP_PX}) {{
          const size = `${{Math.round(r.width)}}x${{Math.round(r.height)}}`;
          found.push(`${{el.className || el.tagName}} ${{size}}`);
        }}
      }}
      return found.slice(0, 8);
    }}"""
    )
    for item in small:
        failures.append(f"{where}: tap target under {MIN_TAP_PX}px — {item}")


def check_contrast(page: Page, where: str, night: bool, failures: list[str]) -> None:
    result = page.evaluate(
        """async () => {
      const options = {runOnly: ['color-contrast'], resultTypes: ['violations']};
      const run = await axe.run(document, options);
      return run.violations.flatMap(v => v.nodes.map(n => ({
        ...(n.any[0]?.data ?? {}),
        target: (n.target ?? []).join(' '),
      })));
    }"""
    )
    for item in result:
        ratio = item.get("contrastRatio")
        if ratio is None:
            continue
        # On paper, axe's own floor: 4.5 for body text and 3 for large, which
        # it decides from the rendered size and weight rather than from a
        # number written here. Night is read across a dark room and its
        # palette is deliberately dim, so AA-large is the bar throughout.
        floor = 3.0 if night else expected_ratio(item)
        if ratio >= floor:
            continue
        failures.append(
            f"{where}: contrast {ratio} under {floor} on {item.get('target')} "
            f"({item.get('fgColor')} over {item.get('bgColor')})"
        )


def expected_ratio(item: dict[str, object]) -> float:
    """What axe says this text needs, as a number. "4.5:1" -> 4.5."""
    raw = item.get("expectedContrastRatio")
    if isinstance(raw, int | float):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.split(":")[0])
        except ValueError:
            pass
    return 4.5


def check_no_white_on_tint(page: Page, where: str, failures: list[str]) -> None:
    """A word written in white on one of the tints.

    The light palette has three forms of every meaning — the colour fills, the
    tint carries, the ink writes — and the one thing it must never do is
    reverse a word out of a colour. A tint is within a ratio of 1.2 of white,
    so white on one is not dim, it is gone. Contrast would catch it too, but
    it would report a number; this reports the mistake.
    """
    found = page.evaluate(
        """() => {
      const rgb = (value) => (value.match(/[\d.]+/g) ?? []).map(Number);
      const channel = (v) => {
        const c = v / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
      };
      const lum = ([r, g, b]) =>
        0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
      // The surface actually behind an element, compositing every
      //semi-transparent layer on the way up to the body.
      const behind = (el) => {
        let over = [255, 255, 255];
        const stack = [];
        for (let node = el; node; node = node.parentElement) {
          const parts = rgb(getComputedStyle(node).backgroundColor);
          if (parts.length >= 3 && (parts[3] ?? 1) > 0) stack.push(parts);
          if (parts.length >= 3 && (parts[3] ?? 1) >= 1) break;
        }
        for (const parts of stack.reverse()) {
          const alpha = parts[3] ?? 1;
          over = [0, 1, 2].map((i) => parts[i] * alpha + over[i] * (1 - alpha));
        }
        return over;
      };
      const out = [];
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let node = walk.nextNode(); node; node = walk.nextNode()) {
        const text = node.textContent.trim();
        if (!text) continue;
        const el = node.parentElement;
        if (!el || !el.getClientRects().length) continue;
        const ink = rgb(getComputedStyle(el).color);
        if (ink.length < 3 || lum(ink) < 0.75) continue;
        const surface = behind(el);
        // A tint is a pale surface. White on a dark one is the night screen,
        // and white on a photograph is the frame, which has its own shadow.
        if (lum(surface) < 0.4) continue;
        out.push(`${el.className || el.tagName} "${text.slice(0, 20)}"`);
      }
      return [...new Set(out)].slice(0, 6);
    }"""
    )
    for item in found:
        failures.append(f"{where}: white on a tint — {item}")


def check_animations(page: Page, where: str, failures: list[str]) -> None:
    moving = page.evaluate(
        """() => document.getAnimations()
             .map(a => a.animationName ?? a.transitionProperty ?? (a.id || 'unknown'))
             .filter(Boolean)"""
    )
    for name in set(moving):
        if name not in ALLOWED_ANIMATIONS:
            failures.append(f"{where}: unexpected animation — {name}")


def check_requests(where: str, seen: list[str], failures: list[str]) -> None:
    for url in seen:
        failures.append(f"{where}: requested something outside the API — {url}")


# -- the run ----------------------------------------------------------------


def wear(page: Page, theme: str) -> None:
    """Put a palette on the page.

    The attribute is what useTheme sets, and setting it here sticks because
    the clock is frozen: nothing changes the mode, so the effect that owns it
    does not run again and put it back.
    """
    page.evaluate("(theme) => document.documentElement.setAttribute('data-theme', theme)", theme)
    page.wait_for_timeout(120)


def shot_name(state: State, theme: str, label: str) -> str:
    """The state's own palette keeps the plain name; the other is suffixed,
    and so is the upright iPad."""
    name = state.name if theme == state.theme else f"{state.name}-{theme}"
    return f"{name}-portrait" if label == PORTRAIT else name


def render(page: Page, state: State, label: str, shot: bool) -> list[str]:
    failures: list[str] = []
    outside: list[str] = []

    def watch(request: object) -> None:
        url = getattr(request, "url", "")
        if url.startswith(("data:", "blob:")):
            return
        host = re.sub(r"^https?://([^/]+).*", r"\1", url)
        if host and not host.startswith("127.0.0.1") and not host.startswith("localhost"):
            outside.append(url)

    page.on("request", watch)
    # On a phone there is no pill to open: the parent screen is the app, and
    # the session it holds is already open.
    stub = Stub(state.api, signed_in=label == PHONE)
    page.route("**/*", partial(serve, stub))
    when = datetime.combine(datetime.fromisoformat(state.day).date(), state.at, tzinfo=TZ)
    page.clock.install(time=when)
    page.goto("http://127.0.0.1:8130/", wait_until="load")
    page.wait_for_selector(".stage, .parent-app", timeout=15000)
    page.wait_for_timeout(500)
    run_steps(page, state, stub)
    page.wait_for_timeout(300)
    # Once per page: axe defines a global, and a second copy of it is only a
    # second megabyte of parse for the same answer.
    page.add_script_tag(path=str(AXE))

    # The palette the screen has in life first, so a screenshot is taken
    # before the forced one has been anywhere near it.
    others = tuple(theme for theme in THEMES if theme != state.theme)
    themes = (state.theme,) if state.pinned else (state.theme, *others)
    for theme in themes:
        wear(page, theme)
        where = f"{state.name} at {label} in {theme}"
        check_no_overflow(page, where, failures)
        check_no_clipping(page, where, failures)
        check_single_line_rows(page, where, failures)
        check_day_budgets(page, where, failures)
        check_header_baseline(page, where, failures)
        check_text_size(page, where, failures)
        check_tap_targets(page, where, failures)
        check_contrast(page, where, theme == "night", failures)
        check_chip_contrast(page, where, failures)
        check_no_white_on_tint(page, where, failures)
        check_animations(page, where, failures)
        if shot and state.shots:
            SCREENS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SCREENS / f"{shot_name(state, theme, label)}.png"))

    check_requests(f"{state.name} at {label}", outside, failures)
    return failures


def main() -> int:
    if not AXE.is_file():
        print(f"axe-core is missing at {AXE}; run npm install in apps/kiosk", file=sys.stderr)
        return 2
    if not (STATIC / "index.html").is_file():
        print("no kiosk build; run `make build`", file=sys.stderr)
        return 2

    failures: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for label, width, height, scale in VIEWPORTS:
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=scale,
                timezone_id=str(TZ),
            )
            for state in STATES:
                if label not in state.viewports:
                    continue
                page = context.new_page()
                try:
                    # Only the smaller viewport leaves a file: the retina pass
                    # checks the same rules, and two copies of every picture
                    # would swamp the diff.
                    found = render(page, state, label, shot=scale == 1)
                except Exception as exc:  # noqa: BLE001 - report, do not abort the run
                    found = [f"{state.name} at {label}: {type(exc).__name__}: {exc}"]
                failures.extend(found)
                print(f"  {'ok  ' if not found else 'FAIL'} {state.name} at {label}")
                page.close()
            context.close()
        browser.close()

    if failures:
        print("\ndesign checks failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    passes = sum(
        (1 if state.pinned else len(THEMES)) * len(state.viewports) for state in STATES
    )
    print(
        f"\ndesign: {len(STATES)} states across {len(VIEWPORTS)} viewports "
        f"(the dashboard upright too, the parent screen on a phone) "
        f"x both palettes: {passes} passes, all clear"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
