#!/usr/bin/env bash
set -e

echo "=== OpenTroop GCP Auth & Infrastructure Setup ==="
echo "This script configures Google Cloud for GitHub Actions deployments using Workload Identity Federation."
echo "You must be logged in to gcloud ('gcloud auth login') with Owner/Editor permissions."
echo ""

# Configuration variables
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "Error: No GCP project selected. Run 'gcloud config set project YOUR_PROJECT_ID'"
    exit 1
fi

GITHUB_REPO="NonProdHuman/OpenTroop" # Using your current GitHub repo
REGION="us-central1" # Default region for Cloud Run and Artifact Registry
SA_NAME="github-actions-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
POOL_NAME="github-actions-pool"
PROVIDER_NAME="github-actions-provider"
AR_REPO="opentroop-containers"

echo "Target Project: $PROJECT_ID"
echo "GitHub Repo:    $GITHUB_REPO"
echo "Region:         $REGION"
echo ""
read -p "Press Enter to continue or Ctrl+C to abort..."

echo "1. Enabling required APIs..."
gcloud services enable \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    cloudresourcemanager.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com

echo "2. Creating Service Account: $SA_NAME"
gcloud iam service-accounts create "$SA_NAME" \
    --display-name="GitHub Actions Service Account" || echo "Service account may already exist."

echo "3. Assigning roles to the Service Account..."
# Allow deploying to Cloud Run
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.admin"
# Allow acting as itself (required for Cloud Run to use this SA)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser"
# Allow reading/writing to Artifact Registry
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/artifactregistry.writer"
# Allow reading secrets (for Cloud Run to fetch DB URLs)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"

echo "4. Creating Artifact Registry repository: $AR_REPO"
gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="OpenTroop Docker repository" || echo "Repository may already exist."

echo "5. Setting up Workload Identity Federation (WIF)..."
# Create Pool
gcloud iam workload-identity-pools create "$POOL_NAME" \
    --location="global" \
    --display-name="GitHub Actions Pool" || echo "Pool may already exist."

# Create Provider
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_NAME" \
    --location="global" \
    --workload-identity-pool="$POOL_NAME" \
    --display-name="GitHub Actions Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository == '${GITHUB_REPO}'" \
    --issuer-uri="https://token.actions.githubusercontent.com" || echo "Provider may already exist."

echo "6. Allowing GitHub Actions to impersonate the Service Account..."
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}"

echo "=== SETUP COMPLETE ==="
echo "Add the following values to your GitHub Repository variables/secrets:"
echo "--------------------------------------------------------"
echo "PROJECT_ID: $PROJECT_ID"
echo "REGION: $REGION"
echo "SERVICE_ACCOUNT: $SA_EMAIL"
echo "WORKLOAD_IDENTITY_PROVIDER: projects/$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}"
echo "--------------------------------------------------------"
