#!/usr/bin/env bash
# ==============================================================================
# Setup DeskID — Central Identity Engine One-Time Setup Script
# ==============================================================================
# Performs:
#   1. Clones DeskID repository (if not already present)
#   2. Generates local RSA signing keypair (if not already present)
#   3. Initializes .env configuration
#   4. Launches the platform stack via Docker Compose (PostgreSQL + Redis + DeskID Core + UI)
#   5. Verifies service health & endpoints
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEMBRANE_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

DESKID_REPO_URL="${DESKID_REPO_URL:-https://github.com/pisigmac/DeskId.git}"
DESKID_TARGET_DIR="${DESKID_DIR:-./deskid}"

echo -e "${BLUE}${BOLD}=== DeskID: Central Identity Engine Setup ===${NC}\n"

# ------------------------------------------------------------------------------
# 1. Clone & Enter repository
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/4] Checking DeskID repository...${NC}"
if [ -d "$DESKID_TARGET_DIR" ] && [ -f "$DESKID_TARGET_DIR/docker-compose.yml" ]; then
  echo -e "  DeskID repo already exists at: ${GREEN}${DESKID_TARGET_DIR}${NC}"
else
  echo -e "  Cloning ${CYAN}${DESKID_REPO_URL}${NC} into ${GREEN}${DESKID_TARGET_DIR}${NC}..."
  git clone "$DESKID_REPO_URL" "$DESKID_TARGET_DIR"
fi

cd "$DESKID_TARGET_DIR"

# ------------------------------------------------------------------------------
# 2. Generate local signing keys (if not already generated)
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[2/4] Verifying RSA signing keys...${NC}"
if [ -f "private.pem" ] && [ -f "public.pem" ]; then
  echo -e "  Signing keys found: ${GREEN}private.pem${NC} & ${GREEN}public.pem${NC}"
else
  echo -e "  Generating 2048-bit RSA key pair for JWT signing..."
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
  openssl rsa -in private.pem -pubout -out public.pem
  chmod 600 private.pem
  chmod 644 public.pem
  echo -e "  ${GREEN}✓ Keys generated successfully.${NC}"
fi

# Initialize .env if missing
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  echo -e "  Initializing .env from .env.example..."
  cp .env.example .env
fi

# ------------------------------------------------------------------------------
# 3. Launch platform stack via Docker Compose
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[3/4] Launching platform stack (Postgres + Redis + DeskID Core)...${NC}"
docker compose up -d

# ------------------------------------------------------------------------------
# 4. Health & Verification Check
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[4/4] Verifying DeskID service health...${NC}"
HEALTH_URL="http://127.0.0.1:8090/health"
JWKS_URL="http://127.0.0.1:8090/.well-known/jwks.json"

DESKID_HEALTHY=false
echo -n "  Waiting for service to be ready..."
for _ in {1..35}; do
  if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
    DESKID_HEALTHY=true
    break
  fi
  sleep 1
  echo -n "."
done
echo ""

if [ "$DESKID_HEALTHY" = true ]; then
  echo -e "  ${GREEN}${BOLD}✓ DeskID is healthy and operational!${NC}\n"
else
  echo -e "  ${YELLOW}Notice: Healthcheck endpoint not responding yet. Check container status: docker compose ps${NC}\n"
fi

echo -e "--------------------------------------------------------"
echo -e "${BOLD}Central Identity Engine Verification:${NC}"
echo -e "  • Central Auth & JWKS:       ${CYAN}http://localhost:8090/.well-known/jwks.json${NC}"
echo -e "  • Admin Console & UI:        ${CYAN}http://localhost:8090/admin${NC}"
echo -e "  • Interactive OpenAPI Docs:  ${CYAN}http://localhost:8090/docs${NC}"
echo -e "  • Deep Health Check:         ${CYAN}http://localhost:8090/health${NC}"
echo -e "--------------------------------------------------------\n"
