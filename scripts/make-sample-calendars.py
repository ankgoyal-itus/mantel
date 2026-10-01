"""Write the sample family's calendars as local ICS files, dated from today.

    services/api/.venv/bin/python scripts/make-sample-calendars.py [FOLDER]

FOLDER defaults to content.sample/calendars/ (git-ignored). `make demo` does
this for its own temporary home; run it by hand to look at the files.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mantel_api.sample import SAMPLE_DIR, write_calendars


def main(argv: list[str]) -> int:
    folder = Path(argv[1]) if len(argv) > 1 else SAMPLE_DIR / "calendars"
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    for path in write_calendars(folder, today):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
