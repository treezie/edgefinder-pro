#!/bin/bash
# EdgeFinder Pro Startup Script

# Navigate to the correct directory
cd "$(dirname "$0")"

# Run the Uvicorn server
echo "Starting EdgeFinder Pro..."
python3 -m uvicorn api.main:app --reload --port 8000 --host 127.0.0.1
