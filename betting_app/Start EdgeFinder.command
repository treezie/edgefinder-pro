#\!/bin/bash
# EdgeFinder Pro — Local Dev Server Launcher
cd "$(dirname "$0")"
echo "============================================"
echo "  EdgeFinder Pro — Starting Local Server"
echo "============================================"
echo ""
echo "Checking dependencies..."
pip3 install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt --quiet 2>/dev/null
echo "Dependencies OK."
echo ""
echo "Starting server at http://127.0.0.1:8000"
echo "Open Safari and go to: http://127.0.0.1:8000"
echo ""
echo "Press Ctrl+C to stop the server."
echo "--------------------------------------------"
python3 -m uvicorn api.main:app --reload --port 8000 --host 127.0.0.1
