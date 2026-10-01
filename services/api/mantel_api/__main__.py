"""`python -m mantel_api` — serve the API on the LAN."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from .paths import repo_root


def main() -> None:
    # Without this the root logger only shows WARNING and above, which hides
    # content reloads while still showing the errors that matter. The timestamp
    # is the point under launchd: ~/Library/Logs/mantel/ is where you go to find
    # out when the API last answered, after a night that went wrong.
    # stdout, not the default stderr: under launchd that puts the whole log in
    # api.log and leaves api.err.log empty unless the process actually dies.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # httpx logs each request URL at INFO, and a calendar feed URL is a secret.
    # Under launchd these lines would persist in ~/Library/Logs/mantel/.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Secrets (MANTEL_CAL_* and friends) live in .env, never in the repo. Loaded
    # here rather than at import, so tests never see the real feed URLs.
    load_dotenv(repo_root() / ".env")
    # `make dev` sets this; the launchd service and `make serve` do not, so
    # neither runs a reloader overnight.
    reloading = os.environ.get("MANTEL_RELOAD", "").strip() not in ("", "0", "false")
    if reloading:
        logging.getLogger("mantel_api").info("reloading on changes under mantel_api/")

    # log_config=None leaves logging to the config above; uvicorn's own dictConfig
    # would otherwise install timestamp-free handlers for its access lines.
    uvicorn.run(
        "mantel_api.app:app",
        host="0.0.0.0",  # noqa: S104
        port=8000,
        log_config=None,
        reload=reloading,
        # The /api/events streams would otherwise hold a stop open until the
        # last iPad let go; three seconds, then they reconnect elsewhere.
        timeout_graceful_shutdown=3,
        # Only the package. The default watches the whole working directory,
        # which would mean .venv, and — worse — content/: a parent-mode save
        # would restart the API and drop the session mid-edit.
        reload_dirs=[str(Path(__file__).resolve().parent)] if reloading else None,
    )


if __name__ == "__main__":
    main()
