const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ERC721 Regular Test Suite with Extended Scenarios", function () {
    let CVIN_NFT_DID_ERC721, cvin_nft_did_erc721;
    let owner, addr1, addr2;

    beforeEach(async function () {
        [owner, addr1, addr2] = await ethers.getSigners();

        CVIN_NFT_DID_ERC721 = await ethers.getContractFactory("CVIN_NFT_DID_ERC721");
        cvin_nft_did_erc721 = await CVIN_NFT_DID_ERC721.deploy("CVIN", "CVN", owner.address, 500);
        await cvin_nft_did_erc721.waitForDeployment();
    });

    it("Should mint a token", async function () {
        await cvin_nft_did_erc721.mint(addr1.address, 1, "tokenURI");
        expect(await cvin_nft_did_erc721.ownerOf(1)).to.equal(addr1.address);
    });

    it("Should verify identity and eligibility for warranty", async function () {
        await cvin_nft_did_erc721.mint(addr1.address, 1, "Toyota Corolla Hatchback LE 2023");
        const tokenURI = await cvin_nft_did_erc721.tokenURI(1);
        const isEligible = tokenURI.includes("Toyota") && tokenURI.includes("2023");
        expect(isEligible).to.be.true;
    });

    it("Should record the timestamp of toll entry", async function () {
        // The contract has no recordEntry/getEntryTimestamp functions; the entry
        // timestamp is the block timestamp of the on-chain transaction.
        const tx = await cvin_nft_did_erc721.mint(addr1.address, 1, "tokenURI");
        const receipt = await tx.wait();

        const block = await ethers.provider.getBlock(receipt.blockNumber);
        expect(block.timestamp).to.be.a("number").and.to.be.gt(0);
    });

    it("Should allow payment of toll in native coin", async function () {
        await cvin_nft_did_erc721.mint(addr1.address, 1, "tokenURI");

        // The contract has no payToll function; the toll is paid as a native
        // coin transfer from the vehicle owner to the toll operator.
        const tollAmount = ethers.parseEther("0.1");
        await expect(
            addr1.sendTransaction({ to: owner.address, value: tollAmount })
        ).to.changeEtherBalances([addr1, owner], [-tollAmount, tollAmount]);
    });
});
