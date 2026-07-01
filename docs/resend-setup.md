# Resend Setup

OpenTroop sends email (invite links today; newsletters and event notifications
later — see issue #75 and
[`docs/spec/messaging.md`](spec/messaging.md)) through
[Resend](https://resend.com), a transactional/bulk email API. App code never
calls Resend directly — it goes through the `EmailBackend` protocol in
`backend/app/core/notifications.py`, so swapping providers later only means
writing a new backend class, not touching callers.

This doc covers signing up and pointing OpenTroop's `EMAIL_BACKEND` config at
your Resend account, for both local dev and a deployed environment.

---

## 1. Create a Resend account

1. Go to [resend.com](https://resend.com) and sign up (GitHub or email).
2. The free tier (100 emails/day, 3,000/month) is enough for local dev and an
   early beta with a handful of troops.

## 2. Verify a sending domain

Resend requires you to send from a domain you control — you can't send from
`@gmail.com` or an unverified domain.

1. In the Resend dashboard, go to **Domains → Add Domain**.
2. Enter the domain you'll send from, e.g. `opentroop.app` (production) or a
   subdomain like `mail.opentroop.app` if you'd rather isolate sending
   reputation from your main domain.
3. Resend gives you DNS records (SPF, DKIM, and a DMARC recommendation) to add
   at your DNS provider. Add them exactly as shown.
4. Wait for verification (usually minutes; DNS propagation can take longer).
   The domain shows **Verified** in the dashboard once it's ready.

> **Local dev shortcut:** you don't need a verified domain to develop against
> the abstraction — set `EMAIL_BACKEND=fake` (the default) and nothing calls
> Resend at all; sends are just recorded in memory. Only switch to
> `EMAIL_BACKEND=resend` once you want to see a real email land in an inbox.

## 3. Create an API key

1. In the dashboard, go to **API Keys → Create API Key**.
2. Give it a name (e.g. `opentroop-dev` or `opentroop-prod`) and
   **Sending access** permission — it doesn't need domain/account admin
   scope.
3. Copy the key (`re_...`) immediately; Resend only shows it once.

Use **separate keys per environment** (dev, staging, prod) so revoking one
doesn't take down the others.

## 4. Configure OpenTroop

The backend reads three settings (`backend/app/core/config.py`):

| Env var | Example | Notes |
|---|---|---|
| `EMAIL_BACKEND` | `resend` | `fake` (default) sends nothing — for local dev/tests |
| `RESEND_API_KEY` | `re_123abc...` | The key from step 3 |
| `EMAIL_FROM_ADDRESS` | `Troop 123 <noreply@opentroop.app>` | Must be `you@<a domain verified in step 2>` |

### Local dev

Add to `backend/.env` (see `backend/.env.example`):

```bash
EMAIL_BACKEND=resend
RESEND_API_KEY=re_your_dev_key
EMAIL_FROM_ADDRESS=noreply@opentroop.app
```

Leave `EMAIL_BACKEND=fake` (or omit it) if you don't need real email — the
`FakeEmailBackend` still runs the full invite flow, it just doesn't call out.

### Cloud Run / production

Store the API key as a secret, not a plain env var (it's a credential):

```bash
echo "re_your_prod_key" | gcloud secrets create RESEND_API_KEY --data-file=-
```

Then wire it into the Cloud Run service alongside the other secrets from
[`docs/deployment.md`](deployment.md):

```bash
gcloud run deploy opentroop-backend \
  --image=us-central1-docker.pkg.dev/<project>/opentroop/backend:latest \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,AUTH_JWKS_URI=AUTH_JWKS_URI:latest,RESEND_API_KEY=RESEND_API_KEY:latest \
  --set-env-vars=EMAIL_BACKEND=resend,EMAIL_FROM_ADDRESS=noreply@opentroop.app \
  --allow-unauthenticated
```

### If deploying via `terraform/` (Scalr)

The repo's Terraform config (`terraform/gcp.tf`, `terraform/variables.tf`)
provisions the Cloud Run services directly and manages this the same way it
manages `clerk_secret_key` — as Terraform variables, not raw `gcloud` calls.
Set these in your Scalr workspace (mirroring the pattern in
[`docs/clerk-setup.md`](clerk-setup.md)):

* `email_backend` = `"resend"` (defaults to `"fake"` — no vendor call — if unset)
* `resend_api_key` = `re_...` (sensitive; stored in Secret Manager, injected
  into the API container as `RESEND_API_KEY`)
* `email_from_address` = `noreply@opentroop.app` (must be on a domain verified
  in step 2)

## 5. Verify it works

With `EMAIL_BACKEND=resend` set and the backend running, invite a member with
an email address (`POST /members/{id}/invite`) and check:

- The response includes `"email_sent": true`.
- The Resend dashboard's **Logs** tab shows the send, with delivery status.
- The invitee's inbox (check spam the first few sends, until your domain
  builds reputation).

If `email_sent` comes back `false`, check the backend logs for a warning —
common causes are an unverified `EMAIL_FROM_ADDRESS` domain or an invalid API
key. `POST /members/{id}/invite` never fails the request over an email
delivery problem; it still returns a valid claim token/link that can be
shared manually.

## What this doesn't cover yet

- **Bounce/complaint webhooks.** `Member.email_bounced` exists as a field but
  nothing sets it yet — that requires wiring a Resend webhook endpoint. Until
  then, a bounced address will keep being retried on every future invite/send.
- **Newsletters and group/event email** (the other two use cases from issue
  #75). Those depend on the `Message`/`MessageRecipient` data model in
  [`docs/spec/messaging.md`](spec/messaging.md), which hasn't been built yet.
- **Per-tenant sending limits.** All tenants currently share one Resend
  account/API key; there's no per-tenant rate limiting or quota isolation, so
  one tenant's high volume or bad content can affect deliverability for
  everyone sharing the domain.
