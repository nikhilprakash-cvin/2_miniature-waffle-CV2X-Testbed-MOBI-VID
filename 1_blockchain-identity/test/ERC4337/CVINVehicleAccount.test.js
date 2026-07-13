const { expect } = require("chai");
const { ethers } = require("hardhat");

/**
 * ERC-4337 (Account Abstraction) — CVINVehicleAccount + CVINMinimalEntryPoint
 *
 * The account is deployed directly (identity creation = account deployment)
 * and exercised both via direct owner calls and via a v0.7-shaped
 * PackedUserOperation routed through the minimal entry point, so the gas
 * benchmark can measure the 4337 indirection overhead.
 *
 * Signing: the account validates the EIP-191 personal-sign envelope of the
 * entry point's userOpHash (SimpleAccount pattern), so tests sign with
 * wallet.signMessage(getBytes(userOpHash)).
 */
describe("CVINVehicleAccount (ERC-4337)", function () {
    let entryPoint;
    let account;
    let ownerWallet; // vehicle signing key (we control the private key)
    let bundler, guardian, other, recipient;

    const ATTR_VIN = ethers.keccak256(ethers.toUtf8Bytes("cvin/vehicle/vin"));
    const VIN_VALUE = ethers.toUtf8Bytes("1HGCM82633A004352");

    // Build a v0.7-shaped packed user operation for `account` with `callData`.
    async function buildUserOp(callData, { nonce, signer } = {}) {
        const sender = await account.getAddress();
        const op = {
            sender,
            nonce: nonce !== undefined ? nonce : await entryPoint.nonces(sender),
            initCode: "0x",
            callData,
            accountGasLimits: ethers.ZeroHash, // hashed but not enforced by the harness
            preVerificationGas: 0,
            gasFees: ethers.ZeroHash,
            paymasterAndData: "0x",
            signature: "0x",
        };
        const userOpHash = await entryPoint.getUserOpHash(op);
        const signingKey = signer || ownerWallet;
        // EIP-191 envelope over the raw 32-byte userOpHash
        op.signature = await signingKey.signMessage(ethers.getBytes(userOpHash));
        return op;
    }

    beforeEach(async function () {
        [bundler, guardian, other, recipient] = await ethers.getSigners();

        // Vehicle key as a wallet we fully control (funded for direct calls).
        ownerWallet = ethers.Wallet.createRandom().connect(ethers.provider);
        await bundler.sendTransaction({
            to: ownerWallet.address,
            value: ethers.parseEther("1"),
        });

        const EntryPoint = await ethers.getContractFactory("CVINMinimalEntryPoint");
        entryPoint = await EntryPoint.deploy();
        await entryPoint.waitForDeployment();

        const Account = await ethers.getContractFactory("CVINVehicleAccount");
        account = await Account.deploy(await entryPoint.getAddress(), ownerWallet.address);
        await account.waitForDeployment();
    });

    describe("Identity Creation (account deployment)", function () {
        it("should deploy with owner and entryPoint set, emitting VehicleAccountCreated", async function () {
            expect(await account.owner()).to.equal(ownerWallet.address);
            expect(await account.entryPoint()).to.equal(await entryPoint.getAddress());

            const deploymentTx = account.deploymentTransaction();
            await expect(deploymentTx)
                .to.emit(account, "VehicleAccountCreated")
                .withArgs(
                    await account.getAddress(),
                    ownerWallet.address,
                    await entryPoint.getAddress()
                );

            const receipt = await deploymentTx.wait();
            console.log("       Gas used for identity creation (account deploy):", receipt.gasUsed.toString());
        });

        it("should measure the 4337 indirection: setAttribute direct vs via entry point", async function () {
            // Direct path: owner key calls the account
            const directTx = await account
                .connect(ownerWallet)
                .setAttribute(ATTR_VIN, VIN_VALUE);
            const directReceipt = await directTx.wait();

            // 4337 path: same logical operation as a UserOperation through the
            // minimal entry point (entryPoint -> validateUserOp -> execute -> self)
            const inner = account.interface.encodeFunctionData("setAttribute", [
                ATTR_VIN,
                ethers.hexlify(VIN_VALUE),
            ]);
            const callData = account.interface.encodeFunctionData("execute", [
                await account.getAddress(),
                0,
                inner,
            ]);
            const op = await buildUserOp(callData);
            const opTx = await entryPoint.connect(bundler).handleOp(op);
            const opReceipt = await opTx.wait();

            console.log("       Gas setAttribute direct:        ", directReceipt.gasUsed.toString());
            console.log("       Gas setAttribute via EntryPoint:", opReceipt.gasUsed.toString());
            console.log(
                "       4337 indirection overhead:      ",
                (opReceipt.gasUsed - directReceipt.gasUsed).toString()
            );

            expect(await account.getAttribute(ATTR_VIN)).to.equal(ethers.hexlify(VIN_VALUE));
            expect(opReceipt.gasUsed).to.be.gt(directReceipt.gasUsed);
        });
    });

    describe("UserOperation handling", function () {
        it("should execute a user operation through the entry point and emit UserOperationHandled", async function () {
            const callData = account.interface.encodeFunctionData("setAttribute", [
                ATTR_VIN,
                ethers.hexlify(VIN_VALUE),
            ]);
            const op = await buildUserOp(callData);
            const userOpHash = await entryPoint.getUserOpHash(op);

            await expect(entryPoint.connect(bundler).handleOp(op))
                .to.emit(entryPoint, "UserOperationHandled")
                .withArgs(userOpHash, await account.getAddress(), 0, true);

            expect(await account.getAttribute(ATTR_VIN)).to.equal(ethers.hexlify(VIN_VALUE));
            expect(await entryPoint.nonces(await account.getAddress())).to.equal(1);
        });

        it("should reject a user operation signed by a non-owner key", async function () {
            const attackerWallet = ethers.Wallet.createRandom();
            const callData = account.interface.encodeFunctionData("setAttribute", [
                ATTR_VIN,
                ethers.hexlify(VIN_VALUE),
            ]);
            const op = await buildUserOp(callData, { signer: attackerWallet });

            await expect(entryPoint.connect(bundler).handleOp(op)).to.be.revertedWith(
                "CVINEntryPoint: signature validation failed"
            );
        });

        it("should reject a user operation with a wrong nonce (replay protection)", async function () {
            const callData = account.interface.encodeFunctionData("setAttribute", [
                ATTR_VIN,
                ethers.hexlify(VIN_VALUE),
            ]);

            // Stale nonce
            const staleOp = await buildUserOp(callData, { nonce: 5 });
            await expect(entryPoint.connect(bundler).handleOp(staleOp)).to.be.revertedWith(
                "CVINEntryPoint: invalid nonce"
            );

            // Replay of an already-consumed op
            const op = await buildUserOp(callData);
            await entryPoint.connect(bundler).handleOp(op);
            await expect(entryPoint.connect(bundler).handleOp(op)).to.be.revertedWith(
                "CVINEntryPoint: invalid nonce"
            );
        });

        it("should only allow the entry point to call validateUserOp", async function () {
            const callData = account.interface.encodeFunctionData("setAttribute", [
                ATTR_VIN,
                ethers.hexlify(VIN_VALUE),
            ]);
            const op = await buildUserOp(callData);
            const userOpHash = await entryPoint.getUserOpHash(op);

            await expect(
                account.connect(other).validateUserOp(op, userOpHash, 0)
            ).to.be.revertedWith("CVINVehicleAccount: not entryPoint");
        });
    });

    describe("Execution", function () {
        it("should allow the owner to execute a value transfer from the account", async function () {
            // Fund the vehicle account
            await bundler.sendTransaction({
                to: await account.getAddress(),
                value: ethers.parseEther("0.5"),
            });

            const amount = ethers.parseEther("0.1");
            const balanceBefore = await ethers.provider.getBalance(recipient.address);

            await expect(
                account.connect(ownerWallet).execute(recipient.address, amount, "0x")
            ).to.emit(account, "Executed");

            const balanceAfter = await ethers.provider.getBalance(recipient.address);
            expect(balanceAfter - balanceBefore).to.equal(amount);
        });

        it("should reject execute from non-owner, non-entryPoint callers", async function () {
            await expect(
                account.connect(other).execute(recipient.address, 0, "0x")
            ).to.be.revertedWith("CVINVehicleAccount: not owner or entryPoint");
        });
    });

    describe("Attribute Store (vehicle metadata)", function () {
        it("should set and read attributes, emitting AttributeChanged", async function () {
            await expect(account.connect(ownerWallet).setAttribute(ATTR_VIN, VIN_VALUE))
                .to.emit(account, "AttributeChanged")
                .withArgs(ATTR_VIN, ethers.hexlify(VIN_VALUE));

            expect(await account.getAttribute(ATTR_VIN)).to.equal(ethers.hexlify(VIN_VALUE));
        });

        it("should reject attribute updates from unauthorized callers", async function () {
            await expect(
                account.connect(other).setAttribute(ATTR_VIN, VIN_VALUE)
            ).to.be.revertedWith("CVINVehicleAccount: not owner or entryPoint");
        });
    });

    describe("Key Rotation", function () {
        it("should rotate the signing key while the identity address stays constant", async function () {
            const identityAddress = await account.getAddress();
            const newKey = ethers.Wallet.createRandom().connect(ethers.provider);
            await bundler.sendTransaction({ to: newKey.address, value: ethers.parseEther("1") });

            await expect(account.connect(ownerWallet).transferOwnership(newKey.address))
                .to.emit(account, "OwnershipTransferred")
                .withArgs(ownerWallet.address, newKey.address);

            expect(await account.owner()).to.equal(newKey.address);
            expect(await account.getAddress()).to.equal(identityAddress);

            // Old key is locked out; new key works — both direct and via 4337 ops
            await expect(
                account.connect(ownerWallet).setAttribute(ATTR_VIN, VIN_VALUE)
            ).to.be.revertedWith("CVINVehicleAccount: not owner or entryPoint");

            const callData = account.interface.encodeFunctionData("setAttribute", [
                ATTR_VIN,
                ethers.hexlify(VIN_VALUE),
            ]);
            const op = await buildUserOp(callData, { signer: newKey });
            await entryPoint.connect(bundler).handleOp(op);
            expect(await account.getAttribute(ATTR_VIN)).to.equal(ethers.hexlify(VIN_VALUE));
        });

        it("should not allow rotation to the zero address", async function () {
            await expect(
                account.connect(ownerWallet).transferOwnership(ethers.ZeroAddress)
            ).to.be.revertedWith("CVINVehicleAccount: zero owner");
        });
    });

    describe("Social Recovery (guardian)", function () {
        it("should let the owner set a guardian, emitting GuardianChanged", async function () {
            await expect(account.connect(ownerWallet).setGuardian(guardian.address))
                .to.emit(account, "GuardianChanged")
                .withArgs(ethers.ZeroAddress, guardian.address);

            expect(await account.guardian()).to.equal(guardian.address);
        });

        it("should let the guardian recover the identity to a new signing key", async function () {
            await account.connect(ownerWallet).setGuardian(guardian.address);

            // Vehicle key is lost/compromised — guardian installs a new key
            const recoveredKey = ethers.Wallet.createRandom().connect(ethers.provider);
            await bundler.sendTransaction({
                to: recoveredKey.address,
                value: ethers.parseEther("1"),
            });

            await expect(account.connect(guardian).recoverOwner(recoveredKey.address))
                .to.emit(account, "OwnerRecovered")
                .withArgs(guardian.address, ownerWallet.address, recoveredKey.address);

            expect(await account.owner()).to.equal(recoveredKey.address);

            // Recovered key controls the identity
            await account.connect(recoveredKey).setAttribute(ATTR_VIN, VIN_VALUE);
            expect(await account.getAttribute(ATTR_VIN)).to.equal(ethers.hexlify(VIN_VALUE));
        });

        it("should reject recovery attempts from non-guardians", async function () {
            await account.connect(ownerWallet).setGuardian(guardian.address);

            await expect(
                account.connect(other).recoverOwner(other.address)
            ).to.be.revertedWith("CVINVehicleAccount: not guardian");
        });

        it("should reject guardian changes from unauthorized callers", async function () {
            await expect(
                account.connect(other).setGuardian(other.address)
            ).to.be.revertedWith("CVINVehicleAccount: not owner or entryPoint");
        });
    });
});
