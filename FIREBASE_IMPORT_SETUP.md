# Firebase Import Setup Guide

This guide will help you set up Firebase credentials to run the import script.

## Step 1: Get Firebase Service Account Credentials

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project: `partner-hospital-issue-tracker`
3. Click the gear icon (⚙️) next to "Project Overview"
4. Select **Project Settings**
5. Go to the **Service Accounts** tab
6. Click **Generate new private key**
7. A JSON file will be downloaded - this is your service account credentials
8. Save it as `firebase-credentials.json` in the project root directory

## Step 2: Set Up Permissions

The service account needs proper permissions to read Firestore and Storage:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project: `partner-hospital-issue-tracker`
3. Navigate to **IAM & Admin** > **IAM**
4. Find your service account (it will have an email like `firebase-adminsdk-xxxxx@partner-hospital-issue-tracker.iam.gserviceaccount.com`)
5. Click the **Edit** (pencil) icon
6. Click **Add Another Role** and add these roles:
   - **Cloud Datastore User** (or **Firestore User**)
   - **Storage Object Viewer** (to download attachments)
   - **Storage Object Admin** (if you need full access to attachments)
7. Click **Save**

## Step 3: Run the Import Script

Once you have the credentials file in place:

```bash
python import_from_firebase.py
```

## Alternative: Use Environment Variable

If you want to store the credentials file in a different location:

```bash
export FIREBASE_CREDENTIALS_PATH=/path/to/your/credentials.json
python import_from_firebase.py
```

## Troubleshooting

### Error: "403 Missing or insufficient permissions"

This means your service account doesn't have the right roles. Follow Step 2 above to add the required permissions.

### Error: "Firebase credentials file not found"

Make sure:
- The file is named exactly `firebase-credentials.json`
- It's in the project root directory (same folder as `import_from_firebase.py`)
- Or set the `FIREBASE_CREDENTIALS_PATH` environment variable

### Error: "Invalid credentials"

- Make sure you downloaded the correct service account key
- The JSON file should not be corrupted
- Try generating a new key from Firebase Console

## Security Note

⚠️ **Important**: The `firebase-credentials.json` file contains sensitive credentials. 

- **DO NOT** commit it to git (it should already be in `.gitignore`)
- Keep it secure and don't share it
- Consider using environment variables in production

