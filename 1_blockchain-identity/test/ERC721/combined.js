const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ERC721 Combined Test Suite", function () {
    let CVIN_NFT_DID_ERC721, cvin_nft_did_erc721;
    let owner, addr1, addr2;

    beforeEach(async function () {
        [owner, addr1, addr2] = await ethers.getSigners();

        CVIN_NFT_DID_ERC721 = await ethers.getContractFactory("CVIN_NFT_DID_ERC721");
        cvin_nft_did_erc721 = await CVIN_NFT_DID_ERC721.deploy("CVIN", "CVN", owner.address, 500);
        await cvin_nft_did_erc721.waitForDeployment();
    });

    describe("Regular ERC721", function () {
        it("Should return the correct name and symbol", async function () {
            expect(await cvin_nft_did_erc721.name()).to.equal("CVIN");
            expect(await cvin_nft_did_erc721.symbol()).to.equal("CVN");
        });

        it("Should mint a token", async function () {
            await cvin_nft_did_erc721.mint(addr1.address, 1, "tokenURI");
            expect(await cvin_nft_did_erc721.ownerOf(1)).to.equal(addr1.address);
        });
    });

    // Note: the previous "Monolithic ERC721" tests were removed because the
    // CVIN_NFT_DID_ERC721_Monolithic contract only exists as a .sol.bak file
    // and is not part of the compiled contract set.
    describe("Royalty (ERC2981)", function () {
        it("Should report the default royalty configured at deployment", async function () {
            await cvin_nft_did_erc721.mint(addr1.address, 1, "tokenURI");

            const salePrice = ethers.parseEther("1");
            const [receiver, royaltyAmount] = await cvin_nft_did_erc721.royaltyInfo(1, salePrice);

            expect(receiver).to.equal(owner.address);
            // 500 basis points = 5%
            expect(royaltyAmount).to.equal((salePrice * 500n) / 10000n);
        });
    });
});
