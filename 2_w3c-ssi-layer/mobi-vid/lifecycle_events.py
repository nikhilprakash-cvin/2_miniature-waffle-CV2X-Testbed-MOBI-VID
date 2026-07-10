#!/usr/bin/env python3
"""
MOBI VID II — Lifecycle Events
===============================

Every lifecycle event is BOTH:

  * a W3C Verifiable Credential, issued through the canonical VC layer
    (`2_w3c-ssi-layer/verifiable-credentials/`) and signed by the event
    issuer's Ethereum key, and
  * an on-chain record in MOBIVIDRegistryV2, whose `credentialHash` field
    anchors keccak256 of the signed VC (content-hash anchoring, not IPFS).

Enum naming: `EventType` (11 values) and `IssuerRole` (NONE + 8 roles) are
imported from `mobi_vid_registry` and mirror MOBIVIDRegistryV2.sol EXACTLY.
The contract is the source of truth — earlier docs listed
GOVERNMENT_INSPECTION / FLEET_MANAGER roles that do not exist on-chain;
the real roles are DEALER and INSPECTION_STATION (among others).

Schema policy: event types with a registered schema in the canonical layer
(MaintenanceRecord, SafetyRecall, TheftReport, InsuranceClaim,
RegistrationCredential, DecommissionCertificate) are issued with
enforce_schema=True. Event types WITHOUT a registered schema (repair,
accident, inspection, modification, recovery) are issued with
enforce_schema=False — still cryptographically signed and verifiable,
just not schema-validated.

Author: Nikhil Prakash
Thesis: MASc, UBC ECE
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from eth_account.messages import encode_defunct
from eth_account.signers.local import LocalAccount
from eth_account import Account
from web3 import Web3

# --- canonical VC layer bootstrap -----------------------------------------
_VC_LAYER = Path(__file__).resolve().parent.parent / "verifiable-credentials"
if str(_VC_LAYER) not in sys.path:
    sys.path.insert(0, str(_VC_LAYER))

from vc_issuer import CredentialIssuer, canonicalize  # noqa: E402
from vc_verifier import CredentialVerifier  # noqa: E402
from vc_schemas import get_schema  # noqa: E402

from mobi_vid_registry import (  # noqa: E402
    EventType, IssuerRole, MOBIVIDRegistryClient,
)

__all__ = [
    "EventType", "IssuerRole", "EVENT_VC_TYPES", "ALLOWED_ISSUERS",
    "LifecycleEventRecorder", "VehicleHistoryAggregator",
]

# ---------------------------------------------------------------------------
# Event-type <-> credential-type mapping
# ---------------------------------------------------------------------------

# Credential type used for the VC issued alongside each on-chain event.
# Types marked (registered) exist in vc_schemas.SCHEMA_REGISTRY and are
# issued with strict schema enforcement.
EVENT_VC_TYPES: Dict[EventType, str] = {
    EventType.MAINTENANCE: "MaintenanceRecord",          # registered
    EventType.REPAIR: "RepairRecord",                    # unregistered
    EventType.ACCIDENT: "AccidentReport",                # unregistered
    EventType.RECALL: "SafetyRecall",                    # registered
    EventType.INSPECTION: "InspectionReport",            # unregistered
    EventType.MODIFICATION: "ModificationRecord",        # unregistered
    EventType.THEFT_REPORT: "TheftReport",               # registered
    EventType.RECOVERY: "RecoveryReport",                # unregistered
    EventType.INSURANCE_CLAIM: "InsuranceClaim",         # registered
    EventType.REGISTRATION: "RegistrationCredential",    # registered
    EventType.DECOMMISSION: "DecommissionCertificate",   # registered
}

# Python-side mirror of _initializeAllowedIssuers() in MOBIVIDRegistryV2.sol.
# Used for fail-fast client-side checks; the CONTRACT enforces the real gate.
ALLOWED_ISSUERS: Dict[EventType, List[IssuerRole]] = {
    EventType.MAINTENANCE: [IssuerRole.DEALER, IssuerRole.SERVICE_CENTER,
                            IssuerRole.OWNER],
    EventType.REPAIR: [IssuerRole.DEALER, IssuerRole.SERVICE_CENTER],
    EventType.ACCIDENT: [IssuerRole.POLICE, IssuerRole.INSURANCE_COMPANY,
                         IssuerRole.OWNER],
    EventType.RECALL: [IssuerRole.MANUFACTURER],
    EventType.INSPECTION: [IssuerRole.INSPECTION_STATION,
                           IssuerRole.GOVERNMENT_DMV],
    EventType.MODIFICATION: [IssuerRole.SERVICE_CENTER, IssuerRole.OWNER],
    EventType.THEFT_REPORT: [IssuerRole.POLICE, IssuerRole.OWNER],
    EventType.RECOVERY: [IssuerRole.POLICE],
    EventType.INSURANCE_CLAIM: [IssuerRole.INSURANCE_COMPANY,
                                IssuerRole.OWNER],
    EventType.REGISTRATION: [IssuerRole.GOVERNMENT_DMV],
    EventType.DECOMMISSION: [IssuerRole.MANUFACTURER,
                             IssuerRole.GOVERNMENT_DMV],
}


def credential_content_hash(vc: Dict[str, Any]) -> bytes:
    """keccak256 over the canonicalized signed VC (content-hash anchor)."""
    return bytes(Web3.keccak(canonicalize(vc)))


# ---------------------------------------------------------------------------
# Event recorder
# ---------------------------------------------------------------------------

class LifecycleEventRecorder:
    """
    Records MOBI VID II lifecycle events: issues the event VC through the
    canonical layer and anchors it on-chain in one call.

    A local `vc_store` keeps eventId -> signed VC so histories can be
    re-verified later. In a deployment this store lives with each holder
    (SSI: credentials stay off-chain with their subjects).
    """

    def __init__(self, registry: MOBIVIDRegistryClient,
                 issuer_account: LocalAccount,
                 issuer_name: str = "Unknown Issuer"):
        self.registry = registry
        self.account = issuer_account
        self.issuer_name = issuer_name
        chain_hex = hex(registry.chain_id())
        self.credential_issuer = CredentialIssuer(
            issuer_did=f"did:ethr:{chain_hex}:{issuer_account.address}",
            private_key=issuer_account.key.hex(),
        )
        # eventId (bytes) -> signed VC
        self.vc_store: Dict[bytes, Dict[str, Any]] = {}

    @property
    def issuer_did(self) -> str:
        return self.credential_issuer.issuer_did

    def on_chain_role(self) -> IssuerRole:
        return self.registry.issuer_role(self.account.address)

    # ------------------------------------------------------------------

    def record_event(self,
                     vehicle_identity: str,
                     event_type: EventType,
                     odometer: int,
                     claims: Dict[str, Any],
                     jurisdiction: str = "BC-CAN",
                     validity_days: Optional[int] = None,
                     check_role_locally: bool = True) -> Dict[str, Any]:
        """
        Issue an event VC and anchor it on-chain.

        Args:
            vehicle_identity: vehicle's Ethereum address (subject of the VC).
            event_type: one of the 11 contract EventTypes.
            odometer: odometer reading (km) at the time of the event.
            claims: event detail claims. For registered credential types the
                schema's required properties MUST be present.
            jurisdiction: legal jurisdiction string stored on-chain.
            validity_days: VC validity (None = does not expire).
            check_role_locally: fail fast if this issuer's on-chain role is
                not allowed for the event type (the contract enforces the
                real gate either way).

        Returns dict with: eventId, verifiableCredential, credentialHash,
        dataHash, txReceipt, gasUsed, eventType, onChain (decoded record).
        """
        event_type = EventType(event_type)

        if check_role_locally:
            role = self.on_chain_role()
            if role not in ALLOWED_ISSUERS[event_type]:
                raise PermissionError(
                    f"issuer role {role.name} may not issue "
                    f"{event_type.name} events (allowed: "
                    f"{[r.name for r in ALLOWED_ISSUERS[event_type]]})")

        cred_type = EVENT_VC_TYPES[event_type]
        enforce = get_schema(cred_type) is not None
        vehicle_did = self.registry.vehicle_did(vehicle_identity)

        envelope = self.credential_issuer.issue_credential(
            credential_type=cred_type,
            subject_did=vehicle_did,
            claims=claims,
            validity_days=validity_days,
            enforce_schema=enforce,
        )
        vc = envelope["verifiableCredential"]

        credential_hash = credential_content_hash(vc)
        data_hash = bytes(Web3.keccak(canonicalize(claims)))

        event_id, receipt = self.registry.record_lifecycle_event(
            issuer=self.account,
            vehicle_identity=vehicle_identity,
            event_type=event_type,
            odometer=odometer,
            data_hash=data_hash,
            credential_hash=credential_hash,
            jurisdiction=jurisdiction,
        )
        self.vc_store[event_id] = vc

        return {
            "eventId": event_id,
            "eventType": event_type,
            "verifiableCredential": vc,
            "credentialHash": credential_hash,
            "dataHash": data_hash,
            "txReceipt": receipt,
            "gasUsed": receipt["gasUsed"],
            "onChain": self.registry.get_event(vehicle_identity, event_id),
        }

    # ------------------------------------------------------------------
    # Multi-party attestation
    # ------------------------------------------------------------------

    @staticmethod
    def attestation_signature(event_id: bytes,
                              attester: LocalAccount) -> bytes:
        """
        EIP-191 personal-sign over the event id. Any verifier can recover
        the attester address from this signature and compare it against
        the on-chain attestation record.
        """
        message = encode_defunct(event_id)
        signed = Account.sign_message(message, attester.key)
        return bytes(signed.signature)

    @staticmethod
    def recover_attester(event_id: bytes, signature: bytes) -> str:
        """Recover the address that produced an attestation signature."""
        return Account.recover_message(encode_defunct(event_id),
                                       signature=signature)

    def attest_event(self, event_id: bytes, vehicle_identity: str,
                     attester: Optional[LocalAccount] = None
                     ) -> Dict[str, Any]:
        """
        Attest to an existing event (multi-party sign-off). The attester
        must hold ANY authorized role on-chain; the signature binds their
        key to the event id.
        """
        acct = attester or self.account
        signature = self.attestation_signature(event_id, acct)
        receipt = self.registry.attest_event(
            attester=acct, event_id=event_id,
            vehicle_identity=vehicle_identity, signature=signature)
        return {"txReceipt": receipt, "gasUsed": receipt["gasUsed"],
                "signature": signature, "attester": acct.address}


# ---------------------------------------------------------------------------
# History aggregation: on-chain records joined with VC verification
# ---------------------------------------------------------------------------

class VehicleHistoryAggregator:
    """
    Builds a complete, VERIFIED vehicle history:

      * birth certificate + event list read from the contract,
      * per-event: presented VC (if available) checked for
          - anchor integrity: keccak256(VC) == on-chain credentialHash,
          - cryptographic validity via the canonical CredentialVerifier
            (signature recovery against the issuer's did:ethr address),
          - issuer consistency: VC signer == on-chain event issuer,
      * per-attestation: EIP-191 signature recovered and compared with the
        on-chain attester address.
    """

    def __init__(self, registry: MOBIVIDRegistryClient,
                 strict_schema: bool = False):
        self.registry = registry
        # strict_schema=False: several event types intentionally have no
        # registered schema (see EVENT_VC_TYPES); signature/temporal/
        # revocation checks are never relaxed.
        self.verifier = CredentialVerifier(strict_schema=strict_schema)

    def get_vehicle_history(self, vehicle_identity: str,
                            vc_store: Optional[Dict[bytes, Dict[str, Any]]]
                            = None,
                            verify: bool = True) -> Dict[str, Any]:
        vc_store = vc_store or {}
        summary = self.registry.get_complete_history(vehicle_identity)
        event_ids = self.registry.get_vehicle_events(vehicle_identity)

        events: List[Dict[str, Any]] = []
        all_valid = True
        for event_id in event_ids:
            record = self.registry.get_event(vehicle_identity, event_id)
            entry: Dict[str, Any] = {
                "eventId": event_id.hex(),
                "eventType": record["eventType"].name,
                "issuer": record["issuer"],
                "odometer": record["odometer"],
                "timestamp": record["timestamp"],
                "jurisdiction": record["jurisdiction"],
                "verifiedIssuer": record["verified"],
            }

            vc = vc_store.get(event_id)
            if vc is not None and verify:
                entry["credential"] = self.verify_event_credential(
                    vc, record)
                all_valid = all_valid and entry["credential"]["valid"]
            elif verify:
                entry["credential"] = {
                    "valid": None,
                    "note": "VC not presented (only on-chain hash available)",
                }

            if verify:
                entry["attestations"] = self._verified_attestations(event_id)

            events.append(entry)

        return {
            "vehicleIdentity": Web3.to_checksum_address(vehicle_identity),
            "vehicleDid": self.registry.vehicle_did(vehicle_identity),
            "birth": summary["birth"],
            "eventCount": summary["eventCount"],
            "events": events,
            "odometerHistory": self.registry.get_odometer_history(
                vehicle_identity),
            "allPresentedCredentialsValid": all_valid,
        }

    def verify_event_credential(self, vc: Dict[str, Any],
                                on_chain: Dict[str, Any]) -> Dict[str, Any]:
        """Verify one event VC against its on-chain anchor record."""
        report: Dict[str, Any] = {"valid": True, "checks": {}, "errors": []}

        anchored = credential_content_hash(vc) == on_chain["credentialHash"]
        report["checks"]["anchored"] = anchored
        if not anchored:
            report["valid"] = False
            report["errors"].append(
                "keccak256(VC) != on-chain credentialHash (tampered VC)")

        vc_result = self.verifier.verify_credential(vc)
        report["checks"]["credential"] = vc_result.valid
        if not vc_result.valid:
            report["valid"] = False
            report["errors"].extend(vc_result.errors)

        issuer_did = vc.get("issuer", "")
        issuer_addr = issuer_did.rsplit(":", 1)[-1].lower() \
            if isinstance(issuer_did, str) else ""
        consistent = issuer_addr == on_chain["issuer"].lower()
        report["checks"]["issuerMatchesOnChain"] = consistent
        if not consistent:
            report["valid"] = False
            report["errors"].append(
                f"VC issuer {issuer_addr} != on-chain issuer "
                f"{on_chain['issuer']}")

        return report

    def _verified_attestations(self, event_id: bytes) -> List[Dict[str, Any]]:
        out = []
        for att in self.registry.get_event_attestations(event_id):
            try:
                recovered = LifecycleEventRecorder.recover_attester(
                    event_id, att["signature"])
                sig_ok = recovered.lower() == att["attester"].lower()
            except Exception:
                sig_ok = False
            out.append({
                "attester": att["attester"],
                "role": att["role"].name,
                "timestamp": att["timestamp"],
                "signatureValid": sig_ok,
            })
        return out

    def detect_odometer_rollback(self, vehicle_identity: str
                                 ) -> List[Dict[str, Any]]:
        """
        Odometer-fraud heuristic: flag every event whose reading is lower
        than a previously recorded one.
        """
        history = self.registry.get_odometer_history(vehicle_identity)
        anomalies = []
        high_water = 0
        for entry in history:
            if entry["odometer"] < high_water:
                anomalies.append({**entry, "expectedAtLeast": high_water})
            high_water = max(high_water, entry["odometer"])
        return anomalies


if __name__ == "__main__":
    print("MOBI VID II module — enum/contract consistency self-check")
    assert len(EventType) == 11, "contract defines 11 event types"
    assert len(IssuerRole) == 9, "contract defines NONE + 8 issuer roles"
    assert set(EVENT_VC_TYPES) == set(EventType)
    assert set(ALLOWED_ISSUERS) == set(EventType)
    registered = [t for t, name in EVENT_VC_TYPES.items()
                  if get_schema(name) is not None]
    print(f"Event types: {[e.name for e in EventType]}")
    print(f"Issuer roles: {[r.name for r in IssuerRole if r != IssuerRole.NONE]}")
    print(f"Schema-enforced event types: {[e.name for e in registered]}")
    print("OK")
