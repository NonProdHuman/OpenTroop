# Clerk Auth Setup for `opentroop.dev` (Development Environment)

This guide steps through the manual configuration required in the Clerk Dashboard to create an isolated authentication instance for the `opentroop.dev` environment.

To keep the development setup simple and avoid the overhead of configuring custom OAuth credentials on Google, Apple, and Microsoft (which requires a paid Apple Developer Account), the development environment runs on a **Clerk Development Instance** (using `pk_test_...` keys).

---

## Step 1 — Create a New Clerk Application

1. Log in to the [Clerk Dashboard](https://dashboard.clerk.com).
2. Click the **Add Application** button (or select your application dropdown in the header and click **Create application**).
3. Name the application (e.g., `OpenTroop Dev`).
4. Select the authentication identifiers:
   * **Email Address** (Required — this must match your application's setup to resolve users and link them to pre-provisioned roster members).
   * **Password**
   * **Social Connections:** Enable **Google**, **Apple**, and **Microsoft**.
5. Click **Create Application**.

---

## Step 2 — Retrieve API Keys & Configure Environment

Since this is a Development Instance, Clerk automatically allows redirects back to the originating domain (such as `localhost` or your dev Cloud Run domain). No manual redirect origins are required in the dashboard.

1. Navigate to **Configure > API Keys** in the Clerk sidebar.
2. Copy the **Publishable Key** (`pk_test_...`) and the **Secret Key** (`sk_test_...`).
3. Note your Clerk development domain (e.g. `merry-arachnid-21.accounts.dev`), which is displayed at the top of the API Keys page.
4. Add these keys/values to your configuration variables:

### A. Scalr Dev Workspace Variables
Add the keys as Terraform variables in your `opentroop-dev` workspace:
* `clerk_publishable_key` = `pk_test_...`
* `clerk_secret_key` = `sk_test_...`
* `clerk_frontend_api` = `your-dev-slug.accounts.dev` (from Step 2, e.g. `merry-arachnid-21.accounts.dev`)

### B. GitHub Actions Environment Secrets
Add the keys to your `development` environment secrets:
* `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` = `pk_test_...`
* `CLERK_SECRET_KEY` = `sk_test_...`
