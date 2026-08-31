#!/usr/bin/env bash
# Retrieve memory for a task and print the AGENT MEMORY block.
# Usage: ./scripts/query.sh "task text" --scope user-4821 [--budget 2000] [--include-archived]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"task text\" --scope user-ID [--budget N] [--include-archived]" >&2
  exit 1
fi

TASK="$1"
shift

SCOPE=""
BUDGET=2000
ARCHIVED_FLAG=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope) SCOPE="$2"; shift 2 ;;
    --budget) BUDGET="$2"; shift 2 ;;
    --include-archived) ARCHIVED_FLAG=(--include-archived); shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$SCOPE" ]]; then
  echo "--scope is required (e.g. user-4821)" >&2
  exit 1
fi

membrane_bin retrieve \
  --task "$TASK" \
  --scope "$SCOPE" \
  --budget "$BUDGET" \
  --root "$MEMBRANE_ROOT" \
  --config "$MEMBRANE_CONFIG" \
  "${ARCHIVED_FLAG[@]}"
