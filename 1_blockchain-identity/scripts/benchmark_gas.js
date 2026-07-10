/**
 * benchmark_gas.js
 *
 * Gas benchmark for blockchain vehicle-identity standards implemented in this repo.
 * Executes a comparable lifecycle operation set against each implemented standard
 * on the in-process Hardhat network and records the REAL gasUsed of every transaction.
 *
 * Standards benchmarked (contracts in ./contracts):
 *   - ERC-1056   : contracts/ERC1056/EthereumDIDRegistry.sol
 *   - ERC-721    : contracts/ERC721/CVINVehicleNFT.sol
 *   - ERC-725    : contracts/ERC725/CVIN_DID_ERC725.sol (CVIN_SCBasedAccOrID_DID_ERC725Basic)
 *   - MOBI-VID-V2: contracts/MOBI/MOBIVIDRegistryV2.sol (copied from cv2x-testbed, unmodified)
 *
 * Operation set (per standard; unsupported operations are recorded as null, never faked):
 *   deployRegistry, createIdentity, updateAttribute, addDelegateOrClaim, revoke, transferOwnership
 *
 * Output: ../4_comparison-framework/results/gas_benchmark.json
 *
 * Run:  npx hardhat run scripts/benchmark_gas.js
 */

const fs = require("fs");
const path = require("path");
const { ethers } = require("hardhat");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Execute a tx-returning promise and return its gasUsed as a Number. */
async function gasOf(txPromise) {
  const tx = await txPromise;
  const receipt = await tx.wait();
  return Number(receipt.gasUsed);
}

/** Deploy a contract and return { contract, gasUsed }. */
async function deployWithGas(factory, ...args) {
  const contract = await factory.deploy(...args);
  await contract.waitForDeployment();
  const receipt = await contract.deploymentTransaction().wait();
  return { contract, gasUsed: Number(receipt.gasUsed) };
}

function op(gasUsed, txCount, notes) {
  return { gasUsed, txCount, notes };
}

function unsupported(notes) {
  return { gasUsed: null, txCount: 0, notes };
}

// ---------------------------------------------------------------------------
// ERC-1056 (EthereumDIDRegistry)
// ---------------------------------------------------------------------------

async function benchmarkERC1056(signers) {
  const [deployer, identityOwner, delegate, newOwner] = signers;
  const results = {};

  const Factory = await ethers.getContractFactory(
    "contracts/ERC1056/EthereumDIDRegistry.sol:EthereumDIDRegistry",
    deployer
  );
  const { contract: registry, gasUsed: deployGas } = await deployWithGas(Factory);
  results.deployRegistry = op(
    deployGas,
    1,
    "Single shared registry for all identities (deployed once per network)."
  );

  const identity = identityOwner.address; // in ERC-1056 every address IS a DID
  const attrName = ethers.encodeBytes32String("did/pub/Secp256k1/veriKey");
  const attrValue = ethers.toUtf8Bytes(
    "0x02b97c30de767f084ce3080168ee293053ba33b235d7116a3263d29f1450936b71"
  );
  const oneYear = 365 * 24 * 60 * 60;
  const reg = registry.connect(identityOwner);

  // Identity creation is implicit (free) in ERC-1056; the first on-chain action
  // is publishing a verification key via setAttribute.
  results.createIdentity = op(
    await gasOf(reg.setAttribute(identity, attrName, attrValue, oneYear)),
    1,
    "Identity exists implicitly (every address is a DID, zero-cost). Measured: first setAttribute publishing a verification key."
  );

  const newValue = ethers.toUtf8Bytes(
    "0x03c1d5e8f2a9b4c7d0e3f6a9b2c5d8e1f4a7b0c3d6e9f2a5b8c1d4e7f0a3b6c9d2"
  );
  results.updateAttribute = op(
    await gasOf(reg.setAttribute(identity, attrName, newValue, oneYear)),
    1,
    "setAttribute rotating the published key (event-only storage; DID document built off-chain from event history)."
  );

  const delegateType = ethers.encodeBytes32String("veriKey");
  results.addDelegateOrClaim = op(
    await gasOf(reg.addDelegate(identity, delegateType, delegate.address, oneYear)),
    1,
    "addDelegate(veriKey) with 1-year validity. On-chain claims are not part of ERC-1056."
  );

  results.revoke = op(
    await gasOf(reg.revokeAttribute(identity, attrName, newValue)),
    1,
    "revokeAttribute of the published key. revokeDelegate is also supported at similar cost."
  );

  results.transferOwnership = op(
    await gasOf(reg.changeOwner(identity, newOwner.address)),
    1,
    "changeOwner: rotates the controlling key of the DID (identifier itself is stable)."
  );

  return results;
}

// ---------------------------------------------------------------------------
// ERC-721 (CVINVehicleNFT)
// ---------------------------------------------------------------------------

async function benchmarkERC721(signers) {
  const [deployer, vehicleOwner, approvedOperator, newOwner] = signers;
  const results = {};

  const Factory = await ethers.getContractFactory("CVINVehicleNFT", deployer);
  const { contract: nft, gasUsed: deployGas } = await deployWithGas(Factory);
  results.deployRegistry = op(
    deployGas,
    1,
    "Single shared NFT contract; deployer receives DEFAULT_ADMIN_ROLE and MANUFACTURER_ROLE in constructor."
  );

  const vin = "1HGBH41JXMN109186";
  const mintGas = await gasOf(
    nft.mintVehicle(
      vehicleOwner.address,
      vin,
      "Honda",
      "Civic",
      2024,
      "Blue",
      "ipfs://QmVehicleMetadataExampleHash"
    )
  );
  const tokenId = 1; // first minted token (contract starts _nextTokenId at 1)
  results.createIdentity = op(
    mintGas,
    1,
    "mintVehicle (manufacturer-only): mints NFT, stores VIN mapping + on-chain metadata struct + initial transfer record."
  );

  // updateAttribute analogue: append a service record (requires SERVICE_CENTER_ROLE;
  // role grant is setup, not counted in the operation gas).
  await (await nft.grantServiceCenterRole(deployer.address)).wait();
  results.updateAttribute = op(
    await gasOf(nft.addServiceRecord(tokenId, "ipfs://QmServiceRecordExampleHash")),
    1,
    "No key/attribute model in ERC-721. Measured closest analogue: addServiceRecord appending a metadata URI (role grant excluded as setup)."
  );

  results.addDelegateOrClaim = op(
    await gasOf(nft.connect(vehicleOwner).approve(approvedOperator.address, tokenId)),
    1,
    "approve(): delegates TRANSFER rights only - not a verification-key delegation or identity claim as in DID standards."
  );

  results.transferOwnership = op(
    await gasOf(
      nft
        .connect(vehicleOwner)
        .transferFrom(vehicleOwner.address, newOwner.address, tokenId)
    ),
    1,
    "transferFrom: token transfer with on-chain transfer-history bookkeeping (contract overrides _update)."
  );

  results.revoke = op(
    await gasOf(nft.deactivateVehicle(tokenId)),
    1,
    "deactivateVehicle (admin-only): marks identity inactive; token itself is not burned."
  );

  return results;
}

// ---------------------------------------------------------------------------
// ERC-725 (CVIN_SCBasedAccOrID_DID_ERC725Basic)
// ---------------------------------------------------------------------------

async function benchmarkERC725(signers) {
  const [, identityOwner, , newOwner] = signers;
  const results = {};

  results.deployRegistry = unsupported(
    "No shared registry in ERC-725: each identity is its own proxy-account contract. Deployment cost is counted under createIdentity."
  );

  const Factory = await ethers.getContractFactory(
    "CVIN_SCBasedAccOrID_DID_ERC725Basic",
    identityOwner
  );
  const { contract: identityContract, gasUsed: deployGas } = await deployWithGas(Factory);
  results.createIdentity = op(
    deployGas,
    1,
    "Per-vehicle identity contract deployment (proxy account); deployer becomes owner/management key. Paid once per identity."
  );

  const mgmtKey = ethers.keccak256(ethers.toUtf8Bytes("vehicle-mgmt-key-1"));
  results.updateAttribute = op(
    await gasOf(identityContract.addKey(mgmtKey, 1, 1)),
    1,
    "addKey(purpose=1 MANAGEMENT, type=1 ECDSA): key rotation/addition stored in contract state."
  );

  const claimKey = ethers.keccak256(ethers.toUtf8Bytes("vehicle-claim-key-1"));
  results.addDelegateOrClaim = op(
    await gasOf(identityContract.addKey(claimKey, 3, 1)),
    1,
    "addKey(purpose=3 CLAIM signer key). Full on-chain claims require the companion ERC-735 contract (not yet implemented)."
  );

  results.revoke = op(
    await gasOf(identityContract.removeKey(claimKey)),
    1,
    "removeKey: deletes key and compacts the key array (cost grows with number of stored keys)."
  );

  results.transferOwnership = op(
    await gasOf(identityContract.transferOwnership(newOwner.address)),
    1,
    "transferOwnership of the identity contract to the new vehicle owner."
  );

  return results;
}

// ---------------------------------------------------------------------------
// MOBI VID V2 (MOBIVIDRegistryV2)
// ---------------------------------------------------------------------------

async function benchmarkMOBIVIDV2(signers) {
  const [deployer, firstOwner, serviceCenter, newOwner, vehicleWallet] = signers;
  const results = {};

  const Factory = await ethers.getContractFactory("MOBIVIDRegistryV2", deployer);
  const { contract: registry, gasUsed: deployGas } = await deployWithGas(Factory);
  results.deployRegistry = op(
    deployGas,
    1,
    "Single shared registry (V2 = ERC-1056 base + MOBI VID I birth certificates + VID II lifecycle events); deployer becomes registry authority + authorized manufacturer."
  );

  const vehicleIdentity = vehicleWallet.address;
  const vin = "5YJSA1E26MF123456";
  const vinHash = ethers.keccak256(ethers.toUtf8Bytes(vin));

  // NOTE: birthAttributes MUST be empty ("0x"). Non-empty attributes trigger the
  // inherited V1 setAttribute with validity = type(uint256).max, which overflows
  // (block.timestamp + validity) and reverts. Known V1 bug, worked around here.
  const birthGas = await gasOf(
    registry.registerVehicleBirth(
      vehicleIdentity,
      vinHash,
      "encrypted:AES256:VINCIPHERTEXT==",
      ethers.keccak256(ethers.toUtf8Bytes("ipfs://QmBirthCertificate")),
      firstOwner.address,
      "0x"
    )
  );
  results.createIdentity = op(
    birthGas,
    1,
    "registerVehicleBirth (MOBI VID I birth certificate): VIN hash + encrypted VIN + cert hash + first owner. birthAttributes left empty to avoid known V1 validity-overflow bug."
  );

  // Setup: authorize a service center so lifecycle events can be issued (not counted).
  await (await registry.authorizeIssuer(serviceCenter.address, 3 /* SERVICE_CENTER */)).wait();

  const eventGas = await gasOf(
    registry.connect(serviceCenter).recordLifecycleEvent(
      vehicleIdentity,
      0, // EventType.MAINTENANCE
      15000, // odometer
      ethers.keccak256(ethers.toUtf8Bytes("ipfs://QmMaintenanceRecord")),
      ethers.keccak256(ethers.toUtf8Bytes("vc:jwt:maintenance-credential")),
      "BC-CAN"
    )
  );
  results.updateAttribute = op(
    eventGas,
    1,
    "recordLifecycleEvent (MOBI VID II, MAINTENANCE): stores full event struct + VC hash + counters on-chain. Issuer authorization excluded as setup."
  );

  // Get the eventId for attestation.
  const eventIds = await registry.getVehicleEvents(vehicleIdentity);
  const eventId = eventIds[0];

  // Setup: authorize a second issuer (deployer as DEALER) to attest (not counted).
  await (await registry.authorizeIssuer(deployer.address, 2 /* DEALER */)).wait();
  const attestGas = await gasOf(
    registry.attestEvent(eventId, vehicleIdentity, "0x" + "ab".repeat(65))
  );

  // Also measure the inherited ERC-1056 addDelegate for cross-standard comparability.
  const delegateType = ethers.encodeBytes32String("sigAuth");
  const addDelegateGas = await gasOf(
    registry
      .connect(firstOwner)
      .addDelegate(vehicleIdentity, delegateType, serviceCenter.address, 365 * 24 * 60 * 60)
  );
  results.addDelegateOrClaim = op(
    addDelegateGas,
    1,
    `Inherited ERC-1056 addDelegate (sigAuth, 1 year). V2-native multi-party attestEvent (claim analogue, 65-byte signature stored) measured separately: ${attestGas} gas.`
  );

  results.transferOwnership = op(
    await gasOf(
      registry
        .connect(firstOwner)
        .transferVehicleOwnership(vehicleIdentity, newOwner.address, 20000, "ICBC BC-CAN")
    ),
    1,
    "transferVehicleOwnership: appends odometer-stamped ownership record + ERC-1056 changeOwner. Called by current owner."
  );

  results.revoke = op(
    await gasOf(registry.connect(newOwner).revokeIdentity(vehicleIdentity)),
    1,
    "revokeIdentity (inherited ERC-1056 extension): permanently flags the vehicle DID as revoked (decommissioning)."
  );

  return results;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const signers = await ethers.getSigners();
  const network = await ethers.provider.getNetwork();

  console.log("CVIN vehicle-identity gas benchmark");
  console.log(`Network: ${network.name} (chainId ${network.chainId})`);
  console.log("");

  const results = {};

  console.log("Benchmarking ERC-1056 (EthereumDIDRegistry)...");
  results["ERC-1056"] = await benchmarkERC1056(signers);

  console.log("Benchmarking ERC-721 (CVINVehicleNFT)...");
  results["ERC-721"] = await benchmarkERC721(signers);

  console.log("Benchmarking ERC-725 (CVIN_SCBasedAccOrID_DID_ERC725Basic)...");
  results["ERC-725"] = await benchmarkERC725(signers);

  console.log("Benchmarking MOBI-VID-V2 (MOBIVIDRegistryV2)...");
  results["MOBI-VID-V2"] = await benchmarkMOBIVIDV2(signers);

  const output = {
    ...results,
    metadata: {
      solcVersion: "0.8.24",
      solcSettings: { optimizer: { enabled: true, runs: 200 }, viaIR: true },
      ozVersion: "5.0.2",
      date: new Date().toISOString(),
      network: "hardhat-local",
      chainId: Number((await ethers.provider.getNetwork()).chainId),
      operations: [
        "deployRegistry",
        "createIdentity",
        "updateAttribute",
        "addDelegateOrClaim",
        "revoke",
        "transferOwnership",
      ],
      contracts: {
        "ERC-1056": "contracts/ERC1056/EthereumDIDRegistry.sol:EthereumDIDRegistry",
        "ERC-721": "contracts/ERC721/CVINVehicleNFT.sol:CVINVehicleNFT",
        "ERC-725": "contracts/ERC725/CVIN_DID_ERC725.sol:CVIN_SCBasedAccOrID_DID_ERC725Basic",
        "MOBI-VID-V2": "contracts/MOBI/MOBIVIDRegistryV2.sol:MOBIVIDRegistryV2 (copied unmodified from cv2x-testbed)",
      },
      notes:
        "gasUsed is the exact receipt.gasUsed of a single representative transaction per operation on a fresh Hardhat in-process network. null = operation not supported by the standard (see notes). Setup transactions (role grants, issuer authorization) are excluded from operation gas.",
    },
  };

  const outDir = path.resolve(__dirname, "../../4_comparison-framework/results");
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, "gas_benchmark.json");
  fs.writeFileSync(outFile, JSON.stringify(output, null, 2));

  // Console summary table
  console.log("\n=== Gas benchmark summary (gasUsed) ===");
  const opsList = output.metadata.operations;
  const header = ["operation", ...Object.keys(results)];
  console.log(header.join("\t"));
  for (const o of opsList) {
    const row = [o];
    for (const std of Object.keys(results)) {
      const r = results[std][o];
      row.push(r && r.gasUsed !== null ? String(r.gasUsed) : "n/a");
    }
    console.log(row.join("\t"));
  }
  console.log(`\nResults written to ${outFile}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
