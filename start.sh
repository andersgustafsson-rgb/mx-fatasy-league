#!/bin/bash
# MX Fantasy League - Startup Script

echo "🚀 Starting MX Fantasy League..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp env.example .env
    echo "📝 Please edit .env file with your configuration before running again."
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Create necessary directories
mkdir -p instance
mkdir -p static/uploads/leagues
mkdir -p static/images
mkdir -p static/sfx
mkdir -p static/brand_logos
mkdir -p data
mkdir -p backups

# Set permissions
chmod 755 static/uploads
chmod 755 static/uploads/leagues

# Check if running in production
if [ "$FLASK_ENV" = "production" ]; then
    echo "🏭 Running in production mode..."
    
    # Install dependencies
    pip install -r requirements.txt
    
    # Run with Gunicorn
    gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
else
    echo "🔧 Running in development mode..."
    
    # Install dependencies
    pip install -r requirements.txt
    
    # Run with Flask development server
    python app.py
fi
