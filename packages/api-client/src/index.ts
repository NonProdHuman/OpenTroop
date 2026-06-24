import createClient from "openapi-fetch"
import type { paths } from "./schema"

export type { paths }

export function createApiClient(
  baseUrl: string,
  getToken?: () => Promise<string | null>,
) {
  return createClient<paths>({
    baseUrl,
    fetch: async (request) => {
      if (getToken) {
        const token = await getToken()
        if (token) {
          const headers = new Headers(request.headers)
          headers.set("Authorization", `Bearer ${token}`)
          request = new Request(request, { headers })
        }
      }
      return fetch(request)
    },
  })
}
