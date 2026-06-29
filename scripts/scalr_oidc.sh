#!/bin/bash

export PROJECT_ID="opentroop"
export POOL_NAME="scalr-pool"
export PROVIDER_NAME="scalr-provider"
export SCALR_ACCOUNT_ID="acc-v0palb5i8lspsbhbs" # Starts with acc-
export SA_NAME="scalr-deployer"

# gcloud iam workload-identity-pools create "${POOL_NAME}" \
#     --project="${PROJECT_ID}" \
#     --location="global" \
#     --display-name="Scalr OIDC Pool" \
#     --description="Identity pool for Scalr deployments"

# gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_NAME}" \
#     --project="${PROJECT_ID}" \
#     --location="global" \
#     --workload-identity-pool="${POOL_NAME}" \
#     --display-name="Scalr Provider" \
#     --issuer-uri="https://scalr.io" \
#     --allowed-audiences="https://scalr.io" \
#     --attribute-mapping="google.subject=assertion.sub,attribute.aud=assertion.aud,attribute.scalr_account_id=assertion.scalr_account_id,attribute.scalr_environment_id=assertion.scalr_environment_id,attribute.scalr_workspace_id=assertion.scalr_workspace_id" \
#     --attribute-condition="attribute.scalr_account_id == '${SCALR_ACCOUNT_ID}'"

# gcloud iam service-accounts create "${SA_NAME}" \
#     --project="${PROJECT_ID}" \
#     --display-name="Scalr Deployment Service Account"

PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
echo $PROJECT_NUMBER

# gcloud iam service-accounts add-iam-policy-binding "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
#     --project="${PROJECT_ID}" \
#     --role="roles/iam.workloadIdentityUser" \
#     --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.scalr_account_id/${SCALR_ACCOUNT_ID}"

# gcloud iam workload-identity-pools create-cred-config \
#     "projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}" \
#     --service-account="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
#     --output-file=scalr-gcp-oidc.json \
#     --credential-source-file="/" \
#     --credential-source-type="text"
