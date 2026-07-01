import { NextResponse } from "next/server"
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"

// Define which routes do not require authentication
const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)", "/landing(.*)", "/api(.*)"])

export default clerkMiddleware(async (auth, request) => {
  const url = request.nextUrl

  // Read X-Forwarded-Host since Cloud Run sits behind Cloudflare proxy
  const hostname = request.headers.get("x-forwarded-host") || request.headers.get("host") || ""
  // Single source of truth for the root domain (mirrors backend APP_DOMAIN).
  // Local: "localhost:3000". Production: e.g. "opentroop.dev".
  const appDomain = process.env.NEXT_PUBLIC_APP_DOMAIN || "localhost:3000"
  // The bare root host (and its www alias) is the marketing landing page; tenants
  // live on subdomains of it and the console on admin.<root>.
  const isLanding = hostname === appDomain || hostname === `www.${appDomain}`

  // Treat landing domain's root as public, otherwise protect
  if (isLanding && url.pathname === "/") {
    // skip auth protect
  } else if (!isPublicRoute(request)) {
    await auth.protect()
  }

  // Exclude auth routes, api, and claim from domain rewriting
  if (
    url.pathname.startsWith("/api") ||
    url.pathname.startsWith("/sign-in") ||
    url.pathname.startsWith("/sign-up") ||
    url.pathname.startsWith("/claim")
  ) {
    return NextResponse.next()
  }

  if (hostname.startsWith("admin.")) {
    url.pathname = `/admin${url.pathname}`
    return NextResponse.rewrite(url)
  }

  if (isLanding) {
    url.pathname = `/landing${url.pathname}`
    return NextResponse.rewrite(url)
  }

  // Otherwise, it must be a tenant subdomain
  url.pathname = `/tenant${url.pathname}`
  return NextResponse.rewrite(url)
})

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
}
