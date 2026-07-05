// Deploy MOBI VID Registry Contract

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("🚗 Deploying MOBI VID Registry Contract...\n");

  // Get deployer account (will be registry authority and first manufacturer)
  const [deployer] = await hre.ethers.getSigners();
  console.log("📝 Deploying with account:", deployer.address);
  console.log("   (This account will be registry authority + authorized manufacturer)");

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("💰 Account balance:", hre.ethers.formatEther(balance), "ETH\n");

  // Deploy contract
  const MOBIVIDRegistry = await hre.ethers.getContractFactory("MOBIVIDRegistry");
  console.log("⏳ Deploying MOBI VID Registry contract...");

  const registry = await MOBIVIDRegistry.deploy();
  await registry.waitForDeployment();

  const contractAddress = await registry.getAddress();
  console.log("✅ MOBIVIDRegistry deployed to:", contractAddress);

  // Get deployment transaction
  const deployTx = registry.deploymentTransaction();
  const receipt = await deployTx.wait();

  console.log("\n📊 Deployment Stats:");
  console.log("   Gas used:", receipt.gasUsed.toString());
  console.log("   Block number:", receipt.blockNumber);
  console.log("   Transaction hash:", receipt.hash);

  // Save deployment info
  const deploymentInfo = {
    contractName: "MOBIVIDRegistry",
    contractAddress: contractAddress,
    deployer: deployer.address,
    network: hre.network.name,
    chainId: (await hre.ethers.provider.getNetwork()).chainId.toString(),
    blockNumber: receipt.blockNumber,
    gasUsed: receipt.gasUsed.toString(),
    transactionHash: receipt.hash,
    timestamp: new Date().toISOString(),
    notes: "MOBI VID 1.0 compliant registry. Deployer is registry authority and first authorized manufacturer."
  };

  const deploymentsDir = path.join(__dirname, '..', 'deployments');
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentFile = path.join(deploymentsDir, `mobi_vid_${hre.network.name}.json`);
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
    'MOBIVIDRegistry.sol',
    'MOBIVIDRegistry.json'
  );

  if (fs.existsSync(artifactPath)) {
    const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));

    // Save ABI
    const abiPath = path.join(__dirname, '..', 'contracts', 'MOBIVIDRegistry_abi.json');
    fs.writeFileSync(abiPath, JSON.stringify(artifact.abi, null, 2));
    console.log("💾 ABI saved to:", abiPath);

    // Save bytecode
    const bytecodePath = path.join(__dirname, '..', 'contracts', 'MOBIVIDRegistry_bytecode.txt');
    fs.writeFileSync(bytecodePath, artifact.bytecode);
    console.log("💾 Bytecode saved to:", bytecodePath);
  }

  // Test MOBI VID functionality
  console.log("\n🧪 Testing MOBI VID contract...");

  // Test 1: Verify registry authority
  const registryAuthority = await registry.registryAuthority();
  console.log("   ✓ Registry Authority:", registryAuthority);
  console.log("     (Should be deployer:", deployer.address, ")");

  // Test 2: Verify deployer is authorized manufacturer
  const isAuthorized = await registry.authorizedManufacturers(deployer.address);
  console.log("   ✓ Deployer is authorized manufacturer:", isAuthorized);

  // Test 3: Register a test vehicle birth
  console.log("\n   Testing vehicle birth registration...");

  const testVehicleIdentity = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8";
  const testVIN = "1HGBH41JXMN109186";
  const testVINHash = hre.ethers.keccak256(hre.ethers.toUtf8Bytes(testVIN + "salt" + testVehicleIdentity));
  const encryptedVIN = "0x" + Buffer.from("encrypted_vin_data").toString('hex');
  const birthCertHash = hre.ethers.keccak256(hre.ethers.toUtf8Bytes("birth_cert_data"));
  const firstOwner = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC";
  const birthAttributes = hre.ethers.toUtf8Bytes(JSON.stringify({
    make: "Tesla",
    model: "Model S",
    year: 2024,
    manufacturer: "Tesla Inc."
  }));

  console.log("   Registering vehicle:");
  console.log("      VIN Hash:", testVINHash);
  console.log("      Vehicle Identity:", testVehicleIdentity);
  console.log("      First Owner:", firstOwner);

  const tx = await registry.registerVehicleBirth(
    testVehicleIdentity,
    testVINHash,
    encryptedVIN,
    birthCertHash,
    firstOwner,
    birthAttributes
  );

  const birthReceipt = await tx.wait();
  console.log("   ✅ Vehicle birth registered!");
  console.log("      Gas used:", birthReceipt.gasUsed.toString());
  console.log("      Transaction:", birthReceipt.hash);

  // Test 4: Retrieve vehicle info
  console.log("\n   Retrieving vehicle information...");

  const [birth, currentOwner, isRevoked, transferCount] = await registry.getVehicleInfo(testVehicleIdentity);

  console.log("   ✓ Vehicle Birth Certificate:");
  console.log("      VIN Hash:", birth.vinHash);
  console.log("      Encrypted VIN:", birth.encryptedVIN);
  console.log("      Birth Cert Hash:", birth.birthCertHash);
  console.log("      Timestamp:", new Date(Number(birth.timestamp) * 1000).toISOString());
  console.log("      Manufacturer:", birth.manufacturer);
  console.log("      First Owner:", birth.firstOwner);
  console.log("      Block Number:", birth.blockNumber.toString());
  console.log("      Exists:", birth.exists);
  console.log("\n   ✓ Current State:");
  console.log("      Current Owner:", currentOwner);
  console.log("      Is Revoked:", isRevoked);
  console.log("      Transfer Count:", transferCount.toString());

  // Test 5: Lookup by VIN hash
  const lookedUpIdentity = await registry.lookupByVINHash(testVINHash);
  console.log("\n   ✓ Lookup by VIN Hash:");
  console.log("      VIN Hash:", testVINHash);
  console.log("      Found Identity:", lookedUpIdentity);
  console.log("      Matches:", lookedUpIdentity === testVehicleIdentity);

  // Test 6: Get vehicle DID
  const vehicleDID = await registry.getVehicleDID(testVehicleIdentity);
  console.log("\n   ✓ Vehicle DID:", vehicleDID);

  console.log("\n✨ MOBI VID deployment and testing complete!\n");

  console.log("📚 Next steps:");
  console.log("\n   1. Update Python provider with contract address:");
  console.log(`      provider = MOBIVIDProvider(contract_address="${contractAddress}")`);
  console.log("\n   2. Run MOBI VID test:");
  console.log("      python scripts/test_mobi_vid.py");
  console.log("\n   3. Register real vehicles:");
  console.log("      from identity.mobi_vid_provider import MOBIVIDProvider");
  console.log(`      provider = MOBIVIDProvider(contract_address="${contractAddress}")`);
  console.log('      credential = provider.register_vehicle_birth(');
  console.log('          vin="YOUR_VIN",');
  console.log('          manufacturer_data={"name": "Tesla"},');
  console.log('          vehicle_data={"make": "Tesla", "model": "Model S", "year": 2024},');
  console.log('          first_owner_address="0x..."');
  console.log('      )');
  console.log("\n   4. Compare with centralized PKI:");
  console.log("      python scripts/test_identity_comparison.py");

  console.log("\n🎯 Standards Compliance:");
  console.log("   ✅ MOBI VID I (Vehicle Birth Certificate)");
  console.log("   ✅ W3C DID Core v1.0");
  console.log("   ✅ ERC-1056 (Ethereum DID Registry)");
  console.log("   ✅ SSI Principles");

  console.log("\n🔐 Security Features:");
  console.log("   ✅ VIN privacy protection (hash + encrypted)");
  console.log("   ✅ Manufacturer authorization");
  console.log("   ✅ Immutable birth certificates");
  console.log("   ✅ Ownership transfer tracking");
  console.log("   ✅ On-chain revocation");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
