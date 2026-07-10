/**
 * MOBI VID Registry test suite (V1 + V2)
 * =======================================
 *
 * Covers the two V1 bugs that previously made vehicle birth registration
 * revert on every realistic call:
 *
 *   1. `type(uint256).max` passed as attribute validity ->
 *      `block.timestamp + validity` overflow (panic 0x11) in
 *      ERC1056Registry.setAttribute. Fixed with a finite 100-year constant
 *      (PERMANENT_ATTRIBUTE_VALIDITY).
 *
 *   2. `owners[vehicleIdentity] = firstOwner` executed BEFORE the internal
 *      setAttribute call that used `msg.sender` (the manufacturer) as actor,
 *      so the ERC-1056 onlyOwner check reverted whenever
 *      manufacturer != firstOwner. Fixed by writing the attribute with
 *      firstOwner as the ERC-1056 actor.
 *
 * Also exercises MOBI VID II (MOBIVIDRegistryV2): lifecycle events for
 * several of the 11 event types, issuer-role gating, attestations,
 * getCompleteHistory and odometer history.
 *
 * Contracts under test live in contracts/MOBI/ (kept byte-identical to the
 * canonical sources in cv2x-testbed/contracts/).
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture } = require("@nomicfoundation/hardhat-toolbox/network-helpers");

const V1_FQN = "contracts/MOBI/MOBIVIDRegistry.sol:MOBIVIDRegistry";
const V2_FQN = "contracts/MOBI/MOBIVIDRegistryV2.sol:MOBIVIDRegistryV2";

// Mirrors of the Solidity enums (order matters)
const EventType = {
  MAINTENANCE: 0, REPAIR: 1, ACCIDENT: 2, RECALL: 3, INSPECTION: 4,
  MODIFICATION: 5, THEFT_REPORT: 6, RECOVERY: 7, INSURANCE_CLAIM: 8,
  REGISTRATION: 9, DECOMMISSION: 10,
};
const IssuerRole = {
  NONE: 0, MANUFACTURER: 1, DEALER: 2, SERVICE_CENTER: 3,
  INSURANCE_COMPANY: 4, GOVERNMENT_DMV: 5, POLICE: 6,
  INSPECTION_STATION: 7, OWNER: 8,
};

const VIN_HASH = ethers.keccak256(ethers.toUtf8Bytes("5YJ3E1EA0PF123456:salt"));
const BIRTH_CERT_HASH = ethers.keccak256(ethers.toUtf8Bytes("signed-birth-vc"));
const BIRTH_ATTRS = ethers.toUtf8Bytes(
  JSON.stringify({ make: "Tesla", model: "Model 3", year: 2024 })
);

function extractEventId(registry, receipt) {
  for (const log of receipt.logs) {
    try {
      const parsed = registry.interface.parseLog(log);
      if (parsed && parsed.name === "LifecycleEventRecorded") {
        return parsed.args.eventId;
      }
    } catch (_) { /* not our event */ }
  }
  throw new Error("LifecycleEventRecorded not emitted");
}

describe("MOBI VID Registry V1 (birth certificates)", function () {
  async function deployV1Fixture() {
    const [authority, manufacturer, firstOwner, secondOwner, vehicle, outsider] =
      await ethers.getSigners();
    const Registry = await ethers.getContractFactory(V1_FQN);
    const registry = await Registry.deploy();
    await registry.waitForDeployment();
    await registry.authorizeManufacturer(manufacturer.address);
    return { registry, authority, manufacturer, firstOwner, secondOwner, vehicle, outsider };
  }

  describe("registerVehicleBirth — the previously-broken path", function () {
    it("succeeds with manufacturer != firstOwner and non-empty attributes (regression for both V1 bugs)", async function () {
      const { registry, manufacturer, firstOwner, vehicle } =
        await loadFixture(deployV1Fixture);

      expect(manufacturer.address).to.not.equal(firstOwner.address);

      const tx = await registry.connect(manufacturer).registerVehicleBirth(
        vehicle.address, VIN_HASH, "encrypted:VIN", BIRTH_CERT_HASH,
        firstOwner.address, BIRTH_ATTRS
      );
      const receipt = await tx.wait();
      console.log(`        gas(V1 registerVehicleBirth, with attributes): ${receipt.gasUsed}`);

      await expect(tx).to.emit(registry, "VehicleBirthRegistered");
      // The birth attribute must be written as a DIDAttributeChanged event
      await expect(tx).to.emit(registry, "DIDAttributeChanged");

      const birth = await registry.getVehicleBirth(vehicle.address);
      expect(birth.vinHash).to.equal(VIN_HASH);
      expect(birth.manufacturer).to.equal(manufacturer.address);
      expect(birth.firstOwner).to.equal(firstOwner.address);
      expect(birth.exists).to.equal(true);

      // ERC-1056 owner is the first owner, not the manufacturer
      expect(await registry.identityOwner(vehicle.address)).to.equal(firstOwner.address);
    });

    it("uses a finite attribute validity (no uint256 overflow panic)", async function () {
      const { registry, manufacturer, firstOwner, vehicle } =
        await loadFixture(deployV1Fixture);

      const validity = await registry.PERMANENT_ATTRIBUTE_VALIDITY();
      expect(validity).to.equal(100n * 365n * 24n * 60n * 60n);

      const tx = await registry.connect(manufacturer).registerVehicleBirth(
        vehicle.address, VIN_HASH, "encrypted:VIN", BIRTH_CERT_HASH,
        firstOwner.address, BIRTH_ATTRS
      );
      const receipt = await tx.wait();
      const block = await ethers.provider.getBlock(receipt.blockNumber);

      const parsed = receipt.logs
        .map((l) => { try { return registry.interface.parseLog(l); } catch { return null; } })
        .find((p) => p && p.name === "DIDAttributeChanged");
      expect(parsed, "DIDAttributeChanged event").to.not.be.undefined;
      expect(parsed.args.validTo).to.equal(BigInt(block.timestamp) + validity);
    });

    it("rejects unauthorized manufacturers", async function () {
      const { registry, outsider, firstOwner, vehicle } =
        await loadFixture(deployV1Fixture);
      await expect(
        registry.connect(outsider).registerVehicleBirth(
          vehicle.address, VIN_HASH, "encrypted:VIN", BIRTH_CERT_HASH,
          firstOwner.address, BIRTH_ATTRS
        )
      ).to.be.revertedWith("Only authorized manufacturers can register vehicles");
    });

    it("rejects duplicate vehicle identity and duplicate VIN hash", async function () {
      const { registry, manufacturer, firstOwner, vehicle, outsider } =
        await loadFixture(deployV1Fixture);
      await registry.connect(manufacturer).registerVehicleBirth(
        vehicle.address, VIN_HASH, "encrypted:VIN", BIRTH_CERT_HASH,
        firstOwner.address, BIRTH_ATTRS
      );
      await expect(
        registry.connect(manufacturer).registerVehicleBirth(
          vehicle.address, VIN_HASH, "encrypted:VIN", BIRTH_CERT_HASH,
          firstOwner.address, BIRTH_ATTRS
        )
      ).to.be.revertedWith("Vehicle already registered");
      await expect(
        registry.connect(manufacturer).registerVehicleBirth(
          outsider.address, VIN_HASH, "encrypted:VIN", BIRTH_CERT_HASH,
          firstOwner.address, BIRTH_ATTRS
        )
      ).to.be.revertedWith("VIN hash already registered");
    });
  });

  describe("VIN-hash lookup", function () {
    it("resolves a registered VIN hash to the vehicle identity", async function () {
      const { registry, manufacturer, firstOwner, vehicle } =
        await loadFixture(deployV1Fixture);
      await registry.connect(manufacturer).registerVehicleBirth(
        vehicle.address, VIN_HASH, "encrypted:VIN", BIRTH_CERT_HASH,
        firstOwner.address, BIRTH_ATTRS
      );
      expect(await registry.lookupByVINHash(VIN_HASH)).to.equal(vehicle.address);
      expect(await registry.lookupByVINHash(ethers.ZeroHash)).to.equal(ethers.ZeroAddress);
      expect(await registry.vehicleExists(vehicle.address)).to.equal(true);
    });
  });

  describe("ownership transfer", function () {
    it("transfers ownership, records history and updates ERC-1056 owner", async function () {
      const { registry, manufacturer, firstOwner, secondOwner, vehicle } =
        await loadFixture(deployV1Fixture);
      await registry.connect(manufacturer).registerVehicleBirth(
        vehicle.address, VIN_HASH, "encrypted:VIN", BIRTH_CERT_HASH,
        firstOwner.address, BIRTH_ATTRS
      );

      const tx = await registry.connect(firstOwner).transferVehicleOwnership(
        vehicle.address, secondOwner.address, 15000, "BC ICBC"
      );
      const receipt = await tx.wait();
      console.log(`        gas(V1 transferVehicleOwnership): ${receipt.gasUsed}`);
      await expect(tx).to.emit(registry, "VehicleOwnershipTransferred");

      expect(await registry.identityOwner(vehicle.address)).to.equal(secondOwner.address);
      const history = await registry.getOwnershipHistory(vehicle.address);
      expect(history.length).to.equal(1);
      expect(history[0].from).to.equal(firstOwner.address);
      expect(history[0].to).to.equal(secondOwner.address);
      expect(history[0].odometer).to.equal(15000n);
      expect(history[0].registrationAuthority).to.equal("BC ICBC");
    });

    it("rejects transfers not initiated by the current owner", async function () {
      const { registry, manufacturer, firstOwner, secondOwner, vehicle, outsider } =
        await loadFixture(deployV1Fixture);
      await registry.connect(manufacturer).registerVehicleBirth(
        vehicle.address, VIN_HASH, "encrypted:VIN", BIRTH_CERT_HASH,
        firstOwner.address, BIRTH_ATTRS
      );
      await expect(
        registry.connect(outsider).transferVehicleOwnership(
          vehicle.address, secondOwner.address, 15000, "BC ICBC"
        )
      ).to.be.revertedWith("Only owner can perform this action");
    });
  });
});

describe("MOBI VID Registry V2 (lifecycle events)", function () {
  async function deployV2Fixture() {
    const [authority, manufacturer, firstOwner, serviceCenter, police,
           dmv, inspection, vehicle, outsider] = await ethers.getSigners();
    const Registry = await ethers.getContractFactory(V2_FQN);
    const registry = await Registry.deploy();
    await registry.waitForDeployment();

    await registry.authorizeManufacturer(manufacturer.address);
    await registry.authorizeIssuer(manufacturer.address, IssuerRole.MANUFACTURER);
    await registry.authorizeIssuer(serviceCenter.address, IssuerRole.SERVICE_CENTER);
    await registry.authorizeIssuer(police.address, IssuerRole.POLICE);
    await registry.authorizeIssuer(dmv.address, IssuerRole.GOVERNMENT_DMV);
    await registry.authorizeIssuer(inspection.address, IssuerRole.INSPECTION_STATION);

    await registry.connect(manufacturer).registerVehicleBirth(
      vehicle.address, VIN_HASH, "encrypted:VIN", BIRTH_CERT_HASH,
      firstOwner.address, BIRTH_ATTRS
    );

    return { registry, authority, manufacturer, firstOwner, serviceCenter,
             police, dmv, inspection, vehicle, outsider };
  }

  const DATA_HASH = ethers.keccak256(ethers.toUtf8Bytes("event-data"));
  const CRED_HASH = ethers.keccak256(ethers.toUtf8Bytes("signed-event-vc"));

  describe("recordLifecycleEvent", function () {
    it("records MAINTENANCE, INSPECTION, ACCIDENT, RECALL and REGISTRATION events", async function () {
      const { registry, manufacturer, serviceCenter, police, dmv, inspection, vehicle } =
        await loadFixture(deployV2Fixture);

      // last element: expected `verified` flag — _isVerifiedIssuer() marks
      // MANUFACTURER / GOVERNMENT_DMV / POLICE / DEALER / INSPECTION_STATION
      // as verified; SERVICE_CENTER is not.
      const cases = [
        ["MAINTENANCE", serviceCenter, EventType.MAINTENANCE, 10000, false],
        ["INSPECTION", inspection, EventType.INSPECTION, 10500, true],
        ["ACCIDENT", police, EventType.ACCIDENT, 11000, true],
        ["RECALL", manufacturer, EventType.RECALL, 11000, true],
        ["REGISTRATION", dmv, EventType.REGISTRATION, 11200, true],
      ];

      for (const [name, signer, type, odometer, expectedVerified] of cases) {
        const tx = await registry.connect(signer).recordLifecycleEvent(
          vehicle.address, type, odometer, DATA_HASH, CRED_HASH, "BC-CAN"
        );
        const receipt = await tx.wait();
        console.log(`        gas(V2 recordLifecycleEvent ${name}): ${receipt.gasUsed}`);
        const eventId = extractEventId(registry, receipt);

        // NOTE: getFunction() is required because ethers v6 contract proxies
        // reserve `getEvent` for ABI event fragment lookup.
        const evt = await registry.getFunction("getEvent")(vehicle.address, eventId);
        expect(evt.eventType).to.equal(BigInt(type));
        expect(evt.issuer).to.equal(signer.address);
        expect(evt.odometer).to.equal(BigInt(odometer));
        expect(evt.credentialHash).to.equal(CRED_HASH);
        expect(evt.jurisdiction).to.equal("BC-CAN");
        expect(evt.verified).to.equal(expectedVerified);
      }

      expect(await registry.vehicleEventCount(vehicle.address)).to.equal(5n);
      expect(await registry.getEventTypeCount(vehicle.address, EventType.MAINTENANCE)).to.equal(1n);
      const maintenanceIds = await registry.getEventsByType(vehicle.address, EventType.MAINTENANCE);
      expect(maintenanceIds.length).to.equal(1);
    });

    it("rejects issuers whose role is not allowed for the event type (role gating)", async function () {
      const { registry, serviceCenter, police, vehicle, outsider } =
        await loadFixture(deployV2Fixture);

      // Completely unauthorized address
      await expect(
        registry.connect(outsider).recordLifecycleEvent(
          vehicle.address, EventType.MAINTENANCE, 100, DATA_HASH, CRED_HASH, "BC-CAN"
        )
      ).to.be.revertedWith("Not authorized to issue this event type");

      // Authorized, but wrong role for the type: SERVICE_CENTER cannot issue RECALL
      await expect(
        registry.connect(serviceCenter).recordLifecycleEvent(
          vehicle.address, EventType.RECALL, 100, DATA_HASH, CRED_HASH, "BC-CAN"
        )
      ).to.be.revertedWith("Not authorized to issue this event type");

      // POLICE cannot issue REGISTRATION (DMV only)
      await expect(
        registry.connect(police).recordLifecycleEvent(
          vehicle.address, EventType.REGISTRATION, 100, DATA_HASH, CRED_HASH, "BC-CAN"
        )
      ).to.be.revertedWith("Not authorized to issue this event type");
    });

    it("rejects events for unregistered vehicles", async function () {
      const { registry, serviceCenter, outsider } = await loadFixture(deployV2Fixture);
      await expect(
        registry.connect(serviceCenter).recordLifecycleEvent(
          outsider.address, EventType.MAINTENANCE, 100, DATA_HASH, CRED_HASH, "BC-CAN"
        )
      ).to.be.revertedWith("Vehicle not registered");
    });
  });

  describe("issuer management", function () {
    it("only the registry authority can authorize issuers, and revocation disables issuance", async function () {
      const { registry, serviceCenter, vehicle, outsider } =
        await loadFixture(deployV2Fixture);

      await expect(
        registry.connect(outsider).authorizeIssuer(outsider.address, IssuerRole.POLICE)
      ).to.be.revertedWith("Only registry authority can perform this action");

      await registry.revokeIssuerAuthorization(serviceCenter.address);
      await expect(
        registry.connect(serviceCenter).recordLifecycleEvent(
          vehicle.address, EventType.MAINTENANCE, 100, DATA_HASH, CRED_HASH, "BC-CAN"
        )
      ).to.be.revertedWith("Not authorized to issue this event type");
    });
  });

  describe("attestEvent", function () {
    it("lets other authorized parties attest to an event", async function () {
      const { registry, serviceCenter, dmv, inspection, vehicle } =
        await loadFixture(deployV2Fixture);

      const tx = await registry.connect(serviceCenter).recordLifecycleEvent(
        vehicle.address, EventType.MAINTENANCE, 12000, DATA_HASH, CRED_HASH, "BC-CAN"
      );
      const eventId = extractEventId(registry, await tx.wait());

      const sig = ethers.toUtf8Bytes("0xsignature-placeholder");
      const attestTx = await registry.connect(dmv).attestEvent(eventId, vehicle.address, sig);
      const attestReceipt = await attestTx.wait();
      console.log(`        gas(V2 attestEvent): ${attestReceipt.gasUsed}`);
      await expect(attestTx).to.emit(registry, "EventAttested");
      await registry.connect(inspection).attestEvent(eventId, vehicle.address, sig);

      const attestations = await registry.getEventAttestations(eventId);
      expect(attestations.length).to.equal(2);
      expect(attestations[0].attester).to.equal(dmv.address);
      expect(attestations[0].role).to.equal(BigInt(IssuerRole.GOVERNMENT_DMV));
      expect(attestations[1].attester).to.equal(inspection.address);
    });

    it("rejects attestations from unauthorized parties and for unknown events", async function () {
      const { registry, serviceCenter, dmv, vehicle, outsider } =
        await loadFixture(deployV2Fixture);
      const tx = await registry.connect(serviceCenter).recordLifecycleEvent(
        vehicle.address, EventType.MAINTENANCE, 12000, DATA_HASH, CRED_HASH, "BC-CAN"
      );
      const eventId = extractEventId(registry, await tx.wait());
      const sig = ethers.toUtf8Bytes("sig");

      await expect(
        registry.connect(outsider).attestEvent(eventId, vehicle.address, sig)
      ).to.be.revertedWith("Not authorized to attest");
      // KNOWN CONTRACT QUIRK: attestEvent(bytes32(0), ...) would NOT revert,
      // because the empty LifecycleEvent struct has eventId == 0. Any
      // non-zero unknown id is correctly rejected.
      const bogusId = ethers.keccak256(ethers.toUtf8Bytes("no-such-event"));
      await expect(
        registry.connect(dmv).attestEvent(bogusId, vehicle.address, sig)
      ).to.be.revertedWith("Event does not exist");
    });
  });

  describe("history queries", function () {
    it("getCompleteHistory returns birth + event count + last event", async function () {
      const { registry, serviceCenter, police, vehicle } =
        await loadFixture(deployV2Fixture);

      const tx1 = await registry.connect(serviceCenter).recordLifecycleEvent(
        vehicle.address, EventType.MAINTENANCE, 5000, DATA_HASH, CRED_HASH, "BC-CAN"
      );
      extractEventId(registry, await tx1.wait());
      const tx2 = await registry.connect(police).recordLifecycleEvent(
        vehicle.address, EventType.ACCIDENT, 7500, DATA_HASH, CRED_HASH, "BC-CAN"
      );
      const lastId = extractEventId(registry, await tx2.wait());

      const [birth, eventCount, lastEvent] =
        await registry.getCompleteHistory(vehicle.address);
      expect(birth.vinHash).to.equal(VIN_HASH);
      expect(eventCount).to.equal(2n);
      expect(lastEvent).to.equal(lastId);

      const ids = await registry.getVehicleEvents(vehicle.address);
      expect(ids.length).to.equal(2);
    });

    it("getOdometerHistory returns readings in event order", async function () {
      const { registry, serviceCenter, vehicle } = await loadFixture(deployV2Fixture);
      for (const odo of [1000, 2000, 3000]) {
        await registry.connect(serviceCenter).recordLifecycleEvent(
          vehicle.address, EventType.MAINTENANCE, odo, DATA_HASH, CRED_HASH, "BC-CAN"
        );
      }
      const [readings, timestamps] = await registry.getOdometerHistory(vehicle.address);
      expect(readings.map(Number)).to.deep.equal([1000, 2000, 3000]);
      expect(timestamps.length).to.equal(3);
    });
  });
});
