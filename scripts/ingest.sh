#!/usr/bin/env bash
# Ingest sessions: construct → govern.
# Usage: ./scripts/ingest.sh <sessions.json|jsonl> --user-id ID [--session-id ID]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <sessions.json|jsonl> --user-id ID [--session-id ID]" >&2
  exit 1
fi

INPUT="$1"
shift

USER_ID=""
SESSION_ID="ingest-$(date +%s)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user-id) USER_ID="$2"; shift 2 ;;
    --session-id) SESSION_ID="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$USER_ID" ]]; then
  echo "--user-id is required" >&2
  exit 1
fi

if [[ ! -f "$INPUT" ]]; then
  echo "Input not found: $INPUT" >&2
  exit 1
fi

BATCH="$MEMBRANE_RUN_DIR/batch-$(date +%Y%m%d-%H%M%S).json"

echo "==> Construct from $INPUT"
membrane_bin construct --input "$INPUT" --out "$BATCH" --config "$MEMBRANE_CONFIG"

echo "==> Govern → user-$USER_ID (session $SESSION_ID)"
membrane_bin govern \
  --batch "$BATCH" \
  --user-id "$USER_ID" \
  --session-id "$SESSION_ID" \
  --root "$MEMBRANE_ROOT" \
  --config "$MEMBRANE_CONFIG"

echo "==> Done. Batch: $BATCH"
membrane_bin status --root "$MEMBRANE_ROOT" | head -n 30
