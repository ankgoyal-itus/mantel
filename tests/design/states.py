"""The screens the design suite renders, and the data behind them.

A stub API rather than the real one: the checks are about layout and contrast
at a known moment, and a suite that fails because the weather changed would
teach nobody anything.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

TODAY = date(2026, 9, 29)  # a Tuesday, matching the kiosk's own fixtures
TOMORROW = TODAY + timedelta(days=1)


def kid(kid_id: str, name: str, colour: str, avatar: str, agenda: list, tasks: list) -> dict:
    return {
        "id": kid_id,
        "name": name,
        "color": colour,
        "avatar": avatar,
        "agenda": agenda,
        "tasks": tasks,
    }


def task(
    task_id: str,
    title: str,
    status: str = "none",
    claim: str = "kid",
    routine: str = "afternoon",
    claim_id: int | None = None,
    every: str = "day",
) -> dict:
    return {
        "id": task_id,
        "title": title,
        "claim": claim,
        "status": status,
        "points": 10,
        "routine": routine,
        "claim_id": claim_id,
        "every": every,
    }


def row(
    title: str,
    start: str | None,
    end: str | None,
    source: str = "calendar",
    where: str | None = None,
) -> dict:
    return {
        "start": start,
        "end": end,
        "title": title,
        "where": where,
        "note": None,
        "source": source,
        "all_day": start is None,
        "calendar_id": "mira",
    }


WEATHER = {
    "now": {"temp": 68, "label": "Partly cloudy", "icon": "partly", "is_day": True},
    "today": {
        "high": 79, "low": 56, "precip_pct": 40,
        "sunrise": f"{TODAY}T06:59", "sunset": f"{TODAY}T18:55",
        "label": "Rain", "icon": "rain",
    },
    "tomorrow": {
        "high": 74, "low": 52, "precip_pct": 10,
        "sunrise": f"{TOMORROW}T07:00", "sunset": f"{TOMORROW}T18:53",
        "label": "Clear", "icon": "clear",
    },
    "stale": False,
    "fetched_at": None,
}

DAY = {
    "date": TODAY.isoformat(),
    "weekday": "tue",
    "is_school_day": True,
    "school_note": None,
    "kids": [
        kid("mira", "Mira", "#1F8A8A", "fox",
            # A district feed's long titles, which is where
            # the row layout either holds or does not.
            [row("Cross Country meet @ Bayside Middle", "15:00", "17:00", "school"),
             row("6th Grade Band practice @ Bayside Middle", "16:30", "18:00", "school"),
             row("Piano", "16:00", "16:45")],
            # tasks.yaml as it actually stands: three chores across two
            # parts of the day, one of them claimed. That puts the open
            # container, its filled row, its plain row and a shut container
            # all on screen at once, which is the card at its fullest.
            [task("hw", "Homework", "claimed", claim_id=1),
             task("outside", "30 minutes outside"),
             task("room", "Tidy room", routine="morning")]),
        kid("kabir", "Kabir", "#D97706", "panda",
            # A short title with a long place beside it: the row that used to
            # render "5:00 pm  S  Aquatic center", because the title took
            # every missing pixel while the place kept its full width.
            [row("Swim", "17:00", "18:00", where="Aquatic center")],
            [task("hw", "Homework", "claimed", claim_id=2),
             task("outside", "30 minutes outside"),
             task("dishes", "Load the dishwasher", routine="evening")]),
    ],
    "family_agenda": [row("Dinner with grandparents", "18:30", "19:30")],
    "meals": {
        "breakfast": {
            "name": "Oatmeal with fruit", "note": None, "kids_protein": "veg",
            "id": None, "picked_by": [], "confirmed": True,
        },
        "lunch": {
            "name": "Pesto pasta", "note": "Lunchbox",
            "kids_protein": "veg", "id": None, "picked_by": [], "confirmed": True,
        },
        # A confirmed pick, so the strip's "Kabir's pick" line is drawn and
        # measured like everything else on the screen.
        "dinner": {
            "name": "Paneer tikka", "note": None, "kids_protein": "veg",
            "id": "paneer_tikka", "picked_by": ["kabir"], "confirmed": True,
        },
        "snack": None,
    },
    # A Tuesday: vegetarian by the weekday rule, and no festival on it.
    "observances": [],
    "diet": {"non_veg_ok": False, "reasons": ["Tuesday"]},
    "weather": WEATHER,
}

TOMORROW_DAY = {
    **DAY,
    "date": TOMORROW.isoformat(),
    "weekday": "wed",
    "is_school_day": False,
    "school_note": "Staff development day",
    "observances": [],
    "diet": {"non_veg_ok": True, "reasons": []},
    "meals": {
        "breakfast": {"name": "Pancakes", "note": None, "kids_protein": "veg",
                      "id": "pancakes", "picked_by": [], "confirmed": True},
        "lunch": {"name": "Quesadilla", "note": None, "kids_protein": "veg",
                  "id": "quesadilla", "picked_by": [], "confirmed": True},
        "dinner": {"name": "Tacos", "note": None, "kids_protein": "chicken",
                   "id": "tacos", "picked_by": [], "confirmed": True},
        "snack": None,
    },
}

#: Tomorrow eaten out, on a vegetarian day: the storefront, the place, and
#: the leaf that travels with the booking.
TOMORROW_OUT = {
    **TOMORROW_DAY,
    # Made vegetarian by hand for the evening (no_non_veg_dates_extra).
    "diet": {"non_veg_ok": False, "reasons": ["Guests for dinner"]},
    "meals": {
        **TOMORROW_DAY["meals"],
        "dinner": {"name": "Dinner out", "id": "dinner_out", "note": "Taqueria Luna",
                   "kids_protein": "veg", "picked_by": [], "confirmed": True},
    },
}


def later(base: dict, days: int) -> dict:
    """A day further on, for the Coming up card: a practice, a family thing,
    and a dinner, so each kind of item is measured."""
    day = date.fromisoformat(base["date"]) + timedelta(days=days)
    return {
        **base,
        "date": day.isoformat(),
        "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][day.weekday()],
        "is_school_day": True,
        "school_note": None,
        "kids": [
            {**base["kids"][0], "agenda": [row("Soccer practice", "20:00", "21:00",
                                                where="Bayside Middle")]},
            {**base["kids"][1],
             "agenda": [row("Gymnastics", "16:00", "18:30", where="Harbor Gym")]},
        ],
        "family_agenda": [row("Library", "10:30", "11:30")] if days == 2 else [],
    }


CONFIG = {
    "family": {
        "kids": [
            {"id": "mira", "name": "Mira", "color": "#1F8A8A", "avatar": "fox"},
            {"id": "kabir", "name": "Kabir", "color": "#D97706", "avatar": "panda"},
        ],
        "parents": [{"id": "dad", "name": "Dad"}, {"id": "mom", "name": "Mum"}],
    },
    "settings": {
        "timezone": "America/Los_Angeles",
        "location": {"name": "Half Moon Bay", "lat": 37.4636, "lon": -122.4286},
        "units": {"temp": "F"},
        "night": {"start": "22:00", "end": "05:30", "idle_minutes": 5, "frame": True},
        "idle_minutes": 3,
        "slide_seconds": 20,
        "refresh_minutes": 5,
        "daily_reload": "04:00",
        "calendars": [],
        "diet": {},
        "panchang": {"masa_scheme": "purnimanta", "show_yoga_karana": False},
        "feelings": {"enabled": False},
    },
}

#: The sample family (content.sample/family.yaml): Mira's teal and Kabir's
#: amber, as the demo and the screenshots show them.
HOUSE_CONFIG = CONFIG

#: The hard case for the night shade: a forest green that vanished on the
#: night screen's black before kid colours got one, beside a pale sky.
DARK_KIDS_CONFIG = {
    **CONFIG,
    "family": {
        **CONFIG["family"],
        "kids": [
            {**CONFIG["family"]["kids"][0], "color": "#1B4D2B", "avatar": "hedgehog"},
            {**CONFIG["family"]["kids"][1], "color": "#A7DDF5"},
        ],
    },
}

PHOTOS = [
    {
        "id": f"photo{n}",
        "url": f"/design-photo-{n}.svg",
        "w": 2048,
        "h": 1536,
        "taken_at": "2024-06-14",
    }
    for n in (1, 2, 3)
]

#: Flat photographs at the two ends: a white sky and a black night.
LIGHT_PHOTO = {**PHOTOS[0], "id": "light", "url": "/design-photo-4.svg"}
DARK_PHOTO = {**PHOTOS[0], "id": "dark", "url": "/design-photo-5.svg"}

#: The month the screen actually opens on, which is TODAY's. It used to be
#: October while the grid asked for September, so every cell came back empty
#: and the month screenshots have been showing a blank calendar.
MONTH_YM = TODAY.strftime("%Y-%m")

TITHI_NAMES = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami",
    "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi",
    "Purnima",
]


WEEKDAY_TOKENS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
#: The lunar month each calendar month is mostly in (purnimanta).
MASA = {"2026-09": "Bhadrapada", "2026-10": "Ashwin", "2026-11": "Kartika"}


def tithi_of(n: int) -> tuple[str, str, int]:
    """A tithi cycle that agrees with the panchang engine for October 2026:
    Amavasya on the 10th, Shukla Pratipada on the 11th (Navratri's first
    day), Purnima on the 25th. Other months borrow the same rhythm."""
    if n <= 10:
        paksha, index = "krishna", n + 5
    elif n <= 25:
        paksha, index = "shukla", n - 10
    else:
        paksha, index = "krishna", n - 25
    name = "Amavasya" if (paksha, index) == ("krishna", 15) else TITHI_NAMES[index - 1]
    return name, paksha, index


def month_of(ym: str) -> dict:
    """A month of cells. October 2026 carries its festivals on the engine's
    dates — Navratri from the 11th, Dussehra on the 20th — and Columbus Day
    on the 12th; any other month carries none."""
    year, month = (int(part) for part in ym.split("-"))
    october = ym == "2026-10"
    days = []
    for n in range(1, 32):
        try:
            when = date(year, month, n)
        except ValueError:
            break
        name, paksha, index = tithi_of(n)
        days.append({
            "date": when.isoformat(),
            "weekday": WEEKDAY_TOKENS[when.weekday()],
            "tithi_short": f"{paksha[0].upper()}{index}",
            # Chaturdashi, the longest name there is, falls on the 24th: it is
            # the one that has to fit a cell with the panel open.
            "tithi_name": name,
            "paksha": paksha,
            "nakshatra": "Chitra",
            "masa": MASA.get(ym, "Ashwin"),
            "flags": ["amavasya"] if n == 10 else (["purnima"] if n == 25 else []),
            # One long name, one short, and one day with two, so the cell's
            # "first word only" rule is measured rather than assumed.
            "observances": (
                (["First Day of Sharad Navratri"] if n == 11 else
                 (["Dussehra", "Ayudha Puja"] if n == 20 else
                  (["Columbus Day"] if n == 12 else [])))
                if october else []
            ),
            "school": {"is_school_day": n != 23 and when.weekday() < 5,
                       "note": "Staff development day" if n == 23 else None},
            "school_kids": ["mira"] if n in (14, 21) else [],
            # Both kids on some days, one on others: the bars under the number.
            "kids": (["mira", "kabir"] if n in (14, 22) else
                     (["kabir"] if n in (5, 17) else
                      (["mira"] if n == 21 else []))),
            "holiday": october and n == 12,
            "family": n in (3, 17, 24),
            "non_veg_ok": when.weekday() not in (1, 3),
            "has_meals": n < 15,
        })
    return {"ym": ym, "days": days}


MONTH = month_of(MONTH_YM)
OCTOBER_MONTH = month_of("2026-10")

PANCHANG_DAY = {
    "date": "2026-10-11",
    "sunrise": "2026-10-11T07:13:00-07:00",
    "sunset": "2026-10-11T18:33:00-07:00",
    "moonrise": "2026-10-11T08:21:00-07:00",
    "moonset": "2026-10-11T18:53:00-07:00",
    "vaara": "Ravivara",
    "tithi": {"name": "Pratipada", "index": 1, "ends_at": "2026-10-11T09:01:00-07:00",
              "paksha": "shukla"},
    "nakshatra": {"name": "Chitra", "index": 14, "ends_at": "2026-10-11T10:02:00-07:00"},
    "yoga": {"name": "Vaidhriti", "index": 27, "ends_at": None},
    "karana": {"name": "Bava", "index": 2, "ends_at": None},
    "masa": {"name": "Ashwin", "adhika": False},
    "samvat": {"vikram": 2083, "shaka": 1948},
    "flags": [],
    "observances": [{"name": "First Day of Sharad Navratri", "kind": "festival",
                     "calendar_id": "india_holidays"}],
    "school": {"is_school_day": False, "note": None},
    "diet": {"non_veg_ok": False, "reasons": ["Sharad Navratri · day 1 of 10"]},
    "meals": {"breakfast": "Pancakes", "lunch": "Dal and rice", "dinner": None},
}

def points(
    kid_id: str, balance: int, week: int, streak: int, saving: list | None = None,
    dollars: int = 0,
) -> dict:
    return {
        "kid_id": kid_id,
        "balance": balance,
        "this_week": week,
        # Monday's share and Tuesday's (the suite's today), so the strip has
        # two bars of different heights and five empty days.
        "week_days": [week - week // 3, week // 3, 0, 0, 0, 0, 0],
        "streak_days": streak,
        "saving_for": saving or [],
        "dollars_owed": dollars,
    }


#: Two bars on the open card: one nearly there and one barely started, so both
#: ends of the arithmetic are on screen and both are measured for height.
SAVING = [
    {"reward_id": "ice_cream", "name": "Ice cream", "glyph": "ice-cream", "cost": 25},
    {"reward_id": "hot_chocolate", "name": "Hot chocolate out", "glyph": "cup", "cost": 40},
]


#: Mira is mid-streak, so the flame is on screen; Kabir is not, so the
#: absence of one is checked too. The jar has enough to be worth drawing.
POINTS = {
    # Fifteen dollars of cash rewards not yet handed over: on his own card,
    # and on the parent's Points, and nowhere on the wall.
    "mira": points("mira", 120, 35, 8, SAVING, dollars=15),
    "kabir": points("kabir", 45, 20, 2),
    "family": points("family", 60, 0, 0),
}

#: The sample family's shop (content.sample/rewards.yaml).
REWARDS = [
    {"id": "ice_cream", "name": "Ice cream", "cost": 25, "fulfilment": "manual",
     "glyph": "ice-cream", "family": False, "enabled": True, "days": None, "minutes": None},
    {"id": "bakery", "name": "Bakery treat", "cost": 40, "fulfilment": "manual",
     "glyph": "cake", "family": False, "enabled": True, "days": None, "minutes": None},
    {"id": "hot_chocolate", "name": "Hot chocolate out", "cost": 40, "fulfilment": "manual",
     "glyph": "cup", "family": False, "enabled": True, "days": None, "minutes": None},
    {"id": "dinner_out", "name": "Dinner out", "cost": 150, "fulfilment": "manual",
     "glyph": "dinner", "family": True, "enabled": True, "days": None, "minutes": None},
    {"id": "allowance_5", "name": "Allowance \u00d7 5 days", "cost": 100, "fulfilment": "allowance",
     "glyph": "coin", "family": False, "enabled": True, "days": 5, "minutes": None},
    {"id": "cash_5", "name": "$5 cash", "cost": 50, "fulfilment": "cash",
     "glyph": "coin", "family": False, "enabled": True, "days": None, "minutes": None,
     "dollars": 5},
    # Screen time: off until the policy plane can enforce it.
    {"id": "roblox_1h", "name": "Roblox +1 h", "cost": 100, "fulfilment": "policy",
     "glyph": "game", "family": False, "enabled": False, "days": None, "minutes": 60},
    {"id": "roblox_2h", "name": "Roblox +2 h", "cost": 175, "fulfilment": "policy",
     "glyph": "game", "family": False, "enabled": False, "days": None, "minutes": 120},
]

MY_REWARDS = [
    {"id": 3, "kid_id": "mira", "reward_id": "ice_cream", "points": 25, "status": "approved",
     "requested_at": f"{TODAY}T09:10:00-07:00", "decided_at": None, "fulfilment_ref": None,
     "note": None, "name": "Ice cream", "glyph": "ice-cream"},
    {"id": 2, "kid_id": "mira", "reward_id": "bakery", "points": 40, "status": "fulfilled",
     "requested_at": f"{TODAY - timedelta(days=2)}T18:00:00-07:00", "decided_at": None,
     "fulfilment_ref": None, "note": None, "name": "Bakery treat", "glyph": "cake"},
]

#: What the picker offers for tomorrow: one everyday dish, one out of reach on
#: a veg day, one treat behind a reward.
# Two cuisines, so the picker's sticky headers are measured rather than
# assumed: catalog order runs in blocks and a header goes in where it changes.
PICK_OPTIONS = [
    # Dinner out: a tile of its own above the list, never one of the dishes.
    {"id": "dinner_out", "name": "Dinner out", "treat": True, "cost": 0, "proteins": ["veg"],
     "pickable": True, "why": None, "cuisine": "Out", "out": True},
    {"id": "veggie_stir_fry", "name": "Veggie stir-fry", "treat": False,
     "cost": 0, "proteins": ["veg", "chicken"], "pickable": True, "why": None,
     "cuisine": "asian"},
    {"id": "tacos", "name": "Tacos", "treat": False, "cost": 0,
     "proteins": ["veg", "chicken"], "pickable": True, "why": None, "cuisine": "mexican"},
    {"id": "khichdi", "name": "Khichdi", "treat": False, "cost": 0,
     "proteins": ["veg"], "pickable": False, "why": "we had this in the last few days",
     "cuisine": "indian"},
    {"id": "pizza_night", "name": "Pizza night", "treat": True, "cost": 25,
     "proteins": ["veg"], "pickable": False, "why": "needs Pick tomorrow's dinner",
     "cuisine": "italian"},
]

APPROVALS = [
    {"kind": "claim", "id": 9, "kid_id": "kabir", "title": "Load the dishwasher",
     "points": 5, "when": f"{TODAY}T17:40:00-07:00", "note": None},
    {"kind": "redemption", "id": 3, "kid_id": "mira", "title": "Ice cream",
     "points": 25, "when": f"{TODAY}T09:10:00-07:00", "note": None},
    {"kind": "claim", "id": 7, "kid_id": "mira", "title": "Homework",
     "points": 10, "when": f"{TODAY}T08:05:00-07:00", "note": None},
]

TODOS = [
    {"ref": "redemption:1", "kind": "manual", "kid_id": "mira", "title": "Ice cream",
     "day": None, "days": None, "due": None},
    {"ref": "allowance:4:2", "kind": "allowance", "kid_id": "kabir", "title": "Allowance",
     "day": 2, "days": 5, "due": TODAY.isoformat()},
    # A cash reward said yes to: "Give Kabir $5", with Paid.
    {"ref": "redemption:6", "kind": "cash", "kid_id": "kabir", "title": "$5 cash",
     "day": None, "days": None, "due": None, "dollars": 5},
]

ROUTES = {
    "/api/version": {"version": 1, "changed_at": None},
    "/api/places/recent": ["Taqueria Luna", "Corner Trattoria", "Grandma's house"],
    "/api/config": CONFIG,
    "/api/today": DAY,
    "/api/agenda": [DAY, TOMORROW_DAY, later(DAY, 2), later(DAY, 3)],
    "/api/weather": WEATHER,
    "/api/health": {"status": "ok", "version": "design", "time": f"{TODAY}T09:00:00-07:00"},
    "/api/photos": PHOTOS,
    "/api/panchang/month": MONTH,
    "/api/panchang": PANCHANG_DAY,
    "/api/points/mira": POINTS["mira"],
    "/api/points/kabir": POINTS["kabir"],
    "/api/points/family": POINTS["family"],
    "/api/kids/pins": {"pins": {"mira": False, "kabir": False}},
    "/api/approvals/count": {"pending": 3},
    "/api/rewards": REWARDS,
    "/api/redemptions/mira": MY_REWARDS,
    "/api/redemptions/kabir": [],
    "/api/picks/options": PICK_OPTIONS,
    "/api/parent/approvals": APPROVALS,
    "/api/parent/todos": TODOS,
    "/api/parent/session": {"ok": True},
}


# -- the day budgets ---------------------------------------------------------
#
# The dashboard at the edges of what it has to hold: no family events, two,
# and five (more than the strip has room for), and a child with four agenda
# rows (one more than a card draws). Each on a Tuesday — the shared fixture —
# and on a Wednesday, which is the family's real week: Kabir swims, Dad is
# out at Hammer & Nails, somebody picks up Kevin, and Kabir chose dinner.

WEDNESDAY = date(2026, 9, 23)
THURSDAY = WEDNESDAY + timedelta(days=1)

#: Five, each with a start: past the width of the strip at either size, so
#: the "+N" pill is what is measured.
FAMILY_FIVE = [
    row("Hammer & Nails [Dad]", "10:30", "12:00"),
    row("Pickup Kevin", "13:30", None),
    row("Costco run [Mum]", "16:00", "17:00"),
    row("Dinner with grandparents", "18:30", "19:30"),
    row("Back to school night", "19:00", "20:30"),
]

#: Mira's day with a fourth row, so the card has to count one away.
FOUR_ROWS = [
    row("Cross Country meet @ Bayside Middle", "15:00", "17:00", "school"),
    row("Piano", "16:00", "16:45", where="Ms. Lee's"),
    row("6th Grade Band practice @ Bayside Middle", "16:30", "18:00", "school"),
    row("Soccer practice", "18:30", "19:30", where="Oak field"),
]

WED_WEATHER = {
    **WEATHER,
    "tomorrow": {**WEATHER["tomorrow"], "high": 91, "low": 60,
                 "sunrise": f"{THURSDAY}T07:00", "sunset": f"{THURSDAY}T18:59"},
}

WED_DAY = {
    **DAY,
    "date": WEDNESDAY.isoformat(),
    "weekday": "wed",
    "kids": [
        kid("mira", "Mira", "#1F8A8A", "fox",
            [row("Cross Country meet @ Bayside Middle", "15:00", "17:00", "school"),
             row("Piano", "16:00", "16:45", where="Ms. Lee's")],
            [task("hw", "Homework", "claimed", claim_id=1),
             task("outside", "30 minutes outside"),
             task("room", "Tidy room", routine="morning")]),
        kid("kabir", "Kabir", "#D97706", "panda",
            [row("Swim", "17:00", "18:00", where="Aquatic center")],
            [task("hw", "Homework", "approved"),
             task("outside", "30 minutes outside", "approved"),
             task("dishes", "Load the dishwasher", routine="evening")]),
    ],
    "family_agenda": FAMILY_FIVE[:2],
    "meals": {
        "breakfast": {
            "name": "Pancakes", "note": None, "kids_protein": "veg",
            "id": None, "picked_by": [], "confirmed": True,
        },
        "lunch": {
            "name": "Dal and rice", "note": "Lunchbox", "kids_protein": "veg",
            "id": None, "picked_by": [], "confirmed": True,
        },
        "dinner": {
            "name": "Pizza night", "note": None, "kids_protein": "veg",
            "id": "pizza_night", "picked_by": ["kabir"], "confirmed": True,
        },
        "snack": None,
    },
    "observances": [],
    "diet": {"non_veg_ok": True, "reasons": []},
    "weather": WED_WEATHER,
}

#: An ordinary school Thursday: no school chip, and a count of what is on —
#: and a dinner the children want different things for, which the wall
#: shows as both faces and "Mom or Dad picks".
THU_DAY = {
    **WED_DAY,
    "date": THURSDAY.isoformat(),
    "weekday": "thu",
    "family_agenda": [row("Library", "10:30", "11:30")],
    "meals": {
        **WED_DAY["meals"],
        "dinner": {
            "name": "Khichdi", "note": None, "kids_protein": "veg",
            "id": "khichdi", "picked_by": ["kabir", "mira"], "confirmed": False,
            "plan": "khichdi",
            "picks": {"kabir": {"id": "pizza_night", "kids_protein": "veg"},
                      "mira": {"id": "tacos", "kids_protein": "veg"}},
        },
    },
}


def pick_row(pick_id: int, kid_id: str, day: date, slot: str, dish: str, name: str,
             **extra: object) -> dict:
    return {
        "id": pick_id, "kid_id": kid_id, "date": day.isoformat(), "slot": slot,
        "dish_id": dish, "kids_protein": "veg", "status": "chosen", "decided_by": None,
        "decided_at": None, "moved_to": None, "created_at": f"{day}T09:00:00-07:00",
        "note": None, "name": name, "treat": False, **extra,
    }


def slot_view(day: date, slot: str, plan: str | None, picks: list, *,
              contested: bool = False, locked: bool = False) -> dict:
    planned = None if plan is None else {
        "name": plan, "note": None, "kids_protein": "veg", "id": None, "picked_by": [],
        "confirmed": True, "plan": None, "picks": {}}
    return {
        "date": day.isoformat(), "slot": slot, "plan": planned, "picks": picks,
        "resolved": planned, "contested": contested, "locked": locked, "decided": False,
    }


def week_of_picks(start: date) -> list:
    """Seven days from `start`: the first breakfast locked, Kabir's lunch the
    day after, and the day after that a dinner the two of them disagree on."""
    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        breakfast = slot_view(day, "breakfast", "Pancakes", [], locked=offset == 0)
        lunch = slot_view(
            day, "lunch", "Dal and rice",
            [pick_row(10, "kabir", day, "lunch", "grilled_cheese", "Grilled cheese")]
            if offset == 1 else [],
        )
        if offset == 1:
            lunch["resolved"] = {**lunch["plan"], "name": "Grilled cheese",
                                 "picked_by": ["kabir"]}
        dinner = slot_view(
            day, "dinner", "Khichdi",
            [pick_row(11, "kabir", day, "dinner", "pizza_night", "Pizza night"),
             pick_row(12, "mira", day, "dinner", "tacos", "Tacos")]
            if offset == 1 else [],
            contested=offset == 1,
        )
        if offset == 4:
            # Dinner out, somewhere: the strip reads "Out · Taqueria Luna".
            out = {**dinner["plan"], "name": "Dinner out", "id": "dinner_out",
                   "note": "Taqueria Luna"}
            dinner = {**dinner, "plan": out, "resolved": out}
        days.append({"date": day.isoformat(), "breakfast": breakfast, "lunch": lunch,
                     "dinner": dinner})
    return days


#: The shared fixture's week of picks, from the Tuesday it is set on.
ROUTES["/api/picks"] = week_of_picks(TODAY)


def day_api(
    base: dict, tomorrow: dict, weather: dict, family: list, mira: list | None = None
) -> dict:
    """The three paths a dashboard state answers differently."""
    kids = base["kids"]
    if mira is not None:
        kids = [{**kids[0], "agenda": mira}, *kids[1:]]
    today = {**base, "family_agenda": family, "kids": kids}
    return {
        "/api/today": today,
        "/api/agenda": [today, tomorrow, later(today, 2), later(today, 3)],
        "/api/weather": weather,
        "/api/picks": week_of_picks(date.fromisoformat(today["date"])),
    }


def body_for(path: str, overrides: dict | None = None) -> bytes | None:
    """The stubbed body for a path, with this state's overrides on top.

    A state that needs different data — an empty balance, say — says so in
    its own definition rather than by forking the fixture, so the fixture
    stays one description of this family.
    """
    if overrides and path in overrides:
        return json.dumps(overrides[path]).encode()
    found = ROUTES.get(path)
    return None if found is None else json.dumps(found).encode()


#: A balance with nothing in it: the state every child starts in, and the one
#: the shop was worst at. Nine tiles at 40% saying "N more" is nine refusals.
BROKE = points("mira", 0, 0, 0)

#: Fifteen buys exactly one thing on the list, which is the other end of the
#: same screen: the shop filters to it, and the toggle is the way to the rest.
NEARLY = points("mira", 15, 15, 1)

#: Mira's day as it actually stands: to-dos in two routines, one waiting,
#: one done, one a parent's — seven of them, and the first five.
SEVEN_TASKS = [
    task("hw", "Homework", "claimed", claim_id=1),
    task("outside", "30 minutes outside"),
    task("reading", "Reading, 20 minutes"),
    task("piano", "Piano practice", "approved", claim_id=4),
    task("dishes", "Load the dishwasher", routine="evening"),
    task("bag", "Pack the school bag", routine="evening"),
    task("trash", "Take out the trash", claim="parent", routine="evening"),
]


#: A Thursday with the week's jobs on it: Math homework approved on Tuesday,
#: still done today; Kabir's still to do this week, marked so.
WEEKLY_DAY = {
    **DAY,
    "kids": [
        {**DAY["kids"][0], "tasks": [
            task("math", "Math homework", "approved", claim_id=3, every="week"),
            task("shw", "School Homework"),
            task("outside", "30 min outside"),
        ]},
        {**DAY["kids"][1], "tasks": [
            task("math", "Math homework", every="week"),
            task("shw", "School Homework", "claimed", claim_id=4),
        ]},
    ],
}


def tasks_day(count: int) -> dict:
    return {**DAY, "kids": [{**DAY["kids"][0], "tasks": SEVEN_TASKS[:count]}, DAY["kids"][1]]}



#: 8 am on a Saturday: no school, one practice, and Mira's five to-dos in
#: every state a chip has — "Tidy room" approved, "30 min outside" waiting,
#: one declined, one a parent's, one open.
SATURDAY = date(2026, 10, 3)
SAT_DAY = {
    **DAY,
    "date": SATURDAY.isoformat(),
    "weekday": "sat",
    "is_school_day": False,
    "school_note": None,
    "kids": [
        {
            **DAY["kids"][0],
            "agenda": [row("Soccer", "09:00", "10:00", where="Oak field")],
            "tasks": [
                task("bed", "Make your bed", routine="morning"),
                task("room", "Tidy room", "approved", routine="morning", claim_id=5),
                task("outside", "30 min outside", "claimed", claim_id=6),
                task("reading", "Reading", "declined", claim_id=7),
                task("plants", "Water the plants", claim="parent", routine="evening"),
            ],
        },
        {**DAY["kids"][1], "agenda": [], "tasks": DAY["kids"][1]["tasks"]},
    ],
    "family_agenda": [],
}

#: Twenty-five: a handful affordable and most not, the shop's ordinary middle.
TWENTY_FIVE = points("mira", 25, 25, 1)

#: Mira's card once a parent has answered: a yes, a no, and one still to do.
ANSWERED_DAY = {
    **DAY,
    "kids": [
        {
            **DAY["kids"][0],
            "tasks": [
                task("hw", "Homework", "approved", claim_id=1),
                task("outside", "30 minutes outside", "declined", claim_id=3),
                task("room", "Tidy room", routine="morning"),
            ],
        },
        DAY["kids"][1],
    ],
}


# -- the parent screen -------------------------------------------------------
#
# Every section's data, as the API sends it, for a parent signed in with eight
# minutes left. The week has one contested dinner (Thursday: Kabir chose pizza
# night, Mira tacos, over the plan's khichdi) so "Parents decide" is on
# the grid, in Approvals, and in the sheet.

WEEK_START = TODAY - timedelta(days=TODAY.weekday())

DISHES = [
    ("pancakes", "Pancakes"),
    ("dal_rice", "Dal and rice"),
    ("veggie_stir_fry", "Veggie stir-fry"),
    ("pizza_night", "Pizza night"),
    ("tacos", "Tacos"),
    ("khichdi", "Khichdi"),
]


def cell(
    name: str = "", dish_id: str = "", note: str = "", picked_by: list | None = None,
    confirmed: bool = True, plan_name: str = "", contested: bool = False,
    choices: list | None = None,
) -> dict:
    return {
        "name": name, "note": note, "id": dish_id, "picked_by": picked_by or [],
        "confirmed": confirmed, "plan_name": plan_name, "contested": contested,
        "choices": choices or [],
    }


CONTESTED = cell(
    "Pizza night", "pizza_night", picked_by=["kabir", "mira"], confirmed=False,
    plan_name="Khichdi", contested=True,
    choices=[
        {"id": "pizza_night", "name": "Pizza night", "kids": ["kabir"]},
        {"id": "tacos", "name": "Tacos", "kids": ["mira"]},
    ],
)

PARENT_WEEK = [
    {
        "date": (TODAY + timedelta(days=offset)).isoformat(),
        "breakfast": cell("Pancakes", "pancakes"),
        "lunch": cell("Dal and rice", "dal_rice", note="Lunchbox"),
        "dinner": (
            CONTESTED if offset == 2 else
            cell("Veggie stir-fry", "veggie_stir_fry",
                 picked_by=["mira"], plan_name="Khichdi")
            if offset == 1 else
            cell("Dinner out", "dinner_out", note="Taqueria Luna")
            if offset == 4 else
            cell("Tacos", "tacos")
        ),
    }
    for offset in range(7)
]

PARENT_APPROVALS = [
    {"kind": "meal", "id": 0, "kid_id": "kabir", "title": "Thursday dinner", "points": 0,
     "when": f"{WEEK_START + timedelta(days=3)}T00:00:00", "note": None,
     "date": (WEEK_START + timedelta(days=3)).isoformat(), "slot": "dinner",
     "choices": CONTESTED["choices"], "plan_name": "Khichdi", "contested": True},
    *[{**item, "date": None, "slot": None, "choices": [], "plan_name": None, "contested": False}
      for item in APPROVALS],
]

PARENT_SETTINGS = {
    "night_start": "22:00", "night_end": "05:30", "idle_minutes": 3, "night_idle_minutes": 5,
    "night_frame": True, "slide_seconds": 20, "refresh_minutes": 5,
    "diet": {
        "non_veg_days": ["mon", "wed", "fri", "sat", "sun"],
        "festivals": [
            {"match": "navaratri", "span_days": 10},
            {"match": "navratri", "span_days": 10},
            {"match": "dussehra", "span_days": 1},
            {"match": "karwa chauth", "span_days": 1},
            {"match": "karaka chaturthi", "span_days": 1},
        ],
        # Five aliases, three festivals: the card draws the three.
        "groups": [
            {"name": "Navratri", "span_days": 10, "matches": ["navaratri", "navratri"]},
            {"name": "Dussehra", "span_days": 1, "matches": ["dussehra"]},
            {"name": "Karwa Chauth", "span_days": 1,
             "matches": ["karwa chauth", "karaka chaturthi"]},
        ],
        "extra_dates": [{"from": "2026-11-01", "to": "2026-11-03", "name": "Chhath"}],
    },
    "points": {"streak_bonus": 20, "streak_days": 7, "roblox_per_week": 2, "deductions": False,
               "parent_idle_minutes": 2},
    "kids": [
        {"id": "mira", "name": "Mira", "avatar": "fox", "color": "#1F8A8A"},
        {"id": "kabir", "name": "Kabir", "avatar": "panda", "color": "#D97706"},
    ],
}

CALENDAR_ROWS = [
    {"id": "mira", "kind": "kid", "kid": "mira", "state": "ok",
     "fetched_at": f"{TODAY}T15:26:00-07:00", "detail": "42 events", "env": "MANTEL_CAL_MIRA"},
    {"id": "kabir", "kind": "kid", "kid": "kabir", "state": "not_configured",
     "fetched_at": None, "detail": "", "env": "MANTEL_CAL_KABIR"},
    {"id": "family", "kind": "family", "kid": "family", "state": "ok",
     "fetched_at": f"{TODAY}T15:26:00-07:00", "detail": "12 events", "env": "MANTEL_CAL_FAMILY"},
    {"id": "us_holidays", "kind": "holiday", "kid": None, "state": "ok",
     "fetched_at": f"{TODAY}T09:00:00-07:00", "detail": "180 events", "env": None},
    {"id": "india_holidays", "kind": "festival", "kid": None, "state": "stale",
     "fetched_at": f"{TODAY - timedelta(days=2)}T09:00:00-07:00",
     "detail": "ConnectTimeout: timed out", "env": None},
    {"id": "district", "kind": "school", "kid": "family", "state": "ok",
     "fetched_at": f"{TODAY}T15:00:00-07:00", "detail": "310 events", "env": None},
    {"id": "bayside", "kind": "school", "kid": "mira", "state": "ok",
     "fetched_at": f"{TODAY}T15:00:00-07:00", "detail": "96 events", "env": None},
    {"id": "sunset", "kind": "school", "kid": "kabir", "state": "error",
     "fetched_at": None, "detail": "HTTPStatusError: 404", "env": None},
]


def series(key: str, title: str, school: str, shown: list, always: bool = False) -> dict:
    day = (TODAY + timedelta(days=5)).isoformat()
    return {
        "series": key, "title": title, "count": 3, "next_date": day, "rule": None,
        "always": always, "shown_to": shown,
        "events": [{"title": title, "date": day, "start": "15:00", "end": "16:00",
                    "where": None, "calendar_id": school}],
    }


SCHOOL_SERIES = [
    series("minimum-day", "Minimum Day", "district", ["mira", "kabir"], always=True),
    series("xc-meet", "Cross Country meet", "bayside", ["mira"]),
    series("band-practice", "6th Grade Band practice", "bayside", []),
    series("book-fair", "Scholastic Book Fair", "sunset", ["kabir"]),
]

LEDGER = [
    {"id": 20 - n, "kid_id": "mira" if n % 2 else "kabir", "delta": -30 if n == 3 else 10,
     "reason_kind": "redeem" if n == 3 else "task", "reason_ref": None,
     "note": "Ice cream" if n == 3 else "Homework", "actor": "parent" if n % 3 else "kid",
     "created_at": f"{TODAY - timedelta(days=n // 3)}T1{n % 9}:00:00-07:00"}
    for n in range(12)
]

DIGEST = {
    "week": "2026-W40", "start": WEEK_START.isoformat(),
    "end": (WEEK_START + timedelta(days=6)).isoformat(),
    "kids": [
        {"kid_id": "mira", "name": "Mira", "earned": 35, "spent": 30,
         "approved": {TODAY.isoformat(): ["Homework", "30 minutes outside"]},
         "redemptions": ["Ice cream"], "picks": ["Tacos"]},
        {"kid_id": "kabir", "name": "Kabir", "earned": 20, "spent": 0,
         "approved": {}, "redemptions": [], "picks": ["Pizza night"]},
    ],
}

DIET_WEEK = [
    {"date": (WEEK_START + timedelta(days=offset)).isoformat(),
     "non_veg_ok": offset % 7 not in (1, 3),
     "reasons": [] if offset % 7 not in (1, 3) else (
         ["Thursday"] if offset % 7 == 3 else ["Tuesday"])}
    for offset in range(-10, 17)
]

PICK_ALL = [
    {**option, "pickable": True, "why": None} for option in PICK_OPTIONS
] + [{"id": "paneer_tikka", "name": "Paneer tikka", "treat": False, "cost": 0,
      "proteins": ["chicken"], "pickable": False, "why": "not a meat day",
      "cuisine": "indian", "yesterday": False}]

PARENT_ROUTES = {
    "/api/parent/session": {"open": True, "expires_in": 480},
    "/api/parent/approvals": PARENT_APPROVALS,
    "/api/parent/meals": PARENT_WEEK,
    "/api/parent/meals/options": PICK_ALL,
    "/api/parent/settings": PARENT_SETTINGS,
    "/api/parent/calendars": CALENDAR_ROWS,
    "/api/parent/school-events": SCHOOL_SERIES,
    "/api/parent/ledger": LEDGER,
    "/api/parent/payouts": [
        {"id": 2, "kid_id": "mira", "dollars": 5, "paid_at": f"{TODAY}T18:00:00-07:00",
         "note": "redemption:5"},
    ],
    "/api/parent/about": {"version": "design", "lan_url": "http://<mac-ip>:8000/",
                          "launchd": "com.mantel.api running (pid 4242)", "upload_token": True},
    "/api/digest": DIGEST,
    "/api/diet": DIET_WEEK,
    "/api/photos": [{**photo, "bytes": 1_450_000} for photo in PHOTOS],
    "/api/health": {
        "status": "ok", "version": "design", "time": f"{TODAY}T15:30:00-07:00",
        "content": {"family": "ok", "settings": "ok", "meals": "ok"},
        "weather": "ok (4m ago)",
        "calendars": {row["id"]: ("ok (4m ago), 42 events" if row["state"] == "ok" else
                                  row["detail"] or "not configured") for row in CALENDAR_ROWS},
        "school_year": "ok (2026–27)", "diet_days": "ok (60 days)",
        "ledger": "ok (schema 4, 120 rows)", "reload_at": None,
    },
}
