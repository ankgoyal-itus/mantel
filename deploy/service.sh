#!/bin/sh
# Install or remove the com.mantel.api launchd agent. Called by `make
# install-service` / `make uninstall-service`; safe to run twice.
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
LOGS="$HOME/Library/Logs/mantel"
DOMAIN="gui/$(id -u)"

plist_for() { echo "$HOME/Library/LaunchAgents/$1.plist"; }

# bootout is the modern spelling; macOS 10.14 and older only know unload.
stop_agent() {
  launchctl bootout "$DOMAIN/$1" 2>/dev/null ||
    launchctl unload "$(plist_for "$1")" 2>/dev/null ||
    true
}

write_plist() {
  mkdir -p "$HOME/Library/LaunchAgents" "$LOGS"
  sed -e "s|__REPO__|$REPO|g" -e "s|__LOGS__|$LOGS|g" \
    "$REPO/deploy/$1.plist.template" >"$(plist_for "$1")"
}

load_agent() {
  launchctl bootstrap "$DOMAIN" "$(plist_for "$1")" 2>/dev/null ||
    launchctl load -w "$(plist_for "$1")"
}

case "${1:-}" in
  install)
    LABEL=com.mantel.api
    PLIST=$(plist_for "$LABEL")
    if [ ! -x "$REPO/services/api/.venv/bin/python" ]; then
      echo "No virtualenv at services/api/.venv — run 'make install' first." >&2
      exit 1
    fi
    if [ ! -f "$REPO/services/api/static/index.html" ]; then
      echo "No kiosk build — run 'make build' first." >&2
      exit 1
    fi
    # KeepAlive would turn a busy port into a restart loop that only shows up
    # in the log, so refuse now. `make dev` is the usual culprit.
    if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
      echo "Port 8000 is already in use — stop 'make dev' (or 'make down') first:" >&2
      lsof -nP -iTCP:8000 -sTCP:LISTEN >&2
      exit 1
    fi

    write_plist "$LABEL"
    stop_agent "$LABEL"
    load_agent "$LABEL"

    echo "Installed $PLIST"
    echo "Logs:      $LOGS/api.log and $LOGS/api.err.log"
    echo "Restart:   launchctl kickstart -k $DOMAIN/$LABEL"
    echo "Status:    launchctl print $DOMAIN/$LABEL | head"
    cat <<RULE

From now on this agent owns :8000 and runs the code it was installed with.
It does not pick up new commits, and it does not step aside for 'make dev'.

  Before working on Mantel:
    launchctl bootout $DOMAIN/$LABEL
    make dev

  Confirm the port is yours — one process, and its parent is not 1:
    lsof -nP -iTCP:8000 -sTCP:LISTEN
    curl -s localhost:8000/openapi.json |
      python3 -c "import sys,json; print('\n'.join(sorted(json.load(sys.stdin)['paths'])))"

  Done for the day — put the iPads back on the service:
    make build
    launchctl bootstrap $DOMAIN $PLIST

'make dev' now refuses to start when something else holds :8000 and tells you
what to boot out, so a lost port cannot look like a prompt that never landed.
RULE
    ;;

  uninstall)
    LABEL=com.mantel.api
    stop_agent "$LABEL"
    rm -f "$(plist_for "$LABEL")"
    echo "Removed $(plist_for "$LABEL"). Logs in $LOGS were left alone."
    ;;

  install-photos)
    LABEL=com.mantel.photos
    if [ ! -x "$REPO/deploy/photos-sync.sh" ]; then
      echo "deploy/photos-sync.sh is missing or not executable." >&2
      exit 1
    fi

    write_plist "$LABEL"
    stop_agent "$LABEL"
    load_agent "$LABEL"

    echo "Installed $(plist_for "$LABEL") — runs nightly at 21:00"
    echo "Log:       $LOGS/photos.log"
    echo "Run now:   launchctl kickstart $DOMAIN/$LABEL"
    echo
    echo "The first run needs permission to read Photos. Run it once by hand,"
    echo "from Terminal, and click OK when macOS asks:"
    echo "  $REPO/deploy/photos-sync.sh"
    ;;

  uninstall-photos)
    LABEL=com.mantel.photos
    stop_agent "$LABEL"
    rm -f "$(plist_for "$LABEL")"
    echo "Removed $(plist_for "$LABEL")."
    ;;

  render)
    # The two new plists, written for review without loading anything.
    # Not into ~/Library/LaunchAgents: launchd loads every plist there at
    # login, and two agents wanting :8000 would fight until `switch` runs.
    OUT=${2:-"$REPO/.local/launchd"}
    mkdir -p "$OUT"
    for LABEL in com.mantel.api com.mantel.photos; do
      sed -e "s|__REPO__|$REPO|g" -e "s|__LOGS__|$LOGS|g" \
        "$REPO/deploy/$LABEL.plist.template" >"$OUT/$LABEL.plist"
      echo "Wrote $OUT/$LABEL.plist"
    done
    ;;

  switch)
    # From an older install of this app to this checkout: its launchd agents
    # stopped, its family state moved into home/, these agents started.
    # The old install is described in .env, so nothing about it is in the
    # tree:
    #   MANTEL_SWITCH_FROM    the old checkout (its content/ holds the state)
    #   MANTEL_SWITCH_LABELS  its launchd labels, space-separated
    #   MANTEL_SWITCH_DB      its ledger's file name inside content/
    # Everything is moved, never copied or rewritten.
    envget() { sed -n "s/^$1=//p" "$REPO/.env" 2>/dev/null | tr -d '\r"' | head -1; }
    OLD=$(envget MANTEL_SWITCH_FROM)
    OLD_LABELS=$(envget MANTEL_SWITCH_LABELS)
    OLD_DB=$(envget MANTEL_SWITCH_DB)
    HOME_DIR="$REPO/home"
    if [ -z "$OLD" ] || [ -z "$OLD_LABELS" ] || [ -z "$OLD_DB" ]; then
      echo "Set MANTEL_SWITCH_FROM, MANTEL_SWITCH_LABELS and MANTEL_SWITCH_DB in $REPO/.env." >&2
      exit 1
    fi
    case "$OLD" in /*) ;; *) OLD="$REPO/$OLD" ;; esac
    [ -d "$OLD/content" ] || { echo "No $OLD/content to move from." >&2; exit 1; }
    [ -x "$REPO/services/api/.venv/bin/python" ] || { echo "Run 'make install' first." >&2; exit 1; }
    [ -f "$REPO/services/api/static/index.html" ] || { echo "Run 'make build' first." >&2; exit 1; }
    if ! grep -q '^MANTEL_PARENT_PIN=' "$REPO/.env" 2>/dev/null; then
      echo "No MANTEL_PARENT_PIN in $REPO/.env." >&2
      exit 1
    fi

    echo "1/4  Stopping the old agents: $OLD_LABELS"
    for LABEL in $OLD_LABELS; do stop_agent "$LABEL"; done
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1 || break
      sleep 1
    done
    if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
      echo "Something still holds :8000; nothing has been moved:" >&2
      lsof -nP -iTCP:8000 -sTCP:LISTEN >&2
      exit 1
    fi

    echo "2/4  Moving the family's state into $HOME_DIR"
    if [ -e "$HOME_DIR" ]; then
      ASIDE="$HOME_DIR.pre-switch-$(date +%Y%m%d-%H%M%S)"
      mv "$HOME_DIR" "$ASIDE"
      echo "     (an existing home/ was moved aside to $ASIDE)"
    fi
    mkdir -p "$HOME_DIR/content"
    for FILE in "$OLD"/content/*.yaml; do
      [ -e "$FILE" ] && mv "$FILE" "$HOME_DIR/content/"
    done
    [ -d "$OLD/content/.cache" ] && mv "$OLD/content/.cache" "$HOME_DIR/cache"
    [ -d "$OLD/content/.backup" ] && mv "$OLD/content/.backup" "$HOME_DIR/backups"
    [ -d "$OLD/content/photos" ] && mv "$OLD/content/photos" "$HOME_DIR/photos"
    for SUFFIX in "" -wal -shm; do
      [ -e "$OLD/content/$OLD_DB$SUFFIX" ] && mv "$OLD/content/$OLD_DB$SUFFIX" "$HOME_DIR/mantel.db$SUFFIX"
    done
    for FILE in "$OLD"/inbox/*; do
      case "$FILE" in */README.md|"$OLD/inbox/*") ;; *) mv "$FILE" "$REPO/inbox/" ;; esac
    done
    LEFT=$(ls -A "$OLD/content" 2>/dev/null || true)
    [ -n "$LEFT" ] && echo "     Left in $OLD/content (not family state): $LEFT"

    echo "3/4  Retiring the old plists, starting the new agents"
    RETIRED="$HOME/Library/LaunchAgents/retired"
    mkdir -p "$RETIRED"
    for LABEL in $OLD_LABELS; do
      [ -e "$(plist_for "$LABEL")" ] && mv "$(plist_for "$LABEL")" "$RETIRED/"
    done
    for LABEL in com.mantel.api com.mantel.photos; do
      write_plist "$LABEL"
      stop_agent "$LABEL"
      load_agent "$LABEL"
    done

    echo "4/4  Checking"
    LAN_IF=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')
    LAN_IP=$(ipconfig getifaddr "$LAN_IF" 2>/dev/null || echo localhost)
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
      curl -fsS localhost:8000/api/health >/dev/null 2>&1 && break
      sleep 1
    done
    curl -fsS localhost:8000/api/health 2>/dev/null | head -c 400 || echo "     The API did not answer; see $LOGS/api.err.log"
    echo
    echo "Check the wall: http://$LAN_IP:8000/"
    echo "Back out: launchctl bootout $DOMAIN/com.mantel.api, move home/* back to"
    echo "$OLD/content (mantel.db -> $OLD_DB), and bootstrap the plists in $RETIRED."
    ;;

  *)
    echo "usage: $0 install|uninstall|install-photos|uninstall-photos|render|switch" >&2
    exit 2
    ;;
esac
