# Internal Report: Research Thrusts, Repository State, and Critical Path

**Classification**: Internal working document (thesis planning)
**Author**: Nikhil Prakash (MASc, UBC ECE)
**Date**: July 5, 2026
**Repository**: 2_miniature-waffle-CV2X-Testbed-MOBI-VID
**Branch**: `claude/cv2x-testbed-setup-011CUz5ay5VfEAsZzv5cexDy`

---

## 1. Executive Summary

This thesis is a **systematic empirical comparison of nine blockchain identity
standards** (ERC-721, ERC-725, ERC-735, ERC-725xy, ERC-1056, ERC-1155, LSP8,
ERC-4337, CVIN-Combined) evaluated as substrates for **Self-Sovereign Identity
(SSI) in Connected and Autonomous Vehicles (CAVs)**. It is organized around
five research thrusts, each with a falsifiable hypothesis and a defined data
collection method.

**Current state**: infrastructure is complete (smart contracts, DID
resolution, CI/CD, documentation), but the **application layer is missing**.
The single blocking component is the **W3C Verifiable Credentials (VC)
layer** — without it, none of the 10 lifecycle use cases can execute, no
experimental data for Thrusts 2–4 can be collected, and thesis Chapter 5
(Results) cannot begin.

**Decision taken**: build the VC layer now (Priority 1), followed by MOBI VID,
then the use-case suite and comparison framework.

Overall thesis completion estimate: **~40%**. Target after VC + MOBI VID:
**~55–60%**.

---

## 2. Research Thrusts (Detailed)

### Thrust 1 — Comparative Performance Under Automotive Constraints

- **RQ**: How do the nine standards compare on gas cost, latency, storage
  overhead, and throughput when executing identical vehicle-identity
  operations?
- **Hypothesis (H1)**: Minimal-state standards (ERC-1056) outperform
  rich-state standards (ERC-725/735) by ≥10× on gas for DID creation and
  update, at the cost of reduced on-chain expressiveness.
- **Method**: Identical operation set (create DID, update key, add delegate,
  anchor credential, revoke) executed on all 9 standards under Hardhat;
  gas via `hardhat-gas-reporter`; nightly CI benchmark (`benchmark.yml`)
  provides longitudinal data.
- **Status**: Contracts done ✅; automated collection wired ✅; analyzer
  scripts (`gas_analyzer.py`, `latency_analyzer.py`) not yet built ⏳.

### Thrust 2 — W3C Compliance Feasibility from Blockchain Primitives

- **RQ**: Can each blockchain standard be lifted to full W3C DID Core v1.0 +
  VC Data Model v2.0 compliance, and where are the structural mismatches?
- **Hypothesis (H2)**: ≥90% aggregate compliance is achievable for all 9
  standards via a resolution/translation layer, but specific properties
  (e.g., `service` endpoints, key rotation history) require off-chain
  augmentation for minimal standards.
- **Method**: DID resolver (built, 4 methods) + VC issuer/verifier (this
  pass) scored against a compliance checklist enforced in CI
  (`w3c-compliance.yml`, >90% gate).
- **Status**: DID side ~75% ✅; **VC side 0% — this is the blocker** 🔴.

### Thrust 3 — Real-Time Viability for Safety-Critical V2V

- **RQ**: Can identity establishment + credential verification fit inside the
  latency envelope of V2V safety applications (FCW/EEBL/IMA, ~100 ms
  end-to-end budget)?
- **Hypothesis (H3)**: Off-chain verification of pre-issued credentials
  (signature check only, no chain round-trip) meets the budget
  (<10 ms verify); any design requiring on-chain reads at message time
  does not.
- **Method**: SUMO simulation (50 vehicles) with credential checks in the
  message path; measure the full pipeline: receive → resolve (cached) →
  verify VC → trust decision.
- **Status**: DID resolution at ~0.8 ms ✅; VC verify timing unmeasured
  (needs VC layer) 🔴; SUMO harness not built ⏳.

### Thrust 4 — Industry Alignment via MOBI VID

- **RQ**: Can MOBI VID I (birth certificate) and VID II (11 lifecycle event
  types) be realized on all nine standards, and which backend fits best?
- **Hypothesis (H4)**: MOBI VID's event model maps most economically onto
  event-log standards (ERC-1056) and most faithfully onto claim-based
  standards (ERC-735); the CVIN-Combined hybrid dominates on the
  fidelity-per-gas frontier.
- **Method**: MOBI VID reference implementation (VC-based birth certificates
  and lifecycle events) parameterized over blockchain backend; per-backend
  cost/fidelity scoring.
- **Status**: Specification documented ✅; implementation 0% — **depends on
  the VC layer** 🔴.

### Thrust 5 — Security Architecture Trade-off Analysis

- **RQ**: Which architecture best resists the V2X threat model (Sybil,
  impersonation, replay, credential forgery, privacy leakage)?
- **Hypothesis (H5)**: No single standard dominates; standards occupy a
  security/performance Pareto frontier, and a hybrid
  (ERC-1056 identity + ERC-735 claims) sits on it.
- **Method**: Structured attack scenarios executed against each
  implementation; on-chain data leakage audit; recovery-mechanism analysis
  (key loss, transfer semantics).
- **Status**: Threat model documented ✅; scenario execution ⏳ (several
  scenarios — forged credentials, replayed presentations — require the VC
  layer's challenge/domain machinery) 🟡.

---

## 3. Dependency Analysis: Why the VC Layer Is the Critical Path

```
                      ┌────────────────────────┐
                      │  9 Smart Contracts ✅  │
                      └──────────┬─────────────┘
                                 │
                      ┌──────────▼─────────────┐
                      │  DID Resolver (75%) ✅ │
                      └──────────┬─────────────┘
                                 │
                 ┌───────────────▼────────────────┐
                 │   VC LAYER (0%)  ← THIS PASS   │ 🔴
                 └───┬───────────┬───────────┬────┘
                     │           │           │
        ┌────────────▼──┐ ┌──────▼──────┐ ┌──▼──────────────┐
        │ MOBI VID (0%) │ │ 10 Use Cases│ │ V2V Latency     │
        │ Thrust 4      │ │ (0%)        │ │ Experiments (0%)│
        └───────────────┘ │ Thrusts 2–5 │ │ Thrust 3        │
                          └──────┬──────┘ └─────────────────┘
                                 │
                      ┌──────────▼─────────────┐
                      │ Comparison Framework   │
                      │ → Thesis Ch. 5 Results │
                      └────────────────────────┘
```

Four of five thrusts have experiments gated on VC issuance/verification.
Thrust 1 (gas) is the only one that can proceed independently, and its
credential-anchoring measurements are also VC-gated.

---

## 4. Asset Inventory (Condensed)

| Layer | Location | State | Evidence |
|---|---|---|---|
| Smart contracts (9 standards) | `1_blockchain-identity/` | ✅ 100% | 18+ passing tests, deploy scripts |
| DID resolver (4 methods) | `2_w3c-ssi-layer/did-resolution/` | ✅ ~75% W3C DID Core | 680 lines, CLI, <1 ms resolution |
| VC layer | `2_w3c-ssi-layer/verifiable-credentials/` | 🔴 0% (README only) | — |
| MOBI VID | `2_w3c-ssi-layer/mobi-vid/` | 🔴 spec only | 200-line spec doc |
| CV2X testbed / use cases | `3_cv2x-testbed/` | ⏳ ~5% | scaffolding |
| Comparison framework | `4_comparison-framework/` | ⏳ ~10% | scaffolding |
| CI/CD | `.github/workflows/` | ✅ 90% | 3 workflows (test / benchmark / compliance) |
| Documentation | root + `docs/` | ✅ | README, INVENTORY, CAPABILITIES, QUICKSTART, SECOND_PASS_PLAN |

Environment verified this session: Python 3.11.15; `web3 7.16.0`,
`eth-account 0.13.7`, `cryptography`, `pytest 9.1.1` installed and importable.

---

## 5. Risks and Mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | VC layer scope creep (full JSON-LD processing, BBS+ signatures) | Weeks of delay | Scope to Data Integrity proofs over canonical JSON + SD-JWT-style salted-hash selective disclosure; document deviations honestly in the compliance matrix |
| R2 | Latency claims challenged at defense | Thrust 3 validity | All timings collected by scripted, CI-reproducible benchmarks; report medians + p95 |
| R3 | "Mock vs. real chain" criticism | External validity | Hardhat-local for controlled comparison + one public-testnet (Sepolia) validation run per standard |
| R4 | W3C compliance self-scored | Rigor | Checklist derived clause-by-clause from VC DM 2.0; CI-enforced; test vectors committed |
| R5 | Attribution/reproducibility questions | Committee trust | All commits under author identity; daily benchmark artifacts version-controlled |

---

## 6. Decision Log (This Session)

1. **Commit attribution stays with the author** (nikhil.prakash1995@gmail.com)
   for academic integrity; hook warning acknowledged and suppressed.
2. **VC proof mechanism**: Ethereum-native ECDSA secp256k1 (EIP-191 signing)
   expressed as a W3C Data Integrity proof — consistent with `did:ethr` and
   verifiable without chain access (supports H3).
3. **Selective disclosure**: SD-JWT-style salted claim digests (issuer signs
   digests; holder discloses chosen claim+salt pairs) rather than BBS+ —
   implementable now, academically defensible, limitation documented.
4. **Revocation**: registry-based status checking (`credentialStatus`),
   file/in-memory backed now, smart-contract anchored in the MOBI VID pass.

---

## 7. Immediate Plan

Execute the VC layer build per `2_w3c-ssi-layer/verifiable-credentials/BUILD_PLAN.md`
(committed alongside this report): 4 modules + test suite + verification
gates, then commit/push and report results.

**Success gate for this pass**: end-to-end
issue → store → present (with challenge/domain) → verify → revoke → re-verify-fails
flow passing in pytest, plus selective disclosure round-trip.
