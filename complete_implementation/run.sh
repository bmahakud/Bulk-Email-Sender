#!/bin/bash
# Quick start script for Outlook Bulk Mail Sender

echo "🚀 Starting Outlook Bulk Mail Sender..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found!"
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import PySide6" 2>/dev/null; then
    echo "⚠️  Dependencies not installed!"
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "✓ Dependencies installed"
    echo ""
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "Please create .env file with your Azure credentials"
    echo "See SETUP_GUIDE.md for instructions"
    echo ""
    exit 1
fi

# Run the application
echo "✓ Starting application..."
echo ""
python app.py
