#!/usr/bin/env python3
"""
W3C Verifiable Credential Verifier — VC Data Model v2.0
=======================================================

Verifies credentials and presentations WITHOUT any blockchain round-trip:
the signer's Ethereum address is recovered from the secp256k1 signature and
compared against the address embedded in the issuer/holder DID (did:ethr,
did:key) or against a trusted-issuer registry (did:mobi and others).

Check pipeline for a credential:
  1. structure   — required VC DM 2.0 properties present
  2. schema      — claims validate against the registered schema
  3. temporal    — validFrom reached, validUntil not passed
  4. revocation  — credentialStatus checked against the registry
  5. signature   — recovered signer matches the issuer DID / registry
  6. disclosure  — disclosed claim+salt pairs match signed claimDigests

Presentation verification additionally checks:
  a. VP signature recovered against the holder DID
  b. challenge matches the verifier's expected nonce (replay protection)
  c. domain matches the verifier's audience
  d. every embedded credential passes the credential pipeline

Author: Nikhil Prakash
Thesis: MASc, UBC ECE
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from vc_schemas import validate_claims, get_schema
from vc_issuer import (
    RevocationRegistry, claim_digest, recover_signer, utc_now_iso,
)


@dataclass
class VerificationResult:
    """Outcome of a verification with per-check detail."""
    valid: bool = True
    checks: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    verified_at: str = field(default_factory=utc_now_iso)
    elapsed_ms: float = 0.0

    def fail(self, check: str, message: str) -> None:
        self.valid = False
        self.checks[check] = False
        self.errors.append(f"[{check}] {message}")

    def ok(self, check: str) -> None:
        self.checks.setdefault(check, True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
            "verifiedAt": self.verified_at,
            "elapsedMs": round(self.elapsed_ms, 3),
        }


class TrustedIssuerRegistry:
    """
    Maps DIDs without an embedded Ethereum address (e.g. did:mobi) to
    their authorized signing addresses. In production this is populated
    from the on-chain issuer registry; for experiments it is seeded
    directly.
    """

    def __init__(self):
        self._issuers: Dict[str, str] = {}

    def register(self, did: str, address: str) -> None:
        self._issuers[did] = address.lower()

    def address_for(self, did: str) -> Optional[str]:
        return self._issuers.get(did)


def address_from_did(did: str) -> Optional[str]:
    """
    Extract the Ethereum address from DID methods that embed one.

    Supported (this repository's conventions):
      did:ethr:<chainId>:<address>   (ERC-1056)
      did:ethr:<address>
      did:key:<chainId>:<address>    (ERC-725, repo convention)
      did:nft:<chainId>:<contract>:<tokenId> → controller = contract? No —
          NFT identity is token-controlled; signature checks require the
          current token owner, resolved on-chain. Returns None here (the
          trusted registry or a chain lookup must supply the owner).
    """
    parts = did.split(":")
    if len(parts) < 3:
        return None
    method = parts[1]
    candidate = parts[-1]
    if method in ("ethr", "key") and candidate.startswith("0x") \
            and len(candidate) == 42:
        return candidate.lower()
    return None


class CredentialVerifier:
    """Verifier for W3C VCs and VPs issued by this thesis stack."""

    REQUIRED_VC_PROPERTIES = ("@context", "type", "issuer",
                              "credentialSubject", "proof")

    def __init__(self,
                 revocation_registry: Optional[RevocationRegistry] = None,
                 trusted_issuers: Optional[TrustedIssuerRegistry] = None):
        self.revocation_registry = revocation_registry
        self.trusted_issuers = trusted_issuers or TrustedIssuerRegistry()

    # ------------------------------------------------------------------
    # Credential verification
    # ------------------------------------------------------------------

    def verify_credential(self, vc: Dict[str, Any]) -> VerificationResult:
        t0 = time.perf_counter()
        result = VerificationResult()

        self._check_structure(vc, result)
        if result.valid:
            self._check_schema(vc, result)
            self._check_temporal(vc, result)
            self._check_revocation(vc, result)
            self._check_signature(vc, result)
            self._check_disclosures(vc, result)

        result.elapsed_ms = (time.perf_counter() - t0) * 1000
        return result

    def _check_structure(self, vc: Dict[str, Any],
                         result: VerificationResult) -> None:
        for prop in self.REQUIRED_VC_PROPERTIES:
            if prop not in vc:
                result.fail("structure", f"missing required property '{prop}'")
        if "structure" not in result.checks:
            types = vc.get("type", [])
            if "VerifiableCredential" not in types:
                result.fail("structure",
                            "'type' must include 'VerifiableCredential'")
        subject = vc.get("credentialSubject", {})
        if isinstance(subject, dict) and "id" not in subject:
            result.warnings.append("credentialSubject has no 'id'")
        result.ok("structure")

    def _check_schema(self, vc: Dict[str, Any],
                      result: VerificationResult) -> None:
        specific_types = [t for t in vc.get("type", [])
                          if t != "VerifiableCredential"]
        if not specific_types:
            result.warnings.append("no specific credential type to validate")
            result.ok("schema")
            return
        cred_type = specific_types[0]
        if get_schema(cred_type) is None:
            result.warnings.append(f"no registered schema for '{cred_type}'")
            result.ok("schema")
            return

        subject = dict(vc.get("credentialSubject", {}))
        subject.pop("id", None)
        if "claimDigests" in subject:
            # Selective-disclosure credential: raw claims are not present in
            # the signed document; schema validation applies to disclosed
            # claims only (partial, by design).
            disclosed = vc.get("disclosedClaims", {})
            partial = {k: v["value"] for k, v in disclosed.items()}
            schema = get_schema(cred_type)
            specs = {p.name: p for p in schema.properties}
            for name, value in partial.items():
                spec = specs.get(name)
                if spec and not isinstance(value, spec.types):
                    result.fail("schema",
                                f"disclosed claim '{name}' has wrong type")
                elif spec and spec.validator and not spec.validator(value):
                    result.fail("schema",
                                f"disclosed claim '{name}' failed validation")
            result.ok("schema")
            return

        ok, errors = validate_claims(cred_type, subject)
        if not ok:
            for e in errors:
                result.fail("schema", e)
        result.ok("schema")

    def _check_temporal(self, vc: Dict[str, Any],
                        result: VerificationResult) -> None:
        now = utc_now_iso()
        valid_from = vc.get("validFrom")
        valid_until = vc.get("validUntil")
        # ISO-8601 Zulu strings compare correctly as strings
        if valid_from and now < valid_from:
            result.fail("temporal", f"not yet valid (validFrom={valid_from})")
        if valid_until and now > valid_until:
            result.fail("temporal", f"expired (validUntil={valid_until})")
        result.ok("temporal")

    def _check_revocation(self, vc: Dict[str, Any],
                          result: VerificationResult) -> None:
        status = vc.get("credentialStatus")
        if status is None:
            result.ok("revocation")
            return
        if self.revocation_registry is None:
            result.warnings.append(
                "credential declares credentialStatus but verifier has no "
                "revocation registry configured"
            )
            result.ok("revocation")
            return
        if self.revocation_registry.is_revoked(vc.get("id", "")):
            info = self.revocation_registry.revocation_info(vc["id"]) or {}
            result.fail("revocation",
                        f"credential revoked at {info.get('revokedAt')} "
                        f"(reason: {info.get('reason')})")
        result.ok("revocation")

    def _check_signature(self, vc: Dict[str, Any],
                         result: VerificationResult) -> None:
        proof = vc.get("proof")
        if not isinstance(proof, dict) or "proofValue" not in proof:
            result.fail("signature", "missing or malformed proof")
            return
        try:
            # disclosedClaims is holder-attached, never part of the
            # issuer-signed document — strip before recovery.
            signed_doc = {k: v for k, v in vc.items()
                          if k != "disclosedClaims"}
            recovered = recover_signer(signed_doc, proof).lower()
        except Exception as exc:
            result.fail("signature", f"signature recovery failed: {exc}")
            return

        issuer = vc.get("issuer")
        issuer_did = issuer.get("id") if isinstance(issuer, dict) else issuer
        expected = address_from_did(issuer_did) \
            or self.trusted_issuers.address_for(issuer_did)
        if expected is None:
            result.fail("signature",
                        f"cannot determine signing address for issuer "
                        f"'{issuer_did}' (not address-bearing, not in "
                        f"trusted registry)")
            return
        if recovered != expected:
            result.fail("signature",
                        f"recovered signer {recovered} does not match "
                        f"issuer {issuer_did}")
        result.ok("signature")

    def _check_disclosures(self, vc: Dict[str, Any],
                           result: VerificationResult) -> None:
        disclosed = vc.get("disclosedClaims")
        if disclosed is None:
            result.ok("disclosure")
            return
        digests = vc.get("credentialSubject", {}).get("claimDigests", {})
        if not digests:
            result.fail("disclosure",
                        "disclosedClaims present but credential carries no "
                        "claimDigests")
            return
        for name, entry in disclosed.items():
            if name not in digests:
                result.fail("disclosure", f"no signed digest for claim '{name}'")
                continue
            recomputed = claim_digest(name, entry["value"], entry["salt"])
            if recomputed != digests[name]:
                result.fail("disclosure",
                            f"digest mismatch for claim '{name}' — value or "
                            f"salt was tampered with")
        result.ok("disclosure")

    # ------------------------------------------------------------------
    # Presentation verification
    # ------------------------------------------------------------------

    def verify_presentation(self, vp: Dict[str, Any],
                            expected_challenge: str,
                            expected_domain: str
                            ) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify a Verifiable Presentation and every credential inside it.

        Returns (is_valid, report) where report contains the VP-level
        result plus one entry per embedded credential.
        """
        t0 = time.perf_counter()
        vp_result = VerificationResult()

        proof = vp.get("proof")
        if not isinstance(proof, dict) or "proofValue" not in proof:
            vp_result.fail("vp_signature", "missing or malformed proof")
        else:
            if proof.get("proofPurpose") != "authentication":
                vp_result.fail("vp_purpose",
                               "presentation proofPurpose must be "
                               "'authentication'")
            if proof.get("challenge") != expected_challenge:
                vp_result.fail("vp_challenge",
                               "challenge mismatch (possible replay)")
            if proof.get("domain") != expected_domain:
                vp_result.fail("vp_domain", "domain mismatch (wrong audience)")

            holder_did = vp.get("holder")
            expected_addr = address_from_did(holder_did) \
                or self.trusted_issuers.address_for(holder_did)
            try:
                recovered = recover_signer(vp, proof).lower()
                if expected_addr is None:
                    vp_result.fail("vp_signature",
                                   f"cannot determine holder address for "
                                   f"'{holder_did}'")
                elif recovered != expected_addr:
                    vp_result.fail("vp_signature",
                                   f"presentation signed by {recovered}, "
                                   f"not holder {holder_did}")
                else:
                    vp_result.ok("vp_signature")
            except Exception as exc:
                vp_result.fail("vp_signature", f"recovery failed: {exc}")

        vp_result.ok("vp_challenge")
        vp_result.ok("vp_domain")
        vp_result.ok("vp_purpose")

        credential_reports: List[Dict[str, Any]] = []
        all_creds_valid = True
        for vc in vp.get("verifiableCredential", []):
            cred_result = self.verify_credential(vc)
            credential_reports.append({
                "credentialId": vc.get("id"),
                **cred_result.to_dict(),
            })
            all_creds_valid = all_creds_valid and cred_result.valid

        vp_result.elapsed_ms = (time.perf_counter() - t0) * 1000
        is_valid = vp_result.valid and all_creds_valid
        report = {
            "valid": is_valid,
            "presentation": vp_result.to_dict(),
            "credentials": credential_reports,
        }
        return is_valid, report


# ---------------------------------------------------------------------------
# W3C VC DM 2.0 compliance self-check (feeds w3c-compliance.yml)
# ---------------------------------------------------------------------------

COMPLIANCE_CHECKLIST = [
    ("@context with base v2 context", True),
    ("credential 'id' (URI)", True),
    ("'type' incl. VerifiableCredential", True),
    ("'issuer' identified by DID", True),
    ("'validFrom' / 'validUntil' (v2 vocabulary)", True),
    ("'credentialSubject' with subject id", True),
    ("'credentialSchema' declared", True),
    ("'credentialStatus' (revocation)", True),
    ("Securing mechanism: embedded DataIntegrityProof", True),
    ("Proof purposes: assertionMethod / authentication", True),
    ("VP with 'holder' + challenge/domain binding", True),
    ("Selective disclosure mechanism", True),
    ("JSON-LD canonicalization (URDNA2015)", False),  # deviation: canonical JSON
    ("Registered cryptosuite (ecdsa-rdfc-2019 etc.)", False),  # thesis-defined suite
]


def compliance_score() -> Tuple[float, List[Tuple[str, bool]]]:
    """Return (percentage, checklist) for the thesis compliance matrix."""
    passed = sum(1 for _, ok in COMPLIANCE_CHECKLIST if ok)
    return 100.0 * passed / len(COMPLIANCE_CHECKLIST), COMPLIANCE_CHECKLIST


if __name__ == "__main__":
    import json as _json
    from vc_issuer import CredentialIssuer
    from vc_holder import HolderWallet

    print("=== Verifier Demo: full issue → present → verify pipeline ===\n")

    issuer = CredentialIssuer.with_ethr_did()
    wallet = HolderWallet.with_ethr_did()
    verifier = CredentialVerifier(
        revocation_registry=issuer.revocation_registry
    )

    envelope = issuer.issue_credential(
        credential_type="VehicleBirthCertificate",
        subject_did=wallet.holder_did,
        claims={
            "vin": "5YJ3E1EA0PF123456",
            "make": "Tesla", "model": "Model 3", "year": 2024,
            "manufacturingDate": "2024-01-15",
            "manufacturerDid": issuer.issuer_did,
        },
        validity_days=None,
    )
    cid = wallet.store_credential(envelope)
    vp = wallet.create_presentation([cid], challenge="nonce-42",
                                    domain="dmv.gov.bc.ca")

    ok, report = verifier.verify_presentation(vp, "nonce-42", "dmv.gov.bc.ca")
    print(f"Presentation valid: {ok}")
    print(_json.dumps(report, indent=2))

    print("\n--- Replay attempt with wrong challenge ---")
    ok2, _ = verifier.verify_presentation(vp, "different-nonce",
                                          "dmv.gov.bc.ca")
    print(f"Replay accepted: {ok2} (must be False)")

    print("\n--- Revocation ---")
    issuer.revoke_credential(cid, reason="test revocation")
    result = verifier.verify_credential(
        wallet.get_credential(cid)
    )
    print(f"After revoke, credential valid: {result.valid} (must be False)")

    score, checklist = compliance_score()
    print(f"\nW3C VC DM 2.0 compliance self-score: {score:.1f}%")
    for item, passed in checklist:
        print(f"  {'✅' if passed else '❌'} {item}")
