#!/usr/bin/env python3
"""
Firebase to CSV Import Script
Exports all data from Firebase Firestore and Storage to CSV files.
"""

import os
import json
import csv
import re
from pathlib import Path
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore, storage
import requests

# Read Firebase config from config.js
def read_firebase_config():
    """Read Firebase configuration from config.js"""
    config_path = Path('config.js')
    if not config_path.exists():
        raise FileNotFoundError("config.js not found. Please ensure it exists with Firebase configuration.")
    
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Extract projectId from config.js
    project_id_match = re.search(r"projectId:\s*['\"]([^'\"]+)['\"]", content)
    if not project_id_match:
        raise ValueError("Could not find projectId in config.js")
    
    project_id = project_id_match.group(1)
    return project_id

# Initialize Firebase Admin SDK
def initialize_firebase(project_id):
    """Initialize Firebase Admin SDK"""
    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
    
    if not os.path.exists(cred_path):
        print("\n" + "="*60)
        print("ERROR: Firebase credentials file not found!")
        print("="*60)
        print(f"\nExpected file: {os.path.abspath(cred_path)}")
        print("\nTo get your Firebase credentials:")
        print("1. Go to Firebase Console: https://console.firebase.google.com/")
        print(f"2. Select your project: {project_id}")
        print("3. Click the gear icon (⚙️) > Project Settings")
        print("4. Go to the 'Service Accounts' tab")
        print("5. Click 'Generate new private key'")
        print("6. Save the downloaded JSON file as 'firebase-credentials.json'")
        print("7. Place it in the project root directory")
        print("\nAlternatively, set FIREBASE_CREDENTIALS_PATH environment variable")
        print("to point to your credentials file location.")
        print("="*60 + "\n")
        raise FileNotFoundError(f"Firebase credentials file not found: {cred_path}")
    
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            'storageBucket': f'{project_id}.appspot.com'
        })
        print("Firebase Admin SDK initialized successfully")
        return firestore.client(), storage.bucket()
    except Exception as e:
        print(f"\nError initializing Firebase: {e}")
        if "PermissionDenied" in str(e) or "403" in str(e):
            print("\n" + "="*60)
            print("PERMISSION ERROR: The service account doesn't have sufficient permissions.")
            print("="*60)
            print("\nTo fix this:")
            print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
            print(f"2. Select project: {project_id}")
            print("3. Go to IAM & Admin > IAM")
            print("4. Find your service account (from the credentials file)")
            print("5. Edit the service account and add these roles:")
            print("   - Cloud Datastore User (or Firestore User)")
            print("   - Storage Object Viewer (for downloading attachments)")
            print("   - Storage Object Admin (if you need full access)")
            print("="*60 + "\n")
        raise

# Data directory setup
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)
COMMENTS_DIR = DATA_DIR / 'comments'
ATTACHMENTS_DIR = DATA_DIR / 'attachments'
HISTORY_DIR = DATA_DIR / 'history'
ATTACHMENTS_FILES_DIR = DATA_DIR / 'attachments' / 'files'
ATTACHMENTS_FILES_DIR.mkdir(parents=True, exist_ok=True)

def convert_timestamp(timestamp):
    """Convert Firestore timestamp to ISO string"""
    if timestamp is None:
        return ''
    if hasattr(timestamp, 'timestamp'):
        return datetime.fromtimestamp(timestamp.timestamp()).isoformat()
    if isinstance(timestamp, datetime):
        return timestamp.isoformat()
    return str(timestamp)

def convert_array_to_string(arr):
    """Convert array to comma-separated string"""
    if not arr:
        return ''
    if isinstance(arr, list):
        return ','.join(str(item) for item in arr)
    return str(arr)

def write_csv(filepath, data, headers):
    """Write list of dictionaries to CSV file"""
    if not data:
        # Create empty CSV with headers
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
        return
    
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)

def export_issues(db):
    """Export issues collection to CSV"""
    print("Exporting issues...")
    try:
        issues_ref = db.collection('issues')
        issues = []
        
        for doc in issues_ref.stream():
            issue_data = doc.to_dict()
            issue_data['id'] = doc.id
            
            # Convert timestamps
            for field in ['dateLogged', 'lastModified', 'dateClosed', 'dueDate']:
                if field in issue_data and issue_data[field]:
                    issue_data[field] = convert_timestamp(issue_data[field])
            
            # Convert arrays
            if 'coOwners' in issue_data:
                issue_data['coOwners'] = convert_array_to_string(issue_data.get('coOwners', []))
            
            # Ensure all required fields exist
            issue_row = {
                'id': issue_data.get('id', ''),
                'hospitalUnit': issue_data.get('hospitalUnit', ''),
                'zone': issue_data.get('zone', ''),
                'priority': issue_data.get('priority', ''),
                'category': issue_data.get('category', ''),
                'taskName': issue_data.get('taskName', ''),
                'description': issue_data.get('description', ''),
                'mainOwner': issue_data.get('mainOwner', ''),
                'coOwners': issue_data.get('coOwners', ''),
                'dueDate': issue_data.get('dueDate', ''),
                'status': issue_data.get('status', 'Open'),
                'dateLogged': issue_data.get('dateLogged', ''),
                'createdBy': issue_data.get('createdBy', ''),
                'lastModified': issue_data.get('lastModified', ''),
                'lastModifiedBy': issue_data.get('lastModifiedBy', ''),
                'stepsTaken': issue_data.get('stepsTaken', ''),
                'resolvedBy': issue_data.get('resolvedBy', ''),
                'reviewNotes': issue_data.get('reviewNotes', ''),
                'dateClosed': issue_data.get('dateClosed', '')
            }
            
            issues.append(issue_row)
        
        headers = ['id', 'hospitalUnit', 'zone', 'priority', 'category', 'taskName', 'description', 
                   'mainOwner', 'coOwners', 'dueDate', 'status', 'dateLogged', 'createdBy', 
                   'lastModified', 'lastModifiedBy', 'stepsTaken', 'resolvedBy', 'reviewNotes', 
                   'dateClosed']
        
        write_csv(DATA_DIR / 'issues.csv', issues, headers)
        print(f"Exported {len(issues)} issues")
        return [issue['id'] for issue in issues]
    except Exception as e:
        print(f"Error exporting issues: {e}")
        if "PermissionDenied" in str(e) or "403" in str(e):
            print("\nMake sure your service account has 'Cloud Datastore User' or 'Firestore User' role.")
        raise

def export_subcollection(db, collection_path, issue_id, headers, output_dir):
    """Export a subcollection (comments, history, attachments) to CSV"""
    subcollection_ref = db.collection(collection_path)
    items = []
    
    for doc in subcollection_ref.stream():
        item_data = doc.to_dict()
        item_data['id'] = doc.id
        
        # Convert timestamps
        if 'timestamp' in item_data:
            item_data['timestamp'] = convert_timestamp(item_data['timestamp'])
        
        # Ensure all headers exist
        item_row = {}
        for header in headers:
            item_row[header] = item_data.get(header, '')
        
        items.append(item_row)
    
    if items or True:  # Always create file even if empty
        output_file = output_dir / f'{issue_id}.csv'
        write_csv(output_file, items, headers)
        return len(items)
    return 0

def export_issue_subcollections(db, issue_ids):
    """Export all subcollections for issues"""
    print("Exporting issue subcollections...")
    
    comments_count = 0
    history_count = 0
    attachments_count = 0
    
    for issue_id in issue_ids:
        # Comments
        comments_path = f'issues/{issue_id}/comments'
        count = export_subcollection(db, comments_path, issue_id, 
                                    ['id', 'text', 'authorName', 'timestamp'], 
                                    COMMENTS_DIR)
        comments_count += count
        
        # History
        history_path = f'issues/{issue_id}/history'
        count = export_subcollection(db, history_path, issue_id,
                                    ['id', 'user', 'action', 'timestamp'],
                                    HISTORY_DIR)
        history_count += count
        
        # Attachments
        attachments_path = f'issues/{issue_id}/attachments'
        count = export_subcollection(db, attachments_path, issue_id,
                                     ['id', 'fileName', 'downloadURL', 'uploadedBy', 'timestamp'],
                                     ATTACHMENTS_DIR)
        attachments_count += count
    
    print(f"Exported {comments_count} comments, {history_count} history entries, {attachments_count} attachments")

def download_attachments(db, bucket, issue_ids):
    """Download attachment files from Firebase Storage"""
    print("Downloading attachment files...")
    
    downloaded_count = 0
    failed_count = 0
    
    for issue_id in issue_ids:
        attachments_ref = db.collection(f'issues/{issue_id}/attachments')
        
        for doc in attachments_ref.stream():
            attachment_data = doc.to_dict()
            download_url = attachment_data.get('downloadURL', '')
            file_name = attachment_data.get('fileName', '')
            
            if not download_url or not file_name:
                continue
            
            try:
                # Create issue-specific directory
                issue_attach_dir = ATTACHMENTS_FILES_DIR / issue_id
                issue_attach_dir.mkdir(parents=True, exist_ok=True)
                
                # Download file
                response = requests.get(download_url, timeout=30)
                response.raise_for_status()
                
                # Save file
                file_path = issue_attach_dir / file_name
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                downloaded_count += 1
                print(f"  Downloaded: {issue_id}/{file_name}")
            except Exception as e:
                failed_count += 1
                print(f"  Failed to download {issue_id}/{file_name}: {e}")
    
    print(f"Downloaded {downloaded_count} files, {failed_count} failed")

def export_users(db):
    """Export users collection to CSV"""
    print("Exporting users...")
    users_ref = db.collection('users')
    users = []
    
    for doc in users_ref.stream():
        user_data = doc.to_dict()
        user_data['id'] = doc.id
        
        user_row = {
            'id': user_data.get('id', ''),
            'email': user_data.get('email', ''),
            'name': user_data.get('name', ''),
            'role': user_data.get('role', 'member'),
            'googleChatWebhookUrl': user_data.get('googleChatWebhookUrl', '')
        }
        
        users.append(user_row)
    
    headers = ['id', 'email', 'name', 'role', 'googleChatWebhookUrl']
    write_csv(DATA_DIR / 'users.csv', users, headers)
    print(f"Exported {len(users)} users")

def export_hospitals(db):
    """Export hospitals settings to CSV"""
    print("Exporting hospitals...")
    hospitals_doc = db.document('settings/hospitals')
    hospitals_data = hospitals_doc.get()
    
    hospitals = []
    if hospitals_data.exists():
        data = hospitals_data.to_dict()
        hospitals_list = data.get('list', [])
        
        for hospital in hospitals_list:
            hospitals.append({
                'name': hospital.get('name', ''),
                'zone': hospital.get('zone', '')
            })
    
    headers = ['name', 'zone']
    write_csv(DATA_DIR / 'hospitals.csv', hospitals, headers)
    print(f"Exported {len(hospitals)} hospitals")

def export_team_members(db):
    """Export team members settings to CSV"""
    print("Exporting team members...")
    team_doc = db.document('settings/teamMembers')
    team_data = team_doc.get()
    
    team_members = []
    if team_data.exists():
        data = team_data.to_dict()
        members_list = data.get('members', [])
        
        for member in members_list:
            team_members.append({
                'uid': member.get('uid', ''),
                'name': member.get('name', ''),
                'email': member.get('email', '')
            })
    
    headers = ['uid', 'name', 'email']
    write_csv(DATA_DIR / 'team_members.csv', team_members, headers)
    print(f"Exported {len(team_members)} team members")

def main():
    """Main import function"""
    print("=" * 60)
    print("Firebase to CSV Import Script")
    print("=" * 60)
    
    try:
        # Read config and initialize
        project_id = read_firebase_config()
        db, bucket = initialize_firebase(project_id)
        
        # Export all collections
        issue_ids = export_issues(db)
        export_issue_subcollections(db, issue_ids)
        download_attachments(db, bucket, issue_ids)
        export_users(db)
        export_hospitals(db)
        export_team_members(db)
        
        print("=" * 60)
        print("Import completed successfully!")
        print(f"Data exported to: {DATA_DIR.absolute()}")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error during import: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())

