# Issue Tracker - CSV Storage Version

This version stores all data in CSV files instead of using Firebase.

## Features

- ✅ **No Firebase Required** - All data stored locally in CSV files
- ✅ **Simple Email Login** - Just enter your email (must be @cloudphysician.net)
- ✅ **CSV Storage** - All issues, users, comments, history stored in CSV files
- ✅ **Flask Backend** - RESTful API for all operations
- ✅ **Dashboard & Metrics** - Full analytics and reporting

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

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
│   └── {issue_id}.csv
└── history/                # Activity history
    └── {issue_id}.csv
```

## Authentication

- Simple email-based login
- Only `@cloudphysician.net` emails are allowed
- No password required (for internal use)
- Session-based authentication

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with email
- `POST /api/auth/logout` - Logout
- `GET /api/auth/current` - Get current user

### Issues
- `GET /api/issues` - Get paginated issues
- `GET /api/issues/<id>` - Get single issue
- `POST /api/issues` - Create issue
- `PUT /api/issues/<id>` - Update issue
- `DELETE /api/issues/<id>` - Delete issue

### Dashboard
- `GET /api/dashboard/stats` - Get statistics

### Settings
- `GET /api/settings/hospitals` - Get hospitals
- `POST /api/settings/hospitals` - Save hospitals (admin)
- `GET /api/settings/team` - Get team members
- `POST /api/settings/team` - Save team members (admin)

## CSV File Structure

### issues.csv
```csv
id,hospitalUnit,zone,priority,category,taskName,description,mainOwner,coOwners,dueDate,status,dateLogged,createdBy,lastModified,lastModifiedBy,stepsTaken,resolvedBy,reviewNotes,dateClosed
```

### users.csv
```csv
id,email,name,role,googleChatWebhookUrl
```

### hospitals.csv
```csv
name,zone
```

### team_members.csv
```csv
uid,name,email
```

## Backup

To backup your data, simply copy the `data/` directory:

```bash
cp -r data/ data_backup_$(date +%Y%m%d)/
```

## Migration from Firebase

If you have existing Firebase data, you can export it and import into CSV format. The CSV structure matches the Firestore document structure.

## Notes

- All timestamps are stored in ISO format
- Lists (like coOwners) are stored as comma-separated strings
- The `data/` directory is gitignored by default
- CSV files are created automatically when first data is added

