const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CVINVehicleLSP8 (LSP8 Identifiable Digital Asset, representative)", function () {
    let lsp8;
    let authority, vehicleOwner, buyer, newAuthority, attacker;

    const TEST_VIN = "1HGBH41JXMN109186";
    const TOKEN_ID = ethers.keccak256(ethers.toUtf8Bytes(TEST_VIN)); // bytes32 tokenId = keccak256(VIN)

    beforeEach(async function () {
        [authority, vehicleOwner, buyer, newAuthority, attacker] = await ethers.getSigners();

        const LSP8 = await ethers.getContractFactory("CVINVehicleLSP8");
        lsp8 = await LSP8.connect(authority).deploy("CVIN Vehicle Identity LSP8", "CVIN-LSP8");
        await lsp8.waitForDeployment();
    });

    describe("Deployment", function () {
        it("deploys with name, symbol and issuing authority as owner (gas sanity)", async function () {
            const receipt = await lsp8.deploymentTransaction().wait();
            console.log(`        [gas] LSP8 deploy: ${receipt.gasUsed.toString()}`);

            expect(await lsp8.name()).to.equal("CVIN Vehicle Identity LSP8");
            expect(await lsp8.symbol()).to.equal("CVIN-LSP8");
            expect(await lsp8.owner()).to.equal(authority.address);
            expect(await lsp8.totalSupply()).to.equal(0);
        });

        it("derives bytes32 tokenIds as keccak256(VIN)", async function () {
            expect(await lsp8.tokenIdForVIN(TEST_VIN)).to.equal(TOKEN_ID);
        });
    });

    describe("Identity creation (mintVehicle)", function () {
        it("mints a vehicle token, stores the VIN in the token data store, emits LSP8 Transfer (gas sanity)", async function () {
            const tx = await lsp8.connect(authority).mintVehicle(vehicleOwner.address, TEST_VIN);
            const receipt = await tx.wait();
            console.log(`        [gas] LSP8 mintVehicle (create identity): ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(lsp8, "Transfer")
                .withArgs(authority.address, ethers.ZeroAddress, vehicleOwner.address, TOKEN_ID, true, "0x");
            await expect(tx)
                .to.emit(lsp8, "VehicleMinted")
                .withArgs(TOKEN_ID, TEST_VIN, vehicleOwner.address);

            expect(await lsp8.tokenOwnerOf(TOKEN_ID)).to.equal(vehicleOwner.address);
            expect(await lsp8.balanceOf(vehicleOwner.address)).to.equal(1);
            expect(await lsp8.totalSupply()).to.equal(1);
            expect(await lsp8.exists(TOKEN_ID)).to.be.true;

            const tokenIds = await lsp8.tokenIdsOf(vehicleOwner.address);
            expect(tokenIds).to.deep.equal([TOKEN_ID]);

            const vinKey = await lsp8.DATA_KEY_VIN();
            const storedVin = await lsp8.getDataForTokenId(TOKEN_ID, vinKey);
            expect(ethers.toUtf8String(storedVin)).to.equal(TEST_VIN);
        });

        it("rejects minting the same VIN twice", async function () {
            await lsp8.connect(authority).mintVehicle(vehicleOwner.address, TEST_VIN);
            await expect(
                lsp8.connect(authority).mintVehicle(buyer.address, TEST_VIN)
            ).to.be.revertedWith("LSP8: tokenId already minted");
        });

        it("rejects mint from a caller that is not the issuing authority (negative authorization)", async function () {
            await expect(
                lsp8.connect(attacker).mintVehicle(attacker.address, TEST_VIN)
            ).to.be.revertedWith("LSP8: caller is not the contract owner");
        });
    });

    describe("Per-token data store (setDataForTokenId / getDataForTokenId)", function () {
        beforeEach(async function () {
            await lsp8.connect(authority).mintVehicle(vehicleOwner.address, TEST_VIN);
        });

        it("authority sets token data and emits TokenIdDataChanged + DataChanged (gas sanity)", async function () {
            const inspectionKey = await lsp8.DATA_KEY_INSPECTION();
            const value = ethers.toUtf8Bytes("inspection:2026-07-13:pass");

            const tx = await lsp8.connect(authority).setDataForTokenId(TOKEN_ID, inspectionKey, value);
            const receipt = await tx.wait();
            console.log(`        [gas] LSP8 setDataForTokenId (update attribute): ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(lsp8, "TokenIdDataChanged")
                .withArgs(TOKEN_ID, inspectionKey, value);
            await expect(tx)
                .to.emit(lsp8, "DataChanged")
                .withArgs(inspectionKey, value);

            const stored = await lsp8.getDataForTokenId(TOKEN_ID, inspectionKey);
            expect(ethers.toUtf8String(stored)).to.equal("inspection:2026-07-13:pass");
        });

        it("supports batch data writes and reads", async function () {
            const regKey = await lsp8.DATA_KEY_REGISTRATION();
            const insKey = await lsp8.DATA_KEY_INSURANCE();
            const regVal = ethers.toUtf8Bytes("ON-CANADA-REG-2026");
            const insVal = ethers.toUtf8Bytes("policy:ABC-777");

            await lsp8
                .connect(authority)
                .setDataBatchForTokenIds([TOKEN_ID, TOKEN_ID], [regKey, insKey], [regVal, insVal]);

            const values = await lsp8.getDataBatchForTokenIds([TOKEN_ID, TOKEN_ID], [regKey, insKey]);
            expect(ethers.toUtf8String(values[0])).to.equal("ON-CANADA-REG-2026");
            expect(ethers.toUtf8String(values[1])).to.equal("policy:ABC-777");
        });

        it("rejects setDataForTokenId from a non-authority caller (negative authorization)", async function () {
            const inspectionKey = await lsp8.DATA_KEY_INSPECTION();
            await expect(
                lsp8.connect(attacker).setDataForTokenId(TOKEN_ID, inspectionKey, "0x1234")
            ).to.be.revertedWith("LSP8: caller is not the contract owner");
        });

        it("rejects setDataForTokenId for a non-existent tokenId", async function () {
            const bogusId = ethers.keccak256(ethers.toUtf8Bytes("NOSUCHVIN"));
            await expect(
                lsp8.connect(authority).setDataForTokenId(bogusId, await lsp8.DATA_KEY_VIN(), "0x00")
            ).to.be.revertedWith("LSP8: tokenId does not exist");
        });
    });

    describe("Transfer (LSP8 signature: from, to, tokenId, force, data)", function () {
        beforeEach(async function () {
            await lsp8.connect(authority).mintVehicle(vehicleOwner.address, TEST_VIN);
        });

        it("token owner transfers the vehicle to a new owner with force=true (gas sanity)", async function () {
            const tx = await lsp8
                .connect(vehicleOwner)
                .transfer(vehicleOwner.address, buyer.address, TOKEN_ID, true, "0x");
            const receipt = await tx.wait();
            console.log(`        [gas] LSP8 transfer (vehicle ownership): ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(lsp8, "Transfer")
                .withArgs(vehicleOwner.address, vehicleOwner.address, buyer.address, TOKEN_ID, true, "0x");

            expect(await lsp8.tokenOwnerOf(TOKEN_ID)).to.equal(buyer.address);
            expect(await lsp8.balanceOf(vehicleOwner.address)).to.equal(0);
            expect(await lsp8.balanceOf(buyer.address)).to.equal(1);
            expect(await lsp8.tokenIdsOf(buyer.address)).to.deep.equal([TOKEN_ID]);
        });

        it("rejects transfer to an EOA when force=false (no LSP1 probing, documented omission)", async function () {
            await expect(
                lsp8
                    .connect(vehicleOwner)
                    .transfer(vehicleOwner.address, buyer.address, TOKEN_ID, false, "0x")
            ).to.be.revertedWith("LSP8: recipient is an EOA (use force=true)");
        });

        it("rejects transfer initiated by a non-token-owner (operators are not implemented)", async function () {
            await expect(
                lsp8
                    .connect(attacker)
                    .transfer(vehicleOwner.address, attacker.address, TOKEN_ID, true, "0x")
            ).to.be.revertedWith("LSP8: caller is not the token owner");

            // even the issuing authority cannot move a token it does not own
            await expect(
                lsp8
                    .connect(authority)
                    .transfer(vehicleOwner.address, buyer.address, TOKEN_ID, true, "0x")
            ).to.be.revertedWith("LSP8: caller is not the token owner");
        });

        it("rejects transfer with a mismatched from address or to the zero address", async function () {
            await expect(
                lsp8.connect(vehicleOwner).transfer(buyer.address, attacker.address, TOKEN_ID, true, "0x")
            ).to.be.revertedWith("LSP8: transfer from incorrect owner");

            await expect(
                lsp8.connect(vehicleOwner).transfer(vehicleOwner.address, ethers.ZeroAddress, TOKEN_ID, true, "0x")
            ).to.be.revertedWith("LSP8: transfer to zero address");
        });
    });

    describe("Revocation (revokeVehicle = burn)", function () {
        beforeEach(async function () {
            await lsp8.connect(authority).mintVehicle(vehicleOwner.address, TEST_VIN);
        });

        it("issuing authority revokes a vehicle token; emits Transfer to zero address (gas sanity)", async function () {
            const tx = await lsp8.connect(authority).revokeVehicle(TOKEN_ID, "0x");
            const receipt = await tx.wait();
            console.log(`        [gas] LSP8 revokeVehicle (burn): ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(lsp8, "Transfer")
                .withArgs(authority.address, vehicleOwner.address, ethers.ZeroAddress, TOKEN_ID, true, "0x");
            await expect(tx)
                .to.emit(lsp8, "VehicleRevoked")
                .withArgs(TOKEN_ID, vehicleOwner.address);

            expect(await lsp8.exists(TOKEN_ID)).to.be.false;
            expect(await lsp8.totalSupply()).to.equal(0);
            expect(await lsp8.balanceOf(vehicleOwner.address)).to.equal(0);
            await expect(lsp8.tokenOwnerOf(TOKEN_ID)).to.be.revertedWith("LSP8: tokenId does not exist");
        });

        it("token owner can also burn their own vehicle token", async function () {
            await expect(lsp8.connect(vehicleOwner).revokeVehicle(TOKEN_ID, "0x"))
                .to.emit(lsp8, "VehicleRevoked")
                .withArgs(TOKEN_ID, vehicleOwner.address);
            expect(await lsp8.exists(TOKEN_ID)).to.be.false;
        });

        it("rejects revocation from a caller that is neither authority nor token owner", async function () {
            await expect(
                lsp8.connect(attacker).revokeVehicle(TOKEN_ID, "0x")
            ).to.be.revertedWith("LSP8: caller is not authority nor token owner");
        });
    });

    describe("Issuing-authority ownership transfer", function () {
        it("transfers contract ownership and enforces new authority (gas sanity)", async function () {
            const tx = await lsp8.connect(authority).transferOwnership(newAuthority.address);
            const receipt = await tx.wait();
            console.log(`        [gas] LSP8 transferOwnership: ${receipt.gasUsed.toString()}`);

            await expect(tx)
                .to.emit(lsp8, "OwnershipTransferred")
                .withArgs(authority.address, newAuthority.address);
            expect(await lsp8.owner()).to.equal(newAuthority.address);

            await expect(
                lsp8.connect(authority).mintVehicle(vehicleOwner.address, TEST_VIN)
            ).to.be.revertedWith("LSP8: caller is not the contract owner");
            await expect(
                lsp8.connect(newAuthority).mintVehicle(vehicleOwner.address, TEST_VIN)
            ).to.emit(lsp8, "VehicleMinted");
        });

        it("rejects ownership transfer from non-owner", async function () {
            await expect(
                lsp8.connect(attacker).transferOwnership(attacker.address)
            ).to.be.revertedWith("LSP8: caller is not the contract owner");
        });
    });
});
