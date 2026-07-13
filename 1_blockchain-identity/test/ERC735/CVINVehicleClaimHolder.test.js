const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CVINVehicleClaimHolder (ERC-735)", function () {
    let claimHolder;
    let owner, manufacturer, inspector, insurer, newOwner, attacker;

    const TEST_VIN = "1HGBH41JXMN109186";
    const ECDSA_SCHEME = 1;

    // Vehicle claim topics
    const VIN_ATTESTATION = 1;
    const MANUFACTURER_CERT = 2;
    const INSPECTION = 3;
    const INSURANCE = 4;

    /**
     * Issuer signs keccak256(abi.encodePacked(identityAddress, topic, data))
     * with the standard eth_sign prefix (ethers signMessage).
     */
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

    beforeEach(async function () {
        [owner, manufacturer, inspector, insurer, newOwner, attacker] =
            await ethers.getSigners();

        const ClaimHolder = await ethers.getContractFactory("CVINVehicleClaimHolder");
        claimHolder = await ClaimHolder.connect(owner).deploy(TEST_VIN);
        await claimHolder.waitForDeployment();
    });

    describe("Deployment / identity creation", function () {
        it("deploys and creates the vehicle identity with VIN and owner (gas sanity)", async function () {
            const deployTx = claimHolder.deploymentTransaction();
            const receipt = await deployTx.wait();
            console.log(`        [gas] ERC-735 deploy + identity creation: ${receipt.gasUsed.toString()}`);

            expect(await claimHolder.vin()).to.equal(TEST_VIN);
            expect(await claimHolder.vinHash()).to.equal(
                ethers.keccak256(ethers.toUtf8Bytes(TEST_VIN))
            );
            expect(await claimHolder.owner()).to.equal(owner.address);
        });

        it("rejects deployment with an empty VIN", async function () {
            const ClaimHolder = await ethers.getContractFactory("CVINVehicleClaimHolder");
            await expect(ClaimHolder.deploy("")).to.be.revertedWith("ERC735: empty VIN");
        });

        it("exposes the vehicle-specific claim topic constants", async function () {
            expect(await claimHolder.VIN_ATTESTATION()).to.equal(VIN_ATTESTATION);
            expect(await claimHolder.MANUFACTURER_CERT()).to.equal(MANUFACTURER_CERT);
            expect(await claimHolder.INSPECTION()).to.equal(INSPECTION);
            expect(await claimHolder.INSURANCE()).to.equal(INSURANCE);
        });
    });

    describe("addClaim", function () {
        it("adds a manufacturer-signed VIN attestation claim and emits ClaimAdded (gas sanity)", async function () {
            const identityAddress = await claimHolder.getAddress();
            const data = ethers.toUtf8Bytes(`VIN:${TEST_VIN}`);
            const signature = await signClaim(manufacturer, identityAddress, VIN_ATTESTATION, data);
            const expectedClaimId = claimIdFor(manufacturer.address, VIN_ATTESTATION);

            const tx = await claimHolder
                .connect(owner)
                .addClaim(VIN_ATTESTATION, ECDSA_SCHEME, manufacturer.address, signature, data, "ipfs://vin-attestation");
            const receipt = await tx.wait();
            console.log(`        [gas] ERC-735 addClaim: ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(claimHolder, "ClaimAdded")
                .withArgs(
                    expectedClaimId,
                    VIN_ATTESTATION,
                    ECDSA_SCHEME,
                    manufacturer.address,
                    signature,
                    data,
                    "ipfs://vin-attestation"
                );

            const claim = await claimHolder.getClaim(expectedClaimId);
            expect(claim.topic).to.equal(VIN_ATTESTATION);
            expect(claim.scheme).to.equal(ECDSA_SCHEME);
            expect(claim.issuer).to.equal(manufacturer.address);
            expect(claim.uri).to.equal("ipfs://vin-attestation");
            expect(ethers.toUtf8String(claim.data)).to.equal(`VIN:${TEST_VIN}`);
        });

        it("indexes claims by topic via getClaimIdsByTopic", async function () {
            const identityAddress = await claimHolder.getAddress();

            const inspData = ethers.toUtf8Bytes("inspection:2026-07:pass");
            const inspSig = await signClaim(inspector, identityAddress, INSPECTION, inspData);
            await claimHolder
                .connect(owner)
                .addClaim(INSPECTION, ECDSA_SCHEME, inspector.address, inspSig, inspData, "ipfs://inspection");

            const insData = ethers.toUtf8Bytes("policy:ABC-777");
            const insSig = await signClaim(insurer, identityAddress, INSURANCE, insData);
            await claimHolder
                .connect(owner)
                .addClaim(INSURANCE, ECDSA_SCHEME, insurer.address, insSig, insData, "ipfs://insurance");

            const inspectionIds = await claimHolder.getClaimIdsByTopic(INSPECTION);
            expect(inspectionIds).to.have.lengthOf(1);
            expect(inspectionIds[0]).to.equal(claimIdFor(inspector.address, INSPECTION));

            const insuranceIds = await claimHolder.getClaimIdsByTopic(INSURANCE);
            expect(insuranceIds).to.have.lengthOf(1);
            expect(await claimHolder.claimExists(insurer.address, INSURANCE)).to.be.true;
            expect(await claimHolder.claimExists(insurer.address, INSPECTION)).to.be.false;
        });

        it("rejects a claim whose signature does not match the stated issuer", async function () {
            const identityAddress = await claimHolder.getAddress();
            const data = ethers.toUtf8Bytes("forged manufacturer cert");
            // attacker signs, but claim names manufacturer as the issuer
            const forgedSignature = await signClaim(attacker, identityAddress, MANUFACTURER_CERT, data);

            await expect(
                claimHolder
                    .connect(owner)
                    .addClaim(MANUFACTURER_CERT, ECDSA_SCHEME, manufacturer.address, forgedSignature, data, "")
            ).to.be.revertedWith("ERC735: invalid issuer signature");
        });

        it("rejects a valid signature that covers different data (tamper detection)", async function () {
            const identityAddress = await claimHolder.getAddress();
            const signedData = ethers.toUtf8Bytes("inspection:pass");
            const tamperedData = ethers.toUtf8Bytes("inspection:FAIL->pass");
            const signature = await signClaim(inspector, identityAddress, INSPECTION, signedData);

            await expect(
                claimHolder
                    .connect(owner)
                    .addClaim(INSPECTION, ECDSA_SCHEME, inspector.address, signature, tamperedData, "")
            ).to.be.revertedWith("ERC735: invalid issuer signature");
        });

        it("rejects addClaim from a non-owner caller (negative authorization)", async function () {
            const identityAddress = await claimHolder.getAddress();
            const data = ethers.toUtf8Bytes("insurance policy");
            const signature = await signClaim(insurer, identityAddress, INSURANCE, data);

            await expect(
                claimHolder
                    .connect(attacker)
                    .addClaim(INSURANCE, ECDSA_SCHEME, insurer.address, signature, data, "")
            ).to.be.revertedWith("ERC735: caller is not the owner");
        });

        it("rejects an unsupported signature scheme", async function () {
            const identityAddress = await claimHolder.getAddress();
            const data = ethers.toUtf8Bytes("data");
            const signature = await signClaim(insurer, identityAddress, INSURANCE, data);

            await expect(
                claimHolder
                    .connect(owner)
                    .addClaim(INSURANCE, 2, insurer.address, signature, data, "")
            ).to.be.revertedWith("ERC735: unsupported signature scheme");
        });
    });

    describe("Claim update (ClaimChanged)", function () {
        it("re-adding a claim for the same (issuer, topic) updates it and emits ClaimChanged (gas sanity)", async function () {
            const identityAddress = await claimHolder.getAddress();
            const claimId = claimIdFor(inspector.address, INSPECTION);

            const dataV1 = ethers.toUtf8Bytes("inspection:2025:pass");
            const sigV1 = await signClaim(inspector, identityAddress, INSPECTION, dataV1);
            await claimHolder
                .connect(owner)
                .addClaim(INSPECTION, ECDSA_SCHEME, inspector.address, sigV1, dataV1, "ipfs://v1");

            const dataV2 = ethers.toUtf8Bytes("inspection:2026:pass");
            const sigV2 = await signClaim(inspector, identityAddress, INSPECTION, dataV2);
            const tx = await claimHolder
                .connect(owner)
                .addClaim(INSPECTION, ECDSA_SCHEME, inspector.address, sigV2, dataV2, "ipfs://v2");
            const receipt = await tx.wait();
            console.log(`        [gas] ERC-735 update claim (ClaimChanged): ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(claimHolder, "ClaimChanged")
                .withArgs(claimId, INSPECTION, ECDSA_SCHEME, inspector.address, sigV2, dataV2, "ipfs://v2");

            // topic index must not grow on update
            expect(await claimHolder.getClaimIdsByTopic(INSPECTION)).to.have.lengthOf(1);
            const claim = await claimHolder.getClaim(claimId);
            expect(claim.uri).to.equal("ipfs://v2");
        });
    });

    describe("removeClaim (revocation)", function () {
        let claimId, data, signature;

        beforeEach(async function () {
            const identityAddress = await claimHolder.getAddress();
            data = ethers.toUtf8Bytes("policy:XYZ-123");
            signature = await signClaim(insurer, identityAddress, INSURANCE, data);
            await claimHolder
                .connect(owner)
                .addClaim(INSURANCE, ECDSA_SCHEME, insurer.address, signature, data, "ipfs://policy");
            claimId = claimIdFor(insurer.address, INSURANCE);
        });

        it("owner can remove a claim; emits ClaimRemoved and clears storage (gas sanity)", async function () {
            const tx = await claimHolder.connect(owner).removeClaim(claimId);
            const receipt = await tx.wait();
            console.log(`        [gas] ERC-735 removeClaim: ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(claimHolder, "ClaimRemoved")
                .withArgs(claimId, INSURANCE, ECDSA_SCHEME, insurer.address, signature, data, "ipfs://policy");

            const claim = await claimHolder.getClaim(claimId);
            expect(claim.issuer).to.equal(ethers.ZeroAddress);
            expect(await claimHolder.getClaimIdsByTopic(INSURANCE)).to.have.lengthOf(0);
        });

        it("issuer can revoke their own claim", async function () {
            await expect(claimHolder.connect(insurer).removeClaim(claimId))
                .to.emit(claimHolder, "ClaimRemoved");
            expect(await claimHolder.claimExists(insurer.address, INSURANCE)).to.be.false;
        });

        it("rejects removeClaim from a caller that is neither owner nor issuer", async function () {
            await expect(
                claimHolder.connect(attacker).removeClaim(claimId)
            ).to.be.revertedWith("ERC735: caller is not owner nor issuer");
        });

        it("rejects removing a non-existent claim", async function () {
            const bogusId = claimIdFor(attacker.address, INSPECTION);
            await expect(
                claimHolder.connect(owner).removeClaim(bogusId)
            ).to.be.revertedWith("ERC735: claim does not exist");
        });
    });

    describe("Ownership transfer", function () {
        it("transfers identity ownership and emits OwnershipTransferred (gas sanity)", async function () {
            const tx = await claimHolder.connect(owner).transferOwnership(newOwner.address);
            const receipt = await tx.wait();
            console.log(`        [gas] ERC-735 transferOwnership: ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(claimHolder, "OwnershipTransferred")
                .withArgs(owner.address, newOwner.address);
            expect(await claimHolder.owner()).to.equal(newOwner.address);

            // new owner can manage claims, old owner cannot
            const identityAddress = await claimHolder.getAddress();
            const data = ethers.toUtf8Bytes("post-sale inspection");
            const signature = await signClaim(inspector, identityAddress, INSPECTION, data);
            await expect(
                claimHolder.connect(owner).addClaim(INSPECTION, ECDSA_SCHEME, inspector.address, signature, data, "")
            ).to.be.revertedWith("ERC735: caller is not the owner");
            await expect(
                claimHolder.connect(newOwner).addClaim(INSPECTION, ECDSA_SCHEME, inspector.address, signature, data, "")
            ).to.emit(claimHolder, "ClaimAdded");
        });

        it("rejects ownership transfer from non-owner", async function () {
            await expect(
                claimHolder.connect(attacker).transferOwnership(attacker.address)
            ).to.be.revertedWith("ERC735: caller is not the owner");
        });
    });
});
