const hre = require("hardhat");

async function main() {
    const [deployer] = await hre.ethers.getSigners();

    console.log("Deploying contracts with the account:", deployer.address);

    const CVIN_NFT_DID_ERC721_Monolithic = await hre.ethers.getContractFactory("CVIN_NFT_DID_ERC721_Monolithic");
    const cvin_nft_did_erc721_monolithic = await CVIN_NFT_DID_ERC721_Monolithic.deploy("CVIN", "CVN", deployer.address, 500);

    await cvin_nft_did_erc721_monolithic.deployed();

    console.log("CVIN_NFT_DID_ERC721_Monolithic deployed to:", cvin_nft_did_erc721_monolithic.address);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
