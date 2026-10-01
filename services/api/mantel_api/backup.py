"""Nightly copies of the ledger.

The ledger is the one file in this project nobody can reconstruct. The YAML
is written by hand and lives in git; a week of approved chores does not.

The copy is taken with SQLite's own backup API rather than `cp`, because a
file copied while a write is in flight can land half-written, and the copy
nobody checks is the one that turns out to be corrupt. Today's copy is taken
once and then left alone, so this is safe to call on a timer.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date as Date
from pathlib import Path

from .db import Database
from .paths import backup_dir

logger = logging.getLogger("mantel_api.backup")

#: A fortnight. Long enough to cover a holiday, short enough that the folder
#: stays something a person can look at and understand.
KEEP = 14

PREFIX = "mantel-"
SUFFIX = ".db"


def backup_path(day: Date, directory: Path | None = None) -> Path:
    base = directory if directory is not None else backup_dir()
    return base / f"{PREFIX}{day.isoformat()}{SUFFIX}"


def copies(directory: Path | None = None) -> list[Path]:
    """Every backup on disk, oldest first. The name sorts as the date does."""
    base = directory if directory is not None else backup_dir()
    if not base.is_dir():
        return []
    return sorted(base.glob(f"{PREFIX}*{SUFFIX}"))


def rotate(directory: Path | None = None, keep: int = KEEP) -> list[Path]:
    """Delete all but the newest `keep` copies. Returns what was removed."""
    existing = copies(directory)
    stale = existing[: max(0, len(existing) - keep)]
    removed = []
    for path in stale:
        try:
            path.unlink()
        except OSError as exc:  # noqa: PERF203 - one bad file must not stop the rest
            logger.warning("could not remove old backup %s: %s", path, exc)
            continue
        removed.append(path)
    return removed


def run(
    database: Database, today: Date, *, directory: Path | None = None, keep: int = KEEP
) -> Path:
    """Take today's copy if it is not already there, then rotate.

    Returns the path of today's copy, whether this call made it or found it.
    """
    target = backup_path(today, directory)
    if target.exists():
        rotate(directory, keep)
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    # Written beside the target and renamed, so a copy interrupted half way
    # never appears under a name that says it finished.
    partial = target.with_suffix(".db.partial")
    try:
        with database.connect() as live:
            destination = sqlite3.connect(partial)
            try:
                live.backup(destination)
            finally:
                destination.close()
        partial.replace(target)
    except (OSError, sqlite3.Error):
        partial.unlink(missing_ok=True)
        logger.exception("could not back up the ledger to %s", target)
        raise

    removed = rotate(directory, keep)
    logger.info(
        "ledger backed up to %s (%d kept, %d removed)",
        target.name,
        len(copies(directory)),
        len(removed),
    )
    return target
