# CV2X TESTBED - REALISTIC ROADMAP
# Connected Vehicle Identity & Communication Integration

**Date**: 2025-11-10
**Version**: 2.0 - Realistic Scenarios Focus
**Status**: Active Development

---

## 🎯 MISSION

Build a comprehensive testbed that demonstrates how **vehicle identity systems** (centralized PKI vs blockchain-based MOBI VID) integrate with **real CV2X protocols** for safety-critical connected vehicle applications.

---

## 📊 CURRENT STATUS

### ✅ COMPLETED (Phases 1-3)

**Phase 1: Identity Systems** ✅
- MOBI VID I (Birth Certificates)
- MOBI VID II (Lifecycle Events)
- W3C Verifiable Credentials
- Centralized Vehicle Registry
- 89.6% W3C compliance achieved

**Phase 2: CV2X Protocol Stack** ✅
- Basic CV2X stack implementation
- PKI-based identity provider
- IEEE 1609.2 compliance
- Message signing/verification

**Phase 3: Comparison Framework** ✅
- Performance benchmarking tools
- Use case automation (5/10 scenarios)
- Comparison test suite
- W3C compliance checker

---

## 🚀 ROADMAP - REALISTIC SCENARIOS

### PHASE 4: SUMO Traffic Simulation Integration (Week 1)
**Goal**: Integrate realistic traffic simulation with identity systems

#### Tasks:
1. **SUMO/TraCI Setup** (2 days)
   - Install SUMO traffic simulator
   - Set up TraCI Python interface
   - Create realistic road network (highway + intersection)
   - Define vehicle types (cars, trucks, emergency)

2. **Vehicle Fleet with Identity** (2 days)
   - Spawn 50 vehicles in SUMO
   - Each vehicle gets MOBI VID or PKI certificate
   - Map SUMO vehicles to identity providers
   - Track vehicle state (position, speed, etc.)

3. **Basic V2V Scenarios** (2 days)
   - Forward Collision Warning (FCW)
   - Emergency Electronic Brake Light (EEBL)
   - Intersection Movement Assist (IMA)
   - All messages signed with vehicle identity

4. **Metrics Collection** (1 day)
   - Message latency
   - Verification time
   - Identity resolution time
   - Safety event detection rate

**Deliverables**:
- SUMO network with 50 vehicles
- V2V safety apps with identity verification
- Performance metrics dashboard
- Comparison: PKI vs MOBI VID latency

---

### PHASE 5: Safety-Critical Use Cases (Week 2)
**Goal**: Implement and test real-world safety scenarios

#### Scenario 1: Highway Emergency Chain (Priority: HIGH)
**Description**: Multi-vehicle emergency brake propagation

**Actors**:
- 10 vehicles in platoon formation
- Lead vehicle detects obstacle
- Chain reaction of brake warnings

**Identity Role**:
- Verify emergency message authenticity
- Prevent spoofed warnings (Sybil attack)
- Track message propagation through trust chain

**Success Criteria**:
- Message verified in <10ms
- 100% authentic message delivery
- Zero false alarms from untrusted vehicles

**Test**:
```python
def test_highway_emergency_chain():
    # Setup 10 vehicles with verified identities
    vehicles = spawn_verified_vehicles(10, identity_type="MOBI_VID")

    # Lead vehicle detects emergency
    vehicles[0].emergency_brake()

    # Propagate warning
    for i, vehicle in enumerate(vehicles[1:]):
        # Receive warning from vehicle ahead
        warning = vehicle.receive_message()

        # Verify sender identity (CRITICAL)
        is_verified = verify_mobi_vid(warning.sender)

        if is_verified:
            # Take action
            vehicle.emergency_brake()
            vehicle.broadcast_warning()  # Continue chain

        # Measure latency
        assert warning.latency < 10ms  # Safety requirement
```

#### Scenario 2: Intersection Collision Avoidance (Priority: HIGH)
**Description**: Prevent T-bone collisions at intersection

**Actors**:
- 4-way intersection with traffic lights
- Multiple vehicles approaching from all directions
- One vehicle runs red light (emergency vehicle or malfunction)

**Identity Role**:
- Verify vehicle positions
- Authenticate emergency vehicle status
- Prevent position spoofing attacks

**Implementation**:
```python
class IntersectionManager:
    def __init__(self):
        self.vehicles_in_range = {}
        self.verified_identities = {}

    def vehicle_approaching(self, vehicle):
        # Verify vehicle identity
        birth_cert = verify_mobi_vid_birth_certificate(vehicle.id)

        if birth_cert:
            self.verified_identities[vehicle.id] = birth_cert

            # Check for collision risk
            risk = self.calculate_collision_risk(vehicle)

            if risk > THRESHOLD:
                # Warn all verified vehicles
                self.broadcast_collision_warning(vehicle.id, risk)

    def broadcast_collision_warning(self, vehicle_id, risk):
        warning = {
            'type': 'IMA_WARNING',
            'source_vehicle': vehicle_id,
            'mobi_vid_cert': self.verified_identities[vehicle_id],
            'risk_level': risk,
            'timestamp': time.time()
        }

        # Sign with infrastructure's certificate
        signed_warning = self.sign_message(warning)

        # Broadcast to all approaching vehicles
        for v in self.vehicles_in_range.values():
            v.receive(signed_warning)
```

#### Scenario 3: Truck Platooning with Fleet Management (Priority: MEDIUM)
**Description**: Coordinated truck platoons with centralized fleet tracking

**Actors**:
- Fleet of 5 trucks (same company)
- Fleet manager (centralized system)
- Highway infrastructure

**Identity Role**:
- Verify all trucks belong to same fleet
- Track platoon formation/breakup
- Audit fuel efficiency gains

**Comparison Point**:
- **Centralized**: Fleet manager has direct access to all vehicle data
- **MOBI VID**: Fleet manager must request Verifiable Presentations

**Test Metrics**:
- Platoon formation time
- V2V message overhead
- Fleet manager query latency
- Privacy: Can competitors see data?

#### Scenario 4: Emergency Vehicle Priority (Priority: HIGH)
**Description**: Ambulance requests right-of-way

**Actors**:
- Ambulance (emergency vehicle)
- 20 surrounding vehicles
- Traffic light controllers

**Identity Role**:
- Verify emergency vehicle credentials
- Prevent fake emergency vehicles
- Prioritize intersection passage

**Critical Security**:
```python
class EmergencyVehicleVerifier:
    def verify_emergency_status(self, vehicle_id):
        # Step 1: Verify MOBI VID birth certificate
        birth_cert = blockchain.get_birth_certificate(vehicle_id)

        if not birth_cert:
            return False, "Birth certificate not found"

        # Step 2: Check manufacturer authorization for emergency vehicles
        if birth_cert.manufacturer not in APPROVED_EMERGENCY_MANUFACTURERS:
            return False, "Not authorized emergency manufacturer"

        # Step 3: Verify current registration with government
        registration = government_registry.check_registration(vehicle_id)

        if registration.vehicle_type != "EMERGENCY":
            return False, "Not registered as emergency vehicle"

        # Step 4: Check for active emergency status (optional)
        # Could query dispatch system

        return True, "Verified emergency vehicle"
```

#### Scenario 5: Misbehavior Detection (Priority: HIGH)
**Description**: Detect and report malicious vehicles

**Misbehavior Types**:
- Position falsification
- Speed falsification
- Phantom vehicle attacks
- Sybil attacks (fake identities)

**Detection with MOBI VID**:
```python
class MisbehaviorDetector:
    def detect_position_falsification(self, vehicle_messages):
        """Detect if vehicle is lying about position"""

        # Collect messages from suspected vehicle
        positions = [msg.position for msg in vehicle_messages]

        # Check physical plausibility
        for i in range(1, len(positions)):
            distance = calculate_distance(positions[i-1], positions[i])
            time_delta = vehicle_messages[i].timestamp - vehicle_messages[i-1].timestamp
            speed = distance / time_delta

            # If claimed speed exceeds physical limits
            if speed > MAX_VEHICLE_SPEED:
                # Report misbehavior with proof
                report = {
                    'vehicle_id': vehicle_messages[0].vehicle_id,
                    'mobi_vid': vehicle_messages[0].mobi_vid_cert,
                    'misbehavior_type': 'POSITION_FALSIFICATION',
                    'evidence': {
                        'impossible_speed': speed,
                        'messages': vehicle_messages[i-1:i+1]
                    }
                }

                # With MOBI VID: Can ban vehicle permanently
                # Birth certificate allows tracking across re-registrations
                self.report_to_authority(report)
```

---

### PHASE 6: Large-Scale Simulation (Week 3)
**Goal**: Test at scale with realistic scenarios

#### Large-Scale Tests:

**Test 1: Urban Congestion (100 vehicles)**
- Downtown grid with traffic lights
- Mix of vehicle types
- Peak hour traffic patterns

**Metrics**:
- Identity verification under load
- Message throughput (BSM rate)
- Collision avoidance effectiveness
- Centralized vs Blockchain performance gap

**Test 2: Highway Traffic (200 vehicles)**
- 10km highway segment
- 65 mph average speed
- Lane changes, merges, exits

**Metrics**:
- FCW detection rate
- EEBL propagation time
- Platooning stability
- Identity resolution latency

**Test 3: Mixed Network (50 PKI + 50 MOBI VID)**
- Half vehicles use PKI, half use MOBI VID
- Test interoperability
- Measure trust differences

**Key Question**: Do MOBI VID vehicles trust PKI vehicles equally?

---

### PHASE 7: Attack Scenarios (Week 4)
**Goal**: Test security of identity systems

#### Attack 1: Sybil Attack
**Description**: Attacker creates multiple fake identities

**Without MOBI VID**:
- Attacker can generate unlimited certificates
- Can fake traffic congestion
- Can manipulate routing

**With MOBI VID**:
- Each vehicle has blockchain-anchored birth certificate
- VIN is unique and traceable
- Manufacturer authorization required
- **Result**: Sybil attack prevented

**Test**:
```python
def test_sybil_attack():
    # Attacker tries to create 100 fake vehicles
    attacker = MaliciousActor()

    # Without MOBI VID (PKI only)
    fake_vehicles_pki = attacker.create_fake_vehicles_pki(100)
    assert len(fake_vehicles_pki) == 100  # Easy to fake

    # With MOBI VID
    try:
        fake_vehicles_mobi = attacker.create_fake_vehicles_mobi(100)
        assert False, "Should not be able to create fake MOBI VIDs"
    except UnauthorizedManufacturerError:
        pass  # Expected - cannot fake birth certificates
```

#### Attack 2: Position Falsification
**Description**: Vehicle lies about position to game system

**Test with Identity Tracking**:
```python
def test_position_tracking():
    # Vehicle claims to be in two places
    vehicle = spawn_vehicle(identity_type="MOBI_VID")

    vehicle.broadcast_position(lat=37.7749, lon=-122.4194)
    time.sleep(1)
    vehicle.broadcast_position(lat=37.8749, lon=-122.5194)  # 10km away in 1 second

    # Misbehavior detection
    detector = MisbehaviorDetector()
    is_misbehaving = detector.check_plausibility(vehicle.messages)

    assert is_misbehaving == True

    # With MOBI VID: Report to blockchain
    # Vehicle's birth certificate allows permanent ban
    report = detector.create_misbehavior_report(vehicle.mobi_vid)
    blockchain.report_misbehavior(report)

    # All future messages from this vehicle are marked suspicious
```

#### Attack 3: Replay Attack
**Description**: Attacker captures and replays old messages

**Prevention with Timestamps**:
```python
def verify_message_freshness(message):
    current_time = time.time()
    message_age = current_time - message.timestamp

    # Reject messages older than 1 second (V2V requirement)
    if message_age > 1.0:
        return False, "Message too old - potential replay attack"

    # With MOBI VID: Can also check message sequence numbers
    # Birth certificate allows tracking message history

    return True, "Message is fresh"
```

---

### PHASE 8: Real-World Integration (Weeks 5-6)
**Goal**: Connect to real vehicle hardware (if available)

#### Integration Points:

**1. OBD-II Interface**
- Read real vehicle data (speed, RPM, fuel)
- Link physical vehicle to MOBI VID
- Test identity with actual CAN bus messages

**2. V2X Hardware (if available)**
- Real RSU (Roadside Unit) integration
- Actual V2X radios
- Measure real-world latency

**3. Cloud Integration**
- Connect to fleet management cloud
- Real-time monitoring dashboard
- Centralized vs blockchain performance comparison

---

## 🎯 KEY MILESTONES

| Milestone | Description | Target Date | Status |
|-----------|-------------|-------------|---------|
| M1: Identity Systems | MOBI VID + Centralized Complete | ✅ Complete | DONE |
| M2: W3C Compliance | 85%+ compliance | ✅ Complete | DONE (89.6%) |
| M3: SUMO Integration | 50 vehicles simulated | Week 1 | PENDING |
| M4: Safety Apps | FCW, EEBL, IMA working | Week 2 | PENDING |
| M5: Large Scale | 200 vehicles tested | Week 3 | PENDING |
| M6: Security Testing | Attack scenarios validated | Week 4 | PENDING |
| M7: Real Hardware | OBD-II integration | Week 6 | OPTIONAL |

---

## 📈 SUCCESS CRITERIA

### Performance Requirements:
- ✅ BSM signing: <100ms (for 10 Hz requirement)
- ✅ BSM verification: <10ms (real-time requirement)
- 🎯 Identity resolution: <50ms
- 🎯 SUMO integration: 50+ vehicles at 60 FPS
- 🎯 Safety app latency: <100ms end-to-end

### Security Requirements:
- ✅ Prevent Sybil attacks (MOBI VID)
- 🎯 Detect position falsification (>95% accuracy)
- 🎯 Prevent replay attacks (100%)
- 🎯 Misbehavior reporting functional

### Comparison Metrics:
- 🎯 Centralized vs MOBI VID performance gap quantified
- 🎯 Privacy analysis complete
- 🎯 Cost analysis complete
- 🎯 Trust model comparison documented

---

## 🔬 RESEARCH QUESTIONS

1. **Performance**: How much slower is blockchain identity vs centralized?
   - Hypothesis: 10-100x slower for writes, similar for reads
   - Test: Measure under load

2. **Security**: Does MOBI VID prevent more attacks than PKI?
   - Hypothesis: Yes, prevents Sybil and improves misbehavior tracking
   - Test: Implement attack scenarios

3. **Privacy**: Does blockchain expose more data than centralized?
   - Hypothesis: No, VIN encryption prevents exposure
   - Test: Analyze what adversary can learn

4. **Scalability**: Can MOBI VID handle 1000s of vehicles?
   - Hypothesis: Off-chain caching enables scale
   - Test: Large-scale simulation

5. **Trust**: Do drivers trust blockchain more than central authority?
   - Hypothesis: Yes, especially for used car sales
   - Test: User study (future work)

---

## 🛠️ IMPLEMENTATION PRIORITIES

### IMMEDIATE (This Week):
1. ✅ Run comparison test suite
2. ✅ Run use case automation (5 scenarios)
3. ✅ Run W3C compliance checker
4. 🎯 Fix any W3C compliance gaps
5. 🎯 Start SUMO installation

### SHORT-TERM (Week 1-2):
1. SUMO/TraCI integration
2. 50-vehicle simulation
3. Implement FCW, EEBL, IMA
4. Collect performance metrics
5. Create real-time dashboard

### MEDIUM-TERM (Week 3-4):
1. Scale to 200 vehicles
2. Implement attack scenarios
3. Complete security testing
4. Write comparison report
5. Create demo video

### LONG-TERM (Week 5-6):
1. Real hardware integration (optional)
2. Cloud deployment
3. Public testbed access
4. Academic paper writeup
5. Open-source release

---

## 📊 DELIVERABLES

### Code Deliverables:
- ✅ MOBI VID smart contracts (VID I + VID II)
- ✅ W3C Verifiable Credentials library
- ✅ Centralized vehicle registry
- ✅ Comparison test suite
- ✅ Use case automation
- 🎯 SUMO integration scripts
- 🎯 Safety application implementations
- 🎯 Attack scenario implementations

### Documentation Deliverables:
- ✅ W3C compliance report (89.6%)
- ✅ Use case descriptions (10 scenarios)
- ✅ Comparison framework design
- 🎯 Performance benchmark results
- 🎯 Security analysis report
- 🎯 Integration guide
- 🎯 Academic paper (optional)

### Demonstration Deliverables:
- ✅ W3C compliance checker output
- 🎯 Live SUMO simulation demo
- 🎯 Safety app demonstration videos
- 🎯 Attack scenario demonstrations
- 🎯 Real-time dashboard
- 🎯 Comparison visualization

---

## 🎓 EDUCATIONAL VALUE

This testbed is valuable for:

1. **Research**: Novel combination of vehicle identity + V2X protocols
2. **Teaching**: Demonstrates real-world SSI applications
3. **Industry**: Shows practical blockchain use case
4. **Standardization**: Informs MOBI VID development
5. **Security**: Tests attack scenarios

---

## 🔄 ITERATION PLAN

After each phase:
1. Run all tests
2. Collect metrics
3. Update comparison report
4. Identify gaps
5. Iterate

After complete implementation:
1. Write academic paper
2. Present to professor
3. Open-source release
4. Demo to industry partners

---

## 📞 STAKEHOLDER REVIEW

**Weekly Reviews**:
- Professor: Weekly progress updates
- Team: Daily standups
- Demo: Every 2 weeks

**Final Review**:
- Complete demonstration
- Performance comparison
- Security analysis
- Recommendations

---

## 🏁 DEFINITION OF DONE

Project complete when:
- ✅ All identity systems implemented
- ✅ W3C compliance >85%
- 🎯 SUMO simulation working (50+ vehicles)
- 🎯 3 safety apps demonstrated
- 🎯 Attack scenarios tested
- 🎯 Comparison report written
- 🎯 Demo video created
- 🎯 Code documented and open-sourced

**Current Completion**: 40% (Phase 1-3 done)

---

**NEXT ACTION**: Run test suites and start SUMO integration!
