#!/bin/bash

# Check if the virtual environment directory "venv" exists; if not, create it:
if [ ! -d "venv" ]; then
    echo "Creating virtual environment 'venv'..."
    python3 -m venv venv
    echo "Virtual environment 'venv' created."
else
    echo "Virtual environment 'venv' already exists."
fi

# Activate the virtual environment:
echo "Activating virtual environment 'venv'..."
source venv/bin/activate
echo "Virtual environment activated."

# Install pip requirements if requirements.txt exists:
if [ -f "requirements.txt" ]; then
    echo "Installing pip requirements from requirements.txt..."
    pip install -r requirements.txt
    echo "Pip requirements installed."
else
    echo "No requirements.txt found. Skipping pip install."
fi

# Run main.py
echo "Executing main.py..."
python main.py
