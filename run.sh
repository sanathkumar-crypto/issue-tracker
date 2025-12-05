#!/bin/bash
# Run script for Flask application with virtual environment

echo "Starting Issue Tracker Flask Application..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check for data directory
if [ ! -d "data" ]; then
    echo "Creating data directory..."
    mkdir -p data
fi

# Check if port 5000 is in use and kill existing process
if lsof -ti:5000 > /dev/null 2>&1; then
    echo "Port 5000 is in use. Stopping existing process..."
    pkill -f "python app.py" 2>/dev/null
    lsof -ti:5000 | xargs kill -9 2>/dev/null
    sleep 2
fi

# Run Flask application
echo ""
echo "Starting Flask server on http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""
python app.py
