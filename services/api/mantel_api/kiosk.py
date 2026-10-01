"""Serving the built kiosk.

`make build` writes the Vite bundle into services/api/static/; this serves it
from `/` so the iPads need one host and one port, with `/api` untouched
underneath. Any other path returns index.html, because the kiosk routes
`/diag` in the browser and an iPad reloading that URL must still get the app.

The API runs before the first build and after a build is wiped, so a missing
bundle is a page that says so, never a crash at startup.
"""

from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from .paths import static_dir

logger = logging.getLogger("mantel_api.kiosk")

#: Vite hashes every asset filename, so a bundle is good until a build renames it.
ASSET_CACHE = "public, max-age=31536000, immutable"
#: index.html is how an iPad discovers a new bundle at all, so it is never cached.
PAGE_CACHE = "no-store"

ASSETS = "assets/"

NO_BUILD_PAGE = """<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><title>Mantel</title></head>
  <body style="font-family: -apple-system, sans-serif; padding: 2rem">
    <h1>No kiosk build</h1>
    <p>Run <code>make build</code>, then reload. The API itself is fine:
       see <a href="/api/health">/api/health</a>.</p>
  </body>
</html>
"""


def _file_in(root: Path, path: str) -> Path | None:
    """`path` as a real file inside `root`, or None. Never escapes the root."""
    if not path or path.endswith("/"):
        return None
    # Both sides are resolved, or a symlinked root (macOS /var) never matches.
    base = root.resolve()
    candidate = (base / path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None  # a ../ that climbs out of the build directory
    return candidate if candidate.is_file() else None


def mount_kiosk(app: FastAPI) -> None:
    """Serve the built kiosk from `/`. Call this last: `/api` routes win."""
    root = static_dir().resolve()
    index = root / "index.html"
    if not index.is_file():
        logger.warning("no kiosk build at %s; serving the build reminder page", root)

    @app.get("/{path:path}", include_in_schema=False)
    def kiosk(path: str) -> Response:
        # Only unmatched /api paths reach here, and they are API mistakes: a
        # kiosk that got index.html back would parse HTML as JSON.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")

        file = _file_in(root, path)
        if file is not None:
            headers = {"Cache-Control": ASSET_CACHE if path.startswith(ASSETS) else PAGE_CACHE}
            return FileResponse(file, headers=headers)

        # A path with an extension is a file, not a browser route. Answering
        # with index.html would hand Safari HTML where it asked for an icon or
        # a script — iOS asks for /favicon.ico and /apple-touch-icon-*.png on
        # every load, and a missing asset means a broken build, not a route.
        if PurePosixPath(path).suffix:
            raise HTTPException(status_code=404, detail="not found")

        page = {"Cache-Control": PAGE_CACHE}
        if not index.is_file():
            return HTMLResponse(NO_BUILD_PAGE, status_code=503, headers=page)
        return FileResponse(index, headers=page)
