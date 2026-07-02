#!/usr/bin/env bash
#
# gen-api.sh — regenerate apps/web/src/types/api.generated.ts from the backend
# OpenAPI spec. Run via `pnpm gen:api` from the repo root.
#
# 1. Export the FastAPI OpenAPI schema (deterministic JSON) from backend/.
# 2. Run openapi-typescript to produce the committed generated types.
#
# The backend settings below are dummy values — the OpenAPI schema does not depend
# on real secrets, and hard-coding them keeps `pnpm gen:api` runnable anywhere
# (CI, a fresh clone) without a configured .env. They mirror the CI env block.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_FILE="$(mktemp -t opentroop-openapi.XXXXXX.json)"
OUT_FILE="$REPO_ROOT/apps/web/src/types/api.generated.ts"
trap 'rm -f "$SPEC_FILE"' EXIT

export APP_DOMAIN="${APP_DOMAIN:-opentroop.local}"
export APP_SECRET="${APP_SECRET:-gen-api-dummy-secret-not-a-real-credential}"  # gitleaks:allow
export CORS_ORIGINS="${CORS_ORIGINS:-[\"http://localhost:3000\"]}"

uv --directory "$REPO_ROOT/backend" run export-openapi --out "$SPEC_FILE"

pnpm --filter web exec openapi-typescript "$SPEC_FILE" --output "$OUT_FILE"

# Prepend an eslint-disable + do-not-edit banner (openapi-typescript's own header
# doesn't disable lint rules or point at the regeneration command).
BANNER="/* eslint-disable */
/**
 * DO NOT EDIT. This file is generated from the backend OpenAPI spec.
 * Regenerate with \`pnpm gen:api\` (see scripts/gen-api.sh).
 */
"
printf '%s\n' "$BANNER" | cat - "$OUT_FILE" > "$OUT_FILE.tmp" && mv "$OUT_FILE.tmp" "$OUT_FILE"

echo "OK: wrote $OUT_FILE"
