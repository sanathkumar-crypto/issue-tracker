# Quick Start Guide - Running the Application

## Method 1: Using the Run Script (Easiest) ⭐

```bash
./run.sh
```

This script will:
- Create virtual environment if it doesn't exist
- Activate it automatically
- Install dependencies
- Start the Flask server

## Method 2: Manual Steps

### Step 1: Activate Virtual Environment
```bash
source venv/bin/activate
```

You should see `(venv)` at the beginning of your terminal prompt.

### Step 2: Run the Application
```bash
python app.py
```

### Step 3: Access the Application
Open your browser and go to:
```
http://localhost:5000
```

## Method 3: Using Python Directly (with venv)

```bash
venv/bin/python app.py
```

## What You'll See

When the app starts, you should see output like:
```
 * Serving Flask app 'app'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

## Stopping the Application

Press `Ctrl+C` in the terminal to stop the server.

## Troubleshooting

### "No module named 'flask'"
Make sure the virtual environment is activated:
```bash
source venv/bin/activate
```

### "Port 5000 already in use"
Either:
1. Stop the other application using port 5000
2. Or change the port in `app.py` (last line):
   ```python
   app.run(debug=True, host='0.0.0.0', port=5001)  # Change to 5001
   ```

### "Permission denied" for run.sh
Make it executable:
```bash
chmod +x run.sh
```

## Login

Once the app is running:
1. Go to http://localhost:5000
2. Enter your email (must be @cloudphysician.net)
3. Click "Sign In"

No password required - it's for internal use only.

