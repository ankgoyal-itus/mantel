# Deploying Mantel on Albert

Albert is the house's Linux server. It runs Mantel in Docker from a **tagged
release** (`vX.Y.Z` on `main`, pushed to GitHub). Nothing is built or edited on
Albert by hand beyond its `.env` and the data folder. Jarvis (the Mac) is where
Mantel is developed, and where the nightly Photos export keeps running.

## What runs

One container, `mantel`, built from `Dockerfile`: the FastAPI service with the
kiosk bundled in. It runs as the image's non-root user (uid 10001) and listens
on `0.0.0.0:8000` inside the container.

    git clone https://github.com/ankgoyal-itus/mantel.git && cd mantel   # once
    git fetch --tags && git checkout vX.Y.Z
    docker compose up -d --build

## Environment

Two kinds of setting. Compose reads the first kind from the shell or from a
`.env` next to `docker-compose.yml`; the app reads the second from the same
`.env` (compose passes it in with `env_file`).

**For compose (where it runs)**, all optional:

| Variable | Default | Meaning |
|---|---|---|
| `MANTEL_BIND` | `0.0.0.0` | Host address the port is published on. `0.0.0.0` = the LAN. |
| `MANTEL_PORT` | `8000` | Host port. |
| `MANTEL_HOME` | `./home` | Host data folder. Use an absolute path on Albert, e.g. `/srv/mantel/home`. (A bare name without `./` would become a Docker volume.) |
| `MANTEL_UID`, `MANTEL_GID` | `10001` | Who the container runs as. Must own `MANTEL_HOME`. |
| `MANTEL_IMAGE_TAG` | `latest` | Image tag; set it to the release, e.g. `0.2.0`. |
| `WATCHFILES_FORCE_POLLING` | `1` | Polling for content edits. On Linux set `0`: bind mounts deliver events. |

Inside the container `MANTEL_HOME`, `MANTEL_BIND` and `MANTEL_PORT` are fixed
(`/app/home`, `0.0.0.0`, `8000`), whatever `.env` says for the Mac.

**For the app (secrets)**, the same as on the Mac; never in the repo:

| Variable | Meaning |
|---|---|
| `MANTEL_PARENT_PIN` | Parent mode PIN. |
| `MANTEL_UPLOAD_TOKEN` | Token for `POST`/`DELETE /api/photos` (header `X-Mantel-Token`). |
| `MANTEL_CAL_FAMILY`, `MANTEL_CAL_<KID ID>` | Private calendar feed URLs, one per kid id in `content/family.yaml`. |

Mac-only settings, ignored on Albert: `MANTEL_ALBUM` and `MANTEL_PHOTOS_URL`
(the Photos export, below).

## Port and addresses

- Mantel: **http://albert.local:8000/** (the iPads' address once Mantel runs
  on Albert).
- Health: **GET /api/health** → `{"status": "ok", "version": "<release>", ...}`.
  The container's own `HEALTHCHECK` calls it every 30 s.
- Version: **GET /api/version** → `{"version": <screens' change counter>,
  "changed_at": ..., "release": "<release>"}`. `release` is the `VERSION`
  file, the same as the tag without the `v`.

## Data folder

Everything the family owns is in `MANTEL_HOME`; the image holds none of it.

    content/    the YAML the family edits (parent mode writes here too)
    mantel.db   the points ledger (SQLite)
    backups/    nightly copies of the ledger, rotated
    photos/     the frame's photos: originals/, cache/, failed/, index.json
    cache/      what the API derives from live feeds (safe to delete)

Owner: uid 10001 (or `MANTEL_UID`): `sudo chown -R 10001:10001 /srv/mantel/home`.

## Moving data between versions

- **The ledger upgrades itself.** `mantel.db` carries its schema version
  (`PRAGMA user_version`); a newer release applies the missing steps when it
  opens the file and logs `ledger upgraded from schema N to M`. Upgrades are
  one way: an older release must not open a newer file.
- **Content** is YAML validated on load. A field a new release does not know
  is refused, and the last good file keeps serving; `/api/health` names the
  file. The release notes say when a content file changes shape.
- **Every upgrade:**

      docker compose down
      cp -a /srv/mantel/home /srv/mantel/home.before-vX.Y.Z   # the rollback point
      git fetch --tags && git checkout vX.Y.Z
      MANTEL_IMAGE_TAG=X.Y.Z docker compose up -d --build
      curl -s http://albert.local:8000/api/health

- **Rollback:** `docker compose down`, check out the previous tag, put the
  `home.before-…` copy back (the ledger may already be on the newer schema),
  `docker compose up -d --build`.

## First move from Jarvis

Done once, by hand (Claude never connects to Albert):

1. On Jarvis: `launchctl bootout gui/$(id -u)/com.mantel.api` (stops the
   service; the iPads go blank until step 4).
2. Copy `~/VS-Code-Files/mantel/home/` to Albert's data folder (e.g.
   `rsync -a`), and the secrets from Jarvis's `.env` into Albert's `.env`.
   `chown -R 10001:10001` the copy.
3. On Albert: check out the release and `docker compose up -d --build`;
   `curl http://albert.local:8000/api/health` must say `ok`.
4. Point both iPads at **http://albert.local:8000/** (docs/ipad-setup.md).
5. On Jarvis: `make uninstall-service`. Keep `com.mantel.photos` (below).

## The Photos export stays on Jarvis

The Photos library is on the Mac, so `deploy/photos-sync.sh` (launchd
`com.mantel.photos`, 21:00) keeps running there. It uploads to
`MANTEL_PHOTOS_URL`, read from the environment, then Jarvis's `.env`; the
default is this Mac's own Mantel, `http://127.0.0.1:8000`. Once photos are
served from Albert, set it in Jarvis's `.env`. If nothing answers there, the
export stops before sending anything and leaves the album and `inbox/` as they
were, so the next night picks everything up.
