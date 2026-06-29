#!/usr/bin/env bash
set -euo pipefail

api_url="${CLERK_API_URL:-https://api.clerk.com/v1}"
template_name="${CLERK_JWT_TEMPLATE:?CLERK_JWT_TEMPLATE is required}"
claims_json="${CLERK_JWT_CLAIMS_JSON:?CLERK_JWT_CLAIMS_JSON is required}"
lifetime="${CLERK_TEMPLATE_LIFETIME:-3600}"
secret_key="${CLERK_SECRET_KEY:?CLERK_SECRET_KEY is required}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

curl_json() {
  local method="$1"
  local path="$2"
  local data="${3:-}"

  if [[ -n "$data" ]]; then
    curl --fail-with-body --silent --show-error \
      --request "$method" \
      --url "${api_url}${path}" \
      --header "Authorization: Bearer ${secret_key}" \
      --header "Content-Type: application/json" \
      --data "$data"
  else
    curl --fail-with-body --silent --show-error \
      --request "$method" \
      --url "${api_url}${path}" \
      --header "Authorization: Bearer ${secret_key}"
  fi
}

templates_file="${tmpdir}/templates.json"
curl_json GET "/jwt_templates?paginated=false" > "$templates_file"

template_id="$(
  python3 - "$templates_file" "$template_name" <<'PY'
import json
import sys

path, name = sys.argv[1], sys.argv[2]
payload = json.load(open(path))
if isinstance(payload, list):
    templates = payload
elif isinstance(payload, dict):
    templates = payload.get("data", [])
else:
    templates = []

for template in templates:
    if isinstance(template, dict) and template.get("name") == name:
        print(template.get("id", ""))
        break
PY
)"

payload_file="${tmpdir}/payload.json"
python3 - "$template_name" "$claims_json" "$lifetime" > "$payload_file" <<'PY'
import json
import sys

name, claims, lifetime = sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3])
print(json.dumps({"name": name, "claims": claims, "lifetime": lifetime}))
PY

if [[ -n "$template_id" ]]; then
  curl_json PATCH "/jwt_templates/${template_id}" "$(cat "$payload_file")" >/dev/null
  echo "Updated Clerk JWT template '${template_name}'."
else
  curl_json POST "/jwt_templates" "$(cat "$payload_file")" >/dev/null
  echo "Created Clerk JWT template '${template_name}'."
fi
