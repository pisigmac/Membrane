#!/usr/bin/env bash
# Print health + unresolved contradictions.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

echo "==> MEMBRANE_ROOT=$MEMBRANE_ROOT"
if [[ -f "$MEMBRANE_RUN_DIR/maintain_loop.pid" ]]; then
  pid="$(cat "$MEMBRANE_RUN_DIR/maintain_loop.pid")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "==> maintain_loop: running (pid $pid)"
  else
    echo "==> maintain_loop: not running (stale pid $pid)"
  fi
else
  echo "==> maintain_loop: not started"
fi

membrane_bin status --root "$MEMBRANE_ROOT"
