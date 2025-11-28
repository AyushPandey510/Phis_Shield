#!/bin/bash

# ===========================================
# PhisGuard Port Conflict Resolution Script
# ===========================================

echo "🔧 Resolving PhisGuard Port Conflicts"
echo "===================================="

# Function to kill processes on a port
kill_port() {
    local port=$1
    echo "Checking port $port..."
    
    # Try to find and kill processes using the port
    pid=$(lsof -ti:$port 2>/dev/null | head -1)
    
    if [ ! -z "$pid" ]; then
        echo "Found process $pid on port $port, killing..."
        kill -9 $pid 2>/dev/null || sudo kill -9 $pid 2>/dev/null
        echo "✅ Killed process on port $port"
    else
        echo "No process found on port $port"
    fi
    
    # Wait a moment for the port to be released
    sleep 2
}

echo "Step 1: Killing processes on conflicting ports..."

# Kill processes on ports 5000 and 3002
kill_port 5000
kill_port 3002

echo ""
echo "Step 2: Verifying ports are free..."

# Verify ports are free
if lsof -ti:5000 >/dev/null 2>&1; then
    echo "⚠️  Port 5000 is still in use"
else
    echo "✅ Port 5000 is free"
fi

if lsof -ti:3002 >/dev/null 2>&1; then
    echo "⚠️  Port 3002 is still in use"
else
    echo "✅ Port 3002 is free"
fi

echo ""
echo "Step 3: Alternative ports ready for use..."

# Suggest alternative ports
echo "If conflicts persist, you can use these alternative ports:"
echo "  Backend: 5001, 5002, 5003, 8000, 8001"
echo "  Extension: 3001, 3003, 8080, 8081"

echo ""
echo "🚀 Ready to start PhisGuard development server!"
echo ""
echo "Run: npm run dev"