# @opentroop/api-types

TypeScript types generated from the backend FastAPI OpenAPI spec — the shared
contract for API consumers in this monorepo (`apps/mobile`; `apps/web` keeps its
own generated copy at `src/types/api.generated.ts` for historical import-path
stability — both come from the same `pnpm gen:api` run).

- **Never edit `index.ts` by hand.** Regenerate with `pnpm gen:api` from the repo
  root; CI fails if the committed file drifts from the backend.
- Consume the schema components via:

  ```ts
  import type { components } from "@opentroop/api-types"

  type Member = components["schemas"]["MemberRead"]
  ```
