#!/bin/bash
# ==============================================================================
# AgriSense — Smart Agriculture & Environmental Monitoring System
# macOS / Linux Unified Startup Launcher
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=================================================================="
echo "  🌱 Starting AgriSense IoT & Agro-Environmental Platform"
echo "  Tagline: Intelligent Agriculture. Sustainable Environment."
echo "=================================================================="

# 1. Check Python Virtual Environment
if [ ! -d ".venv" ]; then
    echo "[1/4] Creating Python virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
else
    echo "[1/4] Python virtual environment ready."
fi

# 2. Check Database Initialization
if [ ! -f "backend/agrisense.db" ]; then
    echo "[2/4] Initializing SQLite database and default seed telemetry..."
    PYTHONPATH=backend .venv/bin/python backend/database.py
else
    echo "[2/4] Database found and ready."
fi

# 3. Check Frontend Dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "[3/4] Installing frontend npm dependencies..."
    cd frontend && npm install && cd ..
else
    echo "[3/4] Frontend dependencies ready."
fi

# 4. Start Servers
echo "[4/4] Launching AgriSense Backend (Port 5001) & Frontend (Port 3000)..."

# Trap to kill both background processes on Ctrl+C
cleanup() {
    echo ""
    echo "Shutting down AgriSense services..."
    kill $(jobs -p) 2>/dev/null || true
    echo "Services stopped cleanly."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Start Backend
PYTHONPATH=backend .venv/bin/python backend/app.py &
BACKEND_PID=$!

# Wait 2 seconds for backend to start
sleep 2

# Start Frontend
cd frontend
npm run dev -- --host 0.0.0.0 --port 3000 &
FRONTEND_PID=$!
cd ..

echo ""
echo "=================================================================="
echo "  🚀 AgriSense is LIVE and running locally!"
echo "  🌐 Web Dashboard: http://localhost:3000"
echo "  📡 Telemetry API: http://localhost:5001/api"
echo "  👤 Default Admin: admin  |  Password: Admin@123"
echo "  Press Ctrl+C to stop all servers."
echo "=================================================================="
echo ""

# Wait for both processes
wait

