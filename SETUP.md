# Setup Instructions

## Quick Start

### Option 1: Using the run script (Recommended)
```bash
./run.sh
```

### Option 2: Manual setup

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   ```

2. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

## Virtual Environment Notes

This project uses a Python virtual environment to avoid conflicts with system Python packages.

### Activating the virtual environment:
```bash
source venv/bin/activate
```

### Deactivating the virtual environment:
```bash
deactivate
```

### If you see "externally-managed-environment" error:
This means you're trying to install packages system-wide. Always use the virtual environment:
1. Create venv: `python3 -m venv venv`
2. Activate it: `source venv/bin/activate`
3. Then install: `pip install -r requirements.txt`

## Troubleshooting

### Python version
Make sure you have Python 3.8 or higher:
```bash
python3 --version
```

### Virtual environment not found
If `venv` directory doesn't exist, create it:
```bash
python3 -m venv venv
```

### Permission errors
Make sure you have write permissions in the project directory.

## Running the Application

After setup, the application will be available at:
- **URL:** http://localhost:5000
- **Port:** 5000 (configurable in app.py)

## Data Storage

The application creates a `data/` directory automatically on first run to store CSV files.

