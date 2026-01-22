#!/bin/bash

# README PDF Reader - Start Script

echo "Starting README PDF Reader..."

# Load configuration from config.yaml
CONFIG_FILE="config.yaml"
if [ -f "$CONFIG_FILE" ]; then
    echo "Loading configuration from $CONFIG_FILE..."

    # Parse YAML and export environment variables
    # OpenAI
    OPENAI_API_KEY=$(grep -A2 "^openai:" "$CONFIG_FILE" | grep "api_key:" | sed 's/.*api_key:[[:space:]]*"\?\([^"]*\)"\?.*/\1/' | tr -d ' ')
    OPENAI_API_BASE=$(grep -A2 "^openai:" "$CONFIG_FILE" | grep "api_base:" | sed 's/.*api_base:[[:space:]]*"\?\([^"]*\)"\?.*/\1/' | tr -d ' ')

    # Translation
    TRANSLATE_API_KEY=$(grep -A2 "^translate:" "$CONFIG_FILE" | grep "api_key:" | sed 's/.*api_key:[[:space:]]*"\?\([^"]*\)"\?.*/\1/' | tr -d ' ')
    TRANSLATE_API_BASE=$(grep -A2 "^translate:" "$CONFIG_FILE" | grep "api_base:" | sed 's/.*api_base:[[:space:]]*"\?\([^"]*\)"\?.*/\1/' | tr -d ' ')

    # Tavily
    TAVILY_API_KEY=$(grep -A2 "^tavily:" "$CONFIG_FILE" | grep "api_key:" | sed 's/.*api_key:[[:space:]]*"\?\([^"]*\)"\?.*/\1/' | tr -d ' ')

    # Export non-empty values
    [ -n "$OPENAI_API_KEY" ] && export OPENAI_API_KEY && echo "  - OPENAI_API_KEY loaded"
    [ -n "$OPENAI_API_BASE" ] && export OPENAI_API_BASE && echo "  - OPENAI_API_BASE loaded"
    [ -n "$TRANSLATE_API_KEY" ] && export TRANSLATE_API_KEY && echo "  - TRANSLATE_API_KEY loaded"
    [ -n "$TRANSLATE_API_BASE" ] && export TRANSLATE_API_BASE && echo "  - TRANSLATE_API_BASE loaded"
    [ -n "$TAVILY_API_KEY" ] && export TAVILY_API_KEY && echo "  - TAVILY_API_KEY loaded"
else
    echo "Warning: $CONFIG_FILE not found. Copy config_example.yaml to config.yaml and fill in your API keys."
fi

# Clean and create uploads directory
rm -rf backend/uploads
mkdir -p backend/uploads

# Start backend
echo "Starting backend server..."
cd backend
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
python app.py &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 2

# Start frontend
echo "Starting frontend server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "==================================="
echo "README PDF Reader is running!"
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:5000"
echo "==================================="
echo ""
echo "Press Ctrl+C to stop all servers"

# Handle Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

# Wait for processes
wait
