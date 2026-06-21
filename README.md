# Self-Sovereign Identity for Connected and Autonomous Vehicles
## A Comparative Analysis of Blockchain-Based Identity Standards

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![UBC](https://img.shields.io/badge/Institution-UBC-blue.svg)](https://www.ubc.ca/)
[![Thesis](https://img.shields.io/badge/Type-MASc%20Thesis-green.svg)](https://github.com/nikhilprakash-cvin/2_miniature-waffle-CV2X-Testbed-MOBI-VID)

---

## 📚 Thesis Overview

**Title**: Comparative Analysis of Self-Sovereign Identity Systems for Connected and Autonomous Vehicles

**Author**: Nikhil Prakash  
**Institution**: University of British Columbia (UBC)  
**Department**: Electrical and Computer Engineering  
**Research Cluster**: Blockchain Interdisciplinary Research Cluster  
**Degree**: Master of Applied Science (MASc)  
**Year**: 2025-2026

### Research Questions

1. **Performance**: How do different blockchain identity standards compare in terms of transaction cost, latency, and throughput for vehicle identity management?

2. **Security**: Which identity architecture provides the strongest security guarantees for V2X (Vehicle-to-Everything) communication?

3. **Compliance**: Can blockchain-based identity systems achieve full W3C Self-Sovereign Identity compliance while meeting automotive industry requirements (MOBI VID)?

4. **Practical Feasibility**: Are blockchain identity systems viable for real-time safety-critical V2V (Vehicle-to-Vehicle) communication?

### Hypothesis

Lightweight blockchain identity standards (ERC-1056) can provide sufficient security and W3C compliance for vehicle identity management while maintaining performance suitable for real-time V2V safety applications, offering a viable alternative to centralized PKI systems.

---

## 🏗️ Repository Structure

```
CVIN-SC-Implementation-SSI-DID/
│
├── 1_blockchain-identity/              # 9 ERC Standard Implementations
│   ├── ERC721/                         # NFT-based vehicle identity
│   ├── ERC725/                         # Proxy account identity
│   ├── ERC735/                         # Claim holder standard
│   ├── ERC725xy/                       # Enhanced proxy
│   ├── ERC1056/                        # Lightweight DID ⭐
│   ├── ERC1155/                        # Multi-token credentials
│   ├── LSP8/                           # LUKSO universal profile
│   ├── ERC4337/                        # Account abstraction
│   └── CVIN-Combined/                  # Hybrid approach
│
├── 2_w3c-ssi-layer/                    # W3C Standards Implementation
│   ├── did-resolution/                 # DID Core v1.0 resolver
│   ├── verifiable-credentials/         # VC Data Model v2.0
│   └── mobi-vid/                       # MOBI VID I & II
│
├── 3_cv2x-testbed/                     # Real-World Testing Environment
│   ├── sumo-simulation/                # Traffic simulation (50 vehicles)
│   ├── safety-applications/            # FCW, EEBL, IMA
│   └── use-cases/                      # 10 lifecycle scenarios
│
├── 4_comparison-framework/             # Thesis Analysis & Results
│   ├── performance-metrics/            # Gas costs, latency, throughput
│   ├── security-analysis/              # Attack scenarios, threat models
│   └── results/                        # Experimental data & graphs
│
├── docs/                               # Documentation
│   ├── thesis/                         # Thesis chapters & LaTeX
│   ├── architecture/                   # System design documents
│   └── api/                            # API documentation
│
├── .github/workflows/                  # CI/CD for reproducible experiments
│   ├── test-contracts.yml
│   ├── benchmark.yml
│   └── deploy-testnet.yml
│
└── README.md                           # This file
```

---

## 🔬 Research Methodology

### Phase 1: Blockchain Identity Implementation (✅ Complete)
- Implement 9 different ERC standards for vehicle identity
- Deploy to Ethereum test networks
- Measure gas costs and transaction times

**Deliverables**:
- ✅ Smart contracts for all 9 standards
- ✅ Hardhat test suite
- ✅ Deployment scripts
- ✅ Initial performance benchmarks

### Phase 2: W3C SSI Compliance (🔄 In Progress)
- Build W3C DID resolver
- Implement Verifiable Credentials Data Model
- MOBI VID I (birth certificates) & II (lifecycle events)

**Deliverables**:
- W3C DID documents for each standard
- VC issuance/verification system
- MOBI VID compliant implementation
- Compliance test suite (target: >90%)

### Phase 3: CV2X Testbed Integration (🔄 In Progress)
- SUMO traffic simulation with 50 vehicles
- Safety-critical V2V applications
- Real-time identity verification

**Deliverables**:
- SUMO network configuration
- 3 safety applications (FCW, EEBL, IMA)
- 10 complete use case scenarios
- Performance metrics (<10ms verification)

### Phase 4: Comparative Analysis (⏳ Planned)
- Run identical experiments across all 9 standards
- Measure performance, cost, security
- Statistical analysis

**Deliverables**:
- Performance comparison report
- Security analysis
- Cost-benefit analysis
- Thesis chapters 4-6

### Phase 5: Thesis Writing (⏳ Planned)
- Literature review
- Methodology documentation
- Results analysis
- Conclusions and future work

---

## 📊 Key Results (Preliminary)

### W3C Compliance Score

| Standard | DID Core | VC Model | SSI Principles | Overall |
|----------|----------|----------|----------------|---------|
| ERC-1056 | 75%      | 100%     | 100%           | **89.6%** ✅ |
| ERC-721  | TBD      | TBD      | TBD            | TBD |
| ERC-725  | TBD      | TBD      | TBD            | TBD |

### Performance Comparison

| Metric | ERC-1056 | ERC-721 | Centralized |
|--------|----------|---------|-------------|
| DID Creation | ~$0.50 | TBD | $0.01 |
| DID Resolution | 50-100ms | TBD | <1ms |
| VC Verification | 5-10ms | TBD | <1ms |
| V2V Message Verify | 50ms | TBD | 5ms |

**Key Finding**: ERC-1056 lightweight DID meets real-time requirements for non-critical V2V applications but requires optimization for safety-critical scenarios.

---

## 🚀 Getting Started

### Prerequisites

```bash
# Node.js & npm
node --version  # v18+
npm --version   # v9+

# Hardhat (Ethereum development)
npm install --save-dev hardhat

# Python (for testbed)
python3 --version  # v3.9+
pip3 install traci sumolib web3

# SUMO (traffic simulation)
sudo apt-get install sumo sumo-tools
```

### Installation

```bash
# Clone repository
git clone https://github.com/nikhilprakash-cvin/2_miniature-waffle-CV2X-Testbed-MOBI-VID.git
cd 2_miniature-waffle-CV2X-Testbed-MOBI-VID

# Install blockchain dependencies
cd 1_blockchain-identity
npm install

# Install Python dependencies
cd ../2_w3c-ssi-layer
pip3 install -r requirements.txt

# Install testbed dependencies
cd ../3_cv2x-testbed
pip3 install -r requirements.txt
```

### Running Tests

```bash
# Test smart contracts
cd 1_blockchain-identity
npx hardhat test

# Test W3C compliance
cd ../2_w3c-ssi-layer
python3 -m pytest tests/

# Run CV2X simulation
cd ../3_cv2x-testbed/sumo-simulation
python3 sumo_identity_integration.py --simulate --duration 60

# Run comparison benchmarks
cd ../../4_comparison-framework
python3 run_benchmarks.py
```

### Running Full Thesis Experiments

```bash
# Automated thesis experiment suite
./scripts/run_thesis_experiments.sh

# Generates:
# - Performance comparison data
# - Security analysis reports
# - Graphs and visualizations
# - LaTeX tables for thesis
```

---

## 📖 Documentation

### Academic Papers Referenced

1. **W3C DID Core v1.0**: https://www.w3.org/TR/did-core/
2. **W3C Verifiable Credentials v2.0**: https://www.w3.org/TR/vc-data-model-2.0/
3. **MOBI VID Specification**: https://dlt.mobi/vid/
4. **ERC-1056**: Lightweight Identity Standard
5. **IEEE 1609.2**: V2X Security Services

### Thesis Chapters

- [Chapter 1: Introduction](docs/thesis/01-introduction.md)
- [Chapter 2: Literature Review](docs/thesis/02-literature-review.md)
- [Chapter 3: Methodology](docs/thesis/03-methodology.md)
- [Chapter 4: Implementation](docs/thesis/04-implementation.md) ✅
- [Chapter 5: Results](docs/thesis/05-results.md) 🔄
- [Chapter 6: Discussion](docs/thesis/06-discussion.md) ⏳
- [Chapter 7: Conclusion](docs/thesis/07-conclusion.md) ⏳

### API Documentation

- [Smart Contract API](docs/api/smart-contracts.md)
- [W3C SSI Layer API](docs/api/w3c-ssi.md)
- [CV2X Testbed API](docs/api/cv2x-testbed.md)

### Architecture Documents

- [System Architecture](1_blockchain-identity/CVIN-SSI-ARCHITECTURE.md) ✅
- [Security Model](docs/architecture/security-model.md)
- [Privacy Design](docs/architecture/privacy-design.md)

---

## 🔐 Security & Privacy

### Threat Model

This research considers the following adversaries:

1. **External Attacker**: Attempts to impersonate vehicles or inject false data
2. **Honest-but-Curious**: Service providers collecting more data than necessary
3. **Malicious Insider**: Compromised manufacturer or government agency
4. **Sybil Attack**: Creating multiple fake identities

### Privacy Features

- ✅ VIN encryption with owner-only decryption
- ✅ Selective disclosure (zero-knowledge proofs ready)
- ✅ Unlinkability between different verifiers
- ✅ Revocation without correlation
- ⏳ Anonymous credentials (planned)

### Compliance

- ✅ GDPR "Right to be Forgotten" (via revocation)
- ✅ W3C Privacy Principles
- ⏳ ISO/SAE 21434 (Automotive Cybersecurity)

---

## 🎯 Use Cases Implemented

All use cases demonstrate complete workflows with multiple parties:

1. ✅ **Vehicle Manufacturing & Birth Registration**
2. ✅ **Regular Maintenance Service**
3. ✅ **Ownership Transfer (Used Car Sale)**
4. ✅ **Insurance Claim (Accident)**
5. ✅ **Manufacturer Recall**
6. ✅ **Cross-Border Vehicle Import**
7. ✅ **Fleet Management**
8. ✅ **Emissions Testing & Compliance**
9. ✅ **Vehicle Theft & Recovery**
10. ✅ **Autonomous Vehicle Data Sharing**

Each use case includes:
- Multi-party interactions
- Verifiable Credential issuance/verification
- Privacy-preserving selective disclosure
- Complete audit trail

---

## 📈 Research Contributions

### Novel Contributions

1. **First comprehensive comparison** of 9 blockchain identity standards for automotive applications

2. **Real-time V2V integration** with blockchain identity verification (first working implementation)

3. **MOBI VID + W3C compliance** - bridging automotive and web identity standards

4. **Hybrid architecture** combining strengths of multiple ERC standards

5. **Open-source testbed** for reproducible vehicular identity research

### Expected Impact

- **Academic**: Benchmark for future automotive identity research
- **Industry**: Reference implementation for MOBI VID
- **Standards**: Feedback to W3C DID/VC working groups
- **Policy**: Insights for vehicle identity regulation

---

## 🤝 Contributing

This is active thesis research. Contributions welcome after thesis defense (expected: 2026).

For questions or collaboration:
- 📧 Email: nikhil.prakash1995@gmail.com
- 🐙 GitHub: [@nikhilprakash-cvin](https://github.com/nikhilprakash-cvin)

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details.

**Academic Use**: Please cite this work if used in academic publications:

```bibtex
@mastersthesis{prakash2026ssi,
  author = {Prakash, Nikhil},
  title = {Comparative Analysis of Self-Sovereign Identity Systems for Connected and Autonomous Vehicles},
  school = {University of British Columbia},
  year = {2026},
  type = {Master's Thesis},
  department = {Electrical and Computer Engineering}
}
```

---

## 🙏 Acknowledgments

- **Supervisor**: [TBD]
- **UBC Blockchain Research Cluster**
- **MOBI (Mobility Open Blockchain Initiative)**
- **W3C DID & VC Working Groups**

---

## 📞 Contact

**Nikhil Prakash**  
MASc Candidate, Electrical and Computer Engineering  
University of British Columbia  
nikhil.prakash1995@gmail.com

**Research Group**: UBC Blockchain Interdisciplinary Research Cluster

---

<div align="center">

**🎓 UBC ECE Department | 🔗 Blockchain Research Cluster | 🚗 MOBI VID**

*Building the future of vehicular identity*

</div>
