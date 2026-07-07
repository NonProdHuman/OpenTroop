import { existsSync, readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

/**
 * Single source of truth for the deterministic demo dataset the e2e specs assert
 * against (GH-245).
 *
 * The JSON is produced by the backend seeder — `uv run seed-dev-data --emit-manifest
 * <path>` — so member/event/location/group names and counts can never silently drift
 * out of sync with what was actually seeded. The e2e stack script writes it to
 * `apps/web/e2e/.seed-manifest.json` (gitignored) right after seeding; specs import
 * `manifest` from here instead of hard-coding strings.
 */

export interface SeedManifest {
  tenant: { slug: string; name: string; id: string }
  counts: {
    scouts: number
    adults: number
    events: number
    locations: number
    groups: number
  }
  members: {
    seniorPatrolLeader: string
    assistantSeniorPatrolLeader: string
    scoutmaster: string
    sampleScout: string
    sampleAdult: string
  }
  events: {
    pastCampout: string
    upcomingMeeting: string
    winterCampout: string
    plcMeeting: string
  }
  locations: { campWapiti: string; church: string; farm: string }
  groups: { patrolLeadersCouncil: string; fundraiserCrew: string }
}

const here = dirname(fileURLToPath(import.meta.url))
const manifestPath =
  process.env.E2E_SEED_MANIFEST ?? resolve(here, "..", ".seed-manifest.json")

function loadManifest(): SeedManifest {
  if (!existsSync(manifestPath)) {
    throw new Error(
      `Seed manifest not found at ${manifestPath}.\n` +
        `Seed the demo tenant with the manifest first, e.g.:\n` +
        `  cd backend && uv run seed-dev-data --reset --emit-manifest ../apps/web/e2e/.seed-manifest.json\n` +
        `(the e2e stack script / CI job does this automatically). ` +
        `Override the path with E2E_SEED_MANIFEST.`,
    )
  }
  return JSON.parse(readFileSync(manifestPath, "utf-8")) as SeedManifest
}

export const manifest: SeedManifest = loadManifest()
