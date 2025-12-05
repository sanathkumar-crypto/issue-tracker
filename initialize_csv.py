#!/usr/bin/env python3
"""
Initialize CSV files with empty headers for fresh start
"""

from pathlib import Path
import csv

# Data directory
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)

COMMENTS_DIR = DATA_DIR / 'comments'
ATTACHMENTS_DIR = DATA_DIR / 'attachments'
ATTACHMENTS_FILES_DIR = DATA_DIR / 'attachments' / 'files'
HISTORY_DIR = DATA_DIR / 'history'

# Create directories
COMMENTS_DIR.mkdir(exist_ok=True)
ATTACHMENTS_DIR.mkdir(exist_ok=True)
ATTACHMENTS_FILES_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)

# Define headers for each CSV file - matching index.html structure
ISSUES_HEADERS = ['id', 'hospitalUnit', 'zone', 'priority', 'category', 'taskName', 'description', 
                  'mainOwner', 'coOwners', 'dueDate', 'status', 'dateLogged', 'dateClosed', 
                  'createdBy', 'lastModified', 'lastModifiedBy', 'resolvedBy', 'stepsTaken', 'reviewNotes']

USERS_HEADERS = ['id', 'email', 'name', 'role', 'googleChatWebhookUrl']
HOSPITALS_HEADERS = ['name', 'zone']
TEAM_HEADERS = ['uid', 'name', 'email']

def create_empty_csv(filepath, headers):
    """Create an empty CSV file with headers"""
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
    print(f"Created: {filepath}")

def main():
    print("=" * 60)
    print("Initializing CSV Files for Fresh Start")
    print("=" * 60)
    
    # Create main CSV files
    create_empty_csv(DATA_DIR / 'issues.csv', ISSUES_HEADERS)
    create_empty_csv(DATA_DIR / 'users.csv', USERS_HEADERS)
    create_empty_csv(DATA_DIR / 'hospitals.csv', HOSPITALS_HEADERS)
    create_empty_csv(DATA_DIR / 'team_members.csv', TEAM_HEADERS)
    
    print("\n" + "=" * 60)
    print("Initialization complete!")
    print("=" * 60)
    print("\nYou can now start the Flask app:")
    print("  python app.py")
    print("\nThe first user to log in will be created automatically.")
    print("=" * 60)

if __name__ == '__main__':
    main()

