import { NextResponse } from "next/server"
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"

// Define which routes do not require authentication
const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)", "/", "/landing(.*)", "/api(.*)"])

export default clerkMiddleware(async (auth, request) => {
  const url = request.nextUrl

  // Check if it's the root landing page domain to ensure the root '/' is considered public
  const hostname = request.headers.get("host") || ""
  const isLocal = hostname.includes("localhost") || hostname.includes("127.0.0.1")
  const isLanding = isLocal
    ? (hostname === "localhost:3000" || hostname === "opentroop.localhost:3000")
    : (hostname === "opentroop.dev" || hostname === "www.opentroop.dev" || hostname === "opentroop.app")

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
