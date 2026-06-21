# Quickstart Guide - 5 Minutes to Running

**Get the thesis implementation up and running in under 5 minutes**

---

## ⏱️ Time Estimate

- **Prerequisites**: 2 minutes (if not installed)
- **Installation**: 1 minute
- **First Example**: 2 minutes
- **Total**: ~5 minutes

---

## 📋 Prerequisites

### Required Software

**Node.js** (for smart contracts):
```bash
# Check if installed
node --version  # Need v18+
npm --version   # Need v9+

# Install if needed (Ubuntu/Debian)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

**Python** (for W3C layer):
```bash
# Check if installed  
python3 --version  # Need v3.9+
pip3 --version

# Usually pre-installed on Linux
```

**Git**:
```bash
git --version  # Any recent version
```

---

## 🚀 Installation

### Step 1: Clone Repository (30 seconds)

```bash
git clone https://github.com/nikhilprakash-cvin/2_miniature-waffle-CV2X-Testbed-MOBI-VID.git
cd 2_miniature-waffle-CV2X-Testbed-MOBI-VID
```

### Step 2: Install Blockchain Dependencies (30 seconds)

```bash
cd 1_blockchain-identity
npm install
```

**Output you should see**:
```
added 234 packages in 25s
```

### Step 3: Install Python Dependencies (20 seconds)

```bash
cd ../2_w3c-ssi-layer
pip3 install -r requirements.txt
```

**Note**: If you get cryptography errors, it's okay - the DID resolver will still work.

---

## ✅ Verify Installation

### Test 1: Smart Contracts (10 seconds)

```bash
cd ../1_blockchain-identity
npx hardhat test test/ERC1056/EthereumDIDRegistry.test.js
```

**Expected output**:
```
  EthereumDIDRegistry
    ✓ Should deploy correctly
    ✓ Should set attributes
    ✓ Should add delegates
    ... (more tests)

  18 passing (2s)
```

### Test 2: DID Resolver (5 seconds)

```bash
cd ../2_w3c-ssi-layer/did-resolution
python3 did_resolver.py did:ethr:0x1:0x1234567890abcdef1234567890abcdef12345678
```

**Expected output**:
```json
{
  "didDocument": {
    "@context": ["https://www.w3.org/ns/did/v1"],
    "id": "did:ethr:0x1:0x1234567890abcdef1234567890abcdef12345678",
    "verificationMethod": [{...}],
    "authentication": [...]
  }
}
```

---

## 🎯 First Example: Create Vehicle DID

### Example 1: Using ERC-1056 (1 minute)

Create a file `create_vehicle_did.js` in `1_blockchain-identity/`:

```javascript
const { ethers } = require("hardhat");

async function main() {
  // Deploy registry
  console.log("Deploying ERC-1056 registry...");
  const Registry = await ethers.getContractFactory("EthereumDIDRegistry");
  const registry = await Registry.deploy();
  await registry.waitForDeployment();
  
  console.log("✅ Registry deployed at:", await registry.getAddress());

  // Create vehicle DID
  const [manufacturer] = await ethers.getSigners();
  const vehicleAddress = "0x1234567890abcdef1234567890abcdef12345678";
  
  // Set VIN hash as attribute
  const vinHash = ethers.keccak256(ethers.toUtf8Bytes("5YJ3E1EA0PF123456"));
  
  console.log("\nCreating vehicle DID...");
  const tx = await registry.setAttribute(
    vehicleAddress,
    ethers.toUtf8Bytes("VIN_HASH"),
    vinHash,
    86400  // Valid for 1 day
  );
  await tx.wait();
  
  console.log("✅ Vehicle DID created: did:ethr:31337:" + vehicleAddress);
  console.log("   VIN Hash:", vinHash);
  console.log("   Gas used:", (await tx.wait()).gasUsed.toString());
}

main()
  .then(() => process.exit(0))
  .catch(error => {
    console.error(error);
    process.exit(1);
  });
```

**Run it**:
```bash
cd 1_blockchain-identity
npx hardhat run create_vehicle_did.js
```

**Expected output**:
```
Deploying ERC-1056 registry...
✅ Registry deployed at: 0x5FbDB2315678afecb367f032d93F642f64180aa3

Creating vehicle DID...
✅ Vehicle DID created: did:ethr:31337:0x1234567890abcdef1234567890abcdef12345678
   VIN Hash: 0xabc123...
   Gas used: 52341
```

### Example 2: Resolve Vehicle DID (30 seconds)

Create `resolve_did.py` in `2_w3c-ssi-layer/did-resolution/`:

```python
#!/usr/bin/env python3
from did_resolver import DIDResolver
import json

# Create resolver
resolver = DIDResolver()

# Vehicle DID from Tesla
vehicle_did = "did:mobi:5YJ3E1EA0PF123456"

print(f"Resolving: {vehicle_did}\n")

# Resolve
result = resolver.resolve(vehicle_did)

if result.didResolutionMetadata.error:
    print(f"❌ Error: {result.didResolutionMetadata.error}")
else:
    print("✅ DID Document:")
    print(json.dumps(result.to_dict(), indent=2))
```

**Run it**:
```bash
python3 resolve_did.py
```

**Expected output**:
```json
Resolving: did:mobi:5YJ3E1EA0PF123456

✅ Resolved did:mobi:5YJ3E1EA0PF123456 in 0.23ms
✅ DID Document:
{
  "didDocument": {
    "@context": [...],
    "id": "did:mobi:5YJ3E1EA0PF123456",
    "verificationMethod": [{
      "id": "did:mobi:5YJ3E1EA0PF123456#manufacturer-key",
      "type": "EcdsaSecp256k1VerificationKey2019",
      "controller": "did:mobi:5YJ3E1EA0PF123456"
    }],
    "service": [{
      "id": "did:mobi:5YJ3E1EA0PF123456#birth-certificate",
      "type": "MobiVidBirthCertificate",
      "serviceEndpoint": "ipfs://Qm..."
    }]
  }
}
```

---

## 📚 Next Steps

### Explore Smart Contracts

```bash
cd 1_blockchain-identity

# Test all standards
npx hardhat test

# Deploy to local network
npx hardhat node  # Terminal 1
npx hardhat run scripts/deployERC1056.js --network localhost  # Terminal 2

# Compile contracts
npx hardhat compile
```

### Explore DID Resolution

```bash
cd 2_w3c-ssi-layer/did-resolution

# Try different DID methods
python3 did_resolver.py did:ethr:0x1:0xabc...
python3 did_resolver.py did:nft:0x1:0x123:456
python3 did_resolver.py did:key:0x1:0xdef...
python3 did_resolver.py did:mobi:5YJ3E1EA0PF123456
```

### Run Benchmarks (when implemented)

```bash
# Performance testing
cd 4_comparison-framework/performance-metrics
python3 gas_analyzer.py  # Compare gas costs
python3 latency_analyzer.py  # Measure latency
```

### View Documentation

```bash
# Architecture
cat 1_blockchain-identity/CVIN-SSI-ARCHITECTURE.md

# Capabilities
cat CAPABILITIES.md

# Inventory
cat INVENTORY.md
```

---

## 🔧 Troubleshooting

### Problem: `npm install` fails

**Solution**:
```bash
# Clear cache
npm cache clean --force

# Try again
npm install

# Or use specific Node version
nvm use 18
npm install
```

### Problem: `pip install` cryptography error

**Error**: `ModuleNotFoundError: No module named '_cffi_backend'`

**Solution**:
```bash
# This is a system dependency issue, but non-blocking
# The DID resolver will still work

# To fix (Ubuntu/Debian):
sudo apt-get install python3-dev libffi-dev libssl-dev
pip3 install --upgrade cryptography
```

### Problem: Hardhat tests timeout

**Solution**:
```bash
# Increase timeout in hardhat.config.js
// Add to networks.hardhat:
timeout: 60000  // 60 seconds
```

### Problem: `git clone` fails

**Solution**:
```bash
# Use HTTPS instead of SSH
git clone https://github.com/nikhilprakash-cvin/2_miniature-waffle-CV2X-Testbed-MOBI-VID.git

# Or check internet connection
ping github.com
```

---

## 🎯 What You Can Do Now

### ✅ Working Features

1. **Deploy smart contracts** (ERC-1056, ERC-721, ERC-725)
2. **Create vehicle DIDs** on blockchain
3. **Resolve DIDs** to W3C documents
4. **Run tests** (18+ test cases)
5. **Measure gas costs** (via test output)

### 🔄 Coming Soon

1. **Issue Verifiable Credentials** (W3C VC layer)
2. **Run 10 use cases** (complete workflows)
3. **Compare all 9 standards** (performance framework)
4. **SUMO simulation** (50 vehicles)

---

## 📖 Learning Path

### Beginner (1 hour)

1. ✅ Complete this quickstart
2. Read `README.md`
3. Read `CAPABILITIES.md`
4. Run `npx hardhat test`

### Intermediate (3 hours)

1. Read `CVIN-SSI-ARCHITECTURE.md`
2. Study smart contract code
3. Understand DID resolution
4. Deploy to testnet

### Advanced (1 day)

1. Implement a use case
2. Add new DID method
3. Contribute to VC layer
4. Run performance benchmarks

---

## 🚀 Common Tasks

### Deploy to Testnet

```bash
# Add to .env file:
SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_KEY
PRIVATE_KEY=your_private_key

# Deploy
npx hardhat run scripts/deployERC1056.js --network sepolia
```

### Run Specific Test

```bash
# Single test file
npx hardhat test test/ERC1056/EthereumDIDRegistry.test.js

# Single test case
npx hardhat test --grep "Should set attributes"

# With gas reporting
REPORT_GAS=true npx hardhat test
```

### Generate Documentation

```bash
# Solidity docs (NatSpec)
npx hardhat docgen

# Coverage report
npx hardhat coverage
```

---

## 📞 Getting Help

### Resources

- **Main README**: `/README.md`
- **Capabilities**: `/CAPABILITIES.md`
- **Inventory**: `/INVENTORY.md`
- **Architecture**: `/1_blockchain-identity/CVIN-SSI-ARCHITECTURE.md`

### Common Issues

| Issue | Solution |
|-------|----------|
| Tests fail | Run `npm install` again |
| Deployment fails | Check `.env` file |
| Python errors | Virtual environment recommended |
| Gas too high | Optimize contract or use different standard |

### Getting Unstuck

1. Check error message carefully
2. Look in `/docs/` for relevant documentation
3. Check GitHub issues
4. Review `CAPABILITIES.md` for what's implemented

---

## ✅ Success Checklist

After completing this quickstart, you should be able to:

- [x] Clone repository
- [x] Install dependencies (Node + Python)
- [x] Run smart contract tests
- [x] Deploy ERC-1056 registry
- [x] Create vehicle DID
- [x] Resolve DID to document
- [x] Understand basic architecture

---

## 🎯 What's Next?

### Immediate Next Steps

1. **Explore smart contracts**: Read `contracts/ERC1056/`
2. **Study DID resolver**: Read `2_w3c-ssi-layer/did-resolution/did_resolver.py`
3. **Run all tests**: `npx hardhat test`

### Build Something

1. **Modify DID resolver** to support new method
2. **Create test for new use case**
3. **Deploy to public testnet** (Sepolia)

### Contribute to Thesis

1. **Implement VC layer** (see `SECOND_PASS_PLAN.md`)
2. **Build use cases** (see `3_cv2x-testbed/use-cases/`)
3. **Add benchmarks** (see `4_comparison-framework/`)

---

**Quickstart Complete!** 🎉

You're now ready to explore the thesis implementation.

**Time Taken**: ~5 minutes  
**Next**: Read `CAPABILITIES.md` to see what you can build

---

**Last Updated**: June 21, 2026  
**Maintainer**: Nikhil Prakash (UBC MASc Thesis)  
**Questions**: nikhil.prakash1995@gmail.com
