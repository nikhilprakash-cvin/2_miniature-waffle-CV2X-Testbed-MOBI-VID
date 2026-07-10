const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ERC721 Identity-Based Transaction Test Suite", function () {
    let CVIN_NFT_DID_ERC721, cvin_nft_did_erc721;
    let owner, addr1, addr2;

    beforeEach(async function () {
        [owner, addr1, addr2] = await ethers.getSigners();

        CVIN_NFT_DID_ERC721 = await ethers.getContractFactory("CVIN_NFT_DID_ERC721");
        cvin_nft_did_erc721 = await CVIN_NFT_DID_ERC721.deploy("CVIN", "CVN", owner.address, 500);
        await cvin_nft_did_erc721.waitForDeployment();
    });

    it("Should verify identity and pay toll", async function () {
        await cvin_nft_did_erc721.mint(addr1.address, 1, "Toyota Corolla Hatchback LE 2023");

        // Verify the identity of the car via its NFT metadata
        const tokenURI = await cvin_nft_did_erc721.tokenURI(1);
        const isVerified = tokenURI.includes("Toyota") && tokenURI.includes("2023");
        expect(isVerified).to.be.true;

        // The vehicle holder must own the identity NFT
        expect(await cvin_nft_did_erc721.ownerOf(1)).to.equal(addr1.address);

        // Pay the toll after verification. The contract has no payToll function;
        // toll settlement is a native coin transfer from the verified vehicle
        // owner to the toll operator.
        const tollAmount = ethers.parseEther("0.1");
        await expect(
            addr1.sendTransaction({ to: owner.address, value: tollAmount })
        ).to.changeEtherBalances([addr1, owner], [-tollAmount, tollAmount]);
    });
});
