const { expect } = require("chai");

describe("ERC721 Regular Test Suite with Extended Scenarios", function () {
    let CVIN_NFT_DID_ERC721, cvin_nft_did_erc721;
    let owner, addr1, addr2;

    beforeEach(async function () {
        [owner, addr1, addr2, _] = await ethers.getSigners();

        CVIN_NFT_DID_ERC721 = await ethers.getContractFactory("CVIN_NFT_DID_ERC721");
        cvin_nft_did_erc721 = await CVIN_NFT_DID_ERC721.deploy("CVIN", "CVN", owner.address, 500);
        await cvin_nft_did_erc721.deployed();
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
        await cvin_nft_did_erc721.mint(addr1.address, 1, "tokenURI");
        const timestamp = Math.floor(Date.now() / 1000); // current timestamp in seconds
        const tx = await cvin_nft_did_erc721.recordEntry(1, timestamp);
        await tx.wait();

        // Assuming the contract has a mapping to store timestamps
        expect(await cvin_nft_did_erc721.getEntryTimestamp(1)).to.equal(timestamp);
    });

    it("Should allow payment of toll in native coin", async function () {
        await cvin_nft_did_erc721.mint(addr1.address, 1, "tokenURI");

        // Assuming the contract has a function to handle toll payments
        const tollAmount = ethers.utils.parseEther("0.1");
        await expect(() =>
            cvin_nft_did_erc721.connect(addr1).payToll(1, { value: tollAmount })
        ).to.changeEtherBalance(addr1, -tollAmount);
    });
});
