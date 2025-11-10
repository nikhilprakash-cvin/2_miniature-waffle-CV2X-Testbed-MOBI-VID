# CV2X Testbed for Connected Vehicle Identity

## Overview

This testbed provides a virtual environment for testing Cellular Vehicle-to-Everything (CV2X) communications before implementing blockchain-based Decentralized Identifiers (DIDs) and Self-Sovereign Identity (SSI) systems.

## Purpose

1. **Baseline Testing**: Establish CV2X communication protocols
2. **Standard Identity Implementation**: Implement traditional PKI-based vehicle identification
3. **Comparison Framework**: Compare standard identity mechanisms with DID/SSI approaches
4. **Integration Platform**: Provide foundation for blockchain-based identity integration

## Architecture

```
cv2x-testbed/
├── docs/              # Technical documentation
├── docker/            # Docker configuration for simulation environment
├── protocols/         # CV2X protocol implementations
│   ├── pc5/          # PC5 interface (V2V direct communication)
│   ├── uu/           # Uu interface (V2N via cellular network)
│   └── messages/     # Message formats (CAM, DENM, BSM)
├── scenarios/         # Test scenarios and use cases
├── identity/          # Identity management systems
│   ├── standard/     # Traditional PKI-based identity
│   └── did/          # DID/SSI integration (future)
└── scripts/           # Utility scripts

```

## CV2X Technology Stack

### Communication Modes

1. **Mode 3**: Network-assisted resource allocation (via eNodeB)
2. **Mode 4**: Autonomous resource allocation (direct V2V)

### Message Types

- **BSM (Basic Safety Message)**: Position, speed, heading (10 Hz)
- **CAM (Cooperative Awareness Message)**: European equivalent of BSM
- **DENM (Decentralized Environmental Notification Message)**: Event-triggered warnings

### Interfaces

- **PC5**: Direct V2V/V2P communication (sidelink)
- **Uu**: V2N communication through cellular infrastructure

## Components

### 1. Traffic Simulation
- **SUMO** (Simulation of Urban MObility)
- Realistic vehicle movement patterns
- Configurable road networks and traffic flows

### 2. Network Simulation
- **ns-3** with CV2X extensions
- LTE-V2X / 5G-NR V2X simulation
- Channel models and interference simulation

### 3. Protocol Stack
- Physical Layer (PHY)
- MAC Layer with resource allocation
- Application Layer (V2X services)

### 4. Identity Systems

#### Standard Identity (Baseline)
- PKI-based certificates
- Certificate Authority (CA) hierarchy
- Certificate revocation lists (CRLs)
- Pseudonym certificates for privacy

#### DID/SSI Identity (Research)
- Blockchain-based identity
- Verifiable Credentials
- Decentralized key management
- Comparison metrics

## Getting Started

### Prerequisites

```bash
# Docker and Docker Compose
docker --version
docker-compose --version

# Python 3.8+
python3 --version

# Node.js (for blockchain integration)
node --version
```

### Quick Start

```bash
# 1. Build the simulation environment
cd docker
docker-compose up -d

# 2. Run a basic V2V scenario
./scripts/run_scenario.sh basic_v2v

# 3. Monitor communications
./scripts/monitor.sh
```

## Test Scenarios

1. **Basic V2V Communication**: Two vehicles exchanging BSM messages
2. **Emergency Warning**: DENM propagation in traffic
3. **Platoon Formation**: Multiple vehicles coordinating
4. **Intersection Coordination**: Traffic signal integration
5. **Identity Comparison**: PKI vs DID performance metrics

## Performance Metrics

### Communication Metrics
- Packet Delivery Ratio (PDR)
- End-to-End Delay
- Channel Busy Ratio (CBR)
- Inter-Packet Gap (IPG)

### Identity Metrics
- Authentication time
- Certificate/credential size
- Revocation latency
- Privacy preservation
- Computational overhead

## Research Questions

1. How does DID-based authentication compare to PKI in terms of latency?
2. What is the overhead of blockchain queries vs CRL checks?
3. How do privacy mechanisms compare (pseudonym certificates vs DIDs)?
4. What is the impact on network performance?

## Next Steps

1. ✅ Set up testbed infrastructure
2. ⏳ Implement CV2X protocol stack
3. ⏳ Deploy standard PKI-based identity
4. ⏳ Create test scenarios
5. ⏳ Integrate DID/SSI from CVIN-ID-SCs
6. ⏳ Run comparative analysis

## References

- 3GPP TS 23.285: Architecture enhancements for V2X services
- ETSI EN 302 637-2: CAM specification
- ETSI EN 302 637-3: DENM specification
- SAE J2735: V2X Message Set Dictionary
- W3C DID Core Specification
- MOBI VID Standard

## License

MIT License - See LICENSE file for details
