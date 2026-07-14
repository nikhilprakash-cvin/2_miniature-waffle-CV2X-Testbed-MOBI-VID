/**
 * securityScenarios.test.js
 *
 * Thrust 5 — Security analysis of the 9 CVIN vehicle-identity standards.
 *
 * EXECUTABLE attack scenarios. Each `it` deploys the real contract on the
 * in-process Hardhat network, stands up a legitimate victim identity, then
 * fires a concrete ADVERSARIAL transaction (wrong signer, forged signature,
 * replayed operation, ...). The suite asserts the attack is DEFENDED (reverts)
 * and, wherever meaningful, that the SAME operation performed by the authorized
 * party SUCCEEDS (control) and that protected state was not mutated.
 *
 * Every scenario records its REAL observed outcome into the shared harness; the
 * after() hook writes the per-standard security matrix to
 *   4_comparison-framework/security-analysis/results/security_matrix.json
 *
 * These are ordinary passing Mocha tests: the suite stays green precisely
 * because the contracts defend. A genuinely vulnerable contract would flip a
 * cell to "VULNERABLE" and fail its assertion — a real finding, never faked.
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");
const H = require("./attackHarness");

// STRIDE-flavoured threat class per attack (for the thesis matrix notes).
const THREAT = {
  unauthorizedIssuance: "Spoofing (forged identity issuance)",
  unauthorizedAttributeWrite: "Tampering (unauthorized state write)",
  unauthorizedDelegateOrClaim: "Spoofing / Elevation (forged delegate or claim)",
  unauthorizedRevocation: "Denial of Service (unauthorized revocation)",
  identityHijack: "Elevation of Privilege (identity/ownership takeover)",
  signatureReplay: "Replay (reuse of a consumed signed operation)",
};

const ONE_YEAR = 365 * 24 * 60 * 60;

// ===========================================================================
// ERC-1056 — EthereumDIDRegistry (shared registry, self-sovereign DIDs)
// ===========================================================================
describe("Security / ERC-1056 (EthereumDIDRegistry)", function () {
  const STD = "ERC-1056";
  let registry, victim, attacker, relayer;
  const name = ethers.encodeBytes32String("did/pub/Secp256k1/veriKey");
  const value = ethers.toUtf8Bytes("0x02b97c30de767f084ce3080168ee29305");

  beforeEach(async function () {
    const [deployer, v, a, r] = await ethers.getSigners();
    victim = v;
    attacker = a;
    relayer = r;
    const F = await ethers.getContractFactory(
      "contracts/ERC1056/EthereumDIDRegistry.sol:EthereumDIDRegistry",
      deployer
    );
    registry = await F.deploy();
    await registry.waitForDeployment();
    // Victim publishes a key on its own DID (legitimate identity in place).
    await (await registry.connect(victim).setAttribute(victim.address, name, value, ONE_YEAR)).wait();
  });

  it("unauthorizedIssuance: N/A (implicit permissionless DIDs)", function () {
    H.naCell(
      STD,
      "unauthorizedIssuance",
      THREAT.unauthorizedIssuance,
      "Self-sovereign: every address is its own did:ethr (implicit, zero-cost creation) — there is no gated issuance step to bypass. The equivalent protection (an attacker cannot publish onto a DID it does not control) is exercised by unauthorizedAttributeWrite."
    );
  });

  it("unauthorizedAttributeWrite: attacker cannot setAttribute on a victim DID", async function () {
    const r = await H.attempt(() =>
      registry.connect(attacker).setAttribute(victim.address, name, value, ONE_YEAR)
    );
    const ctl = await H.control(() =>
      registry.connect(victim).setAttribute(victim.address, name, value, ONE_YEAR)
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedAttributeWrite", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedAttributeWrite,
      attack: "attacker calls setAttribute(victim, ...) to publish/rotate a key on a DID it does not own",
      defense: "onlyOwner(identity, msg.sender): actor must equal identityOwner(identity)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedDelegateOrClaim: attacker cannot addDelegate on a victim DID", async function () {
    const dtype = ethers.encodeBytes32String("veriKey");
    const r = await H.attempt(() =>
      registry.connect(attacker).addDelegate(victim.address, dtype, attacker.address, ONE_YEAR)
    );
    const ctl = await H.control(() =>
      registry.connect(victim).addDelegate(victim.address, dtype, relayer.address, ONE_YEAR)
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    // Protected-state invariant: attacker's delegate was never installed.
    expect(await registry.validDelegate(victim.address, dtype, attacker.address)).to.equal(false);
    H.record(STD, "unauthorizedDelegateOrClaim", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedDelegateOrClaim,
      attack: "attacker calls addDelegate(victim, ...) installing itself as a signing delegate (ERC-1056 has no on-chain claim model)",
      defense: "onlyOwner(identity, msg.sender)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedRevocation: attacker cannot revokeAttribute on a victim DID", async function () {
    const r = await H.attempt(() =>
      registry.connect(attacker).revokeAttribute(victim.address, name, value)
    );
    const ctl = await H.control(() =>
      registry.connect(victim).revokeAttribute(victim.address, name, value)
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedRevocation", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedRevocation,
      attack: "attacker calls revokeAttribute(victim, ...) to disable a victim's published key",
      defense: "onlyOwner(identity, msg.sender)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("identityHijack: attacker cannot changeOwner of a victim DID", async function () {
    const r = await H.attempt(() =>
      registry.connect(attacker).changeOwner(victim.address, attacker.address)
    );
    expect(r.outcome).to.equal("DEFENDED");
    // Owner unchanged (still self-owned).
    expect(await registry.identityOwner(victim.address)).to.equal(victim.address);
    const ctl = await H.control(() =>
      registry.connect(victim).changeOwner(victim.address, relayer.address)
    );
    expect(ctl).to.equal("PASS");
    H.record(STD, "identityHijack", {
      outcome: r.outcome,
      threat: THREAT.identityHijack,
      attack: "attacker calls changeOwner(victim, attacker) to seize control of the DID",
      defense: "onlyOwner(identity, msg.sender)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("signatureReplay: a consumed setAttributeSigned meta-tx cannot be replayed", async function () {
    // Identity owner is a wallet whose private key we control (owns itself).
    const idWallet = new ethers.Wallet(
      "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
    );
    const identity = idWallet.address;
    const regAddr = await registry.getAddress();
    const nonce = await registry.nonce(identity);
    const hash = ethers.solidityPackedKeccak256(
      ["bytes1", "bytes1", "address", "uint256", "address", "string", "bytes32", "bytes", "uint256"],
      ["0x19", "0x00", regAddr, nonce, identity, "setAttribute", name, value, ONE_YEAR]
    );
    const sig = idWallet.signingKey.sign(hash);

    // Control: the relayer submits the owner-signed meta-tx once — it succeeds.
    const ctl = await H.control(() =>
      registry.connect(relayer).setAttributeSigned(identity, sig.v, sig.r, sig.s, name, value, ONE_YEAR)
    );
    expect(ctl).to.equal("PASS");
    expect(await registry.nonce(identity)).to.equal(nonce + 1n);

    // Attack: replay the identical signature — the on-chain nonce has advanced.
    const r = await H.attempt(() =>
      registry.connect(attacker).setAttributeSigned(identity, sig.v, sig.r, sig.s, name, value, ONE_YEAR)
    );
    expect(r.outcome).to.equal("DEFENDED");
    H.record(STD, "signatureReplay", {
      outcome: r.outcome,
      threat: THREAT.signatureReplay,
      attack: "replay a previously mined setAttributeSigned (identical v,r,s) to re-apply a signed key update",
      defense: "per-identity nonce folded into the signed hash; recovered signer != owner after nonce bump",
      revertReason: r.revertReason,
      control: ctl,
    });
  });
});

// ===========================================================================
// ERC-721 — CVINVehicleNFT (role-gated NFT identity)
// ===========================================================================
describe("Security / ERC-721 (CVINVehicleNFT)", function () {
  const STD = "ERC-721";
  let nft, deployer, victim, attacker, other;
  const VIN = "1HGBH41JXMN109186";
  let tokenId;

  beforeEach(async function () {
    const [d, v, a, o] = await ethers.getSigners();
    deployer = d;
    victim = v;
    attacker = a;
    other = o;
    const F = await ethers.getContractFactory("CVINVehicleNFT", deployer);
    nft = await F.deploy();
    await nft.waitForDeployment();
    await (await nft.mintVehicle(victim.address, VIN, "Honda", "Civic", 2024, "Blue", "ipfs://meta")).wait();
    tokenId = 1;
  });

  it("unauthorizedIssuance: attacker without MANUFACTURER_ROLE cannot mint", async function () {
    const r = await H.attempt(() =>
      nft.connect(attacker).mintVehicle(attacker.address, "2HGBH41JXMN109187", "Ford", "F150", 2024, "Red", "ipfs://x")
    );
    const ctl = await H.control(() =>
      nft.connect(deployer).mintVehicle(other.address, "3HGBH41JXMN109188", "Toyota", "Camry", 2024, "White", "ipfs://y")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedIssuance", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedIssuance,
      attack: "attacker (no MANUFACTURER_ROLE) calls mintVehicle to fabricate a vehicle identity",
      defense: "AccessControl onlyRole(MANUFACTURER_ROLE)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedAttributeWrite: attacker without SERVICE_CENTER_ROLE cannot addServiceRecord", async function () {
    const r = await H.attempt(() =>
      nft.connect(attacker).addServiceRecord(tokenId, "ipfs://malicious")
    );
    await (await nft.grantServiceCenterRole(other.address)).wait();
    const ctl = await H.control(() =>
      nft.connect(other).addServiceRecord(tokenId, "ipfs://legit")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedAttributeWrite", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedAttributeWrite,
      attack: "attacker (no SERVICE_CENTER_ROLE) appends a forged service record (closest attribute analogue in ERC-721)",
      defense: "AccessControl onlyRole(SERVICE_CENTER_ROLE)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedDelegateOrClaim: attacker cannot approve a token it does not own", async function () {
    const r = await H.attempt(() =>
      nft.connect(attacker).approve(attacker.address, tokenId)
    );
    const ctl = await H.control(() =>
      nft.connect(victim).approve(other.address, tokenId)
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedDelegateOrClaim", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedDelegateOrClaim,
      attack: "attacker calls approve(attacker, tokenId) to delegate transfer rights over a victim's vehicle (approve = ERC-721's only delegation primitive; no claim model)",
      defense: "ERC721: _msgSender() must be owner or operator (ERC721InvalidApprover)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedRevocation: attacker without DEFAULT_ADMIN_ROLE cannot deactivateVehicle", async function () {
    const r = await H.attempt(() => nft.connect(attacker).deactivateVehicle(tokenId));
    const ctl = await H.control(() => nft.connect(deployer).deactivateVehicle(tokenId));
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedRevocation", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedRevocation,
      attack: "attacker (no DEFAULT_ADMIN_ROLE) calls deactivateVehicle to disable a victim's identity",
      defense: "AccessControl onlyRole(DEFAULT_ADMIN_ROLE)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("identityHijack: attacker cannot transferFrom a victim's token", async function () {
    const r = await H.attempt(() =>
      nft.connect(attacker).transferFrom(victim.address, attacker.address, tokenId)
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(await nft.ownerOf(tokenId)).to.equal(victim.address);
    const ctl = await H.control(() =>
      nft.connect(victim).transferFrom(victim.address, other.address, tokenId)
    );
    expect(ctl).to.equal("PASS");
    H.record(STD, "identityHijack", {
      outcome: r.outcome,
      threat: THREAT.identityHijack,
      attack: "attacker calls transferFrom(victim, attacker, tokenId) to steal the vehicle NFT",
      defense: "ERC721: caller must be owner or approved (ERC721InsufficientApproval)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("signatureReplay: N/A (no signed/relayed operation)", function () {
    H.naCell(
      STD,
      "signatureReplay",
      THREAT.signatureReplay,
      "This ERC-721 implementation exposes no signed/relayed (meta-transaction) operation, so there is no consumed signature to replay."
    );
  });
});

// ===========================================================================
// ERC-725 — CVIN_SCBasedAccOrID_DID_ERC725Basic (per-identity key manager)
// ===========================================================================
describe("Security / ERC-725 (CVIN_SCBasedAccOrID_DID_ERC725Basic)", function () {
  const STD = "ERC-725";
  let id, victim, attacker, other;
  const mgmtKey = ethers.keccak256(ethers.toUtf8Bytes("mgmt-key-1"));
  const claimKey = ethers.keccak256(ethers.toUtf8Bytes("claim-key-1"));

  beforeEach(async function () {
    const [v, a, o] = await ethers.getSigners();
    victim = v;
    attacker = a;
    other = o;
    const F = await ethers.getContractFactory("CVIN_SCBasedAccOrID_DID_ERC725Basic", victim);
    id = await F.deploy();
    await id.waitForDeployment();
    await (await id.connect(victim).addKey(mgmtKey, 1, 1)).wait();
  });

  it("unauthorizedIssuance: N/A (self-sovereign per-identity deployment)", function () {
    H.naCell(
      STD,
      "unauthorizedIssuance",
      THREAT.unauthorizedIssuance,
      "Each identity is its own contract deployed permissionlessly by its controller; there is no shared gated issuer to bypass. Protection of an existing identity is exercised by the write/hijack scenarios."
    );
  });

  it("unauthorizedAttributeWrite: attacker cannot addKey to a victim identity", async function () {
    const r = await H.attempt(() => id.connect(attacker).addKey(claimKey, 1, 1));
    const ctl = await H.control(() => id.connect(victim).addKey(claimKey, 1, 1));
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedAttributeWrite", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedAttributeWrite,
      attack: "attacker calls addKey to inject a management key into a victim's identity contract",
      defense: 'require(msg.sender == _owner, "Only owner can add keys")',
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedDelegateOrClaim: attacker cannot add a CLAIM-signer key", async function () {
    const r = await H.attempt(() => id.connect(attacker).addKey(claimKey, 3, 1));
    const ctl = await H.control(() => id.connect(victim).addKey(claimKey, 3, 1));
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedDelegateOrClaim", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedDelegateOrClaim,
      attack: "attacker calls addKey(purpose=3 CLAIM) to authorize itself as a claim signer",
      defense: 'require(msg.sender == _owner, "Only owner can add keys")',
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedRevocation: attacker cannot removeKey from a victim identity", async function () {
    const r = await H.attempt(() => id.connect(attacker).removeKey(mgmtKey));
    const ctl = await H.control(() => id.connect(victim).removeKey(mgmtKey));
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedRevocation", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedRevocation,
      attack: "attacker calls removeKey to strip a key from a victim's identity",
      defense: 'require(msg.sender == _owner, "Only owner can remove keys")',
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("identityHijack: attacker cannot transferOwnership of a victim identity", async function () {
    const r = await H.attempt(() => id.connect(attacker).transferOwnership(attacker.address));
    expect(r.outcome).to.equal("DEFENDED");
    expect(await id.owner()).to.equal(victim.address);
    const ctl = await H.control(() => id.connect(victim).transferOwnership(other.address));
    expect(ctl).to.equal("PASS");
    H.record(STD, "identityHijack", {
      outcome: r.outcome,
      threat: THREAT.identityHijack,
      attack: "attacker calls transferOwnership(attacker) to seize the identity contract",
      defense: 'require(msg.sender == _owner, "Only owner can transfer ownership")',
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("signatureReplay: N/A (no signed/relayed operation)", function () {
    H.naCell(
      STD,
      "signatureReplay",
      THREAT.signatureReplay,
      "This basic ERC-725 key manager has no signed/relayed operation (execute() is direct-owner-gated), so there is no consumed signature to replay."
    );
  });
});

// ===========================================================================
// ERC-735 — CVINVehicleClaimHolder (per-vehicle claim holder)
// ===========================================================================
describe("Security / ERC-735 (CVINVehicleClaimHolder)", function () {
  const STD = "ERC-735";
  let holder, owner, attacker, issuer, other;
  const VIN = "1HGBH41JXMN109186";
  const TOPIC = 1; // VIN_ATTESTATION
  const SCHEME = 1; // ECDSA
  const data = ethers.toUtf8Bytes("VIN:1HGBH41JXMN109186");

  async function signClaim(signer, holderAddr, topic, d) {
    const messageHash = ethers.solidityPackedKeccak256(
      ["address", "uint256", "bytes"],
      [holderAddr, topic, d]
    );
    return signer.signMessage(ethers.getBytes(messageHash));
  }

  beforeEach(async function () {
    const [o, a, i, x] = await ethers.getSigners();
    owner = o;
    attacker = a;
    issuer = i;
    other = x;
    const F = await ethers.getContractFactory("CVINVehicleClaimHolder", owner);
    holder = await F.deploy(VIN);
    await holder.waitForDeployment();
  });

  it("unauthorizedIssuance: N/A (self-sovereign per-vehicle deployment)", function () {
    H.naCell(
      STD,
      "unauthorizedIssuance",
      THREAT.unauthorizedIssuance,
      "Each vehicle identity is its own claim-holder contract deployed permissionlessly by its owner; there is no shared gated issuer to bypass."
    );
  });

  it("unauthorizedAttributeWrite: non-owner cannot addClaim (update a claim)", async function () {
    const holderAddr = await holder.getAddress();
    const sig = await signClaim(issuer, holderAddr, TOPIC, data);
    const r = await H.attempt(() =>
      holder.connect(attacker).addClaim(TOPIC, SCHEME, issuer.address, sig, data, "ipfs://a")
    );
    const ctl = await H.control(() =>
      holder.connect(owner).addClaim(TOPIC, SCHEME, issuer.address, sig, data, "ipfs://a")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedAttributeWrite", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedAttributeWrite,
      attack: "attacker (non-owner) calls addClaim to write/overwrite a claim on the identity (closest attribute analogue)",
      defense: "onlyOwner modifier (owner plays the ERC-734 MANAGEMENT-key role)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedDelegateOrClaim: owner cannot anchor a claim with a forged issuer signature", async function () {
    const holderAddr = await holder.getAddress();
    // Attacker forges: signature by `attacker` but claim names `issuer` as the issuer.
    const forged = await signClaim(attacker, holderAddr, TOPIC, data);
    const good = await signClaim(issuer, holderAddr, TOPIC, data);
    const r = await H.attempt(() =>
      holder.connect(owner).addClaim(TOPIC, SCHEME, issuer.address, forged, data, "ipfs://forged")
    );
    const ctl = await H.control(() =>
      holder.connect(owner).addClaim(TOPIC, SCHEME, issuer.address, good, data, "ipfs://good")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedDelegateOrClaim", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedDelegateOrClaim,
      attack: "anchor a claim naming a trusted issuer but signed by the attacker's key (issuer-signature forgery)",
      defense: "on-chain ecrecover of EIP-191(identity,topic,data) must equal the named issuer",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedRevocation: a stranger cannot removeClaim", async function () {
    const holderAddr = await holder.getAddress();
    const good = await signClaim(issuer, holderAddr, TOPIC, data);
    await (await holder.connect(owner).addClaim(TOPIC, SCHEME, issuer.address, good, data, "ipfs://good")).wait();
    const claimId = ethers.solidityPackedKeccak256(["address", "uint256"], [issuer.address, TOPIC]);
    // `other` is neither owner nor issuer.
    const r = await H.attempt(() => holder.connect(other).removeClaim(claimId));
    expect(r.outcome).to.equal("DEFENDED");
    expect(await holder.claimExists(issuer.address, TOPIC)).to.equal(true);
    const ctl = await H.control(() => holder.connect(issuer).removeClaim(claimId));
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedRevocation", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedRevocation,
      attack: "a party that is neither owner nor issuer calls removeClaim to strip a valid attestation",
      defense: "require(msg.sender == owner || msg.sender == claim.issuer)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("identityHijack: non-owner cannot transferOwnership", async function () {
    const r = await H.attempt(() => holder.connect(attacker).transferOwnership(attacker.address));
    expect(r.outcome).to.equal("DEFENDED");
    expect(await holder.owner()).to.equal(owner.address);
    const ctl = await H.control(() => holder.connect(owner).transferOwnership(other.address));
    expect(ctl).to.equal("PASS");
    H.record(STD, "identityHijack", {
      outcome: r.outcome,
      threat: THREAT.identityHijack,
      attack: "attacker calls transferOwnership(attacker) to seize the vehicle identity",
      defense: "onlyOwner modifier",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("signatureReplay: a cross-instance issuer signature cannot be replayed onto another vehicle", async function () {
    // Vehicle A (issuer legitimately attests it).
    const holderAddr = await holder.getAddress();
    const sigA = await signClaim(issuer, holderAddr, TOPIC, data);
    const ctl = await H.control(() =>
      holder.connect(owner).addClaim(TOPIC, SCHEME, issuer.address, sigA, data, "ipfs://A")
    );
    expect(ctl).to.equal("PASS");

    // Vehicle B, controlled by the attacker, replays vehicle A's issuer signature.
    const FB = await ethers.getContractFactory("CVINVehicleClaimHolder", attacker);
    const holderB = await FB.deploy("2HGBH41JXMN109999");
    await holderB.waitForDeployment();
    const r = await H.attempt(() =>
      holderB.connect(attacker).addClaim(TOPIC, SCHEME, issuer.address, sigA, data, "ipfs://B")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(await holderB.claimExists(issuer.address, TOPIC)).to.equal(false);
    H.record(STD, "signatureReplay", {
      outcome: r.outcome,
      threat: THREAT.signatureReplay,
      attack: "replay vehicle A's issuer-signed attestation onto attacker-controlled vehicle B",
      defense: "signed digest binds address(this) (the holder contract), so ecrecover on B != issuer",
      revertReason: r.revertReason,
      control: ctl,
    });
  });
});

// ===========================================================================
// ERC-1155 — CVINVehicleCredential1155 (role-gated, soulbound credentials)
// ===========================================================================
describe("Security / ERC-1155 (CVINVehicleCredential1155)", function () {
  const STD = "ERC-1155";
  let cred, deployer, vehicle, attacker, other;
  const VIN = "1HGBH41JXMN109186";
  const BIRTH_CERT = 1;
  const INSPECTION_CERT = 3;

  beforeEach(async function () {
    const [d, v, a, o] = await ethers.getSigners();
    deployer = d;
    vehicle = v;
    attacker = a;
    other = o;
    const F = await ethers.getContractFactory("CVINVehicleCredential1155", deployer);
    cred = await F.deploy();
    await cred.waitForDeployment();
    await (await cred.registerVehicle(vehicle.address, VIN)).wait();
  });

  it("unauthorizedIssuance: attacker without ISSUER_ROLE cannot registerVehicle", async function () {
    const r = await H.attempt(() =>
      cred.connect(attacker).registerVehicle(attacker.address, "2HGBH41JXMN109187")
    );
    const ctl = await H.control(() =>
      cred.connect(deployer).registerVehicle(other.address, "3HGBH41JXMN109188")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedIssuance", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedIssuance,
      attack: "attacker (no ISSUER_ROLE) calls registerVehicle to mint a BIRTH_CERT identity",
      defense: "AccessControl onlyRole(ISSUER_ROLE)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedAttributeWrite: attacker without ISSUER_ROLE cannot setTokenURI", async function () {
    const r = await H.attempt(() =>
      cred.connect(attacker).setTokenURI(INSPECTION_CERT, "ipfs://malicious")
    );
    const ctl = await H.control(() =>
      cred.connect(deployer).setTokenURI(INSPECTION_CERT, "ipfs://legit")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedAttributeWrite", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedAttributeWrite,
      attack: "attacker (no ISSUER_ROLE) rewrites a credential-type metadata URI (closest attribute analogue)",
      defense: "AccessControl onlyRole(ISSUER_ROLE)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedDelegateOrClaim: attacker without ISSUER_ROLE cannot issueCredential", async function () {
    const r = await H.attempt(() =>
      cred.connect(attacker).issueCredential(vehicle.address, INSPECTION_CERT, 1)
    );
    const ctl = await H.control(() =>
      cred.connect(deployer).issueCredential(vehicle.address, INSPECTION_CERT, 1)
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedDelegateOrClaim", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedDelegateOrClaim,
      attack: "attacker (no ISSUER_ROLE) mints an INSPECTION_CERT credential to a vehicle (credential = claim analogue)",
      defense: "AccessControl onlyRole(ISSUER_ROLE)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedRevocation: attacker without ISSUER_ROLE cannot revokeCredential", async function () {
    const r = await H.attempt(() =>
      cred.connect(attacker).revokeCredential(vehicle.address, BIRTH_CERT, 1)
    );
    const ctl = await H.control(() =>
      cred.connect(deployer).revokeCredential(vehicle.address, BIRTH_CERT, 1)
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedRevocation", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedRevocation,
      attack: "attacker (no ISSUER_ROLE) burns a vehicle's BIRTH_CERT to deregister its identity",
      defense: "AccessControl onlyRole(ISSUER_ROLE)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("identityHijack: soulbound credential cannot be pulled by an attacker", async function () {
    // Attacker attempts to grab the victim's BIRTH_CERT via safeTransferFrom.
    const r = await H.attempt(() =>
      cred.connect(attacker).safeTransferFrom(vehicle.address, attacker.address, BIRTH_CERT, 1, "0x")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(await cred.balanceOf(vehicle.address, BIRTH_CERT)).to.equal(1n);
    // Control: the sanctioned issuer-mediated re-binding (vehicle sale) succeeds.
    const ctl = await H.control(() =>
      cred.connect(deployer).issuerTransferCredential(vehicle.address, other.address, BIRTH_CERT)
    );
    expect(ctl).to.equal("PASS");
    H.record(STD, "identityHijack", {
      outcome: r.outcome,
      threat: THREAT.identityHijack,
      attack: "attacker calls safeTransferFrom to pull a victim's soulbound BIRTH_CERT identity token",
      defense: "ERC1155 approval check + soulbound _update guard (holder transfers require ISSUER_ROLE)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("signatureReplay: N/A (no signed/relayed operation)", function () {
    H.naCell(
      STD,
      "signatureReplay",
      THREAT.signatureReplay,
      "Credential issuance/revocation is direct role-gated calls with no signed/relayed operation, so there is no consumed signature to replay."
    );
  });
});

// ===========================================================================
// ERC-4337 — CVINVehicleAccount + CVINMinimalEntryPoint (smart-account identity)
// ===========================================================================
describe("Security / ERC-4337 (CVINVehicleAccount + CVINMinimalEntryPoint)", function () {
  const STD = "ERC-4337";
  let entryPoint, account, bundler, owner, guardian, attacker, newOwner;
  const ATTR = ethers.keccak256(ethers.toUtf8Bytes("cvin/vehicle/vin"));
  const VAL = ethers.toUtf8Bytes("1HGCM82633A004352");

  beforeEach(async function () {
    const [b, o, g, a, n] = await ethers.getSigners();
    bundler = b;
    owner = o;
    guardian = g;
    attacker = a;
    newOwner = n;
    const EP = await ethers.getContractFactory("CVINMinimalEntryPoint", bundler);
    entryPoint = await EP.deploy();
    await entryPoint.waitForDeployment();
    const AF = await ethers.getContractFactory("CVINVehicleAccount", bundler);
    account = await AF.deploy(await entryPoint.getAddress(), owner.address);
    await account.waitForDeployment();
  });

  it("unauthorizedIssuance: N/A (self-sovereign account deployment)", function () {
    H.naCell(
      STD,
      "unauthorizedIssuance",
      THREAT.unauthorizedIssuance,
      "The account (identity) is deployed permissionlessly; the identifier is the account address. There is no shared gated issuer to bypass."
    );
  });

  it("unauthorizedAttributeWrite: attacker cannot setAttribute directly", async function () {
    const r = await H.attempt(() => account.connect(attacker).setAttribute(ATTR, VAL));
    const ctl = await H.control(() => account.connect(owner).setAttribute(ATTR, VAL));
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedAttributeWrite", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedAttributeWrite,
      attack: "attacker calls setAttribute directly on the vehicle account",
      defense: "onlyOwnerOrEntryPoint modifier (msg.sender must be owner, entryPoint, or self)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedDelegateOrClaim: attacker cannot setGuardian", async function () {
    const r = await H.attempt(() => account.connect(attacker).setGuardian(attacker.address));
    const ctl = await H.control(() => account.connect(owner).setGuardian(guardian.address));
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedDelegateOrClaim", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedDelegateOrClaim,
      attack: "attacker calls setGuardian(attacker) to install itself as the recovery delegate (guardian = recovery-delegate analogue; no on-chain claim model)",
      defense: "onlyOwnerOrEntryPoint modifier",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedRevocation: attacker cannot clear the guardian", async function () {
    await (await account.connect(owner).setGuardian(guardian.address)).wait();
    const r = await H.attempt(() => account.connect(attacker).setGuardian(ethers.ZeroAddress));
    expect(r.outcome).to.equal("DEFENDED");
    expect(await account.guardian()).to.equal(guardian.address);
    const ctl = await H.control(() => account.connect(owner).setGuardian(ethers.ZeroAddress));
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedRevocation", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedRevocation,
      attack: "attacker calls setGuardian(0) to strip the account's recovery delegate (delegate-revocation analogue; ERC-4337 has no identity-level revocation)",
      defense: "onlyOwnerOrEntryPoint modifier",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("identityHijack: attacker cannot rotate the key nor abuse recovery", async function () {
    // Direct key rotation by a stranger.
    const rTransfer = await H.attempt(() =>
      account.connect(attacker).transferOwnership(attacker.address)
    );
    // Recovery abuse by a non-guardian (guardian not even set yet).
    const rRecover = await H.attempt(() =>
      account.connect(attacker).recoverOwner(attacker.address)
    );
    expect(rTransfer.outcome).to.equal("DEFENDED");
    expect(rRecover.outcome).to.equal("DEFENDED");
    expect(await account.owner()).to.equal(owner.address);
    const ctl = await H.control(() =>
      account.connect(owner).transferOwnership(newOwner.address)
    );
    expect(ctl).to.equal("PASS");
    H.record(STD, "identityHijack", {
      outcome: rTransfer.outcome,
      threat: THREAT.identityHijack,
      attack: "attacker calls transferOwnership(attacker) to rotate the signing key; also attempts recoverOwner(attacker) as a non-guardian",
      defense: "transferOwnership gated by onlyOwnerOrEntryPoint; recoverOwner gated by require(msg.sender == guardian)",
      revertReason: `transferOwnership: ${rTransfer.revertReason}; recoverOwner(non-guardian): ${rRecover.revertReason}`,
      control: ctl,
    });
  });

  it("signatureReplay: a consumed UserOperation cannot be replayed through the EntryPoint", async function () {
    const sender = await account.getAddress();
    const inner = account.interface.encodeFunctionData("setAttribute", [ATTR, ethers.hexlify(VAL)]);
    const callData = account.interface.encodeFunctionData("execute", [sender, 0, inner]);
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
    userOp.signature = await owner.signMessage(ethers.getBytes(userOpHash));

    // Control: the owner-signed op is handled once.
    const ctl = await H.control(() => entryPoint.connect(bundler).handleOp(userOp));
    expect(ctl).to.equal("PASS");
    expect(await entryPoint.nonces(sender)).to.equal(1n);

    // Attack: replay the identical userOp (same nonce, same signature).
    const r = await H.attempt(() => entryPoint.connect(attacker).handleOp(userOp));
    expect(r.outcome).to.equal("DEFENDED");
    H.record(STD, "signatureReplay", {
      outcome: r.outcome,
      threat: THREAT.signatureReplay,
      attack: "replay a previously mined PackedUserOperation (same nonce and signature) through handleOp",
      defense: "EntryPoint per-sender sequential nonce: require(userOp.nonce == nonces[sender])",
      revertReason: r.revertReason,
      control: ctl,
    });
  });
});

// ===========================================================================
// LSP8 — CVINVehicleLSP8 (authority-gated identifiable asset)
// ===========================================================================
describe("Security / LSP8 (CVINVehicleLSP8)", function () {
  const STD = "LSP8";
  let lsp8, authority, vehicleOwner, attacker, buyer;
  const VIN = "1HGBH41JXMN109186";
  let tokenId;

  beforeEach(async function () {
    const [au, vo, a, b] = await ethers.getSigners();
    authority = au;
    vehicleOwner = vo;
    attacker = a;
    buyer = b;
    const F = await ethers.getContractFactory("CVINVehicleLSP8", authority);
    lsp8 = await F.deploy("CVIN Vehicle Identity LSP8", "CVIN-LSP8");
    await lsp8.waitForDeployment();
    await (await lsp8.mintVehicle(vehicleOwner.address, VIN)).wait();
    tokenId = ethers.keccak256(ethers.toUtf8Bytes(VIN));
  });

  it("unauthorizedIssuance: attacker (not the issuing authority) cannot mintVehicle", async function () {
    const r = await H.attempt(() => lsp8.connect(attacker).mintVehicle(attacker.address, "2HGBH41JXMN109187"));
    const ctl = await H.control(() => lsp8.connect(authority).mintVehicle(buyer.address, "3HGBH41JXMN109188"));
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedIssuance", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedIssuance,
      attack: "attacker (not the contract owner / issuing authority) calls mintVehicle",
      defense: 'onlyOwner modifier ("caller is not the contract owner")',
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedAttributeWrite: attacker cannot setDataForTokenId", async function () {
    const key = await lsp8.DATA_KEY_INSPECTION();
    const r = await H.attempt(() =>
      lsp8.connect(attacker).setDataForTokenId(tokenId, key, ethers.toUtf8Bytes("forged:pass"))
    );
    const ctl = await H.control(() =>
      lsp8.connect(authority).setDataForTokenId(tokenId, key, ethers.toUtf8Bytes("2026-07:pass"))
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedAttributeWrite", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedAttributeWrite,
      attack: "attacker calls setDataForTokenId to forge per-token vehicle metadata (e.g. inspection status)",
      defense: "onlyOwner modifier (only the issuing authority writes token data)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedDelegateOrClaim: N/A (no operator/claim model)", function () {
    H.naCell(
      STD,
      "unauthorizedDelegateOrClaim",
      THREAT.unauthorizedDelegateOrClaim,
      "This representative LSP8 implementation omits operator authorization and has no native claim model, so there is no delegate/claim primitive to abuse (attestations live in owner-gated per-token data keys, covered by unauthorizedAttributeWrite)."
    );
  });

  it("unauthorizedRevocation: attacker (neither authority nor token owner) cannot revokeVehicle", async function () {
    const r = await H.attempt(() => lsp8.connect(attacker).revokeVehicle(tokenId, "0x"));
    expect(r.outcome).to.equal("DEFENDED");
    expect(await lsp8.exists(tokenId)).to.equal(true);
    const ctl = await H.control(() => lsp8.connect(vehicleOwner).revokeVehicle(tokenId, "0x"));
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedRevocation", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedRevocation,
      attack: "attacker calls revokeVehicle to burn a victim's identity token",
      defense: "require(msg.sender == owner || msg.sender == tokenOwner)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("identityHijack: attacker cannot transfer a token it does not own", async function () {
    const r = await H.attempt(() =>
      lsp8.connect(attacker).transfer(vehicleOwner.address, attacker.address, tokenId, true, "0x")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(await lsp8.tokenOwnerOf(tokenId)).to.equal(vehicleOwner.address);
    const ctl = await H.control(() =>
      lsp8.connect(vehicleOwner).transfer(vehicleOwner.address, buyer.address, tokenId, true, "0x")
    );
    expect(ctl).to.equal("PASS");
    H.record(STD, "identityHijack", {
      outcome: r.outcome,
      threat: THREAT.identityHijack,
      attack: "attacker calls transfer(from=victim, to=attacker, tokenId) to steal the vehicle token (operators not implemented)",
      defense: 'require(msg.sender == tokenOwner) ("caller is not the token owner")',
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("signatureReplay: N/A (no signed/relayed operation)", function () {
    H.naCell(
      STD,
      "signatureReplay",
      THREAT.signatureReplay,
      "This LSP8 implementation has no signed/relayed operation, so there is no consumed signature to replay."
    );
  });
});

// ===========================================================================
// MOBI-VID-V2 — MOBIVIDRegistryV2 (shared registry, role-gated issuers)
// ===========================================================================
describe("Security / MOBI-VID-V2 (MOBIVIDRegistryV2)", function () {
  const STD = "MOBI-VID-V2";
  let registry, authority, firstOwner, attacker, serviceCenter, dealer;
  let vehicle;
  const vin = "5YJSA1E26MF123456";
  const vinHash = ethers.keccak256(ethers.toUtf8Bytes(vin));

  beforeEach(async function () {
    const [au, fo, a, sc, de, vw] = await ethers.getSigners();
    authority = au; // registryAuthority + authorized manufacturer (constructor)
    firstOwner = fo;
    attacker = a;
    serviceCenter = sc;
    dealer = de;
    vehicle = vw.address;
    const F = await ethers.getContractFactory("MOBIVIDRegistryV2", authority);
    registry = await F.deploy();
    await registry.waitForDeployment();
    await (await registry.registerVehicleBirth(
      vehicle, vinHash, "encrypted:VIN", ethers.keccak256(ethers.toUtf8Bytes("ipfs://cert")), firstOwner.address, "0x"
    )).wait();
    await (await registry.authorizeIssuer(serviceCenter.address, 3 /* SERVICE_CENTER */)).wait();
  });

  it("unauthorizedIssuance: attacker (not an authorized manufacturer) cannot registerVehicleBirth", async function () {
    const vin2 = "5YJSA1E26MF999999";
    const r = await H.attempt(() =>
      registry.connect(attacker).registerVehicleBirth(
        attacker.address, ethers.keccak256(ethers.toUtf8Bytes(vin2)), "enc", ethers.keccak256(ethers.toUtf8Bytes("ipfs://c2")), attacker.address, "0x"
      )
    );
    const vin3 = "5YJSA1E26MF888888";
    const ctl = await H.control(() =>
      registry.connect(authority).registerVehicleBirth(
        dealer.address, ethers.keccak256(ethers.toUtf8Bytes(vin3)), "enc", ethers.keccak256(ethers.toUtf8Bytes("ipfs://c3")), dealer.address, "0x"
      )
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedIssuance", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedIssuance,
      attack: "attacker (not an authorized manufacturer) calls registerVehicleBirth to forge a birth certificate",
      defense: "onlyAuthorizedManufacturer modifier",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedAttributeWrite: unauthorized issuer cannot recordLifecycleEvent", async function () {
    // MAINTENANCE (EventType 0) — attacker holds no issuer role.
    const r = await H.attempt(() =>
      registry.connect(attacker).recordLifecycleEvent(vehicle, 0, 15000, ethers.keccak256(ethers.toUtf8Bytes("ipfs://m")), ethers.keccak256(ethers.toUtf8Bytes("vc")), "BC-CAN")
    );
    const ctl = await H.control(() =>
      registry.connect(serviceCenter).recordLifecycleEvent(vehicle, 0, 15000, ethers.keccak256(ethers.toUtf8Bytes("ipfs://m")), ethers.keccak256(ethers.toUtf8Bytes("vc")), "BC-CAN")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedAttributeWrite", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedAttributeWrite,
      attack: "attacker (unauthorized issuer) records a fabricated MAINTENANCE lifecycle event (closest attribute analogue)",
      defense: "onlyAuthorizedIssuer(eventType): role must be whitelisted for that event type",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedDelegateOrClaim: unauthorized party cannot attestEvent", async function () {
    // Legit event to attest.
    const evTx = await registry.connect(serviceCenter).recordLifecycleEvent(vehicle, 0, 15000, ethers.keccak256(ethers.toUtf8Bytes("ipfs://m")), ethers.keccak256(ethers.toUtf8Bytes("vc")), "BC-CAN");
    await evTx.wait();
    const eventIds = await registry.getVehicleEvents(vehicle);
    const eventId = eventIds[0];
    await (await registry.authorizeIssuer(dealer.address, 2 /* DEALER */)).wait();
    const r = await H.attempt(() =>
      registry.connect(attacker).attestEvent(eventId, vehicle, "0x" + "ab".repeat(65))
    );
    const ctl = await H.control(() =>
      registry.connect(dealer).attestEvent(eventId, vehicle, "0x" + "cd".repeat(65))
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedDelegateOrClaim", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedDelegateOrClaim,
      attack: "attacker (unauthorized) calls attestEvent to co-sign a lifecycle event (multi-party attestation = claim analogue)",
      defense: "require(authorizedIssuers[msg.sender] != NONE)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedRevocation: attacker cannot revokeIdentity of a victim vehicle", async function () {
    const r = await H.attempt(() => registry.connect(attacker).revokeIdentity(vehicle));
    expect(r.outcome).to.equal("DEFENDED");
    expect(await registry.revoked(vehicle)).to.equal(false);
    const ctl = await H.control(() => registry.connect(firstOwner).revokeIdentity(vehicle));
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedRevocation", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedRevocation,
      attack: "attacker calls revokeIdentity(vehicle) to decommission a victim's DID",
      defense: "inherited onlyOwner(identity, msg.sender) (only the current identity owner)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("identityHijack: attacker cannot transferVehicleOwnership of a victim vehicle", async function () {
    const r = await H.attempt(() =>
      registry.connect(attacker).transferVehicleOwnership(vehicle, attacker.address, 20000, "ICBC")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(await registry.identityOwner(vehicle)).to.equal(firstOwner.address);
    const ctl = await H.control(() =>
      registry.connect(firstOwner).transferVehicleOwnership(vehicle, dealer.address, 20000, "ICBC")
    );
    expect(ctl).to.equal("PASS");
    H.record(STD, "identityHijack", {
      outcome: r.outcome,
      threat: THREAT.identityHijack,
      attack: "attacker calls transferVehicleOwnership to seize a victim vehicle's identity",
      defense: "inherited onlyOwner(identity, msg.sender)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("signatureReplay: N/A (no signed/relayed operation in this implementation)", function () {
    H.naCell(
      STD,
      "signatureReplay",
      THREAT.signatureReplay,
      "This MOBI VID V2 build exposes only direct-call operations (no ERC-1056 *Signed meta-transactions are wired through), so there is no consumed signature to replay. attestEvent stores a signature blob but never re-executes it on-chain."
    );
  });
});

// ===========================================================================
// CVIN-Combined — CVINCombinedIdentity (ERC-1056 + ERC-735 hybrid)
// ===========================================================================
describe("Security / CVIN-Combined (CVINCombinedIdentity)", function () {
  const STD = "CVIN-Combined";
  let registry, deployer, victim, attacker, other;
  const name = ethers.keccak256(ethers.toUtf8Bytes("did/pub/Secp256k1/veriKey"));
  const value = ethers.toUtf8Bytes("0x02b97c30de767f084ce3080168ee29305");
  const TOPIC = 1; // CLAIM_TOPIC_VIN
  const SCHEME = 1;
  const claimData = ethers.toUtf8Bytes("1HGCM82633A004352");
  // Issuer whose private key we control (raw-digest signer, like the benchmark).
  const issuerWallet = new ethers.Wallet(
    "0x1f2e3d4c5b6a79881726354453627181920a1b2c3d4e5f60718293a4b5c6d7e8"
  );
  // A rogue key used to forge issuer signatures (distinct from issuerWallet).
  const forgerWallet = new ethers.Wallet(
    "0x2a3b4c5d6e7f8091a2b3c4d5e6f7081920314253647586970a1b2c3d4e5f6071"
  );

  function rawClaimSig(regAddr, identity, topic, d, wallet) {
    const digest = ethers.solidityPackedKeccak256(
      ["address", "address", "uint256", "bytes"],
      [regAddr, identity, topic, d]
    );
    return ethers.Signature.from(wallet.signingKey.sign(digest)).serialized;
  }

  beforeEach(async function () {
    const [d, v, a, o] = await ethers.getSigners();
    deployer = d;
    victim = v;
    attacker = a;
    other = o;
    const F = await ethers.getContractFactory("CVINCombinedIdentity", deployer);
    registry = await F.deploy();
    await registry.waitForDeployment();
    await (await registry.connect(victim).setAttribute(victim.address, name, value, 86400)).wait();
  });

  it("unauthorizedIssuance: N/A (implicit permissionless identities)", function () {
    H.naCell(
      STD,
      "unauthorizedIssuance",
      THREAT.unauthorizedIssuance,
      "ERC-1056 side: every address is an implicit self-owned identity; there is no gated issuance step to bypass."
    );
  });

  it("unauthorizedAttributeWrite: attacker cannot setAttribute on a victim identity", async function () {
    const r = await H.attempt(() =>
      registry.connect(attacker).setAttribute(victim.address, name, value, 86400)
    );
    const ctl = await H.control(() =>
      registry.connect(victim).setAttribute(victim.address, name, value, 86400)
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedAttributeWrite", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedAttributeWrite,
      attack: "attacker calls setAttribute(victim, ...) on a DID it does not own",
      defense: "onlyIdentityOwner(identity) modifier",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedDelegateOrClaim: a claim with a forged issuer signature is rejected", async function () {
    const regAddr = await registry.getAddress();
    const forged = rawClaimSig(regAddr, victim.address, TOPIC, claimData, forgerWallet); // signed by rogue key, names issuerWallet
    const good = rawClaimSig(regAddr, victim.address, TOPIC, claimData, issuerWallet);
    const r = await H.attempt(() =>
      registry.connect(victim).addClaim(victim.address, TOPIC, SCHEME, issuerWallet.address, forged, claimData, "ipfs://forged")
    );
    const ctl = await H.control(() =>
      registry.connect(victim).addClaim(victim.address, TOPIC, SCHEME, issuerWallet.address, good, claimData, "ipfs://good")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedDelegateOrClaim", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedDelegateOrClaim,
      attack: "anchor a safety-critical claim naming a trusted issuer but signed by the attacker's key (issuer-signature forgery)",
      defense: "on-chain ecrecover of raw digest keccak256(registry,identity,topic,data) must equal the named issuer",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("unauthorizedRevocation: a stranger cannot removeClaim", async function () {
    const regAddr = await registry.getAddress();
    const good = rawClaimSig(regAddr, victim.address, TOPIC, claimData, issuerWallet);
    await (await registry.connect(victim).addClaim(victim.address, TOPIC, SCHEME, issuerWallet.address, good, claimData, "ipfs://good")).wait();
    const claimId = ethers.solidityPackedKeccak256(["address", "uint256"], [issuerWallet.address, TOPIC]);
    const r = await H.attempt(() => registry.connect(attacker).removeClaim(victim.address, claimId));
    expect(r.outcome).to.equal("DEFENDED");
    expect(await registry.hasValidClaim(victim.address, TOPIC, issuerWallet.address)).to.equal(true);
    const ctl = await H.control(() => registry.connect(victim).removeClaim(victim.address, claimId));
    expect(ctl).to.equal("PASS");
    H.record(STD, "unauthorizedRevocation", {
      outcome: r.outcome,
      threat: THREAT.unauthorizedRevocation,
      attack: "a party that is neither identity owner nor claim issuer calls removeClaim to strip a safety-critical attestation",
      defense: "require(msg.sender == identityOwner(identity) || msg.sender == claim.issuer)",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("identityHijack: attacker cannot changeOwner of a victim identity", async function () {
    const r = await H.attempt(() => registry.connect(attacker).changeOwner(victim.address, attacker.address));
    expect(r.outcome).to.equal("DEFENDED");
    expect(await registry.identityOwner(victim.address)).to.equal(victim.address);
    const ctl = await H.control(() => registry.connect(victim).changeOwner(victim.address, other.address));
    expect(ctl).to.equal("PASS");
    H.record(STD, "identityHijack", {
      outcome: r.outcome,
      threat: THREAT.identityHijack,
      attack: "attacker calls changeOwner(victim, attacker) to seize the identity",
      defense: "onlyIdentityOwner(identity) modifier",
      revertReason: r.revertReason,
      control: ctl,
    });
  });

  it("signatureReplay: a claim signature bound to one identity cannot be replayed onto another", async function () {
    const regAddr = await registry.getAddress();
    // Issuer legitimately attests the victim's identity.
    const sigForVictim = rawClaimSig(regAddr, victim.address, TOPIC, claimData, issuerWallet);
    const ctl = await H.control(() =>
      registry.connect(victim).addClaim(victim.address, TOPIC, SCHEME, issuerWallet.address, sigForVictim, claimData, "ipfs://victim")
    );
    expect(ctl).to.equal("PASS");

    // Attacker replays the victim's issuer signature onto ITS OWN identity (attacker owns attacker.address).
    const r = await H.attempt(() =>
      registry.connect(attacker).addClaim(attacker.address, TOPIC, SCHEME, issuerWallet.address, sigForVictim, claimData, "ipfs://attacker")
    );
    expect(r.outcome).to.equal("DEFENDED");
    expect(await registry.hasValidClaim(attacker.address, TOPIC, issuerWallet.address)).to.equal(false);
    H.record(STD, "signatureReplay", {
      outcome: r.outcome,
      threat: THREAT.signatureReplay,
      attack: "replay the victim's issuer-signed claim onto the attacker's own identity to inherit a credential",
      defense: "signed digest binds both registry address and the subject identity; ecrecover on a different identity != issuer",
      revertReason: r.revertReason,
      control: ctl,
    });
  });
});

// ===========================================================================
// Emit the security matrix after all scenarios have executed.
// ===========================================================================
after(function () {
  const metadata = {
    solcVersion: "0.8.24",
    solcSettings: { optimizer: { enabled: true, runs: 200 }, viaIR: true },
    ozVersion: "5.0.2",
    date: new Date().toISOString(),
    network: "hardhat-local",
    chainId: 31337,
    attackLabels: H.ATTACK_LABELS,
    attackThreats: THREAT,
    outcomes: ["DEFENDED", "VULNERABLE", "N/A"],
    contracts: {
      "ERC-1056": "contracts/ERC1056/EthereumDIDRegistry.sol:EthereumDIDRegistry",
      "ERC-721": "contracts/ERC721/CVINVehicleNFT.sol:CVINVehicleNFT",
      "ERC-725": "contracts/ERC725/CVIN_DID_ERC725.sol:CVIN_SCBasedAccOrID_DID_ERC725Basic",
      "ERC-735": "contracts/ERC735/CVINVehicleClaimHolder.sol:CVINVehicleClaimHolder",
      "ERC-1155": "contracts/ERC1155/CVINVehicleCredential1155.sol:CVINVehicleCredential1155",
      "ERC-4337": "contracts/ERC4337/CVINVehicleAccount.sol + CVINMinimalEntryPoint.sol",
      "LSP8": "contracts/LSP8/CVINVehicleLSP8.sol:CVINVehicleLSP8",
      "MOBI-VID-V2": "contracts/MOBI/MOBIVIDRegistryV2.sol:MOBIVIDRegistryV2",
      "CVIN-Combined": "contracts/CVINCombined/CVINCombinedIdentity.sol:CVINCombinedIdentity",
    },
    notes:
      "Each cell is the REAL observed outcome of executing a concrete attack transaction on a fresh Hardhat network: DEFENDED = the malicious tx reverted; VULNERABLE = it was mined; N/A = the attack does not apply to the standard's identity model. Most cells also carry a differential 'control' (the same operation by the authorized party) that must PASS, proving the revert is due to access control / signature verification, not an unrelated failure. Attacks parallel the gas benchmark's lifecycle operation set (create/update/delegate-or-claim/revoke/transfer) plus a cross-cutting signatureReplay attack.",
  };
  const outFile = H.writeMatrix(metadata);

  // Console summary (standards x attacks).
  const symbol = { DEFENDED: "DEF", VULNERABLE: "VULN", "N/A": "n/a" };
  console.log("\n=== Security matrix (attack outcomes) ===");
  const stds = Object.keys(H.RESULTS);
  console.log(["attack", ...stds].join("\t"));
  for (const atk of H.ATTACKS) {
    const row = [atk];
    for (const s of stds) {
      const cell = H.RESULTS[s] && H.RESULTS[s][atk];
      row.push(cell ? symbol[cell.outcome] || cell.outcome : "-");
    }
    console.log(row.join("\t"));
  }
  console.log(`\nSecurity matrix written to ${outFile}`);
});
