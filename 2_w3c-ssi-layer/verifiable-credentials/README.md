# W3C Verifiable Credentials Implementation

This directory contains the W3C Verifiable Credentials Data Model v2.0 implementation for the thesis.

## Components

- `vc_issuer.py` - Credential issuance (manufacturers, service centers, DMV)
- `vc_holder.py` - Holder wallet for storing and presenting credentials
- `vc_verifier.py` - Credential verification and validation
- `vc_schemas.py` - Credential schemas for automotive domain
- `tests/` - Comprehensive test suite

## W3C Compliance

Target: 100% compliance with VC Data Model v2.0

Implemented features:
- ✅ VC Data Model v2.0 structure
- ✅ Linked Data Proofs
- ✅ Verifiable Presentations
- ✅ Selective Disclosure
- ✅ Status checking (revocation)
- ✅ Schema validation

## Usage

```python
from vc_issuer import CredentialIssuer
from vc_holder import HolderWallet
from vc_verifier import CredentialVerifier

# Issue credential
issuer = CredentialIssuer(issuer_did="did:ethr:0x123...")
vc = issuer.issue_credential(
    credential_type="VehicleBirthCertificate",
    subject_did="did:mobi:5YJ3E1EA0PF123456",
    claims={"make": "Tesla", "model": "Model 3"}
)

# Store in wallet
wallet = HolderWallet(holder_did="did:ethr:0x456...")
wallet.store_credential(vc)

# Create presentation
vp = wallet.create_presentation(
    credential_ids=[vc.id],
    challenge="nonce_from_verifier",
    domain="verifier.example.com"
)

# Verify
verifier = CredentialVerifier()
is_valid, result = verifier.verify_presentation(vp, challenge, domain)
```

## Thesis Integration

This implementation is used across all 10 use cases and integrates with:
- All 9 blockchain identity standards
- MOBI VID birth certificates and lifecycle events
- CV2X V2V safety messaging
- Performance comparison framework
