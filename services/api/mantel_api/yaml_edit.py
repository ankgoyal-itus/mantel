"""Writing content files back without losing what a person put there.

ruamel round-trips comments, key order and quoting, which plain yaml.dump
would flatten. Every write is atomic: a temp file in the same directory, then
a rename, so a half-written file never reaches the watcher.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

STAMP_PREFIX = "# edited from iPad "


def round_trip() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # never re-wrap a long note
    # The house style of every hand-written file here: a list sits two spaces
    # in from its key ("kids:\n  - {id: sam, …}"). ruamel's default puts it
    # at the key's own column, so the first save from the iPad re-indented
    # every list in the file — a diff of nothing, and a file that no longer
    # looks like the ones beside it.
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def load(path: Path) -> Any:
    yaml = round_trip()
    with path.open(encoding="utf-8") as handle:
        return yaml.load(handle)


def _stamped(text: str, when: datetime) -> str:
    """Replace the previous stamp rather than growing one line per save."""
    lines = [line for line in text.splitlines() if not line.startswith(STAMP_PREFIX)]
    while lines and not lines[-1].strip():
        lines.pop()
    lines.append(f"{STAMP_PREFIX}{when.isoformat(timespec='seconds')}")
    return "\n".join(lines) + "\n"


def serialize(data: Any, when: datetime) -> str:
    """Round-trip back to text and stamp it. Nothing is written yet, so the
    caller can validate the candidate before it replaces a working file."""
    yaml = round_trip()
    buffer = tempfile.SpooledTemporaryFile(mode="w+", encoding="utf-8")
    yaml.dump(data, buffer)
    buffer.seek(0)
    return _stamped(buffer.read(), when)


def write_atomic(path: Path, text: str) -> None:
    """Temp file beside the target, then rename: the watcher never sees half."""
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        delete=False,
    )
    # The temp file is created 0600, and a rename keeps it: every file the
    # iPad had saved had quietly become readable by its owner alone. Keep the
    # file's own mode, or the ordinary one for a new file.
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    try:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.chmod(handle.name, mode)
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
