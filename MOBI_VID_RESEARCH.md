# MOBI VID RESEARCH DOCUMENT
## Comprehensive Analysis of MOBI VID Standards

**Research Completed**: 2025-11-10
**Status**: COMPLETE ✅
**Sources**: MOBI official announcements, W3C specifications, industry publications

---

## 📋 EXECUTIVE SUMMARY

MOBI (Mobility Open Blockchain Initiative) has released two Vehicle Identity (VID) standards:
- **VID I (2019)**: Vehicle Birth Certificate - Immutable anchor
- **VID II (2021)**: Lifecycle Events - Maintenance, registration, history

Both build on blockchain technology and are designed to integrate with W3C DID standards.

---

## 🏢 MOBI VID I (1.0) - VEHICLE BIRTH CERTIFICATE

### Overview
**Released**: July 2019
**Purpose**: Establish vehicle's existence at creation ("birth")
**Key Concept**: Immutable digital birth certificate

### Core Requirements

#### 1. Vehicle Birth Certificate (VBC)
- **Immutable anchor** for extensible system
- Minimum representation of vehicle creation
- Links physical vehicle to digital identity via VIN

#### 2. Vehicle Identifier (VID)
- **Digital identity** of unique vehicle
- Bridge between physical asset and digital world
- Enables trust and verification of vehicle identity
- Inextricably linked to VIN (Vehicle Identification Number)

#### 3. System Components
- Standard data format for VID
- Standard data format for birth certificate
- Definitions, roles, and account details

#### 4. Key Features
- **Master data key** to vehicle's existence, behavior, performance
- Supports **data transparency** among stakeholders
- Enables **coordination and automation** throughout lifecycle
- Essential for **blockchain interoperability**

### Blockchain Integration
- Birth certificate stored on blockchain (immutable)
- Extensible: other data relates back to birth certificate
- Standard identity format for cross-chain compatibility

### Participants (Industry Endorsement)
**Chairs**: Groupe Renault, Ford

**Members**: Accenture, AIOI Insurance, BMW, Car Vertical, Cerebri AI, Cognizant, ConsenSys, CPChain, Dealer Market Exchange, DLT Labs, GM, Honda, Hyperledger, IBM, IOTA, Kar Auction Services, Luxoft, MintBit, Netsol Tech, Oaken Innovations, On The Road Lending, Quantstamp, Trusted IoT Alliance, Xapix

---

## 🔄 MOBI VID II - LIFECYCLE EVENTS

### Overview
**Released**: 2021
**Purpose**: Extend VID I with lifecycle management
**Key Concept**: Uses VID I as foundation ("birth certificate")

### Core Requirements

#### 1. Maintenance Traceability
- Track vehicle maintenance history
- Record service events
- Verify maintenance claims

#### 2. Vehicle Registration
- Registration events
- Ownership transfers
- Regulatory compliance

#### 3. Ownership History
- Complete ownership chain
- Transfer records
- Current owner verification

#### 4. Key Lifecycle Events
- Manufacturing milestones
- First sale
- Accidents/repairs
- Title changes
- Decommissioning

### Integration with VID I
- **VID I = Birth Certificate** (immutable anchor)
- **VID II = Lifecycle Log** (mutable events)
- Both linked via VID
- Forms complete vehicle history

---

## 🌐 W3C DID COMPLIANCE REQUIREMENTS

### DID Syntax
```
did:method-name:method-specific-id
```

**Rules**:
- Method name: lowercase letters + digits only
- Method-specific ID: alphanumeric + `.` `-` `_` `%` encoding
- Example: `did:ethr:0x123...`

### DID Document Structure

**Required Properties**:
- `id`: DID string (MUST conform to syntax)

**Optional But Standard Properties**:
- `controller`: Entity that controls the DID
- `verificationMethod`: Array of verification methods
- `authentication`: Authentication methods
- `service`: Service endpoints
- `alsoKnownAs`: Alternative identifiers

**Example Structure**:
```json
{
  "@context": ["https://www.w3.org/ns/did/v1"],
  "id": "did:ethr:0x123...",
  "controller": "did:ethr:0x123...",
  "verificationMethod": [{
    "id": "did:ethr:0x123...#keys-1",
    "type": "EcdsaSecp256k1VerificationKey2019",
    "controller": "did:ethr:0x123...",
    "publicKeyJwk": {...}
  }],
  "authentication": ["did:ethr:0x123...#keys-1"],
  "service": [{
    "id": "did:ethr:0x123...#vid-service",
    "type": "VehicleIdentityService",
    "serviceEndpoint": "https://vehicle.example.com/api"
  }]
}
```

### Verification Methods

**Requirements**:
- `id`: Verification method identifier
- `type`: Cryptographic signature suite
- `controller`: DID that controls this method
- Verification material: `publicKeyJwk` or `publicKeyMultibase`

**Common Types**:
- `EcdsaSecp256k1VerificationKey2019` (for ERC-1056)
- `Ed25519VerificationKey2020`
- `RsaVerificationKey2018`

### Service Endpoints

**Requirements**:
- `id`: Service identifier
- `type`: Service type
- `serviceEndpoint`: URI, map, or array

**Vehicle-Specific Services**:
- `VehicleIdentityService`: Core VID operations
- `MaintenanceHistoryService`: Maintenance records
- `OwnershipService`: Transfer and registration
- `TelematicsService`: Real-time vehicle data

### DID Resolution

**Process**:
1. Input: DID + resolution options
2. Output: DID Document + metadata
3. Must comply with method-specific resolution

**For ERC-1056**:
- Resolve from blockchain events
- Reconstruct DID document from event history
- Cache for performance

---

## 🔐 SSI PRINCIPLES COMPLIANCE

### Core SSI Principles

#### 1. User Control and Consent
- **Vehicle owner controls** VID
- Consent required for data sharing
- Can transfer control (ownership transfer)

#### 2. Portable Identity
- VID works across platforms
- Not locked to single service
- Blockchain provides persistence

#### 3. Minimized Data Disclosure
- Selective attribute disclosure
- Only share necessary information
- Zero-knowledge proofs where applicable

#### 4. Interoperability
- Standard formats (W3C DID, VC)
- Works with multiple blockchains
- Compatible with existing systems

#### 5. Privacy by Design
- Pseudonymous by default
- Personal data off-chain when possible
- Encrypted sensitive attributes

---

## 🎯 IMPLEMENTATION REQUIREMENTS MATRIX

### Must Have (P0 - Critical)

| Requirement | VID I | VID II | W3C DID | SSI | Status |
|-------------|-------|--------|---------|-----|--------|
| Vehicle Birth Certificate | ✅ | - | - | - | TODO |
| VIN Linkage | ✅ | - | - | - | TODO |
| Immutable Anchor | ✅ | - | - | - | TODO |
| DID Syntax Compliance | - | - | ✅ | - | TODO |
| DID Document | - | - | ✅ | - | TODO |
| Verification Methods | - | - | ✅ | ✅ | TODO |
| User Control | - | - | - | ✅ | TODO |

### Should Have (P1 - High Priority)

| Requirement | VID I | VID II | W3C DID | SSI | Status |
|-------------|-------|--------|---------|-----|--------|
| Lifecycle Events | - | ✅ | - | - | TODO |
| Maintenance History | - | ✅ | - | - | TODO |
| Ownership Transfers | - | ✅ | - | - | TODO |
| Service Endpoints | - | - | ✅ | - | TODO |
| Data Minimization | - | - | - | ✅ | TODO |

### Could Have (P2 - Nice to Have)

| Requirement | VID I | VID II | W3C DID | SSI | Status |
|-------------|-------|--------|---------|-----|--------|
| Multiple Controllers | - | - | ✅ | ✅ | TODO |
| Delegation | - | - | ✅ | ✅ | TODO |
| Revocation Registry | - | ✅ | - | - | TODO |
| Privacy Enhancements | - | - | - | ✅ | TODO |

---

## 🏗️ PROPOSED ARCHITECTURE

### Layer 1: ERC-1056 Base (Blockchain)
```
ERC1056Registry.sol (Enhanced)
├── Vehicle Birth Registration
├── VIN → DID Mapping
├── Immutable Attributes
├── Lifecycle Event Log
└── Ownership Transfer
```

### Layer 2: DID Document Construction (Off-chain + Event-based)
```
DID Resolver
├── Read blockchain events
├── Construct W3C-compliant DID Document
├── Include verification methods
├── Add service endpoints
└── Cache for performance
```

### Layer 3: VID Provider (Python)
```
MOBIVIDProvider (extends IdentityProvider)
├── register_vehicle_birth() → VID I
├── log_lifecycle_event() → VID II
├── resolve_did() → W3C DID Document
├── verify_credential() → SSI
└── transfer_ownership() → VID II
```

### Layer 4: Verifiable Credentials (Optional)
```
VCIssuer
├── Issue maintenance credentials
├── Issue registration credentials
├── Verify credentials
└── Revoke credentials
```

---

## 📊 COMPLIANCE MAPPING

### ERC-1056 → MOBI VID I

| ERC-1056 Feature | MOBI VID I Requirement | Implementation |
|------------------|------------------------|----------------|
| Identity Registration | Vehicle Birth Certificate | `registerVehicle(address, VIN, birthData)` |
| Attributes | VID/VBC Data Format | `setAttribute("vid/birth/*", data)` |
| Owner | Vehicle Owner | ERC-1056 `owner` mapping |
| Changed Events | Lifecycle Anchor | `DIDAttributeChanged` events |

### ERC-1056 → MOBI VID II

| ERC-1056 Feature | MOBI VID II Requirement | Implementation |
|------------------|-------------------------|----------------|
| Attribute Updates | Lifecycle Events | `setAttribute("vid/lifecycle/*", event)` |
| Delegates | Service Providers | `addDelegate("maintenance", provider)` |
| Owner Changes | Ownership Transfer | `changeOwner(newOwner)` |
| Event Log | History | Reconstruct from events |

### ERC-1056 → W3C DID

| ERC-1056 Feature | W3C DID Requirement | Implementation |
|------------------|---------------------|----------------|
| Identity Address | DID | `did:ethr:0x{chainId}:{address}` |
| Attributes | DID Document Properties | Parse from events |
| Public Keys | Verification Methods | Extract from attributes |
| Services | Service Endpoints | Parse service attributes |

---

## 🔍 TECHNICAL CHALLENGES & SOLUTIONS

### Challenge 1: VIN Privacy
**Problem**: VIN is personally identifiable
**Solution**: Store hash(VIN + salt) on-chain, VIN off-chain or encrypted

### Challenge 2: Lifecycle Data Size
**Problem**: Full history too large for blockchain
**Solution**: Store hashes/merkle roots on-chain, full data on IPFS/Arweave

### Challenge 3: DID Resolution Performance
**Problem**: Event parsing is slow
**Solution**: Maintain off-chain cache, update on new events

### Challenge 4: Ownership Transfer vs Immutability
**Problem**: Birth certificate immutable but owner changes
**Solution**: Birth certificate = creation data, ownership = mutable controller

### Challenge 5: Multi-Chain Compatibility
**Problem**: Different blockchains, different addresses
**Solution**: Chain ID in DID method, cross-chain resolver

---

## 📖 REFERENCES

### Official Specifications
- MOBI VID I: https://dlt.mobi/wp-content/uploads/2019/09/MOBI-Vehicle-Identity-Standard-v1.0-Preview.pdf
- W3C DID Core: https://www.w3.org/TR/did-core/
- W3C VC Data Model: https://www.w3.org/TR/vc-data-model/
- ERC-1056: https://github.com/ethereum/EIPs/issues/1056

### Industry Publications
- MOBI Announcement (2019): https://dlt.mobi/mobi-announces-the-first-vehicle-identity-vid-standard-on-blockchain/
- VID II Release (2021): https://www.pymnts.com/blockchain/2021/mobi-second-installment-of-blockchain-automotive-vehicle-identity/

### Related Standards
- ISO 17438: Vehicle Identification Number
- SAE J2735: V2X Message Set
- IEEE 1609.2: V2X Security

---

## ✅ RESEARCH COMPLETION CHECKLIST

- [x] MOBI VID I core concepts understood
- [x] MOBI VID II extensions documented
- [x] W3C DID compliance requirements extracted
- [x] SSI principles mapped
- [x] Compliance matrix created
- [x] Architecture proposed
- [x] Technical challenges identified
- [x] Implementation roadmap ready

---

**Status**: Research phase COMPLETE ✅
**Next**: Begin implementation of VID I base layer
**Updated**: 2025-11-10
