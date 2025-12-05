# Migration Guide: Converting to Flask API

This document outlines the key changes needed to fully migrate the frontend to use the Flask API instead of direct Firestore access.

## Key Changes Made

### 1. Backend (Flask)
- ✅ Created `app.py` with Flask REST API
- ✅ Firebase Admin SDK for server-side operations
- ✅ API endpoints for all CRUD operations
- ✅ Authentication via Firebase ID token verification

### 2. Frontend Updates Needed

The frontend JavaScript needs to be updated to replace all Firestore calls with API calls. Here are the main functions that need updating:

#### Authentication
- ✅ Updated `handleGoogleSignIn()` to use `apiClient.verifyToken()`
- ✅ Updated `onAuthStateChanged()` to verify tokens with backend

#### Issues Management
- `fetchIssuesPage()` - Replace with `apiClient.getIssues(params)`
- `addIssue()` - Replace with `apiClient.createIssue(issueData)`
- `updateIssue()` - Replace with `apiClient.updateIssue(id, data)`
- `deleteIssue()` - Replace with `apiClient.deleteIssue(id)`
- `showViewModal()` - Replace with `apiClient.getIssue(id)`

#### Dashboard
- `updateDashboard()` - Replace with `apiClient.getDashboardStats()`

#### Settings
- `listenForHospitals()` - Replace with `apiClient.getHospitals()`
- `listenForTeamMembers()` - Replace with `apiClient.getTeamMembers()`

## Example Conversion

### Before (Direct Firestore):
```javascript
const querySnapshot = await getDocs(collection(db, 'issues'));
allIssues = querySnapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
```

### After (API Call):
```javascript
const response = await apiClient.getIssues({
    page: 1,
    per_page: 25,
    sort_by: 'dateLogged',
    sort_dir: 'desc'
});
allIssues = response.issues;
```

## Remaining Work

1. Update all Firestore queries to use API endpoints
2. Remove Firestore imports (keep only Auth and Storage)
3. Update real-time listeners (use polling or WebSockets)
4. Test all functionality with API backend

## Running the Application

1. Install dependencies: `pip install -r requirements.txt`
2. Set up Firebase credentials: `firebase-credentials.json`
3. Configure `.env` file
4. Run Flask: `python app.py`
5. Access at: `http://localhost:5000`

