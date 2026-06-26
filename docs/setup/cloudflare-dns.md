# Cloudflare DNS & Worker Proxy Setup

To support multi-tenant dynamic subdomains (`*.opentroop.app`) without incurring costs for Google Cloud Load Balancers, we use a Cloudflare Worker as a reverse proxy.

## 1. DNS Records Setup
In your Cloudflare dashboard, go to **DNS > Records**:
1. Add an `A` record for `opentroop.app` pointing to a dummy IP like `192.0.2.1` (make sure it is Proxied / orange-clouded).
2. Add a `CNAME` record for `*` pointing to `opentroop.app` (make sure it is Proxied / orange-clouded).
3. Add a `CNAME` record for `api` pointing to the exact `.run.app` URL of your deployed `opentroop-api` Cloud Run service (make sure it is Proxied / orange-clouded).

*Note: Cloudflare automatically provisions free Universal SSL for `opentroop.app` and `*.opentroop.app`.*

## 2. Worker Creation
In your Cloudflare dashboard, go to **Workers & Pages > Overview** and click **Create Application**.
1. Click **Create Worker**.
2. Name it `opentroop-proxy` and click **Deploy**.
3. Once deployed, click **Edit Code** and paste the following:

```javascript
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Define the destination Cloud Run URL for the frontend
    // Update this to match your actual deployed opentroop-web service URL
    const destination = "https://opentroop-web-xxxxx-uc.a.run.app";

    const targetUrl = new URL(destination);
    targetUrl.pathname = url.pathname;
    targetUrl.search = url.search;

    // Create a new request based on the original, but pointing to Cloud Run
    const newRequest = new Request(targetUrl.toString(), request);

    // Pass the original requested hostname so Next.js knows the tenant
    newRequest.headers.set("X-Forwarded-Host", url.hostname);

    return fetch(newRequest);
  }
}
```
4. Click **Save and Deploy**.

## 3. Worker Route
Go back to the **Workers & Pages > opentroop-proxy** settings page.
1. Go to the **Triggers** tab.
2. Under **Routes**, click **Add route**.
3. Enter `*opentroop.app/*` as the route.
4. Select your `opentroop.app` zone.
5. Click **Add route**.

## 4. Testing
Deploy your Next.js application to Cloud Run. Visit `troop123.opentroop.app` and `opentroop.app` to verify they both hit the Next.js app but pass different hostnames!
