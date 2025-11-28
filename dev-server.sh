#!/bin/bash

# ===========================================
# PhisGuard Development Server with Port Fallback
# ===========================================

echo "🚀 PhisGuard Development Server"
echo "==============================="

# Function to check if a port is available
check_port() {
    local port=$1
    if lsof -ti:$port >/dev/null 2>&1; then
        return 1  # Port is in use
    else
        return 0  # Port is free
    fi
}

# Find available ports
BACKEND_PORT=5000
EXTENSION_PORT=3002

echo "Checking port availability..."

# Find available backend port
for port in 5000 5001 5002 5003 8000 8001; do
    if check_port $port; then
        BACKEND_PORT=$port
        echo "✅ Backend will use port: $port"
        break
    fi
done

# Find available extension port  
for port in 3002 3001 3003 8080 8081; do
    if check_port $port; then
        EXTENSION_PORT=$port
        echo "✅ Extension will use port: $port"
        break
    fi
done

echo ""
echo "Starting services with fallback ports..."
echo "Backend: http://localhost:$BACKEND_PORT"
echo "Extension: http://localhost:$EXTENSION_PORT"
echo ""

# Kill any existing processes on these ports
echo "Cleaning up any existing processes..."
pkill -f "python.*app.py" 2>/dev/null || true
pkill -f "http-server.*dist" 2>/dev/null || true

# Wait a moment
sleep 2

echo "Starting development environment..."

# Start backend in background
echo "Starting Flask backend on port $BACKEND_PORT..."
export PYTHONPATH=/home/ayush/.local/lib/python3.12/site-packages:/usr/lib/python3/dist-packages
export PORT=$BACKEND_PORT
python3 app.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 5

# Check if backend started successfully
if curl -f -s http://localhost:$BACKEND_PORT/health >/dev/null 2>&1; then
    echo "✅ Backend started successfully on port $BACKEND_PORT"
else
    echo "❌ Backend failed to start on port $BACKEND_PORT"
    echo "Trying alternative ports..."
    # Kill the failed backend
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# Start extension server in background
echo "Starting extension server on port $EXTENSION_PORT..."
cd chrome-extension
npm run build:dev > /dev/null 2>&1
http-server dist -p $EXTENSION_PORT -c-1 --cors &
EXTENSION_PID=$!

# Wait for extension server to start
sleep 3

# Check if extension server started
if curl -f -s http://localhost:$EXTENSION_PORT >/dev/null 2>&1; then
    echo "✅ Extension server started successfully on port $EXTENSION_PORT"
else
    echo "❌ Extension server failed to start on port $EXTENSION_PORT"
    # Clean up
    kill $BACKEND_PID 2>/dev/null || true
    kill $EXTENSION_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "🎉 PhisGuard Development Environment Ready!"
echo "=========================================="
echo ""
echo "📱 Access Points:"
echo "  Backend API: http://localhost:$BACKEND_PORT"
echo "  Health Check: http://localhost:$BACKEND_PORT/health"
echo "  Extension Files: http://localhost:$EXTENSION_PORT"
echo ""
echo "🛠️  Management:"
echo "  Backend PID: $BACKEND_PID"
echo "  Extension PID: $EXTENSION_PID"
echo ""
echo "To stop services:"
echo "  kill $BACKEND_PID $EXTENSION_PID"
echo ""
echo "Press Ctrl+C to stop both services"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down PhisGuard development server..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $EXTENSION_PID 2>/dev/null || true
    echo "✅ Services stopped"
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM

# Wait for user to stop
wait $BACKEND_PID $EXTENSION_PID