"""The panchang: a Hindu almanac day, computed here rather than fetched.

Everything comes from the Swiss Ephemeris through pyswisseph, using its
built-in Moshier model so there are no data files to ship or download. The
iPad may be offline for minutes; the almanac never depends on anything but
this Mac's clock.

The five limbs, all read **at local sunrise**, which is what makes a panchang
day a day rather than a midnight-to-midnight window:

    vaara      the weekday
    tithi      moon minus sun, in 12° steps: 30 to a lunar month
    nakshatra  the moon's own position, in 13°20' steps: 27 to a circle
    yoga       moon plus sun, also in 13°20' steps
    karana     half a tithi, 6°, cycling through eleven names

Sidereal (nirayana) longitudes throughout, with the Lahiri ayanamsa.

Algorithms follow the approach of the drik-panchanga project
(https://github.com/webresh/drik-panchanga, AGPL-3.0) — the sunrise-anchored
day, the solar-rasi-at-conjunction rule for naming a month, and the
two-conjunctions-in-one-rasi test for an adhika masa. The code here is our
own: end times are found by bisection on the angle rather than by Lagrange
interpolation, which holds up across the 360° wrap without special cases. See
the README for the licence note.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as Date
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe
from pydantic import BaseModel, ValidationError

from .paths import cache_dir

logger = logging.getLogger("mantel_api.panchang")

# Moshier: accurate to well under a second of arc for the sun and moon over
# these centuries, and entirely self-contained.
EPHEMERIS = swe.FLG_SWIEPH | swe.FLG_MOSEPH
SIDEREAL = EPHEMERIS | swe.FLG_SIDEREAL

TITHI_DEGREES = 12.0
NAKSHATRA_DEGREES = 360.0 / 27.0
YOGA_DEGREES = 360.0 / 27.0
KARANA_DEGREES = 6.0

#: The moon gains on the sun by about 12.2° a day, so no limb lasts two days.
SEARCH_DAYS = 2.0
BISECTIONS = 48

TITHI_NAMES = (
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi",
)

NAKSHATRA_NAMES = (
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
)

YOGA_NAMES = (
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata",
    "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti",
)

#: The seven moving karanas repeat eight times, wrapped by four fixed ones.
MOVING_KARANAS = ("Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti")
FIXED_KARANAS = ("Kimstughna", "Shakuni", "Chatushpada", "Naga")

VAARA_NAMES = (
    "Ravivara", "Somavara", "Mangalavara", "Budhavara",
    "Guruvara", "Shukravara", "Shanivara",
)

MASA_NAMES = (
    "Chaitra", "Vaisakha", "Jyeshtha", "Ashadha", "Shravana", "Bhadrapada",
    "Ashwin", "Kartik", "Margashirsha", "Pausha", "Magha", "Phalguna",
)

RASI_NAMES = (
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena",
)

#: Julian day of the Kali Yuga epoch, from which the era years are counted.
KALI_EPOCH_JD = 588465.5
SIDEREAL_YEAR_DAYS = 365.25636
SHAKA_FROM_KALI = 3179
VIKRAM_FROM_SHAKA = 135

_CONFIGURED = False


def _configure() -> None:
    """Set the ephemeris once. swisseph keeps this state globally."""
    global _CONFIGURED
    if not _CONFIGURED:
        swe.set_ephe_path(None)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        _CONFIGURED = True


@dataclass(frozen=True)
class Place:
    lat: float
    lon: float
    timezone: str
    altitude: float = 0.0

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def _longitude(jd: float, body: int) -> float:
    _configure()
    return float(swe.calc_ut(jd, body, SIDEREAL)[0][0])


def sun_longitude(jd: float) -> float:
    return _longitude(jd, swe.SUN)


def moon_longitude(jd: float) -> float:
    return _longitude(jd, swe.MOON)


def elongation(jd: float) -> float:
    """Moon minus sun, 0 at conjunction and 180 at opposition."""
    return (moon_longitude(jd) - sun_longitude(jd)) % 360.0


def yoga_angle(jd: float) -> float:
    return (moon_longitude(jd) + sun_longitude(jd)) % 360.0


def to_jd(when: datetime) -> float:
    """A timezone-aware datetime as a Julian day in universal time."""
    utc = when.astimezone(UTC)
    hours = utc.hour + utc.minute / 60 + utc.second / 3600 + utc.microsecond / 3.6e9
    return float(swe.julday(utc.year, utc.month, utc.day, hours, swe.GREG_CAL))


def from_jd(jd: float, zone: ZoneInfo) -> datetime:
    year, month, day, hours = swe.revjul(jd, swe.GREG_CAL)
    midnight = datetime(int(year), int(month), int(day), tzinfo=UTC)
    return (midnight + timedelta(hours=float(hours))).astimezone(zone)


def _rise_or_set(jd_start: float, body: int, rising: bool, place: Place) -> float | None:
    _configure()
    flag = swe.CALC_RISE if rising else swe.CALC_SET
    if body == swe.SUN:
        # The sunrise a panchang means is the centre of the disc on the
        # horizon, not the first glint of the limb.
        flag |= swe.BIT_DISC_CENTER
    result, times = swe.rise_trans(
        jd_start, body, flag, (place.lon, place.lat, place.altitude), 0, 0, EPHEMERIS
    )
    if result < 0:
        return None
    moment = float(times[0])
    # Above the Arctic circle the sun can simply not rise; nothing here does,
    # but a missing event must read as missing rather than as midnight.
    return moment if moment > 0 else None


def day_start_jd(day: Date, place: Place) -> float:
    """Local midnight, as the Julian day the rise/set search starts from."""
    return to_jd(datetime(day.year, day.month, day.day, tzinfo=place.zone))


def sunrise(day: Date, place: Place) -> datetime | None:
    jd = _rise_or_set(day_start_jd(day, place), swe.SUN, True, place)
    return from_jd(jd, place.zone) if jd is not None else None


def sunset(day: Date, place: Place) -> datetime | None:
    jd = _rise_or_set(day_start_jd(day, place), swe.SUN, False, place)
    return from_jd(jd, place.zone) if jd is not None else None


def moonrise(day: Date, place: Place) -> datetime | None:
    jd = _rise_or_set(day_start_jd(day, place), swe.MOON, True, place)
    return from_jd(jd, place.zone) if jd is not None else None


def moonset(day: Date, place: Place) -> datetime | None:
    jd = _rise_or_set(day_start_jd(day, place), swe.MOON, False, place)
    return from_jd(jd, place.zone) if jd is not None else None


def _crossing(
    jd: float, target: float, angle_of: Callable[[float], float], step_days: float
) -> float | None:
    """When the angle next reaches `target`, by bisection.

    The angles here only ever increase, modulo 360, so the bracket is the
    first sampled step where the distance still to go stops shrinking — which
    is exactly where the angle passed the target and wrapped.
    """
    def remaining(at: float) -> float:
        return (target - angle_of(at)) % 360.0

    lo = jd
    here = remaining(lo)
    if here == 0.0:
        return lo
    hi = lo + step_days
    limit = jd + SEARCH_DAYS
    while hi <= limit:
        if remaining(hi) > here:
            # Passed it somewhere in this step.
            for _ in range(BISECTIONS):
                mid = (lo + hi) / 2
                if remaining(mid) > here:
                    hi = mid
                else:
                    lo = mid
                    here = remaining(lo)
            return hi
        lo, here = hi, remaining(hi)
        hi = lo + step_days
    return None


# -- the five limbs ---------------------------------------------------------


@dataclass(frozen=True)
class Limb:
    """One limb in effect at sunrise, and when it gives way to the next."""

    index: int          # 1-based, in its own cycle
    name: str
    ends_at: datetime | None


def tithi_at(jd: float, zone: ZoneInfo) -> tuple[Limb, str]:
    """The tithi holding at `jd`, and its paksha."""
    angle = elongation(jd)
    index = int(angle // TITHI_DEGREES) + 1          # 1..30
    paksha = "shukla" if index <= 15 else "krishna"
    if index == 15:
        name = "Purnima"
    elif index == 30:
        name = "Amavasya"
    else:
        name = TITHI_NAMES[(index - 1) % 15]
    ends = _crossing(jd, index * TITHI_DEGREES % 360.0, elongation, 0.25)
    return Limb(index, name, from_jd(ends, zone) if ends else None), paksha


def nakshatra_at(jd: float, zone: ZoneInfo) -> Limb:
    longitude = moon_longitude(jd)
    index = int(longitude // NAKSHATRA_DEGREES) + 1  # 1..27
    ends = _crossing(jd, index * NAKSHATRA_DEGREES % 360.0, moon_longitude, 0.2)
    return Limb(index, NAKSHATRA_NAMES[index - 1], from_jd(ends, zone) if ends else None)


def yoga_at(jd: float, zone: ZoneInfo) -> Limb:
    angle = yoga_angle(jd)
    index = int(angle // YOGA_DEGREES) + 1           # 1..27
    ends = _crossing(jd, index * YOGA_DEGREES % 360.0, yoga_angle, 0.2)
    return Limb(index, YOGA_NAMES[index - 1], from_jd(ends, zone) if ends else None)


def karana_name(index: int) -> str:
    """Karana 1..60 within the lunar month, named from its two cycles.

    The first half-tithi of the month and the last three are fixed names; the
    seven moving karanas fill everything between, eight times over.
    """
    if index == 1:
        return FIXED_KARANAS[0]
    if index >= 58:
        return FIXED_KARANAS[index - 57]
    return MOVING_KARANAS[(index - 2) % 7]


def karana_at(jd: float, zone: ZoneInfo) -> Limb:
    angle = elongation(jd)
    index = int(angle // KARANA_DEGREES) + 1         # 1..60
    ends = _crossing(jd, index * KARANA_DEGREES % 360.0, elongation, 0.15)
    return Limb(index, karana_name(index), from_jd(ends, zone) if ends else None)


def vaara(day: Date) -> str:
    """The weekday, counted from Sunday as the panchang does."""
    return VAARA_NAMES[(day.weekday() + 1) % 7]


# -- the lunar month --------------------------------------------------------


def new_moon_before(jd: float) -> float:
    """The conjunction that opened the lunar month holding `jd`.

    Found by bracketing the wrap of the elongation through 360 back to 0, then
    bisecting. A lunar month is 29.5 days, so 31 back is always enough.
    """
    step = 0.5
    lo = jd - 31.0
    bracket = lo
    at = lo
    while at < jd:
        following = min(at + step, jd)
        if elongation(at) > elongation(following):
            bracket = at
        at = following
    lo, hi = bracket, min(bracket + step, jd)
    for _ in range(BISECTIONS):
        mid = (lo + hi) / 2
        if elongation(mid) > 180.0:
            lo = mid
        else:
            hi = mid
    return hi


def new_moon_after(jd: float) -> float:
    """The conjunction that closes the lunar month holding `jd`."""
    step = 0.5
    at = jd
    limit = jd + 31.0
    while at < limit:
        following = at + step
        if elongation(at) > elongation(following):
            lo, hi = at, following
            for _ in range(BISECTIONS):
                mid = (lo + hi) / 2
                if elongation(mid) > 180.0:
                    lo = mid
                else:
                    hi = mid
            return hi
        at = following
    return limit


def rasi_of_sun(jd: float) -> int:
    """Which sign the sun is in, 0 = Mesha."""
    return int(sun_longitude(jd) // 30.0)


@dataclass(frozen=True)
class Masa:
    name: str
    index: int
    adhika: bool


def masa_at(jd: float, paksha: str, scheme: str = "purnimanta") -> Masa:
    """The lunar month holding `jd`.

    The month is named for the solar sign the sun stood in at the conjunction
    that began it. Under purnimanta — the North Indian reckoning — a month
    turns at the full moon instead, which puts the dark fortnight under the
    *next* month's name: the amavasya of Diwali is Kartik, not Ashwin.

    An adhika (leap) month is one where the sun never changes sign between two
    conjunctions, so two lunar months share one solar sign.
    """
    opened = new_moon_before(jd)
    closed = new_moon_after(opened + 1.0)
    start_rasi = rasi_of_sun(opened)
    adhika = start_rasi == rasi_of_sun(closed)

    index = (start_rasi + 1) % 12
    if scheme == "purnimanta" and paksha == "krishna":
        index = (index + 1) % 12
    return Masa(MASA_NAMES[index], index + 1, adhika)


def samvat(jd: float, masa_index: int) -> tuple[int, int]:
    """(vikram, shaka) for this moment, from the days elapsed since Kali."""
    ahargana = jd - KALI_EPOCH_JD
    kali = int((ahargana + (4 - masa_index) * 30) / SIDEREAL_YEAR_DAYS)
    shaka = kali - SHAKA_FROM_KALI
    return shaka + VIKRAM_FROM_SHAKA, shaka


# -- the days worth marking -------------------------------------------------


def sankranti_on(day: Date, place: Place) -> str | None:
    """The sun's entry into a new sign, if it happens on this day.

    Makar Sankranti is the famous one, but every sign change is a sankranti
    and each is a day people mark.
    """
    start = day_start_jd(day, place)
    end = day_start_jd(day + timedelta(days=1), place)
    before, after = rasi_of_sun(start), rasi_of_sun(end)
    return RASI_NAMES[after] if before != after else None


def flags_for(tithi_index: int, sankranti: str | None) -> list[str]:
    """The marks a calendar cell carries: full and new moon, fasts, entries."""
    found: list[str] = []
    if tithi_index == 15:
        found.append("purnima")
    if tithi_index == 30:
        found.append("amavasya")
    if tithi_index in (11, 26):
        found.append("ekadashi")
    if tithi_index in (13, 28):
        # Pradosh is the evening of the thirteenth, in either fortnight.
        found.append("pradosh")
    if sankranti is not None:
        found.append("sankranti")
    return found


@dataclass(frozen=True)
class PanchangDay:
    """One computed day. The API model is built from this."""

    date: Date
    sunrise: datetime | None
    sunset: datetime | None
    moonrise: datetime | None
    moonset: datetime | None
    vaara: str
    tithi: Limb
    paksha: str
    nakshatra: Limb
    yoga: Limb
    karana: Limb
    masa: Masa
    vikram: int
    shaka: int
    flags: list[str]

    @property
    def tithi_short(self) -> str:
        """"S5" or "K12": the fortnight and the day within it."""
        letter = "S" if self.paksha == "shukla" else "K"
        return f"{letter}{(self.tithi.index - 1) % 15 + 1}"


def compute(day: Date, place: Place, scheme: str = "purnimanta") -> PanchangDay:
    """The whole almanac for one date, read at that date's sunrise.

    Sunrise is the anchor: a tithi that ends at nine in the morning is still
    *this* day's tithi, which is why a panchang and a wall calendar disagree
    about when a day begins.
    """
    _configure()
    zone = place.zone
    rise = sunrise(day, place)
    # Somewhere the sun does not rise; the day is then read at local noon so
    # that the almanac still says something rather than nothing.
    anchor = to_jd(rise) if rise is not None else day_start_jd(day, place) + 0.5

    tithi, paksha = tithi_at(anchor, zone)
    sankranti = sankranti_on(day, place)
    masa = masa_at(anchor, paksha, scheme)
    vikram, shaka = samvat(anchor, masa.index)

    return PanchangDay(
        date=day,
        sunrise=rise,
        sunset=sunset(day, place),
        moonrise=moonrise(day, place),
        moonset=moonset(day, place),
        vaara=vaara(day),
        tithi=tithi,
        paksha=paksha,
        nakshatra=nakshatra_at(anchor, zone),
        yoga=yoga_at(anchor, zone),
        karana=karana_at(anchor, zone),
        masa=masa,
        vikram=vikram,
        shaka=shaka,
        flags=flags_for(tithi.index, sankranti),
    )


# -- months, and not recomputing them -----------------------------------------


def month_dates(ym: str) -> list[Date]:
    """Every date in "2026-10", in order."""
    year, month = (int(part) for part in ym.split("-", 1))
    first = Date(year, month, 1)
    following = Date(year + (month == 12), month % 12 + 1, 1)
    return [first + timedelta(days=offset) for offset in range((following - first).days)]


def fingerprint(place: Place, scheme: str) -> str:
    """What a cached month depends on. Anything else changing is not its
    business: observances, school days and meals are folded in per request,
    because those move with the feeds while the sky does not."""
    raw = f"{place.lat:.4f},{place.lon:.4f},{place.altitude:.0f},{place.timezone},{scheme}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class CachedMonth(BaseModel):
    """The astronomy for one month, as it goes to disk."""

    ym: str
    fingerprint: str
    computed_at: datetime
    days: list[CachedDay] = []


class CachedDay(BaseModel):
    date: Date
    sunrise: datetime | None = None
    sunset: datetime | None = None
    moonrise: datetime | None = None
    moonset: datetime | None = None
    vaara: str
    tithi_name: str
    tithi_index: int
    tithi_ends_at: datetime | None = None
    tithi_short: str
    paksha: str
    nakshatra_name: str
    nakshatra_index: int
    nakshatra_ends_at: datetime | None = None
    yoga_name: str
    yoga_index: int
    yoga_ends_at: datetime | None = None
    karana_name: str
    karana_index: int
    karana_ends_at: datetime | None = None
    masa_name: str
    masa_adhika: bool
    vikram: int
    shaka: int
    flags: list[str] = []

    @classmethod
    def of(cls, day: PanchangDay) -> CachedDay:
        return cls(
            date=day.date,
            sunrise=day.sunrise,
            sunset=day.sunset,
            moonrise=day.moonrise,
            moonset=day.moonset,
            vaara=day.vaara,
            tithi_name=day.tithi.name,
            tithi_index=day.tithi.index,
            tithi_ends_at=day.tithi.ends_at,
            tithi_short=day.tithi_short,
            paksha=day.paksha,
            nakshatra_name=day.nakshatra.name,
            nakshatra_index=day.nakshatra.index,
            nakshatra_ends_at=day.nakshatra.ends_at,
            yoga_name=day.yoga.name,
            yoga_index=day.yoga.index,
            yoga_ends_at=day.yoga.ends_at,
            karana_name=day.karana.name,
            karana_index=day.karana.index,
            karana_ends_at=day.karana.ends_at,
            masa_name=day.masa.name,
            masa_adhika=day.masa.adhika,
            vikram=day.vikram,
            shaka=day.shaka,
            flags=list(day.flags),
        )


CachedMonth.model_rebuild()


class PanchangService:
    """The almanac, computed once per month and kept.

    A month is about four hundred ephemeris calls; on this Mac that is well
    under a second, but it is the same answer every time, so it is written to
    content/.cache/ and only recomputed when the place or the naming scheme
    changes.
    """

    def __init__(self, place: Place, scheme: str = "purnimanta", cache: Path | None = None) -> None:
        self.place = place
        self.scheme = scheme
        self.cache_dir = cache if cache is not None else cache_dir()
        self._months: dict[str, list[CachedDay]] = {}

    def _path(self, ym: str) -> Path:
        return self.cache_dir / f"panchang-{ym}.json"

    def day(self, day: Date) -> PanchangDay:
        return compute(day, self.place, self.scheme)

    def month(self, ym: str) -> list[CachedDay]:
        """Every day of a month, from memory, then disk, then the ephemeris."""
        want = fingerprint(self.place, self.scheme)
        held = self._months.get(ym)
        if held is not None:
            return held

        path = self._path(ym)
        if path.is_file():
            try:
                cached = CachedMonth.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, ValidationError) as exc:
                logger.error("unreadable %s (%s); recomputing", path, exc)
            else:
                if cached.fingerprint == want:
                    self._months[ym] = cached.days
                    return cached.days
                logger.info("%s was computed for another place or scheme; recomputing", path.name)

        days = [CachedDay.of(compute(day, self.place, self.scheme)) for day in month_dates(ym)]
        self._months[ym] = days
        self._write(ym, want, days)
        return days

    def _write(self, ym: str, want: str, days: list[CachedDay]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            payload = CachedMonth(
                ym=ym, fingerprint=want, computed_at=datetime.now(self.place.zone), days=days
            )
            temporary = self._path(ym).with_suffix(".json.tmp")
            temporary.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
            os.replace(temporary, self._path(ym))
        except OSError:
            logger.exception("could not write %s", self._path(ym))
