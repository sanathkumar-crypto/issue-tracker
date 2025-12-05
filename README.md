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
- ✅ **Issue Tracking** - Create, assign, track, and resolve issues with comments and history

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or use the virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Initialize CSV Files (First Time Only)

```bash
python3 initialize_csv.py
```

This creates empty CSV files with proper headers in the `data/` directory.

### 3. Run the Application

```bash
python3 app.py
```

Or use a different port:

```bash
python3 app.py 8080
```

The application will be available at `http://localhost:5000`

### 4. First Login

- Enter your email (must be @cloudphysician.net domain)
- Your user account will be created automatically
- You'll be logged in and can start using the app

## Initial Setup

After logging in for the first time:

1. **Add Hospitals:**
   - Go to Admin → Hospital Management
   - Add hospitals with their zones
   - Use "Bulk Add Hospitals" to add multiple at once

2. **Add Users:**
   - Users are automatically created on first login
   - Use `add_users.py` script to bulk add users from a list
   - Go to Admin → User Role Management to set admin roles

3. **Add Team Members:**
   - Go to Admin → Team Member Management
   - Add team members from existing users

## Data Storage

All data is stored in the `data/` directory:

```
data/
├── issues.csv              # All issues/tasks
├── users.csv               # User accounts
├── hospitals.csv           # Hospital list
├── team_members.csv        # Team members
├── categories.json         # Category and subcategory mappings
├── comments/               # Comments for each issue
│   └── {issue_id}.csv
├── attachments/            # Attachments metadata
│   ├── {issue_id}.csv
│   └── files/              # Actual attachment files
│       └── {issue_id}/
└── history/                # Activity history
    └── {issue_id}.csv
```

## Authentication

- Simple email-based login
- Only `@cloudphysician.net` emails are allowed
- No password required (for internal use)
- Session-based authentication
- Admin users are defined in `app.py` (ADMIN_USERS list)

## Admin Features

Admins can:
- Manage user roles
- Add/remove hospitals (single or bulk)
- Add/remove team members
- Manage categories and subcategories
- Delete issues
- Close issues (with review notes)

## Deployment

### Production Deployment with Gunicorn

For production, use a WSGI server like Gunicorn:

1. **Install Gunicorn:**
   ```bash
   pip install gunicorn
   ```

2. **Run with Gunicorn:**
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

   Options:
   - `-w 4`: Number of worker processes (adjust based on your server)
   - `-b 0.0.0.0:5000`: Bind to all interfaces on port 5000
   - `app:app`: Flask application instance

3. **With environment variables:**
   ```bash
   export SECRET_KEY=your-secret-key-here
   export ALLOWED_EMAIL_DOMAIN=cloudphysician.net
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

### Deployment on Railway

1. Create a `Procfile`:
   ```
   web: gunicorn -w 4 -b 0.0.0.0:$PORT app:app
   ```

2. Set environment variables in Railway dashboard:
   - `SECRET_KEY`: A secure random string
   - `ALLOWED_EMAIL_DOMAIN`: cloudphysician.net
   - `PORT`: Railway will set this automatically

3. Deploy from GitHub

### Deployment on Render

1. Create a `render.yaml`:
   ```yaml
   services:
     - type: web
       name: issue-tracker
       env: python
       buildCommand: pip install -r requirements.txt
       startCommand: gunicorn -w 4 -b 0.0.0.0:$PORT app:app
       envVars:
         - key: SECRET_KEY
           generateValue: true
         - key: ALLOWED_EMAIL_DOMAIN
           value: cloudphysician.net
   ```

2. Connect your GitHub repository

### Deployment on Heroku

1. Create a `Procfile`:
   ```
   web: gunicorn -w 4 -b 0.0.0.0:$PORT app:app
   ```

2. Create `runtime.txt`:
   ```
   python-3.12.0
   ```

3. Deploy:
   ```bash
   heroku create your-app-name
   heroku config:set SECRET_KEY=your-secret-key
   heroku config:set ALLOWED_EMAIL_DOMAIN=cloudphysician.net
   git push heroku main
   ```

### Deployment on DigitalOcean App Platform

1. Create `app.yaml`:
   ```yaml
   name: issue-tracker
   services:
     - name: web
       source_dir: /
       github:
         repo: your-username/issue-tracker
         branch: main
       run_command: gunicorn -w 4 -b 0.0.0.0:8080 app:app
       environment_slug: python
       instance_count: 1
       instance_size_slug: basic-xxs
       envs:
         - key: SECRET_KEY
           scope: RUN_TIME
           value: your-secret-key
         - key: ALLOWED_EMAIL_DOMAIN
           scope: RUN_TIME
           value: cloudphysician.net
   ```

### Environment Variables

Set these environment variables for production:

- `SECRET_KEY`: A secure random string for session encryption (required)
- `ALLOWED_EMAIL_DOMAIN`: Email domain allowed for login (default: cloudphysician.net)
- `PORT`: Port to run on (some platforms set this automatically)

### Production Checklist

- [ ] Set a strong `SECRET_KEY` environment variable
- [ ] Use a production WSGI server (Gunicorn, uWSGI, etc.)
- [ ] Set up proper file permissions for `data/` directory
- [ ] Configure reverse proxy (nginx, Apache) if needed
- [ ] Set up SSL/TLS certificates
- [ ] Configure backup strategy for `data/` directory
- [ ] Set up monitoring and logging
- [ ] Review and update admin users list in `app.py`

## Backup

To backup your data, simply copy the `data/` directory:

```bash
cp -r data/ data_backup_$(date +%Y%m%d)/
```

For automated backups, consider using cron:

```bash
# Add to crontab (crontab -e)
0 2 * * * cp -r /path/to/issue-tracker/data /path/to/backups/data_$(date +\%Y\%m\%d)
```

## Migration from Firebase

If you have existing Firebase data, you can use the import script:

```bash
python3 import_from_firebase.py
```

**Note:** This requires Firebase credentials and access to the Firebase project. See the script for setup instructions.

## Utility Scripts

- `initialize_csv.py` - Initialize empty CSV files with headers
- `add_users.py` - Bulk add users from a list
- `import_from_firebase.py` - Import data from Firebase

## Troubleshooting

### Port already in use
If port 5000 is already in use:
```bash
python3 app.py 8080
```

### Permission errors
Make sure the `data/` directory is writable:
```bash
chmod -R 755 data/
```

### "No module named 'flask'"
Make sure dependencies are installed:
```bash
pip install -r requirements.txt
```

Or activate virtual environment:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

## Notes

- All timestamps are stored in ISO format
- Lists (like coOwners) are stored as comma-separated strings
- The `data/` directory is gitignored by default
- CSV files are created automatically when first data is added
- Admin users are hardcoded in `app.py` (ADMIN_USERS list)

## License

Private - All rights reserved
