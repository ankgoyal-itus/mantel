# Mantel — family iPad dashboard
Kiosk web app for two old iPads. Modes: day dashboard, night screen, photo frame, parent mode.
Stack: apps/kiosk = React 18 + Vite + TypeScript. services/api = Python 3.11 + FastAPI + Pydantic v2 + uvicorn. Content = YAML. Points live in SQLite.
Rules:
- The real target is iPadOS 17+: browserslist "iOS >= 17", no legacy bundle. Both iPads run iOS 18.7.9. Modern CSS is allowed: flex gap, dvh/svh, :has(), container queries, aspect-ratio. Size the stage in pixels from innerWidth/innerHeight anyway, because Safari still moves dvh as its toolbars come and go. Test at 1024x768 and 2048x1536 landscape.
- Touch-first: 44px minimum targets, no hover-only UI, no text selection, no pinch zoom, no scrolling on the main screens.
- No LLM in any decision path. No analytics, no third-party scripts, no CDN fonts or icons — bundle everything; the iPad may be offline for minutes.
- Content is YAML, validated by Pydantic. A bad file never crashes the API: serve the last good version and log the path and error.
- Only the API talks to the internet (weather, calendars). The kiosk talks only to the API.
- Secrets live in .env, never in the repo: MANTEL_PARENT_PIN, MANTEL_UPLOAD_TOKEN, MANTEL_CAL_* URLs.
- Development happens on Jarvis (this Mac, jarvis.local). Production is Albert (Linux, Docker, albert.local), which only pulls tagged releases: an annotated vX.Y.Z on main after `make check` passes. Keep the container path free of anything Mac-only, and keep docs/DEPLOY.md current (settings, port, data folder, health, upgrades). The Photos export (deploy/photos-sync.sh) stays on Jarvis.
- The photos belong to Memories (the sibling repo, :8002) since 0.3.0. Mantel reads the photo folder read-only (GET /api/photos and the files, unchanged for the iPads) and never writes it; POST/DELETE /api/photos answer 410 with Memories' address.
- One commit per prompt, conventional commit messages. `make check` must pass before you finish.
- The family lives in home/content/ (MANTEL_HOME, git-ignored): never commit it, never put a real name, place or calendar in the tree. Fixtures, tests, the demo and the screenshots use the fictional sample family in content.sample/ (Mira and Kabir, Half Moon Bay). `scripts/scrub-check.sh` must find nothing.
- Park ideas beyond the current prompt in docs/later.md; do not build them.
