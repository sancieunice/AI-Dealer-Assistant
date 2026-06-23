#!/bin/bash

echo "========================================"
echo "VIKMO Dealer Assistant - Start Script"
echo "========================================"
echo ""

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install Node.js first."
    exit 1
fi

# Check if python is installed
if ! command -v python &> /dev/null; then
    echo "❌ Python is not installed. Please install Python first."
    exit 1
fi

echo "Starting backend server..."
python server.py &
BACKEND_PID=$!

echo "Backend server started (PID: $BACKEND_PID)"
echo ""
echo "Waiting 3 seconds for backend to initialize..."
sleep 3

echo ""
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "✅ Services started successfully!"
echo "========================================"
echo "Backend: http://localhost:5000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Process IDs:"
echo "Backend: $BACKEND_PID"
echo "Frontend: $FRONTEND_PID"
echo ""
echo "To stop services, press Ctrl+C or run:"
echo "kill $BACKEND_PID $FRONTEND_PID"
echo "========================================"

# Keep the script running
wait
