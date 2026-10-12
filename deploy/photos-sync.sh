#!/bin/sh
# Put photos on the frame, from this Mac.
#
# Two sources, both optional:
#   1. the "Mantel" album in Photos, exported through AppleScript
#   2. anything dropped in inbox/, which needs no permissions at all
#
# Both are uploaded to Memories (the photo frame app, which owns the photos
# since Mantel 0.3.0; Mantel reads the same folder), so its catalogue updates without
# a restart. Re-sending a photo is free: the API recognises it by content and
# skips it.
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
# The Photos album to send. The environment wins, then .env (which is how the
# nightly launchd run gets it), then "Mantel". To keep using an album with
# another name, put MANTEL_ALBUM=<its name> in .env.
ALBUM=${MANTEL_ALBUM:-$(sed -n 's/^MANTEL_ALBUM=//p' "$REPO/.env" 2>/dev/null | tr -d '\r' | head -1)}
ALBUM=${ALBUM:-Mantel}
# Where the photos go: MANTEL_PHOTOS_URL from the environment, then .env, then
# MANTEL_API (its old name), then Memories on Albert (the default since 0.3.0:
# Memories owns the photos; Mantel only reads them).
setting() { sed -n "s/^$1=//p" "$REPO/.env" 2>/dev/null | tr -d '\r' | head -1; }
API=${MANTEL_PHOTOS_URL:-$(setting MANTEL_PHOTOS_URL)}
API=${API:-${MANTEL_API:-http://albert.local:8002}}
API=${API%/}
INBOX="$REPO/inbox"
SENT="$INBOX/sent"

say() { printf '%s\n' "$*"; }

# Photos exports more than photographs: an edited picture comes with a .aae
# sidecar describing the edits, and an album can hold videos. Neither is an
# image, and offering them to the API only fills failed/ with the same files
# every night.
is_image() {
  case $(printf '%s' "${1##*.}" | tr '[:upper:]' '[:lower:]') in
    jpg | jpeg | png | heic | heif | webp | tif | tiff | gif | bmp) return 0 ;;
    *) return 1 ;;
  esac
}

# Memories' upload token: MEMORIES_UPLOAD_TOKEN, else MANTEL_UPLOAD_TOKEN (the
# same value Memories is given; see Memories' docs/DEPLOY.md).
TOKEN=$(setting MEMORIES_UPLOAD_TOKEN)
TOKEN=${TOKEN:-$(setting MANTEL_UPLOAD_TOKEN)}
if [ -z "${TOKEN:-}" ]; then
  say "No MEMORIES_UPLOAD_TOKEN or MANTEL_UPLOAD_TOKEN in $REPO/.env — see docs/photos.md, section 0." >&2
  exit 1
fi

if ! curl -fsS -o /dev/null --max-time 5 "$API/api/health"; then
  say "Nothing answers on $API (MANTEL_PHOTOS_URL). Nothing was sent; the album and" >&2
  say "inbox/ are untouched, so the next run picks everything up." >&2
  exit 1
fi

STAGE=$(mktemp -d "${TMPDIR:-/tmp}/mantel-photos.XXXXXX")
# The staging copy is temporary whatever happens: the API keeps its own
# original, so nothing here is the only copy of anything.
trap 'rm -rf "$STAGE"' EXIT INT TERM

# --- 1. the Photos album ----------------------------------------------------
EXPORTED="skipped"
if [ -d /System/Applications/Photos.app ]; then
  RESULT=$(osascript "$REPO/deploy/export-album.applescript" "$ALBUM" "$STAGE" 2>&1) || true
  case "$RESULT" in
    exported\ *)
      EXPORTED="${RESULT#exported }"
      ;;
    *"-1743"*|*"Not authorized"*)
      say "Photos will not talk to this script yet. Grant it once in" >&2
      say "System Settings -> Privacy & Security -> Automation, then run again." >&2
      say "(Running it by hand from Terminal is what raises the prompt.)" >&2
      EXPORTED="not permitted"
      ;;
    error:\ no\ album*)
      say "No album called \"$ALBUM\" in Photos. Make one and put photos in it." >&2
      EXPORTED="no album"
      ;;
    *)
      say "Photos export failed: $RESULT" >&2
      EXPORTED="failed"
      ;;
  esac
fi

# --- 2. the inbox -----------------------------------------------------------
# Only images, so the folder's own README (and a stray .DS_Store) are not
# offered to the API as photographs. Copied rather than moved, so a failed
# upload cannot lose the file; what succeeds is moved to inbox/sent/ after.
INBOX_COUNT=0
if [ -d "$INBOX" ]; then
  for file in "$INBOX"/*; do
    [ -f "$file" ] || continue
    is_image "$file" || continue
    cp "$file" "$STAGE/" 2>/dev/null || continue
    INBOX_COUNT=$((INBOX_COUNT + 1))
  done
fi

# --- 3. upload --------------------------------------------------------------
RESPONSES="$STAGE/.responses"
: >"$RESPONSES"
SENT_COUNT=0
SKIPPED_KIND=0
for file in "$STAGE"/*; do
  [ -f "$file" ] || continue
  case "$file" in *.responses) continue ;; esac
  if ! is_image "$file"; then
    SKIPPED_KIND=$((SKIPPED_KIND + 1))
    continue
  fi
  # The token reaches curl on stdin (-H @-), never in its arguments: the process
  # list shows every command line to anyone on this Mac. printf is a shell
  # builtin, so no process ever carries the token in its argv.
  if printf 'X-Memories-Token: %s\n' "$TOKEN" | curl -fsS -X POST "$API/api/photos" \
    -H @- \
    -F "file=@$file" >>"$RESPONSES" 2>/dev/null; then
    printf '\n' >>"$RESPONSES"
    SENT_COUNT=$((SENT_COUNT + 1))
  else
    say "upload failed: $(basename "$file")" >&2
  fi
done

ADDED=$(python3 -c '
import json, sys
added = skipped = 0
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        body = json.loads(line)
    except ValueError:
        continue
    added += len(body.get("added", []))
    skipped += len(body.get("skipped", []))
print(f"{added} {skipped}")
' "$RESPONSES" 2>/dev/null || echo "0 0")

# Only now is it safe to clear the inbox: the API has its own copy. Only the
# images are moved — whatever else is in there was never sent.
if [ "$INBOX_COUNT" -gt 0 ]; then
  mkdir -p "$SENT"
  for file in "$INBOX"/*; do
    [ -f "$file" ] || continue
    is_image "$file" || continue
    mv "$file" "$SENT/" 2>/dev/null || true
  done
fi

SUMMARY="album \"$ALBUM\": $EXPORTED | inbox: $INBOX_COUNT | uploaded: $SENT_COUNT"
SUMMARY="$SUMMARY | new: ${ADDED% *}, already had: ${ADDED#* }"
if [ "$SKIPPED_KIND" -gt 0 ]; then
  SUMMARY="$SUMMARY | not photos: $SKIPPED_KIND"
fi
say "$SUMMARY"

# A run by hand leaves the same trace as the nightly one, so there is one
# place to look when someone asks what happened to a photo.
LOG="$HOME/Library/Logs/mantel/photos.log"
if [ -w "$(dirname "$LOG")" ] 2>/dev/null || mkdir -p "$(dirname "$LOG")" 2>/dev/null; then
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$SUMMARY" >>"$LOG" 2>/dev/null || true
fi
