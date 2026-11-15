#!/bin/bash

echo "Running MULTYVERS tests..."

# Activate virtual environment
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Run all tests
python -m pytest -q

echo "Testing completed!"