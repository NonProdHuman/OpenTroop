# Authentication Provider Setup

OpenTroop validates standard OIDC JWTs — any compliant provider works.
This guide covers the two recommended options:

| Deployment mode | Recommended provider |
|-----------------|----------------------|
| SaaS (opentroop.org) | **Clerk** — managed, free up to 10 K MAUs |
| Self-hosted (single troop) | **Authentik** — open-source, self-managed |

---

## Option A — Clerk (SaaS / hosted)

### 1. Create a Clerk account and application

1. Sign up at **clerk.com**.
2. Click **Create application**.
3. Name it (e.g. "OpenTroop") and choose sign-in methods:
   - Toggle **Email** on (magic link or password — your call).
   - Toggle **Google** on.
   - Toggle **Apple** on if you want iOS support.
4. Click **Create application**.

On the free plan Clerk supplies its own Google/Apple OAuth credentials, so you
don't need a Google Cloud project yet.  Switch to your own credentials before
going to production (see [Use custom OAuth credentials](#use-custom-oauth-credentials)).

### 2. Find your JWKS URL and issuer

In the Clerk dashboard:

- **API Keys** (left sidebar) → copy the **Publishable key** (starts with `pk_`).
  The frontend needs this; the backend does not.
- Your JWKS URL and issuer are derived from your Frontend API hostname shown
  on the same page.  They follow this pattern:
  ```
  JWKS:   https://<frontend-api-hostname>/.well-known/jwks.json
  Issuer: https://<frontend-api-hostname>
  ```
  Example: if your Frontend API is `capable-fox-42.clerk.accounts.dev`, then:
  ```
  AUTH_JWKS_URI=https://capable-fox-42.clerk.accounts.dev/.well-known/jwks.json
  AUTH_ISSUER=https://capable-fox-42.clerk.accounts.dev
  ```

### 3. Configure the OpenTroop backend

Create (or update) `backend/.env`:

```bash
AUTH_JWKS_URI=https://<your-frontend-api>.clerk.accounts.dev/.well-known/jwks.json
AUTH_ISSUER=https://<your-frontend-api>.clerk.accounts.dev
AUTH_AUDIENCE=        # leave blank unless you configure a custom audience in Clerk
APP_DOMAIN=opentroop.org
```

Restart the backend.  The JWKS keys are fetched and cached on first request.

### 4. Configure redirect URLs

In Clerk dashboard → **Redirects**:

- Add your production domain(s): `https://opentroop.org`, `https://*.opentroop.org`
- Add your local dev URL: `http://localhost:3000`

### 5. Frontend integration (Next.js)

```bash
npm install @clerk/nextjs
```

Wrap your app in `ClerkProvider` and call `getToken()` before API requests:

```ts
// app/layout.tsx
import { ClerkProvider } from "@clerk/nextjs";
export default function RootLayout({ children }) {
  return <ClerkProvider>{children}</ClerkProvider>;
}

// Anywhere you call the API
import { useAuth } from "@clerk/nextjs";
const { getToken } = useAuth();
const token = await getToken();
const res = await fetch("/members/", {
  headers: { Authorization: `Bearer ${token}` },
});
```

Clerk exposes `<SignInButton>`, `<UserButton>`, `<SignedIn>`, `<SignedOut>` —
drop them into any component; no OAuth flow code needed.

### Use custom OAuth credentials

For production, register your own Google OAuth app so the consent screen
shows "OpenTroop" rather than "clerk.com":

1. Go to **Google Cloud Console → APIs & Services → Credentials →
   Create OAuth 2.0 Client ID** (Web application).
2. Add `https://accounts.clerk.dev/v1/oauth_callback` as an authorised
   redirect URI (exact value shown in Clerk dashboard when you edit the
   Google connection).
3. Copy the **Client ID** and **Client Secret** into Clerk dashboard →
   **User & Authentication → Social Connections → Google → Use custom
   credentials**.

Repeat for Apple if needed (Apple's process also requires an Apple Developer
account — $99/yr).

### Pricing summary

| Plan | Monthly cost | MAU limit |
|------|-------------|-----------|
| Free | $0 | 10,000 |
| Pro | ~$25 + $0.02/MAU over limit | unlimited |

A typical troop has 30–60 members plus parents ≈ ~150 MAUs max.
Hundreds of troops would still fit comfortably under 10 K MAUs on the
free plan unless every member logs in every month.

---

## Option B — Authentik (self-hosted)

Self-hosted troop leaders who don't want any SaaS dependency run
[Authentik](https://goauthentik.io) alongside OpenTroop.

### Quick setup with docker-compose

Add Authentik to `docker-compose.yml` (see Authentik's documentation for the
full service definition).  Then:

1. Log in to the Authentik admin UI.
2. Create a new **Provider** → type **OAuth2/OpenID Connect**.
3. Set the redirect URI to your OpenTroop backend callback URL.
4. Create an **Application** backed by that provider.
5. Under the provider's **Advanced** settings, note the **OpenID Configuration URL**.
   Append `/.well-known/jwks.json` to get the JWKS URL.

```bash
# backend/.env for self-hosted
AUTH_JWKS_URI=https://authentik.your-server.com/application/o/opentroop/jwks/
AUTH_ISSUER=https://authentik.your-server.com/application/o/opentroop/
AUTH_AUDIENCE=opentroop
APP_DOMAIN=your-server.com
```

No per-user cost; you pay only for the VPS running Authentik.
