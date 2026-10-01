"""Photos: uploaded from a phone, normalised once, catalogued, served forever.

Everything lands in content/photos/:

    originals/   exactly what was uploaded, kept so a better pipeline can rerun
    cache/       what the kiosk is served: 2048px JPEG, no metadata
    failed/      anything Pillow could not read, kept for a human to look at
    index.json   the catalogue, and the only thing the list endpoint reads

A photo's id is the first 16 hex of the SHA-256 of the original, so uploading
the same file twice is free and the id never depends on when it arrived.

Nothing here may take the API down: a file that cannot be processed is moved
aside and logged, and an unreadable index.json is renamed rather than obeyed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import logging
import os
import sys
import threading
from datetime import date as Date
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from pydantic import BaseModel, ValidationError

from . import places
from .models import Photo
from .paths import photos_dir

logger = logging.getLogger("mantel_api.photos")

# So Image.open() reads the .heic that comes straight off an iPhone.
register_heif_opener()

#: Long edge in pixels. The retina iPad is 2048 wide, and nothing is gained by
#: shipping more than the screen can show over a home Wi-Fi.
LONG_EDGE = 2048
JPEG_QUALITY = 85
MAX_BYTES = 30 * 1024 * 1024
ID_CHARS = 16

#: EXIF tags holding a capture time, best first.
DATE_TAGS = (36867, 36868, 306)  # DateTimeOriginal, DateTimeDigitized, DateTime

#: The GPS IFD, and the four tags inside it that matter.
GPS_IFD = 34853
GPS_LAT_REF, GPS_LAT, GPS_LON_REF, GPS_LON = 1, 2, 3, 4

#: What a phone or a Photos export can hand us. Anything else is refused by
#: name before Pillow is asked to guess.
SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff", ".gif", ".bmp"}


class PhotoError(Exception):
    """The file could not be turned into a photo. It is already in failed/."""


class PhotoRecord(BaseModel):
    """One row of index.json."""

    id: str
    sha256: str
    original: str
    w: int
    h: int
    taken_at: Date | None = None
    #: The nearest town when the photo carried a fix, resolved once at import
    #: from a bundled gazetteer. The coordinates are not kept.
    place: str | None = None
    added_at: datetime

    def public(self) -> Photo:
        return Photo(id=self.id, url=f"/api/photos/{self.id}.jpg", w=self.w, h=self.h,
                     taken_at=self.taken_at, place=self.place, added_at=self.added_at)


class PhotoIndex(BaseModel):
    version: int = 1
    photos: list[PhotoRecord] = []


def taken_at(image: Image.Image) -> Date | None:
    """The capture date out of EXIF, or None. Only the date is ever kept."""
    try:
        exif = image.getexif()
    except Exception:  # noqa: BLE001 - a broken EXIF block is not a broken photo
        return None
    for tag in DATE_TAGS:
        raw = exif.get(tag)
        if not isinstance(raw, str):
            continue
        try:
            return datetime.strptime(raw.strip()[:10], "%Y:%m:%d").date()
        except ValueError:
            continue
    return None


def _degrees(value: object) -> float | None:
    """EXIF writes a coordinate as three rationals: degrees, minutes, seconds."""
    if not isinstance(value, tuple | list) or len(value) != 3:
        return None
    try:
        degrees, minutes, seconds = (float(part) for part in value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return degrees + minutes / 60 + seconds / 3600


def taken_near(image: Image.Image) -> tuple[float, float] | None:
    """Where the photo was taken, out of EXIF, or None.

    Read here and turned into a place name before the file is re-encoded,
    which is what strips it: the coordinates themselves are never stored. What
    is kept is the name of a town, which is the part worth putting on a wall
    and the part that cannot be used to find a house.
    """
    try:
        gps = image.getexif().get_ifd(GPS_IFD)
    except Exception:  # noqa: BLE001 - a broken EXIF block is not a broken photo
        return None
    if not gps:
        return None
    lat = _degrees(gps.get(GPS_LAT))
    lon = _degrees(gps.get(GPS_LON))
    if lat is None or lon is None:
        return None
    if str(gps.get(GPS_LAT_REF, "N")).upper().startswith("S"):
        lat = -lat
    if str(gps.get(GPS_LON_REF, "E")).upper().startswith("W"):
        lon = -lon
    return lat, lon


def process(data: bytes) -> tuple[bytes, int, int, Date | None, str | None]:
    """Normalise one image: upright, at most LONG_EDGE, JPEG, no metadata.

    Re-encoding is what strips the metadata: nothing is copied to the new file,
    so the capture date is read out here, before it is lost.
    """
    try:
        with Image.open(io.BytesIO(data)) as opened:
            opened.load()
            when = taken_at(opened)
            where = taken_near(opened)
            place = places.name_for(*where) if where is not None else None
            # The phone writes the orientation in EXIF rather than the pixels.
            upright = ImageOps.exif_transpose(opened) or opened
            rgb = upright.convert("RGB")
            # thumbnail() only ever shrinks, so a small photo is left alone.
            rgb.thumbnail((LONG_EDGE, LONG_EDGE), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            rgb.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            return out.getvalue(), rgb.width, rgb.height, when, place
    except PhotoError:
        raise
    except Exception as exc:  # noqa: BLE001 - every decode failure reads the same
        raise PhotoError(f"{type(exc).__name__}: {exc}") from exc


class PhotoStore:
    """content/photos/ as the API sees it. Safe to call from a threadpool."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else photos_dir()
        self.originals = self.directory / "originals"
        self.cache = self.directory / "cache"
        self.failed = self.directory / "failed"
        self.index_file = self.directory / "index.json"
        self._lock = threading.Lock()
        self._records: dict[str, PhotoRecord] = {}
        self._index_mtime: float | None = None
        self._load()

    # -- the catalogue -----------------------------------------------------

    def _load(self) -> None:
        if not self.index_file.is_file():
            return
        self._index_mtime = self.index_file.stat().st_mtime
        try:
            parsed = PhotoIndex.model_validate_json(self.index_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, ValidationError) as exc:
            # Renamed rather than trusted or deleted: the photos are still on
            # disk, and a human can see what went wrong.
            spoiled = self.index_file.with_suffix(f".bad-{int(datetime.now().timestamp())}.json")
            logger.error("unreadable %s (%s); moved to %s", self.index_file, exc, spoiled.name)
            try:
                self.index_file.rename(spoiled)
            except OSError:
                logger.exception("could not move %s aside", self.index_file)
            return
        self._records = {record.id: record for record in parsed.photos}

    def _save(self) -> None:
        """Write the catalogue atomically: a half-written index is no index."""
        self.directory.mkdir(parents=True, exist_ok=True)
        index = PhotoIndex(photos=list(self._records.values()))
        temporary = self.index_file.with_suffix(".json.tmp")
        temporary.write_text(index.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, self.index_file)
        # Our own write must not read as somebody else's.
        self._index_mtime = self.index_file.stat().st_mtime

    # -- reading -----------------------------------------------------------

    def _reread_if_changed(self) -> None:
        """Pick up an index written by something else — the import CLI, say.

        The catalogue is held in memory, so without this a bulk import would
        not appear until the service was restarted, which is a surprising way
        for a documented command to behave.
        """
        try:
            mtime = self.index_file.stat().st_mtime
        except OSError:
            return
        if mtime != self._index_mtime:
            logger.info("index.json changed on disk; re-reading")
            self._load()

    def photos(self) -> list[Photo]:
        """Newest first. A photo with no capture date sorts by when it arrived."""
        with self._lock:
            self._reread_if_changed()
            records = list(self._records.values())
        records.sort(key=lambda r: (r.taken_at or r.added_at.date(), r.added_at), reverse=True)
        return [record.public() for record in records]

    def file_for(self, photo_id: str) -> Path | None:
        with self._lock:
            self._reread_if_changed()
            known = photo_id in self._records
        if not known:
            return None
        path = self.cache / f"{photo_id}.jpg"
        return path if path.is_file() else None

    # -- writing -----------------------------------------------------------

    def add(self, data: bytes, filename: str) -> tuple[str, bool]:
        """Store one upload. Returns (id, added); added is False for a repeat."""
        digest = hashlib.sha256(data).hexdigest()
        photo_id = digest[:ID_CHARS]

        with self._lock:
            self._reread_if_changed()
            if photo_id in self._records:
                return photo_id, False

        suffix = Path(filename).suffix.lower()
        original = self.originals / f"{photo_id}{suffix or '.bin'}"
        self.originals.mkdir(parents=True, exist_ok=True)
        original.write_bytes(data)

        try:
            jpeg, width, height, when, place = process(data)
        except PhotoError as exc:
            self._fail(original, str(exc))
            raise

        self.cache.mkdir(parents=True, exist_ok=True)
        (self.cache / f"{photo_id}.jpg").write_bytes(jpeg)

        record = PhotoRecord(
            id=photo_id,
            sha256=digest,
            original=original.name,
            w=width,
            h=height,
            taken_at=when,
            place=place,
            added_at=datetime.now(),
        )
        with self._lock:
            self._records[photo_id] = record
            self._save()
        return photo_id, True

    def _fail(self, original: Path, reason: str) -> None:
        self.failed.mkdir(parents=True, exist_ok=True)
        destination = self.failed / original.name
        try:
            os.replace(original, destination)
        except OSError:
            logger.exception("could not move %s to %s", original, self.failed)
        logger.error("could not process %s: %s (moved to failed/)", original.name, reason)

    def delete(self, photo_id: str) -> bool:
        with self._lock:
            record = self._records.pop(photo_id, None)
            if record is None:
                return False
            self._save()
        for path in (self.cache / f"{photo_id}.jpg", self.originals / record.original):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception("could not remove %s", path)
        return True

    # -- bulk import -------------------------------------------------------

    def import_folder(self, folder: Path) -> tuple[int, int, int]:
        """Walk a Photos export. Returns (added, skipped, failed)."""
        added = skipped = failed = 0
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            if path.suffix.lower() not in SUFFIXES:
                continue
            try:
                data = path.read_bytes()
            except OSError:
                logger.exception("could not read %s", path)
                failed += 1
                continue
            if len(data) > MAX_BYTES:
                logger.error("%s is larger than %d MB", path.name, MAX_BYTES // (1024 * 1024))
                failed += 1
                continue
            try:
                _, was_added = self.add(data, path.name)
            except PhotoError:
                failed += 1
                continue
            if was_added:
                added += 1
            else:
                skipped += 1
        return added, skipped, failed


def main(argv: list[str] | None = None) -> int:
    """`python -m mantel_api.photos import <folder>` — the same pipeline, offline."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(prog="python -m mantel_api.photos")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import", help="add every image in a folder, recursively")
    importer.add_argument("folder", type=Path)
    args = parser.parse_args(argv)

    folder: Path = args.folder
    if not folder.is_dir():
        print(f"not a folder: {folder}", file=sys.stderr)
        return 2

    store = PhotoStore()
    added, skipped, failed = store.import_folder(folder)
    print(f"added {added}, already had {skipped}, failed {failed} -> {store.directory}")
    return 1 if failed and not added else 0


if __name__ == "__main__":
    raise SystemExit(main())
