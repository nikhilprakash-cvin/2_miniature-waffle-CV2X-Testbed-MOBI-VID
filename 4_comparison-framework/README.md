# 4. Comparison Framework

Quantitative comparison of blockchain vehicle-identity standards implemented in this
repository. The current benchmark measures **on-chain gas cost** for a comparable set
of identity lifecycle operations, executed against the real contract implementations
on a local Hardhat network.

## Directory layout

```
4_comparison-framework/
├── performance-metrics/
│   └── generate_tables.py      # JSON -> CSV + LaTeX table generator
├── results/
│   ├── gas_benchmark.json      # raw benchmark output (generated)
│   ├── gas_comparison.csv      # comparison table, CSV (generated)
│   └── gas_comparison.tex      # comparison table, LaTeX booktabs (generated)
└── security-analysis/          # qualitative analysis (separate, not benchmarked here)
```

The benchmark script itself lives in the Hardhat project:
`1_blockchain-identity/scripts/benchmark_gas.js`.

## How to reproduce

Prerequisites: Node.js >= 18 and Python 3 (stdlib only, no pip packages needed).
Dependencies for `1_blockchain-identity` are pinned in its `package-lock.json`
(Solidity 0.8.24, optimizer 200 runs + via-IR, OpenZeppelin Contracts 5.0.2).

```bash
# 1. Run the gas benchmark (writes results/gas_benchmark.json)
cd 1_blockchain-identity
npm install                # first time only
npx hardhat run scripts/benchmark_gas.js

# 2. Generate the thesis tables (writes results/gas_comparison.csv and .tex)
cd ../4_comparison-framework/performance-metrics
python3 generate_tables.py
```

The LaTeX table requires `\usepackage{booktabs}` and can be `\input{}` directly
into the thesis.

## What is measured

For each implemented standard, one representative transaction per operation is
executed on a **fresh in-process Hardhat network** (chain id 31337) and the exact
`receipt.gasUsed` is recorded — no estimates, no simulation.

Operation set (mapped to each standard's closest native mechanism; see the `notes`
field in `gas_benchmark.json` for the exact function measured and any caveats):

| Operation | ERC-1056 | ERC-721 | ERC-725 | MOBI VID V2 |
|---|---|---|---|---|
| Deploy registry | registry deploy | NFT contract deploy | — (no shared registry) | registry deploy |
| Create identity | first `setAttribute` (identity itself is implicit/free) | `mintVehicle` | per-identity contract deploy | `registerVehicleBirth` |
| Update key/attribute | `setAttribute` | `addServiceRecord` | `addKey` (purpose 1) | `recordLifecycleEvent` (maintenance) |
| Add delegate/claim | `addDelegate` | `approve` (transfer rights only) | `addKey` (purpose 3, claim key) | inherited `addDelegate` (`attestEvent` cost reported in notes) |
| Revoke | `revokeAttribute` | `deactivateVehicle` | `removeKey` | `revokeIdentity` |
| Transfer ownership | `changeOwner` | `transferFrom` | `transferOwnership` | `transferVehicleOwnership` |

Benchmarked contracts:

- **ERC-1056** — `1_blockchain-identity/contracts/ERC1056/EthereumDIDRegistry.sol`
- **ERC-721** — `1_blockchain-identity/contracts/ERC721/CVINVehicleNFT.sol`
  (feature-rich variant: on-chain VIN mapping, metadata struct, transfer history)
- **ERC-725 (v1-style basic)** — `1_blockchain-identity/contracts/ERC725/CVIN_DID_ERC725.sol`
- **MOBI VID V2** — `1_blockchain-identity/contracts/MOBI/MOBIVIDRegistryV2.sol`,
  copied **unmodified** from `cv2x-testbed/contracts/` (together with its base
  contracts `MOBIVIDRegistry.sol` and `ERC1056Registry.sol`).

## Honest scope: what is NOT measured

- **Only standards with working contract implementations in this repo are
  benchmarked.** The following standards are part of the thesis comparison matrix
  but are **not yet implemented** and therefore have no measured numbers:
  ERC-735 (claim holder), ERC-1155, LSP8 (LUKSO Identifiable Digital Asset),
  ERC-4337 (account abstraction), and the CVIN-Combined architecture.
  No numbers are fabricated for them.
- Operations a standard does not support are recorded as `null` in the JSON and
  rendered as "—" in the tables (e.g. ERC-725 has no shared registry deployment).
- Single-transaction measurements on a local Hardhat node (`gasUsed` is
  deterministic for a given contract/state, but first-write vs. re-write storage
  costs matter; the sequence used is documented in the script). No statistical
  sampling across state variants, no L2/mainnet calldata pricing, no fiat cost
  conversion, no latency/throughput measurements.
- Comparability caveats are explicit in the `notes` fields: the operations are the
  *closest native analogues*, not identical semantics (e.g. ERC-721 `approve`
  delegates transfer rights, not verification keys; MOBI `recordLifecycleEvent`
  stores a full event struct, which is why it costs more than an ERC-1056
  event-only `setAttribute`).
- **MOBI VID V1** (`MOBIVIDRegistry.sol`) is not benchmarked standalone due to known
  bugs (validity overflow with `type(uint256).max` in `registerVehicleBirth`'s
  attribute path; see notes). V2 is benchmarked with the documented workaround
  (empty `birthAttributes`).
- Setup transactions (role grants, issuer authorization) are executed but
  **excluded** from the reported operation gas; they are noted in the JSON.

## Results snapshot

See `results/gas_comparison.csv` for the current numbers. Headline sanity checks:
ERC-1056 `setAttribute` ≈ 52.6k gas (creation) / 35.5k (update, warm slot), and
MOBI VID V2 `recordLifecycleEvent` ≈ 306.9k gas, consistent with the value
verified in the cv2x testbed (~306k).
