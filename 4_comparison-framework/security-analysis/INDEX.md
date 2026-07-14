# Thrust 5 Security Analysis — Two Complementary Lenses

This directory contains **two executable security suites** that were
developed against the same 9-standard threat model and are kept together
because they answer different questions. Read this first.

## Lens 1 — Authorization/Replay Test Suite (pass/fail)

- **Where**: `1_blockchain-identity/test/security/securityScenarios.test.js`
  (+ `attackHarness.js`), 54 Mocha tests.
- **Run**: `cd 1_blockchain-identity && npx hardhat test` (part of the
  201-test suite; CI-gated).
- **What it proves**: for every standard, unauthorized issuance,
  unauthorized attribute/claim writes, unauthorized revocation, identity
  hijack, and signature replay all **revert** — with a differential
  control asserting the *authorized* operation succeeds. **43/43
  applicable cells DEFENDED.** A regression flips a cell to VULNERABLE and
  fails CI, so the guarantee is continuously enforced, never asserted in
  prose.
- **Output**: `results/attack_results.{json,csv,tex}` via
  `generate_attack_tables.py`.

## Lens 2 — Threat-Matrix Analysis (defended / partial / vulnerable)

- **Where**: `attack_scenarios.py` (+ on-chain `scripts/security_scenarios.js`).
- **Run**: `cd 4_comparison-framework/security-analysis && python3 attack_scenarios.py`.
- **What it adds**: the dimensions a pass/fail test cannot express —
  **Sybil economics** (identity-creation cost as the attack-cost proxy),
  **recovery availability** (is there any key-recovery path at all?), and
  **on-chain PII leakage** (is the VIN readable in plaintext?). Cells are
  graded defended / partial / vulnerable, with `*` marking findings
  reasoned from verified source rather than executed.
- **Output**: `results/security_matrix.json`,
  `results/security_comparison.tex`, `results/onchain_security.json`.

## Why both

Lens 1 gives a **binary, CI-enforced guarantee** on the attacks that are
naturally expressible as "must revert." Lens 2 gives the **comparative
security profile** across the softer dimensions (Sybil, recovery, privacy)
that the thesis needs for RQ2/H5 but that cannot be reduced to a passing
test. The consolidated result matrix in the thesis (Chapter 5 §5.6) is
built from Lens 2, with Lens 1 providing the executable proof behind its
"impersonation / replay / identity-theft" columns.

Both were produced in the same integration pass; the file names are
namespaced (`attack_results.*` vs `security_matrix.*`) so they coexist
without collision.
