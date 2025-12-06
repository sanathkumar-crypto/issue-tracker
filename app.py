from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory
from flask_cors import CORS
from functools import wraps
import os
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from werkzeug.utils import secure_filename
from urllib.parse import unquote

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)

# Data directory
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)

ISSUES_CSV = DATA_DIR / 'issues.csv'
USERS_CSV = DATA_DIR / 'users.csv'
HOSPITALS_CSV = DATA_DIR / 'hospitals.csv'
TEAM_CSV = DATA_DIR / 'team_members.csv'
CATEGORIES_JSON = DATA_DIR / 'categories.json'
COMMENTS_DIR = DATA_DIR / 'comments'
ATTACHMENTS_DIR = DATA_DIR / 'attachments'
ATTACHMENTS_FILES_DIR = DATA_DIR / 'attachments' / 'files'
HISTORY_DIR = DATA_DIR / 'history'

# Create directories
COMMENTS_DIR.mkdir(exist_ok=True)
ATTACHMENTS_DIR.mkdir(exist_ok=True)
ATTACHMENTS_FILES_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)

ALLOWED_DOMAIN = os.getenv('ALLOWED_EMAIL_DOMAIN', 'cloudphysician.net')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}

# Default Categories and Subcategories (used as fallback)
DEFAULT_CATEGORY_MAPPINGS = {
    'Clinical [ICU]': ['Workflow not being followed', 'Staffing Shortage', 'Training Gaps', 'Partner Escalation', 
                       'Less/No patients', 'Consultants not aligned', 'Bedside Doctors not cooperative', 
                       'Bedside Nurses not cooperative', 'Selective Admissions', 'Poor RADAR adoption', 
                       'Poor document transfer', 'Delayed admissions', 'Other'],
    'Clinical [PICU/NICU]': ['Workflow not being followed', 'Staffing Shortage', 'Training Gaps', 'Partner Escalation', 
                             'Less/No patients', 'Consultants not aligned', 'Bedside Doctors not cooperative', 
                             'Bedside Nurses not cooperative', 'Selective Admissions', 'Poor RADAR adoption', 
                             'Poor document transfer', 'Delayed admissions', 'Other'],
    'RADAR Related': ['RADAR not working', 'Camera on app not working', 'Notes goes missing', 'RADAR not opening', 'Other'],
    'Tech/Product': ['Technical issue', 'Other'],
    'Commercial': ['Owner not happy', 'Billing mismatch', 'Bill not paid', 'Other'],
    'Quality': ['Infection Control', 'Quality Issues [General]', 'NABH related', 'Educational Sessions', 'Other'],
    'IT Related': ['Network issues', 'Camera not working', 'Wrong presets', 'Other'],
    'Equipment/Infrastructure': ['Faulty speaker at bedside', 'Medical equipment related', 'Oxygen Supply related', 'Other'],
    'FCC Request': ['Nursing FCC', 'Doctor FCC', 'Other'],
    'Upsell/Change in service': ['Smart ER required', 'Smart Dialysis required', 'Nursing Excellence', 
                                  'IOM + Services', 'Smart ICU/NICU/PICU', 'IOM only', 'Other'],
    'Other': []
}

# Category storage functions
def load_categories():
    """Load categories from JSON file, fallback to defaults if file doesn't exist"""
    if CATEGORIES_JSON.exists():
        try:
            with open(CATEGORIES_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return DEFAULT_CATEGORY_MAPPINGS.copy()
    else:
        # Initialize with defaults
        save_categories(DEFAULT_CATEGORY_MAPPINGS)
        return DEFAULT_CATEGORY_MAPPINGS.copy()

def save_categories(categories):
    """Save categories to JSON file"""
    with open(CATEGORIES_JSON, 'w', encoding='utf-8') as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)

# Load categories on startup
CATEGORY_MAPPINGS = load_categories()

# Hardcoded Admin Users (email addresses)
# Add admin email addresses here - only these users will have admin access
ADMIN_USERS = [
    'sanath.kumar@cloudphysician.net',
    # Add more admin emails as needed
]

def is_admin(email):
    """Check if user is admin - only users in ADMIN_USERS list are admins"""
    return email.lower() in [admin.lower() for admin in ADMIN_USERS]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions
def format_date(date_str):
    """Format ISO date string to readable format"""
    if not date_str:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%d %b %Y')
    except:
        return date_str

def format_datetime(date_str):
    """Format ISO datetime string to readable format"""
    if not date_str:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%b %d, %Y %I:%M %p')
    except:
        return date_str

def time_ago(date_str):
    """Get time ago string"""
    if not date_str:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return f'{diff.days} day{"s" if diff.days > 1 else ""} ago'
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f'{hours} hour{"s" if hours > 1 else ""} ago'
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
        else:
            return 'Just now'
    except:
        return date_str

def is_overdue(due_date_str, status):
    """Check if issue is overdue"""
    if not due_date_str or status in ['Resolved', 'Closed']:
        return False
    try:
        due_date = datetime.fromisoformat(due_date_str)
        return due_date < datetime.now()
    except:
        return False

# CSV Helper Functions
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
            # Filter out fields not in headers to avoid ValueError
            filtered_data = [{k: v for k, v in row.items() if k in headers} for row in data]
            writer.writerows(filtered_data)

def get_next_id(filepath, id_field='id'):
    """Get next ID for a CSV file"""
    data = read_csv(filepath)
    if not data:
        return 1
    ids = [int(row.get(id_field, 0)) for row in data if row.get(id_field) and row.get(id_field).isdigit()]
    return max(ids) + 1 if ids else 1

# Issues Management
ISSUES_HEADERS = ['id', 'hospitalUnit', 'zone', 'priority', 'category', 'taskName', 'description', 
                  'mainOwner', 'coOwners', 'dueDate', 'status', 'dateLogged', 'dateClosed', 
                  'createdBy', 'lastModified', 'lastModifiedBy', 'resolvedBy', 'stepsTaken', 'reviewNotes']

def get_all_issues():
    """Get all issues from CSV"""
    return read_csv(ISSUES_CSV, ISSUES_HEADERS)

def save_issue(issue):
    """Save or update an issue"""
    issues = get_all_issues()
    
    if 'id' in issue and issue['id']:
        # Update existing
        issue_id = issue['id']
        issues = [i for i in issues if i.get('id') != str(issue_id)]
        issues.append(issue)
    else:
        # Create new
        issue['id'] = str(get_next_id(ISSUES_CSV))
        # dateLogged is already set in create_issue, no need for time_started
        issues.append(issue)
    
    write_csv(ISSUES_CSV, issues, ISSUES_HEADERS)
    return issue['id']

def delete_issue_data(issue_id):
    """Delete an issue and its related data"""
    issues = get_all_issues()
    issues = [i for i in issues if i.get('id') != str(issue_id)]
    write_csv(ISSUES_CSV, issues, ISSUES_HEADERS)
    
    # Delete related files
    comments_file = COMMENTS_DIR / f'{issue_id}.csv'
    history_file = HISTORY_DIR / f'{issue_id}.csv'
    attachments_file = ATTACHMENTS_DIR / f'{issue_id}.csv'
    
    if comments_file.exists():
        comments_file.unlink()
    if history_file.exists():
        history_file.unlink()
    if attachments_file.exists():
        attachments_file.unlink()
    
    # Delete attachment files
    attach_dir = ATTACHMENTS_FILES_DIR / issue_id
    if attach_dir.exists():
        import shutil
        shutil.rmtree(attach_dir)

# Comments Management
def get_comments(issue_id):
    """Get comments for an issue"""
    comments_file = COMMENTS_DIR / f'{issue_id}.csv'
    return read_csv(comments_file, ['id', 'text', 'authorName', 'authorEmail', 'timestamp'])

def save_comment(issue_id, comment_data):
    """Add a comment to an issue"""
    comments_file = COMMENTS_DIR / f'{issue_id}.csv'
    comments = get_comments(issue_id)
    
    comment_data['id'] = str(get_next_id(comments_file))
    comment_data['timestamp'] = datetime.now().isoformat()
    comments.append(comment_data)
    
    write_csv(comments_file, comments, ['id', 'text', 'authorName', 'authorEmail', 'timestamp'])
    return comment_data['id']

# History Management
def get_history(issue_id):
    """Get history for an issue"""
    history_file = HISTORY_DIR / f'{issue_id}.csv'
    return read_csv(history_file, ['id', 'user', 'action', 'timestamp'])

def add_history(issue_id, history_data):
    """Add history entry to an issue"""
    history_file = HISTORY_DIR / f'{issue_id}.csv'
    history = get_history(issue_id)
    
    history_data['id'] = str(get_next_id(history_file))
    history_data['timestamp'] = datetime.now().isoformat()
    history.append(history_data)
    
    write_csv(history_file, history, ['id', 'user', 'action', 'timestamp'])
    return history_data['id']

# Attachments Management
def get_attachments(issue_id):
    """Get attachments for an issue"""
    attachments_file = ATTACHMENTS_DIR / f'{issue_id}.csv'
    return read_csv(attachments_file, ['id', 'fileName', 'downloadURL', 'uploadedBy', 'timestamp'])

def add_attachment(issue_id, attachment_data):
    """Add attachment to an issue"""
    attachments_file = ATTACHMENTS_DIR / f'{issue_id}.csv'
    attachments = get_attachments(issue_id)
    
    attachment_data['id'] = str(get_next_id(attachments_file))
    attachment_data['timestamp'] = datetime.now().isoformat()
    attachments.append(attachment_data)
    
    write_csv(attachments_file, attachments, ['id', 'fileName', 'downloadURL', 'uploadedBy', 'timestamp'])
    return attachment_data['id']

# Users Management
USERS_HEADERS = ['id', 'email', 'name', 'role', 'googleChatWebhookUrl']

def get_all_users():
    """Get all users"""
    return read_csv(USERS_CSV, USERS_HEADERS)

def get_user_by_email(email):
    """Get user by email"""
    users = get_all_users()
    for user in users:
        if user.get('email') == email:
            return user
    return None

def get_user_by_id(user_id):
    """Get user by ID"""
    users = get_all_users()
    for user in users:
        if user.get('id') == str(user_id):
            return user
    return None

def create_or_update_user(user_data):
    """Create or update user"""
    users = get_all_users()
    existing_user = get_user_by_email(user_data['email'])
    
    if existing_user:
        # Update existing
        users = [u for u in users if u.get('email') != user_data['email']]
        user_data['id'] = existing_user.get('id')
        users.append(user_data)
    else:
        # Create new
        user_data['id'] = str(get_next_id(USERS_CSV))
        user_data['role'] = user_data.get('role', 'member')
        users.append(user_data)
    
    write_csv(USERS_CSV, users, USERS_HEADERS)
    return user_data

# Settings Management
# Default hospitals (hardcoded from CSV file - 328 hospitals)
DEFAULT_HOSPITALS = [
    {'name': 'Aarogya Hapur', 'zone': ''},
    {'name': 'Aastha', 'zone': ''},
    {'name': 'Abirami Kidney Care - Erode', 'zone': ''},
    {'name': 'Abishek Hospital - Arakkonam', 'zone': ''},
    {'name': 'Adarsh Hospital - Ramdurg', 'zone': ''},
    {'name': 'Adarsh Hospital - Rosera', 'zone': ''},
    {'name': 'Adarsha Hospital - Karimnagar', 'zone': ''},
    {'name': 'Aditya Warangal', 'zone': ''},
    {'name': 'Akash Super Speciality', 'zone': ''},
    {'name': 'Akshar Hospital - Ahmedabad', 'zone': ''},
    {'name': 'Anand Hospital - Chennai', 'zone': ''},
    {'name': 'Anil Neuro and Trauma - Vijayawada', 'zone': ''},
    {'name': 'Antara Care Homes - Bengaluru', 'zone': ''},
    {'name': 'Anurag Healthcare - Vijayawada', 'zone': ''},
    {'name': 'Apex', 'zone': ''},
    {'name': 'Apex Hospital - Katni', 'zone': ''},
    {'name': 'Arora Hospital - Rudrapur', 'zone': ''},
    {'name': 'Aryavrat Hospital - Haridwar', 'zone': ''},
    {'name': 'Ashirvad', 'zone': ''},
    {'name': 'Ashirwad Hospital - Navi Mumbai', 'zone': ''},
    {'name': 'Ashish JRC', 'zone': ''},
    {'name': 'Ashish Jabalpur', 'zone': ''},
    {'name': 'Ashoka Hospital - Singhia', 'zone': ''},
    {'name': 'Ashoka Life Care', 'zone': ''},
    {'name': 'Ashwini Hospital - Yellareddypet', 'zone': ''},
    {'name': 'Asian Noble - Ahilya Nagar', 'zone': ''},
    {'name': 'Aswani Multispeciality - Manvi', 'zone': ''},
    {'name': 'Atlantis Gopalganj', 'zone': ''},
    {'name': 'Aveksha', 'zone': ''},
    {'name': 'Ayushman Bhav Hospital - Panipat', 'zone': ''},
    {'name': 'BGR Hospital - Dharmapuri', 'zone': ''},
    {'name': 'BHIO', 'zone': ''},
    {'name': 'BMS', 'zone': ''},
    {'name': 'Baa Ganga Hospital - Supaul', 'zone': ''},
    {'name': 'Balaji Robotic Rehab Hospital - Salem', 'zone': ''},
    {'name': 'Berlin General Hospital - Ranchi', 'zone': ''},
    {'name': 'Bhate Hospital - Belagavi', 'zone': ''},
    {'name': 'Bhoomi Hospital - Hyderabad', 'zone': ''},
    {'name': 'Bramhapuri Hospital and Research Institute', 'zone': ''},
    {'name': 'Bugga Reddy - Shadnagar', 'zone': ''},
    {'name': 'CCH Davangere', 'zone': ''},
    {'name': 'Cachar', 'zone': ''},
    {'name': 'Care centre', 'zone': 'Care centre'},
    {'name': 'CentraCare - Belagavi', 'zone': ''},
    {'name': 'Charak Hospital - Indore', 'zone': ''},
    {'name': 'Charak Lucknow', 'zone': ''},
    {'name': 'Chendure Hospital - Samalapuram', 'zone': ''},
    {'name': 'Chirayu Children\'s Hospital - Baramati', 'zone': ''},
    {'name': 'Chitradurga Multispeciality', 'zone': ''},
    {'name': 'City Hospital - Bijnor', 'zone': ''},
    {'name': 'City Hospital Buldhana', 'zone': ''},
    {'name': 'ClearMedi Paridhi Hospital - Gwalior', 'zone': ''},
    {'name': 'Credence Care - Navi Mumbai', 'zone': ''},
    {'name': 'Currex Hospital - Bengaluru', 'zone': ''},
    {'name': 'Cutis & Kids Hospital - Bareilly', 'zone': ''},
    {'name': 'Cytecare', 'zone': ''},
    {'name': 'D P Bora - Lucknow', 'zone': ''},
    {'name': 'DORD Hospital - Daudnagar', 'zone': ''},
    {'name': 'Darbhanga Children Hospital', 'zone': ''},
    {'name': 'Daulat Memorial Clinic - Washim', 'zone': ''},
    {'name': 'David Multispeciality - Vaniyambadi', 'zone': ''},
    {'name': 'Devibai Hospital - Nirmal', 'zone': ''},
    {'name': 'Dhakne Hospital - Pune', 'zone': ''},
    {'name': 'Dharani - Mahabubabad', 'zone': ''},
    {'name': 'Dr. Amit Agarwal Childcare Hospital', 'zone': ''},
    {'name': 'Dr. Dasarathan Memorial Hospital', 'zone': ''},
    {'name': 'Dr. Mendadkar\'s Children Hospital', 'zone': ''},
    {'name': 'Dr. Pankaj Sharma Hospital', 'zone': ''},
    {'name': 'Dr. Patil Hospital - Madha', 'zone': ''},
    {'name': 'Dr. Preeti Hospital - Prayagraj', 'zone': ''},
    {'name': 'Dr. Prem Hospital', 'zone': ''},
    {'name': 'Dr. R. K. Thakur Hospital', 'zone': ''},
    {'name': 'Dr. Ravi Khanna\'s Vatsalya', 'zone': ''},
    {'name': 'Durga Hospital - Jaunpur', 'zone': ''},
    {'name': 'East Delhi Advance NICU', 'zone': ''},
    {'name': 'FIMS Hospital - Coimbatore', 'zone': ''},
    {'name': 'Faridabad Medical Center', 'zone': ''},
    {'name': 'Flamingo Chennai', 'zone': ''},
    {'name': 'Fortune Hospital - Kanpur', 'zone': ''},
    {'name': 'G Guru Gopiram', 'zone': ''},
    {'name': 'GBN Hospital - Bhainsa', 'zone': ''},
    {'name': 'GSL Swatantra Hospital', 'zone': ''},
    {'name': 'Gandhi Nursing Home - Rajnandgaon', 'zone': ''},
    {'name': 'Giriraj Hospital - Baramati', 'zone': ''},
    {'name': 'Goyal Hospital - Faridabad', 'zone': ''},
    {'name': 'HCG Bhavnagar', 'zone': ''},
    {'name': 'HCG Cuttack', 'zone': ''},
    {'name': 'HCG EKO', 'zone': ''},
    {'name': 'HCG Kalaburagi', 'zone': ''},
    {'name': 'HCG Mumbai', 'zone': ''},
    {'name': 'HCG Nagpur', 'zone': ''},
    {'name': 'HCG Ranchi', 'zone': ''},
    {'name': 'HCG Vijayawada', 'zone': ''},
    {'name': 'HMC Hospital - Gummidipoondi', 'zone': ''},
    {'name': 'HMH Hospital - Najibabad', 'zone': ''},
    {'name': 'Hada Multispeciality Hospital - Dahod', 'zone': ''},
    {'name': 'Hare Krishna - Begowal', 'zone': ''},
    {'name': 'Heritage Hospital - Gorakhpur', 'zone': ''},
    {'name': 'Hindustan Child Hospital', 'zone': ''},
    {'name': 'ICON hospital - Nalgonda', 'zone': ''},
    {'name': 'IIGH - Cuttack', 'zone': ''},
    {'name': 'Ideal Children Hospital - Varanasi', 'zone': ''},
    {'name': 'Imax Multispeciality - Pune', 'zone': ''},
    {'name': 'Inamdar Multispeciality Hospital', 'zone': ''},
    {'name': 'Indus Hospital - Visakhapatnam', 'zone': ''},
    {'name': 'J.V.M. Mother and Child - Tenali', 'zone': ''},
    {'name': 'JGR Hospital - Pithapuram_ICU', 'zone': ''},
    {'name': 'Jai Patai Mata Hospital - Patewa', 'zone': ''},
    {'name': 'Janani Hospital - Hosur', 'zone': ''},
    {'name': 'Jivan Jyot - Vadodara', 'zone': ''},
    {'name': 'Kailash Superspeciality Hospital', 'zone': ''},
    {'name': 'Kalghatgi', 'zone': ''},
    {'name': 'Kalindi Hospital - Kushinagar', 'zone': ''},
    {'name': 'Kalpataru Hospital - Anjangaon', 'zone': ''},
    {'name': 'Kalpit Hospital - Khalilabad', 'zone': ''},
    {'name': 'Kamal Mahajan Hospital - Amritsar', 'zone': ''},
    {'name': 'Kamala Hospitals - Kovilpatti', 'zone': ''},
    {'name': 'Kaneria - Junagadh', 'zone': ''},
    {'name': 'Kanha - Orai', 'zone': ''},
    {'name': 'Karpagam Hospital - Othakkalmandapam', 'zone': ''},
    {'name': 'Kavan Hospital - Harur', 'zone': ''},
    {'name': 'Keerthana Visakhapatnam', 'zone': ''},
    {'name': 'Keshav Heritage', 'zone': ''},
    {'name': 'Kirti Multispeciality - Bhandara', 'zone': ''},
    {'name': 'Kochhar Nursing Home - Tumsar', 'zone': ''},
    {'name': 'Krishna Children - Hyderabad', 'zone': ''},
    {'name': 'Krishna Children - Pusad', 'zone': ''},
    {'name': 'Krishna Hospital - Samastipur', 'zone': ''},
    {'name': 'Krishna Superspeciality - Bhatinda', 'zone': ''},
    {'name': 'Krishnammal Memorial - Theni', 'zone': ''},
    {'name': 'Kshema - Hubbali', 'zone': ''},
    {'name': 'Laalityam Hospital-Hyderabad', 'zone': ''},
    {'name': 'Laalityam Hospitals - Hyderabad', 'zone': ''},
    {'name': 'Lakhichand', 'zone': ''},
    {'name': 'Lakshya Super Speciality - Proddatur', 'zone': ''},
    {'name': 'Leonard Hospital - Batlagundu', 'zone': ''},
    {'name': 'Life Care Hospital', 'zone': ''},
    {'name': 'Life Hospital - Chirala', 'zone': ''},
    {'name': 'Life Hospital - Guntur', 'zone': ''},
    {'name': 'Life Line Daltonganj', 'zone': ''},
    {'name': 'Lifepoint - Pune', 'zone': ''},
    {'name': 'Livasa Hospital - Khanna', 'zone': ''},
    {'name': 'Lotus Hospital - Belagavi', 'zone': ''},
    {'name': 'MAHAN Trust', 'zone': ''},
    {'name': 'MB Multispeciality - Visakhapatnam', 'zone': ''},
    {'name': 'MK Nursing Home - Chennai', 'zone': ''},
    {'name': 'MMH Rajapalayam', 'zone': ''},
    {'name': 'MR Thanjavur', 'zone': ''},
    {'name': 'MRNH', 'zone': ''},
    {'name': 'MS Multispeciality - Pithapuram', 'zone': ''},
    {'name': 'Maa Sharada Vikarabad', 'zone': ''},
    {'name': 'Mahalakshmi Multispeciality - Ulundurpet', 'zone': ''},
    {'name': 'Mahathma Gandhi - Narasaraopeta', 'zone': ''},
    {'name': 'Maiyan Babu Hospital - Daltonganj', 'zone': ''},
    {'name': 'Manwath Multi-Speciality Hospital', 'zone': ''},
    {'name': 'Mawana Healthcare Center', 'zone': ''},
    {'name': 'Maxfort Aligarh', 'zone': ''},
    {'name': 'Maxlife Superspeciality - Bareilly', 'zone': ''},
    {'name': 'Medical Trust Hospital', 'zone': ''},
    {'name': 'Medifort Hospital - Bhagalpur', 'zone': ''},
    {'name': 'Mediversal Maatri - Patna', 'zone': ''},
    {'name': 'Medway Heart Institute - Kodambakkam', 'zone': ''},
    {'name': 'Medway Hospitals - Erode', 'zone': ''},
    {'name': 'Meera Multispeciality - Hosur', 'zone': ''},
    {'name': 'Metro Super Speciality Hospital - Vijayawada', 'zone': ''},
    {'name': 'Mundhra Hospital - Chaibasa', 'zone': ''},
    {'name': 'Muniya Nadar Memorial - Thanjavur', 'zone': ''},
    {'name': 'Mythri - Bengaluru', 'zone': ''},
    {'name': 'NDR Hospital - Bangalore', 'zone': ''},
    {'name': 'Nageshwari Gopalganj', 'zone': ''},
    {'name': 'Nalanda Bone & Spine', 'zone': ''},
    {'name': 'Nankem Hospital - Coonoor', 'zone': ''},
    {'name': 'Navjeevan Children\'s - Pandharpur', 'zone': ''},
    {'name': 'Navjivan Multispeciality - Sitamarhi', 'zone': ''},
    {'name': 'Neo TrueNorth - Bengaluru', 'zone': ''},
    {'name': 'Neurolife Hospital - Bathinda', 'zone': ''},
    {'name': 'Neuron Plus - Karad', 'zone': ''},
    {'name': 'New Venkatesh Hospital - Manwath', 'zone': ''},
    {'name': 'Nidan Healthcare - Hazaribagh', 'zone': ''},
    {'name': 'Nikhil - Dilsukhnagar', 'zone': ''},
    {'name': 'Nikhil - Srinagar Colony', 'zone': ''},
    {'name': 'Nizar Hospital - Malappuram', 'zone': ''},
    {'name': 'OSG Laparoscopy Hospital', 'zone': ''},
    {'name': 'Omkilkari Hospital - Varanasi', 'zone': ''},
    {'name': 'Ours Hospital - Hisar', 'zone': ''},
    {'name': 'P V Cancer Centre - Sathyamangalam', 'zone': ''},
    {'name': 'PMH Dhanbad', 'zone': ''},
    {'name': 'Pakur Nursing Home', 'zone': ''},
    {'name': 'Parameshwari Devi - New Delhi', 'zone': ''},
    {'name': 'Paramount Mumbai', 'zone': ''},
    {'name': 'Paridhi', 'zone': ''},
    {'name': 'Parmar Hospital - Karnal', 'zone': ''},
    {'name': 'Patil Hospital - Koregaon', 'zone': ''},
    {'name': 'Perumalla Hospital - Nalgonda', 'zone': ''},
    {'name': 'Pranav Hospital - Brahmavara', 'zone': ''},
    {'name': 'Pranayu Hospital - Thane', 'zone': ''},
    {'name': 'Prasad Athani', 'zone': ''},
    {'name': 'Prasad Global Hospital - Prasad Medical Centre', 'zone': ''},
    {'name': 'Prashant', 'zone': ''},
    {'name': 'Pratheep Nursing Home', 'zone': ''},
    {'name': 'Priya Hospital - Varanasi', 'zone': ''},
    {'name': 'Punya Hospital - Bengaluru', 'zone': ''},
    {'name': 'Queen\'s NRI Hospital - Vizianagaram', 'zone': ''},
    {'name': 'RD Multi Speciality Hospital', 'zone': ''},
    {'name': 'RMD Nursing Home - T. Nagar', 'zone': ''},
    {'name': 'RMD Specialities Hospital - Amarambedu', 'zone': ''},
    {'name': 'RN Pandey - Gonda', 'zone': ''},
    {'name': 'RPS Hospital - Kharak', 'zone': ''},
    {'name': 'RadOn Cancer Centre', 'zone': ''},
    {'name': 'Radhakrishna Hospital - Tanuku', 'zone': ''},
    {'name': 'Rahul Multispeciality Hospital - Kothakota', 'zone': ''},
    {'name': 'Rajawat Hospital - Kanpur', 'zone': ''},
    {'name': 'Rajesh Neuro Foundation - Nagercoil', 'zone': ''},
    {'name': 'Rajeswari Multispeciality - Rameswaram', 'zone': ''},
    {'name': 'Rajshekar Multi Speciality - Bengaluru', 'zone': ''},
    {'name': 'Rakshit Sirsa', 'zone': ''},
    {'name': 'Rebirth ICU & Hospital - Junagadh', 'zone': ''},
    {'name': 'Reform Healthcare - Patna', 'zone': ''},
    {'name': 'Regal', 'zone': ''},
    {'name': 'Relief Hospital - Boisar', 'zone': ''},
    {'name': 'Relief Hospital - Palghar', 'zone': ''},
    {'name': 'Renee Hospital - Karimnagar', 'zone': ''},
    {'name': 'Renova Neelima - Hyderabad', 'zone': ''},
    {'name': 'S.D.A. Medical Center - Bengaluru', 'zone': ''},
    {'name': 'SNS Hospital - Neyveli', 'zone': ''},
    {'name': 'SV Clinic - Palladam', 'zone': ''},
    {'name': 'SV Yennam Hospital', 'zone': ''},
    {'name': 'SVCA - Darbhanga', 'zone': ''},
    {'name': 'SWASA Hyderabad', 'zone': ''},
    {'name': 'Sadguru Children Hospital - Nadiad', 'zone': ''},
    {'name': 'Sadhana - Mudhol', 'zone': ''},
    {'name': 'Sahaj Hospital - Indore', 'zone': ''},
    {'name': 'Sahasra Hospital - Bengaluru', 'zone': ''},
    {'name': 'Sai Ram - Kurnool', 'zone': ''},
    {'name': 'Samarth Hospital - Selu', 'zone': ''},
    {'name': 'San Joe Hospital - Ernakulam', 'zone': ''},
    {'name': 'Sanjeevani - Bilaspur', 'zone': ''},
    {'name': 'Sanjeevani Samastipur', 'zone': ''},
    {'name': 'Sanjeevani Superspeciality - Nagpur', 'zone': ''},
    {'name': 'Sanjivani Sirsa', 'zone': ''},
    {'name': 'Sankalp Hospital', 'zone': ''},
    {'name': 'Sanrohi Hospital - Zaheerabad', 'zone': ''},
    {'name': 'Santevita Ranchi', 'zone': ''},
    {'name': 'Sarayu Children\'s Hospital - Sircilla', 'zone': ''},
    {'name': 'Saroj Hospital - Jhansi', 'zone': ''},
    {'name': 'Sarvodya Hospital - Jalandhar', 'zone': ''},
    {'name': 'Sarvottam Hospital - Bhopal', 'zone': ''},
    {'name': 'Satya Kalindi - Muzaffarpur', 'zone': ''},
    {'name': 'Satyadev Superspeciality Patna', 'zone': ''},
    {'name': 'Shahnaaz Rural', 'zone': ''},
    {'name': 'Shameer Hospital - Kunigal', 'zone': ''},
    {'name': 'Shanti Hospital - Jaunpur', 'zone': ''},
    {'name': 'Sharanabasava Hospital, Yadgir', 'zone': ''},
    {'name': 'Shifa Hospital - Tirunelveli', 'zone': ''},
    {'name': 'Shishu Bhavan Hospital - Bilaspur', 'zone': ''},
    {'name': 'Shiv Kamal Memorial - Bhagalpur', 'zone': ''},
    {'name': 'Shiv Seva Sadan - DM Hospital', 'zone': ''},
    {'name': 'Shree Ganesha - Shirur', 'zone': ''},
    {'name': 'Shree Hospital', 'zone': ''},
    {'name': 'Shree Narsinh - Balod', 'zone': ''},
    {'name': 'Shree Sai Baba Hospital - Sinnar', 'zone': ''},
    {'name': 'Shree Sathya Subha', 'zone': ''},
    {'name': 'Shree Vishudhanand - Kolkata', 'zone': ''},
    {'name': 'Shri Shyam Kotputli', 'zone': ''},
    {'name': 'Shriram Hospital - Sultanpur', 'zone': ''},
    {'name': 'Shyam Child Care & Maternity Centre', 'zone': ''},
    {'name': 'Shyavi Sanjeevini - Ilkal', 'zone': ''},
    {'name': 'Siddhi Vinayak Hospital', 'zone': ''},
    {'name': 'Siddhivinayak Children\'s Hospital - Ahilya Nagar', 'zone': ''},
    {'name': 'Siu Ka Pha Hospital', 'zone': ''},
    {'name': 'Smart Rajamahendravaram', 'zone': ''},
    {'name': 'Sowmiya Hospital - Karamadai', 'zone': ''},
    {'name': 'Spandan - Belagavi', 'zone': ''},
    {'name': 'Spandan Jamnagar', 'zone': ''},
    {'name': 'Sravani Hospital - Guntur', 'zone': ''},
    {'name': 'Sree Ayyappa - Kozhencherry', 'zone': ''},
    {'name': 'Sri Ganga - Rajamahendravaram', 'zone': ''},
    {'name': 'Sri Keshav - Rajamahendravaram', 'zone': ''},
    {'name': 'Sri Sai Ganga Nursing Home', 'zone': ''},
    {'name': 'Sri Sai Hospital - Bengaluru', 'zone': ''},
    {'name': 'Sri Sai Life Line - Karimnagar', 'zone': ''},
    {'name': 'Sri Sai Life Line - Karinmagar', 'zone': ''},
    {'name': 'Sri Sri Holistic - Proddatur', 'zone': ''},
    {'name': 'Sri Suraksha Multispeciality - Gudivada', 'zone': ''},
    {'name': 'Srinivasa Hospital - Hyderabad', 'zone': ''},
    {'name': 'Sripathi Hospet', 'zone': ''},
    {'name': 'St. Theresa - Vellore', 'zone': ''},
    {'name': 'Stork Hospital - Hyderabad', 'zone': ''},
    {'name': 'Sunrise Godda', 'zone': ''},
    {'name': 'Sunrise Patna', 'zone': ''},
    {'name': 'Sunrise Varanasi', 'zone': ''},
    {'name': 'Sunseed Hospitals - Hyderabad', 'zone': ''},
    {'name': 'Sunstar Hospital - Rajamahendravaram', 'zone': ''},
    {'name': 'Surendra Hospital - Angul', 'zone': ''},
    {'name': 'Suriyan Hospital - Tiruvannamalai', 'zone': ''},
    {'name': 'Surya Super Speciality - Sahibganj', 'zone': ''},
    {'name': 'Sushruta Bhubaneswar', 'zone': ''},
    {'name': 'Synergy Global', 'zone': ''},
    {'name': 'TLM Chandkhuri', 'zone': ''},
    {'name': 'Taneja Hospital - Jagraon', 'zone': ''},
    {'name': 'Tridev Deoghar', 'zone': ''},
    {'name': 'Trust-In Hospital - Bengaluru', 'zone': ''},
    {'name': 'Tulip Superspeciality - Pandharpur', 'zone': ''},
    {'name': 'Udayananda Hospital - Nandyal', 'zone': ''},
    {'name': 'United City - Ahmednagar', 'zone': ''},
    {'name': 'Urmila Devi Memorial Hospital', 'zone': ''},
    {'name': 'V Care - Bengaluru', 'zone': ''},
    {'name': 'V Care - Hubli', 'zone': ''},
    {'name': 'VGK Heart Institute - Raichur', 'zone': ''},
    {'name': 'Vajra Hospitals - Hyderabad', 'zone': ''},
    {'name': 'Valentis Cancer Hospital - Meerut', 'zone': ''},
    {'name': 'Varad Multispeciality - Atpadi', 'zone': ''},
    {'name': 'Varad Multispeciality Hospital', 'zone': ''},
    {'name': 'Varasiddii Hospital - Gangavati', 'zone': ''},
    {'name': 'Vardaan Hospital - Ranchi', 'zone': ''},
    {'name': 'Vardhaman Hospital - Guna', 'zone': ''},
    {'name': 'Ved Hospital - Kheda', 'zone': ''},
    {'name': 'Vedanta Hospital - Bulandshahr', 'zone': ''},
    {'name': 'Vijaya Global Hospital - Belagavi', 'zone': ''},
    {'name': 'Vijaya Golbal Hospital - Belagavi', 'zone': ''},
    {'name': 'Vijaya Multi-Speciality - Sankeshwar', 'zone': ''},
    {'name': 'Vijaya Ortho & Trauma - Belagavi', 'zone': ''},
    {'name': 'Viva Shadnagar', 'zone': ''},
    {'name': 'Vivekanand Hospital - Khalilabad', 'zone': ''},
    {'name': 'Vivekananda Memorial Hospital - Saragur', 'zone': ''},
    {'name': 'WIINS Kolhapur', 'zone': ''},
    {'name': 'Willis F. Pierce Memorial - Wai', 'zone': ''},
    {'name': 'Yashwantrao Chavan - Junnar', 'zone': ''},
    {'name': 'Yogyam Hospital - Vasai', 'zone': ''},
]
# Total: 329 hospitals from CSV file

def get_hospitals():
    """Get hospitals list from CSV, initialize with defaults if empty or has fewer hospitals"""
    hospitals = read_csv(HOSPITALS_CSV, ['name', 'zone'])
    if not hospitals or len(hospitals) < len(DEFAULT_HOSPITALS):
        # Initialize with defaults if CSV is empty or has fewer hospitals
        save_hospitals(DEFAULT_HOSPITALS)
        return DEFAULT_HOSPITALS.copy()
    return hospitals

def save_hospitals(hospitals_list):
    """Save hospitals list"""
    write_csv(HOSPITALS_CSV, hospitals_list, ['name', 'zone'])

def get_team_members():
    """Get team members list"""
    return read_csv(TEAM_CSV, ['uid', 'name', 'email'])

def save_team_members(team_list):
    """Save team members list"""
    write_csv(TEAM_CSV, team_list, ['uid', 'name', 'email'])

# Category Management Functions
def get_categories():
    """Get current categories"""
    return CATEGORY_MAPPINGS

def add_category(category_name, subcategories=None):
    """Add a new category"""
    global CATEGORY_MAPPINGS
    CATEGORY_MAPPINGS[category_name] = subcategories or []
    save_categories(CATEGORY_MAPPINGS)

def update_category(old_name, new_name):
    """Update category name"""
    global CATEGORY_MAPPINGS
    if old_name in CATEGORY_MAPPINGS:
        subcategories = CATEGORY_MAPPINGS.pop(old_name)
        CATEGORY_MAPPINGS[new_name] = subcategories
        save_categories(CATEGORY_MAPPINGS)
        return True
    return False

def delete_category(category_name):
    """Delete a category"""
    global CATEGORY_MAPPINGS
    if category_name in CATEGORY_MAPPINGS:
        del CATEGORY_MAPPINGS[category_name]
        save_categories(CATEGORY_MAPPINGS)
        return True
    return False

def add_subcategory(category_name, subcategory):
    """Add subcategory to a category"""
    global CATEGORY_MAPPINGS
    if category_name in CATEGORY_MAPPINGS:
        if subcategory not in CATEGORY_MAPPINGS[category_name]:
            CATEGORY_MAPPINGS[category_name].append(subcategory)
            save_categories(CATEGORY_MAPPINGS)
            return True
    return False

def update_subcategory(category_name, old_sub, new_sub):
    """Update subcategory name"""
    global CATEGORY_MAPPINGS
    if category_name in CATEGORY_MAPPINGS:
        subcategories = CATEGORY_MAPPINGS[category_name]
        if old_sub in subcategories:
            index = subcategories.index(old_sub)
            subcategories[index] = new_sub
            save_categories(CATEGORY_MAPPINGS)
            return True
    return False

def delete_subcategory(category_name, subcategory):
    """Delete a subcategory"""
    global CATEGORY_MAPPINGS
    if category_name in CATEGORY_MAPPINGS:
        if subcategory in CATEGORY_MAPPINGS[category_name]:
            CATEGORY_MAPPINGS[category_name].remove(subcategory)
            save_categories(CATEGORY_MAPPINGS)
            return True
    return False

# Routes
@app.before_request
def refresh_user_role():
    """Refresh user role from database on each request to ensure admin status is current"""
    if 'user_id' in session and 'user_email' in session:
        user_email = session.get('user_email')
        if not user_email:
            # Try to get email from user_id if email is missing
            user_id = session.get('user_id')
            if user_id:
                user = get_user_by_id(user_id)
                if user:
                    user_email = user.get('email')
                    session['user_email'] = user_email
        
        if user_email:
            # Check if user should be admin based on current admin list
            if is_admin(user_email):
                user = get_user_by_email(user_email)
                if user:
                    if user.get('role') != 'admin':
                        # Update user role in database
                        user['role'] = 'admin'
                        create_or_update_user(user)
                    # Update session role
                    session['user_role'] = 'admin'
            else:
                # If not admin, ensure role is set correctly from database
                user = get_user_by_email(user_email)
                if user:
                    session['user_role'] = user.get('role', 'member')

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/index.html')
def index_html():
    """Redirect index.html to main route to ensure only Flask templates are used"""
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Email is required', 'error')
            return render_template('login.html')
        
        # Check email domain
        if not email.endswith(f'@{ALLOWED_DOMAIN}'):
            flash(f'Only {ALLOWED_DOMAIN} email addresses are allowed', 'error')
            return render_template('login.html')
        
        # Get or create user
        user = get_user_by_email(email)
        if not user:
            # Determine role based on hardcoded admin list
            role = 'admin' if is_admin(email) else 'member'
            user = create_or_update_user({
                'email': email,
                'name': email.split('@')[0],
                'role': role
            })
        else:
            # Update role if user is in admin list
            if is_admin(email):
                user['role'] = 'admin'
                create_or_update_user(user)
        
        # Set session
        session['user_id'] = user['id']
        session['user_email'] = email
        session['user_name'] = user.get('name', email.split('@')[0])
        session['user_role'] = user.get('role', 'member')
        
        return redirect(url_for('dashboard'))
    
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    issues = get_all_issues()
    
    now = datetime.now()
    today = datetime(now.year, now.month, now.day)
    one_week_ago = today - timedelta(days=7)
    one_day_ago = today - timedelta(days=1)
    
    stats = {
        'totalTasks': len(issues),
        'openTasks': 0,
        'closedTasks': 0,
        'closedThisWeek': 0,
        'createdToday': 0,
        'closedToday': 0,
        'categoryCounts': {},
        'hospitalCounts': {},
        'avgResolutionTime': 0,
        'trendData': []
    }
    
    current_user_email = session.get('user_email', '')
    total_resolution_time = 0
    resolved_count = 0
    
    # Initialize trend data
    trend_data = {}
    for i in range(30):
        date = (today - timedelta(days=29-i)).strftime('%Y-%m-%d')
        trend_data[date] = {'created': 0, 'closed': 0}
    
    for issue in issues:
        # Check if closed
        is_closed = bool(issue.get('dateClosed'))
        
        if is_closed:
            stats['closedTasks'] += 1
        else:
            stats['openTasks'] += 1
        
        # Category counts
        category = issue.get('category', 'Other')
        stats['categoryCounts'][category] = stats['categoryCounts'].get(category, 0) + 1
        
        # Hospital counts
        hospital = issue.get('hospital', 'Unknown')
        stats['hospitalCounts'][hospital] = stats['hospitalCounts'].get(hospital, 0) + 1
        
        # Parse dates
        try:
            time_started = datetime.fromisoformat(issue.get('time_started', '').replace('Z', '+00:00')) if issue.get('time_started') else None
            time_closed = datetime.fromisoformat(issue.get('dateClosed', '').replace('Z', '+00:00')) if issue.get('dateClosed') else None
        except:
            time_started = None
            time_closed = None
        
        # Closed this week
        if time_closed:
            if time_closed >= one_week_ago:
                stats['closedThisWeek'] += 1
            if time_closed >= one_day_ago:
                stats['closedToday'] += 1
            
            # Resolution time
            if time_started:
                resolution_days = (time_closed - time_started).days
                total_resolution_time += resolution_days
                resolved_count += 1
            
            # Trend data
            date_str = time_closed.strftime('%Y-%m-%d')
            if date_str in trend_data:
                trend_data[date_str]['closed'] += 1
        
        # Created today
        if time_started and time_started >= one_day_ago:
            stats['createdToday'] += 1
            
            # Trend data
            date_str = time_started.strftime('%Y-%m-%d')
            if date_str in trend_data:
                trend_data[date_str]['created'] += 1
    
    # Calculate average resolution time
    if resolved_count > 0:
        stats['avgResolutionTime'] = round(total_resolution_time / resolved_count, 1)
    
    # Convert trend data to array
    stats['trendData'] = [{'date': date, 'created': data['created'], 'closed': data['closed']} 
                         for date, data in sorted(trend_data.items())]
    
    return render_template('dashboard.html', stats=stats)

@app.route('/issues')
@login_required
def issues():
    issues_list = get_all_issues()
    current_user_email = session.get('user_email', '')
    
    # Filter for my tasks if requested
    my_tasks = request.args.get('my_tasks') == '1'
    if my_tasks:
        current_user_name = session.get('user_name', '')
        issues_list = [i for i in issues_list if 
                      (i.get('mainOwner') == current_user_name or 
                       current_user_name in (i.get('coOwners', '') or '').split(',')) and 
                      i.get('status') != 'Closed']
    
    # Apply filters
    category = request.args.get('category')
    hospital = request.args.get('hospital')
    status_filter = request.args.get('status')
    zone_filter = request.args.get('zone')
    priority_filter = request.args.get('priority')
    search = request.args.get('search', '').lower()
    
    filtered_issues = issues_list
    if category:
        # Match exact category or category with subcategory (format: "Category: Subcategory")
        filtered_issues = [i for i in filtered_issues 
                          if (i.get('category') or '') == category or 
                             (i.get('category') or '').startswith(category + ': ')]
    if hospital:
        filtered_issues = [i for i in filtered_issues if i.get('hospitalUnit') == hospital]
    if zone_filter:
        filtered_issues = [i for i in filtered_issues if i.get('zone') == zone_filter]
    if priority_filter:
        filtered_issues = [i for i in filtered_issues if i.get('priority') == priority_filter]
    if status_filter:
        filtered_issues = [i for i in filtered_issues if i.get('status') == status_filter]
    if search:
        filtered_issues = [i for i in filtered_issues if 
                         search in (i.get('taskName', '') or '').lower() or
                         search in (i.get('description', '') or '').lower() or
                         search in (i.get('hospitalUnit', '') or '').lower() or
                         search in (i.get('category', '') or '').lower()]
    
    # Apply sorting
    sort_by = request.args.get('sort_by', 'dateLogged')
    sort_dir = request.args.get('sort_dir', 'desc')
    
    def sort_key(issue):
        value = issue.get(sort_by, '')
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    
    filtered_issues.sort(key=sort_key, reverse=(sort_dir == 'desc'))
    
    # Format issues for template
    formatted_issues = []
    issues_to_update = []
    for issue in filtered_issues:
        formatted_issue = dict(issue)
        formatted_issue['dateLogged_formatted'] = format_datetime(issue.get('dateLogged'))
        formatted_issue['dueDate_formatted'] = format_date(issue.get('dueDate'))
        # Sync status with dateClosed - if dateClosed is set, status should be Closed
        if issue.get('dateClosed') and formatted_issue.get('status') != 'Closed':
            formatted_issue['status'] = 'Closed'
            issue['status'] = 'Closed'
            issues_to_update.append(issue)
        formatted_issues.append(formatted_issue)
    
    # Update issues that need status sync (batch update)
    if issues_to_update:
        all_issues = get_all_issues()
        for updated_issue in issues_to_update:
            all_issues = [i for i in all_issues if i.get('id') != updated_issue.get('id')]
            all_issues.append(updated_issue)
        write_csv(ISSUES_CSV, all_issues, ISSUES_HEADERS)
    
    # Pagination
    page = int(request.args.get('page', 1))
    per_page = 25
    total = len(formatted_issues)
    start = (page - 1) * per_page
    end = start + per_page
    
    paginated_issues = formatted_issues[start:end]
    
    # Get hospitals from CSV and sort alphabetically
    all_hospitals = get_hospitals()
    all_hospitals.sort(key=lambda h: h.get('name', '').lower())
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': (total + per_page - 1) // per_page
    }
    
    # Get all categories from hardcoded mappings
    all_categories_list = list(CATEGORY_MAPPINGS.keys())
    
    # Get all users for owner dropdowns (use all users, not just team members)
    all_users = get_all_users()
    # Convert users to team_members format for compatibility with template
    team_members = [{'name': user.get('name', ''), 'email': user.get('email', '')} for user in all_users]
    # Sort by name
    team_members.sort(key=lambda x: x.get('name', '').lower())
    
    return render_template('issues.html', 
                         issues=paginated_issues,
                         categories=all_categories_list,
                         hospitals=all_hospitals,
                         team_members=team_members,
                         category_mappings=CATEGORY_MAPPINGS,
                         pagination=pagination,
                         my_tasks=my_tasks)

@app.route('/my-tasks')
@login_required
def my_tasks():
    return redirect(url_for('issues', my_tasks='1'))

@app.route('/issues/create', methods=['POST'])
@login_required
def create_issue():
    user_email = session.get('user_email', '')
    user_name = session.get('user_name', user_email.split('@')[0])
    
    # Get category - use main category if subcategory not provided
    main_category = request.form.get('mainCategory', '')
    sub_category = request.form.get('subCategory', '')
    other_sub = request.form.get('otherSubCategory', '')
    
    if other_sub:
        category = f"{main_category}: {other_sub}"
    elif sub_category:
        category = f"{main_category}: {sub_category}"
    else:
        category = main_category
    
    # Get co-owners as comma-separated string
    co_owners = []
    if request.form.get('coOwner1'):
        co_owners.append(request.form.get('coOwner1'))
    if request.form.get('coOwner2'):
        co_owners.append(request.form.get('coOwner2'))
    co_owners_str = ','.join(co_owners)
    
    now = datetime.now().isoformat()
    
    new_issue = {
        'hospitalUnit': request.form.get('hospitalUnit', ''),
        'zone': request.form.get('zone', ''),
        'priority': request.form.get('priority', 'Medium'),
        'category': category,
        'taskName': request.form.get('taskName', ''),
        'description': request.form.get('description', ''),
        'mainOwner': request.form.get('mainOwner', ''),
        'coOwners': co_owners_str,
        'dueDate': request.form.get('dueDate', '') or '',
        'status': 'Open',
        'dateLogged': now,
        'dateClosed': '',
        'createdBy': user_name,
        'lastModified': now,
        'lastModifiedBy': user_name,
        'resolvedBy': '',
        'stepsTaken': '',
        'reviewNotes': ''
    }
    
    issue_id = save_issue(new_issue)
    
    # Add history entry
    add_history(issue_id, {
        'user': user_name,
        'action': f'created the task for {new_issue["hospitalUnit"]}.',
        'timestamp': now
    })
    
    flash('Issue created successfully', 'success')
    return redirect(url_for('issues'))

@app.route('/issues/<issue_id>')
@login_required
def issue_detail(issue_id):
    issues = get_all_issues()
    issue = next((i for i in issues if i.get('id') == str(issue_id)), None)
    
    if not issue:
        flash('Issue not found', 'error')
        return redirect(url_for('issues'))
    
    # Format issue
    formatted_issue = dict(issue)
    formatted_issue['dateLogged_formatted'] = format_datetime(issue.get('dateLogged'))
    formatted_issue['dateClosed_formatted'] = format_datetime(issue.get('dateClosed')) if issue.get('dateClosed') else None
    formatted_issue['dueDate_formatted'] = format_date(issue.get('dueDate'))
    formatted_issue['is_closed'] = bool(issue.get('dateClosed'))
    
    # Get creator email
    all_users = get_all_users()
    creator_name = issue.get('createdBy', '')
    creator_user = next((u for u in all_users if u.get('name') == creator_name), None)
    formatted_issue['creatorEmail'] = creator_user.get('email', '') if creator_user else ''
    
    # Get comments
    comments = get_comments(issue_id)
    # Format comments with timestamps
    for comment in comments:
        comment['timestamp_formatted'] = format_datetime(comment.get('timestamp'))
        # If authorEmail is missing, try to look it up
        if not comment.get('authorEmail'):
            author_name = comment.get('authorName', '')
            author_user = next((u for u in all_users if u.get('name') == author_name), None)
            comment['authorEmail'] = author_user.get('email', '') if author_user else ''
    
    return render_template('issue_detail.html', issue=formatted_issue, comments=comments, category_mappings=CATEGORY_MAPPINGS)

@app.route('/issues/<issue_id>/close', methods=['POST'])
@login_required
def close_issue(issue_id):
    issues = get_all_issues()
    issue = next((i for i in issues if i.get('id') == str(issue_id)), None)
    
    if not issue:
        flash('Issue not found', 'error')
        return redirect(url_for('issues'))
    
    if issue.get('dateClosed'):
        flash('Issue is already closed', 'info')
        return redirect(url_for('issue_detail', issue_id=issue_id))
    
    # Close the issue
    issue['dateClosed'] = datetime.now().isoformat()
    issue['status'] = 'Closed'
    save_issue(issue)
    
    flash('Issue closed successfully', 'success')
    return redirect(url_for('issue_detail', issue_id=issue_id))

# Delete functionality removed - tasks are not deletable
# @app.route('/issues/<issue_id>/delete', methods=['POST'])
# @admin_required
# def delete_issue(issue_id):
#     delete_issue_data(issue_id)
#     flash('Issue deleted', 'success')
#     return redirect(url_for('issues'))

@app.route('/issues/<issue_id>/comments', methods=['POST'])
@login_required
def add_comment(issue_id):
    user_name = session.get('user_name', session.get('user_email', 'Unknown'))
    user_email = session.get('user_email', '')
    
    comment_id = save_comment(issue_id, {
        'text': request.form.get('text', ''),
        'authorName': user_name,
        'authorEmail': user_email
    })
    
    # Update issue last modified
    issues = get_all_issues()
    issue = next((i for i in issues if i.get('id') == str(issue_id)), None)
    if issue:
        issue['lastModified'] = datetime.now().isoformat()
        issue['lastModifiedBy'] = user_name
        save_issue(issue)
    
    flash('Comment added', 'success')
    return redirect(url_for('issue_detail', issue_id=issue_id))

@app.route('/issues/<issue_id>/attachments/upload', methods=['POST'])
@login_required
def upload_attachment(issue_id):
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('issue_detail', issue_id=issue_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('issue_detail', issue_id=issue_id))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Create issue-specific directory
        issue_dir = ATTACHMENTS_FILES_DIR / issue_id
        issue_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        filepath = issue_dir / filename
        file.save(str(filepath))
        
        # Add to attachments CSV
        user_name = session.get('user_name', session.get('user_email', 'Unknown'))
        download_url = f'/attachments/{issue_id}/{filename}'
        
        add_attachment(issue_id, {
            'fileName': filename,
            'downloadURL': download_url,
            'uploadedBy': user_name
        })
        
        # Add history
        add_history(issue_id, {
            'user': user_name,
            'action': f'uploaded attachment: {filename}.'
        })
        
        flash('File uploaded successfully', 'success')
    else:
        flash('File type not allowed', 'error')
    
    return redirect(url_for('issue_detail', issue_id=issue_id))

@app.route('/attachments/<issue_id>/<filename>')
@login_required
def download_attachment(issue_id, filename):
    return send_from_directory(ATTACHMENTS_FILES_DIR / issue_id, filename)

@app.route('/issues/<issue_id>/attachments/<attachment_id>/delete', methods=['POST'])
@admin_required
def delete_attachment(issue_id, attachment_id):
    attachments = get_attachments(issue_id)
    attachment = next((a for a in attachments if a.get('id') == attachment_id), None)
    
    if attachment:
        # Delete file
        filepath = ATTACHMENTS_FILES_DIR / issue_id / attachment['fileName']
        if filepath.exists():
            filepath.unlink()
        
        # Remove from CSV
        attachments = [a for a in attachments if a.get('id') != attachment_id]
        write_csv(ATTACHMENTS_DIR / f'{issue_id}.csv', attachments, ['id', 'fileName', 'downloadURL', 'uploadedBy', 'timestamp'])
        
        flash('Attachment deleted', 'success')
    
    return redirect(url_for('issue_detail', issue_id=issue_id))

@app.route('/profile')
@login_required
def profile():
    user = get_user_by_email(session.get('user_email'))
    return render_template('profile.html', user=user or {})

@app.route('/profile/save', methods=['POST'])
@login_required
def save_profile():
    user = get_user_by_email(session.get('user_email'))
    if user:
        user['googleChatWebhookUrl'] = request.form.get('webhook_url', '')
        create_or_update_user(user)
        flash('Profile updated', 'success')
    return redirect(url_for('profile'))

@app.route('/admin')
@admin_required
def admin():
    """Admin panel with full management capabilities"""
    hospitals = get_hospitals()
    # Sort hospitals alphabetically
    hospitals.sort(key=lambda h: h.get('name', '').lower())
    team_members = get_team_members()
    all_users = get_all_users()
    return render_template('admin.html', 
                         category_mappings=CATEGORY_MAPPINGS,
                         admin_users=ADMIN_USERS,
                         hospitals=hospitals,
                         team_members=team_members,
                         all_users=all_users)

# Category Management Routes
@app.route('/admin/categories/add', methods=['POST'])
@admin_required
def add_category_route():
    category_name = request.form.get('category_name', '').strip()
    if not category_name:
        flash('Category name is required', 'error')
        return redirect(url_for('admin'))
    
    if category_name in CATEGORY_MAPPINGS:
        flash('Category already exists', 'error')
    else:
        add_category(category_name, [])
        flash('Category added successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/categories/<path:category>/edit', methods=['POST'])
@admin_required
def edit_category_route(category):
    category = unquote(category)
    new_name = request.form.get('new_name', '').strip()
    if not new_name:
        flash('Category name is required', 'error')
        return redirect(url_for('admin'))
    
    if update_category(category, new_name):
        flash('Category updated successfully', 'success')
    else:
        flash('Category not found', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/categories/<path:category>/delete', methods=['POST'])
@admin_required
def delete_category_route(category):
    category = unquote(category)
    if delete_category(category):
        flash('Category deleted successfully', 'success')
    else:
        flash('Category not found', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/categories/<path:category>/subcategories/add', methods=['POST'])
@admin_required
def add_subcategory_route(category):
    category = unquote(category)
    subcategory = request.form.get('subcategory', '').strip()
    if not subcategory:
        flash('Subcategory name is required', 'error')
        return redirect(url_for('admin'))
    
    if add_subcategory(category, subcategory):
        flash('Subcategory added successfully', 'success')
    else:
        flash('Category not found or subcategory already exists', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/categories/<path:category>/subcategories/<path:sub>/edit', methods=['POST'])
@admin_required
def edit_subcategory_route(category, sub):
    category = unquote(category)
    sub = unquote(sub)
    new_sub = request.form.get('new_sub', '').strip()
    if not new_sub:
        flash('Subcategory name is required', 'error')
        return redirect(url_for('admin'))
    
    if update_subcategory(category, sub, new_sub):
        flash('Subcategory updated successfully', 'success')
    else:
        flash('Subcategory not found', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/categories/<path:category>/subcategories/<path:sub>/delete', methods=['POST'])
@admin_required
def delete_subcategory_route(category, sub):
    category = unquote(category)
    sub = unquote(sub)
    if delete_subcategory(category, sub):
        flash('Subcategory deleted successfully', 'success')
    else:
        flash('Subcategory not found', 'error')
    return redirect(url_for('admin'))

# Hospital Management Routes
@app.route('/admin/hospitals/add', methods=['POST'])
@admin_required
def add_hospital():
    hospitals = get_hospitals()
    name = request.form.get('name', '').strip()
    zone = request.form.get('zone', '').strip()
    
    if not name:
        flash('Hospital name is required', 'error')
        return redirect(url_for('admin'))
    
    # Check if hospital already exists (case-insensitive)
    if any(h.get('name', '').lower() == name.lower() for h in hospitals):
        flash('Hospital already exists', 'error')
    else:
        hospitals.append({'name': name, 'zone': zone})
        # Sort hospitals by name (case-insensitive)
        hospitals.sort(key=lambda h: h.get('name', '').lower())
        save_hospitals(hospitals)
        flash('Hospital added successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/hospitals/<path:name>/edit', methods=['POST'])
@admin_required
def edit_hospital(name):
    name = unquote(name)
    hospitals = get_hospitals()
    new_name = request.form.get('new_name', '').strip()
    new_zone = request.form.get('new_zone', '').strip()
    
    if not new_name:
        flash('Hospital name is required', 'error')
        return redirect(url_for('admin'))
    
    hospital = next((h for h in hospitals if h.get('name') == name), None)
    if hospital:
        hospital['name'] = new_name
        hospital['zone'] = new_zone
        # Sort hospitals by name
        hospitals.sort(key=lambda h: h.get('name', '').lower())
        save_hospitals(hospitals)
        flash('Hospital updated successfully', 'success')
    else:
        flash('Hospital not found', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/hospitals/<path:name>/delete', methods=['POST'])
@admin_required
def delete_hospital(name):
    name = unquote(name)
    hospitals = get_hospitals()
    hospitals = [h for h in hospitals if h.get('name') != name]
    save_hospitals(hospitals)
    flash('Hospital deleted successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/hospitals/bulk_add', methods=['POST'])
@admin_required
def bulk_add_hospitals():
    hospitals = get_hospitals()
    hospitals_text = request.form.get('hospitals', '').strip()
    
    if not hospitals_text:
        flash('No hospitals provided', 'error')
        return redirect(url_for('admin'))
    
    # Parse the textarea input
    lines = hospitals_text.split('\n')
    added_count = 0
    skipped_count = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Split by comma, handling cases with or without zone
        parts = [p.strip() for p in line.split(',', 1)]
        name = parts[0]
        zone = parts[1] if len(parts) > 1 else ''
        
        if not name:
            continue
        
        # Check if hospital already exists (case-insensitive)
        if any(h.get('name', '').lower() == name.lower() for h in hospitals):
            skipped_count += 1
        else:
            hospitals.append({'name': name, 'zone': zone})
            added_count += 1
    
    if added_count > 0:
        # Sort hospitals by name (case-insensitive)
        hospitals.sort(key=lambda h: h.get('name', '').lower())
        save_hospitals(hospitals)
        flash(f'Successfully added {added_count} hospital(s)', 'success')
    
    if skipped_count > 0:
        flash(f'Skipped {skipped_count} duplicate hospital(s)', 'info')
    
    if added_count == 0 and skipped_count == 0:
        flash('No valid hospitals found in the input', 'error')
    
    return redirect(url_for('admin'))

# User Role Management Routes
@app.route('/admin/users/add', methods=['POST'])
@admin_required
def add_user_role():
    email = request.form.get('email', '').strip().lower()
    role = request.form.get('role', 'member')
    
    if not email:
        flash('Email is required', 'error')
        return redirect(url_for('admin'))
    
    user = get_user_by_email(email)
    if user:
        user['role'] = role
    else:
        user = {
            'email': email,
            'name': email.split('@')[0],
            'role': role
        }
    
    create_or_update_user(user)
    flash('User role updated successfully', 'success')
    return redirect(url_for('admin'))

# Team Member Management Routes
@app.route('/admin/team/add', methods=['POST'])
@admin_required
def add_team_member():
    email = request.form.get('email', '').strip().lower()
    user = get_user_by_email(email)
    
    if not user:
        flash('User not found. User must login first to be added to team.', 'error')
        return redirect(url_for('admin'))
    
    team_members = get_team_members()
    # Check if already in team
    if any(tm.get('email') == email for tm in team_members):
        flash('User already in team', 'info')
    else:
        team_members.append({
            'uid': user.get('id', ''),
            'name': user.get('name', email.split('@')[0]),
            'email': email
        })
        save_team_members(team_members)
        flash('Team member added successfully', 'success')
    
    return redirect(url_for('admin'))

@app.route('/admin/team/<uid>/delete', methods=['POST'])
@admin_required
def delete_team_member(uid):
    team_members = get_team_members()
    team_members = [tm for tm in team_members if tm.get('uid') != uid]
    save_team_members(team_members)
    flash('Team member removed successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/export/csv')
@login_required
def export_csv():
    issues = get_all_issues()
    
    # Create CSV in memory
    import io
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ISSUES_HEADERS)
    writer.writeheader()
    writer.writerows(issues)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=issues_export.csv'}
    )

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(debug=True, host='0.0.0.0', port=port)
