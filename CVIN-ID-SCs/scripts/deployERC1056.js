const { ethers } = require("hardhat");

async function main() {
    console.log("Deploying ERC-1056 Ethereum DID Registry...\n");

    const [deployer] = await ethers.getSigners();
    console.log("Deploying contracts with account:", deployer.address);
    console.log("Account balance:", (await ethers.provider.getBalance(deployer.address)).toString(), "\n");

    // Deploy EthereumDIDRegistry
    console.log("1. Deploying EthereumDIDRegistry...");
    const DIDRegistry = await ethers.getContractFactory("EthereumDIDRegistry");
    const didRegistry = await DIDRegistry.deploy();
    await didRegistry.waitForDeployment();
    const didRegistryAddress = await didRegistry.getAddress();
    console.log("   ✓ EthereumDIDRegistry deployed to:", didRegistryAddress);

    // Deploy CVINVehicleDIDRegistry
    console.log("\n2. Deploying CVINVehicleDIDRegistry...");
    const VehicleRegistry = await ethers.getContractFactory("CVINVehicleDIDRegistry");
    const vehicleRegistry = await VehicleRegistry.deploy(didRegistryAddress);
    await vehicleRegistry.waitForDeployment();
    const vehicleRegistryAddress = await vehicleRegistry.getAddress();
    console.log("   ✓ CVINVehicleDIDRegistry deployed to:", vehicleRegistryAddress);

    // Summary
    console.log("\n=== Deployment Summary ===");
    console.log("Network:", (await ethers.provider.getNetwork()).name);
    console.log("Chain ID:", (await ethers.provider.getNetwork()).chainId);
    console.log("\nContracts:");
    console.log("  EthereumDIDRegistry:", didRegistryAddress);
    console.log("  CVINVehicleDIDRegistry:", vehicleRegistryAddress);

    console.log("\nDID Method: did:ethr");
    console.log("Example DID: did:ethr:" + deployer.address);

    // Save deployment info
    const deploymentInfo = {
        network: (await ethers.provider.getNetwork()).name,
        chainId: (await ethers.provider.getNetwork()).chainId.toString(),
        timestamp: new Date().toISOString(),
        contracts: {
            EthereumDIDRegistry: didRegistryAddress,
            CVINVehicleDIDRegistry: vehicleRegistryAddress
        },
        deployer: deployer.address
    };

    const fs = require("fs");
    const path = require("path");
    const deploymentsDir = path.join(__dirname, "..", "deployments");

    if (!fs.existsSync(deploymentsDir)) {
        fs.mkdirSync(deploymentsDir, { recursive: true });
    }

    fs.writeFileSync(
        path.join(deploymentsDir, "erc1056-deployment.json"),
        JSON.stringify(deploymentInfo, null, 2)
    );

    console.log("\n✓ Deployment info saved to deployments/erc1056-deployment.json");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
