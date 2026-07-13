/**
 * benchmark_gas.js
 *
 * Gas benchmark for blockchain vehicle-identity standards implemented in this repo.
 * Executes a comparable lifecycle operation set against each implemented standard
 * on the in-process Hardhat network and records the REAL gasUsed of every transaction.
 *
 * Standards benchmarked (contracts in ./contracts):
 *   - ERC-1056     : contracts/ERC1056/EthereumDIDRegistry.sol
 *   - ERC-721      : contracts/ERC721/CVINVehicleNFT.sol
 *   - ERC-725      : contracts/ERC725/CVIN_DID_ERC725.sol (CVIN_SCBasedAccOrID_DID_ERC725Basic)
 *   - ERC-735      : contracts/ERC735/CVINVehicleClaimHolder.sol
 *   - ERC-1155     : contracts/ERC1155/CVINVehicleCredential1155.sol
 *   - ERC-4337     : contracts/ERC4337/CVINVehicleAccount.sol + CVINMinimalEntryPoint.sol
 *   - LSP8         : contracts/LSP8/CVINVehicleLSP8.sol
 *   - MOBI-VID-V2  : contracts/MOBI/MOBIVIDRegistryV2.sol (copied from cv2x-testbed, unmodified)
 *   - CVIN-Combined: contracts/CVINCombined/CVINCombinedIdentity.sol (ERC-1056 + ERC-735 hybrid)
 *
 * Operation set (per standard; unsupported operations are recorded as null, never faked):
 *   deployRegistry, createIdentity, updateAttribute, updateAttributeVia4337 (ERC-4337 only),
 *   addDelegateOrClaim, revoke, transferOwnership
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
    "addKey(purpose=3 CLAIM signer key). Full on-chain claim storage lives in the companion ERC-735 claim holder, benchmarked separately as ERC-735."
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
// ERC-735 (CVINVehicleClaimHolder)
// ---------------------------------------------------------------------------

async function benchmarkERC735(signers) {
  const [, vehicleOwner, manufacturer, inspector, newOwner] = signers;
  const results = {};

  const VIN = "1HGBH41JXMN109186";
  const ECDSA_SCHEME = 1;
  const VIN_ATTESTATION = 1; // claim topic constants from the contract
  const INSPECTION = 3;

  // Issuer signs keccak256(abi.encodePacked(identityAddress, topic, data))
  // with the standard eth_sign (EIP-191) envelope.
  async function signClaim(issuerSigner, identityAddress, topic, data) {
    const messageHash = ethers.solidityPackedKeccak256(
      ["address", "uint256", "bytes"],
      [identityAddress, topic, data]
    );
    return issuerSigner.signMessage(ethers.getBytes(messageHash));
  }

  function claimIdFor(issuerAddress, topic) {
    return ethers.solidityPackedKeccak256(
      ["address", "uint256"],
      [issuerAddress, topic]
    );
  }

  results.deployRegistry = unsupported(
    "No shared registry in ERC-735: each vehicle identity is its own claim-holder contract. Deployment cost is counted under createIdentity."
  );

  const Factory = await ethers.getContractFactory("CVINVehicleClaimHolder", vehicleOwner);
  const { contract: holder, gasUsed: deployGas } = await deployWithGas(Factory, VIN);
  results.createIdentity = op(
    deployGas,
    1,
    "Per-vehicle claim-holder contract deployment (constructor stores VIN + vinHash, deployer becomes owner). Paid once per identity."
  );

  const identityAddress = await holder.getAddress();

  // addDelegateOrClaim: first addClaim (issuer-signed VIN attestation, ClaimAdded).
  const dataV1 = ethers.toUtf8Bytes(`VIN:${VIN}`);
  const sigV1 = await signClaim(manufacturer, identityAddress, VIN_ATTESTATION, dataV1);
  results.addDelegateOrClaim = op(
    await gasOf(
      holder.addClaim(VIN_ATTESTATION, ECDSA_SCHEME, manufacturer.address, sigV1, dataV1, "ipfs://vin-attestation")
    ),
    1,
    "addClaim (new claim, ClaimAdded): stores full signed claim on-chain after verifying the issuer's EIP-191 signature over (identity, topic, data) via ecrecover. Delegates are not part of ERC-735."
  );

  // updateAttribute analogue: re-adding a claim for the same (issuer, topic)
  // updates it in place (ClaimChanged). ERC-735 has no key/attribute store.
  // Same-length data + URI so this measures a warm same-size rewrite.
  const dataV2 = ethers.toUtf8Bytes(`vin:${VIN}`);
  const sigV2 = await signClaim(manufacturer, identityAddress, VIN_ATTESTATION, dataV2);
  results.updateAttribute = op(
    await gasOf(
      holder.addClaim(VIN_ATTESTATION, ECDSA_SCHEME, manufacturer.address, sigV2, dataV2, "ipfs://vin-attestat-v2")
    ),
    1,
    "No key/attribute model in ERC-735. Measured closest analogue: re-adding a claim for the same (issuer, topic) updates it in place (ClaimChanged, warm same-size rewrite of data/signature/URI)."
  );

  // Add a second claim so revoke deletes a real inspection claim.
  const inspData = ethers.toUtf8Bytes("inspection:2026-07:pass");
  const inspSig = await signClaim(inspector, identityAddress, INSPECTION, inspData);
  await (await holder.addClaim(INSPECTION, ECDSA_SCHEME, inspector.address, inspSig, inspData, "ipfs://inspection")).wait();

  results.revoke = op(
    await gasOf(holder.removeClaim(claimIdFor(inspector.address, INSPECTION))),
    1,
    "removeClaim (owner or issuer): deletes the claim struct and compacts the topic index (ClaimRemoved, storage refund applies)."
  );

  results.transferOwnership = op(
    await gasOf(holder.transferOwnership(newOwner.address)),
    1,
    "transferOwnership of the per-vehicle claim-holder contract to the new vehicle owner."
  );

  return results;
}

// ---------------------------------------------------------------------------
// ERC-1155 (CVINVehicleCredential1155)
// ---------------------------------------------------------------------------

async function benchmarkERC1155(signers) {
  const [deployer, vehicle, newVehicleAddress] = signers;
  const results = {};

  const VIN = "1HGBH41JXMN109186";
  const BIRTH_CERT = 1;
  const REGISTRATION = 2;
  const INSPECTION_CERT = 3;

  const Factory = await ethers.getContractFactory("CVINVehicleCredential1155", deployer);
  const { contract: credential, gasUsed: deployGas } = await deployWithGas(Factory);
  results.deployRegistry = op(
    deployGas,
    1,
    "Single shared multi-token credential contract; deployer receives DEFAULT_ADMIN_ROLE and ISSUER_ROLE in constructor."
  );

  results.createIdentity = op(
    await gasOf(credential.registerVehicle(vehicle.address, VIN)),
    1,
    "registerVehicle (issuer-only): mints one soulbound BIRTH_CERT token, binds VIN string + vinHash mappings to the vehicle address."
  );

  results.updateAttribute = op(
    await gasOf(credential.setTokenURI(REGISTRATION, "ipfs://registration/v2.json")),
    1,
    "No key/attribute model in ERC-1155. Measured closest analogue: setTokenURI per-credential-type metadata URI override (issuer-only)."
  );

  results.addDelegateOrClaim = op(
    await gasOf(credential.issueCredential(vehicle.address, INSPECTION_CERT, 1)),
    1,
    "issueCredential (issuer-only): mints an INSPECTION_CERT credential token to a registered vehicle (claim analogue; delegates are not part of ERC-1155)."
  );

  results.revoke = op(
    await gasOf(credential.revokeCredential(vehicle.address, INSPECTION_CERT, 1)),
    1,
    "revokeCredential (issuer-only burn) of the inspection credential. Burning the BIRTH_CERT would deregister the whole identity."
  );

  results.transferOwnership = op(
    await gasOf(
      credential.issuerTransferCredential(vehicle.address, newVehicleAddress.address, BIRTH_CERT)
    ),
    1,
    "issuerTransferCredential of the BIRTH_CERT: re-binds VIN + registration mappings to the new vehicle address. Credentials are soulbound - holder-initiated transfers revert by design."
  );

  return results;
}

// ---------------------------------------------------------------------------
// ERC-4337 (CVINVehicleAccount + CVINMinimalEntryPoint)
// ---------------------------------------------------------------------------

async function benchmarkERC4337(signers) {
  const [bundler, accountOwner, guardian, newOwner, recoveredOwner] = signers;
  const results = {};

  const EntryPointFactory = await ethers.getContractFactory("CVINMinimalEntryPoint", bundler);
  const { contract: entryPoint, gasUsed: epDeployGas } = await deployWithGas(EntryPointFactory);
  results.deployRegistry = op(
    epDeployGas,
    1,
    "CVINMinimalEntryPoint deployment (shared infrastructure, analogous to a registry). NOTE: minimal research harness, not the canonical v0.7 EntryPoint - no bundler batching, paymasters, deposits or gas accounting."
  );

  const AccountFactory = await ethers.getContractFactory("CVINVehicleAccount", bundler);
  const { contract: account, gasUsed: accountDeployGas } = await deployWithGas(
    AccountFactory,
    await entryPoint.getAddress(),
    accountOwner.address
  );
  results.createIdentity = op(
    accountDeployGas,
    1,
    "Per-vehicle smart-account deployment (identity creation): the account address is the stable vehicle identifier; the signing key can rotate without changing it. Direct deploy - no initCode/AccountFactory counterfactual deployment."
  );

  const ATTR_A = ethers.keccak256(ethers.toUtf8Bytes("cvin/vehicle/vin"));
  const ATTR_B = ethers.keccak256(ethers.toUtf8Bytes("cvin/vehicle/firmwareHash"));
  const VALUE_A = ethers.toUtf8Bytes("1HGCM82633A004352"); // 17 bytes
  const VALUE_B = ethers.toUtf8Bytes("sha256:9f86d0818b"); // 17 bytes (same length, fair comparison)

  // Direct path: owner key calls the account (cold storage slot).
  const directGas = await gasOf(account.connect(accountOwner).setAttribute(ATTR_A, VALUE_A));
  results.updateAttribute = op(
    directGas,
    1,
    "setAttribute called DIRECTLY by the owner key (ERC-725Y-flavoured attribute store, cold slot first write)."
  );

  // 4337 path: the same logical operation as a PackedUserOperation routed
  // through the entry point (handleOp -> validateUserOp -> execute -> self).
  // Uses a different attribute key of identical value length so both paths
  // pay cold-storage first-write costs and the difference is pure indirection.
  const inner = account.interface.encodeFunctionData("setAttribute", [
    ATTR_B,
    ethers.hexlify(VALUE_B),
  ]);
  const callData = account.interface.encodeFunctionData("execute", [
    await account.getAddress(),
    0,
    inner,
  ]);
  const sender = await account.getAddress();
  const userOp = {
    sender,
    nonce: await entryPoint.nonces(sender),
    initCode: "0x",
    callData,
    accountGasLimits: ethers.ZeroHash,
    preVerificationGas: 0,
    gasFees: ethers.ZeroHash,
    paymasterAndData: "0x",
    signature: "0x",
  };
  const userOpHash = await entryPoint.getUserOpHash(userOp);
  userOp.signature = await accountOwner.signMessage(ethers.getBytes(userOpHash)); // EIP-191 over userOpHash
  const viaEpGas = await gasOf(entryPoint.connect(bundler).handleOp(userOp));
  results.updateAttributeVia4337 = op(
    viaEpGas,
    1,
    `Same setAttribute routed as a PackedUserOperation through the EntryPoint (handleOp -> validateUserOp [ecrecover] -> execute -> self-call). Indirection overhead vs direct call: ${viaEpGas - directGas} gas. EXCLUDES real-world bundler overhead (mempool, handleOps batching, paymaster, deposit/refund accounting).`
  );

  results.addDelegateOrClaim = op(
    await gasOf(account.connect(accountOwner).setGuardian(guardian.address)),
    1,
    "setGuardian: designates a social-recovery guardian (recovery-delegate analogue; recovery capability unique to contract accounts). No on-chain claim model in ERC-4337."
  );

  results.transferOwnership = op(
    await gasOf(account.connect(accountOwner).transferOwnership(newOwner.address)),
    1,
    "transferOwnership = signing-key rotation; the identity (account address) is unchanged. Guardian-driven recoverOwner measured separately (see revoke notes)."
  );

  // Guardian recovery (measured, reported in notes; changes owner to recoveredOwner).
  const recoverGas = await gasOf(account.connect(guardian).recoverOwner(recoveredOwner.address));

  results.revoke = op(
    await gasOf(account.connect(recoveredOwner).setGuardian(ethers.ZeroAddress)),
    1,
    `setGuardian(0): revokes the recovery guardian (delegate-revocation analogue; storage clear, refund applies). ERC-4337 has no identity-level revocation - the account contract persists. Guardian recoverOwner (social recovery, new signing key installed by guardian) measured separately: ${recoverGas} gas.`
  );

  return results;
}

// ---------------------------------------------------------------------------
// LSP8 (CVINVehicleLSP8)
// ---------------------------------------------------------------------------

async function benchmarkLSP8(signers) {
  const [authority, vehicleOwner, buyer] = signers;
  const results = {};

  const VIN = "1HGBH41JXMN109186";
  const TOKEN_ID = ethers.keccak256(ethers.toUtf8Bytes(VIN)); // bytes32 tokenId = keccak256(VIN)

  const Factory = await ethers.getContractFactory("CVINVehicleLSP8", authority);
  const { contract: lsp8, gasUsed: deployGas } = await deployWithGas(
    Factory,
    "CVIN Vehicle Identity LSP8",
    "CVIN-LSP8"
  );
  results.deployRegistry = op(
    deployGas,
    1,
    "Single shared LSP8 collection contract; deployer becomes the issuing authority (contract owner)."
  );

  results.createIdentity = op(
    await gasOf(lsp8.mintVehicle(vehicleOwner.address, VIN)),
    1,
    "mintVehicle (authority-only): mints bytes32 tokenId = keccak256(VIN) and stores the VIN in the per-token LSP2-style data store."
  );

  const inspectionKey = await lsp8.DATA_KEY_INSPECTION();
  results.updateAttribute = op(
    await gasOf(
      lsp8.setDataForTokenId(TOKEN_ID, inspectionKey, ethers.toUtf8Bytes("inspection:2026-07-13:pass"))
    ),
    1,
    "setDataForTokenId: writes a per-token ERC-725Y-style data key (TokenIdDataChanged + DataChanged events)."
  );

  results.addDelegateOrClaim = unsupported(
    "Not supported by this representative LSP8 implementation: operator authorization (authorizeOperator) is not implemented, and LSP8 has no native claim model - attestations live in per-token data keys (covered by updateAttribute)."
  );

  results.transferOwnership = op(
    await gasOf(
      lsp8.connect(vehicleOwner).transfer(vehicleOwner.address, buyer.address, TOKEN_ID, true, "0x")
    ),
    1,
    "LSP8 5-arg transfer(from, to, tokenId, force=true, data) by the token owner. force=true skips LSP1 universal-receiver probing (hooks omitted in this implementation)."
  );

  results.revoke = op(
    await gasOf(lsp8.revokeVehicle(TOKEN_ID, "0x")),
    1,
    "revokeVehicle (issuing authority or token owner): burns the token (Transfer to zero + VehicleRevoked); tokenId ceases to exist."
  );

  return results;
}

// ---------------------------------------------------------------------------
// CVIN-Combined (CVINCombinedIdentity: ERC-1056 + ERC-735 hybrid)
// ---------------------------------------------------------------------------

async function benchmarkCVINCombined(signers) {
  const [deployer, identityOwner, delegate, newOwner] = signers;
  const results = {};

  const CLAIM_TOPIC_VIN = 1;
  const SCHEME_ECDSA = 1;
  const ATTR_NAME = ethers.keccak256(ethers.toUtf8Bytes("did/pub/Secp256k1/veriKey"));

  const Factory = await ethers.getContractFactory("CVINCombinedIdentity", deployer);
  const { contract: registry, gasUsed: deployGas } = await deployWithGas(Factory);
  results.deployRegistry = op(
    deployGas,
    1,
    "Single shared hybrid registry (ERC-1056 event-based identity + ERC-735 on-chain claim storage in one contract)."
  );

  const identity = identityOwner.address; // every address is an implicit DID
  const reg = registry.connect(identityOwner);
  const oneDay = 86400;

  results.createIdentity = op(
    await gasOf(
      reg.setAttribute(
        identity,
        ATTR_NAME,
        ethers.toUtf8Bytes("0x02b97c30de767f084ce3080168ee293053ba33b235d7116a3263d29f1450936b71"),
        oneDay
      )
    ),
    1,
    "Identity exists implicitly (ERC-1056 side: every address is a DID, zero-cost). Measured: first setAttribute publishing a verification key (event-only)."
  );

  results.updateAttribute = op(
    await gasOf(
      reg.setAttribute(
        identity,
        ATTR_NAME,
        ethers.toUtf8Bytes("0x03c1d5e8f2a9b4c7d0e3f6a9b2c5d8e1f4a7b0c3d6e9f2a5b8c1d4e7f0a3b6c9d2"),
        oneDay
      )
    ),
    1,
    "setAttribute rotating the published key (ERC-1056 side, event-only storage)."
  );

  // Claim issuer whose private key we control; signs the RAW digest (no
  // EIP-191 envelope) of (registry, identity, topic, data), matching the
  // contract's bare-ecrecover verification. Fixed key (NOT a Hardhat default
  // account) so calldata zero-byte counts - and thus gasUsed - are deterministic
  // across runs.
  const issuerWallet = new ethers.Wallet(
    "0x1f2e3d4c5b6a79881726354453627181920a1b2c3d4e5f60718293a4b5c6d7e8"
  );
  const vinData = ethers.toUtf8Bytes("1HGCM82633A004352");
  const digest = ethers.solidityPackedKeccak256(
    ["address", "address", "uint256", "bytes"],
    [await registry.getAddress(), identity, CLAIM_TOPIC_VIN, vinData]
  );
  const signature = ethers.Signature.from(issuerWallet.signingKey.sign(digest)).serialized;

  // ERC-1056-style addDelegate measured for cross-standard comparability (notes).
  const delegateType = ethers.keccak256(ethers.toUtf8Bytes("veriKey"));
  const addDelegateGas = await gasOf(
    reg.addDelegate(identity, delegateType, delegate.address, oneDay)
  );

  results.addDelegateOrClaim = op(
    await gasOf(
      reg.addClaim(
        identity,
        CLAIM_TOPIC_VIN,
        SCHEME_ECDSA,
        issuerWallet.address,
        signature,
        vinData,
        "ipfs://QmVinAttestation"
      )
    ),
    1,
    `addClaim (ERC-735 side): verifies the issuer's raw-digest ECDSA signature via ecrecover and stores the full claim on-chain (O(1) verification thereafter). Event-only ERC-1056 addDelegate measured separately: ${addDelegateGas} gas.`
  );

  const claimId = ethers.solidityPackedKeccak256(
    ["address", "uint256"],
    [issuerWallet.address, CLAIM_TOPIC_VIN]
  );
  results.revoke = op(
    await gasOf(reg.removeClaim(identity, claimId)),
    1,
    "removeClaim (ERC-735 side): deletes the stored claim + topic index (storage refund applies). Event-only revokeAttribute/revokeDelegate (ERC-1056 side) also supported at ~ERC-1056 cost."
  );

  results.transferOwnership = op(
    await gasOf(reg.changeOwner(identity, newOwner.address)),
    1,
    "changeOwner (ERC-1056 side): rotates the controlling key of the DID (identifier stable)."
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

  console.log("Benchmarking ERC-735 (CVINVehicleClaimHolder)...");
  results["ERC-735"] = await benchmarkERC735(signers);

  console.log("Benchmarking ERC-1155 (CVINVehicleCredential1155)...");
  results["ERC-1155"] = await benchmarkERC1155(signers);

  console.log("Benchmarking ERC-4337 (CVINVehicleAccount + CVINMinimalEntryPoint)...");
  results["ERC-4337"] = await benchmarkERC4337(signers);

  console.log("Benchmarking LSP8 (CVINVehicleLSP8)...");
  results["LSP8"] = await benchmarkLSP8(signers);

  console.log("Benchmarking MOBI-VID-V2 (MOBIVIDRegistryV2)...");
  results["MOBI-VID-V2"] = await benchmarkMOBIVIDV2(signers);

  console.log("Benchmarking CVIN-Combined (CVINCombinedIdentity)...");
  results["CVIN-Combined"] = await benchmarkCVINCombined(signers);

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
        "updateAttributeVia4337",
        "addDelegateOrClaim",
        "revoke",
        "transferOwnership",
      ],
      contracts: {
        "ERC-1056": "contracts/ERC1056/EthereumDIDRegistry.sol:EthereumDIDRegistry",
        "ERC-721": "contracts/ERC721/CVINVehicleNFT.sol:CVINVehicleNFT",
        "ERC-725": "contracts/ERC725/CVIN_DID_ERC725.sol:CVIN_SCBasedAccOrID_DID_ERC725Basic",
        "ERC-735": "contracts/ERC735/CVINVehicleClaimHolder.sol:CVINVehicleClaimHolder",
        "ERC-1155": "contracts/ERC1155/CVINVehicleCredential1155.sol:CVINVehicleCredential1155",
        "ERC-4337": "contracts/ERC4337/CVINVehicleAccount.sol:CVINVehicleAccount + contracts/ERC4337/CVINMinimalEntryPoint.sol:CVINMinimalEntryPoint",
        "LSP8": "contracts/LSP8/CVINVehicleLSP8.sol:CVINVehicleLSP8",
        "MOBI-VID-V2": "contracts/MOBI/MOBIVIDRegistryV2.sol:MOBIVIDRegistryV2 (copied unmodified from cv2x-testbed)",
        "CVIN-Combined": "contracts/CVINCombined/CVINCombinedIdentity.sol:CVINCombinedIdentity",
      },
      notes:
        "gasUsed is the exact receipt.gasUsed of a single representative transaction per operation on a fresh Hardhat in-process network. null = operation not supported by the standard (see notes). Setup transactions (role grants, issuer authorization) are excluded from operation gas. updateAttributeVia4337 exists only for ERC-4337: it is the same setAttribute routed through the EntryPoint as a UserOperation, so the delta vs updateAttribute is the 4337 indirection overhead (bundler overhead excluded).",
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
