#!/bin/bash

# ===========================================
# Simple PhisGuard Development Server
# ===========================================

echo "🚀 PhisGuard Development Server"
echo "==============================="

# Use alternative ports to avoid conflicts
BACKEND_PORT=5001
EXTENSION_PORT=3001

echo "Using alternative ports to avoid conflicts:"
echo "  Backend: http://localhost:$BACKEND_PORT"
echo "  Extension: http://localhost:$EXTENSION_PORT"
echo ""

# Clean up any existing processes
echo "Cleaning up existing processes..."
pkill -f "python.*app.py" 2>/dev/null || true
pkill -f "http-server" 2>/dev/null || true
sleep 2

echo "Starting services..."
echo ""

# Start backend
echo "🔥 Starting Flask backend on port $BACKEND_PORT..."
export PYTHONPATH=/home/ayush/.local/lib/python3.12/site-packages:/usr/lib/python3/dist-packages
export PORT=$BACKEND_PORT

# Start backend in background and capture PID
python3 app.py > backend.log 2>&1 &
BACKEND_PID=$!

echo "Backend started with PID: $BACKEND_PID"

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
for i in {1..10}; do
    if curl -f -s http://localhost:$BACKEND_PORT/health >/dev/null 2>&1; then
        echo "✅ Backend is ready!"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Backend failed to start. Check backend.log"
        exit 1
    fi
    echo "Waiting... ($i/10)"
    sleep 2
done

# Build and start extension
echo ""
echo "🌐 Starting extension development server on port $EXTENSION_PORT..."

# Build the extension
cd chrome-extension
npm run build:dev > ../extension-build.log 2>&1

# Start extension server
http-server dist -p $EXTENSION_PORT -c-1 --cors > ../extension-server.log 2>&1 &
EXTENSION_PID=$!

echo "Extension server started with PID: $EXTENSION_PID"

# Wait for extension server
sleep 3

if curl -f -s http://localhost:$EXTENSION_PORT >/dev/null 2>&1; then
    echo "✅ Extension server is ready!"
else
    echo "⚠️  Extension server may still be starting..."
fi

echo ""
echo "🎉 PhisGuard Development Environment Ready!"
echo "=========================================="
echo ""
echo "📱 Access Points:"
echo "  🔥 Backend API: http://localhost:$BACKEND_PORT"
echo "  ❤️  Health Check: http://localhost:$BACKEND_PORT/health"
echo "  🌐 Extension Files: http://localhost:$EXTENSION_PORT"
echo ""
echo "🔗 Quick Test URLs:"
echo "  Backend Health: curl http://localhost:$BACKEND_PORT/health"
echo "  URL Check Test: curl -X POST http://localhost:$BACKEND_PORT/check-url -H 'Content-Type: application/json' -d '{\"url\":\"https://google.com\"}'"
echo ""
echo "📁 Log Files:"
echo "  Backend: backend.log"
echo "  Extension Build: extension-build.log"
echo "  Extension Server: extension-server.log"
echo ""
echo "🛠️  To stop services:"
echo "  kill $BACKEND_PID $EXTENSION_PID"
echo ""
echo "Press Ctrl+C to stop both services"

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down PhisGuard development server..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $EXTENSION_PID 2>/dev/null || true
    echo "✅ Services stopped"
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Wait for user to stop
echo "Services running... (Press Ctrl+C to stop)"
wait $BACKEND_PID $EXTENSION_PID