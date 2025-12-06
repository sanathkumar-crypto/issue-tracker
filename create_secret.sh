#!/bin/bash

# Script to create ISSUE_TRACKER_SECRET_KEY secret in GCP Secret Manager
# This script helps set up the OAuth credentials for the issue-tracker service

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
PROJECT_ID=${PROJECT_ID:-"patientview-9uxml"}
REGION=${REGION:-"asia-south1"}
SERVICE_NAME=${SERVICE_NAME:-"issue-tracker"}

# Expected service URL (will be updated after first deployment)
SERVICE_URL="https://issue-tracker-971880579407.asia-south1.run.app"

print_status "Creating ISSUE_TRACKER_SECRET_KEY secret for project: $PROJECT_ID"
echo ""

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed. Please install it first."
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    print_error "Not authenticated with gcloud. Please run: gcloud auth login"
    exit 1
fi

# Set the project
gcloud config set project $PROJECT_ID

# Enable Secret Manager API if not already enabled
print_status "Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --quiet

# Check if secret already exists and has versions
SECRET_EXISTS=false
SECRET_HAS_VERSIONS=false

if gcloud secrets describe ISSUE_TRACKER_SECRET_KEY --quiet 2>/dev/null; then
    SECRET_EXISTS=true
    # Check if secret has any versions
    if gcloud secrets versions list ISSUE_TRACKER_SECRET_KEY --quiet 2>/dev/null | grep -q .; then
        SECRET_HAS_VERSIONS=true
    fi
fi

if [ "$SECRET_EXISTS" = true ]; then
    if [ "$SECRET_HAS_VERSIONS" = true ]; then
        print_warning "Secret ISSUE_TRACKER_SECRET_KEY already exists with data!"
        echo ""
        read -p "Do you want to add a new version? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Cancelled. Secret not updated."
            exit 0
        fi
    else
        print_warning "Secret ISSUE_TRACKER_SECRET_KEY exists but has no versions (empty)."
        print_status "Proceeding to add the first version..."
    fi
    UPDATE_EXISTING=true
else
    UPDATE_EXISTING=false
fi

# Prompt for OAuth credentials
echo ""
print_status "Please provide the following OAuth credentials:"
echo ""

read -p "Google Client ID: " CLIENT_ID
read -sp "Google Client Secret: " CLIENT_SECRET
echo ""
read -p "Secret Key (for Flask sessions): " SECRET_KEY
read -p "Allowed Email Domain [cloudphysician.net]: " ALLOWED_DOMAIN
ALLOWED_DOMAIN=${ALLOWED_DOMAIN:-cloudphysician.net}

# Get service URL if available
print_status "Attempting to get service URL..."
CURRENT_SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)" 2>/dev/null || echo "")
if [ -n "$CURRENT_SERVICE_URL" ]; then
    SERVICE_URL=$CURRENT_SERVICE_URL
    print_success "Found service URL: $SERVICE_URL"
else
    print_warning "Service not deployed yet. Using default URL: $SERVICE_URL"
    print_warning "You may need to update the secret after deployment with the actual URL."
fi

REDIRECT_URI="${SERVICE_URL}/login/callback"

# Create JSON secret
SECRET_JSON=$(cat <<EOF
{
  "SECRET_KEY": "$SECRET_KEY",
  "GOOGLE_CLIENT_ID": "$CLIENT_ID",
  "GOOGLE_CLIENT_SECRET": "$CLIENT_SECRET",
  "GOOGLE_REDIRECT_URI": "$REDIRECT_URI",
  "ALLOWED_EMAIL_DOMAIN": "$ALLOWED_DOMAIN"
}
EOF
)

# Save to temporary file
TEMP_FILE=$(mktemp)
echo "$SECRET_JSON" > "$TEMP_FILE"

# Create or update secret
if [ "$UPDATE_EXISTING" = true ]; then
    print_status "Updating existing secret..."
    echo "$SECRET_JSON" | gcloud secrets versions add ISSUE_TRACKER_SECRET_KEY --data-file=- --project=$PROJECT_ID
    print_success "Secret updated successfully!"
else
    print_status "Creating new secret..."
    echo "$SECRET_JSON" | gcloud secrets create ISSUE_TRACKER_SECRET_KEY --data-file=- --project=$PROJECT_ID
    print_success "Secret created successfully!"
fi

# Clean up
rm -f "$TEMP_FILE"

echo ""
print_success "Secret setup completed!"
echo ""
print_status "Secret details:"
echo "  Secret Name: ISSUE_TRACKER_SECRET_KEY"
echo "  Project: $PROJECT_ID"
echo "  Redirect URI: $REDIRECT_URI"
echo ""
print_status "Next steps:"
echo "  1. Make sure the redirect URI is added to your Google OAuth credentials"
echo "  2. Deploy the service using: ./deploy.sh"
echo ""

