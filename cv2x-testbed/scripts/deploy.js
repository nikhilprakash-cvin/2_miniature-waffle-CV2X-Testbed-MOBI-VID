// Deploy ERC-1056 Registry Contract

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("🚀 Deploying ERC-1056 Registry Contract...\n");

  // Get deployer account
  const [deployer] = await hre.ethers.getSigners();
  console.log("📝 Deploying with account:", deployer.address);

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("💰 Account balance:", hre.ethers.formatEther(balance), "ETH\n");

  // Deploy contract
  const ERC1056Registry = await hre.ethers.getContractFactory("ERC1056Registry");
  console.log("⏳ Deploying contract...");

  const registry = await ERC1056Registry.deploy();
  await registry.waitForDeployment();

  const contractAddress = await registry.getAddress();
  console.log("✅ ERC1056Registry deployed to:", contractAddress);

  // Get deployment transaction
  const deployTx = registry.deploymentTransaction();
  const receipt = await deployTx.wait();

  console.log("📊 Deployment Stats:");
  console.log("   Gas used:", receipt.gasUsed.toString());
  console.log("   Block number:", receipt.blockNumber);
  console.log("   Transaction hash:", receipt.hash);

  // Save deployment info
  const deploymentInfo = {
    contractAddress: contractAddress,
    deployer: deployer.address,
    network: hre.network.name,
    chainId: (await hre.ethers.provider.getNetwork()).chainId.toString(),
    blockNumber: receipt.blockNumber,
    gasUsed: receipt.gasUsed.toString(),
    transactionHash: receipt.hash,
    timestamp: new Date().toISOString()
  };

  const deploymentsDir = path.join(__dirname, '..', 'deployments');
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentFile = path.join(deploymentsDir, `${hre.network.name}.json`);
  fs.writeFileSync(
    deploymentFile,
    JSON.stringify(deploymentInfo, null, 2)
  );

  console.log("\n💾 Deployment info saved to:", deploymentFile);

  // Save ABI
  const artifactPath = path.join(
    __dirname,
    '..',
    'artifacts',
    'contracts',
    'ERC1056Registry.sol',
    'ERC1056Registry.json'
  );

  if (fs.existsSync(artifactPath)) {
    const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));

    // Save ABI
    const abiPath = path.join(__dirname, '..', 'contracts', 'ERC1056Registry_abi.json');
    fs.writeFileSync(abiPath, JSON.stringify(artifact.abi, null, 2));
    console.log("💾 ABI saved to:", abiPath);

    // Save bytecode
    const bytecodePath = path.join(__dirname, '..', 'contracts', 'ERC1056Registry_bytecode.txt');
    fs.writeFileSync(bytecodePath, artifact.bytecode);
    console.log("💾 Bytecode saved to:", bytecodePath);
  }

  // Test basic functionality
  console.log("\n🧪 Testing contract...");

  // Register a test vehicle
  const testVehicleAddress = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8";
  const testPublicKey = "0x" + "04" + "a".repeat(128); // Dummy public key

  console.log("   Registering test vehicle:", testVehicleAddress);

  const tx = await registry.registerVehicle(testVehicleAddress, testPublicKey);
  await tx.wait();

  console.log("   ✅ Vehicle registered");

  // Check identity info
  const [owner, lastChanged, isRevoked, revokedAt] = await registry.getIdentityInfo(testVehicleAddress);

  console.log("   Identity Info:");
  console.log("      Owner:", owner);
  console.log("      Last Changed Block:", lastChanged.toString());
  console.log("      Is Revoked:", isRevoked);

  console.log("\n✨ Deployment complete!\n");

  console.log("📚 Next steps:");
  console.log("   1. Update Python provider with contract address:");
  console.log(`      provider = ERC1056Provider(contract_address="${contractAddress}")`);
  console.log("\n   2. Run comparison test:");
  console.log("      python scripts/run_comparison.py");
  console.log("\n   3. Start testbed simulation:");
  console.log("      python scenarios/basic_v2v_scenario.py");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
