# VC Layer Build Plan — Exact Steps and Verification Checks

**Pass**: Priority 1, Component 1 of SECOND_PASS_PLAN.md
**Target**: W3C Verifiable Credentials Data Model v2.0 layer
**Location**: `2_w3c-ssi-layer/verifiable-credentials/`

---

## Design Decisions (fixed before coding)

| Decision | Choice | Rationale |
|---|---|---|
| Proof mechanism | ECDSA secp256k1 via EIP-191 personal-sign, expressed as W3C `DataIntegrityProof` | Ethereum-native: same keys as the 9 on-chain standards; verifiable **offline** (no chain round-trip) → supports Thrust 3 latency budget |
| Canonicalization | Deterministic JSON (sorted keys, fixed separators) over the proof-less document | Avoids full JSON-LD/URDNA2015 dependency; documented as a compliance deviation |
| Verification | Public-key **recovery** from signature → compare to address in issuer `did:ethr`/`did:key`; pluggable trusted-issuer registry for `did:mobi` | No key distribution needed; matches ERC-1056 semantics |
| Selective disclosure | SD-JWT-style salted claim digests (issuer signs digests, holder discloses claim+salt subsets) | Implementable without BBS+; verifier recomputes digests against the signed VC |
| Revocation | `credentialStatus` → registry check (in-memory / JSON-file backed) | Smart-contract anchoring deferred to MOBI VID pass |
| Expiration | `validFrom` / `validUntil` (VC DM 2.0 vocabulary) | v2.0 replaces v1.1 `issuanceDate`/`expirationDate` |

## Build Order (dependency-sorted)

| Step | File | Contents | Est. lines |
|---|---|---|---|
| 1 | `vc_schemas.py` | 10 automotive credential schemas (one per use case) + validator; no internal deps | ~250 |
| 2 | `vc_issuer.py` | `CredentialIssuer`: key mgmt, schema-validated issuance, SD digest generation, proof signing, revocation registry | ~400 |
| 3 | `vc_holder.py` | `HolderWallet`: storage, querying, Verifiable Presentation creation (challenge + domain), selective disclosure | ~300 |
| 4 | `vc_verifier.py` | `CredentialVerifier`: structure/schema/expiry/revocation/signature checks, VP verification (challenge/domain/holder binding), SD digest re-check, W3C compliance scorer | ~350 |
| 5 | `tests/test_vc_layer.py` | End-to-end pytest suite (gates below) | ~300 |

## Verification Gates (all must pass before commit)

- **G1 — Import gate**: every module imports cleanly (`python3 -c "import ..."`).
- **G2 — Schema gate**: all 10 schemas validate a correct example and reject a
  missing-required-field example.
- **G3 — Round-trip gate**: issue → verify returns `valid=True` with zero errors.
- **G4 — Tamper gate**: mutating any claim after issuance ⇒ signature check fails.
- **G5 — Impersonation gate**: VC claiming issuer DID ≠ signing key ⇒ fails.
- **G6 — Expiry gate**: `validUntil` in the past ⇒ fails with `expired`.
- **G7 — Revocation gate**: verify OK → `revoke()` → verify fails with `revoked`.
- **G8 — Presentation gate**: VP with correct challenge+domain verifies; wrong
  challenge fails; wrong domain fails; VP signed by non-holder fails.
- **G9 — Selective disclosure gate**: disclosing 2 of 6 claims verifies; a
  tampered disclosed value fails digest check; undisclosed claims absent from VP.
- **G10 — Full suite**: `pytest tests/ -v` → 0 failures.
- **G11 — Demo output**: each module's `__main__` demo runs and prints a
  human-readable result (used in QUICKSTART and committee demos).

## Exit Criteria / Output Report

After G1–G11: update `README.md` status, update `INVENTORY.md`, commit
(author: Nikhil Prakash), push with retry policy, and emit a completion
report: files, line counts, gates passed, W3C compliance notes, measured
verify latency (first Thrust 3 data point), and next actions (MOBI VID).
