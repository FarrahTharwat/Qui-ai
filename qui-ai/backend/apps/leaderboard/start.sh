#!/bin/bash

# Leaderboard Service Startup Script
echo "🚀 Starting Leaderboard Service on Port 8005..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "📝 Please create a .env file based on .env.example"
    echo "🔗 Copy .env.example to .env and fill in your configuration"
    exit 1
fi

# Check if Python dependencies are installed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate || source venv/Scripts/activate

echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if port 8005 is available
if lsof -Pi :8005 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Port 8005 is already in use!"
    echo "🔍 Process using port 8005:"
    lsof -Pi :8005 -sTCP:LISTEN
    echo "💡 Stop the process or change the port in .env"
    exit 1
fi

# Create logs directory
mkdir -p logs

echo "✅ Environment check complete!"
echo "🌐 Starting server on http://localhost:8005"
echo "📊 Health check: http://localhost:8005/health"
echo "📚 API docs: http://localhost:8005/docs"
echo ""

# Start the application
python main.py