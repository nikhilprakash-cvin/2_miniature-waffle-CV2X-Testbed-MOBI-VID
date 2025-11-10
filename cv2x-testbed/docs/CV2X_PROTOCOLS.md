# CV2X Protocol Implementation Guide

## Overview

Cellular Vehicle-to-Everything (CV2X) is a 3GPP-standardized technology enabling vehicles to communicate with each other and infrastructure using cellular networks.

## CV2X Protocol Stack

### Physical Layer (Layer 1)

```
┌─────────────────────────────────────┐
│      Application Layer (V2X)       │
├─────────────────────────────────────┤
│         PDCP/RLC/MAC Layers        │
├─────────────────────────────────────┤
│      Physical Layer (LTE/5G)       │
└─────────────────────────────────────┘
```

### Communication Modes

#### Mode 3: Network-Assisted
- Resource allocation controlled by eNodeB/gNB
- Better for areas with good cellular coverage
- Lower latency variance
- Requires V2N connection

#### Mode 4: Autonomous
- Vehicles select their own resources
- Distributed sensing and resource allocation
- Works without infrastructure
- Critical for safety applications

## Message Types

### 1. Basic Safety Message (BSM) / CAM

**Purpose**: Periodic broadcast of vehicle status

**Frequency**: 1-10 Hz (typically 10 Hz for safety)

**Contents**:
```
BSM {
  msgID: "BasicSafetyMessage",
  timestamp: <current_time>,
  position: {
    latitude: <lat>,
    longitude: <lon>,
    elevation: <elev>
  },
  speed: <speed_m/s>,
  heading: <degrees>,
  acceleration: {
    longitudinal: <m/s²>,
    lateral: <m/s²>
  },
  vehicleSize: {
    length: <meters>,
    width: <meters>
  },
  vehicleID: <pseudonym>  // Privacy-preserving identifier
}
```

### 2. Decentralized Environmental Notification Message (DENM)

**Purpose**: Event-triggered warning messages

**Trigger Conditions**:
- Emergency braking
- Road hazard detection
- Accident notification
- Weather warnings

**Contents**:
```
DENM {
  msgID: "DENM",
  timestamp: <event_time>,
  eventType: <hazard_type>,
  position: {
    latitude: <lat>,
    longitude: <lon>
  },
  relevanceArea: {
    radius: <meters>,
    duration: <seconds>
  },
  severity: <critical|high|medium|low>,
  description: <event_details>
}
```

### 3. Cooperative Perception Message (CPM)

**Purpose**: Share sensor data about detected objects

**Use Case**: Extend perception beyond line-of-sight

## PC5 Interface (V2V Direct Communication)

### Resource Allocation

**Sensing-Based Semi-Persistent Scheduling (SB-SPS)**:
1. Vehicle senses available resources in resource pool
2. Randomly selects subset of resources with lowest interference
3. Reserves resources for periodic transmission
4. Monitors CBR and adjusts transmission parameters

### Physical Resource Blocks

```
Frequency
    ↑
    │ [PRB_n] [PRB_n] [PRB_n]
    │ [PRB_2] [PRB_2] [PRB_2]
    │ [PRB_1] [PRB_1] [PRB_1]
    │ [PRB_0] [PRB_0] [PRB_0]
    └────────────────────────→ Time
         Subframe_i  i+1  i+2
```

### Channel Access

- **Carrier Sensing**: Check CBR before transmission
- **Power Control**: Adjust TX power based on distance
- **Priority Handling**: Safety messages get highest priority

## Implementation Architecture

### Component Structure

```python
class CV2XStack:
    """CV2X Protocol Stack Implementation"""

    def __init__(self):
        self.phy_layer = PhysicalLayer()
        self.mac_layer = MACLayer()
        self.app_layer = ApplicationLayer()
        self.identity_mgr = IdentityManager()

    def send_bsm(self, vehicle_state):
        """Send Basic Safety Message"""
        # 1. Create BSM from vehicle state
        bsm = self.create_bsm(vehicle_state)

        # 2. Sign message with identity credential
        signed_msg = self.identity_mgr.sign(bsm)

        # 3. MAC layer resource allocation
        resources = self.mac_layer.allocate_resources()

        # 4. PHY layer transmission
        self.phy_layer.transmit(signed_msg, resources)

    def receive_message(self):
        """Receive and process V2X message"""
        # 1. PHY layer reception
        raw_msg = self.phy_layer.receive()

        # 2. MAC layer processing
        decoded_msg = self.mac_layer.decode(raw_msg)

        # 3. Verify message authenticity
        if self.identity_mgr.verify(decoded_msg):
            # 4. Application processing
            self.app_layer.process(decoded_msg)
```

## Security Requirements

### Message Authentication

**Standard Approach (IEEE 1609.2)**:
- ECDSA signatures (256-bit)
- Certificate chain verification
- Pseudonym certificates for privacy

**DID Approach (Research)**:
- Verifiable Credentials
- DID document resolution
- On-chain or off-chain verification

### Privacy Protection

**Pseudonym Certificates**:
- Short-lived certificates (5 minutes typical)
- Frequently changed to prevent tracking
- Certificate pool managed by CA

**Comparison with DIDs**:
- DID rotation mechanisms
- Privacy-preserving verification
- Correlation resistance

## Performance Requirements

### Latency
- **End-to-End Delay**: < 100 ms (safety-critical)
- **Authentication**: < 5 ms per message

### Reliability
- **PDR**: > 90% within 150m
- **Range**: Up to 300m for V2V

### Scalability
- Support 1000+ vehicles per km²
- Handle 10 Hz BSM rate per vehicle

## Test Scenarios

### 1. Forward Collision Warning
```python
scenario = {
    "name": "Forward Collision Warning",
    "vehicles": 2,
    "initial_speed": [80, 40],  # km/h
    "distance": 50,  # meters
    "event": "sudden_brake",
    "expected": "warning_received < 100ms"
}
```

### 2. Intersection Collision Avoidance
```python
scenario = {
    "name": "Intersection Collision",
    "vehicles": 4,
    "topology": "cross_intersection",
    "traffic_light": "present",
    "expected": "collision_avoided"
}
```

## Integration with Identity Systems

### Standard PKI Flow
```
1. Vehicle → CA: Request certificate
2. CA → Vehicle: Issue pseudonym certificates
3. Vehicle → Other: Send signed BSM
4. Other → CRL: Check revocation
5. Other: Verify signature
```

### DID/SSI Flow (Research)
```
1. Vehicle → Blockchain: Register DID
2. Vehicle → IPFS/Blockchain: Publish DID Document
3. Vehicle → Other: Send BSM with DID
4. Other → Blockchain: Resolve DID Document
5. Other: Verify using public key from DID Doc
```

## Metrics Collection

```python
metrics = {
    "communication": {
        "pdr": [],          # Packet Delivery Ratio
        "latency": [],      # End-to-end delay
        "cbr": [],          # Channel Busy Ratio
    },
    "identity": {
        "auth_time": [],    # Authentication time
        "cred_size": [],    # Credential size
        "resolution_time": [], # DID resolution time
    },
    "resource": {
        "cpu": [],
        "memory": [],
        "bandwidth": []
    }
}
```

## Next Steps

1. Implement basic CV2X stack
2. Deploy standard PKI infrastructure
3. Create test scenarios
4. Collect baseline metrics
5. Integrate DID system
6. Comparative analysis

## References

- 3GPP TS 36.213: Physical layer procedures (LTE)
- 3GPP TS 23.285: Architecture enhancements for V2X
- SAE J2735: V2V Message Set Dictionary
- IEEE 1609.2: Security Services
