"""Write eight placeholder photographs for the sample family's frame.

    services/api/.venv/bin/python scripts/make-sample-photos.py [FOLDER]

2048-pixel gradients over a horizon, made with Pillow: they read as
photographs from across a room and are of nobody. FOLDER defaults to
content.sample/photos/ (git-ignored); `make demo` uploads them itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mantel_api.sample import SAMPLE_DIR, write_photos


def main(argv: list[str]) -> int:
    folder = Path(argv[1]) if len(argv) > 1 else SAMPLE_DIR / "photos"
    for path in write_photos(folder):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
