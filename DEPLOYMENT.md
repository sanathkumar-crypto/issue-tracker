# GCP Deployment Guide for Issue Tracker

This guide explains how to deploy the Issue Tracker application as a microservice on Google Cloud Platform (GCP) with Google OAuth authentication.

## Overview

The application has been configured to deploy on Google Cloud Run with:
- **Google OAuth 2.0** authentication
- **Secret Manager** for secure credential storage
- **Cloud Build** for automated builds
- **Container Registry** for Docker images

## Prerequisites

1. **Google Cloud SDK** installed and authenticated
   ```bash
   gcloud auth login
   gcloud config set project patientview-9uxml
   ```

2. **Google OAuth Credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - Create OAuth 2.0 Client ID credentials (Web application)
   - Note down the Client ID and Client Secret

## Step 1: Set Up Secrets

### Option A: Using the Setup Script (Recommended)

```bash
./create_secret.sh
```

The script will prompt you for:
- Google Client ID
- Google Client Secret
- Secret Key (for Flask sessions)
- Allowed Email Domain (default: cloudphysician.net)

### Option B: Manual Setup

1. Create a JSON file `secret.json`:
```json
{
  "SECRET_KEY": "your-secret-key-here",
  "GOOGLE_CLIENT_ID": "your-client-id.apps.googleusercontent.com",
  "GOOGLE_CLIENT_SECRET": "GOCSPX-your-client-secret",
  "GOOGLE_REDIRECT_URI": "https://issue-tracker-971880579407.asia-south1.run.app/login/callback",
  "ALLOWED_EMAIL_DOMAIN": "cloudphysician.net"
}
```

2. Upload to Secret Manager:
```bash
gcloud secrets create ISSUE_TRACKER_SECRET_KEY --data-file=secret.json --project=patientview-9uxml
```

**Important**: The redirect URI will need to be updated after the first deployment with the actual service URL.

## Step 2: Configure OAuth Redirect URI

After creating the secret, you need to add the redirect URI to your Google OAuth credentials:

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Click on your OAuth 2.0 Client ID
3. Under "Authorized redirect URIs", add:
   - `https://issue-tracker-971880579407.asia-south1.run.app/login/callback`
   - (You'll update this with the actual URL after deployment)

## Step 3: Deploy to Cloud Run

```bash
./deploy.sh
```

The deployment script will:
1. Check gcloud authentication
2. Verify secrets exist
3. Enable required APIs
4. Build the Docker container
5. Push to Container Registry
6. Deploy to Cloud Run
7. Display the service URL

## Step 4: Update OAuth Redirect URI

After deployment, get your service URL:

```bash
gcloud run services describe issue-tracker --region=asia-south1 --format="value(status.url)"
```

Then:
1. Update the redirect URI in Google Cloud Console with the actual URL
2. Update the secret in Secret Manager with the new redirect URI:
   ```bash
   # Edit secret.json with new redirect URI
   gcloud secrets versions add ISSUE_TRACKER_SECRET_KEY --data-file=secret.json --project=patientview-9uxml
   ```

## Configuration Details

### Project Settings
- **Project ID**: `patientview-9uxml`
- **Service Name**: `issue-tracker`
- **Region**: `asia-south1`
- **Memory**: 1Gi
- **CPU**: 1
- **Max Instances**: 10
- **Timeout**: 900 seconds

### Environment Variables

All configuration is loaded from Secret Manager:
- `ISSUE_TRACKER_SECRET_KEY` - JSON secret containing:
  - `SECRET_KEY` - Flask session secret
  - `GOOGLE_CLIENT_ID` - OAuth client ID
  - `GOOGLE_CLIENT_SECRET` - OAuth client secret
  - `GOOGLE_REDIRECT_URI` - OAuth callback URL
  - `ALLOWED_EMAIL_DOMAIN` - Allowed email domain

## Files Created/Modified

### New Files
- `Dockerfile` - Container definition
- `cloudbuild.yaml` - Cloud Build configuration
- `deploy.sh` - Deployment script
- `create_secret.sh` - Secret setup script
- `config.py` - Configuration management with OAuth support

### Modified Files
- `app.py` - Integrated Google OAuth authentication
- `requirements.txt` - Added OAuth dependencies
- `templates/login.html` - Updated for OAuth login
- `README.md` - Added GCP deployment section
- `.gitignore` - Added secret files and session directory

## Local Development

For local development without OAuth:

1. The app will automatically fall back to email-based login if OAuth credentials are not configured
2. You can create a local `issue_tracker_secret_key.json` file (gitignored) with the same structure as the secret
3. Or set individual environment variables:
   ```bash
   export SECRET_KEY=your-secret-key
   export GOOGLE_CLIENT_ID=your-client-id
   export GOOGLE_CLIENT_SECRET=your-client-secret
   export GOOGLE_REDIRECT_URI=http://localhost:5001/login/callback
   export ALLOWED_EMAIL_DOMAIN=cloudphysician.net
   ```

## Troubleshooting

### OAuth Not Working
- Verify the redirect URI matches exactly in Google Cloud Console
- Check that the secret is correctly formatted JSON
- Ensure the service URL is HTTPS (required for OAuth)

### Deployment Fails
- Check that all required APIs are enabled
- Verify you have permissions to create Cloud Run services
- Check Cloud Build logs: `gcloud builds list`

### Service Not Responding
- Check service logs: `gcloud run services logs read issue-tracker --region=asia-south1`
- Verify the service is running: `gcloud run services describe issue-tracker --region=asia-south1`

## Manual Deployment

If you prefer to deploy manually:

```bash
# Build and push image
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION=asia-south1 \
  --project patientview-9uxml
```

## Updating the Service

To update the service after making changes:

```bash
./deploy.sh
```

The script will rebuild and redeploy automatically.

## Security Notes

- Secrets are stored in Secret Manager, not in code or environment variables
- OAuth credentials are never exposed in logs
- Session cookies are secure (HTTPS only) in production
- Only `@cloudphysician.net` email addresses are allowed

## Support

For issues or questions:
1. Check the Cloud Run logs
2. Verify secrets are correctly configured
3. Ensure OAuth redirect URI matches exactly
4. Check that all required APIs are enabled

