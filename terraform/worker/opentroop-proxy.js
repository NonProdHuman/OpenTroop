export default {
  async fetch(request, env, ctx) {
    const requestUrl = new URL(request.url)
    const originalHost = request.headers.get("Host") || requestUrl.host
    const isApiRequest = requestUrl.pathname.startsWith("/api/")
    const isLegacyApiSubdomain = originalHost === `api.${env.APP_DOMAIN}`

    const origin = (isApiRequest || isLegacyApiSubdomain) ? env.API_ORIGIN : env.WEB_ORIGIN
    const originUrl = new URL(origin)

    requestUrl.protocol = "https:"
    requestUrl.host = originUrl.host

    if (isApiRequest) {
      requestUrl.pathname = requestUrl.pathname.substring(4)
    }

    const headers = new Headers(request.headers)
    headers.set("Host", originUrl.host)
    headers.set("X-Forwarded-Host", originalHost)
    headers.set("X-Forwarded-Proto", "https")

    // Origin authentication (GH-116): prove to the backend that this request came
    // through the Worker. Always drop any client-supplied value first — the header
    // is a trust assertion only the Worker may set.
    headers.delete("X-Origin-Auth")
    if (env.ORIGIN_SHARED_SECRET) {
      headers.set("X-Origin-Auth", env.ORIGIN_SHARED_SECRET)
    }

    const init = {
      headers,
      method: request.method,
      redirect: "manual",
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = request.body
    }

    return fetch(new Request(requestUrl.toString(), init))
  }
}
