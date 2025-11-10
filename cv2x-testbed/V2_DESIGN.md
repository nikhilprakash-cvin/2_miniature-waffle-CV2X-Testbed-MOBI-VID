# CV2X Testbed V2 - Design Document

## Executive Summary

This document outlines the design for V2 of the CV2X testbed, transforming it from a proof-of-concept into a **research-grade platform** suitable for a university Connected Vehicles Lab.

## Critical Analysis of V1

### What V1 Got Right ✅
- Solid foundation with proper CV2X protocol structure
- Good PKI implementation (IEEE 1609.2 compliant)
- Extensible architecture
- Comprehensive documentation
- DID integration framework

### Major Gaps in V1 🔴

#### 1. **Simulation Realism**
- ❌ No real traffic simulation (SUMO not integrated)
- ❌ Oversimplified channel model (just free-space path loss)
- ❌ No fading, shadowing, or realistic propagation
- ❌ No collision detection or hidden terminal problem
- ❌ Static scenarios, no dynamic traffic

#### 2. **V2X Application Layer**
- ❌ Only basic BSM/DENM - missing critical safety apps
- ❌ No Forward Collision Warning (FCW)
- ❌ No Cooperative Adaptive Cruise Control (CACC)
- ❌ No Intersection Management
- ❌ No V2I (Infrastructure) integration

#### 3. **Security & Privacy**
- ❌ No misbehavior detection
- ❌ No attack simulations (Sybil, replay, position falsification)
- ❌ No privacy metrics (k-anonymity, unlinkability)
- ❌ Simplistic CRL - no OCSP or blockchain revocation comparison
- ❌ No reputation/trust system

#### 4. **Network Realism**
- ❌ No actual NS-3 integration
- ❌ No congestion control (DCC - Decentralized Congestion Control)
- ❌ No channel models (VehA, VehB from 3GPP)
- ❌ Only Mode 4 - Mode 3 is placeholder
- ❌ No 5G NR-V2X (only LTE-V2X)

#### 5. **DID/Blockchain Integration**
- ❌ DID verification is placeholder
- ❌ No actual blockchain queries
- ❌ No gas cost analysis
- ❌ No scalability testing with real smart contracts
- ❌ No comparison of different DID methods (ERC-721 vs 1056 vs 725)

#### 6. **Visualization & Analysis**
- ❌ No real-time visualization
- ❌ No geographic map display
- ❌ No message flow visualization
- ❌ Limited metrics collection
- ❌ No automated experiment runs

#### 7. **Standards Compliance**
- ❌ Partial SAE J2735 (only BSM)
- ❌ Missing ETSI ITS-G5 specific features
- ❌ No ISO 21217 (CALM) architecture
- ❌ No conformance testing

#### 8. **Research Features**
- ❌ No machine learning integration
- ❌ No parameter sweeps or design space exploration
- ❌ No reproducibility features (random seed management)
- ❌ No automated statistical analysis
- ❌ No comparison with baseline datasets

---

## V2 Architecture - Research-Grade Platform

### Design Principles

1. **Publication-Ready**: Generate graphs, tables, and data suitable for IEEE/ACM papers
2. **Reproducible**: Seed management, configuration versioning, experiment tracking
3. **Realistic**: Industry-standard tools (SUMO, NS-3) with validated models
4. **Comprehensive**: Full V2X stack from PHY to application
5. **Secure**: Complete security framework with attack/defense scenarios
6. **Blockchain-Native**: Real smart contract integration, not simulated
7. **Extensible**: Plugin architecture for new protocols and applications

---

## V2 Component Design

### 1. Realistic Traffic Simulation

#### SUMO Integration (TraCI)
```python
class SUMOTrafficSimulator:
    """
    Real-time integration with SUMO via TraCI.
    """
    - Load OpenStreetMap road networks
    - Realistic traffic patterns (rush hour, incidents)
    - Multiple vehicle types (cars, trucks, buses, emergency)
    - Lane changes, overtaking, merging
    - Traffic light control (SPaT messages)
    - Pedestrian simulation (PSM messages)
    - Calibrated with real traffic data
```

**Scenarios**:
- Urban Grid (downtown Vancouver)
- Highway (Interstate)
- Mixed Urban-Highway
- Intersection Coordination
- Parking Lot (low speed)
- Emergency Vehicle Corridors

#### Pre-loaded Datasets
- Real traffic traces from Vancouver/UBC area
- Standard benchmark scenarios (Bologna, Manhattan, SUMO examples)
- Calibrated mobility models

---

### 2. Advanced Network Simulation

#### NS-3 Integration
```python
class NS3CV2XNetwork:
    """
    Full NS-3 integration for realistic channel simulation.
    """
    # 3GPP Channel Models
    - VehA: Urban street canyon
    - VehB: Highway (LOS/NLOS)
    - VehC: Rural (extended range)

    # Features
    - Fast fading (Rayleigh, Rician)
    - Shadow fading (log-normal)
    - Doppler shift
    - Building blockage
    - Multi-path propagation

    # Interference
    - Co-channel interference
    - Adjacent channel interference
    - Hidden terminal problem
    - Collision detection
```

#### Decentralized Congestion Control (DCC)
```python
class DCCController:
    """
    ETSI TS 102 687 DCC implementation.
    """
    - CBR monitoring
    - Transmit power control
    - Transmit rate control (TRC)
    - Message priority queuing
    - Adaptive datarate
```

#### 5G NR-V2X Support
```python
class NR_V2X_Stack:
    """
    5G New Radio V2X (3GPP Release 16+)
    """
    - Higher throughput (up to 50 Mbps)
    - Lower latency (<10ms)
    - Sidelink mode 2 (autonomous)
    - Resource pools with sensing
    - QoS management
    - Comparison with LTE-V2X
```

---

### 3. Complete V2X Application Suite

#### Safety Applications (SAE J2945)

```python
class ForwardCollisionWarning:
    """FCW: Detect imminent rear-end collision"""
    - Time-to-collision (TTC) calculation
    - Brake warning generation
    - Multi-hop relay for chain collisions
    - Effectiveness metrics (false alarm rate, detection rate)

class EmergencyElectronicBrakeLight:
    """EEBL: Broadcast hard braking event"""
    - Deceleration threshold detection
    - DENM generation and broadcast
    - Effective warning distance
    - Driver response time modeling

class IntersectionMovementAssist:
    """IMA: Prevent intersection collisions"""
    - MAP message parsing (intersection geometry)
    - SPaT message integration (signal timing)
    - Trajectory prediction
    - Collision point estimation
    - Stop recommendation

class BlindSpotWarning:
    """BSW: Detect vehicles in blind spot"""
    - Relative position tracking
    - Lane change safety assessment
    - Warning generation

class CooperativeAdaptiveCruiseControl:
    """CACC: Cooperative platoon control"""
    - String stability analysis
    - Inter-vehicle gap control
    - Acceleration coordination
    - Platooning efficiency metrics
```

#### Infrastructure Integration

```python
class RoadsideUnit:
    """RSU: Infrastructure-based V2X"""
    - Traffic signal controller interface
    - SPaT/MAP broadcasting
    - Local hazard warnings
    - Work zone alerts
    - Parking availability
    - Toll collection

class TrafficManagementCenter:
    """TMC: Centralized coordination"""
    - Global traffic state
    - Route optimization
    - Incident management
    - Emergency vehicle priority
```

#### Additional Message Types

```python
# Full SAE J2735 Message Set
class MessageFactory:
    BSM   # Basic Safety Message ✅ (already in v1)
    DENM  # Decentralized Event Notification ✅ (already in v1)
    SPaT  # Signal Phase and Timing ⭐ NEW
    MAP   # Intersection geometry ⭐ NEW
    PSM   # Personal Safety Message (pedestrians) ⭐ NEW
    RSA   # Road Safety Advisory ⭐ NEW
    SSM   # Signal Status Message ⭐ NEW
    SRM   # Signal Request Message ⭐ NEW
    TIM   # Traveler Information Message ⭐ NEW
    PVD   # Probe Vehicle Data ⭐ NEW
```

---

### 4. Advanced Security & Privacy Framework

#### Misbehavior Detection System

```python
class MisbehaviorDetectionSystem:
    """
    Multi-layered misbehavior detection.
    """
    # Detection Layers
    - Plausibility checks (position, speed, acceleration)
    - Consistency checks (position history)
    - Kalman filter-based tracking
    - Machine learning anomaly detection
    - Reputation-based filtering

    # Attack Detection
    - Position falsification
    - Denial of Service (DoS)
    - Sybil attacks
    - Replay attacks
    - Message injection
    - Bogus information

    # Response
    - Local revocation
    - Report to CA/blockchain
    - Neighbor notification
    - Forensic evidence collection
```

#### Attack Simulation Framework

```python
class AttackScenario:
    """Configurable attack scenarios for testing"""

    class SybilAttack:
        """Multiple fake identities"""
        - Generate N fake vehicles
        - Test DID resistance
        - Measure detection time

    class PositionFalsification:
        """False position reporting"""
        - Ghost vehicle attack
        - Illusion attack (create fake traffic jam)
        - Measure safety impact

    class ReplayAttack:
        """Replay old messages"""
        - Test timestamp validation
        - Nonce verification
        - Freshness guarantees

    class EavesdropAttack:
        """Privacy violation"""
        - Track vehicles across pseudonyms
        - Test unlinkability
        - Measure privacy metrics
```

#### Privacy Metrics

```python
class PrivacyAnalyzer:
    """Quantitative privacy evaluation"""

    # Metrics
    - k-anonymity: Min set size for indistinguishability
    - Entropy: Information leaked per message
    - Unlinkability: Correlation between pseudonyms
    - Tracking resistance: Max tracking time
    - Location privacy: Spatial cloaking effectiveness

    # Analysis
    - Pseudonym change strategy evaluation
    - Mix zone effectiveness
    - Silent period optimization
    - DID vs PKI privacy comparison
```

---

### 5. Blockchain & DID Integration (Real Implementation)

#### Multi-DID Comparison Framework

```python
class DIDComparison:
    """
    Test ALL DID methods from CVIN-ID-SCs
    """
    # Implementations to compare:
    1. ERC-721 (NFT-based)
    2. ERC-725 (Proxy identity)
    3. ERC-1056 (Lightweight)
    4. ERC-1155 (Multi-token)
    5. ERC-725x,y (Enhanced)
    6. LSP8 (LUKSO)
    7. ERC-4337 (Account abstraction)

    # Metrics per implementation:
    - Gas costs (deployment, registration, update, revocation)
    - Latency (on-chain vs off-chain resolution)
    - Storage costs
    - Scalability (TPS limits)
    - Privacy (linkability analysis)
    - Feature comparison (recovery, delegation, etc.)
```

#### Blockchain Network Options

```python
class BlockchainBackend:
    """Support multiple blockchain backends"""

    # Local Development
    - Ganache (fast, no gas costs)
    - Hardhat Network (debugging)

    # Testnets
    - Sepolia (Ethereum testnet)
    - Mumbai (Polygon testnet)
    - BSC Testnet

    # Scaling Solutions
    - Polygon (low gas)
    - Optimism (L2 rollup)
    - Arbitrum (L2 rollup)

    # Private Chains
    - Hyperledger Besu
    - Quorum
```

#### Smart Contract Integration

```python
class VehicleRegistry:
    """
    Deploy and interact with real smart contracts
    """
    # Operations
    - Register vehicle DID
    - Update DID document
    - Revoke credential
    - Query DID document
    - Check revocation status

    # Performance tracking
    - Transaction confirmation time
    - Gas used per operation
    - Batch operation optimization
    - Off-chain storage (IPFS) integration
```

#### Hybrid Identity Modes

```python
class HybridIdentityManager:
    """
    Compare different identity architectures
    """

    Mode 1: Pure PKI (v1 baseline)
    Mode 2: Pure DID (all on-chain)
    Mode 3: Hybrid (PKI with blockchain anchoring)
    Mode 4: Federated DID (consortium blockchain)
    Mode 5: Layer 2 DID (rollup-based)
```

---

### 6. Real-Time Visualization & Dashboard

#### Web-Based Dashboard

```python
class RealtimeDashboard:
    """
    React + WebGL visualization
    """
    # Map View
    - OpenStreetMap integration
    - Vehicle positions (real-time)
    - Message propagation animation
    - Communication range circles
    - Collision warnings highlighted

    # Metrics Panel
    - Live PDR, latency graphs
    - Channel utilization (CBR)
    - Authentication success rate
    - Gas costs (for DID)
    - Network topology

    # Security View
    - Misbehavior alerts
    - Attack detection events
    - Reputation scores
    - Revoked identities

    # Controls
    - Simulation speed control
    - Scenario selection
    - Attack injection
    - Parameter adjustment
```

#### Data Export & Analysis

```python
class ExperimentManager:
    """
    Automated experiment orchestration
    """
    # Experiment Definition
    - YAML configuration files
    - Parameter sweeps (grid search)
    - Random seed management
    - Reproducibility metadata

    # Data Collection
    - Time-series data (HDF5)
    - Event logs (JSON)
    - Traces (pcap format)
    - Performance profiles

    # Analysis
    - Automated statistical tests
    - Confidence intervals
    - Hypothesis testing
    - Publication-ready plots (matplotlib/seaborn)
```

---

### 7. Machine Learning Integration

#### Predictive Models

```python
class MLComponents:
    """
    ML-enhanced V2X
    """

    # Trajectory Prediction
    - LSTM/GRU for vehicle trajectory
    - Predict future positions (1-5 seconds)
    - Improve collision detection
    - Reduce false alarms

    # Anomaly Detection
    - Autoencoder for misbehavior detection
    - Real-time classification (benign/malicious)
    - Adaptive thresholds
    - Transfer learning from other datasets

    # Resource Allocation
    - Deep RL for optimal resource selection
    - Predictive congestion control
    - Dynamic power/rate adaptation

    # Privacy
    - Differential privacy for location sharing
    - Federated learning across vehicles
    - Privacy-utility tradeoff optimization
```

---

### 8. Standards Compliance & Validation

#### Conformance Testing

```python
class ConformanceTest:
    """
    Validate against official standards
    """
    # Message Encoding
    - ASN.1 UPER encoding (SAE J2735)
    - ETSI ITS format validation
    - IEEE 1609.2 security header

    # Protocol Behavior
    - 3GPP test cases
    - ETSI plugtest scenarios
    - CAR 2 CAR Communication Consortium tests

    # Interoperability
    - Cross-vendor compatibility
    - Message parsing validation
    - Security certificate formats
```

#### Certification Support

```python
class CertificationFramework:
    """
    Support for industry certification
    """
    - IEEE 1609.2 certificate profiles
    - CAMP (Crash Avoidance Metrics Partnership) tests
    - NHTSA V2V test procedures
    - Euro NCAP scenarios
```

---

## V2 Feature Comparison

| Feature | V1 | V2 |
|---------|----|----|
| **Traffic Simulation** | Simplified | ✅ SUMO/TraCI + Real maps |
| **Network Simulation** | Basic path loss | ✅ NS-3 + 3GPP models |
| **Channel Models** | Free-space | ✅ VehA/B/C, Fading |
| **Safety Apps** | None | ✅ FCW, EEBL, IMA, CACC |
| **V2I Support** | No | ✅ RSU, SPaT, MAP |
| **Message Types** | 2 (BSM, DENM) | ✅ 10+ (Full SAE J2735) |
| **Misbehavior Detection** | No | ✅ Multi-layer detection |
| **Attack Simulation** | No | ✅ 6+ attack types |
| **Privacy Metrics** | None | ✅ k-anonymity, unlinkability |
| **DID Integration** | Placeholder | ✅ Real smart contracts |
| **Blockchain Options** | Ganache only | ✅ 5+ networks |
| **DID Comparisons** | 1 (PKI) | ✅ 7+ DID methods |
| **Gas Cost Analysis** | No | ✅ Full gas tracking |
| **Visualization** | CLI only | ✅ Web dashboard + maps |
| **5G NR-V2X** | No | ✅ Yes |
| **ML Integration** | No | ✅ Prediction + Anomaly |
| **Experiment Automation** | Manual | ✅ YAML configs + sweeps |
| **Statistical Analysis** | Basic | ✅ Automated + CI |
| **Standards Compliance** | Partial | ✅ Full conformance |
| **Publication Support** | Limited | ✅ Auto-generated figures |

---

## Implementation Priorities

### Phase 1: Core Infrastructure (Week 1-2)
1. ✅ SUMO integration with TraCI
2. ✅ NS-3 integration or advanced channel models
3. ✅ Real-time dashboard skeleton
4. ✅ Experiment configuration framework

### Phase 2: Applications (Week 3-4)
5. ✅ Safety applications (FCW, EEBL, IMA)
6. ✅ V2I support (RSU, SPaT, MAP)
7. ✅ Cooperative applications (CACC)

### Phase 3: Security (Week 5)
8. ✅ Misbehavior detection system
9. ✅ Attack simulation framework
10. ✅ Privacy metrics

### Phase 4: Blockchain (Week 6-7)
11. ✅ Real smart contract deployment
12. ✅ Multi-DID implementation testing
13. ✅ Gas cost analysis
14. ✅ Hybrid identity modes

### Phase 5: Advanced Features (Week 8)
15. ✅ ML components
16. ✅ 5G NR-V2X
17. ✅ Automated experiments
18. ✅ Publication-ready outputs

---

## Research Questions V2 Can Answer

1. **Performance**: How do 7 different DID methods compare in V2X latency?
2. **Cost**: What are the gas costs for different DID operations at scale?
3. **Security**: How effective is blockchain-based revocation vs CRL?
4. **Privacy**: What is the privacy-performance tradeoff for DID rotation?
5. **Scalability**: Can DID handle 1000+ vehicles in dense traffic?
6. **Safety**: Does DID authentication overhead impact safety app effectiveness?
7. **Attacks**: Are DIDs more resistant to Sybil attacks than PKI?
8. **Hybrid**: What is the optimal PKI-DID hybrid architecture?
9. **ML**: Can ML-based misbehavior detection improve DID security?
10. **5G**: How does 5G NR-V2X change the DID feasibility calculus?

---

## Deliverables

### For Lab Director Review
1. ✅ Live demo of dashboard with moving vehicles on real map
2. ✅ Comparison table: PKI vs 7 DID methods
3. ✅ Attack scenarios demonstrating security
4. ✅ Publication-quality figures
5. ✅ Integration with existing CVIN-ID-SCs work

### For Thesis
1. Comprehensive experimental results
2. Statistical validation
3. Reproducible experiments
4. Open-source release potential
5. Conference/journal paper draft

---

## Next Steps

Should we:
1. **Implement all of Phase 1** (SUMO, NS-3, dashboard, experiment framework)?
2. **Focus on one killer feature** (e.g., misbehavior detection + DID)?
3. **Prioritize publication angle** (what would make best paper)?

What do you think would most impress your professor? Let's build what matters most first.
