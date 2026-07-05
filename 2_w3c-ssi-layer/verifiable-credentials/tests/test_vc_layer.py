#!/usr/bin/env python3
"""
VC Layer Test Suite — verification gates G2–G9 from BUILD_PLAN.md
=================================================================

Run:  cd 2_w3c-ssi-layer/verifiable-credentials && python3 -m pytest tests/ -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vc_schemas import SCHEMA_REGISTRY, validate_claims, is_valid_vin
from vc_issuer import CredentialIssuer, RevocationRegistry, recover_signer
from vc_holder import HolderWallet
from vc_verifier import CredentialVerifier, TrustedIssuerRegistry

VIN = "5YJ3E1EA0PF123456"


@pytest.fixture
def issuer():
    return CredentialIssuer.with_ethr_did()


@pytest.fixture
def wallet():
    return HolderWallet.with_ethr_did()


@pytest.fixture
def verifier(issuer):
    return CredentialVerifier(revocation_registry=issuer.revocation_registry)


def birth_claims(issuer):
    return {
        "vin": VIN,
        "make": "Tesla",
        "model": "Model 3",
        "year": 2024,
        "manufacturingDate": "2024-01-15",
        "manufacturerDid": issuer.issuer_did,
    }


def issue_birth(issuer, wallet, **kwargs):
    return issuer.issue_credential(
        credential_type="VehicleBirthCertificate",
        subject_did=wallet.holder_did,
        claims=birth_claims(issuer),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# G2 — Schema gate
# ---------------------------------------------------------------------------

class TestSchemas:
    def test_all_ten_schemas_registered(self):
        assert len(SCHEMA_REGISTRY) == 10

    def test_valid_vin(self):
        assert is_valid_vin(VIN)
        assert not is_valid_vin("SHORT")
        assert not is_valid_vin("5YJ3E1EA0PF12345I")  # 'I' not in ISO 3779

    @pytest.mark.parametrize("cred_type,claims", [
        ("VehicleBirthCertificate", {
            "vin": VIN, "make": "Tesla", "model": "3", "year": 2024,
            "manufacturingDate": "2024-01-15",
            "manufacturerDid": "did:mobi:manufacturer:tesla"}),
        ("OwnershipTransfer", {
            "vin": VIN, "previousOwnerDid": "did:ethr:0x1:0x" + "a" * 40,
            "newOwnerDid": "did:ethr:0x1:0x" + "b" * 40,
            "transferDate": "2026-01-01", "transferType": "private_sale"}),
        ("MaintenanceRecord", {
            "vin": VIN, "serviceCenterDid": "did:mobi:service:jiffy",
            "serviceDate": "2026-06-01", "serviceType": "oil_change",
            "odometerKm": 12000}),
        ("V2VSafetyCredential", {
            "vehicleDid": "did:ethr:0x1:0x" + "c" * 40,
            "pseudonymId": "PSN-001",
            "authorizedApplications": ["FCW", "EEBL"],
            "region": "BC-CA", "securityLevel": 3}),
    ])
    def test_valid_claims_accepted(self, cred_type, claims):
        ok, errors = validate_claims(cred_type, claims)
        assert ok, errors

    def test_missing_required_rejected(self):
        ok, errors = validate_claims("VehicleBirthCertificate",
                                     {"vin": VIN, "make": "Tesla"})
        assert not ok
        assert any("missing required" in e for e in errors)

    def test_bad_enum_rejected(self):
        ok, errors = validate_claims("OwnershipTransfer", {
            "vin": VIN, "previousOwnerDid": "did:ethr:0x1:0x" + "a" * 40,
            "newOwnerDid": "did:ethr:0x1:0x" + "b" * 40,
            "transferDate": "2026-01-01", "transferType": "gifted_maybe"})
        assert not ok

    def test_unknown_type_rejected(self):
        ok, _ = validate_claims("NotARealCredential", {})
        assert not ok


# ---------------------------------------------------------------------------
# G3/G4/G5/G6/G7 — issuance, tamper, impersonation, expiry, revocation
# ---------------------------------------------------------------------------

class TestIssueAndVerify:
    def test_round_trip_valid(self, issuer, wallet, verifier):
        vc = issue_birth(issuer, wallet, validity_days=None)["verifiableCredential"]
        result = verifier.verify_credential(vc)
        assert result.valid, result.errors
        assert all(result.checks.values())

    def test_issuance_rejects_invalid_claims(self, issuer, wallet):
        with pytest.raises(ValueError, match="schema validation"):
            issuer.issue_credential(
                "VehicleBirthCertificate", wallet.holder_did,
                claims={"vin": "BAD", "make": "Tesla"})

    def test_recovered_signer_matches_issuer(self, issuer, wallet):
        vc = issue_birth(issuer, wallet)["verifiableCredential"]
        assert recover_signer(vc, vc["proof"]) == issuer.address

    def test_tampered_claim_fails(self, issuer, wallet, verifier):
        vc = issue_birth(issuer, wallet)["verifiableCredential"]
        vc["credentialSubject"]["make"] = "Lada"  # G4
        result = verifier.verify_credential(vc)
        assert not result.valid
        assert any("signature" in e for e in result.errors)

    def test_impersonation_fails(self, wallet, verifier):
        # G5: attacker signs with own key but claims Tesla's DID as issuer
        attacker = CredentialIssuer(
            issuer_did="did:ethr:0x1:0x" + "d" * 40  # not attacker's address
        )
        vc = attacker.issue_credential(
            "VehicleBirthCertificate", wallet.holder_did,
            claims={
                "vin": VIN, "make": "Tesla", "model": "3", "year": 2024,
                "manufacturingDate": "2024-01-15",
                "manufacturerDid": attacker.issuer_did,
            })["verifiableCredential"]
        result = verifier.verify_credential(vc)
        assert not result.valid
        assert any("does not match issuer" in e for e in result.errors)

    def test_expired_fails(self, issuer, wallet, verifier):
        # G6
        vc = issue_birth(issuer, wallet, validity_days=365)["verifiableCredential"]
        vc_expired = dict(vc)
        vc_expired["validUntil"] = "2020-01-01T00:00:00Z"
        # signature now broken too, but temporal check must fire on its own
        result = verifier.verify_credential(vc_expired)
        assert not result.valid
        assert any("expired" in e for e in result.errors)

    def test_revocation(self, issuer, wallet, verifier):
        # G7
        vc = issue_birth(issuer, wallet)["verifiableCredential"]
        assert verifier.verify_credential(vc).valid
        issuer.revoke_credential(vc["id"], reason="stolen key")
        result = verifier.verify_credential(vc)
        assert not result.valid
        assert any("revoked" in e for e in result.errors)

    def test_revocation_persists_to_file(self, tmp_path):
        path = str(tmp_path / "revocations.json")
        reg = RevocationRegistry(path=path)
        reg.revoke("urn:uuid:test-1", "test")
        reloaded = RevocationRegistry(path=path)
        assert reloaded.is_revoked("urn:uuid:test-1")

    def test_trusted_registry_for_mobi_dids(self, wallet):
        # did:mobi has no embedded address → verifier needs the registry
        mobi_issuer = CredentialIssuer(issuer_did="did:mobi:manufacturer:tesla")
        vc = mobi_issuer.issue_credential(
            "VehicleBirthCertificate", wallet.holder_did,
            claims={
                "vin": VIN, "make": "Tesla", "model": "3", "year": 2024,
                "manufacturingDate": "2024-01-15",
                "manufacturerDid": mobi_issuer.issuer_did,
            })["verifiableCredential"]

        bare = CredentialVerifier(
            revocation_registry=mobi_issuer.revocation_registry)
        assert not bare.verify_credential(vc).valid  # unknown issuer

        trusted = TrustedIssuerRegistry()
        trusted.register(mobi_issuer.issuer_did, mobi_issuer.address)
        knowing = CredentialVerifier(
            revocation_registry=mobi_issuer.revocation_registry,
            trusted_issuers=trusted)
        assert knowing.verify_credential(vc).valid


# ---------------------------------------------------------------------------
# G8 — Presentation gate
# ---------------------------------------------------------------------------

class TestPresentations:
    CHALLENGE = "nonce-8f3a"
    DOMAIN = "dmv.gov.bc.ca"

    def _vp(self, issuer, wallet, **vp_kwargs):
        cid = wallet.store_credential(issue_birth(issuer, wallet))
        return wallet.create_presentation(
            [cid], challenge=self.CHALLENGE, domain=self.DOMAIN, **vp_kwargs)

    def test_valid_presentation(self, issuer, wallet, verifier):
        vp = self._vp(issuer, wallet)
        ok, report = verifier.verify_presentation(vp, self.CHALLENGE, self.DOMAIN)
        assert ok, report

    def test_wrong_challenge_fails(self, issuer, wallet, verifier):
        vp = self._vp(issuer, wallet)
        ok, report = verifier.verify_presentation(vp, "other", self.DOMAIN)
        assert not ok
        assert any("challenge" in e
                   for e in report["presentation"]["errors"])

    def test_wrong_domain_fails(self, issuer, wallet, verifier):
        vp = self._vp(issuer, wallet)
        ok, report = verifier.verify_presentation(vp, self.CHALLENGE, "evil.example")
        assert not ok

    def test_non_holder_cannot_present(self, issuer, wallet, verifier):
        # Thief copies the credential into their own wallet and presents it
        envelope = issue_birth(issuer, wallet)
        thief = HolderWallet(holder_did=wallet.holder_did)  # same DID, wrong key
        cid = thief.store_credential(envelope)
        vp = thief.create_presentation([cid], challenge=self.CHALLENGE,
                                       domain=self.DOMAIN)
        ok, report = verifier.verify_presentation(vp, self.CHALLENGE, self.DOMAIN)
        assert not ok
        assert any("not holder" in e
                   for e in report["presentation"]["errors"])

    def test_missing_challenge_rejected_at_creation(self, issuer, wallet):
        cid = wallet.store_credential(issue_birth(issuer, wallet))
        with pytest.raises(ValueError):
            wallet.create_presentation([cid], challenge="", domain=self.DOMAIN)


# ---------------------------------------------------------------------------
# G9 — Selective disclosure gate
# ---------------------------------------------------------------------------

class TestSelectiveDisclosure:
    def _sd_setup(self, issuer, wallet):
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
        return cid

    def test_partial_disclosure_verifies(self, issuer, wallet, verifier):
        cid = self._sd_setup(issuer, wallet)
        vp = wallet.create_presentation(
            [cid], challenge="n1", domain="d1",
            disclose_claims={cid: ["vin", "odometerKm"]})
        ok, report = verifier.verify_presentation(vp, "n1", "d1")
        assert ok, report

        presented = vp["verifiableCredential"][0]
        assert set(presented["disclosedClaims"]) == {"vin", "odometerKm"}
        # hidden claims never leave the wallet as raw values
        assert "cost" not in str(presented.get("disclosedClaims"))
        assert "credentialSubject" in presented
        assert "cost" not in presented["credentialSubject"]

    def test_tampered_disclosed_value_fails(self, issuer, wallet, verifier):
        cid = self._sd_setup(issuer, wallet)
        vp = wallet.create_presentation(
            [cid], challenge="n1", domain="d1",
            disclose_claims={cid: ["odometerKm"]})
        # odometer fraud: change disclosed value after presentation creation
        vp["verifiableCredential"][0]["disclosedClaims"]["odometerKm"]["value"] = 9000
        ok, report = verifier.verify_presentation(vp, "n1", "d1")
        assert not ok
        cred_errors = report["credentials"][0]["errors"]
        assert any("digest mismatch" in e for e in cred_errors)

    def test_cannot_disclose_unknown_claim(self, issuer, wallet):
        cid = self._sd_setup(issuer, wallet)
        with pytest.raises(KeyError):
            wallet.create_presentation(
                [cid], challenge="n1", domain="d1",
                disclose_claims={cid: ["secretField"]})

    def test_sd_credential_alone_verifies(self, issuer, wallet, verifier):
        cid = self._sd_setup(issuer, wallet)
        result = verifier.verify_credential(wallet.get_credential(cid))
        assert result.valid, result.errors


# ---------------------------------------------------------------------------
# Thrust 3 smoke check: offline verification latency
# ---------------------------------------------------------------------------

class TestLatency:
    def test_verification_under_10ms(self, issuer, wallet, verifier):
        vc = issue_birth(issuer, wallet)["verifiableCredential"]
        verifier.verify_credential(vc)  # warm-up
        timings = [verifier.verify_credential(vc).elapsed_ms
                   for _ in range(20)]
        timings.sort()
        median = timings[len(timings) // 2]
        assert median < 10.0, f"median verify latency {median:.2f} ms ≥ 10 ms"
