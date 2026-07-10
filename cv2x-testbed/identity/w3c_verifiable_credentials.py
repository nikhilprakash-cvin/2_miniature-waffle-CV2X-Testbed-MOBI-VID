#!/usr/bin/env python3
"""
W3C Verifiable Credentials — Compatibility Shim over the Canonical Layer
=========================================================================

HISTORY / WHY THIS FILE WAS REPLACED
------------------------------------
The original 699-line implementation in this file performed REAL signing but
MOCKED verification: `_verify_signature` only checked that a `jws` key was
present, and presentation verification was a challenge string comparison.
A fully forged credential (fake issuer, garbage signature, tampered VIN)
verified as True. Any benchmark or use-case result produced through it was
cryptographically meaningless.

This shim preserves the original module's public API (`CredentialIssuer`,
`HolderWallet`, `CredentialVerifier` and their call/return shapes) but
delegates all cryptography to the canonical, tested implementation in
`2_w3c-ssi-layer/verifiable-credentials/` (28 passing tests, real secp256k1
signature recovery, VC Data Model v2.0).

Consumers (`scripts/test_use_cases.py`, `scenarios/cv2x_identity_integration.py`)
keep working unchanged — but verification is now real: tampered or forged
credentials FAIL.

Legacy-API notes handled here:
- Demo DIDs like `did:ethr:0x1:0xTESLA123` are not valid Ethereum addresses,
  so every issuer/holder auto-registers its (DID -> signing address) mapping
  in a shared TrustedIssuerRegistry that the verifier consults.
- Legacy credential types (e.g. "VehicleMaintenanceCredential") are not in
  the canonical schema registry, so issuance runs with enforce_schema=False:
  claims are not schema-checked, but signatures are real and verified.
- Issued credentials/presentations are returned as attribute-accessible
  handles (`.id`, `.expirationDate`, `.verifiableCredential`) to match the
  original dataclass API.

Author: Nikhil Prakash (MASc, UBC ECE)
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_CANONICAL_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..",
    "2_w3c-ssi-layer", "verifiable-credentials",
))
if _CANONICAL_DIR not in sys.path:
    sys.path.insert(0, _CANONICAL_DIR)

from vc_issuer import (                                     # noqa: E402
    CredentialIssuer as _CanonicalIssuer,
    RevocationRegistry,
)
from vc_holder import HolderWallet as _CanonicalWallet      # noqa: E402
from vc_verifier import (                                   # noqa: E402
    CredentialVerifier as _CanonicalVerifier,
    TrustedIssuerRegistry,
    VerificationResult,
)

# MOBI vocabulary context carried over from the original implementation
MOBI_CONTEXT = "https://w3id.org/mobi/v1"

# Shared state so independently-constructed issuers/wallets/verifiers in the
# demo scripts see each other (the legacy API constructs CredentialVerifier()
# with no arguments).
SHARED_REVOCATION_REGISTRY = RevocationRegistry()
SHARED_TRUSTED_ISSUERS = TrustedIssuerRegistry()


class _Handle:
    """Attribute-accessible wrapper around a credential/presentation dict."""

    def __init__(self, document: Dict[str, Any]):
        self._document = document

    def to_dict(self) -> Dict[str, Any]:
        return self._document

    def __getattr__(self, name: str) -> Any:
        doc = object.__getattribute__(self, "_document")
        if name in doc:
            return doc[name]
        raise AttributeError(name)

    def __getitem__(self, key: str) -> Any:
        return self._document[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._document.get(key, default)


class VCHandle(_Handle):
    """Issued-credential handle exposing the legacy dataclass attributes."""

    def __init__(self, envelope: Dict[str, Any]):
        super().__init__(envelope["verifiableCredential"])
        self.envelope = envelope  # full envelope incl. disclosure map

    @property
    def issuanceDate(self) -> Optional[str]:  # legacy v1.1 name
        return self._document.get("validFrom")

    @property
    def expirationDate(self) -> Optional[str]:  # legacy v1.1 name
        return self._document.get("validUntil")


class VPHandle(_Handle):
    """Presentation handle (`.verifiableCredential`, `.holder`, `.proof`)."""


def _unwrap(document: Any) -> Any:
    if isinstance(document, VCHandle):
        return document.envelope
    if isinstance(document, _Handle):
        return document.to_dict()
    return document


class CredentialIssuer(_CanonicalIssuer):
    """Legacy-API issuer: (issuer_did, private_key, issuer_name)."""

    def __init__(self, issuer_did: str,
                 private_key: Optional[str] = None,
                 issuer_name: Optional[str] = None):
        super().__init__(issuer_did, private_key,
                         revocation_registry=SHARED_REVOCATION_REGISTRY)
        self.issuer_name = issuer_name
        # Demo DIDs don't embed real addresses — register the mapping so
        # the verifier can check recovered signers for real.
        SHARED_TRUSTED_ISSUERS.register(issuer_did, self.address)

    def issue_credential(self, credential_type: str, subject_did: str,
                         claims: Dict[str, Any],
                         validity_days: Optional[int] = 365,
                         **kwargs: Any) -> VCHandle:
        kwargs.setdefault("enforce_schema", False)
        kwargs.setdefault("extra_contexts", [MOBI_CONTEXT])
        envelope = super().issue_credential(
            credential_type=credential_type,
            subject_did=subject_did,
            claims=claims,
            validity_days=validity_days,
            **kwargs,
        )
        return VCHandle(envelope)


class HolderWallet(_CanonicalWallet):
    """Legacy-API wallet: (holder_did, private_key)."""

    def __init__(self, holder_did: str, private_key: Optional[str] = None):
        super().__init__(holder_did, private_key)
        SHARED_TRUSTED_ISSUERS.register(holder_did, self.address)

    def store_credential(self, credential: Any) -> str:
        return super().store_credential(_unwrap(credential))

    def create_presentation(self, credential_ids: List[str],
                            challenge: str, domain: str,
                            **kwargs: Any) -> VPHandle:
        vp = super().create_presentation(
            credential_ids=credential_ids,
            challenge=challenge, domain=domain, **kwargs,
        )
        return VPHandle(vp)


class CredentialVerifier:
    """
    Legacy-API verifier: zero-arg constructor, tuple-returning methods.

    Composes (rather than subclasses) the canonical verifier: the canonical
    verify_presentation calls self.verify_credential internally and expects
    a VerificationResult, so overriding it to return the legacy tuple would
    break the parent's own pipeline.
    """

    def __init__(self,
                 revocation_registry: Optional[RevocationRegistry] = None,
                 trusted_issuers: Optional[TrustedIssuerRegistry] = None):
        self._inner = _CanonicalVerifier(
            revocation_registry=revocation_registry
            or SHARED_REVOCATION_REGISTRY,
            trusted_issuers=trusted_issuers or SHARED_TRUSTED_ISSUERS,
            strict_schema=False,  # legacy demo claims predate the schemas
        )

    def verify_credential(self, credential: Any
                          ) -> Tuple[bool, Dict[str, Any]]:
        doc = _unwrap(credential)
        if isinstance(doc, dict) and "verifiableCredential" in doc:
            doc = doc["verifiableCredential"]
        result: VerificationResult = self._inner.verify_credential(doc)
        return result.valid, result.to_dict()

    def verify_presentation(self, presentation: Any,
                            expected_challenge: str,
                            expected_domain: str
                            ) -> Tuple[bool, Dict[str, Any]]:
        return self._inner.verify_presentation(
            _unwrap(presentation), expected_challenge, expected_domain,
        )


if __name__ == "__main__":
    print("=== Shim self-test: real verification through the legacy API ===\n")

    issuer = CredentialIssuer("did:ethr:0x1:0xTESLA123", "0x" + "1" * 64,
                              "Tesla Inc.")
    wallet = HolderWallet("did:ethr:0x1:0xJOHNDOE123", "0x" + "2" * 64)

    vc = issuer.issue_credential(
        "VehicleBirthCertificate", "did:ethr:0x1:0xVEHICLE123",
        {"vin": "5YJ3E1EA0PF123456", "make": "Tesla",
         "model": "Model S", "year": 2024},
    )
    print(f"Issued: {vc.id} (expires {vc.expirationDate})")

    wallet.store_credential(vc)
    vp = wallet.create_presentation([vc.id], challenge="nonce-1",
                                    domain="demo.example")
    verifier = CredentialVerifier()
    ok, _ = verifier.verify_presentation(vp, "nonce-1", "demo.example")
    print(f"Genuine presentation verifies: {ok} (must be True)")

    # The check the old implementation failed: forgery must be rejected
    forged = dict(vc.to_dict())
    forged["credentialSubject"] = dict(forged["credentialSubject"],
                                       vin="FORGED00000000000")
    ok_forged, _ = verifier.verify_credential(forged)
    print(f"Forged credential verifies: {ok_forged} (must be False)")

    ok_replay, _ = verifier.verify_presentation(vp, "wrong-nonce",
                                                "demo.example")
    print(f"Replayed presentation verifies: {ok_replay} (must be False)")
