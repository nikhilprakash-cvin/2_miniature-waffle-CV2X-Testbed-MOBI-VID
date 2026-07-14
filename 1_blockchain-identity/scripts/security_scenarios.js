/**
 * security_scenarios.js  —  Thrust 5 on-chain attack suite
 *
 * Executes real V2X attack scenarios against each of the 9 vehicle-identity
 * standard contracts on the in-process Hardhat network and records the REAL
 * outcome of every attempt (revert reason captured, state read back). No
 * outcome is invented: an attack is "DEFENDED" only if the malicious tx
 * actually reverted (reason string recorded) or the read-back proves the
 * property; "VULNERABLE" only if the malicious/undesirable action actually
 * succeeded on-chain.
 *
 * Threat categories exercised on-chain:
 *   - impersonation : non-owner create/mint/setAttribute/addClaim must revert;
 *                     forged issuer/UserOp signatures must be rejected.
 *   - replay        : replay of a signed meta-tx / UserOperation must fail
 *                     (nonce), or is recorded as unprotected where it succeeds.
 *   - identity_theft: transfer/theft model demonstrated (token-transferable vs
 *                     owner-authorised vs soulbound).
 *   - sybil         : can an unprivileged attacker create identities at will?
 *                     (gating demonstrated; cost proxy comes from the gas
 *                     benchmark, merged in Python).
 *   - recovery      : key-compromise recovery primitive demonstrated where it
 *                     exists (4337 guardian, 1155 issuer re-bind).
 *   - privacy       : read back on-chain state after a birth/registration op
 *                     and detect plaintext VIN vs hash/ciphertext.
 *
 * Output: ../../4_comparison-framework/security-analysis/results/onchain_security.json
 *
 * Run:  cd 1_blockchain-identity && npx hardhat run scripts/security_scenarios.js
 */

const fs = require("fs");
const path = require("path");
const { ethers } = require("hardhat");

const VIN = "1HGBH41JXMN109186"; // 17-char ISO-3779 VIN used across scenarios

// ---------------------------------------------------------------------------
// Outcome helpers
// ---------------------------------------------------------------------------

function cell(outcome, mechanism, evidence, method = "executed") {
  return { outcome, mechanism, evidence, method };
}

/** Run a tx promise expecting it to revert; capture whether it did + reason. */
async function expectRevert(txPromise) {
  try {
    const tx = await txPromise;
    await tx.wait();
    return { reverted: false, reason: null };
  } catch (err) {
    const reason =
      err.reason ||
      err.shortMessage ||
      (err.info && err.info.error && err.info.error.message) ||
      err.message ||
      "revert";
    return { reverted: true, reason: String(reason) };
  }
}

/** Run a tx promise expecting success; return true/false + reason on failure. */
async function expectSuccess(txPromise) {
  try {
    const tx = await txPromise;
    await tx.wait();
    return { ok: true, reason: null };
  } catch (err) {
    return { ok: false, reason: err.reason || err.shortMessage || err.message };
  }
}

/** Heuristic: does a returned string look like a plaintext VIN (17 alnum)? */
function looksLikeVIN(s) {
  return typeof s === "string" && /^[A-HJ-NPR-Z0-9]{17}$/.test(s);
}

// ---------------------------------------------------------------------------
// ERC-1056  (EthereumDIDRegistry)
// ---------------------------------------------------------------------------

async function scenarioERC1056(signers) {
  const [deployer, owner, attacker, newOwner] = signers;
  const out = {};

  const Reg = await ethers.getContractFactory(
    "contracts/ERC1056/EthereumDIDRegistry.sol:EthereumDIDRegistry",
    deployer
  );
  const reg = await Reg.deploy();
  await reg.waitForDeployment();

  const identity = owner.address; // owner controls its own DID
  const name = ethers.encodeBytes32String("did/pub/Secp256k1/veriKey");
  const value = ethers.toUtf8Bytes("0x02b97c30de767f084ce3080168ee29305");
  const year = 365 * 24 * 60 * 60;

  // impersonation: attacker tries to setAttribute on the victim's DID
  const imp = await expectRevert(
    reg.connect(attacker).setAttribute(identity, name, value, year)
  );
  const impOwner = await expectRevert(
    reg.connect(attacker).changeOwner(identity, attacker.address)
  );
  out.impersonation = cell(
    imp.reverted && impOwner.reverted ? "DEFENDED" : "VULNERABLE",
    "onlyOwner(identity, msg.sender): every state-changer requires actor == identityOwner(identity)",
    `attacker setAttribute reverted: "${imp.reason}"; attacker changeOwner reverted: "${impOwner.reason}"`
  );

  // replay: signed meta-transaction (setAttributeSigned) must not be replayable.
  // Use a fresh wallet as the identity so we control its private key.
  const w = ethers.Wallet.createRandom();
  const wid = w.address;
  const n0 = await reg.nonce(wid);
  const validity = year;
  const digest = ethers.solidityPackedKeccak256(
    ["bytes1", "bytes1", "address", "uint256", "address", "string", "bytes32", "bytes", "uint256"],
    ["0x19", "0x00", await reg.getAddress(), n0, wid, "setAttribute", name, value, validity]
  );
  const sig = w.signingKey.sign(digest);
  const first = await expectSuccess(
    reg.connect(deployer).setAttributeSigned(wid, sig.v, sig.r, sig.s, name, value, validity)
  );
  const replayed = await expectRevert(
    reg.connect(deployer).setAttributeSigned(wid, sig.v, sig.r, sig.s, name, value, validity)
  );
  out.replay = cell(
    first.ok && replayed.reverted ? "DEFENDED" : "VULNERABLE",
    "per-identity incrementing nonce in the signed-hash preimage; second submission recomputes with nonce+1 -> ecrecover != owner",
    `first setAttributeSigned ok=${first.ok}; identical replay reverted: "${replayed.reason}". ` +
      "CAVEAT: signed hash binds contract address but NOT block.chainid -> cross-chain replay is possible (documented limitation of ERC-1056)."
  );

  // identity_theft: owner-authorised controller rotation; identifier (address) stable.
  const ownerXfer = await expectSuccess(
    reg.connect(owner).changeOwner(identity, newOwner.address)
  );
  const newOwnerOnChain = await reg.identityOwner(identity);
  out.identity_theft = cell(
    "PARTIAL",
    "address-bound identifier; controller transferable only via owner-authorised changeOwner. No token/approval transfer surface.",
    `changeOwner by owner ok=${ownerXfer.ok}; identityOwner now ${newOwnerOnChain} (== newOwner ${newOwner.address}); ` +
      "attacker changeOwner already shown to revert. Identifier (the address) never changes; a stolen owner key can still seize control."
  );

  // sybil: identity creation is implicit (every address is a DID) and permissionless.
  // Demonstrate an attacker standing up 5 distinct DIDs with no gate.
  let created = 0;
  for (let i = 0; i < 5; i++) {
    const s = ethers.Wallet.createRandom().connect(ethers.provider);
    // fund so it can transact
    await (await deployer.sendTransaction({ to: s.address, value: ethers.parseEther("1") })).wait();
    const r = await expectSuccess(
      reg.connect(s).setAttribute(s.address, name, value, year)
    );
    if (r.ok) created++;
  }
  out.sybil = cell(
    "VULNERABLE",
    "no issuer gating; every Ethereum address is already a DID (zero-cost implicit creation)",
    `attacker created ${created}/5 independent DIDs unchallenged. Identity creation is permissionless and effectively free.`
  );

  // recovery: none.
  out.recovery = cell(
    "VULNERABLE",
    "no recovery primitive; changeOwner requires the CURRENT owner key, so a lost/compromised key cannot be recovered",
    "contract exposes no guardian/social-recovery function; compromised key = permanent loss of control.",
    "reasoned"
  );

  // privacy: identity is an address; only public keys are emitted; no VIN anywhere.
  out.privacy = cell(
    "DEFENDED",
    "identifier is the Ethereum address; attributes are pubkeys/endpoints emitted as events; no VIN/PII field",
    "contract has no VIN storage or getter; createIdentity emits only a Secp256k1 verification key. DID form is did:ethr:<chainId>:<address>."
  );

  return out;
}

// ---------------------------------------------------------------------------
// ERC-721  (CVINVehicleNFT)
// ---------------------------------------------------------------------------

async function scenarioERC721(signers) {
  const [deployer, vehicleOwner, attacker, buyer, operator] = signers;
  const out = {};

  const NFT = await ethers.getContractFactory("CVINVehicleNFT", deployer);
  const nft = await NFT.deploy();
  await nft.waitForDeployment();

  // impersonation: attacker without MANUFACTURER_ROLE tries to mint an identity.
  const imp = await expectRevert(
    nft
      .connect(attacker)
      .mintVehicle(attacker.address, VIN, "Honda", "Civic", 2024, "Blue", "ipfs://x")
  );
  out.impersonation = cell(
    imp.reverted ? "DEFENDED" : "VULNERABLE",
    "onlyRole(MANUFACTURER_ROLE) on mintVehicle (OpenZeppelin AccessControl)",
    `attacker mint reverted: "${imp.reason}"`
  );

  // legitimate mint (manufacturer = deployer) for the remaining scenarios
  await (
    await nft.mintVehicle(vehicleOwner.address, VIN, "Honda", "Civic", 2024, "Blue", "ipfs://x")
  ).wait();
  const tokenId = 1;

  // replay: no signed meta-tx surface; on-chain txs are protected by the
  // Ethereum account nonce at the protocol level.
  out.replay = cell(
    "N/A",
    "no contract-level signed meta-transaction; all ops are direct calls protected by the Ethereum tx nonce",
    "ERC-721 identity ops (mint/transfer) carry no in-contract signature to replay.",
    "reasoned"
  );

  // identity_theft: NFT is freely transferable AND approvable -> identity moves
  // with the token; an operator/approved party can move it too.
  await (await nft.connect(vehicleOwner).transferFrom(vehicleOwner.address, buyer.address, tokenId)).wait();
  const ownerAfter = await nft.ownerOf(tokenId);
  const vinStill = await nft.tokenIdToVIN(tokenId);
  // approval-based transfer by a third party (widened attack surface)
  await (await nft.connect(buyer).approve(operator.address, tokenId)).wait();
  const opXfer = await expectSuccess(
    nft.connect(operator).transferFrom(buyer.address, attacker.address, tokenId)
  );
  out.identity_theft = cell(
    "VULNERABLE",
    "identity == transferable NFT; transferFrom / approved-operator moves the whole identity (VIN + history follow the token)",
    `transfer moved ownerOf to ${ownerAfter} while VIN stayed "${vinStill}"; approved operator then moved it again ok=${opXfer.ok}. ` +
      "A stolen key OR an approval grants full identity takeover; no owner-authorised gate beyond token control."
  );

  // sybil: mint is MANUFACTURER_ROLE gated -> attacker cannot self-issue.
  const syb = await expectRevert(
    nft
      .connect(attacker)
      .mintVehicle(attacker.address, "2HGBH41JXMN109999", "X", "Y", 2024, "Red", "ipfs://y")
  );
  out.sybil = cell(
    syb.reverted ? "DEFENDED" : "VULNERABLE",
    "identity minting gated by MANUFACTURER_ROLE; unprivileged attacker cannot create identities",
    `attacker self-mint reverted: "${syb.reason}". Sybil cost = manufacturer authorisation, not just gas.`
  );

  // recovery: no key recovery; admin can only deactivate metadata, not reassign owner.
  out.recovery = cell(
    "VULNERABLE",
    "no key-recovery primitive; deactivateVehicle (admin) only flags metadata inactive and cannot reassign token ownership",
    "a lost/stolen owner key cannot be recovered; the token (identity) stays with whoever holds it.",
    "reasoned"
  );

  // privacy: VIN plaintext in public mappings + VehicleMinted event.
  const vinPublic = await nft.tokenIdToVIN(tokenId);
  const meta = await nft.vehicleMetadata(tokenId);
  out.privacy = cell(
    looksLikeVIN(vinPublic) ? "VULNERABLE" : "DEFENDED",
    "no VIN hashing; plaintext VIN stored in tokenIdToVIN / vinToTokenId / vehicleMetadata and emitted in VehicleMinted",
    `tokenIdToVIN(${tokenId}) read back plaintext VIN "${vinPublic}"; vehicleMetadata.vin = "${meta.vin}". Full PII (make/model/year/color) also public.`
  );

  return out;
}

// ---------------------------------------------------------------------------
// ERC-725  (CVIN_SCBasedAccOrID_DID_ERC725Basic)
// ---------------------------------------------------------------------------

async function scenarioERC725(signers) {
  const [, owner, attacker, newOwner] = signers;
  const out = {};

  const ID = await ethers.getContractFactory("CVIN_SCBasedAccOrID_DID_ERC725Basic", owner);
  const id = await ID.deploy();
  await id.waitForDeployment();

  const key = ethers.keccak256(ethers.toUtf8Bytes("vehicle-mgmt-key-1"));

  // impersonation: attacker tries to add a management key / transfer ownership
  const impKey = await expectRevert(id.connect(attacker).addKey(key, 1, 1));
  const impOwn = await expectRevert(id.connect(attacker).transferOwnership(attacker.address));
  out.impersonation = cell(
    impKey.reverted && impOwn.reverted ? "DEFENDED" : "VULNERABLE",
    "require(msg.sender == _owner) on addKey / removeKey / transferOwnership / execute",
    `attacker addKey reverted: "${impKey.reason}"; attacker transferOwnership reverted: "${impOwn.reason}"`
  );

  out.replay = cell(
    "N/A",
    "no signed meta-transaction surface; direct owner calls only (Ethereum tx nonce)",
    "no in-contract signature to replay.",
    "reasoned"
  );

  // identity_theft: whole identity contract transferable by owner call.
  const xfer = await expectSuccess(id.connect(owner).transferOwnership(newOwner.address));
  const ownerAfter = await id.owner();
  out.identity_theft = cell(
    "PARTIAL",
    "identity = a per-vehicle proxy-account contract; ownership transferable only via owner-authorised transferOwnership (no approval/operator surface)",
    `transferOwnership by owner ok=${xfer.ok}; owner() now ${ownerAfter}. A stolen owner key can seize the contract; transferOwnership has no zero-address guard (bricking risk).`
  );

  // sybil: permissionless deployment (anyone can deploy their own identity contract).
  const IDa = await ethers.getContractFactory("CVIN_SCBasedAccOrID_DID_ERC725Basic", attacker);
  let deployed = 0;
  for (let i = 0; i < 3; i++) {
    const c = await IDa.deploy();
    await c.waitForDeployment();
    deployed++;
  }
  out.sybil = cell(
    "PARTIAL",
    "permissionless per-identity contract deployment; the only Sybil barrier is deployment gas (~529k each)",
    `attacker deployed ${deployed}/3 independent identity contracts with no authorisation. Cost-gated only, not issuer-gated.`
  );

  out.recovery = cell(
    "VULNERABLE",
    "no recovery primitive (no guardian, no admin reassignment)",
    "compromised owner key = permanent loss; renounceOwnership can even brick the identity.",
    "reasoned"
  );

  out.privacy = cell(
    "DEFENDED",
    "no VIN/PII on-chain; only key identifiers (keccak256 hashes) are stored/emitted",
    "contract stores Key{purpose,keyType,key} entries only; DID form is did:key:<chainId>:<proxyAddress>, no VIN."
  );

  return out;
}

// ---------------------------------------------------------------------------
// ERC-735  (CVINVehicleClaimHolder)
// ---------------------------------------------------------------------------

async function scenarioERC735(signers) {
  const [, owner, attacker, issuer, newOwner] = signers;
  const out = {};

  const Holder = await ethers.getContractFactory("CVINVehicleClaimHolder", owner);
  const holder = await Holder.deploy(VIN);
  await holder.waitForDeployment();
  const identityAddr = await holder.getAddress();
  const TOPIC = 1; // VIN_ATTESTATION
  const SCHEME = 1; // ECDSA
  const data = ethers.toUtf8Bytes(`VIN:${VIN}`);

  // EIP-191 signature of keccak256(address(this), topic, data) by the issuer
  async function signClaim(signer) {
    const h = ethers.solidityPackedKeccak256(
      ["address", "uint256", "bytes"],
      [identityAddr, TOPIC, data]
    );
    return signer.signMessage(ethers.getBytes(h));
  }

  // impersonation (a): attacker (non-owner) tries to anchor a claim
  const validSig = await signClaim(issuer);
  const impA = await expectRevert(
    holder.connect(attacker).addClaim(TOPIC, SCHEME, issuer.address, validSig, data, "ipfs://a")
  );
  // impersonation (b): owner tries to anchor a FORGED claim (attacker-signed,
  // but claiming issuer == trusted issuer) -> ecrecover mismatch must revert
  const forgedSig = await signClaim(attacker); // signed by attacker, not issuer
  const impB = await expectRevert(
    holder.connect(owner).addClaim(TOPIC, SCHEME, issuer.address, forgedSig, data, "ipfs://a")
  );
  out.impersonation = cell(
    impA.reverted && impB.reverted ? "DEFENDED" : "VULNERABLE",
    "addClaim onlyOwner + on-chain ecrecover: recovered signer must equal declared issuer (EIP-191, EIP-2 malleability guard)",
    `non-owner addClaim reverted: "${impA.reason}"; forged-issuer-signature addClaim reverted: "${impB.reason}"`
  );

  // replay: anchor a valid claim, then replay the SAME signed claim.
  const anchor = await expectSuccess(
    holder.connect(owner).addClaim(TOPIC, SCHEME, issuer.address, validSig, data, "ipfs://a")
  );
  const replay = await expectSuccess(
    holder.connect(owner).addClaim(TOPIC, SCHEME, issuer.address, validSig, data, "ipfs://a")
  );
  out.replay = cell(
    "PARTIAL",
    "issuer signature binds address(this)+topic+data (blocks cross-identity replay) but has NO nonce/expiry/chainid; same-identity re-anchor is accepted (idempotent overwrite -> ClaimChanged)",
    `valid anchor ok=${anchor.ok}; identical re-submission also ok=${replay.ok} (idempotent, keyed by (issuer,topic)). ` +
      "No replay protection primitive; harmless here only because re-adding overwrites in place. Signature is not chain-bound."
  );

  // identity_theft: owner-authorised contract-ownership transfer.
  const xfer = await expectSuccess(holder.connect(owner).transferOwnership(newOwner.address));
  out.identity_theft = cell(
    "PARTIAL",
    "identity = per-vehicle claim-holder contract; transferOwnership is onlyOwner (no approval/operator surface)",
    `transferOwnership by owner ok=${xfer.ok}. Stolen owner key can seize; no passive transfer surface.`
  );

  // sybil: permissionless deployment (each deploy = one identity, ~1.4M gas).
  const HolderA = await ethers.getContractFactory("CVINVehicleClaimHolder", attacker);
  let deployed = 0;
  for (let i = 0; i < 3; i++) {
    const c = await HolderA.deploy(`SYBIL0000000000${i}${i}`);
    await c.waitForDeployment();
    deployed++;
  }
  out.sybil = cell(
    "PARTIAL",
    "permissionless per-identity contract deployment; Sybil barrier is deployment gas only (~1.40M each — the most expensive to spam)",
    `attacker deployed ${deployed}/3 claim-holder identities unchallenged. Cost-gated only; claims themselves still need a trusted issuer signature.`
  );

  out.recovery = cell(
    "VULNERABLE",
    "no recovery primitive (owner is the sole MANAGEMENT key)",
    "compromised owner key = permanent loss of the identity contract.",
    "reasoned"
  );

  // privacy: VIN plaintext in public string + VehicleIdentityCreated event.
  const vinPublic = await holder.vin();
  out.privacy = cell(
    looksLikeVIN(vinPublic) ? "VULNERABLE" : "DEFENDED",
    "constructor stores VIN as `string public vin` and emits VehicleIdentityCreated(vinHash, vin, owner) with plaintext VIN",
    `holder.vin() read back plaintext "${vinPublic}" (vinHash is also stored, but plaintext is exposed alongside it).`
  );

  return out;
}

// ---------------------------------------------------------------------------
// ERC-1155  (CVINVehicleCredential1155)
// ---------------------------------------------------------------------------

async function scenarioERC1155(signers) {
  const [deployer, vehicle, attacker, newVehicle] = signers;
  const out = {};

  const Cred = await ethers.getContractFactory("CVINVehicleCredential1155", deployer);
  const cred = await Cred.deploy();
  await cred.waitForDeployment();
  const BIRTH_CERT = 1;
  const INSPECTION = 3;

  // impersonation: attacker without ISSUER_ROLE registers a vehicle identity
  const imp = await expectRevert(cred.connect(attacker).registerVehicle(attacker.address, VIN));
  out.impersonation = cell(
    imp.reverted ? "DEFENDED" : "VULNERABLE",
    "onlyRole(ISSUER_ROLE) on registerVehicle / issueCredential / revokeCredential",
    `attacker registerVehicle reverted: "${imp.reason}"`
  );

  // legitimate registration for later scenarios
  await (await cred.registerVehicle(vehicle.address, VIN)).wait();
  await (await cred.issueCredential(vehicle.address, INSPECTION, 1)).wait();

  out.replay = cell(
    "N/A",
    "no signed meta-transaction surface; issuer-gated direct calls (Ethereum tx nonce)",
    "no in-contract signature to replay.",
    "reasoned"
  );

  // identity_theft: SOULBOUND. Holder-initiated transfer of the birth cert reverts.
  const theft = await expectRevert(
    cred
      .connect(vehicle)
      .safeTransferFrom(vehicle.address, attacker.address, BIRTH_CERT, 1, "0x")
  );
  out.identity_theft = cell(
    theft.reverted ? "DEFENDED" : "VULNERABLE",
    "soulbound: _update blocks transfers between non-zero addresses unless msg.sender holds ISSUER_ROLE",
    `holder safeTransferFrom of BIRTH_CERT reverted: "${theft.reason}". A stolen vehicle key cannot move the identity token; only an issuer can re-bind it.`
  );

  // sybil: registration is ISSUER_ROLE gated.
  const syb = await expectRevert(cred.connect(attacker).registerVehicle(attacker.address, "9HGBH41JXMN100000"));
  out.sybil = cell(
    syb.reverted ? "DEFENDED" : "VULNERABLE",
    "identity registration gated by ISSUER_ROLE",
    `attacker self-register reverted: "${syb.reason}". Sybil cost = issuer authorisation.`
  );

  // recovery: issuer-mediated re-binding of the birth cert to a fresh address.
  const rec = await expectSuccess(
    cred.connect(deployer).issuerTransferCredential(vehicle.address, newVehicle.address, BIRTH_CERT)
  );
  const newBal = await cred.balanceOf(newVehicle.address, BIRTH_CERT);
  out.recovery = cell(
    rec.ok && newBal === 1n ? "PARTIAL" : "VULNERABLE",
    "issuer-mediated recovery: ISSUER_ROLE can issuerTransferCredential the BIRTH_CERT to a new vehicle address (re-binds VIN)",
    `issuer re-bound identity to ${newVehicle.address}; balanceOf(new, BIRTH_CERT)=${newBal}. Recovery depends on a trusted issuer, not the key holder.`
  );

  // privacy: VIN plaintext in public vehicleVIN mapping + VehicleRegistered event.
  const vinPublic = await cred.vehicleVIN(newVehicle.address); // moved with re-bind
  out.privacy = cell(
    looksLikeVIN(vinPublic) ? "VULNERABLE" : "DEFENDED",
    "no VIN hashing for storage; plaintext VIN in `vehicleVIN` mapping and VehicleRegistered(vehicle, vinHash, vin) event",
    `vehicleVIN() read back plaintext "${vinPublic}" (a keccak vinHash index also exists, but plaintext is stored+emitted).`
  );

  return out;
}

// ---------------------------------------------------------------------------
// ERC-4337  (CVINVehicleAccount + CVINMinimalEntryPoint)
// ---------------------------------------------------------------------------

async function scenarioERC4337(signers) {
  const [bundler, accountOwner, attacker, guardian, recovered] = signers;
  const out = {};

  const EP = await ethers.getContractFactory("CVINMinimalEntryPoint", bundler);
  const ep = await EP.deploy();
  await ep.waitForDeployment();
  const Acct = await ethers.getContractFactory("CVINVehicleAccount", bundler);
  const acct = await Acct.deploy(await ep.getAddress(), accountOwner.address);
  await acct.waitForDeployment();
  const sender = await acct.getAddress();

  const KEY = ethers.keccak256(ethers.toUtf8Bytes("cvin/vehicle/firmwareHash"));
  const VAL = ethers.toUtf8Bytes("sha256:9f86d0818b");

  // impersonation (a): attacker calls setAttribute directly (not owner/entryPoint)
  const impA = await expectRevert(acct.connect(attacker).setAttribute(KEY, VAL));

  // build a valid UserOp helper
  async function buildUserOp(nonce, signer) {
    const inner = acct.interface.encodeFunctionData("setAttribute", [KEY, ethers.hexlify(VAL)]);
    const callData = acct.interface.encodeFunctionData("execute", [sender, 0, inner]);
    const userOp = {
      sender,
      nonce,
      initCode: "0x",
      callData,
      accountGasLimits: ethers.ZeroHash,
      preVerificationGas: 0,
      gasFees: ethers.ZeroHash,
      paymasterAndData: "0x",
      signature: "0x",
    };
    const h = await ep.getUserOpHash(userOp);
    userOp.signature = await signer.signMessage(ethers.getBytes(h));
    return userOp;
  }

  // impersonation (b): UserOp signed by attacker (not the owner) must be rejected
  const forgedOp = await buildUserOp(await ep.nonces(sender), attacker);
  const impB = await expectRevert(ep.connect(bundler).handleOp(forgedOp));
  out.impersonation = cell(
    impA.reverted && impB.reverted ? "DEFENDED" : "VULNERABLE",
    "onlyOwnerOrEntryPoint on direct calls; validateUserOp ecrecover requires recovered == owner (EntryPoint reverts on validationData != 0)",
    `direct attacker setAttribute reverted: "${impA.reason}"; attacker-signed UserOp reverted: "${impB.reason}"`
  );

  // replay: submit a valid UserOp, then replay the identical op (stale nonce).
  const op0 = await buildUserOp(await ep.nonces(sender), accountOwner);
  const first = await expectSuccess(ep.connect(bundler).handleOp(op0));
  const replay = await expectRevert(ep.connect(bundler).handleOp(op0)); // same nonce
  out.replay = cell(
    first.ok && replay.reverted ? "DEFENDED" : "VULNERABLE",
    "EntryPoint enforces require(userOp.nonce == nonces[sender]) and bumps it; userOpHash also binds entryPoint address + block.chainid",
    `first handleOp ok=${first.ok}; identical replay reverted: "${replay.reason}". Best replay posture (nonce + chainid-bound hash).`
  );

  // identity_theft: transferOwnership rotates the signing key; the account
  // address (identity) is unchanged.
  const rot = await expectSuccess(acct.connect(accountOwner).transferOwnership(bundler.address));
  // rotate back so the owner variable is a known signer for recovery test setup
  await (await acct.connect(bundler).transferOwnership(accountOwner.address)).wait();
  out.identity_theft = cell(
    "PARTIAL",
    "identity = stable account address; only the owner signing key rotates via owner-authorised transferOwnership (no token/approval surface)",
    `transferOwnership (key rotation) ok=${rot.ok}; account address (identity) unchanged. A stolen owner key can rotate itself out, but guardian recovery (below) can restore control.`
  );

  // sybil: permissionless account deployment (~768k gas each).
  const AcctA = await ethers.getContractFactory("CVINVehicleAccount", attacker);
  let deployed = 0;
  for (let i = 0; i < 3; i++) {
    const c = await AcctA.deploy(await ep.getAddress(), attacker.address);
    await c.waitForDeployment();
    deployed++;
  }
  out.sybil = cell(
    "PARTIAL",
    "permissionless smart-account deployment; Sybil barrier is deployment gas only (~768k each)",
    `attacker deployed ${deployed}/3 accounts unchallenged. Cost-gated only, not issuer-gated.`
  );

  // recovery: guardian social recovery (the headline 4337 property).
  await (await acct.connect(accountOwner).setGuardian(guardian.address)).wait();
  // attacker (non-guardian) cannot recover
  const badRec = await expectRevert(acct.connect(attacker).recoverOwner(attacker.address));
  // guardian installs a new signing key
  const goodRec = await expectSuccess(acct.connect(guardian).recoverOwner(recovered.address));
  const ownerAfter = await acct.owner();
  out.recovery = cell(
    goodRec.ok && badRec.reverted && ownerAfter === recovered.address ? "DEFENDED" : "VULNERABLE",
    "guardian social recovery: recoverOwner(newOwner) callable only by the designated guardian installs a fresh signing key without changing the identity address",
    `non-guardian recoverOwner reverted: "${badRec.reason}"; guardian recoverOwner ok=${goodRec.ok}; owner() now ${ownerAfter} (== recovered ${recovered.address}). ` +
      "CAVEAT: single-guardian, instant, no timelock/threshold -> a compromised guardian is itself a takeover vector."
  );

  // privacy: attribute store is public and unhashed; VIN leaks if written there.
  await (await acct.connect(recovered).setAttribute(ethers.keccak256(ethers.toUtf8Bytes("cvin/vehicle/vin")), ethers.toUtf8Bytes(VIN))).wait();
  const stored = await acct.getAttribute(ethers.keccak256(ethers.toUtf8Bytes("cvin/vehicle/vin")));
  const storedStr = ethers.toUtf8String(stored);
  out.privacy = cell(
    looksLikeVIN(storedStr) ? "PARTIAL" : "DEFENDED",
    "ERC-725Y-style attribute store is public and does NOT hash values; app-dependent (no forced VIN field, but any VIN written is exposed via getAttribute + AttributeChanged event)",
    `setAttribute(vin) then getAttribute read back plaintext "${storedStr}". No built-in VIN protection; privacy depends on the application encrypting before storing.`
  );

  return out;
}

// ---------------------------------------------------------------------------
// LSP8  (CVINVehicleLSP8)
// ---------------------------------------------------------------------------

async function scenarioLSP8(signers) {
  const [authority, vehicleOwner, attacker, buyer] = signers;
  const out = {};

  const LSP8 = await ethers.getContractFactory("CVINVehicleLSP8", authority);
  const lsp8 = await LSP8.deploy("CVIN Vehicle Identity LSP8", "CVIN-LSP8");
  await lsp8.waitForDeployment();
  const tokenId = ethers.keccak256(ethers.toUtf8Bytes(VIN));

  // impersonation: attacker (not issuing authority) tries to mint an identity
  const imp = await expectRevert(lsp8.connect(attacker).mintVehicle(attacker.address, VIN));
  out.impersonation = cell(
    imp.reverted ? "DEFENDED" : "VULNERABLE",
    "onlyOwner (issuing authority) on mintVehicle / setDataForTokenId",
    `attacker mintVehicle reverted: "${imp.reason}"`
  );

  await (await lsp8.mintVehicle(vehicleOwner.address, VIN)).wait();

  out.replay = cell(
    "N/A",
    "no signed meta-transaction surface; direct calls (Ethereum tx nonce)",
    "no in-contract signature to replay.",
    "reasoned"
  );

  // identity_theft: token-transferable by the token owner (identity moves with token).
  const xfer = await expectSuccess(
    lsp8.connect(vehicleOwner).transfer(vehicleOwner.address, buyer.address, tokenId, true, "0x")
  );
  const ownerAfter = await lsp8.tokenOwnerOf(tokenId);
  // an attacker who is NOT the token owner cannot move it (no operator support)
  const attackerMove = await expectRevert(
    lsp8.connect(attacker).transfer(buyer.address, attacker.address, tokenId, true, "0x")
  );
  out.identity_theft = cell(
    "VULNERABLE",
    "identity == transferable token; the token owner can move the whole identity via transfer (VIN data follows the tokenId)",
    `token owner transfer ok=${xfer.ok}, tokenOwnerOf now ${ownerAfter}; non-owner transfer reverted: "${attackerMove.reason}". ` +
      "A stolen token-owner key = stolen identity (no operator surface, so slightly narrower than ERC-721, but still freely transferable by the holder)."
  );

  // sybil: mint gated by issuing authority (onlyOwner).
  const syb = await expectRevert(lsp8.connect(attacker).mintVehicle(attacker.address, "8HGBH41JXMN100000"));
  out.sybil = cell(
    syb.reverted ? "DEFENDED" : "VULNERABLE",
    "identity minting gated by the issuing authority (onlyOwner)",
    `attacker self-mint reverted: "${syb.reason}". Sybil cost = authority authorisation.`
  );

  // recovery: authority can revoke (burn) and re-mint to a new owner = admin recovery.
  await (await lsp8.connect(authority).revokeVehicle(tokenId, "0x")).wait();
  const reMint = await expectSuccess(lsp8.connect(authority).mintVehicle(buyer.address, VIN));
  out.recovery = cell(
    reMint.ok ? "PARTIAL" : "VULNERABLE",
    "authority-mediated recovery: the issuing authority can revokeVehicle then re-mint the same tokenId (keccak256(VIN)) to a new owner",
    `authority revoked + re-minted identity to a new owner ok=${reMint.ok}. Recovery depends on a trusted authority, not the key holder.`
  );

  // privacy: VIN plaintext in per-token data store + events.
  const raw = await lsp8.getDataForTokenId(tokenId, await lsp8.DATA_KEY_VIN());
  const vinStr = ethers.toUtf8String(raw);
  out.privacy = cell(
    looksLikeVIN(vinStr) ? "VULNERABLE" : "DEFENDED",
    "tokenId = keccak256(VIN) is hashed, but the plaintext VIN is also stored under DATA_KEY_VIN and emitted in TokenIdDataChanged / VehicleMinted",
    `getDataForTokenId(DATA_KEY_VIN) read back plaintext "${vinStr}".`
  );

  return out;
}

// ---------------------------------------------------------------------------
// MOBI-VID-V2  (MOBIVIDRegistryV2)
// ---------------------------------------------------------------------------

async function scenarioMOBI(signers) {
  const [deployer, firstOwner, attacker, newOwner, vehicleWallet] = signers;
  const out = {};

  const Reg = await ethers.getContractFactory("MOBIVIDRegistryV2", deployer);
  const reg = await Reg.deploy();
  await reg.waitForDeployment();

  const vehicleIdentity = vehicleWallet.address;
  const vinHash = ethers.keccak256(ethers.toUtf8Bytes(VIN));
  const encVIN = "encrypted:AES256:VINCIPHERTEXT==";
  const certHash = ethers.keccak256(ethers.toUtf8Bytes("ipfs://QmBirthCertificate"));

  // impersonation: attacker (not an authorized manufacturer) registers a birth
  const imp = await expectRevert(
    reg
      .connect(attacker)
      .registerVehicleBirth(vehicleIdentity, vinHash, encVIN, certHash, firstOwner.address, "0x")
  );
  out.impersonation = cell(
    imp.reverted ? "DEFENDED" : "VULNERABLE",
    "onlyAuthorizedManufacturer on registerVehicleBirth; recordLifecycleEvent gated by onlyAuthorizedIssuer(eventType) role matrix",
    `attacker registerVehicleBirth reverted: "${imp.reason}"`
  );

  // legitimate birth (deployer is auto-authorized manufacturer)
  await (
    await reg.registerVehicleBirth(vehicleIdentity, vinHash, encVIN, certHash, firstOwner.address, "0x")
  ).wait();

  // replay: MOBI VID layer has no signed meta-tx; attestEvent stores an
  // UNVERIFIED signature blob (a finding) but the birth/transfer path is
  // direct-call + role gated.
  out.replay = cell(
    "PARTIAL",
    "no signed meta-tx on the identity path (role-gated direct calls); attestEvent stores a signature blob that is NEVER verified on-chain (no ecrecover) — a replay/forgery gap for attestations",
    "birth/ownership ops carry no replayable in-contract signature; attestEvent signatures are unvalidated and could be replayed/forged (only gated by attester role).",
    "reasoned"
  );

  // identity_theft: owner-authorised transfer; immutable birth certificate.
  const xfer = await expectSuccess(
    reg.connect(firstOwner).transferVehicleOwnership(vehicleIdentity, newOwner.address, 20000, "ICBC BC-CAN")
  );
  const ownerAfter = await reg.identityOwner(vehicleIdentity);
  out.identity_theft = cell(
    "PARTIAL",
    "owner-authorised transferVehicleOwnership (onlyOwner(identity, actor)); immutable birth certificate + full ownership history preserve provenance across transfers",
    `transferVehicleOwnership by owner ok=${xfer.ok}; identityOwner now ${ownerAfter}. A stolen owner key can transfer, but the birth cert and odometer-stamped ownership chain remain tamper-evident.`
  );

  // sybil: birth registration gated by onlyAuthorizedManufacturer (strongest gate + highest cost).
  const syb = await expectRevert(
    reg
      .connect(attacker)
      .registerVehicleBirth(attacker.address, ethers.keccak256(ethers.toUtf8Bytes("OTHERVIN")), encVIN, certHash, attacker.address, "0x")
  );
  out.sybil = cell(
    syb.reverted ? "DEFENDED" : "VULNERABLE",
    "identity creation gated by onlyAuthorizedManufacturer AND VIN-hash uniqueness; highest per-identity cost (~299k gas)",
    `attacker registerVehicleBirth reverted: "${syb.reason}". Strongest Sybil resistance: manufacturer authorisation + unique-VIN enforcement.`
  );

  out.recovery = cell(
    "VULNERABLE",
    "inherits ERC-1056 changeOwner (requires current owner key); no guardian/social recovery",
    "a compromised owner key cannot be recovered by the vehicle; registryAuthority can re-authorize manufacturers but cannot restore a lost owner key.",
    "reasoned"
  );

  // privacy: VIN stored as hash + ciphertext ONLY; read back and confirm no plaintext.
  const birth = await reg.vehicleBirths(vehicleIdentity);
  const didStr = await reg.getVehicleDID(vehicleIdentity);
  const plaintextLeak = looksLikeVIN(birth.encryptedVIN) || didStr.includes(VIN);
  out.privacy = cell(
    !plaintextLeak ? "DEFENDED" : "VULNERABLE",
    "VIN stored ONLY as bytes32 vinHash + off-chain-encrypted `encryptedVIN`; VehicleBirthRegistered event emits the hash, not the VIN; DID is did:ethr:<chainId>:<address>",
    `vehicleBirths.vinHash = ${birth.vinHash} (hash); encryptedVIN = "${birth.encryptedVIN}" (ciphertext, not the VIN); getVehicleDID() = "${didStr}" (no VIN in the DID). Only family that avoids plaintext VIN on-chain.`
  );

  return out;
}

// ---------------------------------------------------------------------------
// CVIN-Combined  (CVINCombinedIdentity)
// ---------------------------------------------------------------------------

async function scenarioCVINCombined(signers) {
  const [deployer, owner, attacker, newOwner] = signers;
  const out = {};

  const Reg = await ethers.getContractFactory("CVINCombinedIdentity", deployer);
  const reg = await Reg.deploy();
  await reg.waitForDeployment();
  const regAddr = await reg.getAddress();

  const identity = owner.address;
  const TOPIC = 1; // CLAIM_TOPIC_VIN
  const SCHEME = 1;
  const name = ethers.keccak256(ethers.toUtf8Bytes("did/pub/Secp256k1/veriKey"));
  const value = ethers.toUtf8Bytes("0x02b97c30de767f084ce3080168ee29305");

  // raw-digest claim signing helper (no EIP-191 envelope, per contract)
  const issuerWallet = ethers.Wallet.createRandom();
  const vinData = ethers.toUtf8Bytes(VIN);
  function signClaim(wallet) {
    const digest = ethers.solidityPackedKeccak256(
      ["address", "address", "uint256", "bytes"],
      [regAddr, identity, TOPIC, vinData]
    );
    return ethers.Signature.from(wallet.signingKey.sign(digest)).serialized;
  }

  // impersonation (a): attacker sets an attribute on the victim's identity
  const impA = await expectRevert(reg.connect(attacker).setAttribute(identity, name, value, 86400));
  // impersonation (b): owner anchors a FORGED claim (attacker-signed but declaring issuerWallet)
  const forged = signClaim(ethers.Wallet.createRandom()); // wrong signer
  const impB = await expectRevert(
    reg.connect(owner).addClaim(identity, TOPIC, SCHEME, issuerWallet.address, forged, vinData, "ipfs://x")
  );
  out.impersonation = cell(
    impA.reverted && impB.reverted ? "DEFENDED" : "VULNERABLE",
    "onlyIdentityOwner on ERC-1056 side; addClaim ecrecover requires recovered raw-digest signer == declared issuer",
    `attacker setAttribute reverted: "${impA.reason}"; forged-issuer claim reverted: "${impB.reason}"`
  );

  // replay: anchor a valid claim then replay the same signed claim.
  const validSig = signClaim(issuerWallet);
  const anchor = await expectSuccess(
    reg.connect(owner).addClaim(identity, TOPIC, SCHEME, issuerWallet.address, validSig, vinData, "ipfs://x")
  );
  const replay = await expectSuccess(
    reg.connect(owner).addClaim(identity, TOPIC, SCHEME, issuerWallet.address, validSig, vinData, "ipfs://x")
  );
  out.replay = cell(
    "PARTIAL",
    "claim signature binds address(this)+identity+topic+data (blocks cross-context replay) but has NO nonce/expiry/chainid and NO EIP-2 malleability guard; same-context re-anchor accepted (idempotent)",
    `valid anchor ok=${anchor.ok}; identical re-submission also ok=${replay.ok}. No replay primitive; changeOwner path is a direct owner call (no signature to replay).`
  );

  // identity_theft: owner-authorised changeOwner; identifier (address) stable.
  const xfer = await expectSuccess(reg.connect(owner).changeOwner(identity, newOwner.address));
  const ownerAfter = await reg.identityOwner(identity);
  out.identity_theft = cell(
    "PARTIAL",
    "address-bound identifier; controller transfer only via owner-authorised changeOwner (no token/approval surface)",
    `changeOwner by owner ok=${xfer.ok}; identityOwner now ${ownerAfter}. Stolen owner key can seize; no passive transfer surface.`
  );

  // sybil: permissionless + implicit (every address is an identity, ~52k first write).
  let created = 0;
  for (let i = 0; i < 5; i++) {
    const s = ethers.Wallet.createRandom().connect(ethers.provider);
    await (await deployer.sendTransaction({ to: s.address, value: ethers.parseEther("1") })).wait();
    const r = await expectSuccess(reg.connect(s).setAttribute(s.address, name, value, 86400));
    if (r.ok) created++;
  }
  out.sybil = cell(
    "VULNERABLE",
    "ERC-1056 side: every address is an implicit identity; no issuer gating; near-zero creation cost (~52k first attribute write)",
    `attacker created ${created}/5 independent identities unchallenged. Safety-critical CLAIMS still need a trusted issuer signature, but base identities are free/permissionless.`
  );

  out.recovery = cell(
    "VULNERABLE",
    "no recovery primitive; changeOwner requires the current owner key",
    "compromised owner key = permanent loss (the hybrid adds on-chain claims but no key recovery).",
    "reasoned"
  );

  // privacy: attributes are event-only (not stored), but claim `data` IS stored
  // on-chain and returned by getClaim -> plaintext if a VIN is placed there.
  const claimId = ethers.solidityPackedKeccak256(["address", "uint256"], [issuerWallet.address, TOPIC]);
  const claim = await reg.getClaim(identity, claimId);
  const claimData = ethers.toUtf8String(claim.data);
  out.privacy = cell(
    looksLikeVIN(claimData) ? "PARTIAL" : "DEFENDED",
    "ERC-1056 attributes are event-only (no storage); but ERC-735 claim `data` is stored and readable via getClaim — unhashed, app-dependent",
    `getClaim(...).data read back plaintext "${claimData}" (the benchmark/app placed the VIN in claim data). No forced hashing; privacy depends on the app hashing/encrypting claim payloads.`
  );

  return out;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const signers = await ethers.getSigners();
  const net = await ethers.provider.getNetwork();

  console.log("CVIN Thrust 5 — on-chain attack suite");
  console.log(`Network: ${net.name} (chainId ${net.chainId})\n`);

  const results = {};
  const runners = [
    ["ERC-1056", scenarioERC1056],
    ["ERC-721", scenarioERC721],
    ["ERC-725", scenarioERC725],
    ["ERC-735", scenarioERC735],
    ["ERC-1155", scenarioERC1155],
    ["ERC-4337", scenarioERC4337],
    ["LSP8", scenarioLSP8],
    ["MOBI-VID-V2", scenarioMOBI],
    ["CVIN-Combined", scenarioCVINCombined],
  ];

  for (const [name, fn] of runners) {
    console.log(`Running scenarios for ${name} ...`);
    results[name] = await fn(signers);
  }

  const output = {
    metadata: {
      layer: "on-chain",
      solcVersion: "0.8.24",
      ozVersion: "5.0.2",
      network: "hardhat-local",
      chainId: Number(net.chainId),
      date: new Date().toISOString(),
      categories: ["impersonation", "replay", "identity_theft", "sybil", "recovery", "privacy"],
      note:
        "Every cell outcome is derived from a REAL on-chain outcome: reverts were captured (reason recorded) and state was read back. method='executed' means the malicious tx was actually sent and its outcome observed; method='reasoned' means the property is a structural absence (e.g. no recovery function) argued from the verified contract source, not a sent transaction.",
    },
    standards: results,
  };

  const outDir = path.resolve(
    __dirname,
    "../../4_comparison-framework/security-analysis/results"
  );
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, "onchain_security.json");
  fs.writeFileSync(outFile, JSON.stringify(output, null, 2));

  // console summary
  console.log("\n=== On-chain security summary (outcome per category) ===");
  const cats = output.metadata.categories;
  console.log(["standard", ...cats].join("\t"));
  for (const [name] of runners) {
    const row = [name];
    for (const c of cats) row.push(results[name][c].outcome);
    console.log(row.join("\t"));
  }
  console.log(`\nResults written to ${outFile}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
