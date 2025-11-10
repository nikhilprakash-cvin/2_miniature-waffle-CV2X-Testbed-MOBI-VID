#!/bin/bash
#
# CV2X Testbed Setup Script
#

set -e

echo "========================================"
echo "CV2X Testbed Setup"
echo "========================================"
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "To activate the environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run a basic V2V scenario:"
echo "  python scenarios/basic_v2v_scenario.py"
echo ""
echo "For help:"
echo "  python scenarios/basic_v2v_scenario.py --help"
echo ""
