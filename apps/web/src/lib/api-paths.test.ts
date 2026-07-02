import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

/**
 * Static sweep of every `request(...)` call in src/: the path portion (before any
 * query string) must not end with "/".
 *
 * Backend routes are declared at "" (canonical /foo). A trailing slash — bare
 * (`/foo/`) or in front of a query string (`/foo/?bar=x`) — makes the backend
 * 307-redirect to the canonical path, and because /api/* is proxied cross-origin,
 * the browser drops the Clerk Authorization header on the redirect → 401 / empty
 * data. The runtime guards in collection-paths.test.tsx only cover the hooks they
 * enumerate; this scan covers every current and future call site. Regression guard
 * for issues #97 and #109.
 */

const SRC_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")

function sourceFiles(): string[] {
  return fs
    .readdirSync(SRC_ROOT, { recursive: true, encoding: "utf-8" })
    .filter((f) => /\.(ts|tsx)$/.test(f) && !/\.(test|spec)\.(ts|tsx)$/.test(f))
    .map((f) => path.join(SRC_ROOT, f))
}

// Matches request("..."), request<T>(`...`), etc., capturing the path literal.
// The literal must start with "/" to be an API path.
const REQUEST_CALL = /\brequest(?:<[^>]*>)?\(\s*(["'`])(\/(?:(?!\1).)*)\1/g

function violationsIn(file: string): string[] {
  const content = fs.readFileSync(file, "utf-8")
  const bad: string[] = []
  for (const match of content.matchAll(REQUEST_CALL)) {
    const literal = match[2]
    const pathPart = literal.split("?")[0]
    if (pathPart.endsWith("/")) {
      bad.push(literal)
    }
  }
  return bad
}

describe("API request paths", () => {
  it("never end the path portion with a trailing slash", () => {
    const files = sourceFiles()
    // Sanity: the scan actually sees the codebase and its request() calls.
    expect(files.length).toBeGreaterThan(50)

    const violations = files.flatMap((file) =>
      violationsIn(file).map(
        (literal) => `${path.relative(SRC_ROOT, file)}: request("${literal}")`,
      ),
    )
    expect(violations).toEqual([])
  })

  it("the scanner itself catches both trailing-slash shapes", () => {
    // Guard the guard: if the regex rots, this fails rather than silently passing.
    const fixture = `
      const a = request<Foo[]>(\`/relationships/?member_id=\${memberId}\`)
      const b = request("/tenant/settings/")
      const c = request("/members")
      const d = request(\`/members/\${id}/positions?current=false\`)
    `
    const bad: string[] = []
    for (const match of fixture.matchAll(REQUEST_CALL)) {
      if (match[2].split("?")[0].endsWith("/")) bad.push(match[2])
    }
    expect(bad).toEqual(["/relationships/?member_id=${memberId}", "/tenant/settings/"])
  })
})
