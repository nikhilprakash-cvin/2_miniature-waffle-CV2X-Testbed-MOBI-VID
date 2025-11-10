# CV2X Testbed Quick Start Guide

## Overview

This testbed allows you to:
1. Simulate CV2X (Cellular Vehicle-to-Everything) communications
2. Test standard PKI-based vehicle identity
3. Compare with DID/SSI-based identity (to be integrated)
4. Analyze performance metrics for V2X applications

## Prerequisites

- Python 3.8 or higher
- pip package manager
- Git

## Installation

### 1. Clone the repository (if not already done)

```bash
git clone <repository-url>
cd CVIN-SC-Implementation-SSI-DID/cv2x-testbed
```

### 2. Run the setup script

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

This will:
- Create a Python virtual environment
- Install all required dependencies
- Set up the development environment

### 3. Activate the environment

```bash
source venv/bin/activate
```

## Running Tests

### Test 1: PKI Identity System

Test the standard PKI-based identity:

```bash
cd identity/standard
python pki_identity.py
```

Expected output:
```
=== Standard PKI Identity System Test ===

✓ Certificate Authority initialized: CVIN-Test-CA
✓ Vehicle identity created: V001
✓ Enrollment certificate issued
✓ 20 pseudonym certificates issued
✓ BSM signed with pseudonym certificate
✓ Message verification: True (took X.XX ms)
```

### Test 2: CV2X Protocol Stack

Test the CV2X communication stack:

```bash
cd protocols
python cv2x_stack.py
```

Expected output:
```
=== CV2X Protocol Stack Test ===

Vehicle 1 sending BSM...
  ✓ BSM transmitted (XXX bytes)

Vehicle 2 receiving BSM...
  ✓ BSM received successfully
  Distance: XX.X m
  RX Power: XX.X dBm
  Latency: X.XX ms
```

### Test 3: Basic V2V Scenario

Run a multi-vehicle V2V communication scenario:

```bash
cd scenarios
python basic_v2v_scenario.py
```

For more vehicles and longer simulation:

```bash
python basic_v2v_scenario.py --vehicles 5 --time 30
```

Command-line options:
- `--vehicles N`: Number of vehicles (default: 2)
- `--time T`: Simulation duration in seconds (default: 10)
- `--no-identity`: Disable PKI identity system for baseline testing

### Test 4: Identity System Comparison

Run benchmark comparison between identity systems:

```bash
cd scripts
python run_comparison.py
```

This generates:
- Performance metrics (signing time, verification time, etc.)
- Size metrics (credential size, signature overhead)
- Comparison report saved in `reports/` directory

## Understanding the Results

### Communication Metrics

- **Packet Delivery Ratio (PDR)**: Percentage of successfully received messages
  - Target: > 90% for V2X safety applications

- **End-to-End Latency**: Time from transmission to reception
  - Target: < 100 ms for safety-critical messages

- **Channel Busy Ratio (CBR)**: Percentage of channel occupied
  - Target: < 70% to avoid congestion

### Identity Metrics

- **Signing Time**: Time to sign a message (e.g., BSM)
  - Target: < 10 ms (for 10 Hz BSM rate)

- **Verification Time**: Time to verify a received message
  - Target: < 5 ms (vehicles receive multiple BSMs/second)

- **Credential Size**: Size of certificate/DID credential
  - Important for bandwidth efficiency

- **Message Overhead**: Additional bytes added by signature + credential
  - Target: < 50% of base message size

## Directory Structure

```
cv2x-testbed/
├── docs/                    # Technical documentation
│   └── CV2X_PROTOCOLS.md   # CV2X protocol details
├── docker/                  # Docker setup (optional)
│   └── docker-compose.yml  # Multi-container setup
├── protocols/               # CV2X protocol implementations
│   └── cv2x_stack.py       # Main protocol stack
├── identity/                # Identity systems
│   ├── standard/           # PKI-based identity
│   │   └── pki_identity.py
│   ├── did/                # DID/SSI (to be integrated)
│   └── comparison_framework.py
├── scenarios/               # Test scenarios
│   └── basic_v2v_scenario.py
├── scripts/                 # Utility scripts
│   ├── setup.sh
│   └── run_comparison.py
└── reports/                 # Generated reports
```

## Next Steps

### Phase 1: Baseline Testing (Current)
✅ Standard PKI identity system
✅ CV2X protocol stack
✅ Basic V2V scenarios
✅ Performance benchmarking

### Phase 2: DID Integration (Upcoming)
⏳ Integrate DID implementations from CVIN-ID-SCs
⏳ Implement DID-based message signing/verification
⏳ Run comparative benchmarks
⏳ Analyze results

### Phase 3: Advanced Scenarios
⏳ Emergency vehicle approaching
⏳ Intersection collision avoidance
⏳ Platoon formation
⏳ Large-scale simulation (100+ vehicles)

## Integrating DID/SSI

The DID/SSI implementations are in the `CVIN-ID-SCs/` directory. To integrate:

1. Choose a DID implementation (ERC-721, ERC-725, ERC-1056, etc.)
2. Create wrapper in `cv2x-testbed/identity/did/`
3. Implement `sign_message()` and `verify_message()` methods
4. Run comparison with PKI baseline

Example integration:

```python
# cv2x-testbed/identity/did/did_identity.py
from CVIN-ID-SCs.ERC1056 import EthrDID

class VehicleDIDIdentity:
    def __init__(self, vehicle_id):
        self.did = EthrDID(vehicle_id)

    def sign_message(self, message):
        # Use DID to sign message
        return self.did.sign(message)

    def verify_message(self, signed_message, registry):
        # Verify using DID document from blockchain
        return self.did.verify(signed_message)
```

## Troubleshooting

### Import Errors

If you get import errors:
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall requirements
pip install -r requirements.txt
```

### Permission Denied on Scripts

```bash
chmod +x scripts/*.sh
```

### Blockchain Connection (for DID integration)

The docker-compose includes a local Ganache blockchain:
```bash
cd docker
docker-compose up blockchain
```

Access at: `http://localhost:8545`

## Documentation

- [CV2X Protocols](docs/CV2X_PROTOCOLS.md) - Detailed protocol documentation
- [Main README](README.md) - Project overview and architecture

## Support

For issues or questions:
1. Check existing documentation
2. Review test output and error messages
3. Consult 3GPP and ETSI specifications (see references in docs)

## License

MIT License - See LICENSE file for details
