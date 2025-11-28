#!/bin/bash

# ===========================================
# PhisGuard - One Command Setup
# ===========================================

echo "🛡️  PhisGuard - Complete Development Setup"
echo "==========================================="
echo ""

# Make sure we're in the right directory
if [ ! -f "app.py" ] || [ ! -f "package.json" ]; then
    echo "❌ Please run this script from the PhisGuard project root directory"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down PhisGuard..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $EXTENSION_PID 2>/dev/null || true
    echo "✅ All services stopped"
    exit 0
}

# Set trap for cleanup
trap cleanup INT TERM

echo "🔨 Step 1: Building Chrome extension..."
npm run build:dev

if [ $? -ne 0 ]; then
    echo "❌ Extension build failed"
    exit 1
fi

echo "✅ Extension built successfully"
echo ""

echo "🚀 Step 2: Starting Flask backend..."

# Use alternative ports to avoid conflicts
BACKEND_PORT=5001
EXTENSION_PORT=3002

export PYTHONPATH=/home/ayush/.local/lib/python3.12/site-packages:/usr/lib/python3/dist-packages
export PORT=$BACKEND_PORT

# Start backend with alternative port
PORT=$BACKEND_PORT python3 app.py &
BACKEND_PID=$!

echo "Backend started on port $BACKEND_PORT (PID: $BACKEND_PID)"
echo "⏳ Waiting for backend to be ready..."

# Wait for backend to be ready
i=1
while [ $i -le 10 ]; do
    if curl -f -s http://localhost:$BACKEND_PORT/health >/dev/null 2>&1; then
        echo "✅ Backend is ready!"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Backend failed to start. Check app.py"
        exit 1
    fi
    echo "  Waiting... ($i/10)"
    sleep 2
    i=$((i + 1))
done

echo ""
echo "🌐 Step 3: Starting extension file server..."

# Start extension server with alternative port
npx http-server chrome-extension/dist -p $EXTENSION_PORT -c-1 --cors &
EXTENSION_PID=$!

echo "Extension server started on port $EXTENSION_PORT (PID: $EXTENSION_PID)"
echo ""

# Final status
echo "🎉 PhisGuard is ready!"
echo "========================"
echo ""
echo "📱 Quick Access:"
echo "  🔥 Backend API: http://localhost:$BACKEND_PORT"
echo "  ❤️  Health Check: http://localhost:$BACKEND_PORT/health"
echo "  📊 Dashboard: http://localhost:$BACKEND_PORT/dashboard"
echo "  📁 Extension Files: http://localhost:$EXTENSION_PORT"
echo ""
echo "🔧 To Install Chrome Extension:"
echo "  1. Open chrome://extensions/"
echo "  2. Enable 'Developer mode'"
echo "  3. Click 'Load unpacked'"
echo "  4. Select: chrome-extension/dist"
echo ""
echo "🧪 Test Commands:"
echo "  curl http://localhost:$BACKEND_PORT/health"
echo "  # Test extension popup with any URL"
echo ""
echo "Press Ctrl+C to stop everything"
echo "================================"
echo ""

# Keep script running
wait $BACKEND_PID $EXTENSION_PID