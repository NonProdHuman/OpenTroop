#!/usr/bin/env python3
"""
export_openapi.py — Dump the FastAPI OpenAPI schema as deterministic JSON.

This is the source of truth for the web app's generated TypeScript types
(`apps/web/src/types/api.generated.ts`). The output is byte-stable — keys are
sorted and a trailing newline is emitted — so regenerating it produces a clean
diff only when the backend schema actually changed. CI regenerates and diffs to
catch schemas that drifted without regenerated types.

    uv run export-openapi              # write JSON to stdout
    uv run export-openapi --out spec.json

Requires the same settings env as the app (APP_DOMAIN, APP_SECRET, CORS_ORIGINS).
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write JSON to this path instead of stdout",
    )
    args = parser.parse_args()

    from app.main import app

    spec = app.openapi()
    text = json.dumps(spec, sort_keys=True, indent=2) + "\n"

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"OK: wrote OpenAPI spec to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
