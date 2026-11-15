#!/bin/bash

echo "Starting MULTYVERS..."

# Activate virtual environment
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Start Flask application
python run.py