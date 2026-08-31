#!/usr/bin/env bash
# Reset runtime state (optional --data to wipe the memory store).
# Usage: ./scripts/reset.sh [--data]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

# Stop background jobs first
bash "$SCRIPT_DIR/stop_all.sh" || true

if [[ "${1:-}" == "--data" ]]; then
  echo "==> Wiping MEMBRANE_ROOT=$MEMBRANE_ROOT"
  rm -rf "$MEMBRANE_ROOT"
  mkdir -p "$MEMBRANE_ROOT"
  membrane_bin init --root "$MEMBRANE_ROOT"
  if [[ -f "$MEMBRANE_HOME/config.yaml" ]]; then
    cp "$MEMBRANE_HOME/config.yaml" "$MEMBRANE_ROOT/config.yaml"
  fi
  echo "==> Fresh store initialized."
else
  echo "==> Cleared run PIDs only. Pass --data to wipe the memory store."
fi
