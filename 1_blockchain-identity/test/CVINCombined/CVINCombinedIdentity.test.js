const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

/**
 * CVIN-Combined — the thesis's hybrid: ERC-1056-style event-based identity
 * registry + ERC-735-style on-chain claim storage in a single contract.
 *
 * Claim signatures use the RAW-digest pattern (no EIP-191 envelope), matching
 * how the ERC-1056 reference registry recovers bare keccak256 digests: the
 * issuer wallet signs keccak256(abi.encodePacked(registry, identity, topic,
 * data)) with signingKey.sign(hash) and the contract recovers it with a bare
 * ecrecover.
 */
describe("CVINCombinedIdentity (ERC-1056 + ERC-735 hybrid)", function () {
    let registry;
    let deployer, identity, newOwner, delegate, attacker;
    let issuerWallet; // claim issuer whose private key we control

    const CLAIM_TOPIC_VIN = 1;
    const CLAIM_TOPIC_MANUFACTURER = 2;
    const CLAIM_TOPIC_INSPECTION = 3;
    const SCHEME_ECDSA = 1;

    const DELEGATE_TYPE_VERIKEY = ethers.keccak256(ethers.toUtf8Bytes("veriKey"));
    const ATTR_NAME = ethers.keccak256(ethers.toUtf8Bytes("did/vehicle/firmwareHash"));

    // Sign the raw claim digest with the issuer key; returns 65-byte signature.
    async function signClaim(identityAddress, topic, data, wallet = issuerWallet) {
        const digest = ethers.solidityPackedKeccak256(
            ["address", "address", "uint256", "bytes"],
            [await registry.getAddress(), identityAddress, topic, data]
        );
        const sig = wallet.signingKey.sign(digest);
        return ethers.Signature.from(sig).serialized; // r || s || v (65 bytes)
    }

    function claimIdFor(issuerAddress, topic) {
        return ethers.solidityPackedKeccak256(["address", "uint256"], [issuerAddress, topic]);
    }

    beforeEach(async function () {
        [deployer, identity, newOwner, delegate, attacker] = await ethers.getSigners();
        issuerWallet = ethers.Wallet.createRandom();

        const Registry = await ethers.getContractFactory("CVINCombinedIdentity");
        registry = await Registry.deploy();
        await registry.waitForDeployment();
    });

    describe("Deployment & Identity Creation", function () {
        it("should deploy and expose the safety-critical claim topic constants", async function () {
            expect(await registry.CLAIM_TOPIC_VIN()).to.equal(CLAIM_TOPIC_VIN);
            expect(await registry.CLAIM_TOPIC_MANUFACTURER()).to.equal(CLAIM_TOPIC_MANUFACTURER);
            expect(await registry.CLAIM_TOPIC_INSPECTION()).to.equal(CLAIM_TOPIC_INSPECTION);
            expect(await registry.SCHEME_ECDSA()).to.equal(SCHEME_ECDSA);
        });

        it("should treat every address as a self-owned identity by default (free identity creation)", async function () {
            expect(await registry.identityOwner(identity.address)).to.equal(identity.address);
            expect(await registry.changed(identity.address)).to.equal(0);
        });
    });

    describe("Ownership (ERC-1056 side)", function () {
        it("should change owner and emit DIDOwnerChanged with the previousChange pointer", async function () {
            await expect(registry.connect(identity).changeOwner(identity.address, newOwner.address))
                .to.emit(registry, "DIDOwnerChanged")
                .withArgs(identity.address, newOwner.address, 0);

            expect(await registry.identityOwner(identity.address)).to.equal(newOwner.address);
            expect(await registry.changed(identity.address)).to.be.gt(0);
        });

        it("should let the new owner keep operating after key rotation, and lock out the old key", async function () {
            await registry.connect(identity).changeOwner(identity.address, newOwner.address);

            // Old key locked out
            await expect(
                registry.connect(identity).changeOwner(identity.address, identity.address)
            ).to.be.revertedWith("CVINCombined: unauthorized");

            // New owner operates the identity
            await expect(
                registry.connect(newOwner).setAttribute(identity.address, ATTR_NAME, "0x1234", 86400)
            ).to.emit(registry, "DIDAttributeChanged");
        });

        it("should reject unauthorized owner changes", async function () {
            await expect(
                registry.connect(attacker).changeOwner(identity.address, attacker.address)
            ).to.be.revertedWith("CVINCombined: unauthorized");
        });
    });

    describe("Attributes (event-based, ERC-1056 side)", function () {
        const attrValue = ethers.toUtf8Bytes("sha256:9f86d081884c7d65");

        it("should set an attribute purely via event with validity", async function () {
            const tx = await registry
                .connect(identity)
                .setAttribute(identity.address, ATTR_NAME, attrValue, 86400);
            const currentTime = await time.latest();

            await expect(tx)
                .to.emit(registry, "DIDAttributeChanged")
                .withArgs(identity.address, ATTR_NAME, ethers.hexlify(attrValue), currentTime + 86400, 0);
        });

        it("should revoke an attribute (validTo = 0) and chain previousChange", async function () {
            await registry.connect(identity).setAttribute(identity.address, ATTR_NAME, attrValue, 86400);
            const previousChange = await registry.changed(identity.address);

            await expect(
                registry.connect(identity).revokeAttribute(identity.address, ATTR_NAME, attrValue)
            )
                .to.emit(registry, "DIDAttributeChanged")
                .withArgs(identity.address, ATTR_NAME, ethers.hexlify(attrValue), 0, previousChange);
        });

        it("should reject unauthorized attribute updates", async function () {
            await expect(
                registry.connect(attacker).setAttribute(identity.address, ATTR_NAME, attrValue, 86400)
            ).to.be.revertedWith("CVINCombined: unauthorized");
        });
    });

    describe("Delegates (ERC-1056 side)", function () {
        it("should add a delegate with validity and emit DIDDelegateChanged", async function () {
            const tx = await registry
                .connect(identity)
                .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, 86400);
            const currentTime = await time.latest();

            await expect(tx)
                .to.emit(registry, "DIDDelegateChanged")
                .withArgs(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, currentTime + 86400, 0);

            expect(
                await registry.validDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address)
            ).to.be.true;
        });

        it("should expire delegates after their validity window", async function () {
            await registry
                .connect(identity)
                .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, 3600);

            await time.increase(3601);

            expect(
                await registry.validDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address)
            ).to.be.false;
        });

        it("should revoke a delegate immediately and reject unauthorized delegate ops", async function () {
            await registry
                .connect(identity)
                .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address, 86400);

            await expect(
                registry
                    .connect(identity)
                    .revokeDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address)
            ).to.emit(registry, "DIDDelegateChanged");

            expect(
                await registry.validDelegate(identity.address, DELEGATE_TYPE_VERIKEY, delegate.address)
            ).to.be.false;

            await expect(
                registry
                    .connect(attacker)
                    .addDelegate(identity.address, DELEGATE_TYPE_VERIKEY, attacker.address, 86400)
            ).to.be.revertedWith("CVINCombined: unauthorized");
        });
    });

    describe("Claims (on-chain, ERC-735 side)", function () {
        const vinData = ethers.toUtf8Bytes("1HGCM82633A004352");
        const claimUri = "ipfs://QmVinAttestation";

        it("should add a claim with a real issuer signature (ethers raw-digest signing agrees with ecrecover)", async function () {
            const signature = await signClaim(identity.address, CLAIM_TOPIC_VIN, vinData);
            const claimId = claimIdFor(issuerWallet.address, CLAIM_TOPIC_VIN);

            await expect(
                registry
                    .connect(identity)
                    .addClaim(
                        identity.address,
                        CLAIM_TOPIC_VIN,
                        SCHEME_ECDSA,
                        issuerWallet.address,
                        signature,
                        vinData,
                        claimUri
                    )
            )
                .to.emit(registry, "ClaimAdded")
                .withArgs(
                    claimId,
                    identity.address,
                    CLAIM_TOPIC_VIN,
                    SCHEME_ECDSA,
                    issuerWallet.address,
                    signature,
                    ethers.hexlify(vinData),
                    claimUri
                );

            const [topic, scheme, issuer, sig, data, uri] = await registry.getClaim(
                identity.address,
                claimId
            );
            expect(topic).to.equal(CLAIM_TOPIC_VIN);
            expect(scheme).to.equal(SCHEME_ECDSA);
            expect(issuer).to.equal(issuerWallet.address);
            expect(sig).to.equal(signature);
            expect(data).to.equal(ethers.hexlify(vinData));
            expect(uri).to.equal(claimUri);

            expect(await registry.hasValidClaim(identity.address, CLAIM_TOPIC_VIN, issuerWallet.address))
                .to.be.true;
        });

        it("should reject a claim whose signature does not match the declared issuer", async function () {
            // Signed by a different key than the declared issuer
            const rogueWallet = ethers.Wallet.createRandom();
            const badSignature = await signClaim(identity.address, CLAIM_TOPIC_VIN, vinData, rogueWallet);

            await expect(
                registry
                    .connect(identity)
                    .addClaim(
                        identity.address,
                        CLAIM_TOPIC_VIN,
                        SCHEME_ECDSA,
                        issuerWallet.address,
                        badSignature,
                        vinData,
                        claimUri
                    )
            ).to.be.revertedWith("CVINCombined: invalid claim signature");
        });

        it("should reject a valid signature over different data (tamper detection)", async function () {
            const signature = await signClaim(identity.address, CLAIM_TOPIC_VIN, vinData);
            const tamperedData = ethers.toUtf8Bytes("1HGCM82633A999999");

            await expect(
                registry
                    .connect(identity)
                    .addClaim(
                        identity.address,
                        CLAIM_TOPIC_VIN,
                        SCHEME_ECDSA,
                        issuerWallet.address,
                        signature,
                        tamperedData,
                        claimUri
                    )
            ).to.be.revertedWith("CVINCombined: invalid claim signature");
        });

        it("should reject claim additions from non-owners of the identity", async function () {
            const signature = await signClaim(identity.address, CLAIM_TOPIC_VIN, vinData);

            await expect(
                registry
                    .connect(attacker)
                    .addClaim(
                        identity.address,
                        CLAIM_TOPIC_VIN,
                        SCHEME_ECDSA,
                        issuerWallet.address,
                        signature,
                        vinData,
                        claimUri
                    )
            ).to.be.revertedWith("CVINCombined: unauthorized");
        });

        it("should index claims by topic across the safety-critical subset", async function () {
            const manufacturerWallet = ethers.Wallet.createRandom();
            const inspectionData = ethers.toUtf8Bytes("inspection:2026-06-30:pass");

            await registry
                .connect(identity)
                .addClaim(
                    identity.address,
                    CLAIM_TOPIC_VIN,
                    SCHEME_ECDSA,
                    issuerWallet.address,
                    await signClaim(identity.address, CLAIM_TOPIC_VIN, vinData),
                    vinData,
                    claimUri
                );

            await registry
                .connect(identity)
                .addClaim(
                    identity.address,
                    CLAIM_TOPIC_INSPECTION,
                    SCHEME_ECDSA,
                    manufacturerWallet.address,
                    await signClaim(identity.address, CLAIM_TOPIC_INSPECTION, inspectionData, manufacturerWallet),
                    inspectionData,
                    "ipfs://QmInspection"
                );

            const vinIds = await registry.getClaimIdsByTopic(identity.address, CLAIM_TOPIC_VIN);
            const inspectionIds = await registry.getClaimIdsByTopic(identity.address, CLAIM_TOPIC_INSPECTION);
            expect(vinIds).to.deep.equal([claimIdFor(issuerWallet.address, CLAIM_TOPIC_VIN)]);
            expect(inspectionIds).to.deep.equal([
                claimIdFor(manufacturerWallet.address, CLAIM_TOPIC_INSPECTION),
            ]);
        });

        it("should remove (revoke) a claim, emitting ClaimRemoved and clearing storage", async function () {
            const signature = await signClaim(identity.address, CLAIM_TOPIC_VIN, vinData);
            const claimId = claimIdFor(issuerWallet.address, CLAIM_TOPIC_VIN);

            await registry
                .connect(identity)
                .addClaim(
                    identity.address,
                    CLAIM_TOPIC_VIN,
                    SCHEME_ECDSA,
                    issuerWallet.address,
                    signature,
                    vinData,
                    claimUri
                );

            await expect(registry.connect(identity).removeClaim(identity.address, claimId))
                .to.emit(registry, "ClaimRemoved")
                .withArgs(claimId, identity.address, CLAIM_TOPIC_VIN, issuerWallet.address);

            const [, , issuer] = await registry.getClaim(identity.address, claimId);
            expect(issuer).to.equal(ethers.ZeroAddress);
            expect(await registry.getClaimIdsByTopic(identity.address, CLAIM_TOPIC_VIN)).to.deep.equal([]);
            expect(await registry.hasValidClaim(identity.address, CLAIM_TOPIC_VIN, issuerWallet.address))
                .to.be.false;
        });

        it("should reject claim removal from parties that are neither owner nor issuer", async function () {
            const signature = await signClaim(identity.address, CLAIM_TOPIC_VIN, vinData);
            const claimId = claimIdFor(issuerWallet.address, CLAIM_TOPIC_VIN);

            await registry
                .connect(identity)
                .addClaim(
                    identity.address,
                    CLAIM_TOPIC_VIN,
                    SCHEME_ECDSA,
                    issuerWallet.address,
                    signature,
                    vinData,
                    claimUri
                );

            await expect(
                registry.connect(attacker).removeClaim(identity.address, claimId)
            ).to.be.revertedWith("CVINCombined: unauthorized");
        });
    });

    describe("Gas Costs (hybrid benchmark)", function () {
        it("should measure gas for the hybrid's core operations", async function () {
            // Event-based side (expected cheap)
            const ownerTx = await registry.connect(identity).changeOwner(identity.address, newOwner.address);
            const ownerReceipt = await ownerTx.wait();
            console.log("       Gas changeOwner (event-based):", ownerReceipt.gasUsed.toString());

            const attrTx = await registry
                .connect(newOwner)
                .setAttribute(identity.address, ATTR_NAME, ethers.toUtf8Bytes("fw-v2.4.1"), 86400);
            const attrReceipt = await attrTx.wait();
            console.log("       Gas setAttribute (event-based):", attrReceipt.gasUsed.toString());

            // On-chain claim side (expected costlier, buys O(1) verification)
            const vinData = ethers.toUtf8Bytes("1HGCM82633A004352");
            const signature = await signClaim(identity.address, CLAIM_TOPIC_VIN, vinData);
            const claimTx = await registry
                .connect(newOwner)
                .addClaim(
                    identity.address,
                    CLAIM_TOPIC_VIN,
                    SCHEME_ECDSA,
                    issuerWallet.address,
                    signature,
                    vinData,
                    "ipfs://QmVinAttestation"
                );
            const claimReceipt = await claimTx.wait();
            console.log("       Gas addClaim (on-chain + ecrecover):", claimReceipt.gasUsed.toString());

            // Sanity bounds consistent with the thesis hypothesis
            expect(attrReceipt.gasUsed).to.be.lt(80000); // events are cheap
            expect(claimReceipt.gasUsed).to.be.gt(attrReceipt.gasUsed); // storage+ecrecover costs more
        });
    });
});
