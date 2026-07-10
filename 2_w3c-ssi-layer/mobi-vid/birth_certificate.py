#!/usr/bin/env python3
"""
MOBI VID I — Vehicle Birth Certificate
=======================================

Issues a W3C Verifiable Credential birth certificate through the canonical
VC layer (`2_w3c-ssi-layer/verifiable-credentials/`) and anchors it in the
MOBIVIDRegistryV2 smart contract.

Design decisions (documented honestly):

* CONTENT-HASH ANCHORING, NOT IPFS. The contract's `birthCertHash` field
  stores keccak256 of the canonicalized, signed VC. The full credential
  lives off-chain with the holder (SSI principle: data minimization);
  anyone holding the VC can prove integrity against the on-chain hash.
  No IPFS node is involved anywhere in this implementation.

* did:ethr, NOT did:mobi:<VIN>. Embedding the VIN in the DID would leak
  the VIN to every party that ever sees the identifier, defeating the
  registry's VIN-privacy design (only a salted hash goes on-chain). The
  vehicle DID is `did:ethr:<chainId>:<vehicleAddress>`, unlinkable to the
  VIN without the salt.

* SALTED-SHA256 VIN HASHING. `vinHash = sha256(vin || ":" || salt)`.
  A raw sha256(VIN) would be trivially reversible by enumerating the
  small VIN space; the 32-byte random salt prevents dictionary attacks.
  The salt is returned to the issuer/owner and must be disclosed to any
  party that should be able to link VIN -> vehicle identity.

* The `encryptedVIN` contract field is filled with an XOR-keystream
  ciphertext derived from a caller-supplied secret (see `encrypt_vin`).
  This is a DEMONSTRATION cipher for the thesis testbed, not a vetted
  AEAD scheme — production use would substitute e.g. AES-GCM.

Author: Nikhil Prakash
Thesis: MASc, UBC ECE
"""

import hashlib
import json
import secrets
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from eth_account.signers.local import LocalAccount
from web3 import Web3

# --- canonical VC layer bootstrap -----------------------------------------
_VC_LAYER = Path(__file__).resolve().parent.parent / "verifiable-credentials"
if str(_VC_LAYER) not in sys.path:
    sys.path.insert(0, str(_VC_LAYER))

from vc_issuer import CredentialIssuer, canonicalize  # noqa: E402
from vc_verifier import CredentialVerifier, TrustedIssuerRegistry  # noqa: E402
from vc_schemas import is_valid_vin  # noqa: E402

from mobi_vid_registry import MOBIVIDRegistryClient  # noqa: E402


# ---------------------------------------------------------------------------
# VIN privacy primitives
# ---------------------------------------------------------------------------

def new_vin_salt() -> str:
    """Fresh 32-byte random salt, hex-encoded."""
    return secrets.token_hex(32)


def salted_vin_hash(vin: str, salt: str) -> bytes:
    """
    Privacy-preserving VIN commitment: sha256(vin || ':' || salt) -> 32 bytes.

    The salt prevents dictionary attacks over the enumerable VIN space.
    Anyone given (vin, salt) can recompute the hash and look the vehicle up
    on-chain via lookupByVINHash; nobody else can link VIN to identity.
    """
    return hashlib.sha256(f"{vin}:{salt}".encode("utf-8")).digest()


def _keystream(secret: str, length: int) -> bytes:
    """SHA256-based expanding keystream (demo cipher support)."""
    stream = b""
    counter = 0
    while len(stream) < length:
        stream += hashlib.sha256(f"{secret}:{counter}".encode()).digest()
        counter += 1
    return stream[:length]


def encrypt_vin(vin: str, secret: str) -> str:
    """XOR-keystream VIN encryption (demonstration-grade, see module docs)."""
    data = vin.encode("utf-8")
    ct = bytes(a ^ b for a, b in zip(data, _keystream(secret, len(data))))
    return "xor1:" + ct.hex()


def decrypt_vin(ciphertext: str, secret: str) -> str:
    """Inverse of encrypt_vin."""
    if not ciphertext.startswith("xor1:"):
        raise ValueError("unsupported ciphertext format")
    ct = bytes.fromhex(ciphertext[len("xor1:"):])
    pt = bytes(a ^ b for a, b in zip(ct, _keystream(secret, len(ct))))
    return pt.decode("utf-8")


def credential_content_hash(vc: Dict[str, Any]) -> bytes:
    """
    keccak256 over the canonicalized signed VC — the value anchored in the
    contract's `birthCertHash` / `credentialHash` fields (content-hash
    anchoring; NOT an IPFS CID).
    """
    return bytes(Web3.keccak(canonicalize(vc)))


# ---------------------------------------------------------------------------
# Birth certificate issuer
# ---------------------------------------------------------------------------

class BirthCertificateIssuer:
    """
    MOBI VID I issuance pipeline:

        1. issue a `VehicleBirthCertificate` VC via the canonical VC layer
           (schema-enforced: vin, make, model, year, manufacturingDate,
           manufacturerDid are required),
        2. compute keccak256 of the signed VC (content-hash anchoring),
        3. register the birth on-chain: salted VIN hash, encrypted VIN,
           VC content hash, first owner.
    """

    def __init__(self,
                 registry: MOBIVIDRegistryClient,
                 manufacturer_account: LocalAccount,
                 manufacturer_name: str = "Unknown Manufacturer"):
        self.registry = registry
        self.account = manufacturer_account
        self.manufacturer_name = manufacturer_name
        chain_hex = hex(registry.chain_id())
        # The VC issuer signs with the SAME key that sends the on-chain
        # registration, so the manufacturer's did:ethr DID binds both.
        self.credential_issuer = CredentialIssuer(
            issuer_did=f"did:ethr:{chain_hex}:{manufacturer_account.address}",
            private_key=manufacturer_account.key.hex(),
        )

    @property
    def manufacturer_did(self) -> str:
        return self.credential_issuer.issuer_did

    # ------------------------------------------------------------------

    def issue_birth_certificate(self,
                                vehicle_identity: str,
                                vin: str,
                                make: str,
                                model: str,
                                year: int,
                                manufacturing_date: str,
                                first_owner: str,
                                vin_secret: Optional[str] = None,
                                extra_claims: Optional[Dict[str, Any]] = None,
                                anchor_attributes: bool = True
                                ) -> Dict[str, Any]:
        """
        Issue + anchor a MOBI VID I birth certificate.

        Args:
            vehicle_identity: Ethereum address representing the vehicle DID.
            vin: 17-character ISO 3779 VIN (validated by the schema layer).
            make/model/year/manufacturing_date: birth claims.
            first_owner: Ethereum address of the first owner.
            vin_secret: secret for VIN encryption (random if omitted).
            extra_claims: optional additional claims (open-world VC model).
            anchor_attributes: also store a compact attribute blob via
                ERC-1056 DIDAttributeChanged (exercises the fixed V1 path).

        Returns dict with: verifiableCredential, vinSalt, vinHash, vinSecret,
        vehicleDid, txReceipt, gasUsed, contentHash.
        """
        if not is_valid_vin(vin):
            raise ValueError(f"invalid ISO 3779 VIN: {vin!r}")

        vehicle_did = self.registry.vehicle_did(vehicle_identity)

        # 1. W3C VC via the canonical layer — schema STRICTLY enforced
        claims: Dict[str, Any] = {
            "vin": vin,
            "make": make,
            "model": model,
            "year": year,
            "manufacturingDate": manufacturing_date,
            "manufacturerDid": self.manufacturer_did,
            **(extra_claims or {}),
        }
        envelope = self.credential_issuer.issue_credential(
            credential_type="VehicleBirthCertificate",
            subject_did=vehicle_did,
            claims=claims,
            validity_days=None,   # birth certificates do not expire
            enforce_schema=True,
        )
        vc = envelope["verifiableCredential"]

        # 2. content-hash anchoring (keccak256 of the signed VC)
        content_hash = credential_content_hash(vc)

        # 3. on-chain registration
        salt = new_vin_salt()
        vin_hash = salted_vin_hash(vin, salt)
        secret = vin_secret or secrets.token_hex(32)
        encrypted = encrypt_vin(vin, secret)

        birth_attributes = b""
        if anchor_attributes:
            # Public, non-identifying attributes only — never the VIN.
            birth_attributes = canonicalize(
                {"make": make, "model": model, "year": year}
            )

        receipt = self.registry.register_vehicle_birth(
            manufacturer=self.account,
            vehicle_identity=vehicle_identity,
            vin_hash=vin_hash,
            encrypted_vin=encrypted,
            birth_cert_hash=content_hash,
            first_owner=first_owner,
            birth_attributes=birth_attributes,
        )

        return {
            "verifiableCredential": vc,
            "vehicleDid": vehicle_did,
            "vinSalt": salt,
            "vinHash": vin_hash,
            "vinSecret": secret,
            "contentHash": content_hash,
            "txReceipt": receipt,
            "gasUsed": receipt["gasUsed"],
        }


# ---------------------------------------------------------------------------
# Verification (off-chain VC check + on-chain anchor check)
# ---------------------------------------------------------------------------

class BirthCertificateVerifier:
    """
    Two-layer verification of a MOBI VID I certificate:

      * cryptographic: the VC verifies through the canonical
        CredentialVerifier pipeline (structure, schema, temporal,
        signature recovery against the manufacturer's did:ethr address);
      * anchoring: keccak256 of the presented VC matches the
        `birthCertHash` stored on-chain for the vehicle, and the presented
        (vin, salt) pair recomputes the on-chain `vinHash`.
    """

    def __init__(self, registry: MOBIVIDRegistryClient,
                 trusted_issuers: Optional[TrustedIssuerRegistry] = None):
        self.registry = registry
        self.verifier = CredentialVerifier(trusted_issuers=trusted_issuers)

    def verify(self, vc: Dict[str, Any], vehicle_identity: str,
               vin: Optional[str] = None,
               vin_salt: Optional[str] = None) -> Dict[str, Any]:
        report: Dict[str, Any] = {"valid": True, "checks": {}, "errors": []}

        # 1. canonical VC pipeline
        vc_result = self.verifier.verify_credential(vc)
        report["checks"]["credential"] = vc_result.valid
        report["vcReport"] = vc_result.to_dict()
        if not vc_result.valid:
            report["valid"] = False
            report["errors"].extend(vc_result.errors)

        # 2. on-chain anchor
        if not self.registry.vehicle_exists(vehicle_identity):
            report["checks"]["anchored"] = False
            report["valid"] = False
            report["errors"].append("vehicle not registered on-chain")
            return report

        birth = self.registry.get_vehicle_birth(vehicle_identity)
        anchored = credential_content_hash(vc) == birth["birthCertHash"]
        report["checks"]["anchored"] = anchored
        if not anchored:
            report["valid"] = False
            report["errors"].append(
                "keccak256(VC) does not match on-chain birthCertHash "
                "(credential was tampered with or is not the anchored one)")

        # 3. optional VIN linkage proof
        if vin is not None and vin_salt is not None:
            vin_ok = salted_vin_hash(vin, vin_salt) == birth["vinHash"]
            report["checks"]["vinLinkage"] = vin_ok
            if not vin_ok:
                report["valid"] = False
                report["errors"].append(
                    "salted VIN hash does not match on-chain vinHash")

        # 4. issuer consistency: VC issuer address == on-chain manufacturer
        issuer_did = vc.get("issuer", "")
        issuer_addr = issuer_did.rsplit(":", 1)[-1].lower() \
            if isinstance(issuer_did, str) else ""
        consistent = issuer_addr == birth["manufacturer"].lower()
        report["checks"]["issuerMatchesManufacturer"] = consistent
        if not consistent:
            report["valid"] = False
            report["errors"].append(
                f"VC issuer {issuer_addr} is not the on-chain manufacturer "
                f"{birth['manufacturer']}")

        return report


if __name__ == "__main__":
    from eth_account import Account

    print("MOBI VID I demo — requires a local Hardhat node + compiled artifacts")
    registry = MOBIVIDRegistryClient()
    manufacturer = Account.from_key(
        "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
    registry.deploy(manufacturer)

    issuer = BirthCertificateIssuer(registry, manufacturer, "Tesla Inc.")
    vehicle = Account.create()
    owner = Account.create()
    result = issuer.issue_birth_certificate(
        vehicle_identity=vehicle.address,
        vin="5YJ3E1EA0PF123456", make="Tesla", model="Model 3", year=2024,
        manufacturing_date="2024-01-15", first_owner=owner.address,
    )
    print(f"Vehicle DID: {result['vehicleDid']}")
    print(f"Gas used:    {result['gasUsed']}")

    verifier = BirthCertificateVerifier(registry)
    report = verifier.verify(result["verifiableCredential"], vehicle.address,
                             vin="5YJ3E1EA0PF123456",
                             vin_salt=result["vinSalt"])
    print(f"Verification: {json.dumps(report['checks'], indent=2)}")
