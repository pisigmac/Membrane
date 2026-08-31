#!/usr/bin/env bash
# Stop Membrane background services started by start_all.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

stopped=0

stop_pidfile() {
  local name="$1"
  local pid_file="$MEMBRANE_RUN_DIR/$name.pid"
  if [[ ! -f "$pid_file" ]]; then
    return 0
  fi
  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "==> Stopping $name (pid $pid)…"
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.4
    done
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    echo "    stopped"
    stopped=1
  else
    echo "==> $name not running (stale pid file)"
  fi
  rm -f "$pid_file"
}

stop_pidfile maintain_loop
stop_pidfile api

if pgrep -f "membrane.*maintain" >/dev/null 2>&1; then
  echo "==> Note: other membrane maintain processes may still be running (cron/manual)."
fi

if [[ "$stopped" -eq 0 ]]; then
  echo "==> No Membrane background services were running."
else
  echo "==> Membrane background services stopped."
fi

echo "==> Store at $MEMBRANE_ROOT is preserved (data is not deleted)."
