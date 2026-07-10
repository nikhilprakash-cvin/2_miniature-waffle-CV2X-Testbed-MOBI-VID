# 3. CV2X Testbed — Location Map

The working CV2X testbed implementation lives in the repository-root
directory **`cv2x-testbed/`** (built by a parallel development session and
verified/repaired in the July 2026 integration pass). This numbered
directory is retained for the thesis chapter mapping; physically moving
~100 files would break the testbed's internal `sys.path` wiring for no
research benefit, so the mapping is documented instead:

| Thesis component | Actual location | Status |
|---|---|---|
| Use-case suite (12 lifecycle scenarios) | `cv2x-testbed/scripts/test_use_cases.py` | ✅ 12/12 passing, real VC verification |
| V2V scenarios (platooning, EEBL) | `cv2x-testbed/scenarios/` | ✅ 3/3 passing, real ECDSA verification |
| Safety applications (FCW/EEBL/IMA) | `cv2x-testbed/sumo/sumo_identity_integration.py` | 🔄 runs in `--simulate` mode; latency values are assumed, not crypto-measured |
| SUMO configs (50 vehicles) | `cv2x-testbed/sumo/` | 🔄 hand-authored net.xml — regenerate with `netconvert` before real-SUMO runs |
| CV2X protocol stack (PHY/MAC, BSM/DENM) | `cv2x-testbed/protocols/cv2x_stack.py` | ✅ simulation-grade |
| Identity providers (PKI, centralized, ERC-1056, MOBI VID) | `cv2x-testbed/identity/` | ✅ imports clean under web3 v7 |
| W3C compliance checker (executable) | `cv2x-testbed/scripts/w3c_compliance_checker.py` | ✅ measured 93.2% |

Canonical SSI layers consumed by the testbed:

- W3C VCs: `2_w3c-ssi-layer/verifiable-credentials/` (28 tests)
- MOBI VID I/II: `2_w3c-ssi-layer/mobi-vid/` (21 tests)
- DID resolution: `2_w3c-ssi-layer/did-resolution/`

Known honest gaps (targets for the next pass): real-SUMO execution (needs
the `sumo` binary + `netconvert`-generated network), replacing the
simulated verification latencies in the SUMO loop with real calls into the
identity providers, and periodic BSM broadcast so runs produce nonzero
message counts.
