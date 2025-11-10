#!/bin/bash
#
# Set up blockchain infrastructure for CV2X testbed
#

set -e

echo "========================================"
echo "CV2X Testbed - Blockchain Setup"
echo "========================================"
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo "Please install Node.js (v18+ recommended):"
    echo "  https://nodejs.org/"
    exit 1
fi

echo "✓ Node.js version: $(node --version)"
echo "✓ npm version: $(npm --version)"
echo ""

# Install npm dependencies
echo "Installing npm dependencies..."
npm install

echo ""
echo "Compiling smart contracts..."
npx hardhat compile

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "To start local blockchain:"
echo "  npx hardhat node"
echo ""
echo "In another terminal, deploy contracts:"
echo "  npx hardhat run scripts/deploy.js --network localhost"
echo ""
echo "Or use the all-in-one command:"
echo "  ./scripts/start_testbed.sh"
echo ""
