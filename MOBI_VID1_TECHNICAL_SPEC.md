# MOBI VID 1.0 TECHNICAL SPECIFICATION
## Detailed Implementation Design

**Version**: 1.0.0
**Status**: DESIGN PHASE
**Last Updated**: 2025-11-10

---

## 🎯 SCOPE

This document specifies the technical implementation of MOBI VID 1.0 (Vehicle Birth Certificate) using ERC-1056 as the base DID method, ensuring full compliance with:
- MOBI VID I Standard
- W3C Decentralized Identifiers (DIDs) v1.0
- SSI Principles

---

## 📋 SYSTEM OVERVIEW

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  Application Layer                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │ Vehicle    │  │ Owner      │  │ Authority  │        │
│  │ Registrar  │  │ Portal     │  │ Validator  │        │
│  └────────────┘  └────────────┘  └────────────┘        │
└───────────────────────┬──────────────────────────────────┘
                        │
┌───────────────────────┴──────────────────────────────────┐
│              MOBI VID Provider (Python)                  │
│  ┌──────────────────────────────────────────────┐       │
│  │ MOBIVIDProvider                              │       │
│  │  • register_vehicle_birth()                  │       │
│  │  • resolve_vid_did()                        │       │
│  │  • verify_birth_certificate()               │       │
│  │  • get_vehicle_info()                       │       │
│  └──────────────────────────────────────────────┘       │
│                         │                                │
│  ┌──────────────────────┴──────────────────────┐       │
│  │ DID Document Builder                        │       │
│  │  • parse_blockchain_events()                │       │
│  │  • construct_did_document()                 │       │
│  │  • add_verification_methods()               │       │
│  └──────────────────────────────────────────────┘       │
└───────────────────────┬──────────────────────────────────┘
                        │
┌───────────────────────┴──────────────────────────────────┐
│              Smart Contract Layer                        │
│  ┌──────────────────────────────────────────────┐       │
│  │ MOBIVIDRegistry.sol (extends ERC1056)        │       │
│  │  • registerVehicleBirth()                    │       │
│  │  • setVehicleAttribute()                     │       │
│  │  • transferOwnership()                       │       │
│  │  • revokeVehicle()                          │       │
│  └──────────────────────────────────────────────┘       │
└───────────────────────┬──────────────────────────────────┘
                        │
┌───────────────────────┴──────────────────────────────────┐
│                  Blockchain Layer                        │
│  Ethereum / Polygon / BSC / Private Chain               │
└──────────────────────────────────────────────────────────┘
```

---

## 🏗️ COMPONENT SPECIFICATIONS

### 1. Vehicle Birth Certificate (VBC) Data Structure

#### Core Attributes (Immutable)

```json
{
  "vid": "did:ethr:0x1:0x123...",
  "birthCertificate": {
    "version": "1.0",
    "timestamp": "2025-11-10T12:00:00Z",
    "manufacturer": {
      "name": "Tesla Inc.",
      "did": "did:ethr:0x1:0xABC...",
      "facility": {
        "location": "Fremont, CA, USA",
        "code": "TESLA-FREMONT-01"
      }
    },
    "vehicle": {
      "vin": "1HGBH41JXMN109186",
      "vinHash": "0x5d7e...",  // hash(VIN + salt) for privacy
      "make": "Tesla",
      "model": "Model 3",
      "year": 2025,
      "bodyType": "Sedan",
      "color": "Midnight Silver",
      "engineType": "Electric",
      "specifications": {
        "batteryCapacity": "75 kWh",
        "range": "350 miles",
        "powerOutput": "283 hp"
      }
    },
    "production": {
      "date": "2025-10-15",
      "serialNumber": "TM3-2025-001234",
      "qualityCheckPassed": true,
      "certificateOfOrigin": "ipfs://Qm..."
    },
    "firstOwner": {
      "did": "did:ethr:0x1:0xDEF...",
      "registrationDate": "2025-11-01",
      "registrationAuthority": "California DMV",
      "initialOdometer": 0
    }
  },
  "blockchain": {
    "chainId": 1,
    "contractAddress": "0xCONTRACT...",
    "blockNumber": 12345678,
    "transactionHash": "0xTXHASH...",
    "timestamp": 1699617600
  },
  "signatures": {
    "manufacturer": "0xSIG1...",
    "authority": "0xSIG2..."
  }
}
```

#### VIN Privacy Protection

**Problem**: VIN is PII and can be used to track vehicles
**Solution**: Three-tier approach

1. **Public On-Chain**: `vinHash = SHA256(VIN + salt + vehicleDID)`
2. **Encrypted Off-Chain**: VIN encrypted with owner's public key
3. **Zero-Knowledge Proof**: Prove VIN ownership without revealing VIN

```solidity
// On-chain storage
struct VehicleBirth {
    bytes32 vinHash;          // hash of VIN (public, searchable)
    string encryptedVIN;       // encrypted VIN (only owner can decrypt)
    bytes32 birthCertHash;     // hash of full birth certificate
    uint256 timestamp;
    address manufacturer;
    address firstOwner;
    bool exists;
}
```

---

### 2. Smart Contract: MOBIVIDRegistry.sol

#### Contract Structure

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./ERC1056Registry.sol";

/**
 * @title MOBI VID Registry
 * @dev Extends ERC-1056 with MOBI VID 1.0 compliance
 *
 * Features:
 * - Vehicle birth certificate registration
 * - VIN privacy protection
 * - Manufacturer authentication
 * - Ownership transfer with history
 * - W3C DID compliance
 */
contract MOBIVIDRegistry is ERC1056Registry {

    // Events
    event VehicleBirthRegistered(
        address indexed vehicleIdentity,
        bytes32 indexed vinHash,
        address indexed manufacturer,
        uint256 timestamp
    );

    event VehicleOwnershipTransferred(
        address indexed vehicleIdentity,
        address indexed fromOwner,
        address indexed toOwner,
        uint256 timestamp,
        uint256 odometer
    );

    event VehicleAttributeUpdated(
        address indexed vehicleIdentity,
        string attributeType,
        bytes32 valueHash,
        uint256 timestamp
    );

    // Structs
    struct VehicleBirth {
        bytes32 vinHash;
        string encryptedVIN;
        bytes32 birthCertHash;
        uint256 timestamp;
        address manufacturer;
        address firstOwner;
        uint256 blockNumber;
        bool exists;
    }

    struct OwnershipRecord {
        address owner;
        uint256 timestamp;
        uint256 odometer;
        string registrationAuthority;
    }

    // Storage
    mapping(address => VehicleBirth) public vehicleBirths;
    mapping(bytes32 => address) public vinHashToVehicle;
    mapping(address => OwnershipRecord[]) public ownershipHistory;

    // Authorized manufacturers
    mapping(address => bool) public authorizedManufacturers;
    address public registryAuthority;

    // Modifiers
    modifier onlyManufacturer() {
        require(
            authorizedManufacturers[msg.sender],
            "Not authorized manufacturer"
        );
        _;
    }

    modifier onlyRegistryAuthority() {
        require(
            msg.sender == registryAuthority,
            "Not registry authority"
        );
        _;
    }

    constructor() {
        registryAuthority = msg.sender;
    }

    /**
     * @dev Register vehicle birth certificate
     * @param vehicleIdentity Ethereum address for vehicle DID
     * @param vinHash Hash of VIN for privacy-preserving search
     * @param encryptedVIN VIN encrypted with owner's public key
     * @param birthCertHash Hash of complete birth certificate (stored off-chain)
     * @param firstOwner Initial vehicle owner
     * @param birthAttributes Birth certificate attributes (IPFS CID, etc.)
     */
    function registerVehicleBirth(
        address vehicleIdentity,
        bytes32 vinHash,
        string calldata encryptedVIN,
        bytes32 birthCertHash,
        address firstOwner,
        bytes calldata birthAttributes
    ) external onlyManufacturer {
        require(!vehicleBirths[vehicleIdentity].exists, "Vehicle already registered");
        require(vinHashToVehicle[vinHash] == address(0), "VIN already registered");

        // Create birth record
        vehicleBirths[vehicleIdentity] = VehicleBirth({
            vinHash: vinHash,
            encryptedVIN: encryptedVIN,
            birthCertHash: birthCertHash,
            timestamp: block.timestamp,
            manufacturer: msg.sender,
            firstOwner: firstOwner,
            blockNumber: block.number,
            exists: true
        });

        // Map VIN hash to vehicle
        vinHashToVehicle[vinHash] = vehicleIdentity;

        // Initialize ownership history
        ownershipHistory[vehicleIdentity].push(OwnershipRecord({
            owner: firstOwner,
            timestamp: block.timestamp,
            odometer: 0,
            registrationAuthority: "Manufacturer"
        }));

        // Set birth certificate as attribute (ERC-1056)
        setAttribute(
            vehicleIdentity,
            msg.sender,
            keccak256("vid/birth/certificate"),
            birthAttributes,
            type(uint256).max  // Never expires
        );

        // Emit event
        emit VehicleBirthRegistered(
            vehicleIdentity,
            vinHash,
            msg.sender,
            block.timestamp
        );

        // Set initial owner
        changeOwner(vehicleIdentity, msg.sender, firstOwner);
    }

    /**
     * @dev Transfer vehicle ownership
     * @param vehicleIdentity Vehicle DID address
     * @param newOwner New owner address
     * @param odometer Current odometer reading
     * @param authority Registering authority (DMV, etc.)
     */
    function transferVehicleOwnership(
        address vehicleIdentity,
        address newOwner,
        uint256 odometer,
        string calldata authority
    ) external onlyOwner(vehicleIdentity, msg.sender) {
        require(vehicleBirths[vehicleIdentity].exists, "Vehicle not registered");

        address currentOwner = identityOwner(vehicleIdentity);

        // Add to ownership history
        ownershipHistory[vehicleIdentity].push(OwnershipRecord({
            owner: newOwner,
            timestamp: block.timestamp,
            odometer: odometer,
            registrationAuthority: authority
        }));

        // Transfer ownership (ERC-1056)
        changeOwner(vehicleIdentity, msg.sender, newOwner);

        emit VehicleOwnershipTransferred(
            vehicleIdentity,
            currentOwner,
            newOwner,
            block.timestamp,
            odometer
        );
    }

    /**
     * @dev Get vehicle birth information
     */
    function getVehicleBirth(address vehicleIdentity)
        external
        view
        returns (
            bytes32 vinHash,
            bytes32 birthCertHash,
            uint256 timestamp,
            address manufacturer,
            address currentOwner
        )
    {
        VehicleBirth memory birth = vehicleBirths[vehicleIdentity];
        require(birth.exists, "Vehicle not found");

        return (
            birth.vinHash,
            birth.birthCertHash,
            birth.timestamp,
            birth.manufacturer,
            identityOwner(vehicleIdentity)
        );
    }

    /**
     * @dev Find vehicle by VIN hash
     */
    function findVehicleByVINHash(bytes32 vinHash)
        external
        view
        returns (address vehicleIdentity)
    {
        vehicleIdentity = vinHashToVehicle[vinHash];
        require(vehicleIdentity != address(0), "Vehicle not found");
    }

    /**
     * @dev Get ownership history
     */
    function getOwnershipHistory(address vehicleIdentity)
        external
        view
        returns (OwnershipRecord[] memory)
    {
        require(vehicleBirths[vehicleIdentity].exists, "Vehicle not found");
        return ownershipHistory[vehicleIdentity];
    }

    /**
     * @dev Authorize manufacturer
     */
    function authorizeManufacturer(address manufacturer)
        external
        onlyRegistryAuthority
    {
        authorizedManufacturers[manufacturer] = true;
    }

    /**
     * @dev Revoke manufacturer authorization
     */
    function revokeManufacturerAuthorization(address manufacturer)
        external
        onlyRegistryAuthority
    {
        authorizedManufacturers[manufacturer] = false;
    }

    /**
     * @dev Check if vehicle exists
     */
    function vehicleExists(address vehicleIdentity)
        external
        view
        returns (bool)
    {
    return vehicleBirths[vehicleIdentity].exists;
    }
}
```

---

### 3. Python Provider: MOBIVIDProvider

#### Class Structure

```python
from identity.base import IdentityProvider, IdentityType, IdentityMetrics, VehicleCredential
from web3 import Web3
from typing import Dict, Tuple, Optional
import json
from datetime import datetime

class MOBIVIDProvider(IdentityProvider):
    """
    MOBI VID 1.0 Provider

    Implements MOBI Vehicle Identity Standard 1.0 (Vehicle Birth Certificate)
    using ERC-1056 as base, with full W3C DID compliance.
    """

    def __init__(
        self,
        web3_provider_url: str,
        contract_address: str,
        private_key: str
    ):
        super().__init__(IdentityType.MOBI_VID)

        self.w3 = Web3(Web3.HTTPProvider(web3_provider_url))
        self.contract = self._load_contract(contract_address)
        self.account = Account.from_key(private_key)

        # Update metrics
        self.metrics.signature_algorithm = "ECDSA-secp256k1"
        self.metrics.key_size_bits = 256
        self.metrics.revocation_mechanism = "blockchain_registry"
        self.metrics.single_point_of_failure = False

    def register_vehicle_birth(
        self,
        vin: str,
        manufacturer_data: Dict,
        vehicle_data: Dict,
        first_owner_did: str
    ) -> VehicleCredential:
        """
        Register vehicle birth certificate on blockchain.

        Args:
            vin: Vehicle Identification Number
            manufacturer_data: Manufacturer information
            vehicle_data: Vehicle specifications
            first_owner_did: DID of first owner

        Returns:
            VehicleCredential with VID
        """
        start_time = time.time()

        # Generate vehicle identity address
        vehicle_identity = self._generate_vehicle_identity(vin)

        # Create VIN hash for privacy
        vin_hash = self._hash_vin(vin, vehicle_identity)

        # Encrypt VIN
        encrypted_vin = self._encrypt_vin(vin, first_owner_did)

        # Create birth certificate
        birth_cert = self._create_birth_certificate(
            vehicle_identity,
            vin,
            manufacturer_data,
            vehicle_data,
            first_owner_did
        )

        # Store full certificate off-chain (IPFS)
        birth_cert_cid = self._store_on_ipfs(birth_cert)
        birth_cert_hash = Web3.keccak(text=json.dumps(birth_cert))

        # Register on blockchain
        tx_hash = self._register_on_blockchain(
            vehicle_identity,
            vin_hash,
            encrypted_vin,
            birth_cert_hash,
            first_owner_did,
            birth_cert_cid
        )

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        # Create VID (W3C DID compliant)
        vid = f"did:ethr:0x{self.w3.eth.chain_id:x}:{vehicle_identity}"

        # Create credential
        credential = VehicleCredential(
            vehicle_id=vin,  # Use VIN as external ID
            public_key="",  # Vehicle doesn't sign messages
            credential_data={
                'vid': vid,
                'vinHash': vin_hash.hex(),
                'birthCertificateCID': birth_cert_cid,
                'manufacturer': manufacturer_data['name'],
                'model': vehicle_data['model'],
                'year': vehicle_data['year'],
                'blockNumber': receipt.blockNumber
            },
            signature="",
            issuer=f"MOBIVIDRegistry@{self.contract.address}",
            issued_at=int(time.time()),
            expires_at=0  # Birth certificate never expires
        )

        # Update metrics
        elapsed = (time.time() - start_time) * 1000
        self.metrics.registration_time_ms = elapsed
        self.metrics.gas_used = receipt.gasUsed

        return credential

    def resolve_vid_did(self, vid: str) -> Tuple[Optional[Dict], float]:
        """
        Resolve VID to W3C-compliant DID Document.

        Args:
            vid: Vehicle Identifier (DID format)

        Returns:
            Tuple of (DID Document, resolution time in ms)
        """
        start_time = time.time()

        # Parse VID
        vehicle_address = self._parse_vid(vid)

        # Get birth information from blockchain
        birth_info = self.contract.functions.getVehicleBirth(
            vehicle_address
        ).call()

        # Get attributes from events
        attributes = self._get_vehicle_attributes(vehicle_address)

        # Construct W3C DID Document
        did_document = {
            "@context": [
                "https://www.w3.org/ns/did/v1",
                "https://w3id.org/security/suites/secp256k1-2019/v1",
                "https://dlt.mobi/ns/vid/v1"
            ],
            "id": vid,
            "controller": f"did:ethr:0x{self.w3.eth.chain_id:x}:{birth_info[4]}",  # current owner
            "verificationMethod": [{
                "id": f"{vid}#controller",
                "type": "EcdsaSecp256k1VerificationKey2019",
                "controller": vid,
                "blockchainAccountId": f"eip155:{self.w3.eth.chain_id}:{birth_info[4]}"
            }],
            "authentication": [f"{vid}#controller"],
            "service": [{
                "id": f"{vid}#vid-service",
                "type": "VehicleIdentityService",
                "serviceEndpoint": {
                    "vehicleBirthCertificate": attributes.get('birthCertificateCID', ''),
                    "manufacturer": birth_info[3],
                    "registrationTimestamp": birth_info[2]
                }
            }],
            "vid": {
                "version": "1.0",
                "standard": "MOBI-VID-I",
                "vinHash": birth_info[0].hex(),
                "birthCertificateHash": birth_info[1].hex(),
                "registrationBlock": birth_info[2],
                "manufacturer": birth_info[3]
            }
        }

        elapsed = (time.time() - start_time) * 1000
        return did_document, elapsed
```

---

## 🧪 TESTING STRATEGY

### Unit Tests

1. **Smart Contract Tests** (`test/MOBIVIDRegistry.test.js`):
   - Birth registration
   - VIN hash uniqueness
   - Ownership transfer
   - Authorization checks
   - Event emission

2. **Provider Tests** (`tests/test_mobi_vid_provider.py`):
   - Birth registration flow
   - DID document resolution
   - VIN privacy protection
   - W3C DID compliance
   - Error handling

### Integration Tests

1. **End-to-End Flow**:
   - Manufacturer registers vehicle
   - First owner receives VID
   - Third party resolves DID document
   - Owner transfers vehicle
   - New owner queries history

### Compliance Tests

1. **MOBI VID I Compliance**:
   - Birth certificate contains all required fields
   - VIN linkage works correctly
   - Immutability enforced

2. **W3C DID Compliance**:
   - DID syntax validation
   - DID document structure
   - Resolution produces valid document

3. **SSI Principles**:
   - Owner controls VID
   - Portable across systems
   - Privacy-preserving

---

## 📊 SUCCESS CRITERIA

- [ ] Vehicle birth registration completes in < 5 seconds
- [ ] DID document resolution in < 100ms
- [ ] 100% test coverage for critical paths
- [ ] Gas costs < $5 per registration (at 50 gwei)
- [ ] Zero VIN leakage in public blockchain data
- [ ] W3C DID validator passes
- [ ] MOBI VID I requirements checklist 100%

---

**Next**: Implementation Phase
**Status**: Design Complete, Ready for Implementation
