#!/usr/bin/env bash
# Start Membrane: init store, maintain loop, HTTP API (and hint DeskID + Vite).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

cd "$MEMBRANE_HOME"

echo "==> Membrane home: $MEMBRANE_HOME"
echo "==> MEMBRANE_ROOT: $MEMBRANE_ROOT"

if ! python3 -c "import membrane" >/dev/null 2>&1; then
  echo "==> Installing membrane (editable)…"
  if ! pip3 install -e ".$([ -n "${MEMBRANE_DEV:-}" ] && echo '[dev]')" >/dev/null 2>&1; then
    echo "    pip install failed; using PYTHONPATH=$PYTHONPATH"
  fi
fi

echo "==> Initializing memory layout…"
membrane_bin init --root "$MEMBRANE_ROOT"

if [[ ! -f "$MEMBRANE_CONFIG" && -f "$MEMBRANE_HOME/config.yaml" ]]; then
  cp "$MEMBRANE_HOME/config.yaml" "$MEMBRANE_CONFIG"
  echo "==> Seeded config → $MEMBRANE_CONFIG"
fi

PID_FILE="$MEMBRANE_RUN_DIR/maintain_loop.pid"
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "==> Maintenance loop already running (pid $(cat "$PID_FILE"))"
else
  echo "==> Starting background maintenance loop…"
  nohup bash "$SCRIPT_DIR/maintain_loop.sh" \
    >>"$MEMBRANE_LOG_DIR/maintain_loop.log" 2>&1 &
  echo $! >"$PID_FILE"
  echo "    pid $(cat "$PID_FILE")  log $MEMBRANE_LOG_DIR/maintain_loop.log"
fi

API_PID_FILE="$MEMBRANE_RUN_DIR/api.pid"
if [[ "${MEMBRANE_START_API:-1}" == "1" ]]; then
  if [[ -f "$API_PID_FILE" ]] && kill -0 "$(cat "$API_PID_FILE")" 2>/dev/null; then
    echo "==> Membrane API already running (pid $(cat "$API_PID_FILE"))"
  else
    echo "==> Starting Membrane API (membrane serve)…"
    export MEMBRANE_ROOT
    export MEMBRANE_AUTH_JWKS_URL="${MEMBRANE_AUTH_JWKS_URL:-http://127.0.0.1:8090/.well-known/jwks.json}"
    export MEMBRANE_AUTH_ISSUER="${MEMBRANE_AUTH_ISSUER:-https://auth.pisigma.local}"
    nohup membrane_bin serve --host "${MEMBRANE_API_HOST:-127.0.0.1}" --port "${MEMBRANE_API_PORT:-8787}" \
      --root "$MEMBRANE_ROOT" \
      >>"$MEMBRANE_LOG_DIR/api.log" 2>&1 &
    echo $! >"$API_PID_FILE"
    echo "    pid $(cat "$API_PID_FILE")  http://${MEMBRANE_API_HOST:-127.0.0.1}:${MEMBRANE_API_PORT:-8787}"
  fi
fi

echo "==> Status"
membrane_bin status --root "$MEMBRANE_ROOT" | head -n 40

AUTH_HOME="$(cd "$MEMBRANE_HOME/../DeskID" 2>/dev/null && pwd || true)"

cat <<EOF

Membrane is ready.

  Ingest sessions:  ./scripts/ingest.sh fixtures/sessions.json --user-id 4821
  Query memory:     ./scripts/query.sh "How do I deploy?" --scope user-4821
  Health check:     ./scripts/health.sh
  API:              http://${MEMBRANE_API_HOST:-127.0.0.1}:${MEMBRANE_API_PORT:-8787}/api/health
  Stop services:    ./stop_all.sh

DeskID (shared microservice) — start separately:
  cd ${AUTH_HOME:-../DeskID} && PYTHONPATH=src python3 -m deskid.cli
  # or: deskid / docker compose up -d

Console (Vite):
  cd web && npm install && npm run dev
  → http://localhost:5173  (proxies /api → Membrane, /auth-api → DeskID)

See USAGE.md for multi-user hosting and OAuth setup.
EOF
