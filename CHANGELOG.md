# Changelog

All notable changes to the CVIN SSI/DID thesis implementation are recorded
here. Versions track thesis-completion milestones rather than a shipped
product. Dates are the working-session dates.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/).

---

## [0.7.0] — 2026-07-14 — "Integration & Verification Milestone"

The milestone that turned a collection of demo-grade prototypes into a
verified, reproducible research platform. An external-style audit of the
merged parallel-session work found that much of it was demo theater
(mocked verification, hardcoded results, contracts that never ran); this
release fixes all of it and adds the missing empirical layers. Every
number in the thesis is now traceable to a committed artifact or a
reproducible command.

### Thesis status
- Overall completion: **~40% → ~70%**
- Automated tests green: **201 Hardhat + 28 VC + 21 MOBI VID + 12 use cases**
- W3C compliance: **93.2% measured** (executable, ≥90% CI-gated)
- All five research thrusts now backed by measured data.

### Added
- **All 9 identity standards implemented and tested.** Added the five
  that were missing: ERC-735 (claim holder), ERC-1155 (multi-token
  credentials, soulbound), LSP8 (identifiable digital asset), ERC-4337
  (account abstraction + minimal EntryPoint + guardian recovery), and
  **CVIN-Combined** (the thesis's own ERC-1056+735 hybrid). 86 new
  contract tests.
- **W3C Verifiable Credentials layer** (`2_w3c-ssi-layer/verifiable-credentials/`):
  issuer, holder, verifier, 10 automotive schemas, selective disclosure,
  revocation — 28 tests, real secp256k1 signatures.
- **Canonical MOBI VID layer** (`2_w3c-ssi-layer/mobi-vid/`): VID I birth
  certificates + VID II (11 lifecycle event types) as W3C VCs with
  on-chain content-hash anchoring — 21 on-chain tests.
- **RQ1 gas benchmark** across all 9 standards with LaTeX/CSV thesis
  table generation (`4_comparison-framework/`).
- **RQ4/Thrust 3 real V2V latency data**: SUMO loop with real ECDSA/VC
  verification (SSI warm-verify p95 0.27 ms ≪ 100 ms budget).
- **RQ2/Thrust 5 security analysis** in two complementary lenses: a
  54-test authorization/replay suite (43/43 DEFENDED, CI-gated) and a
  threat-matrix analysis (Sybil/recovery/privacy).
- **Chapter 5 (Results) draft** assembled entirely from measured artifacts.
- CI workflows that run the real suites and gate on the measured 90%
  compliance target.

### Fixed
- **VC verification was mocked** (accepted forged credentials) → replaced
  the cv2x-testbed implementation with a shim over the canonical, tested
  layer; forged/replayed credentials now fail.
- **MOBI VID birth registration had never succeeded on-chain** → fixed two
  contract bugs (uint256-max validity overflow; owner-check ordering).
- **Use-case suite**: 3 crashing use cases fixed, 2 missing thesis use
  cases added, hardcoded "10/10 passing" banner replaced with computed
  12/12 and a real exit code.
- **W3C compliance checker** was 67 hardcoded PASS literals → now executes
  44 real checks (incl. negative attacks); measures 93.2%.
- **Chain providers** didn't import under web3 v7 → migrated
  (`geth_poa_middleware`, `raw_transaction`, real key resolution).
- **All 14 failing Hardhat tests** repaired (ethers v6 migration, contract
  API alignment).
- Fabricated blockchain cost figures relabeled as assumptions pointing to
  the measured data; `SESSION_3_SUMMARY.md` given an honest correction
  header.

### Known limitations (carried into 0.8)
- V2V latency excludes radio/MAC/network-stack; mobility is simulated
  (no SUMO binary in the measurement environment).
- Gas measured on Hardhat-local; no public-testnet (Sepolia) validation yet.
- MOBI VID VIN encryption is demo-grade; `attestEvent` signature is not
  verified on-chain (recorded finding).
- ERC-4337 EntryPoint and LSP8 are minimal representative implementations
  (documented in-header).

---

## [0.4.0] — 2026-06-21 — "Thesis Restructure & W3C DID Layer"
### Added
- Numbered 4-part repository structure mapping to thesis chapters.
- W3C DID Core v1.0 resolver (4 methods: ethr, nft, key, mobi).
- Initial CI/CD workflows; thesis-quality README and documentation set.
- Second-pass planning and inventory documents.

## [0.1.0] — earlier — "Blockchain Identity Foundations"
### Added
- ERC-1056, ERC-721, ERC-725 vehicle-identity smart contracts and tests
  (initial thesis prototype work).

[0.7.0]: milestone — integration & verification
[0.4.0]: milestone — restructure & DID layer
[0.1.0]: milestone — foundations
