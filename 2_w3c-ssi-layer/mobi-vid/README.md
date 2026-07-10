# MOBI VID Implementation

Implementation of MOBI (Mobility Open Blockchain Initiative) Vehicle Identity
(VID) standards I and II, layered on the canonical W3C VC stack in
`../verifiable-credentials/` and the `MOBIVIDRegistryV2` smart contract.

This README describes **what is actually implemented and tested**, replacing
an earlier version that claimed unmeasured "100% compliance" figures and
features (IPFS storage, `did:mobi:<VIN>`, zero-knowledge proofs) that were
never built.

## Architecture

```
birth_certificate.py / lifecycle_events.py     (this directory)
        │  issues W3C VCs via                  ../verifiable-credentials/
        │  anchors keccak256(VC) via           mobi_vid_registry.py
        ▼
MOBIVIDRegistryV2.sol  (canonical source: cv2x-testbed/contracts/;
                        compiled copy: 1_blockchain-identity/contracts/MOBI/)
        └── extends MOBIVIDRegistry.sol (VID I) ── extends ERC1056Registry.sol
```

- **MOBI VID I** (birth certificate): immutable on-chain record — salted VIN
  hash, encrypted VIN, VC content hash, manufacturer, first owner.
- **MOBI VID II** (lifecycle events): 11 event types issued by role-gated
  parties, each anchored as a hash of a signed W3C Verifiable Credential,
  with multi-party attestations.

## Files

- `mobi_vid_registry.py` — web3.py v7 client for MOBIVIDRegistryV2
  (deploy/connect, issuer management, birth registration, lifecycle events,
  attestations, history/odometer queries, event-log queries). Loads
  ABI/bytecode from `1_blockchain-identity/artifacts/contracts/MOBI/`.
- `birth_certificate.py` — VID I: issues a schema-enforced
  `VehicleBirthCertificate` VC through the canonical layer and anchors it
  on-chain; salted-SHA256 VIN hashing; two-layer verification.
- `lifecycle_events.py` — VID II: the 11 event types and 8 issuer roles,
  event VCs, multi-party attestation (EIP-191 signatures recoverable
  off-chain), verified history aggregation, odometer-rollback detection.
- `tests/test_mobi_vid_layer.py` — pytest integration suite; starts and
  stops its own Hardhat node (skips with a clear message if it cannot).

## Design decisions (and corrections to earlier docs)

### Content-hash anchoring, NOT IPFS

The contract fields `birthCertHash` / `credentialHash` store
**keccak256 of the canonicalized, signed VC** — a content hash, not an IPFS
CID. No IPFS node exists anywhere in this implementation. The full
credential stays off-chain with its holder (SSI data minimization); any
party presented with the VC can recompute the hash and check it against the
chain. Earlier documentation called these fields "IPFS hashes"; that was
aspirational, not implemented.

### `did:ethr`, NOT `did:mobi:<VIN>`

Earlier docs specified `did:mobi:<VIN>` as the vehicle DID. That design is
**rejected here for privacy reasons**: a DID is a public, widely shared
identifier (it appears in every credential, presentation, and log line), so
embedding the VIN in it would leak the VIN to every party that ever sees
the identifier — defeating the registry's own VIN-privacy design, which
deliberately puts only a *salted hash* of the VIN on-chain. Vehicles are
identified as:

```
did:ethr:<chainIdHex>:<vehicleAddress>     e.g. did:ethr:0x7a69:0xAbC...
```

VIN ↔ identity linkage is possible **only** for parties given the salt:
`vinHash = SHA256(VIN || ":" || salt)` with a 32-byte random salt
(dictionary attacks over the enumerable VIN space are infeasible without
it), resolved on-chain via `lookupByVINHash`.

### Enum names follow the contract

`EventType` (11 values) and `IssuerRole` (`NONE` + 8 roles) in
`mobi_vid_registry.py` mirror `MOBIVIDRegistryV2.sol` exactly. The earlier
README listed roles `GOVERNMENT_INSPECTION` and `FLEET_MANAGER` — those do
not exist on-chain. The actual roles are:

`MANUFACTURER, DEALER, SERVICE_CENTER, INSURANCE_COMPANY, GOVERNMENT_DMV,
POLICE, INSPECTION_STATION, OWNER`

Event types: `MAINTENANCE, REPAIR, ACCIDENT, RECALL, INSPECTION,
MODIFICATION, THEFT_REPORT, RECOVERY, INSURANCE_CLAIM, REGISTRATION,
DECOMMISSION`.

## Implemented-feature status

| Feature | Status | Evidence |
|---|---|---|
| VID I birth registration (manufacturer ≠ first owner, with attributes) | Implemented | Hardhat + pytest (previously reverted; V1 bugs fixed) |
| Salted-SHA256 VIN hash + on-chain lookup | Implemented | `test_salted_vin_hash_lookup` |
| Encrypted VIN field | Demo-grade only | XOR keystream cipher, NOT production crypto (no AEAD) |
| Birth certificate as schema-enforced W3C VC | Implemented | `VehicleBirthCertificate` schema, `enforce_schema=True` |
| Content-hash anchoring of VCs | Implemented | keccak256(VC) checked in both directions |
| 11 lifecycle event types | Implemented | contract + Python enums, tested for 5 types end-to-end |
| Role-gated issuance (8 roles) | Implemented | on-chain revert tested for wrong role and no role |
| Event VCs via canonical layer | Implemented | schema-enforced for 6 registered types, `enforce_schema=False` for 5 unregistered types |
| Multi-party attestation | Implemented | EIP-191 signature stored on-chain, recovered off-chain |
| History aggregation + VC re-verification | Implemented | `VehicleHistoryAggregator` |
| Odometer-rollback detection | Implemented (heuristic) | monotonicity check over on-chain readings |
| Ownership transfer with history | Implemented (V1) | Hardhat tests |
| IPFS document storage | **Not implemented** | content-hash anchoring instead (see above) |
| `did:mobi:<VIN>` method | **Rejected by design** | privacy: VIN in a DID leaks the VIN |
| Zero-knowledge VIN proofs | **Not implemented** | salt disclosure is the linkage mechanism |
| ISO 3779 VIN check-digit validation | Partial | length + alphabet only (`vc_schemas.is_valid_vin`) |

No percentage "compliance scores" are claimed here; the table above is the
compliance statement.

## Measured gas costs (Hardhat local node, solc 0.8.24, optimizer on)

| Operation | Gas (measured) |
|---|---|
| V1 `registerVehicleBirth` (with attributes, JS test) | 283,895 |
| `registerVehicleBirth` via Python pipeline (longer ciphertext/attrs) | 328,865 |
| V1 `transferVehicleOwnership` | 199,541 |
| V2 `recordLifecycleEvent` (first event, cold storage) | 306,923 |
| V2 `recordLifecycleEvent` (subsequent events) | ~292,500 |
| V2 `attestEvent` (65-byte signature) | 188,480 |
| History / odometer / lookup queries | 0 (view calls) |

Dollar costs depend on gas price and were removed; the earlier table's
timings/costs were not measurements.

## Usage

```python
from eth_account import Account
from mobi_vid_registry import MOBIVIDRegistryClient, EventType, IssuerRole
from birth_certificate import BirthCertificateIssuer, BirthCertificateVerifier
from lifecycle_events import LifecycleEventRecorder, VehicleHistoryAggregator

registry = MOBIVIDRegistryClient("http://127.0.0.1:8545")
authority = Account.from_key("0x...")        # registry authority
registry.deploy(authority)

manufacturer = Account.from_key("0x...")
registry.authorize_manufacturer(authority, manufacturer.address)
registry.authorize_issuer(authority, manufacturer.address, IssuerRole.MANUFACTURER)

# VID I — birth certificate (VC + on-chain anchor)
vehicle = Account.create()
issuer = BirthCertificateIssuer(registry, manufacturer, "Tesla Inc.")
birth = issuer.issue_birth_certificate(
    vehicle_identity=vehicle.address,
    vin="5YJ3E1EA0PF123456", make="Tesla", model="Model 3", year=2024,
    manufacturing_date="2024-01-15", first_owner="0xOwner...",
)

# VID II — lifecycle event (VC + on-chain anchor)
recorder = LifecycleEventRecorder(registry, manufacturer, "Tesla Inc.")
recall = recorder.record_event(
    vehicle.address, EventType.RECALL, odometer=15500,
    claims={"vin": "5YJ3E1EA0PF123456", "recallId": "TSLA-2025-17",
            "issuingAuthorityDid": recorder.issuer_did,
            "component": "brake actuator", "severity": "high",
            "description": "Firmware fault"},
)

# Verified history
history = VehicleHistoryAggregator(registry).get_vehicle_history(
    vehicle.address, vc_store=recorder.vc_store)
```

## Running the tests

```bash
cd 1_blockchain-identity && npx hardhat compile   # build artifacts (once)
cd ../2_w3c-ssi-layer/mobi-vid
python3 -m pytest tests/ -v                       # starts its own node on :8547
```

Hardhat contract tests (V1 regression + V2 behavior) live in
`1_blockchain-identity/test/MOBIVID/` and run with `npx hardhat test`.

## Known limitations

- The VIN "encryption" is a demonstrative XOR keystream, not vetted
  cryptography; production use requires an AEAD scheme (e.g. AES-GCM).
- `attestEvent` accepts `bytes32(0)` as an event id without reverting
  (empty-struct comparison quirk in the contract); clients must not treat
  the zero id as valid.
- Event VC storage is a per-recorder in-memory dict in this testbed; a
  deployment needs holder wallets (see `vc_holder.py` in the canonical
  layer) for credential custody.
- On-chain and VC timestamps come from different clocks (block time vs
  issuer wall clock) and are not reconciled.
- Only 5 of the 11 event types are exercised end-to-end in the integration
  suite (all 11 are supported by contract and client).
