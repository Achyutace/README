#!/bin/bash

# Moonlight PDF Reader - Start Script

echo "Starting Moonlight PDF Reader..."

# Start backend
echo "Starting backend server..."
cd backend
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt -q
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
echo "Moonlight PDF Reader is running!"
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:5000"
echo "==================================="
echo ""
echo "Press Ctrl+C to stop all servers"

# Handle Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

# Wait for processes
wait
