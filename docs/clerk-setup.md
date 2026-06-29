# Clerk Auth Setup for `opentroop.dev` (Development Environment)

This guide steps through the manual configuration required in the Clerk Dashboard to create an isolated authentication instance for the `opentroop.dev` environment running on Clerk's Free Plan.

---

## Step 1 — Create a New Clerk Application

1. Log in to the [Clerk Dashboard](https://dashboard.clerk.com).
2. Click the **Add Application** button (or select your application dropdown in the header and click **Create application**).
3. Name the application (e.g. `OpenTroop Dev`).
4. Select the authentication identifiers:
   * **Email Address** (Required — this must match your application's setup to resolve users and link them to pre-provisioned roster members).
   * **Password**
   * **Social Connections:** Enable **Google**, **Apple**, and **Microsoft**.
5. Click **Create Application**.

---

## Step 2 — Activate the Production Instance

By default, new applications start in **Development mode**, which forces a randomized `*.accounts.dev` domain. To bind your custom `opentroop.dev` domain on the Free Plan:

1. In the Clerk Dashboard header, click the environment toggle (set to **Development**) and select **Create production instance**.
2. Select whether to copy settings from your development instance and follow the prompts to activate it.
3. Switch your dashboard view to **Production** in the environment switcher.

---

## Step 3 — Configure Your Custom Domain

Once in Production mode, Clerk allows you to bind one custom domain for free:

1. In the sidebar, navigate to **Configure > Domains**.
2. Enter your primary domain name: `opentroop.dev`.
3. Configure the **Frontend API URL** (Clerk's authentication endpoint):
   * By default, Clerk suggests `clerk.opentroop.dev`.
   * You can customize this to `auth.opentroop.dev` or leave it as `clerk.opentroop.dev`.
4. Clerk will display the DNS records (CNAMEs and TXT records) that need to be added to verify domain ownership.
5. Add these DNS records to your **Cloudflare DNS zone** for `opentroop.dev`.
   *(Note: Since these DNS records are managed manually in your Cloudflare dashboard, they do not need to be written into Terraform).*

---

## Step 4 — Configure Allowed Redirect URLs

To support wildcard subdomains (tenant routing) in the development environment:

1. In the sidebar, navigate to **Configure > Paths** (or **Redirect URLs**).
2. Under **Allowed redirect origins**, add:
   * `http://localhost:3000` (for local development testing)
   * `https://opentroop.dev` (for the apex environment)
   * `https://*.opentroop.dev` (for tenant subdomains)

---

## Step 5 — Retrieve API Keys & Configure Environment

1. Navigate to **Configure > API Keys** in the Clerk sidebar.
2. Copy the **Publishable Key** (starts with `pk_live_...`) and the **Secret Key** (starts with `sk_live_...`).
3. Add these keys to your configuration variables:

### A. Scalr Dev Workspace Variables
Add the keys as Terraform variables in your `opentroop-dev` workspace:
* `clerk_publishable_key` = `pk_live_...`
* `clerk_secret_key` = `sk_live_...`
* `clerk_frontend_api` = `auth.opentroop.dev` (or the Frontend API subdomain you configured in Step 3).

### B. GitHub Actions Environment Secrets
Add the keys to your `development` environment secrets:
* `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` = `pk_live_...`
* `CLERK_SECRET_KEY` = `sk_live_...`

---

## Step 6 — Configure OAuth Credentials for Production Instance

Since your Dev environment runs on a Clerk Production Instance, Clerk's shared developer credentials for social logins are disabled. You must configure custom credentials for your enabled providers in the Clerk Dashboard under **Configure > Social Connections**:
* **Google:** Set up a Google Cloud Console project, configure the OAuth consent screen, and supply your custom Client ID and Client Secret.
* **Microsoft:** Configure an application in the Microsoft Entra ID portal, enable multi-tenant authentication, and supply the Client ID and Secret.
* **Apple:** Register a Service ID, create a private key (`.p8`), and configure the domain association.
