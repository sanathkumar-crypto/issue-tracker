import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def load_issue_tracker_secret_key():
    """
    Load configuration from ISSUE_TRACKER_SECRET_KEY JSON secret (for Cloud Run)
    or from local JSON file (for local development with python app.py)
    or fall back to individual environment variables
    """
    # First, try to load from environment variable (Cloud Run)
    secret_key = os.environ.get('ISSUE_TRACKER_SECRET_KEY', '')
    if secret_key:
        try:
            # Parse JSON secret from environment variable
            secret_data = json.loads(secret_key)
            print(f"DEBUG: Successfully parsed ISSUE_TRACKER_SECRET_KEY from environment variable")
            print(f"DEBUG: Found keys: {list(secret_data.keys())}")
            return {
                'SECRET_KEY': secret_data.get('SECRET_KEY', ''),
                'GOOGLE_CLIENT_ID': secret_data.get('GOOGLE_CLIENT_ID', ''),
                'GOOGLE_CLIENT_SECRET': secret_data.get('GOOGLE_CLIENT_SECRET', ''),
                'GOOGLE_REDIRECT_URI': secret_data.get('GOOGLE_REDIRECT_URI', ''),
                'ALLOWED_EMAIL_DOMAIN': secret_data.get('ALLOWED_EMAIL_DOMAIN', 'cloudphysician.net')
            }
        except (json.JSONDecodeError, TypeError) as e:
            # If JSON parsing fails, fall back to individual env vars
            print(f"ERROR: Failed to parse ISSUE_TRACKER_SECRET_KEY as JSON: {e}")
            print(f"DEBUG: ISSUE_TRACKER_SECRET_KEY value (first 100 chars): {secret_key[:100]}")
            return None
    
    # For local development, try to load from local JSON file
    # Only do this when NOT in Cloud Run (when K_SERVICE is not set)
    if not os.environ.get('K_SERVICE'):
        local_json_file = os.path.join(os.path.dirname(__file__), 'issue_tracker_secret_key.json')
        if os.path.exists(local_json_file):
            try:
                with open(local_json_file, 'r', encoding='utf-8') as f:
                    secret_data = json.load(f)
                    print(f"DEBUG: Successfully loaded ISSUE_TRACKER_SECRET_KEY from local JSON file: {local_json_file}")
                    print(f"DEBUG: Found keys: {list(secret_data.keys())}")
                    return {
                        'SECRET_KEY': secret_data.get('SECRET_KEY', ''),
                        'GOOGLE_CLIENT_ID': secret_data.get('GOOGLE_CLIENT_ID', ''),
                        'GOOGLE_CLIENT_SECRET': secret_data.get('GOOGLE_CLIENT_SECRET', ''),
                        'GOOGLE_REDIRECT_URI': secret_data.get('GOOGLE_REDIRECT_URI', ''),
                        'ALLOWED_EMAIL_DOMAIN': secret_data.get('ALLOWED_EMAIL_DOMAIN', 'cloudphysician.net')
                    }
            except (json.JSONDecodeError, IOError) as e:
                print(f"WARNING: Failed to load local JSON file {local_json_file}: {e}")
                print("DEBUG: Falling back to individual env vars")
    
    print("DEBUG: ISSUE_TRACKER_SECRET_KEY not found in environment or local file, using individual env vars")
    return None

# Try to load from JSON secret first, then fall back to individual env vars
_secret_config = load_issue_tracker_secret_key()

class Config:
    # Load from JSON secret if available, otherwise from individual env vars
    if _secret_config:
        SECRET_KEY = _secret_config['SECRET_KEY'] or 'dev-secret-key-change-in-production'
        GOOGLE_CLIENT_ID = _secret_config['GOOGLE_CLIENT_ID'] or ''
        GOOGLE_CLIENT_SECRET = _secret_config['GOOGLE_CLIENT_SECRET'] or ''
        # Use the redirect URI from secret, or try to detect Cloud Run URL
        default_redirect = os.environ.get('GOOGLE_REDIRECT_URI', '')
        if not default_redirect and os.environ.get('K_SERVICE'):
            # We're in Cloud Run, construct URL from environment
            service_url = os.environ.get('K_SERVICE_URL', '')
            if service_url:
                default_redirect = f"{service_url}/login/callback"
        GOOGLE_REDIRECT_URI = _secret_config['GOOGLE_REDIRECT_URI'] or default_redirect or 'http://localhost:5001/login/callback'
        ALLOWED_EMAIL_DOMAIN = _secret_config.get('ALLOWED_EMAIL_DOMAIN', 'cloudphysician.net')
        print(f"DEBUG: Loaded config from ISSUE_TRACKER_SECRET_KEY - Client ID present: {bool(GOOGLE_CLIENT_ID)}, Redirect URI: {GOOGLE_REDIRECT_URI}")
    else:
        SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
        GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
        GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
        GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5001/login/callback')
        ALLOWED_EMAIL_DOMAIN = os.environ.get('ALLOWED_EMAIL_DOMAIN', 'cloudphysician.net')
        print(f"DEBUG: Loaded config from individual env vars - Client ID present: {bool(GOOGLE_CLIENT_ID)}")
    
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'session:'
    # Ensure session directory exists
    SESSION_FILE_DIR = os.path.join(os.path.dirname(__file__), 'flask_session')
    SESSION_FILE_THRESHOLD = 500

