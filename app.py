from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory
from flask_cors import CORS
from flask_session import Session
from functools import wraps
import os
import csv
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from werkzeug.utils import secure_filename
from urllib.parse import unquote, urlparse, parse_qs, urlencode
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
from config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Allow HTTP for localhost (required for local development)
# WARNING: Only use this for local development, never in production!
# In Cloud Run, we use HTTPS, so explicitly unset OAUTHLIB_INSECURE_TRANSPORT
if os.environ.get('K_SERVICE'):
    # We're in Cloud Run - ensure HTTPS is enforced
    os.environ.pop('OAUTHLIB_INSECURE_TRANSPORT', None)
elif os.environ.get('FLASK_ENV') == 'development' or 'localhost' in os.environ.get('GOOGLE_REDIRECT_URI', ''):
    # Local development - allow HTTP
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    print("DEBUG: OAUTHLIB_INSECURE_TRANSPORT set to 1 for localhost development")

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config.from_object(Config)
# Configure session cookie settings for OAuth flow
# In Cloud Run, use secure cookies (HTTPS)
is_cloud_run = bool(os.environ.get('K_SERVICE'))
app.config['SESSION_COOKIE_SECURE'] = is_cloud_run  # True in Cloud Run (HTTPS), False for localhost
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Log configuration on startup
logger.info(f"Running in Cloud Run: {is_cloud_run}")
logger.info(f"OAuth Client ID configured: {bool(app.config.get('GOOGLE_CLIENT_ID'))}")
logger.info(f"OAuth Redirect URI: {app.config.get('GOOGLE_REDIRECT_URI', 'Not set')}")

# Ensure session directory exists
session_dir = app.config.get('SESSION_FILE_DIR', 'flask_session')
os.makedirs(session_dir, exist_ok=True)
Session(app)

CORS(app)

# OAuth 2.0 scopes
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

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

ALLOWED_DOMAIN = app.config.get('ALLOWED_EMAIL_DOMAIN', 'cloudphysician.net')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}

# Category storage functions
def load_categories():
    """Load categories from JSON file"""
    if CATEGORIES_JSON.exists():
        try:
            with open(CATEGORIES_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

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
def get_hospitals():
    """Get hospitals list from CSV"""
    return read_csv(HOSPITALS_CSV, ['name', 'zone'])

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
    """Initiate Google OAuth login or handle email login fallback."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    # Handle POST request (fallback email login when OAuth not configured)
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Email is required', 'error')
            return render_template('login.html', oauth_configured=False)
        
        # Check email domain
        if not email.endswith(f'@{ALLOWED_DOMAIN}'):
            flash(f'Only @{ALLOWED_DOMAIN} email addresses are allowed', 'error')
            return render_template('login.html', oauth_configured=False)
        
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
    
    # For local development, always use localhost redirect URI
    # Check if we're running locally (not in Cloud Run)
    is_local = not os.environ.get('K_SERVICE')
    if is_local:
        # Use localhost with the port the app is running on
        port = int(os.environ.get('PORT', 5001))
        redirect_uri = f'http://localhost:{port}/login/callback'
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    else:
        # In Cloud Run, use the configured redirect URI
        redirect_uri = app.config.get('GOOGLE_REDIRECT_URI', 'http://localhost:5001/login/callback').strip()
        if 'localhost' in redirect_uri or '127.0.0.1' in redirect_uri:
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    
    # Check if we have OAuth credentials configured
    client_id = app.config.get('GOOGLE_CLIENT_ID', '').strip()
    client_secret = app.config.get('GOOGLE_CLIENT_SECRET', '').strip()
    
    # Debug logging
    logger.info(f"Client ID present: {bool(client_id)}")
    logger.info(f"Redirect URI: {redirect_uri}")
    
    if not client_id or not client_secret:
        # For development, allow bypass with email login
        return render_template('login.html', oauth_configured=False)
    
    try:
        # Validate client ID format
        if not client_id.endswith('.apps.googleusercontent.com'):
            raise ValueError(f"Invalid Client ID format. Should end with .apps.googleusercontent.com")
        
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }
        
        logger.info(f"Creating OAuth flow with redirect URI: {redirect_uri}")
        flow = Flow.from_client_config(client_config, scopes=SCOPES)
        flow.redirect_uri = redirect_uri
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        session['oauth_state'] = state
        logger.info(f"OAuth flow created successfully, redirecting to: {authorization_url[:100]}...")
        return redirect(authorization_url)
    except ValueError as e:
        error_msg = f"Configuration error: {str(e)}"
        logger.error(error_msg)
        return render_template('login.html', 
                             oauth_configured=False, 
                             oauth_error=error_msg)
    except Exception as e:
        # If OAuth fails, show error and allow dev bypass
        error_msg = f"OAuth error: {str(e)}"
        logger.error(error_msg)
        import traceback
        traceback.print_exc()
        return render_template('login.html', 
                             oauth_configured=False, 
                             oauth_error=error_msg)

@app.route('/login/callback')
def login_callback():
    """Handle OAuth callback."""
    # For local development, always use localhost redirect URI
    # Check if we're running locally (not in Cloud Run)
    is_local = not os.environ.get('K_SERVICE')
    if is_local:
        # Use localhost with the port the app is running on
        port = int(os.environ.get('PORT', 5001))
        redirect_uri = f'http://localhost:{port}/login/callback'
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    else:
        # In Cloud Run, use the configured redirect URI
        redirect_uri = app.config.get('GOOGLE_REDIRECT_URI', 'http://localhost:5001/login/callback').strip()
        if 'localhost' in redirect_uri or '127.0.0.1' in redirect_uri:
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    
    if 'error' in request.args:
        error = request.args.get('error')
        error_description = request.args.get('error_description', '')
        logger.error(f"OAuth error from Google: {error}")
        logger.error(f"Error description: {error_description}")
        return render_template('login.html', 
                             oauth_configured=False, 
                             oauth_error=f"OAuth Error: {error}. {error_description}")
    
    state = session.get('oauth_state')
    received_state = request.args.get('state')
    
    # Debug session info
    logger.info(f"Session ID: {session.get('_id', 'N/A')}")
    logger.info(f"Session keys: {list(session.keys())}")
    logger.info(f"OAuth state in session: {state}")
    logger.info(f"Received state from callback: {received_state}")
    
    client_id = app.config.get('GOOGLE_CLIENT_ID', '').strip()
    client_secret = app.config.get('GOOGLE_CLIENT_SECRET', '').strip()
    
    if not client_id or not client_secret:
        return "OAuth not configured", 500
    
    # In Cloud Run, ensure OAUTHLIB_INSECURE_TRANSPORT is NOT set
    if os.environ.get('K_SERVICE'):
        os.environ.pop('OAUTHLIB_INSECURE_TRANSPORT', None)
        # Ensure redirect_uri is HTTPS
        if redirect_uri and not redirect_uri.startswith('https://'):
            # Try to get from Cloud Run environment
            service_url = os.environ.get('K_SERVICE_URL', '')
            if service_url:
                redirect_uri = f"{service_url}/login/callback"
            else:
                # Fallback: construct from request
                redirect_uri = request.url.replace('http://', 'https://', 1).split('?')[0]
    
    # Validate state - if session state exists, it must match. Otherwise, proceed with received state
    if state and state != received_state:
        logger.warning(f"State mismatch. Expected: {state}, Received: {received_state}")
        return "Invalid state parameter", 400
    elif not state:
        # State was lost from session - this happens in development with Flask-Session issues
        # We can still proceed if we have a valid code and received_state
        logger.warning(f"WARNING - State lost from session but received: {received_state}")
        if not received_state or not request.args.get('code'):
            return "Session expired. Please try again.", 400
    
    try:
        logger.info(f"Creating OAuth flow for callback with redirect URI: {redirect_uri}")
        logger.info(f"OAUTHLIB_INSECURE_TRANSPORT: {os.environ.get('OAUTHLIB_INSECURE_TRANSPORT', 'NOT SET')}")
        logger.info(f"Is Cloud Run: {bool(os.environ.get('K_SERVICE'))}")
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }
        
        # Create flow without state - we'll validate it separately
        # The Flow doesn't require state for token exchange, only for validation
        flow = Flow.from_client_config(client_config, scopes=SCOPES)
        flow.redirect_uri = redirect_uri
        
        # In Cloud Run, ensure we use HTTPS for the callback URL
        # request.url might be HTTP internally, but we need HTTPS for OAuth
        callback_url = request.url
        if os.environ.get('K_SERVICE'):
            # We're in Cloud Run - MUST use HTTPS
            # Ensure OAUTHLIB_INSECURE_TRANSPORT is not set
            os.environ.pop('OAUTHLIB_INSECURE_TRANSPORT', None)
            
            # Construct proper HTTPS URL
            if redirect_uri.startswith('https://'):
                # Use the redirect_uri as base and append query parameters
                parsed_request = urlparse(request.url)
                query_params = parse_qs(parsed_request.query)
                # Build the callback URL using the configured redirect_uri
                callback_url = f"{redirect_uri}?{urlencode(query_params, doseq=True)}"
            elif callback_url.startswith('http://'):
                # Fallback: replace http with https
                callback_url = callback_url.replace('http://', 'https://', 1)
            
            # Double-check that callback_url is HTTPS
            if not callback_url.startswith('https://'):
                raise ValueError(f"Callback URL must be HTTPS in Cloud Run, got: {callback_url[:100]}")
        else:
            # Local development - use the request URL as-is (should be localhost)
            callback_url = request.url
        
        logger.info(f"Fetching token with URL: {callback_url[:200]}...")
        logger.info(f"Callback URL is HTTPS: {callback_url.startswith('https://')}")
        flow.fetch_token(authorization_response=callback_url)
        logger.info("Token fetched successfully")
        
        credentials = flow.credentials
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Get user info
        logger.info("Building OAuth2 service to get user info")
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        logger.info(f"User info retrieved: {user_info.get('email', 'N/A')}")
        
        email = user_info.get('email', '').lower()
        if not email.endswith(f'@{ALLOWED_DOMAIN}'):
            session.clear()
            return f"Access denied. Only @{ALLOWED_DOMAIN} email addresses are allowed.", 403
        
        # Get or create user
        user = get_user_by_email(email)
        if not user:
            # Determine role based on hardcoded admin list
            role = 'admin' if is_admin(email) else 'member'
            user = create_or_update_user({
                'email': email,
                'name': user_info.get('name', email.split('@')[0]),
                'role': role
            })
        else:
            # Update role if user is in admin list
            if is_admin(email):
                user['role'] = 'admin'
                create_or_update_user(user)
            # Update name if available from OAuth
            if user_info.get('name'):
                user['name'] = user_info.get('name')
                create_or_update_user(user)
        
        # Set session
        session['user_id'] = user['id']
        session['user_email'] = email
        session['user_name'] = user.get('name', user_info.get('name', email.split('@')[0]))
        session['user_role'] = user.get('role', 'member')
        session.pop('oauth_state', None)
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        error_msg = f"OAuth callback error: {str(e)}"
        logger.error(error_msg)
        import traceback
        traceback.print_exc()
        return render_template('login.html', 
                             oauth_configured=False, 
                             oauth_error=error_msg)

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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    app.run(debug=True, host='0.0.0.0', port=port)
