# Advancement catalog data (GH-92)

Curated seed data for the platform-global advancement catalog, loaded by
`uv run seed-advancement` (`app/core/advancement_catalog.py`). One
`ranks-<version>.json` per BSA version year plus `merit-badges.json`. The loader
is an idempotent upsert — editing a file and re-running corrects rows in place.

## Schemas

`ranks-<version>.json`:

```json
{
  "version": "2025",
  "effective_date": "2025-01-01",
  "ranks": [
    {
      "code": "tenderfoot",            // RankCode enum value
      "name": "Tenderfoot",
      "sort_order": 2,                  // earn-in-sequence order 1–7
      "requirements": [
        {
          "number": "7",
          "letter": "b",               // "" for bare-numbered items
          "text": "…full official wording…",
          "stable_key": "tenderfoot.7b-service",  // cross-version identity (remap key)
          "metrics": [                  // null = plain sign-off item
            {"kind": "service_hours", "threshold": 1, "window": "since_joining"}
          ],
          "auto_credit": true           // engine records completion when metrics met
        }
      ]
    }
  ]
}
```

- List order is display order. A lettered item's parent is the bare-numbered
  item of the same number when one exists (derived by the loader).
- `metrics` conditions are AND-ed; `kind`/`window` must be valid `MetricKind`/
  `MetricWindow` values (the loader rejects the file otherwise).
- Removing an entry tombstones the DB row; re-adding revives it.

`merit-badges.json`: `{"badges": [{"name", "eagle_required", "is_discontinued"}]}`.
Badges are never deleted — retire one by setting `is_discontinued: true`.

## Modeling decisions

- **Cumulative service-hour thresholds.** The rank texts say "one hour" (T 7b),
  "two hours" (2C 8e), "three hours" (FC 9d), each *in addition to* prior ranks'
  hours. Our metrics are cumulative-per-window, so the thresholds are encoded as
  running totals since joining: 1 / 3 / 6. Star/Life service uses `since_rank`
  windows and matches the official six hours directly.
- **`auto_credit: true`** only where the official condition is fully computable:
  the service-hour requirements and the Star/Life merit-badge counts. Tenure
  ("be active") and POR ("serve actively") involve GTA judgment and stay manual
  with progress meters. Eagle requirement 3 is a meter only — its 14 required
  badges include either/or slots (e.g. Emergency Preparedness OR Lifesaving)
  that a flat count of Eagle-required badges cannot express exactly.
- `eagle_required` is flagged on **all** alternates (Cycling/Hiking/Swimming,
  EP/Lifesaving, EnvSci/Sustainability) — 18 badges for the 14 slots.

## Provenance / verification status

Transcribed 2026-07-04 from the current published Scouts BSA requirements
(model knowledge; the official PDF at scouting.org was not fetchable from the
build environment). Wording is believed accurate but **should be verified
against the official Scouts BSA Rank Requirements PDF** — corrections are a
data-file edit plus `uv run seed-advancement`; completions keep their ids.
