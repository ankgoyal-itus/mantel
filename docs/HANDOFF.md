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
- **2026-10-10 (J3, v0.3.0):** the photo pipeline moved to Memories (new repo,
  :8002): the store, the import, uploads and deletes. Mantel reads the folder
  read-only (`MANTEL_PHOTOS_DIR`; compose `MANTEL_PHOTOS`, mounted `:ro`) and
  keeps `GET /api/photos` and the files; `POST`/`DELETE` answer 410 with
  `MANTEL_MEMORIES_URL` (default http://albert.local:8002). The nightly export
  now defaults to Memories on Albert with `X-Memories-Token`; until Memories runs
  there it stops cleanly every night. The gazetteer (places.py, cities.tsv) went
  with the pipeline. Parent mode's photo delete now shows the 410's message.
- **2026-10-12 (J4, no release):** the Photos export sends the upload token to
  curl on stdin (`printf … | curl -H @-`) instead of as a `-H` argument, which
  the process list showed to anyone on Jarvis during an upload. A test with a
  stand-in curl checks that no command line carries the token or the header
  name. On Jarvis, `com.mantel.api` is disabled (Mantel runs on Albert) and
  `com.mantel.photos` gets `MANTEL_PHOTOS_URL` from its plist. The token that
  was visible before this change should be rotated (Memories and Jarvis's `.env`).
  The script doesn't ship in the image, so there is no release.
