addEventListener("fetch", (event) => {
  event.respondWith(proxy(event.request))
})

async function proxy(request) {
  const requestUrl = new URL(request.url)
  const originalHost = request.headers.get("Host") || requestUrl.host
  const origin = originalHost === `api.${APP_DOMAIN}` ? API_ORIGIN : WEB_ORIGIN
  const originUrl = new URL(origin)

  requestUrl.protocol = "https:"
  requestUrl.host = originUrl.host

  const headers = new Headers(request.headers)
  headers.set("Host", originUrl.host)
  headers.set("X-Forwarded-Host", originalHost)
  headers.set("X-Forwarded-Proto", "https")

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
