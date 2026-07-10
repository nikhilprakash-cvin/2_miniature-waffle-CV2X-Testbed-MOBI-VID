#!/usr/bin/env python3
"""
W3C Compliance Checker — EXECUTABLE validation
==============================================

Every check in this file RUNS the actual implementation and records the
observed outcome. Nothing is hardcoded to PASS.

What gets exercised:
- W3C DID Core v1.0 ......... 2_w3c-ssi-layer/did-resolution/did_resolver.py
                              (did:ethr, did:nft, did:key, did:mobi)
- W3C VC Data Model v2.0 .... 2_w3c-ssi-layer/verifiable-credentials/
                              (CredentialIssuer, HolderWallet,
                               CredentialVerifier, RevocationRegistry,
                               selective disclosure)
- SSI Principles ............ assessed qualitatively; explicitly EXCLUDED
                              from the executable compliance score.

Negative checks are first-class citizens: forged, tampered, expired and
revoked credentials must be rejected; replayed / wrong-audience / stolen
presentations must be rejected; malformed DIDs must produce resolution
errors. A security property that cannot fail is not being tested.

Known, documented deviations (executed and honestly counted as FAIL):
- Canonicalization is deterministic JSON, not URDNA2015 / RDFC-1.0.
- Cryptosuite 'eip191-secp256k1-recovery-2024' is thesis-defined, not in
  the W3C Data Integrity cryptosuite registry.

Exit code: 0 if executable score >= 90%, else 1.

Author: Nikhil Prakash
Thesis: MASc, UBC ECE
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# sys.path bootstrap: import the canonical SSI layer, not a local copy
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VC_DIR = REPO_ROOT / "2_w3c-ssi-layer" / "verifiable-credentials"
DID_DIR = REPO_ROOT / "2_w3c-ssi-layer" / "did-resolution"
for _p in (str(VC_DIR), str(DID_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vc_schemas import VC_CONTEXT_V2  # noqa: E402
from vc_issuer import (  # noqa: E402
    CredentialIssuer, canonicalize, recover_signer,
)
from vc_holder import HolderWallet  # noqa: E402
from vc_verifier import CredentialVerifier  # noqa: E402
from did_resolver import DIDResolver  # noqa: E402

# W3C Data Integrity cryptosuite registry (VC specs directory), as of the
# VC DM 2.0 Recommendation. Used to test the cryptosuite deviation.
W3C_REGISTERED_CRYPTOSUITES = {
    "ecdsa-rdfc-2019", "ecdsa-jcs-2019", "ecdsa-sd-2023",
    "eddsa-rdfc-2022", "eddsa-jcs-2022", "bbs-2023",
}

DID_CORE_CONTEXT = "https://www.w3.org/ns/did/v1"
VIN = "5YJ3E1EA0PF123456"

KEY_MATERIAL_PROPS = ("publicKeyHex", "publicKeyBase58",
                      "publicKeyJwk", "blockchainAccountId")


def parse_zulu(value: str) -> datetime:
    """Parse the XML-Schema dateTime format the VC layer emits."""
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ComplianceCheck:
    """Single compliance check with its executed outcome."""
    spec: str          # Specification name
    section: str       # Section number / name
    requirement: str   # What is required
    status: str        # PASS, FAIL, PARTIAL, QUALITATIVE
    notes: str = ""    # Observed behavior / failure reason


# Return type of a check function: a notes string (=> PASS) or an explicit
# (status, notes) tuple. Raising AssertionError/Exception => FAIL.
CheckOutcome = Union[str, Tuple[str, str], None]


class W3CComplianceChecker:
    """
    Executable W3C compliance checker.

    Each check calls into the real DID resolver / VC stack, asserts a
    concrete behavior, and records PASS/FAIL/PARTIAL from what actually
    happened. SSI principles are recorded as QUALITATIVE and excluded
    from the executable score.
    """

    def __init__(self):
        self.checks: List[ComplianceCheck] = []
        self.pass_count = 0
        self.fail_count = 0
        self.partial_count = 0
        self.qualitative_count = 0

    # ------------------------------------------------------------------
    # Check execution machinery
    # ------------------------------------------------------------------

    def _run_check(self, spec: str, section: str, requirement: str,
                   fn: Callable[[], CheckOutcome]) -> None:
        """Execute one check function and record its real outcome."""
        try:
            outcome = fn()
            if isinstance(outcome, tuple):
                status, notes = outcome
            else:
                status, notes = "PASS", (outcome or "behavior verified")
        except AssertionError as exc:
            status, notes = "FAIL", (str(exc) or "assertion failed")
        except Exception as exc:  # check code itself blew up => FAIL
            status, notes = "FAIL", f"{type(exc).__name__}: {exc}"
        self._record(spec, section, requirement, status, notes)

    def _record(self, spec: str, section: str, requirement: str,
                status: str, notes: str) -> None:
        self.checks.append(
            ComplianceCheck(spec, section, requirement, status, notes))
        if status == "PASS":
            self.pass_count += 1
            symbol = "✅"
        elif status == "FAIL":
            self.fail_count += 1
            symbol = "❌"
        elif status == "PARTIAL":
            self.partial_count += 1
            symbol = "⚠️ "
        else:  # QUALITATIVE
            self.qualitative_count += 1
            symbol = "📝"
        print(f"{symbol} [{spec} {section}] {requirement}")
        if notes:
            print(f"   → {notes}")

    # ------------------------------------------------------------------
    # Top level
    # ------------------------------------------------------------------

    def run_all_checks(self):
        """Run all compliance checks against the live implementation."""
        print("=" * 80)
        print(" W3C COMPLIANCE CHECKER — EXECUTABLE VALIDATION")
        print(" (every check below runs real code and records the outcome)")
        print("=" * 80)
        print()

        self._check_did_core()
        self._check_vc_data_model()
        self._check_presentations()
        self._check_selective_disclosure()
        self._check_securing_mechanism_deviations()
        self._check_ssi_principles()

    # ------------------------------------------------------------------
    # W3C DID Core v1.0 — executed against DIDResolver
    # ------------------------------------------------------------------

    def _check_did_core(self):
        print("📋 W3C DID Core v1.0 — executing DIDResolver")
        print("-" * 80)

        spec = "DID Core v1.0"
        resolver = DIDResolver()
        address = "0x" + "ab12" * 10  # syntactically valid 20-byte address

        dids = {
            "ethr": f"did:ethr:0x1:{address}",
            "nft": f"did:nft:0x1:{address}:42",
            "key": f"did:key:0x1:{address}",
            "mobi": f"did:mobi:{VIN}",
        }
        results = {name: resolver.resolve(did) for name, did in dids.items()}
        docs = {}
        for name, res in results.items():
            if res.didDocument is not None:
                docs[name] = res.didDocument.to_dict()

        def check_syntax():
            for name, did in dids.items():
                res = results[name]
                assert res.didResolutionMetadata.error is None, \
                    f"{did} failed to resolve: {res.didResolutionMetadata.error}"
                assert res.didDocument is not None, f"{did} returned no document"
                assert did.startswith("did:"), f"{did} lacks 'did:' scheme"
            return f"resolved {len(dids)} conformant DIDs (ethr, nft, key, mobi)"
        self._run_check(spec, "3.1",
                        "Conformant DIDs (did:method:id) MUST resolve for all "
                        "4 implemented methods", check_syntax)

        def check_malformed():
            res = resolver.resolve("not-a-did")
            assert res.didResolutionMetadata.error is not None, \
                "resolver accepted a string without the 'did:' scheme"
            assert res.didDocument is None, \
                "resolver returned a document for a malformed DID"
            return (f"'not-a-did' rejected with error="
                    f"'{res.didResolutionMetadata.error}', didDocument=null")
        self._run_check(spec, "3.1",
                        "Malformed DID (no 'did:' scheme) MUST produce a "
                        "resolution error, not a document", check_malformed)

        def check_unsupported_method():
            res = resolver.resolve("did:example:12345")
            err = res.didResolutionMetadata.error
            assert err is not None and res.didDocument is None, \
                "resolver produced a document for an unsupported DID method"
            if err == "methodNotSupported":
                return "error='methodNotSupported' as specified"
            return ("PARTIAL",
                    f"error surfaced (resolution safely refused) but code is "
                    f"'{err}' instead of 'methodNotSupported'")
        self._run_check(spec, "7.1.2",
                        "Unsupported DID method MUST yield a resolution "
                        "error ('methodNotSupported')", check_unsupported_method)

        def check_malformed_nft():
            res = resolver.resolve(f"did:nft:0x1:{address}")  # tokenId missing
            assert res.didResolutionMetadata.error is not None, \
                "resolver accepted a did:nft missing its tokenId"
            assert res.didDocument is None
            return (f"did:nft without tokenId rejected with error="
                    f"'{res.didResolutionMetadata.error}'")
        self._run_check(spec, "3.1",
                        "Method-specific identifier violating the method's "
                        "ABNF (did:nft w/o tokenId) MUST error", check_malformed_nft)

        def check_id_property():
            for name, did in dids.items():
                doc = docs.get(name)
                assert doc is not None, f"no document for {did}"
                assert doc.get("id") == did, \
                    f"{name}: document id '{doc.get('id')}' != resolved DID"
            return "all 4 documents carry id equal to the resolved DID"
        self._run_check(spec, "5.1.1",
                        "DID document MUST contain 'id' equal to the DID "
                        "that was resolved", check_id_property)

        def check_context():
            for name, doc in docs.items():
                ctx = doc.get("@context")
                assert isinstance(ctx, list) and DID_CORE_CONTEXT in ctx, \
                    f"{name}: @context missing '{DID_CORE_CONTEXT}'"
            return f"all 4 documents include '{DID_CORE_CONTEXT}'"
        self._run_check(spec, "6.3",
                        "JSON-LD DID document MUST include the DID Core "
                        "@context", check_context)

        def check_controller():
            doc = docs["ethr"]
            controller = doc.get("controller")
            assert controller is not None, "did:ethr document has no controller"
            assert str(controller).startswith("did:"), \
                f"controller '{controller}' is not a DID"
            return f"did:ethr controller = {controller}"
        self._run_check(spec, "5.1.2",
                        "'controller', when present, MUST be a valid DID",
                        check_controller)

        def check_verification_methods():
            for name, doc in docs.items():
                vms = doc.get("verificationMethod")
                assert vms, f"{name}: no verificationMethod"
                for vm in vms:
                    for prop in ("id", "type", "controller"):
                        assert vm.get(prop), \
                            f"{name}: verification method missing '{prop}'"
            return "id/type/controller present on every verification method (4 methods)"
        self._run_check(spec, "5.2",
                        "Verification methods MUST have 'id', 'type' and "
                        "'controller'", check_verification_methods)

        def check_key_material():
            placeholder = []
            for name, doc in docs.items():
                for vm in doc.get("verificationMethod", []):
                    material = [p for p in KEY_MATERIAL_PROPS if vm.get(p)]
                    assert material, f"{name}: verification method has no key material"
                    if vm.get("publicKeyHex") == "0x...":
                        placeholder.append(name)
            if placeholder:
                return ("PARTIAL",
                        f"key material present for all methods, but "
                        f"{placeholder} carry the placeholder '0x...' instead "
                        f"of a real key (registry lookup not implemented)")
            return "verifiable key material on every verification method"
        self._run_check(spec, "5.2",
                        "Verification methods MUST carry public key material",
                        check_key_material)

        def check_authentication():
            for name, doc in docs.items():
                auth = doc.get("authentication")
                assert auth, f"{name}: no authentication relationship"
                vm_ids = {vm["id"] for vm in doc.get("verificationMethod", [])}
                for ref in auth:
                    assert ref in vm_ids, \
                        f"{name}: authentication ref '{ref}' dangling"
            return "authentication references resolve to in-document methods (4 methods)"
        self._run_check(spec, "5.3.1",
                        "'authentication' references MUST resolve to "
                        "verification methods in the document", check_authentication)

        def check_assertion_method():
            with_am = []
            for name, doc in docs.items():
                am = doc.get("assertionMethod")
                if not am:
                    continue
                vm_ids = {vm["id"] for vm in doc.get("verificationMethod", [])}
                for ref in am:
                    assert ref in vm_ids, \
                        f"{name}: assertionMethod ref '{ref}' dangling"
                with_am.append(name)
            assert with_am, "no document exposes assertionMethod at all"
            return (f"valid assertionMethod on {with_am} "
                    f"(property is optional for the others)")
        self._run_check(spec, "5.3.2",
                        "'assertionMethod', when present, MUST reference "
                        "in-document verification methods", check_assertion_method)

        def check_services():
            for name in ("nft", "mobi"):
                services = docs[name].get("service")
                assert services, f"{name}: no service endpoints"
                for svc in services:
                    for prop in ("id", "type", "serviceEndpoint"):
                        assert svc.get(prop), \
                            f"{name}: service missing '{prop}'"
            return "did:nft and did:mobi services all carry id/type/serviceEndpoint"
        self._run_check(spec, "5.4",
                        "Services MUST have 'id', 'type' and "
                        "'serviceEndpoint'", check_services)

        def check_resolution_metadata():
            for name, res in results.items():
                meta = res.didResolutionMetadata
                assert meta.contentType == "application/did+ld+json", \
                    f"{name}: contentType={meta.contentType}"
                assert meta.retrieved, f"{name}: no 'retrieved' timestamp"
                datetime.fromisoformat(meta.retrieved)  # must parse
            return "contentType + parseable 'retrieved' timestamp on all resolutions"
        self._run_check(spec, "7.1.2",
                        "Resolution MUST return DID resolution metadata "
                        "(contentType, retrieved)", check_resolution_metadata)

        def check_document_metadata():
            for name, res in results.items():
                created = res.didDocumentMetadata.created
                assert created, f"{name}: documentMetadata.created missing"
                datetime.fromisoformat(created)
            return "documentMetadata.created present and ISO-8601 parseable"
        self._run_check(spec, "7.1.3",
                        "Resolution SHOULD return DID document metadata "
                        "('created')", check_document_metadata)

        def check_fragment_dereference():
            did = dids["ethr"]
            target = f"{did}#controller"
            doc = docs["ethr"]
            matches = [vm for vm in doc["verificationMethod"]
                       if vm["id"] == target]
            assert matches, f"cannot dereference fragment DID URL {target}"
            return f"'{target}' dereferences to a verification method"
        self._run_check(spec, "7.2",
                        "DID URL fragment MUST dereference to a resource "
                        "inside the DID document", check_fragment_dereference)

        print()

    # ------------------------------------------------------------------
    # W3C VC Data Model v2.0 — executed against the VC stack
    # ------------------------------------------------------------------

    def _vc_fixtures(self):
        """Fresh issuer / wallet / verifier trio."""
        issuer = CredentialIssuer.with_ethr_did()
        wallet = HolderWallet.with_ethr_did()
        verifier = CredentialVerifier(
            revocation_registry=issuer.revocation_registry)
        return issuer, wallet, verifier

    @staticmethod
    def _birth_claims(issuer) -> Dict[str, Any]:
        return {
            "vin": VIN,
            "make": "Tesla",
            "model": "Model 3",
            "year": 2024,
            "manufacturingDate": "2024-01-15",
            "manufacturerDid": issuer.issuer_did,
        }

    def _check_vc_data_model(self):
        print("📋 W3C VC Data Model v2.0 — executing issue → verify pipeline")
        print("-" * 80)

        spec = "VC Data Model v2.0"
        issuer, wallet, verifier = self._vc_fixtures()
        envelope = issuer.issue_credential(
            credential_type="VehicleBirthCertificate",
            subject_did=wallet.holder_did,
            claims=self._birth_claims(issuer),
            validity_days=365,
        )
        vc = envelope["verifiableCredential"]

        def check_context():
            ctx = vc.get("@context")
            assert isinstance(ctx, list) and ctx, "@context missing or not a list"
            assert ctx[0] == VC_CONTEXT_V2, \
                f"first @context entry is '{ctx[0]}', expected '{VC_CONTEXT_V2}'"
            return f"@context[0] == '{VC_CONTEXT_V2}' on a freshly issued VC"
        self._run_check(spec, "Contexts",
                        "@context MUST be present with the base v2 context "
                        "first", check_context)

        def check_id():
            cid = vc.get("id")
            assert cid and cid.startswith("urn:uuid:"), \
                f"credential id '{cid}' is not a URN/URI"
            return f"credential id is a URI: {cid}"
        self._run_check(spec, "Identifiers",
                        "Credential 'id', when present, MUST be a URL/URI",
                        check_id)

        def check_type():
            types = vc.get("type")
            assert isinstance(types, list), "'type' missing or not an array"
            assert "VerifiableCredential" in types, \
                "'type' lacks 'VerifiableCredential'"
            specific = [t for t in types if t != "VerifiableCredential"]
            assert specific, "no specific credential type alongside the base type"
            return f"type = {types}"
        self._run_check(spec, "Types",
                        "'type' MUST include 'VerifiableCredential' plus a "
                        "specific type", check_type)

        def check_issuer():
            iss = vc.get("issuer")
            assert iss == issuer.issuer_did, \
                f"issuer '{iss}' != issuing DID '{issuer.issuer_did}'"
            assert str(iss).startswith("did:"), "issuer is not a DID/URI"
            return f"issuer = {iss}"
        self._run_check(spec, "Issuer",
                        "'issuer' MUST be present and be a URI (DID) "
                        "identifying the issuer", check_issuer)

        def check_subject():
            subject = vc.get("credentialSubject")
            assert isinstance(subject, dict), "credentialSubject missing"
            assert subject.get("id") == wallet.holder_did, \
                "credentialSubject.id != holder DID"
            claim_keys = set(subject) - {"id"}
            assert claim_keys >= {"vin", "make", "model"}, \
                f"expected vehicle claims, got {sorted(claim_keys)}"
            return (f"subject id = holder DID, "
                    f"{len(claim_keys)} claims carried")
        self._run_check(spec, "Credential Subject",
                        "'credentialSubject' MUST be present with claims "
                        "about the subject", check_subject)

        def check_validity():
            vf, vu = vc.get("validFrom"), vc.get("validUntil")
            assert vf, "validFrom missing (v2 vocabulary)"
            assert vu, "validUntil missing (issued with validity_days=365)"
            t_from, t_until = parse_zulu(vf), parse_zulu(vu)
            assert t_until > t_from, "validUntil not after validFrom"
            return f"validFrom={vf}, validUntil={vu}, both XML-Schema dateTime"
        self._run_check(spec, "Validity Period",
                        "'validFrom'/'validUntil' MUST be valid XML-Schema "
                        "dateTime values (v2 renames issuanceDate)", check_validity)

        def check_schema_property():
            schema = vc.get("credentialSchema")
            assert isinstance(schema, dict), "credentialSchema missing"
            assert schema.get("id") and schema.get("type"), \
                f"credentialSchema lacks id/type: {schema}"
            return f"credentialSchema: type={schema['type']}, id={schema['id']}"
        self._run_check(spec, "Data Schemas",
                        "'credentialSchema', when present, MUST have 'id' "
                        "and 'type'", check_schema_property)

        def check_status_property():
            status = vc.get("credentialStatus")
            assert isinstance(status, dict), "credentialStatus missing"
            assert status.get("id") and status.get("type"), \
                f"credentialStatus lacks id/type: {status}"
            return f"credentialStatus: type={status['type']}"
        self._run_check(spec, "Status",
                        "'credentialStatus', when present, MUST have 'id' "
                        "and 'type'", check_status_property)

        def check_proof_structure():
            proof = vc.get("proof")
            assert isinstance(proof, dict), "no embedded proof"
            assert proof.get("type") == "DataIntegrityProof", \
                f"proof type is '{proof.get('type')}'"
            for prop in ("cryptosuite", "created", "verificationMethod",
                         "proofPurpose", "proofValue"):
                assert proof.get(prop), f"proof missing '{prop}'"
            assert proof["proofPurpose"] == "assertionMethod", \
                f"credential proofPurpose is '{proof['proofPurpose']}'"
            parse_zulu(proof["created"])
            return ("DataIntegrityProof with cryptosuite/created/"
                    "verificationMethod/proofPurpose=assertionMethod/proofValue")
        self._run_check(spec, "Securing Mechanisms",
                        "Credential MUST carry a DataIntegrityProof with all "
                        "required proof properties", check_proof_structure)

        def check_signature_binding():
            recovered = recover_signer(vc, vc["proof"])
            assert recovered == issuer.address, \
                f"recovered {recovered}, expected issuer {issuer.address}"
            return (f"secp256k1 recovery yields the issuer address "
                    f"{recovered} (offline, no chain round-trip)")
        self._run_check(spec, "Securing Mechanisms",
                        "Proof MUST be cryptographically bound to the "
                        "issuer's key (recoverable signature)", check_signature_binding)

        def check_round_trip():
            result = verifier.verify_credential(vc)
            assert result.valid, f"verification failed: {result.errors}"
            assert all(result.checks.values()), \
                f"sub-checks not all true: {result.checks}"
            return (f"verify_credential => valid, sub-checks "
                    f"{sorted(result.checks)} all true "
                    f"({result.elapsed_ms:.2f} ms)")
        self._run_check(spec, "Verification",
                        "A well-formed, freshly issued credential MUST "
                        "verify end-to-end", check_round_trip)

        def check_missing_property_rejected():
            broken = {k: v for k, v in vc.items() if k != "issuer"}
            result = verifier.verify_credential(broken)
            assert not result.valid, \
                "credential without 'issuer' was accepted"
            assert any("issuer" in e for e in result.errors), result.errors
            return "credential stripped of 'issuer' rejected by structure check"
        self._run_check(spec, "Verification",
                        "NEGATIVE: credential missing a required property "
                        "MUST be rejected", check_missing_property_rejected)

        def check_tamper_rejected():
            tampered = json.loads(json.dumps(vc))
            tampered["credentialSubject"]["make"] = "Lada"
            result = verifier.verify_credential(tampered)
            assert not result.valid, "tampered claim was accepted"
            assert any("signature" in e for e in result.errors), result.errors
            return "claim edit ('make': Tesla→Lada) breaks signature recovery"
        self._run_check(spec, "Securing Mechanisms",
                        "NEGATIVE: tampering with a signed claim MUST "
                        "invalidate the proof", check_tamper_rejected)

        def check_forgery_rejected():
            # Attacker signs with their own key but claims a victim DID
            victim_did = "did:ethr:0x1:0x" + "d" * 40
            attacker = CredentialIssuer(issuer_did=victim_did)
            forged = attacker.issue_credential(
                "VehicleBirthCertificate", wallet.holder_did,
                claims={**self._birth_claims(issuer),
                        "manufacturerDid": victim_did},
            )["verifiableCredential"]
            result = verifier.verify_credential(forged)
            assert not result.valid, "forged credential was accepted"
            assert any("does not match issuer" in e for e in result.errors), \
                result.errors
            return ("recovered signer != address embedded in the claimed "
                    "issuer DID → rejected")
        self._run_check(spec, "Securing Mechanisms",
                        "NEGATIVE: credential forged under another issuer's "
                        "DID MUST be rejected", check_forgery_rejected)

        def check_expired_rejected():
            expired = dict(vc)
            expired["validUntil"] = "2020-01-01T00:00:00Z"
            result = verifier.verify_credential(expired)
            assert not result.valid, "expired credential was accepted"
            assert any("expired" in e for e in result.errors), result.errors
            return "validUntil in the past → temporal check rejects"
        self._run_check(spec, "Validity Period",
                        "NEGATIVE: credential past 'validUntil' MUST be "
                        "rejected", check_expired_rejected)

        def check_revoked_rejected():
            iss2, wal2, ver2 = self._vc_fixtures()
            fresh = iss2.issue_credential(
                "VehicleBirthCertificate", wal2.holder_did,
                claims=self._birth_claims(iss2))["verifiableCredential"]
            assert ver2.verify_credential(fresh).valid, \
                "credential invalid even before revocation"
            iss2.revoke_credential(fresh["id"], reason="compliance test")
            result = ver2.verify_credential(fresh)
            assert not result.valid, "revoked credential was accepted"
            assert any("revoked" in e for e in result.errors), result.errors
            return ("valid before revocation, rejected after "
                    "RevocationRegistry.revoke()")
        self._run_check(spec, "Status",
                        "NEGATIVE: revoked credential MUST fail status "
                        "checking", check_revoked_rejected)

        def check_schema_enforced():
            try:
                issuer.issue_credential(
                    "VehicleBirthCertificate", wallet.holder_did,
                    claims={"vin": "BAD", "make": "Tesla"})
            except ValueError as exc:
                assert "schema validation" in str(exc), str(exc)
                return f"issuance refused: {exc}"
            raise AssertionError("schema-invalid claims were issued anyway")
        self._run_check(spec, "Data Schemas",
                        "NEGATIVE: claims violating the declared schema MUST "
                        "be refused at issuance", check_schema_enforced)

        print()

    # ------------------------------------------------------------------
    # Verifiable Presentations — executed against HolderWallet + verifier
    # ------------------------------------------------------------------

    def _check_presentations(self):
        print("📋 W3C VC Data Model v2.0 — executing Verifiable Presentations")
        print("-" * 80)

        spec = "VC Data Model v2.0"
        challenge, domain = "nonce-8f3a", "dmv.gov.bc.ca"
        issuer, wallet, verifier = self._vc_fixtures()
        cid = wallet.store_credential(issuer.issue_credential(
            "VehicleBirthCertificate", wallet.holder_did,
            claims=self._birth_claims(issuer)))
        vp = wallet.create_presentation([cid], challenge=challenge,
                                        domain=domain)

        def check_vp_structure():
            assert vp.get("@context", [None])[0] == VC_CONTEXT_V2, \
                "VP @context does not start with the base v2 context"
            assert "VerifiablePresentation" in vp.get("type", []), \
                "VP type lacks 'VerifiablePresentation'"
            assert vp.get("holder") == wallet.holder_did, "holder DID missing"
            creds = vp.get("verifiableCredential")
            assert isinstance(creds, list) and len(creds) == 1, \
                "verifiableCredential array missing/empty"
            return "@context/type/holder/verifiableCredential all present"
        self._run_check(spec, "Verifiable Presentations",
                        "VP MUST have '@context', 'type' incl. "
                        "VerifiablePresentation, 'holder' and credentials",
                        check_vp_structure)

        def check_vp_proof():
            proof = vp.get("proof")
            assert isinstance(proof, dict) and proof.get("proofValue"), \
                "VP has no signed proof"
            assert proof.get("proofPurpose") == "authentication", \
                f"VP proofPurpose is '{proof.get('proofPurpose')}'"
            assert proof.get("challenge") == challenge, "challenge not bound"
            assert proof.get("domain") == domain, "domain not bound"
            return ("holder-signed proof with proofPurpose=authentication, "
                    "challenge and domain bound")
        self._run_check(spec, "Verifiable Presentations",
                        "VP proof MUST bind challenge + domain with "
                        "proofPurpose 'authentication'", check_vp_proof)

        def check_vp_verifies():
            ok, report = verifier.verify_presentation(vp, challenge, domain)
            assert ok, f"valid VP rejected: {report['presentation']['errors']}"
            assert report["credentials"][0]["valid"], \
                "embedded credential failed inside a valid VP"
            return ("VP and embedded credential verify against the expected "
                    "challenge/domain")
        self._run_check(spec, "Verifiable Presentations",
                        "A holder-signed VP MUST verify, including every "
                        "embedded credential", check_vp_verifies)

        def check_replay_rejected():
            ok, report = verifier.verify_presentation(
                vp, "different-nonce", domain)
            assert not ok, "VP accepted under a different challenge (replay!)"
            errors = report["presentation"]["errors"]
            assert any("challenge" in e for e in errors), errors
            return "same VP replayed under a new challenge → rejected"
        self._run_check(spec, "Verifiable Presentations",
                        "NEGATIVE: replayed VP (stale challenge) MUST be "
                        "rejected", check_replay_rejected)

        def check_wrong_domain_rejected():
            ok, report = verifier.verify_presentation(
                vp, challenge, "evil.example")
            assert not ok, "VP accepted for the wrong audience"
            errors = report["presentation"]["errors"]
            assert any("domain" in e for e in errors), errors
            return "VP presented to a different domain → rejected"
        self._run_check(spec, "Verifiable Presentations",
                        "NEGATIVE: VP bound to another domain/audience MUST "
                        "be rejected", check_wrong_domain_rejected)

        def check_stolen_credential_rejected():
            # Thief copies the credential, claims the holder DID, but signs
            # with their own key.
            thief = HolderWallet(holder_did=wallet.holder_did)
            stolen_cid = thief.store_credential(
                {"verifiableCredential": wallet.get_credential(cid)})
            stolen_vp = thief.create_presentation(
                [stolen_cid], challenge=challenge, domain=domain)
            ok, report = verifier.verify_presentation(
                stolen_vp, challenge, domain)
            assert not ok, "non-holder presentation was accepted"
            errors = report["presentation"]["errors"]
            assert any("not holder" in e for e in errors), errors
            return ("VP signed with a non-holder key over a stolen "
                    "credential → rejected")
        self._run_check(spec, "Verifiable Presentations",
                        "NEGATIVE: presentation by a non-holder (stolen "
                        "credential) MUST be rejected", check_stolen_credential_rejected)

        def check_challenge_required():
            try:
                wallet.create_presentation([cid], challenge="", domain=domain)
            except ValueError:
                return "wallet refuses to create a VP without a challenge"
            raise AssertionError("VP created without a challenge")
        self._run_check(spec, "Verifiable Presentations",
                        "NEGATIVE: wallet MUST refuse presentation creation "
                        "without a challenge", check_challenge_required)

        print()

    # ------------------------------------------------------------------
    # Selective disclosure — executed
    # ------------------------------------------------------------------

    def _check_selective_disclosure(self):
        print("📋 W3C VC Data Model v2.0 — executing selective disclosure")
        print("-" * 80)

        spec = "VC Data Model v2.0"
        issuer, wallet, verifier = self._vc_fixtures()
        envelope = issuer.issue_credential(
            "MaintenanceRecord", wallet.holder_did,
            claims={
                "vin": VIN, "serviceCenterDid": issuer.issuer_did,
                "serviceDate": "2026-06-01", "serviceType": "brakes",
                "odometerKm": 42150, "cost": 890.5,
                "technicianId": "TECH-0231",
            },
            selective_disclosure=True)
        cid = wallet.store_credential(envelope)

        def check_digests_only():
            signed_vc = envelope["verifiableCredential"]
            subject = signed_vc["credentialSubject"]
            assert "claimDigests" in subject, "no claimDigests in SD credential"
            raw = json.dumps(subject)
            for secret in ("890.5", "TECH-0231"):
                assert secret not in raw, \
                    f"raw claim value '{secret}' leaked into the signed VC"
            return (f"signed VC carries {len(subject['claimDigests'])} salted "
                    f"digests; raw values stay with the holder")
        self._run_check(spec, "Selective Disclosure",
                        "SD credential MUST carry salted claim digests, not "
                        "raw claim values", check_digests_only)

        def check_partial_disclosure():
            vp = wallet.create_presentation(
                [cid], challenge="n1", domain="d1",
                disclose_claims={cid: ["vin", "odometerKm"]})
            ok, report = verifier.verify_presentation(vp, "n1", "d1")
            assert ok, f"partial disclosure rejected: {report}"
            presented = vp["verifiableCredential"][0]
            assert set(presented["disclosedClaims"]) == {"vin", "odometerKm"}
            # Hidden claim VALUES must not travel (names appear only as
            # digest keys); raw values stay in the wallet.
            raw = json.dumps(presented)
            for secret in ("890.5", "TECH-0231"):
                assert secret not in raw, \
                    f"hidden claim value '{secret}' leaked in the presentation"
            assert "cost" not in presented["disclosedClaims"]
            assert "cost" not in presented["credentialSubject"], \
                "undisclosed raw claim present in credentialSubject"
            return ("disclosed {vin, odometerKm} verified against signed "
                    "digests; cost/technicianId values never leave the wallet")
        self._run_check(spec, "Selective Disclosure",
                        "Partial disclosure MUST verify while hidden claims "
                        "remain hidden", check_partial_disclosure)

        def check_tampered_disclosure_rejected():
            vp = wallet.create_presentation(
                [cid], challenge="n2", domain="d1",
                disclose_claims={cid: ["odometerKm"]})
            vp["verifiableCredential"][0]["disclosedClaims"]["odometerKm"][
                "value"] = 9000  # odometer fraud
            ok, report = verifier.verify_presentation(vp, "n2", "d1")
            assert not ok, "tampered disclosed value was accepted"
            errors = report["credentials"][0]["errors"]
            assert any("digest mismatch" in e for e in errors), errors
            return "odometer 42150→9000 after signing → digest mismatch → rejected"
        self._run_check(spec, "Selective Disclosure",
                        "NEGATIVE: tampering with a disclosed value MUST "
                        "break the digest check", check_tampered_disclosure_rejected)

        print()

    # ------------------------------------------------------------------
    # Documented deviations — executed and honestly counted as FAIL
    # ------------------------------------------------------------------

    def _check_securing_mechanism_deviations(self):
        print("📋 Securing mechanisms — documented deviations (executed, "
              "counted as FAIL)")
        print("-" * 80)

        spec = "VC Data Model v2.0"

        def check_canonicalization():
            # Prove which canonicalization the stack really uses.
            out = canonicalize({"b": 1, "a": {"y": 2, "x": 1}})
            assert out == b'{"a":{"x":1,"y":2},"b":1}', \
                f"unexpected canonical form: {out!r}"
            return ("FAIL",
                    "DOCUMENTED DEVIATION: proofs are computed over "
                    "deterministic (sorted-key) JSON, not URDNA2015/RDFC-1.0 "
                    "RDF dataset canonicalization required by registered "
                    "Data Integrity cryptosuites")
        self._run_check(spec, "Securing Mechanisms",
                        "Data Integrity proofs SHOULD use a standard "
                        "canonicalization (RDFC-1.0)", check_canonicalization)

        def check_cryptosuite_registered():
            issuer = CredentialIssuer.with_ethr_did()
            vc = issuer.issue_credential(
                "VehicleBirthCertificate", "did:mobi:" + VIN,
                claims=self._birth_claims(issuer))["verifiableCredential"]
            suite = vc["proof"]["cryptosuite"]
            if suite in W3C_REGISTERED_CRYPTOSUITES:
                return f"cryptosuite '{suite}' is W3C-registered"
            return ("FAIL",
                    f"DOCUMENTED DEVIATION: cryptosuite '{suite}' is "
                    f"thesis-defined (EIP-191 + secp256k1 recovery), not in "
                    f"the W3C Data Integrity cryptosuite registry "
                    f"{sorted(W3C_REGISTERED_CRYPTOSUITES)}")
        self._run_check(spec, "Securing Mechanisms",
                        "Proof cryptosuite SHOULD be a W3C-registered Data "
                        "Integrity cryptosuite", check_cryptosuite_registered)

        print()

    # ------------------------------------------------------------------
    # SSI principles — qualitative, excluded from the executable score
    # ------------------------------------------------------------------

    def _check_ssi_principles(self):
        print("📋 SSI Principles — assessed qualitatively "
              "(NOT counted in the executable score)")
        print("-" * 80)

        principles = [
            ("1", "User Control: holder controls keys and credentials",
             "holder wallet holds its own secp256k1 key; presentations are "
             "holder-signed"),
            ("2", "Consent: data sharing requires an explicit holder action",
             "credentials leave the wallet only via create_presentation()"),
            ("3", "Portability: identity is expressed in standard formats",
             "W3C DIDs and VC DM 2.0 JSON documents"),
            ("4", "Interoperability: follows open W3C specifications",
             "subject to the deviations counted as FAIL above"),
            ("5", "Privacy by design: minimal data exposure",
             "selective disclosure via salted digests, demonstrated above"),
            ("6", "Decentralization: no mandatory central verifier",
             "offline verification via signature recovery; no chain round-trip"),
            ("7", "Transparency: open standards and auditable design",
             "spec-referenced checks in this file exercise the public API"),
            ("8", "Minimal disclosure: share only what is required",
             "hidden claims travel as digests only, demonstrated above"),
            ("9", "Security: cryptographic protection",
             "secp256k1 signatures; forgery/tamper/replay rejections "
             "demonstrated above"),
            ("10", "Persistence: identifiers are long-lived",
             "DIDs derived from keys / VIN / on-chain identity"),
        ]
        for section, requirement, notes in principles:
            self._record("SSI Principles", section, requirement,
                         "QUALITATIVE",
                         f"assessed qualitatively — {notes}")

        print()

    # ------------------------------------------------------------------
    # Scoring / reporting
    # ------------------------------------------------------------------

    @property
    def executed_total(self) -> int:
        """Executable checks only — qualitative items are excluded."""
        return self.pass_count + self.fail_count + self.partial_count

    def get_overall_compliance(self) -> float:
        """Score over EXECUTED checks: PASS + 0.5*PARTIAL over executed."""
        if self.executed_total == 0:
            return 0.0
        return ((self.pass_count + 0.5 * self.partial_count)
                / self.executed_total * 100)

    def _spec_score(self, spec: str) -> Tuple[float, int, int]:
        subset = [c for c in self.checks
                  if c.spec == spec and c.status != "QUALITATIVE"]
        if not subset:
            return 0.0, 0, 0
        passed = sum(1 for c in subset if c.status == "PASS")
        partial = sum(1 for c in subset if c.status == "PARTIAL")
        return (passed + 0.5 * partial) / len(subset) * 100, passed, len(subset)

    def print_summary(self):
        """Print the compliance summary (public API used by run_all_demos)."""
        executed = self.executed_total
        score = self.get_overall_compliance()

        print("=" * 80)
        print(" COMPLIANCE SUMMARY (executed checks only)")
        print("=" * 80)
        print()
        print(f"Executed checks:  {executed}")
        print(f"✅ PASS:          {self.pass_count} "
              f"({self.pass_count / executed * 100:.1f}%)")
        print(f"❌ FAIL:          {self.fail_count} "
              f"({self.fail_count / executed * 100:.1f}%)")
        print(f"⚠️  PARTIAL:       {self.partial_count} "
              f"({self.partial_count / executed * 100:.1f}%)")
        print(f"📝 QUALITATIVE:   {self.qualitative_count} "
              f"(SSI principles — excluded from score)")
        print()
        print(f"📊 EXECUTABLE COMPLIANCE SCORE: {score:.1f}%")
        print(f"   (PASS + 0.5×PARTIAL over {executed} executed checks; "
              f"qualitative items not counted)")
        print()

        print("Breakdown by specification (executed checks):")
        for spec in ("DID Core v1.0", "VC Data Model v2.0"):
            s, passed, total = self._spec_score(spec)
            print(f"  {spec:<24} {s:5.1f}%  ({passed}/{total} pass)")
        print(f"  {'SSI Principles':<24} assessed qualitatively "
              f"({self.qualitative_count} items, not scored)")
        print()

        failed = [c for c in self.checks if c.status == "FAIL"]
        if failed:
            print(f"❌ FAILED CHECKS ({len(failed)}):")
            for c in failed:
                print(f"  - [{c.spec} | {c.section}] {c.requirement}")
                print(f"      {c.notes}")
            print()

        partials = [c for c in self.checks if c.status == "PARTIAL"]
        if partials:
            print(f"⚠️  PARTIAL CHECKS ({len(partials)}):")
            for c in partials:
                print(f"  - [{c.spec} | {c.section}] {c.requirement}")
                print(f"      {c.notes}")
            print()

        deviations = [c for c in failed if "DOCUMENTED DEVIATION" in c.notes]
        if deviations:
            print("📌 DOCUMENTED DEVIATIONS (counted as FAIL, by design):")
            for c in deviations:
                print(f"  - {c.notes}")
            print()

        print("=" * 80)

    def export_results(self, filename: str = "w3c_compliance_report.json"):
        """Export executed results to JSON."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "methodology": (
                "All non-qualitative checks execute the DID resolver and VC "
                "stack and record observed outcomes. SSI principles are "
                "qualitative and excluded from the score."
            ),
            "summary": {
                "executed_checks": self.executed_total,
                "pass": self.pass_count,
                "fail": self.fail_count,
                "partial": self.partial_count,
                "qualitative": self.qualitative_count,
                "score": self.get_overall_compliance(),
            },
            "checks": [
                {
                    "spec": c.spec,
                    "section": c.section,
                    "requirement": c.requirement,
                    "status": c.status,
                    "notes": c.notes,
                }
                for c in self.checks
            ],
        }
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)
        print(f"📄 Compliance report exported to: {filename}")


def main() -> int:
    """Run the executable compliance checker."""
    checker = W3CComplianceChecker()
    checker.run_all_checks()
    checker.print_summary()
    checker.export_results()

    score = checker.get_overall_compliance()
    if score >= 90:
        print(f"\nResult: {score:.1f}% ≥ 90% — exit 0")
        return 0
    print(f"\nResult: {score:.1f}% < 90% — exit 1")
    return 1


if __name__ == "__main__":
    sys.exit(main())
