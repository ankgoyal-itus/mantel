"""Pick the published screenshots out of the design suite's renders.

    make screenshots

The design suite (tests/design) renders every state at 1x into docs/screens/
(git-ignored); this copies the ten the README and the essay use into
screenshots/, optimised, and keeps the untouched renders in screenshots/raw/
(also ignored). Everything shown is the fictional sample family.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
RENDERS = REPO / "docs" / "screens"
OUT = REPO / "screenshots"
RAW = OUT / "raw"
#: Over this, a picture is quantised to a 256-colour palette, which a flat UI
#: survives without a visible change.
MAX_BYTES = 400 * 1024

#: Published name ← the design state's render, day palette unless the state
#: is the night screen's own.
PICKS = {
    "01-day.png": "day-evening.png",
    "02-kid-card.png": "kid.png",
    "03-approvals.png": "parent-approvals.png",
    "04-rewards.png": "kid-shop-all.png",
    "05-meal-picks.png": "kid-week.png",
    "06-night.png": "night.png",
    "07-frame.png": "frame.png",
    "08-parent-phone.png": "phone-approvals.png",
    "09-day-portrait.png": "day-evening-portrait.png",
    "10-month.png": "month-october-panel.png",
}


def optimise(source: Path, target: Path) -> int:
    image = Image.open(source)
    image.save(target, format="PNG", optimize=True)
    if target.stat().st_size > MAX_BYTES:
        image.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(
            target, format="PNG", optimize=True
        )
    if shutil.which("oxipng"):
        subprocess.run(["oxipng", "-q", "-o", "4", "--strip", "safe", str(target)], check=False)
    return target.stat().st_size


def main() -> int:
    missing = [render for render in PICKS.values() if not (RENDERS / render).is_file()]
    if missing:
        print(f"Not rendered: {missing} — run the design suite first.", file=sys.stderr)
        return 1
    RAW.mkdir(parents=True, exist_ok=True)
    for name, render in PICKS.items():
        shutil.copy2(RENDERS / render, RAW / render)
        size = optimise(RENDERS / render, OUT / name)
        with Image.open(OUT / name) as image:
            width, height = image.size
        flag = "" if size <= MAX_BYTES else "  (over 400 KB)"
        print(f"  {name:22} ← {render:26} {width}x{height} {size // 1024} KB{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
