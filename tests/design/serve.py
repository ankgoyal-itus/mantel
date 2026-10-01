"""Serve the built kiosk on a spare port and run the design checks against it."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "services" / "api" / "static"
PORT = 8130


class Handler(SimpleHTTPRequestHandler):
    """Static files only. Every /api call is intercepted in the browser."""

    def do_GET(self) -> None:  # noqa: N802 - the base class spells it this way
        path = self.path.split("?")[0]
        if path == "/" or "." not in path.rsplit("/", 1)[-1]:
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, *args: object) -> None:
        pass


def main() -> int:
    if not (STATIC / "index.html").is_file():
        print("no kiosk build; run `make build`", file=sys.stderr)
        return 2

    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(STATIC)))
    except OSError as exc:
        # Another design run already has it. Without this the traceback reads
        # as a design failure, and — worse — a run that starts while another
        # is rewriting services/api/static measures a half-written build and
        # reports states as broken that are fine.
        print(
            f"design checks: :{PORT} is already in use ({exc.strerror}).\n"
            "Another `make check` or `make design` is running; wait for it to finish.",
            file=sys.stderr,
        )
        return 2
    Thread(target=server.serve_forever, daemon=True).start()

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1).close()
            break
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)

    try:
        return subprocess.run(
            [sys.executable, str(Path(__file__).with_name("design.py"))], cwd=REPO
        ).returncode
    finally:
        # Both: shutdown stops serve_forever, server_close releases the port.
        # Without the second, a run cut short leaves :8130 held and the next
        # one dies on bind rather than on anything to do with the design.
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
