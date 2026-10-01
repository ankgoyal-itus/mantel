"""Turning a photo's coordinates into a place name, without asking anybody.

A caption that says "Lake Tahoe · June 2024" is worth having; one that needs
the internet to say it is not, because the frame is the screen most likely to
be running while the house is offline and it is the screen nobody would think
to check. So the whole gazetteer is a file in this package: 34,167 places,
every city on Earth over fifteen thousand people, as name, latitude to two
decimals, longitude, country.

Two decimals is about a kilometre, which is far finer than "which town is
this" needs, and it halves the file. The rows are sorted by latitude so a
lookup walks a band rather than the world.

The hard rule is the distance cap. The nearest city to a photo taken in the
Sierra can be sixty kilometres away, and a caption naming it would not be
vague, it would be wrong — one town captioned as the next one over is a lie
about where the family was. Past the cap there is simply no place, and the caption is the
month and the year, which is what it was before this existed.

Data: GeoNames (geonames.org), CC BY 4.0. Attribution is in the README.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).with_name("data") / "cities.tsv"

#: Past this, a photo gets no place at all. A name 60km away is not a vaguer
#: answer than the right one, it is a different answer.
MAX_KM = 30.0

#: Degrees of latitude that could hold anything inside MAX_KM, with room to
#: spare. One degree is about 111km.
BAND = MAX_KM / 111.0 + 0.02


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float
    country: str


@lru_cache(maxsize=1)
def _table() -> tuple[list[Place], list[float]]:
    """The gazetteer, read once and kept. Missing, it is simply empty."""
    places: list[Place] = []
    try:
        text = DATA.read_text(encoding="utf-8")
    except OSError:
        return [], []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        try:
            places.append(Place(parts[0], float(parts[1]), float(parts[2]), parts[3]))
        except ValueError:
            continue
    return places, [place.lat for place in places]


def loaded() -> int:
    """How many places are in hand, for /api/health to say."""
    return len(_table()[0])


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular, which is accurate to well under a kilometre at 30km."""
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return math.hypot(x, y) * 6371.0


def nearest(lat: float, lon: float, within_km: float = MAX_KM) -> Place | None:
    """The closest place, or None when the closest is too far to name.

    The bisect narrows to a band of latitudes first: without it this is 34,000
    trigonometric distances per photo, which the frame does every twenty
    seconds on a ten-year-old iPad's worth of CPU.
    """
    places, latitudes = _table()
    if not places:
        return None
    low = bisect.bisect_left(latitudes, lat - BAND)
    high = bisect.bisect_right(latitudes, lat + BAND)

    best: Place | None = None
    closest = within_km
    for place in places[low:high]:
        away = _km(lat, lon, place.lat, place.lon)
        if away <= closest:
            best, closest = place, away
    return best


def name_for(lat: float | None, lon: float | None) -> str | None:
    """The caption's place, or None. Anything unusable is None, never a guess."""
    if lat is None or lon is None:
        return None
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None
    # 0,0 is the Atlantic, and it is what a camera writes when it has no fix.
    if abs(lat) < 0.01 and abs(lon) < 0.01:
        return None
    found = nearest(lat, lon)
    return found.name if found is not None else None
