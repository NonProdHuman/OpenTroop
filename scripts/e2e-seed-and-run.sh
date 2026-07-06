#!/usr/bin/env bash
#
# e2e-seed-and-run.sh — seed the deterministic demo tenant (emitting the e2e
# manifest) and run the Playwright suite against an already-running local stack
# (GH-245). Bring the stack up first with `./start.sh`.
#
# The manifest (apps/web/e2e/.seed-manifest.json) is the single source of truth
# the specs assert against, so this script always re-seeds with --reset so the
# data and the manifest are guaranteed consistent.
#
# Usage:
#   ./start.sh                       # in another terminal: Postgres + backend + web
#   scripts/e2e-seed-and-run.sh      # seed + run e2e
#   scripts/e2e-seed-and-run.sh --ui # same, Playwright UI mode
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${REPO_ROOT}/apps/web/e2e/.seed-manifest.json"
BASE_URL="${E2E_BASE_URL:-http://demo.localhost:3000}"

echo "==> Checking the web app is reachable at ${BASE_URL} …"
if ! curl -fsS -o /dev/null "${BASE_URL}" 2>/dev/null; then
  echo "ERROR: ${BASE_URL} is not reachable. Start the stack first: ./start.sh" >&2
  exit 1
fi

echo "==> Seeding the demo tenant + emitting the e2e manifest …"
(
  cd "${REPO_ROOT}/backend"
  uv run seed-dev-data --reset --emit-manifest "${MANIFEST}"
)

echo "==> Running Playwright e2e …"
if [[ "${1:-}" == "--ui" ]]; then
  pnpm --filter web e2e:ui
else
  pnpm --filter web e2e
fi
