# 4. Comparison Framework

Quantitative comparison of blockchain vehicle-identity standards implemented in this
repository. The benchmark measures **on-chain gas cost** for a comparable set
of identity lifecycle operations across **all 9 standards** of the thesis comparison
matrix (ERC-1056, ERC-721, ERC-725, ERC-735, ERC-1155, ERC-4337, LSP8, MOBI VID V2,
CVIN-Combined), executed against the real contract implementations on a local
Hardhat network.

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
field in `gas_benchmark.json` for the exact function measured and any caveats).
All **9 standards** of the thesis comparison matrix are now measured; the table
below is rotated (standards as rows) to fit:

| Standard | Deploy registry | Create identity | Update key/attribute | Add delegate/claim | Revoke | Transfer ownership |
|---|---|---|---|---|---|---|
| ERC-1056 | registry deploy | first `setAttribute` (identity itself is implicit/free) | `setAttribute` | `addDelegate` | `revokeAttribute` | `changeOwner` |
| ERC-721 | NFT contract deploy | `mintVehicle` | `addServiceRecord` | `approve` (transfer rights only) | `deactivateVehicle` | `transferFrom` |
| ERC-725 | — (no shared registry) | per-identity contract deploy | `addKey` (purpose 1) | `addKey` (purpose 3, claim key) | `removeKey` | `transferOwnership` |
| ERC-735 | — (no shared registry) | per-vehicle claim-holder deploy | re-`addClaim` same (issuer, topic) = `ClaimChanged` | `addClaim` (issuer-signed, ecrecover-verified) | `removeClaim` | `transferOwnership` |
| ERC-1155 | credential contract deploy | `registerVehicle` (mints BIRTH_CERT) | `setTokenURI` | `issueCredential` | `revokeCredential` (burn) | `issuerTransferCredential` (BIRTH_CERT) |
| ERC-4337 | minimal EntryPoint deploy | smart-account deploy | `setAttribute` direct (plus separate via-EntryPoint entry) | `setGuardian` (recovery delegate) | `setGuardian(0)` (`recoverOwner` in notes) | `transferOwnership` (key rotation) |
| LSP8 | collection contract deploy | `mintVehicle` (tokenId = keccak256(VIN)) | `setDataForTokenId` | — (no operators/claims implemented) | `revokeVehicle` (burn) | 5-arg `transfer(..., force=true, ...)` |
| MOBI VID V2 | registry deploy | `registerVehicleBirth` | `recordLifecycleEvent` (maintenance) | inherited `addDelegate` (`attestEvent` cost reported in notes) | `revokeIdentity` | `transferVehicleOwnership` |
| CVIN-Combined | hybrid registry deploy | first `setAttribute` (implicit/free identity) | `setAttribute` (event-only) | `addClaim` (raw-digest sig, on-chain storage; `addDelegate` in notes) | `removeClaim` | `changeOwner` |

The operation set additionally contains a seventh, ERC-4337-only entry,
`updateAttributeVia4337`: the same `setAttribute` routed through the EntryPoint
as a `PackedUserOperation` (`handleOp` → `validateUserOp` → `execute`). The
delta versus the direct call is the **4337 indirection overhead**, a headline
finding of the thesis comparison.

Benchmarked contracts:

- **ERC-1056** — `1_blockchain-identity/contracts/ERC1056/EthereumDIDRegistry.sol`
- **ERC-721** — `1_blockchain-identity/contracts/ERC721/CVINVehicleNFT.sol`
  (feature-rich variant: on-chain VIN mapping, metadata struct, transfer history)
- **ERC-725 (v1-style basic)** — `1_blockchain-identity/contracts/ERC725/CVIN_DID_ERC725.sol`
- **ERC-735** — `1_blockchain-identity/contracts/ERC735/CVINVehicleClaimHolder.sol`
- **ERC-1155** — `1_blockchain-identity/contracts/ERC1155/CVINVehicleCredential1155.sol`
- **ERC-4337** — `1_blockchain-identity/contracts/ERC4337/CVINVehicleAccount.sol`
  + `CVINMinimalEntryPoint.sol`
- **LSP8** — `1_blockchain-identity/contracts/LSP8/CVINVehicleLSP8.sol`
- **MOBI VID V2** — `1_blockchain-identity/contracts/MOBI/MOBIVIDRegistryV2.sol`,
  copied **unmodified** from `cv2x-testbed/contracts/` (together with its base
  contracts `MOBIVIDRegistry.sol` and `ERC1056Registry.sol`).
- **CVIN-Combined** — `1_blockchain-identity/contracts/CVINCombined/CVINCombinedIdentity.sol`
  (the thesis hybrid: ERC-1056 event-based registry + ERC-735 on-chain claims)

## Honest scope: what is NOT measured

- Operations a standard does not support are recorded as `null` in the JSON and
  rendered as "—" in the tables (e.g. ERC-725/ERC-735 have no shared registry
  deployment; LSP8 has no delegate/claim mechanism in this implementation).
- Per-standard semantic caveats (the operations are the *closest native
  analogues*, not identical semantics — full details in the JSON `notes`):
  - **ERC-1056**: identity creation is implicit/free; the measured "create" is the
    first key-publishing `setAttribute` (event-only storage).
  - **ERC-721**: `approve` delegates *transfer rights only*, not verification keys;
    `deactivateVehicle` flags the identity inactive rather than revoking a DID.
  - **ERC-725**: v1-style basic key manager, not a full LSP0/ERC-725Y account;
    per-identity deployment is counted as identity creation.
  - **ERC-735**: per-vehicle claim-holder deployment (~1.40M gas) is the identity
    creation cost; `addClaim` includes on-chain ecrecover signature verification
    plus full claim storage.
  - **ERC-1155**: credentials are soulbound by design, so "transfer ownership" is
    the issuer-mediated BIRTH_CERT re-binding, not a holder-initiated transfer.
  - **ERC-4337**: numbers **exclude real-world bundler overhead** (mempool,
    `handleOps` batching, paymaster, deposit/refund gas accounting) — the
    EntryPoint is a minimal single-op research harness; the account is deployed
    directly (no initCode/factory); guardian `recoverOwner` is reported in notes.
  - **LSP8**: representative implementation — LSP1 universal-receiver hooks are
    omitted (transfers use `force=true`) and operator authorization is not
    implemented; a canonical LUKSO LSP8 transfer would cost more.
  - **MOBI VID V2**: V1 is not benchmarked standalone due to known bugs (validity
    overflow in the birth-attribute path); V2 is benchmarked with the documented
    workaround (empty `birthAttributes`).
  - **CVIN-Combined**: `addClaim` verifies a raw-digest (non-EIP-191) issuer
    signature and stores the claim on-chain — the hybrid's deliberate trade-off
    (cheap event-based ops, expensive O(1)-verifiable claims).
- Single-transaction measurements on a local Hardhat node (`gasUsed` is
  deterministic for a given contract/state — verified by back-to-back runs —
  but first-write vs. re-write storage costs matter; the sequence used is
  documented in the script). No statistical sampling across state variants, no
  L2/mainnet calldata pricing, no fiat cost conversion, no latency/throughput
  measurements.
- Setup transactions (role grants, issuer authorization) are executed but
  **excluded** from the reported operation gas; they are noted in the JSON.

## Results snapshot

See `results/gas_comparison.csv` for the current numbers. Headline sanity checks
(consistent with the gas figures printed by the 147-test suite):
ERC-1056 `setAttribute` ≈ 52.6k gas (creation) / 35.5k (update, warm slot);
MOBI VID V2 `recordLifecycleEvent` ≈ 306.9k gas; ERC-4337 account deployment
≈ 768k gas with a 4337 indirection overhead of ≈ 46.9k gas per operation
(96.2k via EntryPoint vs 49.4k direct); LSP8 `mintVehicle` ≈ 149.4k gas;
CVIN-Combined `addClaim` ≈ 290k gas vs 35.1k for its event-only `setAttribute` —
the hybrid's measured trade-off.
