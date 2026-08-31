#!/usr/bin/env bash
# Shared environment for Membrane scripts.
# shellcheck disable=SC2034

MEMBRANE_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export MEMBRANE_HOME

export MEMBRANE_ROOT="${MEMBRANE_ROOT:-$MEMBRANE_HOME/.membrane}"
export MEMBRANE_CONFIG="${MEMBRANE_CONFIG:-$MEMBRANE_ROOT/config.yaml}"
export MEMBRANE_RUN_DIR="${MEMBRANE_RUN_DIR:-$MEMBRANE_ROOT/run}"
export MEMBRANE_LOG_DIR="${MEMBRANE_LOG_DIR:-$MEMBRANE_ROOT/logs}"
export PYTHONPATH="${PYTHONPATH:-}:$MEMBRANE_HOME/src"

mkdir -p "$MEMBRANE_ROOT" "$MEMBRANE_RUN_DIR" "$MEMBRANE_LOG_DIR"

membrane_bin() {
  if command -v membrane >/dev/null 2>&1; then
    command membrane "$@"
  else
    python3 -m membrane "$@"
  fi
}
