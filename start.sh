#!/usr/bin/env bash
# start.sh — Start the OpenTroop development stack.
#
# Starts Postgres via Docker (db only), runs the backend with uvicorn
# directly so backend/.env is loaded, validates Clerk alignment between
# frontend and backend, then launches the Next.js frontend.
#
# Usage:  ./start.sh
# Logs:   tail -f /tmp/opentroop-backend.log
#
# Prerequisites: docker, uv, pnpm, python3, curl
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""

die()  { echo -e "${RED}✗  $*${NC}" >&2; exit 1; }
ok()   { echo -e "${GREEN}✓  $*${NC}"; }
info() { echo -e "${BOLD}▶  $*${NC}"; }

cleanup() {
  echo ""
  info "Shutting down backend..."
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    pkill -P "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# 1. Prerequisites
# ---------------------------------------------------------------------------
for tool in docker uv pnpm python3 curl; do
  command -v "$tool" >/dev/null 2>&1 || die "'$tool' not found — install it and retry"
done

# ---------------------------------------------------------------------------
# 2. Env files
# ---------------------------------------------------------------------------
[[ -f "$REPO/apps/web/.env.local" ]] || die \
  "apps/web/.env.local not found.\n  Run: cp apps/web/.env.local.example apps/web/.env.local"

[[ -f "$REPO/backend/.env" ]] || die \
  "backend/.env not found.\n  Run: cp backend/.env.example backend/.env"

# Read a value from a .env file (strips surrounding quotes)
env_val() { grep -E "^${2}=" "$1" 2>/dev/null | head -1 | cut -d'=' -f2- | sed "s/^['\"]//;s/['\"]$//"; }

# ---------------------------------------------------------------------------
# 3. Validate Clerk alignment
# ---------------------------------------------------------------------------
info "Checking Clerk configuration..."

FRONTEND_KEY=$(env_val "$REPO/apps/web/.env.local" "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
[[ -n "$FRONTEND_KEY" ]] || die \
  "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY not set in apps/web/.env.local"

# Decode the publishable key to extract the Clerk instance hostname.
# Format: pk_test_<base64(hostname$)>
FRONTEND_HOST=$(python3 -c '
import base64, sys
raw = sys.argv[1].split("_", 2)[2]
raw += "=" * (-len(raw) % 4)
print(base64.b64decode(raw).decode().rstrip("$"))
' "$FRONTEND_KEY") || die "Could not decode Clerk publishable key"

EXPECTED_ISSUER="https://${FRONTEND_HOST}"
BACKEND_ISSUER=$(env_val "$REPO/backend/.env" "AUTH_ISSUER")

if [[ "$BACKEND_ISSUER" != "$EXPECTED_ISSUER" ]]; then
  echo -e "${RED}✗  Clerk instance mismatch — the backend will reject all tokens${NC}"
  echo ""
  echo "  Frontend key → ${EXPECTED_ISSUER}"
  echo "  backend/.env AUTH_ISSUER → ${BACKEND_ISSUER:-"(not set)"}"
  echo ""
  echo "  Fix backend/.env:"
  echo "    AUTH_ISSUER=${EXPECTED_ISSUER}"
  echo "    AUTH_JWKS_URI=${EXPECTED_ISSUER}/.well-known/jwks.json"
  exit 1
fi
ok "Clerk instances match (${FRONTEND_HOST})"

# ---------------------------------------------------------------------------
# 4. Ensure the Docker backend container is not stealing port 8000.
#    The backend must run via uvicorn directly so backend/.env is loaded.
# ---------------------------------------------------------------------------
if docker compose -f "$REPO/docker-compose.yml" ps --services --status running 2>/dev/null \
    | grep -q "^backend$"; then
  echo -e "${YELLOW}⚠  Docker 'backend' container is running on port 8000.${NC}"
  echo "   Stopping it so uvicorn can start with the correct env vars..."
  docker compose -f "$REPO/docker-compose.yml" stop backend
fi

# ---------------------------------------------------------------------------
# 5. Start Postgres (db only — backend runs outside Docker so .env is loaded)
# ---------------------------------------------------------------------------
info "Starting Postgres..."
docker compose -f "$REPO/docker-compose.yml" -f "$REPO/docker-compose.override.yml" \
  up db --detach --wait \
  || die "Failed to start Postgres. Is Docker running?"
ok "Postgres ready on 127.0.0.1:5432"

# ---------------------------------------------------------------------------
# 6. Migrations
# ---------------------------------------------------------------------------
info "Applying migrations..."
(cd "$REPO/backend" && uv run alembic upgrade head 2>&1) | sed 's/^/    /'
ok "Migrations up to date"

# ---------------------------------------------------------------------------
# 7. Backend (uvicorn — reads backend/.env directly)
# ---------------------------------------------------------------------------
info "Starting backend..."
(cd "$REPO/backend" && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) \
  >"${TMPDIR:-/tmp}/opentroop-backend.log" 2>&1 &
BACKEND_PID=$!

for i in $(seq 1 20); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    ok "Backend ready on http://127.0.0.1:8000"
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo -e "${RED}✗  Backend exited unexpectedly. Last output:${NC}"
    tail -20 "${TMPDIR:-/tmp}/opentroop-backend.log" | sed 's/^/    /'
    exit 1
  fi
  [[ $i -lt 20 ]] || die "Backend didn't start in time. See ${TMPDIR:-/tmp}/opentroop-backend.log"
  sleep 0.5
done

# ---------------------------------------------------------------------------
# 8. Frontend
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}  ┌─────────────────────────────────────────┐${NC}"
echo -e "${BOLD}  │  App   →  http://localhost:3000          │${NC}"
echo -e "${BOLD}  │  API   →  http://localhost:8000/docs     │${NC}"
echo -e "${BOLD}  │  Logs  →  tail -f \${TMPDIR}/opentroop-backend.log │${NC}"
echo -e "${BOLD}  └─────────────────────────────────────────┘${NC}"
echo ""

(cd "$REPO" && pnpm dev) || true
