"""The sample family, made into a home.

content.sample/ is a fictional family — Mira and Kabir, in Half Moon Bay —
written as templates: `{{today}}`, `{{today+3}}`, `{{today-7}}` and
`{{tomorrow}}` stand for dates, because a dashboard only ever shows the week
it is run in. `make_home` renders it into a MANTEL_HOME for whoever needs
one — the demo, the smoke suite, the API tests — and writes the sample's
calendars beside it as local ICS files, dated from the same today, so none of
them needs the network.
"""

from __future__ import annotations

import io
import math
import re
import shutil
from datetime import date as Date
from datetime import timedelta
from pathlib import Path

#: Found from the code, not from MANTEL_ROOT: a run with its root somewhere
#: temporary still renders the sample that ships with this checkout.
SAMPLE_DIR = Path(__file__).resolve().parents[3] / "content.sample"

_DATE = re.compile(r"\{\{\s*(today|tomorrow)\s*(?:([+-])\s*(\d+))?\s*\}\}")


def render(text: str, today: Date) -> str:
    """Fill in every date placeholder, relative to `today`."""

    def one(match: re.Match[str]) -> str:
        offset = 1 if match.group(1) == "tomorrow" else 0
        if match.group(3):
            step = int(match.group(3))
            offset += step if match.group(2) == "+" else -step
        return (today + timedelta(days=offset)).isoformat()

    return _DATE.sub(one, text)


def _stamp(day: Date, hhmm: str | None = None) -> str:
    return day.strftime("%Y%m%d") + (f"T{hhmm.replace(':', '')}00" if hhmm else "")


#: One event: its day, start and end ("HH:MM", or None all day), title, where.
Event = tuple[Date, str | None, str | None, str, str | None]


def _calendar(name: str, events: list[Event]) -> str:
    """A small ICS file. Times are floating: local to the house, as a
    calendar app writes them for an event in its own timezone."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Mantel//sample//EN",
        f"X-WR-CALNAME:{name}",
    ]
    for index, (day, start, end, title, where) in enumerate(events):
        lines += ["BEGIN:VEVENT", f"UID:{name.lower().replace(' ', '-')}-{index}@mantel.sample"]
        if start is None:
            lines += [
                f"DTSTART;VALUE=DATE:{_stamp(day)}",
                f"DTEND;VALUE=DATE:{_stamp(day + timedelta(days=1))}",
            ]
        else:
            lines += [f"DTSTART:{_stamp(day, start)}", f"DTEND:{_stamp(day, end or start)}"]
        lines.append(f"SUMMARY:{title}")
        if where:
            lines.append(f"LOCATION:{where}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def calendars_for(today: Date) -> dict[str, str]:
    """The sample's four feeds, dated from `today`: the family's, one school
    per child, and a festivals feed with two festivals in the coming week,
    so the vegetarian-day rule has something to show."""

    def day(offset: int) -> Date:
        return today + timedelta(days=offset)

    return {
        "family.ics": _calendar(
            "Family",
            [
                (day(0), "18:30", "20:00", "Dinner with grandparents", None),
                (day(2), "09:00", "10:00", "Dentist [Mum]", "Coastside Dental"),
                (day(5), "10:00", "12:00", "Farmers market", None),
            ],
        ),
        "school-mira.ics": _calendar(
            "Seaview Elementary",
            [
                (day(1), "15:30", "17:00", "Cross country meet @ Seaview", None),
                (day(3), None, None, "Picture day", None),
                (day(4), None, None, "Minimum day", None),
            ],
        ),
        "school-kabir.ics": _calendar(
            "Bayside Middle",
            [
                (day(0), "15:15", "16:15", "Band practice", "Music room"),
                (day(3), None, None, "Picture day", None),
                (day(7), "15:15", "16:15", "Band practice", "Music room"),
            ],
        ),
        "festivals.ics": _calendar(
            "Festivals",
            [(day(2), None, None, "Diwali", None), (day(6), None, None, "Janmashtami", None)],
        ),
    }


def write_calendars(folder: Path, today: Date) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in calendars_for(today).items():
        target = folder / name
        target.write_text(text, encoding="utf-8")
        written.append(target)
    return written


#: Eight skies over a horizon, for the photo frame: (top, bottom, ground).
_SKIES = [
    ((28, 64, 110), (242, 170, 120), (38, 52, 44)),
    ((12, 30, 60), (90, 120, 170), (22, 30, 40)),
    ((70, 130, 190), (200, 225, 240), (60, 92, 60)),
    ((120, 60, 110), (250, 190, 140), (50, 40, 50)),
    ((20, 80, 90), (160, 210, 200), (30, 60, 55)),
    ((200, 120, 60), (255, 220, 160), (80, 60, 40)),
    ((40, 40, 70), (150, 140, 190), (30, 30, 45)),
    ((90, 150, 200), (235, 240, 245), (140, 130, 110)),
]


def sample_photo(index: int, width: int = 2048, height: int = 1536) -> bytes:
    """A gradient sky, a soft sun and a horizon, as a JPEG. Placeholders
    that look like photographs from across a room and are nobody's."""
    from PIL import Image, ImageDraw, ImageFilter

    top, bottom, ground = _SKIES[index % len(_SKIES)]
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    horizon = int(height * (0.58 + 0.08 * math.sin(index)))
    for y in range(horizon):
        t = y / max(1, horizon - 1)
        colour = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True))
        draw.line([(0, y), (width, y)], fill=colour)
    sun_x = int(width * (0.25 + 0.5 * ((index * 37) % 10) / 10))
    radius = int(height * 0.06)
    draw.ellipse(
        [sun_x - radius, horizon - radius * 2, sun_x + radius, horizon],
        fill=tuple(min(255, c + 40) for c in bottom),
    )
    for y in range(horizon, height):
        t = (y - horizon) / max(1, height - horizon)
        colour = tuple(round(c * (1 - 0.4 * t)) for c in ground)
        draw.line([(0, y), (width, y)], fill=colour)
    image = image.filter(ImageFilter.GaussianBlur(2))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=85)
    return out.getvalue()


def write_photos(folder: Path, count: int = 8) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for index in range(count):
        target = folder / f"sample-{index + 1}.jpg"
        target.write_bytes(sample_photo(index))
        written.append(target)
    return written


def make_home(dest: Path, today: Date, *, source: Path = SAMPLE_DIR) -> Path:
    """Render the sample into `dest` as a MANTEL_HOME: content/ with its
    dates filled in and its calendars written. Returns `dest`."""
    content = dest / "content"
    content.mkdir(parents=True, exist_ok=True)
    for template in sorted(source.glob("*.yaml")):
        text = render(template.read_text(encoding="utf-8"), today)
        (content / template.name).write_text(text, encoding="utf-8")
    write_calendars(content / "calendars", today)
    return dest


def fresh_home(dest: Path, today: Date) -> Path:
    """`make_home` into an empty directory, clearing whatever was there."""
    if dest.exists():
        shutil.rmtree(dest)
    return make_home(dest, today)
