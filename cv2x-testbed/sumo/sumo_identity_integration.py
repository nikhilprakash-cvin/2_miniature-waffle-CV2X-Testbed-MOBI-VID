#!/usr/bin/env python3
"""
SUMO + Vehicle Identity Integration (Thrust 3: V2V latency budget)
==================================================================

Measures REAL identity-verification latency in a V2V message flow:

- PKI population ("PKI"): IEEE 1609.2-style pseudonym certificates from
  `identity/centralized_provider.py`. Every BSM is signed with real
  ECDSA P-256 at send and verified with real ECDSA P-256 at receive.
  Cold path (first contact with a pseudonym cert) additionally validates
  the certificate chain against the CA; the cert public key is then
  cached, so the warm path is a signature check only.

- SSI population ("MOBI_VID"): each vehicle holds an Ethereum secp256k1
  key, a did:ethr DID, and a W3C V2VSafetyCredential issued through the
  canonical VC layer (`identity/w3c_verifiable_credentials.py` shim).
  BSMs are signed per-message with EIP-191 personal-sign. Cold path
  (first contact with a peer DID) performs full Verifiable Credential
  verification (structure, validity window, revocation, issuer signature
  recovery, subject/DID binding); the peer's address is then cached, so
  the warm path is signature recovery + address comparison only.

Cold (first-contact) and warm (per-message) latencies are recorded
separately per population, and the verdict compares measured p95 against
the 100 ms V2V safety budget and the 10 ms signature-check target.

What is REAL: all signing, signature verification, certificate chain
validation and VC verification (measured with time.perf_counter).
What is MOCK: vehicle mobility in --simulate mode (no SUMO binary) and
the radio channel (messages are delivered in-process; no network stack).

Usage:
    python3 sumo_identity_integration.py --simulate --duration 60
    python3 sumo_identity_integration.py             # with SUMO installed
    python3 sumo_identity_integration.py --gui       # with SUMO GUI

Results are written to results/v2v_latency.json.
"""

import sys
import os
import time
import json
import random
import math
import hashlib
import argparse
import statistics
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Add parent (cv2x-testbed) to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Optional SUMO libraries
# ---------------------------------------------------------------------------
try:
    import traci  # noqa: F401
    SUMO_AVAILABLE = True
except ImportError:
    SUMO_AVAILABLE = False

# ---------------------------------------------------------------------------
# Real crypto / identity dependencies (REQUIRED — no simulated fallback)
# ---------------------------------------------------------------------------
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from eth_account import Account
from eth_account.messages import encode_defunct

from identity.centralized_provider import CentralizedIdentityProvider
from identity.w3c_verifiable_credentials import (
    CredentialIssuer,
    CredentialVerifier,
)

try:
    from identity.centralized_vehicle_registry import (
        CentralizedVehicleRegistry,
        IssuerRole,
    )
    REGISTRY_AVAILABLE = True
except Exception:
    REGISTRY_AVAILABLE = False

# V2V performance targets (SAE J2945/1-derived thesis budget)
V2V_BUDGET_MS = 100.0          # end-to-end identity verification budget
SIG_CHECK_TARGET_MS = 10.0     # per-message signature-check target

BSM_RATE_HZ = 10               # SAE J2735 BSM broadcast rate
STEP_LENGTH_S = 0.1            # simulation step = 100 ms
NEIGHBOR_RADIUS_M = 300.0      # DSRC/C-V2X plausible reception range
MAX_NEIGHBORS = 8              # cap receivers per broadcast (runtime sanity)


def _pki_payload_bytes(message: Dict[str, Any]) -> bytes:
    """Serialization used by CentralizedIdentityProvider.sign_message."""
    return json.dumps(message, sort_keys=True).encode()


def _ssi_payload_bytes(message: Dict[str, Any]) -> bytes:
    """Deterministic canonical JSON for SSI BSM signing."""
    return json.dumps(message, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False).encode()


def _ssi_signable(message: Dict[str, Any]):
    """EIP-191 signable message over sha256(canonical payload)."""
    return encode_defunct(hashlib.sha256(_ssi_payload_bytes(message)).digest())


def _cert_validity_window(cert) -> Tuple[datetime, datetime]:
    """Validity window, tolerant of cryptography-library deprecations."""
    try:
        return cert.not_valid_before_utc, cert.not_valid_after_utc
    except AttributeError:
        nb = cert.not_valid_before.replace(tzinfo=timezone.utc)
        na = cert.not_valid_after.replace(tzinfo=timezone.utc)
        return nb, na


# ===========================================================================
# Identity layers
# ===========================================================================

class PKIIdentityLayer:
    """IEEE 1609.2-style PKI: pseudonym certificates + ECDSA P-256."""

    def __init__(self):
        self.provider = CentralizedIdentityProvider(ca_name="V2X-CA-CVIN")
        self.ca_public_key = self.provider.ca_certificate.public_key()
        # Per-receiver cache: receiver_id -> {cert_fingerprint: public_key}
        self._cert_cache: Dict[str, Dict[str, Any]] = {}

    def enroll(self, vehicle_id: str, metadata: Optional[Dict] = None):
        return self.provider.register_vehicle(vehicle_id, metadata or {})

    def sign(self, vehicle_id: str, message: Dict) -> Tuple[Dict, float]:
        """Real ECDSA P-256 signature over the BSM payload."""
        t0 = time.perf_counter()
        signed = self.provider.sign_message(vehicle_id, message)
        return signed, (time.perf_counter() - t0) * 1000.0

    def verify(self, receiver_id: str, signed: Dict) -> Tuple[bool, float, bool]:
        """
        Verify at the receiver. Returns (ok, latency_ms, cold).

        cold  = first contact with this pseudonym certificate: full chain
                validation (CA signature, validity window, CRL) + message
                signature verification, then cache the cert public key.
        warm  = per-message ECDSA verify against the cached public key.
        """
        t0 = time.perf_counter()
        cache = self._cert_cache.setdefault(receiver_id, {})
        ok = False
        try:
            cert_pem: str = signed["certificate"]
            signature = bytes.fromhex(signed["signature"])
            payload = _pki_payload_bytes(signed["message"])
            fingerprint = hashlib.sha256(cert_pem.encode()).hexdigest()

            cold = fingerprint not in cache
            if cold:
                cert = x509.load_pem_x509_certificate(cert_pem.encode())
                # 1. Certificate chain: pseudonym cert signed by our CA
                self.ca_public_key.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    ec.ECDSA(cert.signature_hash_algorithm),
                )
                # 2. Validity window
                not_before, not_after = _cert_validity_window(cert)
                now = datetime.now(timezone.utc)
                if not (not_before <= now <= not_after):
                    raise ValueError("certificate outside validity window")
                # 3. Revocation (CRL)
                if cert.serial_number in self.provider.revocation_list:
                    raise ValueError("certificate revoked")
                public_key = cert.public_key()
            else:
                public_key = cache[fingerprint]

            # 4. Message signature (every message)
            public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
            if cold:
                cache[fingerprint] = public_key
            ok = True
        except Exception:
            cold = True  # failures never warm the cache
            ok = False
        return ok, (time.perf_counter() - t0) * 1000.0, cold


class SSIIdentityLayer:
    """did:ethr + W3C Verifiable Credentials (canonical VC layer)."""

    def __init__(self):
        issuer_account = Account.create()
        self.issuer = CredentialIssuer(
            f"did:ethr:0x1:{issuer_account.address}",
            issuer_account.key.hex(),
            "CVIN Manufacturer Consortium",
        )
        self.verifier = CredentialVerifier()
        # vehicle_id -> {"account", "did", "credential"}
        self.wallets: Dict[str, Dict[str, Any]] = {}
        # Per-receiver cache: receiver_id -> {sender_did: signing_address}
        self._peer_cache: Dict[str, Dict[str, str]] = {}

    def enroll(self, vehicle_id: str, vin: str, make: str, model: str,
               year: int) -> Dict[str, Any]:
        """Create a DID and issue a real V2VSafetyCredential to it."""
        account = Account.create()
        did = f"did:ethr:0x1:{account.address}"
        credential = self.issuer.issue_credential(
            credential_type="V2VSafetyCredential",
            subject_did=did,
            claims={
                "vin": vin,
                "vehicleId": vehicle_id,
                "make": make,
                "model": model,
                "year": year,
                "authorizedMessages": ["BSM", "DENM"],
            },
            validity_days=365,
        )
        wallet = {"account": account, "did": did, "credential": credential}
        self.wallets[vehicle_id] = wallet
        return wallet

    def sign(self, vehicle_id: str, message: Dict) -> Tuple[Dict, float]:
        """Real secp256k1 EIP-191 signature over the BSM payload."""
        wallet = self.wallets[vehicle_id]
        t0 = time.perf_counter()
        signed = Account.sign_message(_ssi_signable(message),
                                      wallet["account"].key)
        package = {
            "message": message,
            "sender_did": wallet["did"],
            "signature": signed.signature.hex(),
            "credential": wallet["credential"],  # attached for first contact
            "identity_type": "ssi_vc",
        }
        return package, (time.perf_counter() - t0) * 1000.0

    def verify(self, receiver_id: str, package: Dict) -> Tuple[bool, float, bool]:
        """
        Verify at the receiver. Returns (ok, latency_ms, cold).

        cold  = first contact with this DID: full VC verification (issuer
                signature recovery, trusted-issuer check, validity window,
                revocation) + subject/DID binding + BSM signature recovery,
                then cache the peer's signing address.
        warm  = per-message signature recovery + cached-address comparison.
        """
        t0 = time.perf_counter()
        cache = self._peer_cache.setdefault(receiver_id, {})
        ok = False
        sender_did = package.get("sender_did", "")
        cold = sender_did not in cache
        try:
            recovered = Account.recover_message(
                _ssi_signable(package["message"]),
                signature=package["signature"],
            )
            if not cold:
                ok = (recovered.lower() == cache[sender_did].lower())
            else:
                credential = package.get("credential")
                if credential is not None:
                    valid, _report = self.verifier.verify_credential(credential)
                    if valid:
                        doc = credential.to_dict() if hasattr(
                            credential, "to_dict") else credential
                        subject = doc.get("credentialSubject", {})
                        subject_did = subject.get("id", "")
                        did_address = sender_did.rsplit(":", 1)[-1]
                        if (subject_did == sender_did
                                and recovered.lower() == did_address.lower()):
                            cache[sender_did] = recovered
                            ok = True
        except Exception:
            ok = False
        return ok, (time.perf_counter() - t0) * 1000.0, cold


# ===========================================================================
# Data structures
# ===========================================================================

@dataclass
class VehicleIdentity:
    vehicle_id: str
    vin: str
    identity_type: str  # "MOBI_VID" (SSI/VC) or "PKI"
    make: str
    model: str
    year: int
    did: Optional[str] = None


@dataclass
class VehicleState:
    vehicle_id: str
    position: Tuple[float, float]
    speed: float
    heading: float
    lane_id: str
    timestamp: float


@dataclass
class PopulationStats:
    sign_ms: List[float] = field(default_factory=list)
    cold_ms: List[float] = field(default_factory=list)
    warm_ms: List[float] = field(default_factory=list)
    sent: int = 0
    verified: int = 0
    failed: int = 0


@dataclass
class Metrics:
    messages_sent: int = 0          # signed broadcasts
    messages_delivered: int = 0     # receiver deliveries (sent x neighbors)
    messages_verified: int = 0      # successful receiver verifications
    verification_failures: int = 0
    safety_events_detected: int = 0
    eebl_warnings_delivered: int = 0
    pki: PopulationStats = field(default_factory=PopulationStats)
    ssi: PopulationStats = field(default_factory=PopulationStats)


def summarize(samples: List[float]) -> Optional[Dict[str, float]]:
    """Median/p95 summary from real samples; None when there is no data."""
    if not samples:
        return None
    ordered = sorted(samples)
    n = len(ordered)

    def pct(p: float) -> float:
        return ordered[min(n - 1, max(0, math.ceil(p / 100.0 * n) - 1))]

    return {
        "n": n,
        "mean_ms": round(statistics.fmean(ordered), 4),
        "median_ms": round(statistics.median(ordered), 4),
        "p95_ms": round(pct(95.0), 4),
        "min_ms": round(ordered[0], 4),
        "max_ms": round(ordered[-1], 4),
    }


# ===========================================================================
# Mock mobility (used only in --simulate mode; SUMO provides real mobility)
# ===========================================================================

class MockMobility:
    """Persistent kinematic model: vehicles on a 5 km, 3-lane highway."""

    HIGHWAY_LENGTH_M = 5000.0

    def __init__(self, num_vehicles: int, rng: random.Random):
        self.rng = rng
        self.states: Dict[str, VehicleState] = {}
        for i in range(num_vehicles):
            vid = f"veh_{i:03d}"
            lane = i % 3
            self.states[vid] = VehicleState(
                vehicle_id=vid,
                position=(rng.uniform(0.0, self.HIGHWAY_LENGTH_M),
                          500.0 + lane * 3.5),
                speed=rng.uniform(20.0, 30.0),   # ~72-108 km/h
                heading=90.0,                    # eastbound
                lane_id=f"highway_east_{lane}",
                timestamp=0.0,
            )

    def step(self, sim_time: float, dt: float = STEP_LENGTH_S):
        for st in self.states.values():
            st.speed = min(32.0, max(15.0,
                           st.speed + self.rng.uniform(-0.3, 0.3)))
            x = (st.position[0] + st.speed * dt) % self.HIGHWAY_LENGTH_M
            st.position = (x, st.position[1])
            st.timestamp = sim_time

    def vehicle_ids(self) -> List[str]:
        return list(self.states.keys())


# ===========================================================================
# Main integration
# ===========================================================================

class SUMOIdentityIntegration:

    def __init__(self, simulation_mode=False, use_gui=False,
                 num_vehicles=50, seed=42,
                 results_path: Optional[Path] = None):
        self.simulation_mode = simulation_mode or not SUMO_AVAILABLE
        self.use_gui = use_gui
        self.num_vehicles = num_vehicles
        self.rng = random.Random(seed)
        self.running = False

        self.sumo_dir = Path(__file__).parent
        self.sumo_cfg = self.sumo_dir / "simulation.sumocfg"
        self.results_path = results_path or (
            self.sumo_dir / "results" / "v2v_latency.json")

        # Identity layers (REAL crypto)
        self.pki = PKIIdentityLayer()
        self.ssi = SSIIdentityLayer()

        # Optional provenance registry for the MOBI VID population
        self.registry = None
        if REGISTRY_AVAILABLE:
            try:
                self.registry = CentralizedVehicleRegistry()
                self.registry.authorize_issuer(
                    "cvin_mfg", "CVIN Manufacturer Consortium",
                    IssuerRole.MANUFACTURER, "MFG-CVIN")
            except Exception:
                self.registry = None

        self.vehicles: Dict[str, VehicleIdentity] = {}
        self.vehicle_states: Dict[str, VehicleState] = {}
        self.mobility: Optional[MockMobility] = None
        self.metrics = Metrics()
        self.attack_results: Dict[str, bool] = {}
        self._seq = 0

    # ------------------------------------------------------------------
    # SUMO lifecycle
    # ------------------------------------------------------------------

    def start_sumo(self):
        if self.simulation_mode:
            print("Running in SIMULATION MODE (mock mobility, real crypto)")
            self.mobility = MockMobility(self.num_vehicles, self.rng)
            return
        print("Starting SUMO traffic simulation...")
        sumo_binary = "sumo-gui" if self.use_gui else "sumo"
        sumo_cmd = [
            sumo_binary, "-c", str(self.sumo_cfg),
            "--step-length", str(STEP_LENGTH_S),
            "--collision.action", "warn", "--no-warnings",
        ]
        try:
            traci.start(sumo_cmd)
            print(f"SUMO started ({sumo_binary})")
            self.running = True
        except Exception as e:
            print(f"Failed to start SUMO: {e} — falling back to simulation mode")
            self.simulation_mode = True
            self.mobility = MockMobility(self.num_vehicles, self.rng)

    def stop_sumo(self):
        if not self.simulation_mode and self.running:
            traci.close()
            print("SUMO stopped")
        self.running = False

    # ------------------------------------------------------------------
    # Identity enrollment
    # ------------------------------------------------------------------

    def assign_vehicle_identity(self, vehicle_id: str,
                                sumo_type: str = "passenger_car") -> VehicleIdentity:
        mfg_map = {
            "passenger_car": ("Tesla", "Model 3", 2024),
            "delivery_truck": ("Ford", "Transit", 2024),
            "semi_truck": ("Freightliner", "Cascadia", 2023),
            "emergency": ("Ford", "Explorer", 2024),
        }
        make, model, year = mfg_map.get(sumo_type, mfg_map["passenger_car"])
        vin = self._generate_vin(make, year, vehicle_id)

        # Deterministic 70/30 split: 70% SSI ("MOBI_VID"), 30% PKI
        index = len(self.vehicles)
        identity_type = "MOBI_VID" if index % 10 < 7 else "PKI"

        did = None
        if identity_type == "MOBI_VID":
            wallet = self.ssi.enroll(vehicle_id, vin, make, model, year)
            did = wallet["did"]
            if self.registry is not None:
                try:
                    self.registry.register_vehicle_birth(
                        vin=vin, manufacturer=f"{make} Inc.", make=make,
                        model=model, year=year, color="Various",
                        first_owner=f"owner_{vehicle_id}",
                        manufacturer_id="cvin_mfg")
                except Exception:
                    pass
        else:
            self.pki.enroll(vehicle_id, {"vin": vin, "make": make})

        identity = VehicleIdentity(
            vehicle_id=vehicle_id, vin=vin, identity_type=identity_type,
            make=make, model=model, year=year, did=did)
        self.vehicles[vehicle_id] = identity
        return identity

    def _generate_vin(self, make: str, year: int, vehicle_id: str) -> str:
        wmi = {"Tesla": "5YJ", "Ford": "1FT", "Freightliner": "1FU"}.get(make, "XXX")
        year_code = chr(65 + (year - 2020))
        serial = "".join(c for c in vehicle_id if c.isalnum())[-10:].zfill(10).upper()
        return f"{wmi}{year_code}{serial[:13]}"

    # ------------------------------------------------------------------
    # Vehicle state
    # ------------------------------------------------------------------

    def get_vehicle_state(self, vehicle_id: str) -> Optional[VehicleState]:
        if self.simulation_mode:
            return self.mobility.states.get(vehicle_id)
        try:
            pos = traci.vehicle.getPosition(vehicle_id)
            return VehicleState(
                vehicle_id=vehicle_id, position=pos,
                speed=traci.vehicle.getSpeed(vehicle_id),
                heading=traci.vehicle.getAngle(vehicle_id),
                lane_id=traci.vehicle.getLaneID(vehicle_id),
                timestamp=time.time())
        except Exception:
            return None

    def _neighbors(self, vehicle_id: str) -> List[str]:
        """Up to MAX_NEIGHBORS nearest vehicles within radio range."""
        state = self.vehicle_states.get(vehicle_id)
        if state is None:
            return []
        candidates = []
        for other_id, other in self.vehicle_states.items():
            if other_id == vehicle_id:
                continue
            d = math.dist(state.position, other.position)
            if d <= NEIGHBOR_RADIUS_M:
                candidates.append((d, other_id))
        candidates.sort()
        return [vid for _, vid in candidates[:MAX_NEIGHBORS]]

    # ------------------------------------------------------------------
    # V2V message path (REAL sign at send, REAL verify at receive)
    # ------------------------------------------------------------------

    def _build_bsm(self, vehicle_id: str, message_type: str,
                   sim_time: float, emergency: bool) -> Optional[Dict]:
        state = self.vehicle_states.get(vehicle_id)
        identity = self.vehicles.get(vehicle_id)
        if state is None or identity is None:
            return None
        self._seq += 1
        return {
            "msg_type": message_type,
            "seq": self._seq,
            "sender": vehicle_id,
            "timestamp": round(sim_time, 3),
            "position": [round(state.position[0], 2),
                         round(state.position[1], 2)],
            "speed": round(state.speed, 2),
            "heading": round(state.heading, 1),
            "emergency": emergency,
        }

    def broadcast(self, vehicle_id: str, sim_time: float,
                  message_type: str = "BSM", emergency: bool = False) -> int:
        """Sign once, deliver to nearest neighbors, verify at each receiver.

        Returns the number of receivers that verified the message."""
        identity = self.vehicles.get(vehicle_id)
        payload = self._build_bsm(vehicle_id, message_type, sim_time, emergency)
        if identity is None or payload is None:
            return 0

        pop = self.metrics.ssi if identity.identity_type == "MOBI_VID" \
            else self.metrics.pki
        layer = self.ssi if identity.identity_type == "MOBI_VID" else self.pki

        package, sign_ms = layer.sign(vehicle_id, payload)
        pop.sign_ms.append(sign_ms)
        pop.sent += 1
        self.metrics.messages_sent += 1

        verified_count = 0
        for receiver_id in self._neighbors(vehicle_id):
            ok, latency_ms, cold = layer.verify(receiver_id, package)
            self.metrics.messages_delivered += 1
            if ok:
                (pop.cold_ms if cold else pop.warm_ms).append(latency_ms)
                pop.verified += 1
                self.metrics.messages_verified += 1
                verified_count += 1
            else:
                pop.failed += 1
                self.metrics.verification_failures += 1
        return verified_count

    # ------------------------------------------------------------------
    # Safety applications (ride on the verified message flow)
    # ------------------------------------------------------------------

    def forward_collision_warning(self, vehicle_id: str,
                                  sim_time: float) -> Optional[str]:
        state = self.vehicle_states.get(vehicle_id)
        if state is None:
            return None
        for other_id, other in self.vehicle_states.items():
            if other_id == vehicle_id or other.lane_id != state.lane_id:
                continue
            dx = other.position[0] - state.position[0]
            if dx <= 0:  # eastbound: ahead means larger x
                continue
            closing = state.speed - other.speed
            if closing <= 0:
                continue
            ttc = dx / closing
            if ttc < 3.0:
                self.broadcast(vehicle_id, sim_time, "FCW", emergency=True)
                self.metrics.safety_events_detected += 1
                return (f"FCW: {vehicle_id} -> {other_id} "
                        f"TTC {ttc:.1f}s (gap {dx:.0f}m)")
        return None

    def emergency_electronic_brake_light(self, vehicle_id: str,
                                         sim_time: float):
        """Hard-brake event: EEBL/DENM broadcast through the signed path."""
        state = self.vehicle_states.get(vehicle_id)
        if state is None:
            return
        state.speed = max(0.0, state.speed - 8.0)  # hard deceleration
        warned = self.broadcast(vehicle_id, sim_time, "EEBL", emergency=True)
        self.metrics.safety_events_detected += 1
        self.metrics.eebl_warnings_delivered += warned
        print(f"  EEBL: {vehicle_id} hard braking at t={sim_time:.1f}s "
              f"— {warned} neighbors verified the warning")

    # ------------------------------------------------------------------
    # Attack injection tests
    # ------------------------------------------------------------------

    def run_attack_tests(self, sim_time: float):
        """Tampered and unknown-sender messages MUST be rejected."""
        print("\nAttack injection tests:")
        pki_vehicles = [v for v in self.vehicles.values()
                        if v.identity_type == "PKI"]
        ssi_vehicles = [v for v in self.vehicles.values()
                        if v.identity_type == "MOBI_VID"]

        # 1. Tampered PKI message (payload modified after signing)
        if pki_vehicles:
            vid = pki_vehicles[0].vehicle_id
            payload = self._build_bsm(vid, "BSM", sim_time, False)
            package, _ = self.pki.sign(vid, payload)
            package["message"] = dict(package["message"],
                                      speed=package["message"]["speed"] + 30.0)
            ok, _, _ = self.pki.verify("attack_probe_rx", package)
            self.attack_results["tampered_pki_rejected"] = not ok
            if not ok:
                self.metrics.verification_failures += 1
                self.metrics.pki.failed += 1
            print(f"  Tampered PKI BSM rejected:        {not ok}")

        # 2. Tampered SSI message (position falsification after signing)
        if ssi_vehicles:
            vid = ssi_vehicles[0].vehicle_id
            payload = self._build_bsm(vid, "BSM", sim_time, False)
            package, _ = self.ssi.sign(vid, payload)
            package["message"] = dict(package["message"],
                                      position=[0.0, 0.0])
            ok, _, _ = self.ssi.verify("attack_probe_rx", package)
            self.attack_results["tampered_ssi_rejected"] = not ok
            if not ok:
                self.metrics.verification_failures += 1
                self.metrics.ssi.failed += 1
            print(f"  Tampered SSI BSM rejected:        {not ok}")

        # 3. Unknown / uncredentialed sender (valid key, no credential)
        rogue = Account.create()
        rogue_did = f"did:ethr:0x1:{rogue.address}"
        payload = {"msg_type": "BSM", "seq": -1, "sender": "rogue_001",
                   "timestamp": round(sim_time, 3),
                   "position": [100.0, 500.0], "speed": 25.0,
                   "heading": 90.0, "emergency": False}
        signed = Account.sign_message(_ssi_signable(payload), rogue.key)
        package = {"message": payload, "sender_did": rogue_did,
                   "signature": signed.signature.hex(),
                   "credential": None, "identity_type": "ssi_vc"}
        ok, _, _ = self.ssi.verify("attack_probe_rx", package)
        self.attack_results["uncredentialed_sender_rejected"] = not ok
        if not ok:
            self.metrics.verification_failures += 1
            self.metrics.ssi.failed += 1
        print(f"  Uncredentialed sender rejected:   {not ok}")

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def run_simulation(self, duration_seconds=60):
        print(f"\n{'=' * 80}")
        print("SUMO + VEHICLE IDENTITY INTEGRATION — "
              "REAL CRYPTOGRAPHIC V2V VERIFICATION")
        print(f"{'=' * 80}\n")
        print(f"Simulated duration: {duration_seconds}s "
              f"({int(duration_seconds / STEP_LENGTH_S)} steps of "
              f"{int(STEP_LENGTH_S * 1000)}ms, BSMs at {BSM_RATE_HZ} Hz)")
        print(f"Mode: {'SIMULATION (mock mobility)' if self.simulation_mode else 'SUMO'}")
        print("Crypto: PKI = ECDSA P-256 (IEEE 1609.2-style pseudonym certs); "
              "SSI = secp256k1 EIP-191 + W3C VC")
        print(f"Radio model: in-process delivery, {NEIGHBOR_RADIUS_M:.0f}m radius, "
              f"<= {MAX_NEIGHBORS} nearest receivers per broadcast\n")

        self.start_sumo()
        wall_start = time.time()
        total_steps = int(duration_seconds / STEP_LENGTH_S)
        sim_time = 0.0

        try:
            for step in range(total_steps):
                sim_time = step * STEP_LENGTH_S

                if not self.simulation_mode:
                    traci.simulationStep()
                    vehicle_ids = list(traci.vehicle.getIDList())
                else:
                    self.mobility.step(sim_time)
                    vehicle_ids = self.mobility.vehicle_ids()

                # Enroll new vehicles (real key generation + issuance)
                for vehicle_id in vehicle_ids:
                    if vehicle_id not in self.vehicles:
                        vtype = "passenger_car"
                        if not self.simulation_mode:
                            try:
                                vtype = traci.vehicle.getTypeID(vehicle_id)
                            except Exception:
                                pass
                        self.assign_vehicle_identity(vehicle_id, vtype)

                # Update states
                for vehicle_id in vehicle_ids:
                    state = self.get_vehicle_state(vehicle_id)
                    if state is not None:
                        self.vehicle_states[vehicle_id] = state

                # Periodic BSM broadcast: EVERY vehicle, EVERY 100ms step
                for vehicle_id in vehicle_ids:
                    self.broadcast(vehicle_id, sim_time, "BSM")

                # Safety applications once per second, over ALL vehicles
                if step % BSM_RATE_HZ == 0:
                    for vehicle_id in vehicle_ids:
                        warning = self.forward_collision_warning(
                            vehicle_id, sim_time)
                        if warning:
                            print(f"  {warning}")

                # Recurring hard-brake events (every 15s, rotating vehicle)
                if step > 0 and step % 150 == 0 and vehicle_ids:
                    braking = vehicle_ids[(step // 150) % len(vehicle_ids)]
                    self.emergency_electronic_brake_light(braking, sim_time)

                if (step + 1) % 100 == 0:
                    elapsed = time.time() - wall_start
                    print(f"t={sim_time + STEP_LENGTH_S:5.1f}s / "
                          f"{duration_seconds}s | sent "
                          f"{self.metrics.messages_sent} | verified "
                          f"{self.metrics.messages_verified} | failures "
                          f"{self.metrics.verification_failures} | wall "
                          f"{elapsed:.0f}s")

        except KeyboardInterrupt:
            print("\nSimulation interrupted by user")
        finally:
            self.stop_sumo()

        self.run_attack_tests(sim_time)
        wall_elapsed = time.time() - wall_start
        results = self.build_results(duration_seconds, wall_elapsed)
        self.print_statistics(results)
        self.write_results(results)

    # ------------------------------------------------------------------
    # Results / statistics
    # ------------------------------------------------------------------

    def build_results(self, duration_s: int, wall_elapsed_s: float) -> Dict:
        m = self.metrics

        def pop_block(pop: PopulationStats) -> Dict:
            return {
                "sign_ms": summarize(pop.sign_ms),
                "cold_ms": summarize(pop.cold_ms),
                "warm_ms": summarize(pop.warm_ms),
                "messages_sent": pop.sent,
                "messages_verified": pop.verified,
                "verification_failures": pop.failed,
            }

        def budget_check(pop: PopulationStats) -> Dict[str, Any]:
            cold = summarize(pop.cold_ms)
            warm = summarize(pop.warm_ms)
            return {
                "cold_p95_within_100ms_budget":
                    (cold["p95_ms"] <= V2V_BUDGET_MS) if cold else None,
                "warm_p95_within_100ms_budget":
                    (warm["p95_ms"] <= V2V_BUDGET_MS) if warm else None,
                "warm_p95_within_10ms_sig_target":
                    (warm["p95_ms"] <= SIG_CHECK_TARGET_MS) if warm else None,
            }

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "simulate" if self.simulation_mode else "sumo",
            "sim_duration_s": duration_s,
            "wall_clock_s": round(wall_elapsed_s, 1),
            "step_length_ms": int(STEP_LENGTH_S * 1000),
            "bsm_rate_hz": BSM_RATE_HZ,
            "neighbor_radius_m": NEIGHBOR_RADIUS_M,
            "max_receivers_per_broadcast": MAX_NEIGHBORS,
            "vehicles": {
                "total": len(self.vehicles),
                "ssi_mobi_vid": sum(1 for v in self.vehicles.values()
                                    if v.identity_type == "MOBI_VID"),
                "pki": sum(1 for v in self.vehicles.values()
                           if v.identity_type == "PKI"),
            },
            "pki": pop_block(m.pki),
            "ssi": pop_block(m.ssi),
            "messages_sent": m.messages_sent,
            "messages_delivered": m.messages_delivered,
            "messages_verified": m.messages_verified,
            "verification_failures": m.verification_failures,
            "safety_events_detected": m.safety_events_detected,
            "eebl_warnings_delivered": m.eebl_warnings_delivered,
            "attack_tests": self.attack_results,
            "budgets": {
                "v2v_budget_ms": V2V_BUDGET_MS,
                "signature_check_target_ms": SIG_CHECK_TARGET_MS,
                "pki": budget_check(m.pki),
                "ssi": budget_check(m.ssi),
            },
            "notes": {
                "real": "ECDSA P-256 sign/verify, X.509 chain validation, "
                        "secp256k1 EIP-191 sign/recover, W3C VC verification "
                        "(all latencies measured with time.perf_counter)",
                "mock": "vehicle mobility (in --simulate mode) and radio "
                        "channel (in-process delivery; no network stack, "
                        "no channel loss, no MAC-layer latency)",
            },
        }

    @staticmethod
    def _fmt(stats: Optional[Dict], key: str = "p95_ms") -> str:
        if stats is None:
            return "no data"
        return (f"median {stats['median_ms']:8.3f} ms | "
                f"p95 {stats['p95_ms']:8.3f} ms | n={stats['n']}")

    def print_statistics(self, results: Dict):
        m = self.metrics
        print(f"\n{'=' * 80}")
        print("MEASURED RESULTS (real cryptographic operations)")
        print(f"{'=' * 80}\n")

        v = results["vehicles"]
        print(f"Vehicles: {v['total']} total — "
              f"{v['ssi_mobi_vid']} SSI/MOBI_VID, {v['pki']} PKI")
        print(f"Messages: sent {m.messages_sent}, delivered "
              f"{m.messages_delivered}, verified {m.messages_verified}, "
              f"failures {m.verification_failures}")
        print(f"Safety events: {m.safety_events_detected} "
              f"(EEBL warnings verified by {m.eebl_warnings_delivered} receivers)")
        print(f"Wall clock: {results['wall_clock_s']}s for "
              f"{results['sim_duration_s']}s of simulated time\n")

        print("Identity-verification latency (measured):")
        print(f"  PKI  sign            : {self._fmt(results['pki']['sign_ms'])}")
        print(f"  PKI  verify (cold)   : {self._fmt(results['pki']['cold_ms'])}"
              f"   [cert-chain + CRL + ECDSA verify, first contact]")
        print(f"  PKI  verify (warm)   : {self._fmt(results['pki']['warm_ms'])}"
              f"   [ECDSA verify, cached cert]")
        print(f"  SSI  sign            : {self._fmt(results['ssi']['sign_ms'])}")
        print(f"  SSI  verify (cold)   : {self._fmt(results['ssi']['cold_ms'])}"
              f"   [full VC verification + sig recovery, first contact]")
        print(f"  SSI  verify (warm)   : {self._fmt(results['ssi']['warm_ms'])}"
              f"   [sig recovery vs cached peer address]")
        print()

        # Verdict — computed from MEASURED p95, never asserted on no data
        print(f"Requirements check (budget: {V2V_BUDGET_MS:.0f}ms V2V, "
              f"{SIG_CHECK_TARGET_MS:.0f}ms signature-check target):")
        any_data = False
        for label, pop in (("PKI", m.pki), ("SSI", m.ssi)):
            cold = summarize(pop.cold_ms)
            warm = summarize(pop.warm_ms)
            if cold is None and warm is None:
                print(f"  {label}: NO DATA — no verified messages; "
                      f"requirements cannot be assessed")
                continue
            any_data = True
            if cold is not None:
                mark = "PASS" if cold["p95_ms"] <= V2V_BUDGET_MS else "FAIL"
                print(f"  {label} cold p95 {cold['p95_ms']:.3f}ms vs "
                      f"{V2V_BUDGET_MS:.0f}ms budget: {mark}")
            if warm is not None:
                mark = "PASS" if warm["p95_ms"] <= V2V_BUDGET_MS else "FAIL"
                print(f"  {label} warm p95 {warm['p95_ms']:.3f}ms vs "
                      f"{V2V_BUDGET_MS:.0f}ms budget: {mark}")
                mark = ("PASS" if warm["p95_ms"] <= SIG_CHECK_TARGET_MS
                        else "FAIL")
                print(f"  {label} warm p95 {warm['p95_ms']:.3f}ms vs "
                      f"{SIG_CHECK_TARGET_MS:.0f}ms sig-check target: {mark}")
        if not any_data:
            print("  OVERALL: NO DATA — nothing was measured; "
                  "'requirements met' cannot be claimed")

        if self.attack_results:
            all_rejected = all(self.attack_results.values())
            print(f"\nAttack tests: "
                  f"{'all injected bad messages rejected' if all_rejected else 'SOME BAD MESSAGES ACCEPTED — INVESTIGATE'}")

    def write_results(self, results: Dict):
        self.results_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.results_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults written to {self.results_path}")


def main():
    parser = argparse.ArgumentParser(
        description="SUMO + vehicle identity integration with real "
                    "cryptographic V2V verification")
    parser.add_argument("--simulate", action="store_true",
                        help="Run with mock mobility (no SUMO required); "
                             "crypto is still real")
    parser.add_argument("--gui", action="store_true",
                        help="Use SUMO GUI (if SUMO available)")
    parser.add_argument("--duration", type=int, default=60,
                        help="Simulated duration in seconds (default: 60)")
    parser.add_argument("--vehicles", type=int, default=50,
                        help="Vehicle count in --simulate mode (default: 50)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for mock mobility (default: 42)")
    args = parser.parse_args()

    integration = SUMOIdentityIntegration(
        simulation_mode=args.simulate,
        use_gui=args.gui,
        num_vehicles=args.vehicles,
        seed=args.seed,
    )
    integration.run_simulation(duration_seconds=args.duration)


if __name__ == "__main__":
    main()
