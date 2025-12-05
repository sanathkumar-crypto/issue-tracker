# Issue Tracker - Flask Application

This is the Flask backend version of the Issue Tracker application.

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Firebase Setup

1. Go to Firebase Console: https://console.firebase.google.com/
2. Select your project: `partner-hospital-issue-tracker`
3. Go to Project Settings > Service Accounts
4. Click "Generate New Private Key"
5. Save the JSON file as `firebase-credentials.json` in the project root

### 3. Environment Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Update `.env` with your configuration:
   ```
   FIREBASE_PROJECT_ID=partner-hospital-issue-tracker
   FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
   FLASK_ENV=development
   FLASK_DEBUG=True
   SECRET_KEY=your-secret-key-here
   ALLOWED_EMAIL_DOMAIN=cloudphysician.net
   ```

### 4. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Project Structure

```
issue-tracker/
├── app.py                 # Flask application
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not in git)
├── firebase-credentials.json  # Firebase service account (not in git)
├── templates/
│   └── index.html        # Main HTML template
├── static/
│   ├── js/
│   │   └── api.js        # API client JavaScript
│   └── css/
└── README_FLASK.md       # This file
```

## API Endpoints

### Authentication
- `POST /api/auth/verify` - Verify Firebase ID token
- `POST /api/auth/logout` - Logout user

### Issues
- `GET /api/issues` - Get paginated issues (query params: page, per_page, sort_by, sort_dir, status, priority, zone, search)
- `GET /api/issues/<id>` - Get single issue with subcollections
- `POST /api/issues` - Create new issue
- `PUT /api/issues/<id>` - Update issue
- `DELETE /api/issues/<id>` - Delete issue (admin only)

### Dashboard
- `GET /api/dashboard/stats` - Get dashboard statistics

### Settings
- `GET /api/settings/hospitals` - Get hospitals list
- `GET /api/settings/team` - Get team members list

## Features

- ✅ Flask REST API backend
- ✅ Firebase Admin SDK for server-side operations
- ✅ Email domain restriction (cloudphysician.net)
- ✅ Session-based authentication
- ✅ Pagination and filtering
- ✅ Dashboard statistics
- ✅ Role-based access control (admin/member)

## Development

The application uses Flask's development server. For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Notes

- The frontend still uses Firebase Auth for Google Sign-In, but all data operations go through the Flask API
- Firebase credentials file should never be committed to git
- Update SECRET_KEY in production
- The frontend JavaScript needs to be updated to use the API client instead of direct Firestore access

