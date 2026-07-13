const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CVINVehicleCredential1155 (ERC-1155 multi-token credentials)", function () {
    let credential;
    let admin, issuer, vehicle, newVehicleAddress, attacker;

    const TEST_VIN = "1HGBH41JXMN109186";

    // Credential type token IDs
    const BIRTH_CERT = 1;
    const REGISTRATION = 2;
    const INSPECTION_CERT = 3;
    const INSURANCE_CERT = 4;
    const MAINTENANCE_BADGE = 5;

    beforeEach(async function () {
        [admin, issuer, vehicle, newVehicleAddress, attacker] = await ethers.getSigners();

        const Credential = await ethers.getContractFactory("CVINVehicleCredential1155");
        credential = await Credential.connect(admin).deploy();
        await credential.waitForDeployment();

        const ISSUER_ROLE = await credential.ISSUER_ROLE();
        await credential.connect(admin).grantRole(ISSUER_ROLE, issuer.address);
    });

    describe("Deployment", function () {
        it("deploys with admin holding DEFAULT_ADMIN_ROLE and ISSUER_ROLE (gas sanity)", async function () {
            const receipt = await credential.deploymentTransaction().wait();
            console.log(`        [gas] ERC-1155 deploy: ${receipt.gasUsed.toString()}`);

            const DEFAULT_ADMIN_ROLE = await credential.DEFAULT_ADMIN_ROLE();
            const ISSUER_ROLE = await credential.ISSUER_ROLE();
            expect(await credential.hasRole(DEFAULT_ADMIN_ROLE, admin.address)).to.be.true;
            expect(await credential.hasRole(ISSUER_ROLE, admin.address)).to.be.true;
            expect(await credential.hasRole(ISSUER_ROLE, issuer.address)).to.be.true;
        });

        it("exposes the credential type constants", async function () {
            expect(await credential.BIRTH_CERT()).to.equal(BIRTH_CERT);
            expect(await credential.REGISTRATION()).to.equal(REGISTRATION);
            expect(await credential.INSPECTION_CERT()).to.equal(INSPECTION_CERT);
            expect(await credential.INSURANCE_CERT()).to.equal(INSURANCE_CERT);
            expect(await credential.MAINTENANCE_BADGE()).to.equal(MAINTENANCE_BADGE);
        });
    });

    describe("Identity creation (registerVehicle = mint BIRTH_CERT)", function () {
        it("registers a vehicle: mints one BIRTH_CERT, binds VIN, emits events (gas sanity)", async function () {
            const vinHash = ethers.keccak256(ethers.toUtf8Bytes(TEST_VIN));

            const tx = await credential.connect(issuer).registerVehicle(vehicle.address, TEST_VIN);
            const receipt = await tx.wait();
            console.log(`        [gas] ERC-1155 registerVehicle (create identity): ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(credential, "VehicleRegistered")
                .withArgs(vehicle.address, vinHash, TEST_VIN);
            await expect(tx)
                .to.emit(credential, "TransferSingle")
                .withArgs(issuer.address, ethers.ZeroAddress, vehicle.address, BIRTH_CERT, 1);

            expect(await credential.balanceOf(vehicle.address, BIRTH_CERT)).to.equal(1);
            expect(await credential.isRegistered(vehicle.address)).to.be.true;
            expect(await credential.vehicleVIN(vehicle.address)).to.equal(TEST_VIN);
            expect(await credential.vinHashToVehicle(vinHash)).to.equal(vehicle.address);
        });

        it("rejects duplicate registration of the same vehicle or VIN", async function () {
            await credential.connect(issuer).registerVehicle(vehicle.address, TEST_VIN);

            await expect(
                credential.connect(issuer).registerVehicle(vehicle.address, "OTHERVIN000000001")
            ).to.be.revertedWith("CVIN1155: vehicle already registered");

            await expect(
                credential.connect(issuer).registerVehicle(newVehicleAddress.address, TEST_VIN)
            ).to.be.revertedWith("CVIN1155: VIN already registered");
        });

        it("rejects registerVehicle from a caller without ISSUER_ROLE (negative authorization)", async function () {
            await expect(
                credential.connect(attacker).registerVehicle(vehicle.address, TEST_VIN)
            ).to.be.revertedWithCustomError(credential, "AccessControlUnauthorizedAccount");
        });
    });

    describe("Credential issuance", function () {
        beforeEach(async function () {
            await credential.connect(issuer).registerVehicle(vehicle.address, TEST_VIN);
        });

        it("issues an INSPECTION_CERT to a registered vehicle and emits CredentialIssued (gas sanity)", async function () {
            const tx = await credential.connect(issuer).issueCredential(vehicle.address, INSPECTION_CERT, 1);
            const receipt = await tx.wait();
            console.log(`        [gas] ERC-1155 issueCredential: ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(credential, "CredentialIssued")
                .withArgs(vehicle.address, INSPECTION_CERT, 1, issuer.address);

            expect(await credential.hasCredential(vehicle.address, INSPECTION_CERT)).to.be.true;
            expect(await credential.balanceOf(vehicle.address, INSPECTION_CERT)).to.equal(1);
        });

        it("rejects issuing to an unregistered vehicle and re-minting BIRTH_CERT via issueCredential", async function () {
            await expect(
                credential.connect(issuer).issueCredential(newVehicleAddress.address, INSURANCE_CERT, 1)
            ).to.be.revertedWith("CVIN1155: vehicle not registered");

            await expect(
                credential.connect(issuer).issueCredential(vehicle.address, BIRTH_CERT, 1)
            ).to.be.revertedWith("CVIN1155: use registerVehicle for BIRTH_CERT");
        });

        it("rejects issueCredential from a non-issuer (negative authorization)", async function () {
            await expect(
                credential.connect(attacker).issueCredential(vehicle.address, MAINTENANCE_BADGE, 1)
            ).to.be.revertedWithCustomError(credential, "AccessControlUnauthorizedAccount");
        });
    });

    describe("Metadata update (per-token URI)", function () {
        it("issuer updates a credential type URI; uri() returns override then falls back (gas sanity)", async function () {
            const baseURI = await credential.uri(REGISTRATION);
            expect(baseURI).to.equal("ipfs://cvin-vehicle-credentials/{id}.json");

            const tx = await credential
                .connect(issuer)
                .setTokenURI(REGISTRATION, "ipfs://registration/v2.json");
            const receipt = await tx.wait();
            console.log(`        [gas] ERC-1155 setTokenURI (update attribute): ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(credential, "CredentialURIUpdated")
                .withArgs(REGISTRATION, "ipfs://registration/v2.json");

            expect(await credential.uri(REGISTRATION)).to.equal("ipfs://registration/v2.json");
            expect(await credential.uri(INSPECTION_CERT)).to.equal(baseURI);
        });

        it("rejects setTokenURI from a non-issuer", async function () {
            await expect(
                credential.connect(attacker).setTokenURI(REGISTRATION, "ipfs://evil")
            ).to.be.revertedWithCustomError(credential, "AccessControlUnauthorizedAccount");
        });
    });

    describe("Revocation (burn)", function () {
        beforeEach(async function () {
            await credential.connect(issuer).registerVehicle(vehicle.address, TEST_VIN);
            await credential.connect(issuer).issueCredential(vehicle.address, INSURANCE_CERT, 1);
        });

        it("issuer revokes a credential; balance goes to zero and CredentialRevoked is emitted (gas sanity)", async function () {
            const tx = await credential.connect(issuer).revokeCredential(vehicle.address, INSURANCE_CERT, 1);
            const receipt = await tx.wait();
            console.log(`        [gas] ERC-1155 revokeCredential (burn): ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(credential, "CredentialRevoked")
                .withArgs(vehicle.address, INSURANCE_CERT, 1, issuer.address);

            expect(await credential.hasCredential(vehicle.address, INSURANCE_CERT)).to.be.false;
        });

        it("burning the BIRTH_CERT deregisters the vehicle identity", async function () {
            const vinHash = ethers.keccak256(ethers.toUtf8Bytes(TEST_VIN));
            await credential.connect(issuer).revokeCredential(vehicle.address, BIRTH_CERT, 1);

            expect(await credential.isRegistered(vehicle.address)).to.be.false;
            expect(await credential.vehicleVIN(vehicle.address)).to.equal("");
            expect(await credential.vinHashToVehicle(vinHash)).to.equal(ethers.ZeroAddress);
        });

        it("rejects revocation from a non-issuer (negative authorization)", async function () {
            await expect(
                credential.connect(attacker).revokeCredential(vehicle.address, INSURANCE_CERT, 1)
            ).to.be.revertedWithCustomError(credential, "AccessControlUnauthorizedAccount");
        });
    });

    describe("Soulbound transfer restrictions", function () {
        beforeEach(async function () {
            await credential.connect(issuer).registerVehicle(vehicle.address, TEST_VIN);
            await credential.connect(issuer).issueCredential(vehicle.address, REGISTRATION, 1);
        });

        it("blocks holder-initiated safeTransferFrom (credentials are soulbound)", async function () {
            await expect(
                credential
                    .connect(vehicle)
                    .safeTransferFrom(vehicle.address, attacker.address, REGISTRATION, 1, "0x")
            ).to.be.revertedWith(
                "CVIN1155: credentials are soulbound (issuer-mediated transfer only)"
            );

            // approval does not help a non-issuer operator either
            await credential.connect(vehicle).setApprovalForAll(attacker.address, true);
            await expect(
                credential
                    .connect(attacker)
                    .safeTransferFrom(vehicle.address, attacker.address, REGISTRATION, 1, "0x")
            ).to.be.revertedWith(
                "CVIN1155: credentials are soulbound (issuer-mediated transfer only)"
            );
        });

        it("issuer-mediated transfer re-binds the identity to a new vehicle address (gas sanity)", async function () {
            const vinHash = ethers.keccak256(ethers.toUtf8Bytes(TEST_VIN));

            const tx = await credential
                .connect(issuer)
                .issuerTransferCredential(vehicle.address, newVehicleAddress.address, BIRTH_CERT);
            const receipt = await tx.wait();
            console.log(`        [gas] ERC-1155 issuerTransferCredential (ownership transfer): ${receipt.gasUsed.toString()}`);

            expect(await credential.isRegistered(vehicle.address)).to.be.false;
            expect(await credential.isRegistered(newVehicleAddress.address)).to.be.true;
            expect(await credential.vehicleVIN(newVehicleAddress.address)).to.equal(TEST_VIN);
            expect(await credential.vinHashToVehicle(vinHash)).to.equal(newVehicleAddress.address);
        });

        it("rejects issuerTransferCredential from a non-issuer", async function () {
            await expect(
                credential
                    .connect(attacker)
                    .issuerTransferCredential(vehicle.address, attacker.address, REGISTRATION)
            ).to.be.revertedWithCustomError(credential, "AccessControlUnauthorizedAccount");
        });
    });

    describe("Interface support", function () {
        it("supports ERC-1155 and AccessControl interfaces", async function () {
            expect(await credential.supportsInterface("0xd9b67a26")).to.be.true; // ERC-1155
            expect(await credential.supportsInterface("0x7965db0b")).to.be.true; // AccessControl
            expect(await credential.supportsInterface("0x01ffc9a7")).to.be.true; // ERC-165
        });
    });
});
