#!/usr/bin/env python3
"""
Add hardcoded users to the users.csv file
"""

import re
from pathlib import Path
import csv

# Data directory
DATA_DIR = Path('data')
USERS_CSV = DATA_DIR / 'users.csv'
USERS_HEADERS = ['id', 'email', 'name', 'role', 'googleChatWebhookUrl']

# User list from the user's input
user_list = """Stephen Shanthkumar <stephen.shanthkumar@cloudphysician.net>, Abhijeet Maji <abhijeet.maji@cloudphysician.net>, Ajinkya Gaikwad <ajinkya.gaikwad@cloudphysician.net>, Ankit Dubey <ankit.dubey@cloudphysician.net>, Arathi KR <arathi.kr@cloudphysician.net>, Asha B S <asha.bs@cloudphysician.net>, Ayesha Gopal <ayesha.gopal@cloudphysician.net>, Bibin George <bibin.george@cloudphysician.net>, Bineesh TS <bineesh.ts@cloudphysician.net>, Chandeshwar <chandeshwar.kumar@cloudphysician.net>, Dattakumar Patil <dattakumar.patil@cloudphysician.net>, Deepak Kumar <deepak.kumar@cloudphysician.net>, "Dr. Ajay Stephen" <ajay.stephen@cloudphysician.net>, "Dr. Akella Chendrasekhar" <akella.chendrasekhar@cloudphysician.net>, "Dr. Aneesa Goravankolla" <aneesa.goravankolla@cloudphysician.net>, "Dr. Deepak Sehrawat" <deepak.sehrawat@cloudphysician.net>, "Dr. Deepika Dash" <deepika.dash@cloudphysician.net>, "Dr. Jerry Jacob" <jerry.jacob@cloudphysician.net>, "Dr. Johncy Nathasha" <johncy.nathasha@cloudphysician.net>, "Dr. Kaustuv Mitra" <kaustuv.mitra@cloudphysician.net>, "Dr. Kavita Bhagwat" <kavita.bhagwat@cloudphysician.net>, "Dr. Lokesh MB" <lokesh.mb@cloudphysician.net>, "Dr. Malik Suhail Rasool" <malik.rasool@cloudphysician.net>, "Dr. Nikhil Sharma" <nikhil.sharma@cloudphysician.net>, "Dr. Nivedita Wadhwa" <nivedita.wadhwa@cloudphysician.net>, "Dr. Prudhvi Dasari" <prudhvi.dasari@cloudphysician.net>, "Dr. Rajesh Kumar Donda" <rajesh.kumar@cloudphysician.net>, "Dr. Reena Sinha" <reena.sinha@cloudphysician.net>, "Dr. Sanath Kumar" <sanath.kumar@cloudphysician.net>, "Dr. Sandeep Mangla" <sandeep.mangla@cloudphysician.net>, "Dr. Sandesh Kumar" <sandesh.kumar@cloudphysician.net>, "Dr. Sanu Anand" <sanu.anand@cloudphysician.net>, "Dr. Shashi Bhaskara Krishnamurthy" <shashi.krishnamurthy@cloudphysician.net>, "Dr. Swarna Shashi Bhaskara" <swarna.shashi@cloudphysician.net>, "Dr. Taranath Kamath" <taranath.kamath@cloudphysician.net>, Gaurav Pandey <gaurav.pandey@cloudphysician.net>, Jesline Rose <jesline.rose@cloudphysician.net>, Keerthika R <keerthika.r@cloudphysician.net>, Malathi R <malathi.r@cloudphysician.net>, Mamatha G N <mamatha.gn@cloudphysician.net>, Mani Balaji <mani.balaji@cloudphysician.net>, Manimalai S <manimalai.s@cloudphysician.net>, Megha Kantesh <megha.kantesh@cloudphysician.net>, Muhammed Saneer Salim <saneer.salim@cloudphysician.net>, Nagaveni G <nagaveni.g@cloudphysician.net>, Nataraj M <nataraj.m@cloudphysician.net>, Piyush Maurya <piyush.maurya@cloudphysician.net>, Prakash M <prakash.m@cloudphysician.net>, Reema Singh <reema.singh@cloudphysician.net>, Rohini R <rohini.r@cloudphysician.net>, Saddam Shaikh <saddam.shaikh@cloudphysician.net>, Sahitya Immidisetty <sahitya.immidisetty@cloudphysician.net>, "Sai Nadh D.B" <sai.nadh@cloudphysician.net>, Sai Teja Muske <saiteja.muske@cloudphysician.net>, Sophiya Gurusumuthu <sophiya.gurusumuthu@cloudphysician.net>, Srishti Chouhan <srishti.chouhan@cloudphysician.net>, Subhashini K <subhashini.k@cloudphysician.net>, Suni M <suni.m@cloudphysician.net>, Vidya K V <vidya.kv@cloudphysician.net>, Vijay Kuber <vijay.kuber@cloudphysician.net>"""

def read_csv(filepath, default_headers=None):
    """Read CSV file and return list of dictionaries"""
    if not filepath.exists():
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def write_csv(filepath, data, headers):
    """Write list of dictionaries to CSV file"""
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        if not data:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
        else:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)

def get_next_id(filepath, id_field='id'):
    """Get next ID for a CSV file"""
    data = read_csv(filepath)
    if not data:
        return 1
    ids = [int(row.get(id_field, 0)) for row in data if row.get(id_field) and row.get(id_field).isdigit()]
    return max(ids) + 1 if ids else 1

def parse_user_entry(entry):
    """Parse a user entry like 'Name <email>' or '"Dr. Name" <email>'"""
    entry = entry.strip()
    # Match pattern: name <email> or "name" <email>
    match = re.match(r'^"?([^<"]+)"?\s*<([^>]+)>$', entry)
    if match:
        name = match.group(1).strip()
        email = match.group(2).strip().lower()
        return name, email
    return None, None

def main():
    print("=" * 60)
    print("Adding Hardcoded Users")
    print("=" * 60)
    
    # Read existing users
    existing_users = read_csv(USERS_CSV, USERS_HEADERS)
    existing_emails = {user.get('email', '').lower() for user in existing_users}
    
    # Parse user list - split by email pattern since all emails end with @cloudphysician.net>
    # Pattern: find all entries like "Name <email@cloudphysician.net>"
    users_to_add = []
    
    # Use regex to find all user entries
    # Pattern matches: optional quoted name, then <email>
    pattern = r'"?([^<"]+)"?\s*<([^>]+@cloudphysician\.net)>'
    matches = re.findall(pattern, user_list)
    
    for name, email in matches:
        # Clean up name: remove leading/trailing commas, quotes, and spaces
        name = name.strip().lstrip(',').strip().strip('"').strip()
        email = email.strip().lower()
        if name and email:
            users_to_add.append((name, email))
    
    print(f"\nFound {len(users_to_add)} users to process")
    
    # Get next ID
    next_id = get_next_id(USERS_CSV)
    
    added_count = 0
    skipped_count = 0
    
    for name, email in users_to_add:
        if email.lower() in existing_emails:
            print(f"  Skipping {name} ({email}) - already exists")
            skipped_count += 1
            continue
        
        # Determine role - check if admin (from app.py ADMIN_USERS)
        ADMIN_USERS = ['sanath.kumar@cloudphysician.net']
        role = 'admin' if email.lower() in [admin.lower() for admin in ADMIN_USERS] else 'member'
        
        new_user = {
            'id': str(next_id),
            'email': email,
            'name': name,
            'role': role,
            'googleChatWebhookUrl': ''
        }
        
        existing_users.append(new_user)
        existing_emails.add(email.lower())
        next_id += 1
        added_count += 1
        print(f"  Added {name} ({email}) - {role}")
    
    # Write updated users
    write_csv(USERS_CSV, existing_users, USERS_HEADERS)
    
    print("\n" + "=" * 60)
    print(f"Summary:")
    print(f"  Added: {added_count} users")
    print(f"  Skipped: {skipped_count} users (already exist)")
    print(f"  Total users: {len(existing_users)}")
    print("=" * 60)

if __name__ == '__main__':
    main()

