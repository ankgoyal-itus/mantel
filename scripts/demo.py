"""`make demo`: the sample family on a throwaway home, on http://localhost:8140/.

content.sample/ is rendered into a temporary MANTEL_HOME, dated from today,
with its calendars as local files; a fresh ledger is seeded with a fortnight
of history (mantel_api/demo.py); eight placeholder photos go to the frame.
MANTEL_DEMO=1 gives it a forecast of its own, so nothing is fetched from
anywhere. Ctrl-C stops it and the temporary home goes with it.
"""

from __future__ import annotations

import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mantel_api.content import Content
from mantel_api.db import Database
from mantel_api.demo import CODES, seed
from mantel_api.photos import write_sample_album
from mantel_api.sample import make_home, sample_photo

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "services" / "api" / "static"
PARENT_PIN = "1234"
ZONE = ZoneInfo("America/Los_Angeles")


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def main() -> int:
    port = int(os.environ.get("MANTEL_DEMO_PORT", "8140"))
    if not (STATIC / "index.html").is_file():
        print("No kiosk build — run `make build` first.", file=sys.stderr)
        return 2
    if not port_free(port):
        print(f"Port {port} is in use; set MANTEL_DEMO_PORT to another.", file=sys.stderr)
        return 2

    root = Path(tempfile.mkdtemp(prefix="mantel-demo-"))
    try:
        today = datetime.now(ZONE).date()
        home = make_home(root / "home", today)
        content = Content(home / "content")
        content.load_all()
        books = Database(home / "mantel.db")
        with books.write() as connection:
            seed(connection, content, today, ZONE)
        books.close()
        write_sample_album(home / "photos", [sample_photo(index) for index in range(8)])

        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("MANTEL_CAL_")
        }
        environment.update(
            MANTEL_HOME=str(home),
            MANTEL_DEMO="1",
            MANTEL_PARENT_PIN=PARENT_PIN,
            MANTEL_UPLOAD_TOKEN=secrets.token_urlsafe(16),
            MANTEL_STATIC=str(STATIC),
        )
        environment.pop("MANTEL_CONTENT_DIR", None)
        environment.pop("MANTEL_DB_PATH", None)

        print(f"Mantel demo: http://localhost:{port}/")
        print(f"  parent PIN {PARENT_PIN} · Mira {CODES['mira']} · Kabir {CODES['kabir']}")
        print("  Ctrl-C to stop; the demo's home is thrown away.", flush=True)
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "mantel_api.app:app",
                "--host",
                "0.0.0.0",  # noqa: S104 - an iPad on the LAN is the point of a demo
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=REPO / "services" / "api",
            env=environment,
        )
        # Stopped by Ctrl-C or by a kill: the server goes with it either way.
        signal.signal(signal.SIGTERM, lambda *_: server.terminate())
        try:
            return server.wait()
        except KeyboardInterrupt:
            server.terminate()
            server.wait(timeout=10)
            return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
