#!/usr/bin/env python3
"""
W3C Verifiable Credential Issuer — VC Data Model v2.0
=====================================================

Issues signed Verifiable Credentials using Ethereum-native ECDSA secp256k1
keys (EIP-191 personal-sign), expressed as W3C Data Integrity proofs. The
same keys control the on-chain identities in `1_blockchain-identity/`, so a
credential issuer here corresponds directly to an ERC-1056/ERC-725 identity.

Design notes (see BUILD_PLAN.md):
- Canonicalization: deterministic JSON (sorted keys, fixed separators) over
  the proof-less document. Full JSON-LD canonicalization (URDNA2015) is a
  documented deviation, recorded in the thesis compliance matrix.
- Signatures verify OFFLINE via public-key recovery — no blockchain
  round-trip at verification time (Thrust 3 requirement).
- Selective disclosure: SD-JWT-style salted claim digests. The signed
  credential carries only digests; the holder receives claims + salts and
  discloses subsets at presentation time.
- Revocation: `credentialStatus` entries checked against a RevocationRegistry
  (in-memory or JSON-file backed; on-chain anchoring lands with MOBI VID).

Author: Nikhil Prakash
Thesis: MASc, UBC ECE
"""

import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from eth_account import Account
from eth_account.messages import encode_defunct

from vc_schemas import VC_CONTEXT_V2, CVIN_CONTEXT, validate_claims, get_schema

PROOF_TYPE = "DataIntegrityProof"
# Ethereum-native cryptosuite identifier (thesis-defined, documented in
# the compliance matrix): EIP-191 personal-sign over canonical JSON,
# verified by secp256k1 public-key recovery.
CRYPTOSUITE = "eip191-secp256k1-recovery-2024"


def canonicalize(document: Dict[str, Any]) -> bytes:
    """
    Deterministic JSON canonicalization: sorted keys, minimal separators,
    UTF-8. Both issuer and verifier MUST use this exact function.
    """
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def utc_now_iso() -> str:
    """Current UTC time in XML Schema dateTime format (second precision)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def claim_digest(name: str, value: Any, salt: str) -> str:
    """
    Salted digest of a single claim for selective disclosure:
    sha256(salt || name || canonical(value)), hex-encoded.
    """
    payload = salt.encode() + name.encode() + canonicalize({"v": value})
    return hashlib.sha256(payload).hexdigest()


class RevocationRegistry:
    """
    Minimal status registry backing `credentialStatus`.

    In-memory by default; pass `path` for JSON-file persistence. The MOBI
    VID pass replaces this with a smart-contract-anchored registry while
    keeping this interface.
    """

    def __init__(self, registry_id: str = f"{CVIN_CONTEXT}/status/default",
                 path: Optional[str] = None):
        self.registry_id = registry_id
        self.path = path
        self._revoked: Dict[str, Dict[str, str]] = {}
        if path and os.path.exists(path):
            with open(path, "r") as f:
                self._revoked = json.load(f)

    def revoke(self, credential_id: str, reason: str = "unspecified") -> None:
        self._revoked[credential_id] = {
            "revokedAt": utc_now_iso(),
            "reason": reason,
        }
        self._persist()

    def is_revoked(self, credential_id: str) -> bool:
        return credential_id in self._revoked

    def revocation_info(self, credential_id: str) -> Optional[Dict[str, str]]:
        return self._revoked.get(credential_id)

    def _persist(self) -> None:
        if self.path:
            with open(self.path, "w") as f:
                json.dump(self._revoked, f, indent=2)

    def status_entry(self, credential_id: str) -> Dict[str, str]:
        """The `credentialStatus` object embedded in issued credentials."""
        return {
            "id": f"{self.registry_id}#{credential_id}",
            "type": "CvinRevocationRegistry2024",
            "statusListCredential": self.registry_id,
        }


class CredentialIssuer:
    """
    W3C VC DM v2.0 credential issuer bound to an Ethereum secp256k1 key.

    The issuer DID should be a did:ethr / did:key DID whose method-specific
    identifier contains the issuer's Ethereum address, so verifiers can
    check recovered signing addresses against the DID itself. For methods
    without an embedded address (e.g. did:mobi), verifiers use a trusted
    issuer registry (see vc_verifier.TrustedIssuerRegistry).
    """

    def __init__(self, issuer_did: str,
                 private_key: Optional[str] = None,
                 revocation_registry: Optional[RevocationRegistry] = None):
        if not issuer_did.startswith("did:"):
            raise ValueError(f"issuer_did must be a DID, got: {issuer_did}")
        self.issuer_did = issuer_did
        self._account = (
            Account.from_key(private_key) if private_key
            else Account.create()
        )
        self.revocation_registry = revocation_registry or RevocationRegistry()

    @property
    def address(self) -> str:
        """Ethereum address of the issuer's signing key."""
        return self._account.address

    @property
    def verification_method(self) -> str:
        """Verification method reference used in proofs."""
        return f"{self.issuer_did}#controller"

    @classmethod
    def with_ethr_did(cls, private_key: Optional[str] = None,
                      chain_id: str = "0x1",
                      **kwargs) -> "CredentialIssuer":
        """Create an issuer whose did:ethr DID is derived from its own key."""
        account = Account.from_key(private_key) if private_key else Account.create()
        did = f"did:ethr:{chain_id}:{account.address}"
        return cls(issuer_did=did, private_key=account.key.hex(), **kwargs)

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------

    def issue_credential(
        self,
        credential_type: str,
        subject_did: str,
        claims: Dict[str, Any],
        validity_days: Optional[int] = 365,
        selective_disclosure: bool = False,
        revocable: bool = True,
    ) -> Dict[str, Any]:
        """
        Issue a signed Verifiable Credential.

        Args:
            credential_type: registered schema type (see vc_schemas).
            subject_did: DID of the credential subject (the vehicle/owner).
            claims: claim properties, validated against the schema.
            validity_days: None for no expiry, else days until validUntil.
            selective_disclosure: if True, the signed credential carries
                salted claim digests instead of raw claims; the returned
                envelope includes the disclosure map for the holder.
            revocable: include a credentialStatus entry.

        Returns:
            {"verifiableCredential": <signed VC>,
             "disclosures": {claim: {"value":…, "salt":…}} | None}
        """
        ok, errors = validate_claims(credential_type, claims)
        if not ok:
            raise ValueError(
                f"claims failed schema validation for {credential_type}: "
                + "; ".join(errors)
            )
        if not subject_did.startswith("did:"):
            raise ValueError(f"subject_did must be a DID, got: {subject_did}")

        credential_id = f"urn:uuid:{uuid.uuid4()}"
        now = utc_now_iso()

        disclosures: Optional[Dict[str, Dict[str, Any]]] = None
        if selective_disclosure:
            disclosures = {
                name: {"value": value, "salt": secrets.token_hex(16)}
                for name, value in claims.items()
            }
            subject: Dict[str, Any] = {
                "id": subject_did,
                "claimDigests": {
                    name: claim_digest(name, d["value"], d["salt"])
                    for name, d in disclosures.items()
                },
            }
        else:
            subject = {"id": subject_did, **claims}

        credential: Dict[str, Any] = {
            "@context": [VC_CONTEXT_V2, CVIN_CONTEXT],
            "id": credential_id,
            "type": ["VerifiableCredential", credential_type],
            "issuer": self.issuer_did,
            "validFrom": now,
            "credentialSubject": subject,
        }
        schema = get_schema(credential_type)
        if schema is not None:
            credential["credentialSchema"] = schema.to_credential_schema_entry()
        if validity_days is not None:
            valid_until = datetime.now(timezone.utc) + timedelta(days=validity_days)
            credential["validUntil"] = valid_until.strftime("%Y-%m-%dT%H:%M:%SZ")
        if revocable:
            credential["credentialStatus"] = (
                self.revocation_registry.status_entry(credential_id)
            )

        credential["proof"] = self._create_proof(
            credential, proof_purpose="assertionMethod"
        )
        return {"verifiableCredential": credential, "disclosures": disclosures}

    def revoke_credential(self, credential_id: str,
                          reason: str = "unspecified") -> None:
        """Revoke a previously issued credential by id."""
        self.revocation_registry.revoke(credential_id, reason)

    # ------------------------------------------------------------------
    # Proof machinery (shared with vc_holder via sign_document)
    # ------------------------------------------------------------------

    def _create_proof(self, document: Dict[str, Any],
                      proof_purpose: str,
                      challenge: Optional[str] = None,
                      domain: Optional[str] = None) -> Dict[str, Any]:
        proof: Dict[str, Any] = {
            "type": PROOF_TYPE,
            "cryptosuite": CRYPTOSUITE,
            "created": utc_now_iso(),
            "verificationMethod": self.verification_method,
            "proofPurpose": proof_purpose,
        }
        if challenge is not None:
            proof["challenge"] = challenge
        if domain is not None:
            proof["domain"] = domain

        signature = sign_document(document, proof, self._account.key)
        proof["proofValue"] = signature
        return proof


def signing_payload(document: Dict[str, Any],
                    proof_options: Dict[str, Any]) -> bytes:
    """
    Build the byte payload that gets signed: canonical JSON of the document
    (without `proof`) concatenated with canonical JSON of the proof options
    (without `proofValue`). Issuer and verifier share this function.
    """
    doc = {k: v for k, v in document.items() if k != "proof"}
    options = {k: v for k, v in proof_options.items() if k != "proofValue"}
    return canonicalize(doc) + b"." + canonicalize(options)


def sign_document(document: Dict[str, Any],
                  proof_options: Dict[str, Any],
                  private_key: bytes) -> str:
    """EIP-191 personal-sign over the signing payload; returns hex signature."""
    payload = signing_payload(document, proof_options)
    message = encode_defunct(hashlib.sha256(payload).digest())
    signed = Account.sign_message(message, private_key)
    return signed.signature.hex()


def recover_signer(document: Dict[str, Any],
                   proof: Dict[str, Any]) -> str:
    """Recover the Ethereum address that signed a proofed document."""
    payload = signing_payload(document, proof)
    message = encode_defunct(hashlib.sha256(payload).digest())
    signature = proof["proofValue"]
    if not signature.startswith("0x"):
        signature = "0x" + signature
    return Account.recover_message(message, signature=signature)


if __name__ == "__main__":
    import time

    print("=== VC Issuer Demo: Tesla issues a birth certificate ===\n")
    issuer = CredentialIssuer.with_ethr_did(chain_id="0x1")
    print(f"Issuer DID:     {issuer.issuer_did}")
    print(f"Issuer address: {issuer.address}\n")

    t0 = time.perf_counter()
    envelope = issuer.issue_credential(
        credential_type="VehicleBirthCertificate",
        subject_did="did:mobi:5YJ3E1EA0PF123456",
        claims={
            "vin": "5YJ3E1EA0PF123456",
            "make": "Tesla",
            "model": "Model 3",
            "year": 2024,
            "manufacturingDate": "2024-01-15",
            "manufacturerDid": issuer.issuer_did,
            "plantCode": "FRE",
            "color": "Midnight Silver",
        },
        validity_days=None,  # birth certificates do not expire
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    vc = envelope["verifiableCredential"]
    print(json.dumps(vc, indent=2))
    print(f"\nIssuance time: {elapsed_ms:.2f} ms")
    print(f"Recovered signer matches issuer: "
          f"{recover_signer(vc, vc['proof']) == issuer.address}")
