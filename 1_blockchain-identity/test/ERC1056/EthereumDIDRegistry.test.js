const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("EthereumDIDRegistry (ERC-1056)", function () {
    let didRegistry;
    let owner, identity, delegate, newOwner, attacker;

    const DELEGATE_TYPE_VERIKEY = ethers.keccak256(ethers.toUtf8Bytes("veriKey"));
    const DELEGATE_TYPE_SIGAUTH = ethers.keccak256(ethers.toUtf8Bytes("sigAuth"));
    const ATTR_NAME = ethers.keccak256(ethers.toUtf8Bytes("did/pub/Ed25519/veriKey"));

    beforeEach(async function () {
        [owner, identity, delegate, newOwner, attacker] = await ethers.getSigners();

        const DIDRegistry = await ethers.getContractFactory("EthereumDIDRegistry");
        didRegistry = await DIDRegistry.deploy();
        await didRegistry.waitForDeployment();
    });

    describe("Owner Management", function () {
        it("should return identity as default owner", async function () {
            expect(await didRegistry.identityOwner(identity.address)).to.equal(identity.address);
        });

        it("should allow identity to change owner", async function () {
            const tx = await didRegistry.connect(identity).changeOwner(identity.address, newOwner.address);
            await expect(tx)
                .to.emit(didRegistry, "DIDOwnerChanged")
                .withArgs(identity.address, newOwner.address, 0);

            expect(await didRegistry.identityOwner(identity.address)).to.equal(newOwner.address);
        });

        it("should not allow unauthorized owner change", async function () {
            await expect(
                didRegistry.connect(attacker).changeOwner(identity.address, attacker.address)
            ).to.be.revertedWith("DIDRegistry: unauthorized");
        });

        it("should allow new owner to make changes", async function () {
            await didRegistry.connect(identity).changeOwner(identity.address, newOwner.address);

            await expect(
                didRegistry.connect(newOwner).changeOwner(identity.address, attacker.address)
            ).to.emit(didRegistry, "DIDOwnerChanged");

            expect(await didRegistry.identityOwner(identity.address)).to.equal(attacker.address);
        });

        it("should increment nonce on signed owner change", async function () {
            // Use a wallet whose private key we control so we can sign the raw
            // digest (the contract recovers over the bare hash, not an
            // EIP-191 "Ethereum Signed Message" envelope).
            const identityWallet = ethers.Wallet.createRandom();

            const nonceBefore = await didRegistry.nonce(identityWallet.address);

            // Create signature for changeOwnerSigned:
            // keccak256(0x19, 0x00, registry, nonce, identity, "changeOwner", newOwner)
            const hash = ethers.solidityPackedKeccak256(
                ["bytes1", "bytes1", "address", "uint256", "address", "string", "address"],
                ["0x19", "0x00", await didRegistry.getAddress(), nonceBefore, identityWallet.address, "changeOwner", newOwner.address]
            );

            const sig = identityWallet.signingKey.sign(hash);

            await didRegistry.changeOwnerSigned(
                identityWallet.address,
                sig.v,
                sig.r,
                sig.s,
                newOwner.address
            );

            const nonceAfter = await didRegistry.nonce(identityWallet.address);
            expect(nonceAfter).to.equal(nonceBefore + 1n);

            expect(await didRegistry.identityOwner(identityWallet.address)).to.equal(newOwner.address);
        });
    });

    describe("Delegate Management", function () {
        const validityPeriod = 86400; // 1 day

        it("should add delegate", async function () {
            const tx = await didRegistry
                .connect(identity)
                .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, validityPeriod);

            const currentTime = await time.latest();
            await expect(tx)
                .to.emit(didRegistry, "DIDDelegateChanged")
                .withArgs(
                    identity.address,
                    DELEGATE_TYPE_VERIKEY,
                    delegate.address,
                    currentTime + validityPeriod,
                    0
                );

            expect(
                await didRegistry.validDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address)
            ).to.be.true;
        });

        it("should not allow unauthorized delegate addition", async function () {
            await expect(
                didRegistry
                    .connect(attacker)
                    .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, validityPeriod)
            ).to.be.revertedWith("DIDRegistry: unauthorized");
        });

        it("should invalidate delegate after expiration", async function () {
            await didRegistry
                .connect(identity)
                .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, validityPeriod);

            // Fast forward time past validity period
            await time.increase(validityPeriod + 1);

            expect(
                await didRegistry.validDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address)
            ).to.be.false;
        });

        it("should revoke delegate", async function () {
            await didRegistry
                .connect(identity)
                .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, validityPeriod);

            // The event emits the previousChange block, i.e. changed[] as it was
            // BEFORE the revoke tx updates it — capture it before sending.
            const previousChange = await didRegistry.changed(identity.address);

            const tx = await didRegistry
                .connect(identity)
                .revokeDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address);

            await expect(tx)
                .to.emit(didRegistry, "DIDDelegateChanged")
                .withArgs(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, 0, previousChange);

            expect(
                await didRegistry.validDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address)
            ).to.be.false;
        });

        it("should support multiple delegate types", async function () {
            await didRegistry
                .connect(identity)
                .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, validityPeriod);

            await didRegistry
                .connect(identity)
                .addDelegate(identity.address, DELEGATE_TYPE_SIGAUTH, delegate.address, validityPeriod);

            expect(
                await didRegistry.validDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address)
            ).to.be.true;

            expect(
                await didRegistry.validDelegate(identity.address, DELEGATE_TYPE_SIGAUTH, delegate.address)
            ).to.be.true;
        });
    });

    describe("Attribute Management", function () {
        const validityPeriod = 86400;
        const attributeValue = ethers.toUtf8Bytes("Ed25519PublicKey");

        it("should set attribute", async function () {
            const tx = await didRegistry
                .connect(identity)
                .setAttribute(identity.address, ATTR_NAME, attributeValue, validityPeriod);

            const currentTime = await time.latest();
            await expect(tx)
                .to.emit(didRegistry, "DIDAttributeChanged")
                .withArgs(
                    identity.address,
                    ATTR_NAME,
                    ethers.hexlify(attributeValue),
                    currentTime + validityPeriod,
                    0
                );
        });

        it("should not allow unauthorized attribute setting", async function () {
            await expect(
                didRegistry
                    .connect(attacker)
                    .setAttribute(identity.address, ATTR_NAME, attributeValue, validityPeriod)
            ).to.be.revertedWith("DIDRegistry: unauthorized");
        });

        it("should revoke attribute", async function () {
            await didRegistry
                .connect(identity)
                .setAttribute(identity.address, ATTR_NAME, attributeValue, validityPeriod);

            // The event emits the previousChange block, i.e. changed[] as it was
            // BEFORE the revoke tx updates it — capture it before sending.
            const previousChange = await didRegistry.changed(identity.address);

            const tx = await didRegistry
                .connect(identity)
                .revokeAttribute(identity.address, ATTR_NAME, attributeValue);

            await expect(tx)
                .to.emit(didRegistry, "DIDAttributeChanged")
                .withArgs(identity.address, ATTR_NAME, ethers.hexlify(attributeValue), 0, previousChange);
        });

        it("should support service endpoint attributes", async function () {
            const serviceName = ethers.keccak256(ethers.toUtf8Bytes("did/svc/CredentialService"));
            const serviceEndpoint = ethers.toUtf8Bytes("https://credentials.cvin.network");

            await expect(
                didRegistry
                    .connect(identity)
                    .setAttribute(identity.address, serviceName, serviceEndpoint, validityPeriod)
            ).to.emit(didRegistry, "DIDAttributeChanged");
        });
    });

    describe("Changed Tracking", function () {
        it("should track last changed block", async function () {
            const changedBefore = await didRegistry.changed(identity.address);
            expect(changedBefore).to.equal(0);

            await didRegistry.connect(identity).changeOwner(identity.address, newOwner.address);

            const changedAfter = await didRegistry.changed(identity.address);
            expect(changedAfter).to.be.gt(0);
        });

        it("should update changed on delegate operations", async function () {
            await didRegistry
                .connect(identity)
                .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, 86400);

            const changedAfterAdd = await didRegistry.changed(identity.address);

            await didRegistry
                .connect(identity)
                .revokeDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address);

            const changedAfterRevoke = await didRegistry.changed(identity.address);
            expect(changedAfterRevoke).to.be.gt(changedAfterAdd);
        });
    });

    describe("Gas Costs", function () {
        it("should measure gas for owner change", async function () {
            const tx = await didRegistry.connect(identity).changeOwner(identity.address, newOwner.address);
            const receipt = await tx.wait();
            console.log("       Gas used for changeOwner:", receipt.gasUsed.toString());
            // Bound tracks solc 0.8.20 + OZ 5.0.2 toolchain (measured ~68.9k)
            expect(receipt.gasUsed).to.be.lt(80000);
        });

        it("should measure gas for add delegate", async function () {
            const tx = await didRegistry
                .connect(identity)
                .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, 86400);
            const receipt = await tx.wait();
            console.log("       Gas used for addDelegate:", receipt.gasUsed.toString());
            expect(receipt.gasUsed).to.be.lt(80000);
        });

        it("should measure gas for set attribute", async function () {
            const tx = await didRegistry
                .connect(identity)
                .setAttribute(
                    identity.address,
                    ATTR_NAME,
                    ethers.toUtf8Bytes("Ed25519PublicKey"),
                    86400
                );
            const receipt = await tx.wait();
            console.log("       Gas used for setAttribute:", receipt.gasUsed.toString());
            expect(receipt.gasUsed).to.be.lt(80000);
        });
    });
});
