#!/usr/bin/env bash
# Refuse to start when the port is already taken, and say who has it.
#
# The failure this prevents: once com.mantel.api is installed, launchd holds
# :8000 with whatever code it started with. `make dev` then loses the port
# silently, the API keeps answering, and every new prompt looks like it never
# landed. Better to stop here than to debug that twice.
set -euo pipefail

PORT="${1:-8000}"
PIDS=$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)

if [ -z "$PIDS" ]; then
  exit 0
fi

{
  echo
  echo ":$PORT is already in use."
  echo

  FIX=""
  for PID in $PIDS; do
    PPID_OF=$(ps -o ppid= -p "$PID" 2>/dev/null | tr -d ' ' || true)
    COMMAND=$(ps -o command= -p "$PID" 2>/dev/null || echo "unknown")
    echo "  PID $PID  $COMMAND"

    if [ "$PPID_OF" = "1" ]; then
      LABEL=$(launchctl list 2>/dev/null | awk -v pid="$PID" '$1 == pid { print $3 }' | head -1)
      if [ -n "$LABEL" ]; then
        echo "  owner: launchd ($LABEL)"
        FIX="launchctl bootout gui/$(id -u)/$LABEL"
      else
        echo "  owner: launchd"
      fi
    else
      echo "  owner: a terminal (parent PID ${PPID_OF:-unknown}) — another make dev, make serve, or docker"
    fi
  done

  echo
  if [ -n "$FIX" ]; then
    echo "Free it with:"
    echo "  $FIX"
  else
    echo "Stop that process first (Ctrl-C in its terminal, or 'make down' for Docker)."
  fi
  echo
  echo "Then run this again."
  echo
} >&2

exit 1
