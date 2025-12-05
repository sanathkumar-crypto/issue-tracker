# Issue Tracker

A hospital/healthcare issue tracking system built with Flask and CSV storage.

## Features

- ✅ **No Firebase Required** - All data stored locally in CSV files
- ✅ **Simple Email Login** - Just enter your email (must be @cloudphysician.net)
- ✅ **CSV Storage** - All issues, users, comments, history stored in CSV files
- ✅ **Flask Backend** - Server-side rendering with Jinja2 templates
- ✅ **Dashboard & Metrics** - Full analytics and reporting
- ✅ **File Attachments** - Upload and manage attachments locally
- ✅ **Admin Panel** - Manage users, hospitals, and team members

## Quick Start

### 1. Initialize CSV Files (First Time Only)

```bash
python3 initialize_csv.py
```

This creates empty CSV files with proper headers in the `data/` directory.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Application

```bash
python3 app.py
```

The application will be available at `http://localhost:5000`

### 4. First Login

- Enter your email (must be @cloudphysician.net domain)
- Your user account will be created automatically
- You'll be logged in and can start using the app

## Data Storage

All data is stored in the `data/` directory:

```
data/
├── issues.csv              # All issues/tasks
├── users.csv               # User accounts
├── hospitals.csv           # Hospital list
├── team_members.csv        # Team members
├── comments/               # Comments for each issue
│   └── {issue_id}.csv
├── attachments/            # Attachments metadata
│   ├── {issue_id}.csv
│   └── files/              # Actual attachment files
│       └── {issue_id}/
└── history/                # Activity history
    └── {issue_id}.csv
```

## Initial Setup

After logging in for the first time:

1. **Add Hospitals:**
   - Go to Admin → Hospital Management
   - Add hospitals with their zones

2. **Add Team Members:**
   - Go to Admin → Team Management
   - Add team members from existing users

3. **Set User Roles (Admin only):**
   - Go to Admin → User Role Management
   - Promote users to admin role if needed

## Authentication

- Simple email-based login
- Only `@cloudphysician.net` emails are allowed
- No password required (for internal use)
- Session-based authentication

## Admin Features

Admins can:
- Manage user roles
- Add/remove hospitals
- Add/remove team members
- Delete issues
- Close issues (with review notes)

## Port Configuration

By default, the app runs on port 5000. To use a different port:

```bash
python3 app.py 8080
```

## Migration from Firebase

If you have existing Firebase data, you can use the import script:

```bash
python3 import_from_firebase.py
```

**Note:** This requires Firebase credentials and access to the Firebase project. See `FIREBASE_IMPORT_SETUP.md` for details.

## Backup

To backup your data, simply copy the `data/` directory:

```bash
cp -r data/ data_backup_$(date +%Y%m%d)/
```

## Notes

- All timestamps are stored in ISO format
- Lists (like coOwners) are stored as comma-separated strings
- The `data/` directory is gitignored by default
- CSV files are created automatically when first data is added

## License

Private - All rights reserved
