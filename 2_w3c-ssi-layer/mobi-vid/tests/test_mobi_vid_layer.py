#!/usr/bin/env python3
"""
MOBI VID layer integration tests
=================================

Runs against a real Hardhat node that this suite starts (and stops) itself.
If the node cannot be started (no npm/hardhat, missing artifacts), the whole
module SKIPS with a clear message instead of failing.

Flow covered:
    deploy -> authorize issuers -> birth certificate (VC + on-chain anchor)
    -> 3 lifecycle events (VC + anchor) -> multi-party attestation
    -> aggregated history with full VC re-verification.

Negative paths:
    * issuer with wrong role rejected ON-CHAIN (contract revert),
    * completely unauthorized issuer rejected,
    * tampered VC fails both anchor check and signature verification.
"""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from eth_account import Account
from web3.exceptions import ContractLogicError, Web3RPCError

# Module under test lives one directory up
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mobi_vid_registry import (  # noqa: E402
    DEFAULT_ARTIFACT, EventType, IssuerRole, MOBIVIDRegistryClient,
)
from birth_certificate import (  # noqa: E402
    BirthCertificateIssuer, BirthCertificateVerifier,
    credential_content_hash, decrypt_vin, salted_vin_hash,
)
from lifecycle_events import (  # noqa: E402
    ALLOWED_ISSUERS, EVENT_VC_TYPES, LifecycleEventRecorder,
    VehicleHistoryAggregator,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
HARDHAT_DIR = REPO_ROOT / "1_blockchain-identity"
RPC_PORT = 8547
RPC_URL = f"http://127.0.0.1:{RPC_PORT}"

# Hardhat's standard, publicly-known test mnemonic accounts (NOT secrets)
HARDHAT_KEYS = [
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
    "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
    "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
    "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
    "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a",
    "0x8b3a350cf5c34c9194ca85829a2df0ec3153be0318b5e2d3348e872092edffba",
    "0x92db14e403b83dfe3df233f83dfa3a0d7096f21ca9b0d6d6b8d88b2b4ec1564e",
]

VIN = "5YJ3E1EA0PF123456"


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def hardhat_node():
    """Start `npx hardhat node` for the session; skip cleanly if impossible."""
    if not DEFAULT_ARTIFACT.exists():
        pytest.skip(
            f"Hardhat artifacts missing ({DEFAULT_ARTIFACT}); "
            "run `npx hardhat compile` in 1_blockchain-identity/ first."
        )
    if not (HARDHAT_DIR / "node_modules").exists():
        pytest.skip("1_blockchain-identity/node_modules missing; run npm install")
    if _port_open(RPC_PORT):
        pytest.skip(f"Port {RPC_PORT} already in use; refusing to reuse an "
                    "unknown node")

    proc = subprocess.Popen(
        ["npx", "hardhat", "node", "--port", str(RPC_PORT)],
        cwd=str(HARDHAT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.skip("hardhat node exited immediately — cannot run "
                            "integration tests in this environment")
            if _port_open(RPC_PORT):
                time.sleep(1.0)  # give JSON-RPC a moment after the socket opens
                break
            time.sleep(0.5)
        else:
            pytest.skip("hardhat node did not become ready within 60 s")
        yield RPC_URL
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


@pytest.fixture(scope="session")
def accounts():
    keys = [Account.from_key(k) for k in HARDHAT_KEYS]
    return {
        "authority": keys[0],      # deploys; registry authority
        "manufacturer": keys[1],
        "service_center": keys[2],
        "police": keys[3],
        "dmv": keys[4],
        "first_owner": keys[5],
        "outsider": keys[6],
    }


@pytest.fixture(scope="session")
def registry(hardhat_node, accounts):
    """Deploy MOBIVIDRegistryV2 and set up the issuer roles once."""
    client = MOBIVIDRegistryClient(rpc_url=hardhat_node)
    client.deploy(accounts["authority"])

    a = accounts
    client.authorize_manufacturer(a["authority"], a["manufacturer"].address)
    client.authorize_issuer(a["authority"], a["manufacturer"].address,
                            IssuerRole.MANUFACTURER)
    client.authorize_issuer(a["authority"], a["service_center"].address,
                            IssuerRole.SERVICE_CENTER)
    client.authorize_issuer(a["authority"], a["police"].address,
                            IssuerRole.POLICE)
    client.authorize_issuer(a["authority"], a["dmv"].address,
                            IssuerRole.GOVERNMENT_DMV)
    return client


@pytest.fixture(scope="session")
def vehicle():
    """A fresh vehicle identity (its address IS the DID subject)."""
    return Account.create()


@pytest.fixture(scope="session")
def birth(registry, accounts, vehicle):
    """Issue + anchor the birth certificate (manufacturer != first owner)."""
    issuer = BirthCertificateIssuer(
        registry, accounts["manufacturer"], "Tesla Inc.")
    result = issuer.issue_birth_certificate(
        vehicle_identity=vehicle.address,
        vin=VIN,
        make="Tesla",
        model="Model 3",
        year=2024,
        manufacturing_date="2024-01-15",
        first_owner=accounts["first_owner"].address,
        vin_secret="owner-only-secret",
    )
    print(f"\n[gas] registerVehicleBirth (with attributes): {result['gasUsed']}")
    return result


# ---------------------------------------------------------------------------
# VID I — birth certificate
# ---------------------------------------------------------------------------

class TestBirthCertificate:

    def test_birth_succeeds_with_distinct_manufacturer_and_owner(
            self, registry, accounts, vehicle, birth):
        # This exact configuration reverted before the V1 fixes.
        assert accounts["manufacturer"].address != \
            accounts["first_owner"].address
        assert registry.vehicle_exists(vehicle.address)
        record = registry.get_vehicle_birth(vehicle.address)
        assert record["manufacturer"] == accounts["manufacturer"].address
        assert record["firstOwner"] == accounts["first_owner"].address
        assert registry.identity_owner(vehicle.address) == \
            accounts["first_owner"].address

    def test_vc_is_schema_valid_and_anchored(self, registry, vehicle, birth):
        vc = birth["verifiableCredential"]
        assert "VehicleBirthCertificate" in vc["type"]
        subject = vc["credentialSubject"]
        for prop in ("vin", "make", "model", "year", "manufacturingDate",
                     "manufacturerDid"):
            assert prop in subject
        record = registry.get_vehicle_birth(vehicle.address)
        assert credential_content_hash(vc) == record["birthCertHash"]

    def test_salted_vin_hash_lookup(self, registry, vehicle, birth):
        recomputed = salted_vin_hash(VIN, birth["vinSalt"])
        assert recomputed == birth["vinHash"]
        assert registry.lookup_by_vin_hash(recomputed) == vehicle.address
        # A different salt must NOT find the vehicle (privacy property)
        wrong = salted_vin_hash(VIN, "00" * 32)
        assert registry.lookup_by_vin_hash(wrong) == \
            "0x0000000000000000000000000000000000000000"

    def test_encrypted_vin_round_trip(self, registry, vehicle, birth):
        record = registry.get_vehicle_birth(vehicle.address)
        assert decrypt_vin(record["encryptedVIN"], "owner-only-secret") == VIN
        assert VIN not in record["encryptedVIN"]

    def test_full_verification_report(self, registry, vehicle, birth):
        verifier = BirthCertificateVerifier(registry)
        report = verifier.verify(
            birth["verifiableCredential"], vehicle.address,
            vin=VIN, vin_salt=birth["vinSalt"])
        assert report["valid"], report["errors"]
        assert report["checks"]["credential"]
        assert report["checks"]["anchored"]
        assert report["checks"]["vinLinkage"]
        assert report["checks"]["issuerMatchesManufacturer"]

    def test_invalid_vin_rejected_before_chain(self, registry, accounts):
        issuer = BirthCertificateIssuer(
            registry, accounts["manufacturer"], "Tesla Inc.")
        with pytest.raises(ValueError, match="VIN"):
            issuer.issue_birth_certificate(
                vehicle_identity=Account.create().address,
                vin="SHORT", make="Tesla", model="3", year=2024,
                manufacturing_date="2024-01-15",
                first_owner=accounts["first_owner"].address)


# ---------------------------------------------------------------------------
# VID II — lifecycle events (full flow)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def lifecycle(registry, accounts, vehicle, birth):
    """Record 3 lifecycle events by 3 different issuers, then attest."""
    a = accounts
    service = LifecycleEventRecorder(registry, a["service_center"],
                                     "ACME Service")
    police = LifecycleEventRecorder(registry, a["police"], "VPD")
    oem = LifecycleEventRecorder(registry, a["manufacturer"], "Tesla Inc.")

    maintenance = service.record_event(
        vehicle.address, EventType.MAINTENANCE, odometer=12000,
        claims={  # MaintenanceRecord schema — strictly enforced
            "vin": VIN,
            "serviceCenterDid": service.issuer_did,
            "serviceDate": "2025-03-01",
            "serviceType": "oil_change",
            "odometerKm": 12000,
        })
    accident = police.record_event(
        vehicle.address, EventType.ACCIDENT, odometer=15500,
        claims={  # AccidentReport — no registered schema (enforce off)
            "vin": VIN,
            "reportNumber": "VPD-2025-0042",
            "severity": "minor",
            "location": "Vancouver, BC",
        })
    recall = oem.record_event(
        vehicle.address, EventType.RECALL, odometer=15500,
        claims={  # SafetyRecall schema — strictly enforced
            "vin": VIN,
            "recallId": "TSLA-2025-17",
            "issuingAuthorityDid": oem.issuer_did,
            "component": "brake actuator",
            "severity": "high",
            "description": "Firmware fault in brake actuator controller",
        })

    for name, rec in (("MAINTENANCE", maintenance), ("ACCIDENT", accident),
                      ("RECALL", recall)):
        print(f"[gas] recordLifecycleEvent {name}: {rec['gasUsed']}")

    # DMV attests to the maintenance event (multi-party sign-off)
    dmv_recorder = LifecycleEventRecorder(registry, a["dmv"], "BC DMV")
    attestation = dmv_recorder.attest_event(
        maintenance["eventId"], vehicle.address)
    print(f"[gas] attestEvent: {attestation['gasUsed']}")

    vc_store = {**service.vc_store, **police.vc_store, **oem.vc_store}
    return {
        "events": {"maintenance": maintenance, "accident": accident,
                   "recall": recall},
        "attestation": attestation,
        "vc_store": vc_store,
    }


class TestLifecycleEvents:

    def test_three_events_recorded_on_chain(self, registry, vehicle,
                                            lifecycle):
        history = registry.get_complete_history(vehicle.address)
        assert history["eventCount"] == 3
        assert history["lastEvent"] == \
            lifecycle["events"]["recall"]["eventId"]
        ids = registry.get_vehicle_events(vehicle.address)
        assert len(ids) == 3

    def test_event_records_match_inputs(self, registry, vehicle, lifecycle):
        ev = lifecycle["events"]["maintenance"]
        on_chain = registry.get_event(vehicle.address, ev["eventId"])
        assert on_chain["eventType"] == EventType.MAINTENANCE
        assert on_chain["odometer"] == 12000
        assert on_chain["credentialHash"] == ev["credentialHash"]
        # SERVICE_CENTER is not in the contract's verified-role set
        assert on_chain["verified"] is False
        recall = registry.get_event(
            vehicle.address, lifecycle["events"]["recall"]["eventId"])
        assert recall["verified"] is True  # MANUFACTURER is a verified role

    def test_events_by_type_and_odometer_history(self, registry, vehicle,
                                                 lifecycle):
        recalls = registry.get_events_by_type(vehicle.address,
                                              EventType.RECALL)
        assert recalls == [lifecycle["events"]["recall"]["eventId"]]
        odo = registry.get_odometer_history(vehicle.address)
        assert [e["odometer"] for e in odo] == [12000, 15500, 15500]

    def test_attestation_recorded_and_signature_recoverable(
            self, registry, accounts, lifecycle):
        event_id = lifecycle["events"]["maintenance"]["eventId"]
        atts = registry.get_event_attestations(event_id)
        assert len(atts) == 1
        assert atts[0]["attester"] == accounts["dmv"].address
        assert atts[0]["role"] == IssuerRole.GOVERNMENT_DMV
        recovered = LifecycleEventRecorder.recover_attester(
            event_id, atts[0]["signature"])
        assert recovered == accounts["dmv"].address

    def test_event_log_queries(self, registry, vehicle, lifecycle):
        logs = registry.query_lifecycle_logs(vehicle_identity=vehicle.address)
        assert len(logs) == 3
        assert {lg["eventType"] for lg in logs} == {
            EventType.MAINTENANCE, EventType.ACCIDENT, EventType.RECALL}
        births = registry.query_birth_logs()
        assert any(b["vehicleIdentity"] == vehicle.address for b in births)


class TestHistoryAggregation:

    def test_aggregated_history_verifies_all_vcs(self, registry, vehicle,
                                                 lifecycle):
        aggregator = VehicleHistoryAggregator(registry)
        history = aggregator.get_vehicle_history(
            vehicle.address, vc_store=lifecycle["vc_store"])
        assert history["eventCount"] == 3
        assert len(history["events"]) == 3
        assert history["allPresentedCredentialsValid"] is True
        for entry in history["events"]:
            cred = entry["credential"]
            assert cred["valid"], cred["errors"]
            assert cred["checks"]["anchored"]
            assert cred["checks"]["issuerMatchesOnChain"]
        # the DMV attestation appears with a valid signature
        maintenance_entry = next(e for e in history["events"]
                                 if e["eventType"] == "MAINTENANCE")
        assert maintenance_entry["attestations"][0]["signatureValid"]

    def test_no_odometer_rollback_detected(self, registry, vehicle,
                                           lifecycle):
        aggregator = VehicleHistoryAggregator(registry)
        assert aggregator.detect_odometer_rollback(vehicle.address) == []


# ---------------------------------------------------------------------------
# Negative paths
# ---------------------------------------------------------------------------

class TestNegativePaths:

    def test_wrong_role_rejected_locally(self, registry, accounts, vehicle,
                                         birth):
        service = LifecycleEventRecorder(registry, accounts["service_center"])
        with pytest.raises(PermissionError, match="RECALL"):
            service.record_event(vehicle.address, EventType.RECALL,
                                 odometer=1, claims={"x": 1})

    def test_wrong_role_rejected_on_chain(self, registry, accounts, vehicle,
                                          birth):
        # Bypass the local check to prove the CONTRACT enforces the gate:
        # SERVICE_CENTER is authorized, but not for RECALL events. Claims are
        # schema-valid so the failure can only come from the contract.
        service = LifecycleEventRecorder(registry, accounts["service_center"])
        claims = {
            "vin": VIN, "recallId": "FAKE-1",
            "issuingAuthorityDid": service.issuer_did,
            "component": "none", "severity": "low", "description": "n/a",
        }
        with pytest.raises((ContractLogicError, Web3RPCError, ValueError),
                           match="Not authorized"):
            service.record_event(vehicle.address, EventType.RECALL,
                                 odometer=1, claims=claims,
                                 check_role_locally=False)

    def test_unauthorized_issuer_rejected_on_chain(self, registry, accounts,
                                                   vehicle, birth):
        outsider = LifecycleEventRecorder(registry, accounts["outsider"])
        assert registry.issuer_role(accounts["outsider"].address) == \
            IssuerRole.NONE
        claims = {
            "vin": VIN, "serviceCenterDid": outsider.issuer_did,
            "serviceDate": "2025-01-01", "serviceType": "oil_change",
            "odometerKm": 1,
        }
        with pytest.raises((ContractLogicError, Web3RPCError, ValueError),
                           match="Not authorized|not authorized"):
            outsider.record_event(vehicle.address, EventType.MAINTENANCE,
                                  odometer=1, claims=claims,
                                  check_role_locally=False)

    def test_unauthorized_attester_rejected_on_chain(self, registry, accounts,
                                                     vehicle, lifecycle):
        event_id = lifecycle["events"]["maintenance"]["eventId"]
        recorder = LifecycleEventRecorder(registry, accounts["outsider"])
        with pytest.raises((ContractLogicError, Web3RPCError, ValueError),
                           match="Not authorized"):
            recorder.attest_event(event_id, vehicle.address)

    def test_tampered_vc_fails_verification(self, registry, vehicle,
                                            lifecycle):
        import copy
        ev = lifecycle["events"]["maintenance"]
        tampered = copy.deepcopy(ev["verifiableCredential"])
        tampered["credentialSubject"]["odometerKm"] = 1  # rollback fraud

        aggregator = VehicleHistoryAggregator(registry)
        on_chain = registry.get_event(vehicle.address, ev["eventId"])
        report = aggregator.verify_event_credential(tampered, on_chain)
        assert report["valid"] is False
        assert report["checks"]["anchored"] is False       # hash mismatch
        assert report["checks"]["credential"] is False     # signature broken

    def test_tampered_birth_vc_fails_verification(self, registry, vehicle,
                                                  birth):
        import copy
        tampered = copy.deepcopy(birth["verifiableCredential"])
        tampered["credentialSubject"]["year"] = 1999
        verifier = BirthCertificateVerifier(registry)
        report = verifier.verify(tampered, vehicle.address)
        assert report["valid"] is False
        assert report["checks"]["anchored"] is False


# ---------------------------------------------------------------------------
# Enum / contract consistency
# ---------------------------------------------------------------------------

class TestEnumConsistency:

    def test_enums_mirror_contract(self):
        assert len(EventType) == 11
        assert len(IssuerRole) == 9  # NONE + 8 roles
        assert set(EVENT_VC_TYPES) == set(EventType)
        assert set(ALLOWED_ISSUERS) == set(EventType)
        # Contract-defined names (README previously drifted from these)
        assert IssuerRole.DEALER.value == 2
        assert IssuerRole.INSPECTION_STATION.value == 7

    def test_allowed_roles_match_contract_matrix(self, registry, accounts):
        # Cross-check the Python mirror against isAuthorizedIssuer()
        a = accounts
        assert registry.is_authorized_issuer(
            a["service_center"].address, EventType.MAINTENANCE)
        assert not registry.is_authorized_issuer(
            a["service_center"].address, EventType.RECALL)
        assert registry.is_authorized_issuer(
            a["manufacturer"].address, EventType.RECALL)
        assert registry.is_authorized_issuer(
            a["dmv"].address, EventType.REGISTRATION)
        assert not registry.is_authorized_issuer(
            a["police"].address, EventType.REGISTRATION)
        assert not registry.is_authorized_issuer(
            a["outsider"].address, EventType.MAINTENANCE)
