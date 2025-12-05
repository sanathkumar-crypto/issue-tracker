# Fresh Start Guide

This guide will help you start the Issue Tracker application with a clean slate (no existing data).

## Quick Start

1. **Initialize CSV files:**
   ```bash
   python3 initialize_csv.py
   ```
   This creates empty CSV files with proper headers in the `data/` directory.

2. **Start the Flask application:**
   ```bash
   python3 app.py
   ```

3. **Access the application:**
   - Open your browser and go to: `http://localhost:5000`
   - You'll be redirected to the login page

4. **First Login:**
   - Enter your email (must be @cloudphysician.net domain)
   - Your user account will be created automatically
   - You'll be logged in and can start using the app

## Initial Setup

After logging in for the first time, you may want to:

1. **Add Hospitals:**
   - Go to Admin → Hospital Management
   - Add hospitals with their zones

2. **Add Team Members:**
   - Go to Admin → Team Management
   - Add team members from existing users

3. **Set User Roles (Admin only):**
   - Go to Admin → User Role Management
   - Promote users to admin role if needed

## Data Storage

All data is stored in CSV files in the `data/` directory:
- `data/issues.csv` - All issues/tasks
- `data/users.csv` - User accounts
- `data/hospitals.csv` - Hospital list
- `data/team_members.csv` - Team members
- `data/comments/` - Comments for each issue (one CSV per issue)
- `data/attachments/` - Attachment metadata and files
- `data/history/` - Activity history for each issue

## No Firebase Required

This application does NOT use Firebase. All data is stored locally in CSV files.

The `import_from_firebase.py` script is only needed if you want to migrate existing Firebase data. Since you're starting fresh, you don't need it.

## Troubleshooting

### Port already in use
If port 5000 is already in use, you can specify a different port:
```bash
python3 app.py 8080
```

### Permission errors
Make sure the `data/` directory is writable:
```bash
chmod -R 755 data/
```

