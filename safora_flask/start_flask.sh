#!/bin/bash

echo "Starting Flask Backend Server..."
echo ""
echo "Make sure you're in the safora_flask directory"
echo "Flask will run on http://0.0.0.0:5000"
echo ""
echo "For Android Emulator, use: http://10.0.2.2:5000"
echo "For iOS Simulator, use: http://localhost:5000"
echo "For real device, use your computer's IP (e.g., http://192.168.1.5:5000)"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

cd "$(dirname "$0")"
python app.py

