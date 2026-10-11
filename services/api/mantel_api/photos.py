"""Photos, read-only. The store belongs to Memories since 2026-10-10 (Mantel 0.3.0).

Memories (the photo frame app, :8002) owns the photo folder: uploads, the import, deletes and
the pipeline that normalises each photo. Mantel only reads the same folder, so its iPads'
frame keeps playing exactly what it did:

    originals/   exactly what was uploaded (not read here)
    cache/       what the kiosk is served: 2048px JPEG, no metadata
    failed/      what could not be read (not read here)
    index.json   the catalogue, and the only thing the list endpoint reads

The folder is MANTEL_PHOTOS_DIR, else MANTEL_HOME/photos; on Albert it is Memories' folder,
mounted read-only. Nothing here writes to it: a catalogue that will not parse is logged and
the last good one keeps serving (Memories, not Mantel, decides what to do with the file).
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import threading
from datetime import date as Date
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .models import Photo
from .paths import photos_dir

logger = logging.getLogger("mantel_api.photos")

#: A photo id is the first 16 hex of the SHA-256 of the original (Memories decides).
ID_CHARS = 16


class PhotoRecord(BaseModel):
    """One row of index.json, as Memories writes it."""

    id: str
    sha256: str
    original: str
    w: int
    h: int
    taken_at: Date | None = None
    place: str | None = None
    added_at: datetime

    def public(self) -> Photo:
        return Photo(
            id=self.id,
            url=f"/api/photos/{self.id}.jpg",
            w=self.w,
            h=self.h,
            taken_at=self.taken_at,
            place=self.place,
            added_at=self.added_at,
        )


class PhotoIndex(BaseModel):
    version: int = 1
    photos: list[PhotoRecord] = []


class PhotoStore:
    """The photo folder as the API sees it: read-only. Safe to call from a threadpool."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else photos_dir()
        self.cache = self.directory / "cache"
        self.index_file = self.directory / "index.json"
        self._lock = threading.Lock()
        self._records: dict[str, PhotoRecord] = {}
        self._index_mtime: float | None = None
        self._load()

    def _load(self) -> None:
        try:
            mtime = self.index_file.stat().st_mtime
        except OSError:
            return
        self._index_mtime = mtime
        try:
            parsed = PhotoIndex.model_validate_json(self.index_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, ValidationError) as exc:
            # Not ours to move aside: keep serving the last good catalogue.
            logger.error("unreadable %s (%s); keeping the last good list", self.index_file, exc)
            return
        self._records = {record.id: record for record in parsed.photos}

    def _reread_if_changed(self) -> None:
        """Memories writes index.json on every upload and delete; pick it up."""
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


def write_sample_album(directory: Path, jpegs: list[bytes]) -> None:
    """The demo's and the tests' photos (the fictional sample family only): written in
    Memories' layout so the reader above has something to read. The service never calls this;
    real photos only ever arrive through Memories."""
    from PIL import Image

    records: list[PhotoRecord] = []
    (directory / "cache").mkdir(parents=True, exist_ok=True)
    for data in jpegs:
        digest = hashlib.sha256(data).hexdigest()
        photo_id = digest[:ID_CHARS]
        (directory / "cache" / f"{photo_id}.jpg").write_bytes(data)
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
        records.append(
            PhotoRecord(
                id=photo_id,
                sha256=digest,
                original=f"{photo_id}.jpg",
                w=width,
                h=height,
                added_at=datetime.now(),
            )
        )
    temporary = directory / "index.json.tmp"
    temporary.write_text(PhotoIndex(photos=records).model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, directory / "index.json")
