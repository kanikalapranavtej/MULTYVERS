#!/bin/bash

echo "Setting up MULTYVERS..."

# Create virtual environment if it does not exist
if [ ! -d "venv" ]; then
    python -m venv venv
fi

# Activate virtual environment
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Install project requirements
pip install -r requirements.txt

echo "MULTYVERS setup completed!"