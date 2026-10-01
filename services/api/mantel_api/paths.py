"""Filesystem locations.

The code is found from the repo root. The family's own state — content, the
ledger and its backups, photos, the derived caches — lives under one
directory, MANTEL_HOME (default `home/` in the repo, git-ignored):

    home/content/   the YAML the family edits
    home/photos/    uploads, their resized copies and the catalogue
    home/cache/     what the API derives from live feeds
    home/backups/   nightly copies of the ledger
    home/mantel.db  the points ledger

so the tree can be public and the family's data never in it.
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_ROOT = Path(__file__).resolve().parents[3]


def repo_root() -> Path:
    """Repo root, overridable with MANTEL_ROOT (used by tests and deploys)."""
    override = os.environ.get("MANTEL_ROOT")
    return Path(override).resolve() if override else _DEFAULT_ROOT


def home_dir() -> Path:
    """MANTEL_HOME, or `home/` in the repo. A relative MANTEL_HOME is read
    from the repo root, so .env can say `MANTEL_HOME=home`."""
    override = os.environ.get("MANTEL_HOME")
    if not override:
        return repo_root() / "home"
    path = Path(override).expanduser()
    return (path if path.is_absolute() else repo_root() / path).resolve()


def content_dir() -> Path:
    """home/content/, or MANTEL_CONTENT_DIR when set.

    The tests always point MANTEL_HOME at a copy: nothing a test does may
    touch the family's own files, and a test that edits settings.yaml or
    appends to the ledger is doing exactly the thing the family would notice.
    """
    override = os.environ.get("MANTEL_CONTENT_DIR")
    return Path(override).resolve() if override else home_dir() / "content"


def cache_dir() -> Path:
    """What the API derives and writes for itself. Never hand-edited, never
    committed: the only family files that hold dates."""
    return home_dir() / "cache"


def db_path() -> Path:
    """The points ledger, or MANTEL_DB_PATH when set. It is the house's own
    record, not content."""
    override = os.environ.get("MANTEL_DB_PATH")
    return Path(override).resolve() if override else home_dir() / "mantel.db"


def backup_dir() -> Path:
    """Nightly copies of the ledger, rotated."""
    return home_dir() / "backups"


def photos_dir() -> Path:
    """Uploads, their resized copies and the catalogue."""
    return home_dir() / "photos"


def static_dir() -> Path:
    """The built kiosk, overridable with MANTEL_STATIC (the Docker image, tests)."""
    override = os.environ.get("MANTEL_STATIC")
    return Path(override).resolve() if override else repo_root() / "services" / "api" / "static"


def version_file() -> Path:
    return repo_root() / "VERSION"


def read_version() -> str:
    try:
        return version_file().read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
