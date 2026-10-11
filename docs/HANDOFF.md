# Mantel handoff

A dated log for the next session; the durable rules are in CLAUDE.md. Read
docs/later.md and docs/DEPLOY.md too.

- **2026-10-10 (J2, v0.2.0):** Mantel can run on Albert unchanged. The API
  listens on `MANTEL_BIND`:`MANTEL_PORT` (default 0.0.0.0:8000); compose takes
  the host address, port and data folder (`MANTEL_HOME`) and the container user
  from the environment; `/api/version` also names the release. The nightly
  Photos export stays on Jarvis and uploads to `MANTEL_PHOTOS_URL` (default
  this Mac's Mantel, as before). docs/DEPLOY.md written. Mantel still runs on
  Jarvis as `com.mantel.api` until the user moves it (DEPLOY.md, "First move").
