# CV2X Testbed V2 - Complete Implementation Roadmap

**Goal**: Build comprehensive research-grade platform with ALL advanced features

**Timeline**: 2-3 weeks for complete system

---

## 🎯 Master Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WEB DASHBOARD (D)                        │
│  React + WebGL Visualization | Real-time Metrics           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Map View │ │ Metrics  │ │ Security │ │ DID Cost │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│              PYTHON TESTBED CORE                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  SUMO Traffic Simulator (A)                          │  │
│  │  • Real OpenStreetMap (Vancouver/UBC)                │  │
│  │  • TraCI Python integration                          │  │
│  │  • Realistic vehicle movement                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────┴────────────────────────────────┐ │
│  │  V2X Applications (A)                                 │ │
│  │  • Forward Collision Warning (FCW)                    │ │
│  │  • Emergency Electronic Brake Light (EEBL)            │ │
│  │  • Intersection Movement Assist (IMA)                 │ │
│  └──────────────────────────────────────────────────────┘ │
│                         │                                   │
│  ┌──────────────────────┴────────────────────────────────┐ │
│  │  Security Layer (B)                                   │ │
│  │  • Misbehavior Detection                              │ │
│  │  • Attack Simulation (Sybil, Position Falsification)  │ │
│  │  • Privacy Metrics (k-anonymity, unlinkability)       │ │
│  │  • Anomaly Detection (ML-based)                       │ │
│  └──────────────────────────────────────────────────────┘ │
│                         │                                   │
│  ┌──────────────────────┴────────────────────────────────┐ │
│  │  Identity Manager (CORE)                              │ │
│  │  • Modular architecture                               │ │
│  │  • Hot-swappable backends                             │ │
│  │  • Unified metrics                                    │ │
│  └──────────────────────────────────────────────────────┘ │
│           │              │              │                   │
│     ┌─────┴──────┐  ┌───┴────┐  ┌──────┴─────────┐        │
│     │  PKI (v1)  │  │ ERC-   │  │  6 More DIDs   │        │
│     │  Provider  │  │  1056  │  │     (C)        │        │
│     └────────────┘  └────────┘  └────────────────┘        │
│                         │                                   │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────┐
│              BLOCKCHAIN LAYER (C)                           │
│                                                              │
│  Local Development:        Testnets:                        │
│  • Hardhat (1337)          • Sepolia                        │
│  • Ganache                 • Mumbai (Polygon)               │
│                                                              │
│  Smart Contracts (All 7 DID Methods):                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ ERC-1056 │ │ ERC-721  │ │ ERC-725  │ │ ERC-1155 │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│  │ERC-725xy │ │  LSP8    │ │ ERC-4337 │                   │
│  └──────────┘ └──────────┘ └──────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📅 Implementation Timeline

### Week 1: Core Infrastructure (A + C Foundation)

**Days 1-2: SUMO Integration (A.1)**
- Install SUMO
- TraCI Python bindings
- Load OpenStreetMap (Vancouver/UBC area)
- Basic vehicle movement
- Integration with CV2X stack

**Days 3-4: Deploy All DID Contracts (C.1)**
- Adapt remaining 6 contracts from CVIN-ID-SCs
- Deploy all 7 to local Hardhat
- Create providers for each
- Basic comparison test

**Day 5: FCW Foundation (A.2)**
- Implement TTC (Time-To-Collision) algorithm
- BSM-based position tracking
- Warning message generation
- Basic testing

**Deliverable**: Vehicles moving on real map, all DIDs deployed, FCW working

### Week 2: Advanced Features (B + D)

**Days 6-7: Misbehavior Detection (B.1)**
- Position plausibility checks
- Speed/acceleration bounds
- Kalman filter tracking
- Consistency verification

**Days 8-9: Attack Scenarios (B.2)**
- Sybil attack implementation
- Position falsification
- Replay attacks
- Bogus information injection

**Days 10-11: Dashboard Backend (D.1)**
- WebSocket server for real-time updates
- REST API for metrics
- Data streaming architecture
- Backend services

**Day 12: Dashboard Frontend Start (D.2)**
- React setup
- Map integration (Leaflet/MapBox)
- Basic vehicle visualization
- Metrics display

**Deliverable**: Full security layer, dashboard showing live vehicles

### Week 3: Integration & Polish

**Days 13-14: Complete Dashboard (D.3)**
- Message propagation animation
- Attack visualization
- Gas cost graphs
- Interactive controls

**Days 15-16: Full Integration (E)**
- Connect all components
- End-to-end testing
- Performance optimization
- Bug fixes

**Days 17-18: Advanced Features**
- ML anomaly detection
- Privacy metrics (k-anonymity)
- Additional safety apps (EEBL, IMA)
- Documentation

**Days 19-20: Results & Publication**
- Run comprehensive experiments
- Generate publication figures
- Statistical analysis
- Write methodology section

**Day 21: Buffer & Demo Prep**
- Contingency for issues
- Demo scenarios
- Presentation materials

---

## 🏗️ Component Details

### A. SUMO + Safety Applications

#### A.1: SUMO Integration

**Files to Create**:
```
cv2x-testbed/
├── sumo/
│   ├── networks/
│   │   ├── vancouver_ubc.net.xml
│   │   ├── vancouver_ubc.rou.xml
│   │   └── simulation.sumocfg
│   ├── scenarios/
│   │   ├── highway_scenario.py
│   │   ├── urban_scenario.py
│   │   └── intersection_scenario.py
│   └── traci_interface.py
├── applications/
│   ├── __init__.py
│   ├── base_app.py
│   ├── fcw.py              # Forward Collision Warning
│   ├── eebl.py             # Emergency Electronic Brake Light
│   └── ima.py              # Intersection Movement Assist
```

**Key Classes**:
```python
class SUMOInterface:
    def __init__(self, sumo_config)
    def step(self)  # Advance simulation
    def get_vehicle_state(self, vehicle_id) -> VehicleState
    def set_vehicle_speed(self, vehicle_id, speed)
    def spawn_vehicle(self, route, departure_time)

class ForwardCollisionWarning:
    def __init__(self, identity_provider)
    def process_bsm(self, sender_id, bsm)
    def calculate_ttc(self, ego, target) -> float
    def generate_warning(self) -> DENM
```

**SUMO Network**:
- Download Vancouver/UBC area from OpenStreetMap
- Convert with `netconvert`
- Generate traffic with `randomTrips.py`
- Traffic demand: 50-500 vehicles/hour

**Integration**:
```python
sumo = SUMOInterface("sumo/simulation.sumocfg")
cv2x_stack = CV2XStack("V001", identity_manager)
fcw = ForwardCollisionWarning(identity_manager)

while sumo.running:
    # Get vehicle states from SUMO
    for vid in sumo.get_vehicle_ids():
        state = sumo.get_vehicle_state(vid)

        # Send BSM via CV2X
        bsm_msg = create_bsm(state)
        signed_bsm = cv2x_stack.sign_message(vid, bsm_msg)

        # Other vehicles receive and process
        for other in sumo.get_vehicle_ids():
            if fcw.process_bsm(vid, signed_bsm):
                # Warning! Adjust speed in SUMO
                sumo.set_vehicle_speed(other, fcw.safe_speed)

    sumo.step()
```

#### A.2: Safety Applications

**FCW (Forward Collision Warning)**:
```python
TTC = (distance - safe_distance) / relative_speed

if TTC < 2.7 seconds:  # NHTSA threshold
    trigger_warning()
```

**EEBL (Emergency Electronic Brake Light)**:
```python
if deceleration < -4.0 m/s²:  # Hard braking
    broadcast_denm(event_type="emergency_braking")
```

**IMA (Intersection Movement Assist)**:
```python
# Receive SPaT (signal phase & timing)
# Receive MAP (intersection geometry)
# Calculate collision point
if will_collide(ego_trajectory, other_trajectory):
    warn_driver()
```

---

### B. Misbehavior Detection & Security

#### B.1: Misbehavior Detection System

**Files to Create**:
```
cv2x-testbed/
├── security/
│   ├── __init__.py
│   ├── misbehavior_detector.py
│   ├── attacks.py
│   ├── privacy_metrics.py
│   └── models/
│       ├── kalman_filter.py
│       └── anomaly_detector.py  # ML-based
```

**Detection Layers**:

1. **Plausibility Checks**:
```python
class PlausibilityChecker:
    def check_position(self, bsm):
        # Position must be on road network
        if not on_road(bsm.position):
            return False, "Position off road"

    def check_speed(self, bsm):
        # Speed within physical limits
        if bsm.speed > MAX_SPEED:
            return False, "Speed exceeds limit"

    def check_acceleration(self, bsm):
        # Acceleration within vehicle capabilities
        if abs(bsm.acceleration) > MAX_ACCEL:
            return False, "Impossible acceleration"
```

2. **Consistency Checks**:
```python
class ConsistencyChecker:
    def __init__(self):
        self.history = {}  # vehicle_id -> [positions]

    def check_position_consistency(self, vehicle_id, bsm):
        if vehicle_id in self.history:
            prev = self.history[vehicle_id][-1]
            distance = calculate_distance(prev.position, bsm.position)
            time_delta = bsm.timestamp - prev.timestamp

            max_possible = prev.speed * time_delta + 0.5 * MAX_ACCEL * time_delta²

            if distance > max_possible:
                return False, "Position jump"
```

3. **Kalman Filter Tracking**:
```python
class VehicleTracker:
    def __init__(self):
        self.kalman = KalmanFilter(dim_x=4, dim_z=2)

    def predict_position(self, dt):
        self.kalman.predict()
        return self.kalman.x[:2]  # predicted position

    def update(self, measured_position):
        self.kalman.update(measured_position)

    def get_innovation(self):
        # How different is measured vs predicted?
        return np.linalg.norm(self.kalman.y)

    def is_anomalous(self):
        return self.get_innovation() > THRESHOLD
```

4. **ML Anomaly Detection**:
```python
class AnomalyDetector:
    def __init__(self):
        self.autoencoder = load_model('models/autoencoder.h5')

    def detect(self, bsm_sequence):
        # Encode sequence
        features = self.extract_features(bsm_sequence)

        # Reconstruction error
        reconstructed = self.autoencoder.predict(features)
        error = mse(features, reconstructed)

        return error > ANOMALY_THRESHOLD
```

#### B.2: Attack Scenarios

**Attacks to Implement**:

1. **Sybil Attack**:
```python
class SybilAttack:
    """Create multiple fake identities"""

    def __init__(self, num_fake_vehicles=10):
        self.fake_vehicles = []

        for i in range(num_fake_vehicles):
            # Register fake identity
            fake_id = f"SYBIL_{i}"
            credential = identity_provider.register_vehicle(fake_id)
            self.fake_vehicles.append(credential)

    def broadcast_fake_bsms(self):
        for fake in self.fake_vehicles:
            # Create fake BSM at random position
            fake_bsm = create_fake_bsm(random_position())
            signed = sign_with_sybil(fake, fake_bsm)
            broadcast(signed)
```

2. **Position Falsification**:
```python
class PositionFalsificationAttack:
    """Report false position to create phantom traffic jam"""

    def execute(self, attacker_id):
        # Report position 500m ahead on highway
        real_state = get_vehicle_state(attacker_id)
        fake_state = real_state.copy()
        fake_state.position = advance_position(real_state.position, 500)
        fake_state.speed = 0  # Stopped

        fake_bsm = create_bsm(fake_state)
        signed = identity_provider.sign_message(attacker_id, fake_bsm)

        # Other vehicles think there's traffic jam ahead
        broadcast(signed)
```

3. **Replay Attack**:
```python
class ReplayAttack:
    """Replay old messages to confuse receivers"""

    def __init__(self):
        self.captured_messages = []

    def capture(self, message):
        self.captured_messages.append(message)

    def replay(self):
        # Replay old message (should be detected via timestamp)
        old_message = self.captured_messages[0]
        broadcast(old_message)
```

**Detection Effectiveness**:
```python
class AttackDetectionEvaluator:
    def test_sybil_detection(self):
        # Launch Sybil attack
        attack = SybilAttack(num_fake=20)

        # Measure detection time
        start = time.time()
        detected = detector.detect_sybil(attack.fake_vehicles)
        detection_time = time.time() - start

        # Metrics
        return {
            'detection_rate': len(detected) / len(attack.fake_vehicles),
            'detection_time': detection_time,
            'false_positives': count_false_positives()
        }
```

#### B.3: Privacy Metrics

```python
class PrivacyAnalyzer:
    def calculate_k_anonymity(self, vehicle_id, time_window):
        """
        Calculate k-anonymity: minimum size of indistinguishable set
        """
        vehicle_positions = get_positions_in_window(time_window)

        # Find all vehicles in proximity
        nearby = find_nearby_vehicles(vehicle_id, radius=100)

        # k-anonymity is size of nearby set
        return len(nearby)

    def calculate_entropy(self, vehicle_id, messages):
        """
        Calculate information entropy leaked per message
        """
        # Unique identifiers in messages
        unique_ids = count_unique_identifiers(messages)

        # Shannon entropy
        entropy = -sum(p * log2(p) for p in probabilities)
        return entropy

    def measure_unlinkability(self, vehicle_id, pseudonym_changes):
        """
        Measure how well pseudonym changes prevent tracking
        """
        # Try to link pseudonyms
        linked = attempt_linking(pseudonym_changes)

        # Unlinkability score (0-1, higher is better)
        return 1 - (len(linked) / len(pseudonym_changes))

    def tracking_resistance(self, vehicle_id, duration):
        """
        How long can vehicle be tracked continuously?
        """
        start = time.time()

        while can_track(vehicle_id):
            time.sleep(0.1)
            if time.time() - start > duration:
                break

        return time.time() - start
```

---

### C. All 7 DID Methods

#### C.1: Contract Deployment

**Contracts to Deploy**:

1. ✅ **ERC-1056** (Already done)
2. **ERC-721** (NFT-based unique identity)
3. **ERC-725** (Proxy account)
4. **ERC-1155** (Multi-token)
5. **ERC-725x,y** (Enhanced proxy)
6. **LSP8** (LUKSO Standard)
7. **ERC-4337** (Account abstraction)

**Deployment Script**:
```javascript
// scripts/deploy_all_dids.js

async function main() {
  console.log("Deploying all 7 DID contracts...\n");

  const contracts = [
    "ERC1056Registry",
    "ERC721DID",
    "ERC725Identity",
    "ERC1155DID",
    "ERC725xyIdentity",
    "LSP8DID",
    "ERC4337Account"
  ];

  const deployments = {};

  for (const contractName of contracts) {
    console.log(`Deploying ${contractName}...`);

    const Contract = await ethers.getContractFactory(contractName);
    const contract = await Contract.deploy();
    await contract.waitForDeployment();

    const address = await contract.getAddress();
    deployments[contractName] = address;

    console.log(`  ✓ ${contractName}: ${address}\n`);
  }

  // Save all addresses
  fs.writeFileSync(
    'deployments/all_dids.json',
    JSON.stringify(deployments, null, 2)
  );
}
```

#### C.2: Comparison Framework

**Metrics to Compare**:

| Metric | ERC-1056 | ERC-721 | ERC-725 | ERC-1155 | 725xy | LSP8 | 4337 |
|--------|----------|---------|---------|----------|-------|------|------|
| Gas: Deploy | | | | | | | |
| Gas: Register | | | | | | | |
| Gas: Update | | | | | | | |
| Gas: Revoke | | | | | | | |
| Latency: Register | | | | | | | |
| Latency: Verify | | | | | | | |
| Features: Key Rotation | | | | | | | |
| Features: Delegation | | | | | | | |
| Features: Recovery | | | | | | | |
| Privacy: Pseudonyms | | | | | | | |
| Scalability: TPS | | | | | | | |

**Comparison Test**:
```python
# scripts/compare_all_dids.py

def compare_all_dids():
    manager = IdentityManager()

    # Load all 7 DID providers
    with open('deployments/all_dids.json') as f:
        contracts = json.load(f)

    providers = [
        ERC1056Provider(contract_address=contracts['ERC1056Registry']),
        ERC721Provider(contract_address=contracts['ERC721DID']),
        ERC725Provider(contract_address=contracts['ERC725Identity']),
        # ... etc
    ]

    for provider in providers:
        manager.register_provider(provider)

    # Run benchmarks on all
    benchmark = IdentityBenchmark(manager)
    results = benchmark.run_full_benchmark_suite()

    # Generate comparison table
    generate_comparison_table(results)
```

---

### D. Real-Time Web Dashboard

#### D.1: Architecture

```
Frontend (React):          Backend (Python):
┌─────────────────┐       ┌─────────────────┐
│  React App      │◄─────►│  FastAPI Server │
│  ├─ Map View    │  WS   │  ├─ WebSocket   │
│  ├─ Metrics     │       │  ├─ REST API    │
│  ├─ Controls    │       │  └─ Data Stream │
│  └─ Visualizer  │       └─────────┬───────┘
└─────────────────┘                 │
                                    ▼
                          ┌─────────────────┐
                          │ Testbed Core    │
                          │ (Simulation)    │
                          └─────────────────┘
```

#### D.2: Backend

**Files to Create**:
```
cv2x-testbed/
├── dashboard/
│   ├── backend/
│   │   ├── server.py          # FastAPI server
│   │   ├── websocket.py       # WebSocket handler
│   │   ├── api.py             # REST endpoints
│   │   └── streamer.py        # Data streaming
│   └── frontend/
│       ├── package.json
│       ├── src/
│       │   ├── App.js
│       │   ├── components/
│       │   │   ├── MapView.js
│       │   │   ├── MetricsPanel.js
│       │   │   ├── SecurityView.js
│       │   │   └── ControlPanel.js
│       │   └── hooks/
│       │       ├── useWebSocket.js
│       │       └── useVehicles.js
│       └── public/
```

**Backend Implementation**:
```python
# dashboard/backend/server.py

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json

app = FastAPI()

# CORS for React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
active_connections: List[WebSocket] = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)

    try:
        while True:
            # Stream simulation data
            data = {
                'vehicles': get_vehicle_positions(),
                'messages': get_recent_messages(),
                'metrics': get_current_metrics(),
                'attacks': get_active_attacks(),
                'gas_costs': get_gas_costs()
            }

            await websocket.send_json(data)
            await asyncio.sleep(0.1)  # 10 Hz update

    except:
        active_connections.remove(websocket)

@app.get("/api/metrics/summary")
def get_metrics_summary():
    return {
        'total_vehicles': simulation.vehicle_count,
        'messages_sent': simulation.message_count,
        'attacks_detected': security.attack_count,
        'avg_latency': metrics.avg_latency_ms
    }

@app.get("/api/did/comparison")
def get_did_comparison():
    return comparison_results.to_dict()

@app.post("/api/attack/trigger/{attack_type}")
def trigger_attack(attack_type: str):
    if attack_type == "sybil":
        attack = SybilAttack(num_fake=10)
        attack.execute()
    elif attack_type == "position_falsification":
        attack = PositionFalsificationAttack()
        attack.execute()

    return {"status": "attack_launched", "type": attack_type}
```

#### D.3: Frontend

**Map View Component**:
```javascript
// dashboard/frontend/src/components/MapView.js

import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Circle } from 'react-leaflet';
import useWebSocket from '../hooks/useWebSocket';

function MapView() {
  const { vehicles, messages } = useWebSocket('ws://localhost:8000/ws');

  return (
    <MapContainer center={[49.2827, -123.1207]} zoom={13}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Render vehicles */}
      {vehicles.map(vehicle => (
        <Marker
          key={vehicle.id}
          position={[vehicle.lat, vehicle.lon]}
          icon={getVehicleIcon(vehicle.type)}
        />
      ))}

      {/* Render communication range */}
      {vehicles.map(vehicle => (
        <Circle
          key={`range-${vehicle.id}`}
          center={[vehicle.lat, vehicle.lon]}
          radius={300}  // 300m V2X range
          pathOptions={{ color: 'blue', fillOpacity: 0.1 }}
        />
      ))}

      {/* Animate message propagation */}
      {messages.map(msg => (
        <MessagePropagation key={msg.id} message={msg} />
      ))}
    </MapContainer>
  );
}
```

**Metrics Panel**:
```javascript
// dashboard/frontend/src/components/MetricsPanel.js

import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

function MetricsPanel({ metrics }) {
  return (
    <div className="metrics-panel">
      <h2>Performance Metrics</h2>

      {/* Latency Graph */}
      <div className="metric-card">
        <h3>Authentication Latency</h3>
        <LineChart width={400} height={200} data={metrics.latency_history}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="pki" stroke="#8884d8" name="PKI" />
          <Line type="monotone" dataKey="did" stroke="#82ca9d" name="DID" />
        </LineChart>
      </div>

      {/* Gas Costs */}
      <div className="metric-card">
        <h3>DID Gas Costs</h3>
        <div className="cost-display">
          <div>Registration: ${metrics.gas_costs.registration.toFixed(4)}</div>
          <div>Verification: ${metrics.gas_costs.verification.toFixed(4)}</div>
          <div>Revocation: ${metrics.gas_costs.revocation.toFixed(4)}</div>
        </div>
      </div>

      {/* PDR */}
      <div className="metric-card">
        <h3>Packet Delivery Ratio</h3>
        <div className="pdr-value">
          {(metrics.pdr * 100).toFixed(1)}%
        </div>
      </div>
    </div>
  );
}
```

**Security View**:
```javascript
// dashboard/frontend/src/components/SecurityView.js

function SecurityView({ attacks, detections }) {
  return (
    <div className="security-view">
      <h2>Security Monitor</h2>

      {/* Attack Controls */}
      <div className="attack-controls">
        <h3>Attack Simulation</h3>
        <button onClick={() => triggerAttack('sybil')}>
          Launch Sybil Attack
        </button>
        <button onClick={() => triggerAttack('position_falsification')}>
          Position Falsification
        </button>
        <button onClick={() => triggerAttack('replay')}>
          Replay Attack
        </button>
      </div>

      {/* Detection Log */}
      <div className="detection-log">
        <h3>Misbehavior Detections</h3>
        {detections.map(detection => (
          <div key={detection.id} className="detection-item">
            <span className="timestamp">{detection.timestamp}</span>
            <span className="vehicle">{detection.vehicle_id}</span>
            <span className="type">{detection.attack_type}</span>
            <span className="severity">{detection.severity}</span>
          </div>
        ))}
      </div>

      {/* Heatmap of attacks */}
      <div className="attack-heatmap">
        <h3>Attack Locations</h3>
        {/* Render heatmap overlay on map */}
      </div>
    </div>
  );
}
```

---

## 📊 Integration Points

### How Components Connect:

1. **SUMO → CV2X Stack**:
   ```python
   vehicle_state = sumo.get_vehicle_state(vid)
   bsm = cv2x_stack.send_bsm(vehicle_state)
   ```

2. **CV2X Stack → Identity Manager**:
   ```python
   signed_message = identity_manager.sign_message(vid, bsm)
   is_valid, metrics = identity_manager.verify_message(signed_message)
   ```

3. **Identity Manager → Security Layer**:
   ```python
   if not security.check_plausibility(bsm):
       security.flag_misbehavior(vid)
   ```

4. **Security Layer → Dashboard**:
   ```python
   websocket.broadcast({
       'type': 'misbehavior_detected',
       'vehicle': vid,
       'attack': 'position_falsification'
   })
   ```

5. **Dashboard → User**:
   ```javascript
   // Real-time visualization of detected attack
   showAttackAlert(attackData)
   ```

---

## 🎯 Success Criteria

### Technical:
- ✅ All 7 DID contracts deployed and tested
- ✅ Vehicles moving on real OpenStreetMap
- ✅ FCW preventing collisions in real-time
- ✅ Sybil attack detected within 5 seconds
- ✅ Dashboard showing live simulation
- ✅ Comparison table with all DID methods

### Research:
- ✅ Can answer: "Which DID is best for V2X?" with data
- ✅ Can show: DID overhead impact on FCW performance
- ✅ Can prove: DID better against Sybil than PKI
- ✅ Can quantify: Privacy metrics for each approach

### Demo:
- ✅ Live dashboard with 50+ vehicles on Vancouver map
- ✅ Launch attack, see detection in real-time
- ✅ Switch between PKI/DID, compare performance
- ✅ Publication-ready figures generated automatically

---

## 🚀 Getting Started (Now)

While you check with your professor, I'll start building:

**Option 1**: Start SUMO foundation (most critical path)
**Option 2**: Deploy remaining 6 DID contracts (independent task)
**Option 3**: Build dashboard backend skeleton (can parallelize)

What should I start with while you consult your professor?

Or should I wait for their input on priorities?

---

**Total Estimated Time**: 15-21 days for complete platform
**Can be parallelized**: Yes, components are modular
**Risk**: SUMO setup can be tricky on some systems

What do you want me to build first? 🚀
