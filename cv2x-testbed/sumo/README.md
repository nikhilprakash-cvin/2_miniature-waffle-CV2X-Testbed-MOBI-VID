# SUMO + Vehicle Identity Integration (Thrust 3: V2V latency budget)

## Overview

This directory integrates traffic simulation (SUMO, or a mock mobility model
when SUMO is not installed) with **real cryptographic identity verification**
in the V2V message path. It answers the thesis question: *can identity
verification fit inside the ~100 ms V2V safety budget?*

Every Basic Safety Message (BSM) is **actually signed at send and actually
verified at receive**; all reported latencies are measured with
`time.perf_counter` around real cryptographic operations.

### What is REAL (measured)
- **PKI population (30%)**: IEEE 1609.2-style pseudonym certificates from
  `identity/centralized_provider.py`. ECDSA P-256 signing per BSM; receivers
  perform full X.509 chain validation (CA signature, validity window, CRL)
  on first contact with a pseudonym certificate ("cold"), then cache the
  certificate public key and do a per-message ECDSA verify ("warm").
- **SSI population ("MOBI_VID", 70%)**: each vehicle holds a secp256k1 key,
  a `did:ethr` DID, and a W3C **V2VSafetyCredential** issued through the
  canonical VC layer (`identity/w3c_verifiable_credentials.py`, delegating
  to `2_w3c-ssi-layer/verifiable-credentials/`). BSMs are signed per-message
  with EIP-191 personal-sign. On first contact with a peer DID, receivers
  run **full Verifiable Credential verification** (structure, validity
  window, revocation, issuer signature recovery, trusted-issuer check,
  subject/DID binding) plus BSM signature recovery ("cold"); afterwards the
  peer's signing address is cached and each message costs one signature
  recovery + address comparison ("warm").
- **Attack rejection**: tampered messages (payload modified after signing)
  and messages from an unknown/uncredentialed sender are injected each run
  and must be rejected (`attack_tests` in the results JSON).

### What is MOCK (not measured)
- **Mobility** in `--simulate` mode: a persistent kinematic model
  (50 vehicles on a 5 km, 3-lane highway) stands in for SUMO. With SUMO
  installed, mobility comes from TraCI.
- **Radio channel**: messages are delivered in-process to up to 8 nearest
  neighbors within 300 m. There is no network stack in the path — no
  channel loss, no MAC/PHY latency, no congestion. Reported numbers are
  **compute latency of identity verification only**.
- The `CentralizedVehicleRegistry` birth-certificate anchor is an in-memory
  registry (centralized baseline), not an actual blockchain.

## Files

- `sumo_identity_integration.py` — integration + measurement harness
- `highway_intersection.net.xml`, `routes.rou.xml`, `simulation.sumocfg` —
  SUMO network/route configuration (used only when SUMO is installed)
- `results/v2v_latency.json` — machine-readable results of the last run

## Usage

```bash
# No SUMO required (mock mobility, real crypto) — default 60 s, 50 vehicles
python3 sumo_identity_integration.py --simulate --duration 60

# With SUMO installed
python3 sumo_identity_integration.py --duration 60
python3 sumo_identity_integration.py --gui

# Options: --vehicles N (simulate mode), --seed N
```

A default 60 s `--simulate` run broadcasts BSMs from every vehicle at 10 Hz
(~30,000 signed messages) and performs ~170,000 receiver-side verifications
in well under a minute of wall-clock time (with `coincurve` installed; see
below).

## Measured results (60 s, 50 vehicles, `--simulate`, this machine)

With native secp256k1 (`pip install coincurve`, auto-detected by
`eth-keys`):

| Operation | Median | p95 | n |
|---|---|---|---|
| PKI sign (ECDSA P-256) | 0.10 ms | 0.16 ms | 9,014 |
| PKI verify — cold (cert chain + CRL + ECDSA) | 0.56 ms | 0.84 ms | 591 |
| PKI verify — warm (cached cert, ECDSA) | 0.10 ms | 0.14 ms | 52,197 |
| SSI sign (EIP-191 secp256k1) | 0.30 ms | 0.37 ms | 21,047 |
| SSI verify — cold (full VC verification) | 0.54 ms | 0.84 ms | 310 |
| SSI verify — warm (sig recovery vs cached peer) | 0.20 ms | 0.27 ms | 120,541 |

Without `coincurve` (pure-Python secp256k1 fallback in `eth-keys`), the SSI
path is roughly: sign ~4.8 ms, warm verify ~7.4 ms, cold verify ~15 ms
(median) — slower, but still inside the 100 ms budget, and warm verification
still inside the 10 ms signature-check target. PKI numbers are unaffected
(the `cryptography` package uses OpenSSL).

**Verdict (measured p95 vs targets):** both populations fit the 100 ms V2V
budget and the 10 ms per-message signature-check target on this hardware,
*excluding* network/MAC latency, which is not modeled here. The verdict is
computed from measured p95 samples; a run with zero verified messages
reports "NO DATA" instead of a pass.

## Architecture of a verification (receiver side)

```
first contact (cold):                      per message (warm):
  PKI: load cert PEM                         PKI: ECDSA P-256 verify
       verify cert sig vs CA                       against cached cert key
       validity window + CRL
       ECDSA verify BSM sig
       cache cert public key

  SSI: verify V2VSafetyCredential            SSI: recover signer address
       (issuer sig recovery, trusted              from BSM signature,
        issuer, validity, revocation)             compare to cached
       check VC subject == sender DID             peer address
       recover BSM signer, bind to DID
       cache peer address
```

This mirrors the realistic V2V architecture: a peer's credential is verified
once per encounter, while every 10 Hz message costs only a signature check.

## Safety applications

FCW (forward collision warning) and EEBL (emergency electronic brake light)
events are generated from vehicle kinematics and broadcast **through the
same signed/verified message path** as BSMs, so safety-event messages are
included in the latency samples. They demonstrate the message flow; the
mobility that triggers them is mock in `--simulate` mode.

## Results JSON

`results/v2v_latency.json` contains per-population statistics
(`pki`/`ssi` × `sign_ms`/`cold_ms`/`warm_ms`, each with
`median_ms`/`p95_ms`/`n`), top-level `messages_sent`,
`messages_verified`, `verification_failures`, `attack_tests`
(tampered PKI/SSI + uncredentialed sender, all must be `true` = rejected),
and a `budgets` block with the pass/fail comparison against the 100 ms /
10 ms targets.

## Installation

```bash
pip install cryptography eth-account       # required
pip install coincurve                      # optional: ~40x faster secp256k1
sudo apt-get install sumo sumo-tools       # optional: real mobility
pip install traci sumolib                  # optional: TraCI bindings
```

## Known limitations

1. Mobility is mock in `--simulate` mode (no car-following model, no
   intersection traffic); with SUMO installed, TraCI mobility is used but
   has not been re-validated in this environment.
2. No network stack in the measurement path: latencies exclude radio,
   MAC-layer, and channel-congestion delays.
3. Revocation checking is in-memory (CRL set / VC revocation registry);
   no CRL distribution or OCSP round-trip latency is modeled.
4. Single-host measurement: sender and receivers share one CPU; per-message
   costs are serialized rather than parallel per vehicle.

## References

- [SUMO Documentation](https://sumo.dlr.de/docs/)
- [SAE J2735 (V2V Messages)](https://www.sae.org/standards/content/j2735_202007/)
- [IEEE 1609.2 (V2X Security)](https://standards.ieee.org/standard/1609_2-2016.html)
- [W3C Verifiable Credentials Data Model v2.0](https://www.w3.org/TR/vc-data-model-2.0/)
- [MOBI VID Specification](https://dlt.mobi/vid/)
