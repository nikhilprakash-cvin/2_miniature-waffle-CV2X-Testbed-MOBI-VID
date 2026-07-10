const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CVINVehicleDIDRegistry", function () {
    let didRegistry, vehicleRegistry;
    let owner, manufacturer, vehicleOwner, newOwner, attacker;

    const TEST_VIN = "1HGBH41JXMN109186";
    const VEHICLE_DATA = {
        make: "Honda",
        model: "Accord",
        year: 2024,
        color: "Silver",
        engineNumber: "ENG-12345-XYZ",
        manufacturingDate: Math.floor(Date.now() / 1000),
        autonomyLevel: "SAE Level 3"
    };

    beforeEach(async function () {
        [owner, manufacturer, vehicleOwner, newOwner, attacker] = await ethers.getSigners();

        // Deploy base DID registry
        const DIDRegistry = await ethers.getContractFactory("EthereumDIDRegistry");
        didRegistry = await DIDRegistry.deploy();
        await didRegistry.waitForDeployment();

        // Deploy vehicle-specific registry
        const VehicleRegistry = await ethers.getContractFactory("CVINVehicleDIDRegistry");
        vehicleRegistry = await VehicleRegistry.deploy(await didRegistry.getAddress());
        await vehicleRegistry.waitForDeployment();

        // Authorize manufacturer
        await vehicleRegistry.connect(owner).setAuthorizedManufacturer(manufacturer.address, true);
    });

    describe("Manufacturer Authorization", function () {
        it("should authorize manufacturer", async function () {
            await vehicleRegistry.connect(owner).setAuthorizedManufacturer(attacker.address, true);
            expect(await vehicleRegistry.authorizedManufacturers(attacker.address)).to.be.true;
        });

        it("should deauthorize manufacturer", async function () {
            await vehicleRegistry.connect(owner).setAuthorizedManufacturer(manufacturer.address, false);
            expect(await vehicleRegistry.authorizedManufacturers(manufacturer.address)).to.be.false;
        });

        it("should not allow non-owner to authorize", async function () {
            await expect(
                vehicleRegistry.connect(attacker).setAuthorizedManufacturer(attacker.address, true)
            ).to.be.revertedWith("CVINRegistry: not owner");
        });
    });

    describe("Vehicle DID Creation", function () {
        it("should create vehicle DID with all attributes", async function () {
            const tx = await vehicleRegistry
                .connect(manufacturer)
                .createVehicleDID(
                    TEST_VIN,
                    vehicleOwner.address,
                    VEHICLE_DATA.make,
                    VEHICLE_DATA.model,
                    VEHICLE_DATA.year,
                    VEHICLE_DATA.color,
                    VEHICLE_DATA.engineNumber,
                    VEHICLE_DATA.manufacturingDate,
                    VEHICLE_DATA.autonomyLevel
                );

            const receipt = await tx.wait();
            const event = receipt.logs.find(log => {
                try {
                    return vehicleRegistry.interface.parseLog(log)?.name === "VehicleDIDCreated";
                } catch {
                    return false;
                }
            });

            expect(event).to.not.be.undefined;

            console.log("       Gas used for vehicle DID creation:", receipt.gasUsed.toString());
        });

        it("should map VIN to DID correctly", async function () {
            await vehicleRegistry
                .connect(manufacturer)
                .createVehicleDID(
                    TEST_VIN,
                    vehicleOwner.address,
                    VEHICLE_DATA.make,
                    VEHICLE_DATA.model,
                    VEHICLE_DATA.year,
                    VEHICLE_DATA.color,
                    VEHICLE_DATA.engineNumber,
                    VEHICLE_DATA.manufacturingDate,
                    VEHICLE_DATA.autonomyLevel
                );

            const did = await vehicleRegistry.getDIDFromVIN(TEST_VIN);
            expect(did).to.not.equal(ethers.ZeroAddress);

            const vin = await vehicleRegistry.getVINFromDID(did);
            expect(vin).to.equal(TEST_VIN);
        });

        it("should set correct owner", async function () {
            await vehicleRegistry
                .connect(manufacturer)
                .createVehicleDID(
                    TEST_VIN,
                    vehicleOwner.address,
                    VEHICLE_DATA.make,
                    VEHICLE_DATA.model,
                    VEHICLE_DATA.year,
                    VEHICLE_DATA.color,
                    VEHICLE_DATA.engineNumber,
                    VEHICLE_DATA.manufacturingDate,
                    VEHICLE_DATA.autonomyLevel
                );

            const did = await vehicleRegistry.getDIDFromVIN(TEST_VIN);
            const owner = await vehicleRegistry.getVehicleOwner(did);
            expect(owner).to.equal(vehicleOwner.address);
        });

        it("should not allow duplicate VIN registration", async function () {
            await vehicleRegistry
                .connect(manufacturer)
                .createVehicleDID(
                    TEST_VIN,
                    vehicleOwner.address,
                    VEHICLE_DATA.make,
                    VEHICLE_DATA.model,
                    VEHICLE_DATA.year,
                    VEHICLE_DATA.color,
                    VEHICLE_DATA.engineNumber,
                    VEHICLE_DATA.manufacturingDate,
                    VEHICLE_DATA.autonomyLevel
                );

            await expect(
                vehicleRegistry
                    .connect(manufacturer)
                    .createVehicleDID(
                        TEST_VIN,
                        newOwner.address,
                        VEHICLE_DATA.make,
                        VEHICLE_DATA.model,
                        VEHICLE_DATA.year,
                        VEHICLE_DATA.color,
                        VEHICLE_DATA.engineNumber,
                        VEHICLE_DATA.manufacturingDate,
                        VEHICLE_DATA.autonomyLevel
                    )
            ).to.be.revertedWith("CVINRegistry: VIN already registered");
        });

        it("should reject invalid VIN length", async function () {
            await expect(
                vehicleRegistry
                    .connect(manufacturer)
                    .createVehicleDID(
                        "INVALID",
                        vehicleOwner.address,
                        VEHICLE_DATA.make,
                        VEHICLE_DATA.model,
                        VEHICLE_DATA.year,
                        VEHICLE_DATA.color,
                        VEHICLE_DATA.engineNumber,
                        VEHICLE_DATA.manufacturingDate,
                        VEHICLE_DATA.autonomyLevel
                    )
            ).to.be.revertedWith("CVINRegistry: invalid VIN length");
        });

        it("should not allow unauthorized manufacturer to create DID", async function () {
            await expect(
                vehicleRegistry
                    .connect(attacker)
                    .createVehicleDID(
                        TEST_VIN,
                        vehicleOwner.address,
                        VEHICLE_DATA.make,
                        VEHICLE_DATA.model,
                        VEHICLE_DATA.year,
                        VEHICLE_DATA.color,
                        VEHICLE_DATA.engineNumber,
                        VEHICLE_DATA.manufacturingDate,
                        VEHICLE_DATA.autonomyLevel
                    )
            ).to.be.revertedWith("CVINRegistry: not authorized manufacturer");
        });
    });

    describe("Ownership Transfer", function () {
        let vehicleDID;

        beforeEach(async function () {
            await vehicleRegistry
                .connect(manufacturer)
                .createVehicleDID(
                    TEST_VIN,
                    vehicleOwner.address,
                    VEHICLE_DATA.make,
                    VEHICLE_DATA.model,
                    VEHICLE_DATA.year,
                    VEHICLE_DATA.color,
                    VEHICLE_DATA.engineNumber,
                    VEHICLE_DATA.manufacturingDate,
                    VEHICLE_DATA.autonomyLevel
                );

            vehicleDID = await vehicleRegistry.getDIDFromVIN(TEST_VIN);
        });

        it("should transfer ownership", async function () {
            // ERC-1056: the current owner transfers ownership directly on the
            // DID registry, then the VIN mapping is synchronized via
            // updateOwnershipMapping on the vehicle registry.
            await didRegistry
                .connect(vehicleOwner)
                .changeOwner(vehicleDID, newOwner.address);

            const tx = await vehicleRegistry
                .connect(newOwner)
                .updateOwnershipMapping(vehicleDID, newOwner.address);

            await expect(tx)
                .to.emit(vehicleRegistry, "VehicleOwnershipTransferred")
                .withArgs(vehicleDID, vehicleOwner.address, newOwner.address);

            const owner = await vehicleRegistry.getVehicleOwner(vehicleDID);
            expect(owner).to.equal(newOwner.address);

            // VIN now resolves to the new owner's DID
            expect(await vehicleRegistry.getDIDFromVIN(TEST_VIN)).to.equal(newOwner.address);
        });

        it("should not allow unauthorized transfer", async function () {
            // Attacker cannot change the DID owner in the DID registry
            await expect(
                didRegistry.connect(attacker).changeOwner(vehicleDID, attacker.address)
            ).to.be.revertedWith("DIDRegistry: unauthorized");

            // Nor update the VIN mapping without a completed DID ownership transfer
            await expect(
                vehicleRegistry
                    .connect(attacker)
                    .updateOwnershipMapping(vehicleDID, attacker.address)
            ).to.be.revertedWith("CVINRegistry: ownership not transferred in DID registry");
        });

        it("should allow new owner to make changes", async function () {
            await didRegistry
                .connect(vehicleOwner)
                .changeOwner(vehicleDID, newOwner.address);

            await vehicleRegistry
                .connect(newOwner)
                .updateOwnershipMapping(vehicleDID, newOwner.address);

            const DELEGATE_VERIKEY = await vehicleRegistry.DELEGATE_VERIKEY();

            // ERC-1056: the DID owner manages delegates directly on the DID registry
            await expect(
                didRegistry
                    .connect(newOwner)
                    .addDelegate(vehicleDID, DELEGATE_VERIKEY, attacker.address, 86400)
            ).to.not.be.reverted;
        });
    });

    describe("Service Endpoints", function () {
        let vehicleDID;

        beforeEach(async function () {
            await vehicleRegistry
                .connect(manufacturer)
                .createVehicleDID(
                    TEST_VIN,
                    vehicleOwner.address,
                    VEHICLE_DATA.make,
                    VEHICLE_DATA.model,
                    VEHICLE_DATA.year,
                    VEHICLE_DATA.color,
                    VEHICLE_DATA.engineNumber,
                    VEHICLE_DATA.manufacturingDate,
                    VEHICLE_DATA.autonomyLevel
                );

            vehicleDID = await vehicleRegistry.getDIDFromVIN(TEST_VIN);
        });

        it("should set service endpoint", async function () {
            const SVC_CREDENTIAL = await vehicleRegistry.SVC_CREDENTIAL_SERVICE();
            const endpoint = "https://credentials.cvin.network";

            // ERC-1056: attributes must be set by the DID owner directly on the
            // DID registry (the vehicle registry contract is not the DID owner).
            await expect(
                didRegistry
                    .connect(vehicleOwner)
                    .setAttribute(vehicleDID, SVC_CREDENTIAL, ethers.toUtf8Bytes(endpoint), 86400)
            ).to.emit(didRegistry, "DIDAttributeChanged");
        });

        it("should not allow unauthorized endpoint setting", async function () {
            const SVC_CREDENTIAL = await vehicleRegistry.SVC_CREDENTIAL_SERVICE();

            await expect(
                vehicleRegistry
                    .connect(attacker)
                    .setServiceEndpoint(vehicleDID, SVC_CREDENTIAL, "https://evil.com", 86400)
            ).to.be.revertedWith("CVINRegistry: not vehicle owner");
        });
    });

    describe("Verification Delegates", function () {
        let vehicleDID;

        beforeEach(async function () {
            await vehicleRegistry
                .connect(manufacturer)
                .createVehicleDID(
                    TEST_VIN,
                    vehicleOwner.address,
                    VEHICLE_DATA.make,
                    VEHICLE_DATA.model,
                    VEHICLE_DATA.year,
                    VEHICLE_DATA.color,
                    VEHICLE_DATA.engineNumber,
                    VEHICLE_DATA.manufacturingDate,
                    VEHICLE_DATA.autonomyLevel
                );

            vehicleDID = await vehicleRegistry.getDIDFromVIN(TEST_VIN);
        });

        // ERC-1056: delegates are managed by the DID owner directly on the DID
        // registry (the vehicle registry contract is not the DID owner); the
        // vehicle registry is used as the query layer via isValidDelegate.
        it("should add verification delegate", async function () {
            const DELEGATE_VERIKEY = await vehicleRegistry.DELEGATE_VERIKEY();

            await didRegistry
                .connect(vehicleOwner)
                .addDelegate(vehicleDID, DELEGATE_VERIKEY, attacker.address, 86400);

            const isValid = await vehicleRegistry.isValidDelegate(
                vehicleDID,
                DELEGATE_VERIKEY,
                attacker.address
            );

            expect(isValid).to.be.true;
        });

        it("should revoke verification delegate", async function () {
            const DELEGATE_VERIKEY = await vehicleRegistry.DELEGATE_VERIKEY();

            await didRegistry
                .connect(vehicleOwner)
                .addDelegate(vehicleDID, DELEGATE_VERIKEY, attacker.address, 86400);

            await didRegistry
                .connect(vehicleOwner)
                .revokeDelegate(vehicleDID, DELEGATE_VERIKEY, attacker.address);

            const isValid = await vehicleRegistry.isValidDelegate(
                vehicleDID,
                DELEGATE_VERIKEY,
                attacker.address
            );

            expect(isValid).to.be.false;
        });

        it("should support different delegate types", async function () {
            const DELEGATE_VERIKEY = await vehicleRegistry.DELEGATE_VERIKEY();
            const DELEGATE_SIGAUTH = await vehicleRegistry.DELEGATE_SIGAUTH();

            await didRegistry
                .connect(vehicleOwner)
                .addDelegate(vehicleDID, DELEGATE_VERIKEY, attacker.address, 86400);

            await didRegistry
                .connect(vehicleOwner)
                .addDelegate(vehicleDID, DELEGATE_SIGAUTH, newOwner.address, 86400);

            expect(
                await vehicleRegistry.isValidDelegate(vehicleDID, DELEGATE_VERIKEY, attacker.address)
            ).to.be.true;

            expect(
                await vehicleRegistry.isValidDelegate(vehicleDID, DELEGATE_SIGAUTH, newOwner.address)
            ).to.be.true;
        });
    });

    describe("Query Functions", function () {
        it("should return zero address for non-existent VIN", async function () {
            const did = await vehicleRegistry.getDIDFromVIN("NONEXISTENT123456");
            expect(did).to.equal(ethers.ZeroAddress);
        });

        it("should return empty string for non-existent DID", async function () {
            const vin = await vehicleRegistry.getVINFromDID(attacker.address);
            expect(vin).to.equal("");
        });
    });
});
