#!/usr/bin/env bash
# Background loop: daily eviction often; weekly/monthly on cadence.
# Intended to be launched by start_all.sh (not usually run by hand).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

DAILY_EVERY_SEC="${MEMBRANE_DAILY_EVERY_SEC:-86400}"   # 24h
WEEKLY_EVERY_SEC="${MEMBRANE_WEEKLY_EVERY_SEC:-604800}" # 7d
MONTHLY_EVERY_SEC="${MEMBRANE_MONTHLY_EVERY_SEC:-2592000}" # 30d

# Faster defaults for demos if MEMBRANE_DEMO_SCHEDULE=1
if [[ "${MEMBRANE_DEMO_SCHEDULE:-0}" == "1" ]]; then
  DAILY_EVERY_SEC=300
  WEEKLY_EVERY_SEC=900
  MONTHLY_EVERY_SEC=1800
fi

last_daily=0
last_weekly=0
last_monthly=0

echo "[maintain_loop] started at $(date -u +%Y-%m-%dT%H:%M:%SZ) root=$MEMBRANE_ROOT"

while true; do
  now="$(date +%s)"

  if (( now - last_daily >= DAILY_EVERY_SEC )); then
    echo "[maintain_loop] daily $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    membrane_bin maintain --mode daily --root "$MEMBRANE_ROOT" \
      >>"$MEMBRANE_LOG_DIR/maintain-daily.log" 2>&1 || true
    last_daily=$now
  fi

  if (( now - last_weekly >= WEEKLY_EVERY_SEC )); then
    echo "[maintain_loop] weekly $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    membrane_bin maintain --mode weekly --root "$MEMBRANE_ROOT" \
      >>"$MEMBRANE_LOG_DIR/maintain-weekly.log" 2>&1 || true
    last_weekly=$now
  fi

  if (( now - last_monthly >= MONTHLY_EVERY_SEC )); then
    echo "[maintain_loop] monthly $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    membrane_bin maintain --mode monthly --root "$MEMBRANE_ROOT" \
      >>"$MEMBRANE_LOG_DIR/maintain-monthly.log" 2>&1 || true
    last_monthly=$now
  fi

  sleep 30
done
