#!/bin/bash
#
# Start CV2X testbed with blockchain backend
#

set -e

echo "========================================"
echo "Starting CV2X Testbed"
echo "========================================"
echo ""

# Check if Hardhat node is already running
if lsof -Pi :8545 -sTCP:LISTEN -t >/dev/null ; then
    echo "✓ Blockchain node already running on port 8545"
else
    echo "Starting Hardhat blockchain node..."
    npx hardhat node > hardhat.log 2>&1 &
    HARDHAT_PID=$!
    echo "✓ Hardhat node started (PID: $HARDHAT_PID)"

    # Wait for node to be ready
    echo "Waiting for node to be ready..."
    sleep 3
fi

# Deploy contracts
echo ""
echo "Deploying ERC-1056 Registry contract..."
npx hardhat run scripts/deploy.js --network localhost

# Check deployment
if [ -f "deployments/localhost.json" ]; then
    CONTRACT_ADDRESS=$(python3 -c "import json; print(json.load(open('deployments/localhost.json'))['contractAddress'])")
    echo ""
    echo "✅ Contract deployed at: $CONTRACT_ADDRESS"
else
    echo "❌ Deployment failed"
    exit 1
fi

echo ""
echo "========================================"
echo "Testbed Ready!"
echo "========================================"
echo ""
echo "Contract Address: $CONTRACT_ADDRESS"
echo ""
echo "Run tests:"
echo "  python scripts/test_identity_comparison.py"
echo ""
echo "Run simulation:"
echo "  python scenarios/basic_v2v_scenario.py"
echo ""
echo "To stop:"
echo "  kill $HARDHAT_PID"
echo "  (or press Ctrl+C if node is in foreground)"
echo ""
