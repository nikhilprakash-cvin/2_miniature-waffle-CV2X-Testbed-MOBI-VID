#!/usr/bin/env python3
"""
W3C Verifiable Credential Holder Wallet — VC Data Model v2.0
============================================================

Holder-side wallet: stores issued credentials (and their selective-
disclosure maps), answers queries, and creates signed Verifiable
Presentations bound to a verifier's challenge and domain (replay
protection).

For selective disclosure, the wallet keeps the issuer-provided
{claim: {value, salt}} map alongside the digest-only credential and, at
presentation time, attaches only the chosen claim+salt pairs. The verifier
recomputes each digest against the issuer-signed `claimDigests`.

Author: Nikhil Prakash
Thesis: MASc, UBC ECE
"""

import json
import uuid
from typing import Any, Dict, List, Optional

from eth_account import Account

from vc_schemas import VC_CONTEXT_V2, CVIN_CONTEXT
from vc_issuer import (
    PROOF_TYPE, CRYPTOSUITE, utc_now_iso, sign_document,
)


class HolderWallet:
    """
    Credential wallet bound to a holder DID and secp256k1 key.

    The holder key signs Verifiable Presentations (proofPurpose:
    "authentication"), proving that the presenter controls the holder DID
    — this is what stops a stolen credential from being replayed by a
    third party.
    """

    def __init__(self, holder_did: str, private_key: Optional[str] = None):
        if not holder_did.startswith("did:"):
            raise ValueError(f"holder_did must be a DID, got: {holder_did}")
        self.holder_did = holder_did
        self._account = (
            Account.from_key(private_key) if private_key else Account.create()
        )
        # credential id -> {"verifiableCredential": ..., "disclosures": ...}
        self._store: Dict[str, Dict[str, Any]] = {}

    @property
    def address(self) -> str:
        return self._account.address

    @classmethod
    def with_ethr_did(cls, private_key: Optional[str] = None,
                      chain_id: str = "0x1") -> "HolderWallet":
        """Create a wallet whose did:ethr DID is derived from its own key."""
        account = Account.from_key(private_key) if private_key else Account.create()
        did = f"did:ethr:{chain_id}:{account.address}"
        return cls(holder_did=did, private_key=account.key.hex())

    # ------------------------------------------------------------------
    # Storage & queries
    # ------------------------------------------------------------------

    def store_credential(self, envelope: Dict[str, Any]) -> str:
        """
        Store an issuance envelope ({"verifiableCredential":…,
        "disclosures":…}) or a bare VC dict. Returns the credential id.
        """
        if "verifiableCredential" in envelope:
            vc = envelope["verifiableCredential"]
            disclosures = envelope.get("disclosures")
        else:
            vc, disclosures = envelope, None

        credential_id = vc.get("id")
        if not credential_id:
            raise ValueError("credential has no 'id'")
        self._store[credential_id] = {
            "verifiableCredential": vc,
            "disclosures": disclosures,
        }
        return credential_id

    def get_credential(self, credential_id: str) -> Optional[Dict[str, Any]]:
        entry = self._store.get(credential_id)
        return entry["verifiableCredential"] if entry else None

    def list_credentials(self,
                         credential_type: Optional[str] = None
                         ) -> List[Dict[str, Any]]:
        """List stored credentials, optionally filtered by type."""
        result = []
        for entry in self._store.values():
            vc = entry["verifiableCredential"]
            if credential_type is None or credential_type in vc.get("type", []):
                result.append(vc)
        return result

    def delete_credential(self, credential_id: str) -> bool:
        return self._store.pop(credential_id, None) is not None

    # ------------------------------------------------------------------
    # Presentations
    # ------------------------------------------------------------------

    def create_presentation(
        self,
        credential_ids: List[str],
        challenge: str,
        domain: str,
        disclose_claims: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a signed Verifiable Presentation.

        Args:
            credential_ids: ids of stored credentials to present.
            challenge: verifier-supplied nonce (replay protection).
            domain: verifier-supplied audience string.
            disclose_claims: for selective-disclosure credentials, a map
                {credential_id: [claim names to disclose]}. Undisclosed
                claims remain hidden (only their digests travel).

        Returns:
            Signed VP dict with proofPurpose "authentication" binding the
            challenge and domain.
        """
        if not challenge or not domain:
            raise ValueError("challenge and domain are required")

        credentials: List[Dict[str, Any]] = []
        for cid in credential_ids:
            entry = self._store.get(cid)
            if entry is None:
                raise KeyError(f"credential not in wallet: {cid}")
            vc = entry["verifiableCredential"]
            disclosures = entry["disclosures"]

            requested = (disclose_claims or {}).get(cid)
            if requested is not None:
                if disclosures is None:
                    raise ValueError(
                        f"{cid} was not issued with selective disclosure"
                    )
                unknown = [c for c in requested if c not in disclosures]
                if unknown:
                    raise KeyError(f"claims not in disclosure map: {unknown}")
                # Attach only the chosen claim+salt pairs (unsigned region;
                # verifier re-derives digests against the signed VC).
                vc = dict(vc)  # shallow copy; signed content untouched
                vc["disclosedClaims"] = {
                    name: disclosures[name] for name in requested
                }
            credentials.append(vc)

        presentation: Dict[str, Any] = {
            "@context": [VC_CONTEXT_V2, CVIN_CONTEXT],
            "id": f"urn:uuid:{uuid.uuid4()}",
            "type": ["VerifiablePresentation"],
            "holder": self.holder_did,
            "verifiableCredential": credentials,
        }

        proof: Dict[str, Any] = {
            "type": PROOF_TYPE,
            "cryptosuite": CRYPTOSUITE,
            "created": utc_now_iso(),
            "verificationMethod": f"{self.holder_did}#controller",
            "proofPurpose": "authentication",
            "challenge": challenge,
            "domain": domain,
        }
        # disclosedClaims are excluded from the VP signature payload domain
        # of each inner VC (they were never part of the issuer-signed VC);
        # the VP proof covers the presentation as assembled, so tampering
        # with disclosed values still breaks digest checks at verify time.
        proof["proofValue"] = sign_document(
            presentation, proof, self._account.key
        )
        presentation["proof"] = proof
        return presentation


if __name__ == "__main__":
    from vc_issuer import CredentialIssuer

    print("=== Holder Wallet Demo: selective disclosure ===\n")

    issuer = CredentialIssuer.with_ethr_did()
    wallet = HolderWallet.with_ethr_did()
    print(f"Issuer: {issuer.issuer_did}")
    print(f"Holder: {wallet.holder_did}\n")

    envelope = issuer.issue_credential(
        credential_type="MaintenanceRecord",
        subject_did=wallet.holder_did,
        claims={
            "vin": "5YJ3E1EA0PF123456",
            "serviceCenterDid": issuer.issuer_did,
            "serviceDate": "2026-06-01",
            "serviceType": "brake_replacement",
            "odometerKm": 42150,
            "cost": 890.50,
            "technicianId": "TECH-0231",
        },
        selective_disclosure=True,
    )
    cid = wallet.store_credential(envelope)
    print(f"Stored credential: {cid}")
    print(f"Wallet holds {len(wallet.list_credentials())} credential(s)\n")

    vp = wallet.create_presentation(
        credential_ids=[cid],
        challenge="nonce-1234",
        domain="insurer.example.com",
        # Disclose service facts, hide cost and technician
        disclose_claims={cid: ["vin", "serviceDate", "serviceType",
                               "odometerKm"]},
    )
    disclosed = vp["verifiableCredential"][0]["disclosedClaims"]
    print("Disclosed claims:", sorted(disclosed.keys()))
    print("Hidden claims stay as digests only:",
          sorted(set(vp["verifiableCredential"][0]["credentialSubject"]
                     ["claimDigests"]) - set(disclosed)))
    print("\nPresentation proof purpose:", vp["proof"]["proofPurpose"])
    print("Challenge bound:", vp["proof"]["challenge"])
