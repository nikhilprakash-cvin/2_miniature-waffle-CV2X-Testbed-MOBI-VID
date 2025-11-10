// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./MOBIVIDRegistry.sol";

/**
 * @title MOBI VID Registry V2
 * @dev Extends MOBI VID Registry with VID 2.0 lifecycle events
 *
 * Standards Compliance:
 * - MOBI VID I (Vehicle Birth Certificate) - from base contract
 * - MOBI VID II (Lifecycle Events) - NEW
 * - W3C Decentralized Identifiers (DIDs) v1.0
 * - W3C Verifiable Credentials v1.1
 * - ERC-1056 (Ethereum DID Registry)
 * - SSI (Self-Sovereign Identity) principles
 *
 * Key Features:
 * - Lifecycle event tracking (maintenance, accidents, recalls, etc.)
 * - Multi-party event issuance
 * - Event attestations from multiple signers
 * - Role-based access control for issuers
 * - Verifiable Credential integration
 * - Complete vehicle history
 */
contract MOBIVIDRegistryV2 is MOBIVIDRegistry {

    // ============ ENUMS ============

    /**
     * @dev Types of lifecycle events
     */
    enum EventType {
        MAINTENANCE,        // Regular service (oil change, tire rotation, etc.)
        REPAIR,            // Breakdown repair
        ACCIDENT,          // Collision or damage
        RECALL,            // Manufacturer recall
        INSPECTION,        // Safety or emissions inspection
        MODIFICATION,      // Aftermarket modifications
        THEFT_REPORT,      // Vehicle reported stolen
        RECOVERY,          // Stolen vehicle recovered
        INSURANCE_CLAIM,   // Insurance claim filed
        REGISTRATION,      // DMV registration/renewal
        DECOMMISSION      // Vehicle scrapped/totaled
    }

    /**
     * @dev Roles for event issuers
     */
    enum IssuerRole {
        NONE,              // Not authorized
        MANUFACTURER,      // Can issue recalls, updates, decommissions
        DEALER,            // Can issue maintenance, repairs, sales
        SERVICE_CENTER,    // Can issue maintenance, repairs
        INSURANCE_COMPANY, // Can issue claims, appraisals
        GOVERNMENT_DMV,    // Can issue registrations, inspections
        POLICE,            // Can issue theft reports, accidents
        INSPECTION_STATION,// Can issue safety/emissions tests
        OWNER              // Can report events (unverified)
    }

    // ============ STRUCTS ============

    /**
     * @dev Lifecycle Event (MOBI VID II)
     * Represents a mutable event in the vehicle's history
     */
    struct LifecycleEvent {
        bytes32 eventId;           // Unique event identifier
        EventType eventType;       // Type of event
        address issuer;            // DID of issuer
        uint256 timestamp;         // When event occurred
        uint256 odometer;          // Odometer reading at event
        bytes32 dataHash;          // IPFS hash of detailed event data
        bytes32 credentialHash;    // Hash of W3C Verifiable Credential
        bool verified;             // Official verification status
        string jurisdiction;       // Legal jurisdiction (e.g., "CA-USA")
        uint256 blockNumber;       // Block when recorded
    }

    /**
     * @dev Event Attestation
     * Multiple parties can attest to an event
     */
    struct EventAttestation {
        address attester;          // DID of attester
        IssuerRole role;           // Role of attester
        bytes signature;           // Signature of event data
        uint256 timestamp;         // When attested
    }

    // ============ STORAGE ============

    // Authorized issuers (address => role)
    mapping(address => IssuerRole) public authorizedIssuers;

    // Vehicle lifecycle events (vehicleIdentity => eventId => LifecycleEvent)
    mapping(address => mapping(bytes32 => LifecycleEvent)) public lifecycleEvents;

    // Vehicle event IDs list (vehicleIdentity => array of eventIds)
    mapping(address => bytes32[]) public vehicleEventIds;

    // Event attestations (eventId => array of attestations)
    mapping(bytes32 => EventAttestation[]) public eventAttestations;

    // Event count per vehicle
    mapping(address => uint256) public vehicleEventCount;

    // Event type statistics (vehicleIdentity => eventType => count)
    mapping(address => mapping(EventType => uint256)) public eventTypeCount;

    // Allowed issuers per event type
    mapping(EventType => mapping(IssuerRole => bool)) public allowedIssuers;

    // ============ EVENTS ============

    /**
     * @dev Emitted when a lifecycle event is recorded
     */
    event LifecycleEventRecorded(
        address indexed vehicleIdentity,
        bytes32 indexed eventId,
        EventType indexed eventType,
        address issuer,
        uint256 odometer,
        uint256 timestamp
    );

    /**
     * @dev Emitted when an event is attested
     */
    event EventAttested(
        bytes32 indexed eventId,
        address indexed attester,
        IssuerRole role,
        uint256 timestamp
    );

    /**
     * @dev Emitted when an issuer is authorized
     */
    event IssuerAuthorized(
        address indexed issuer,
        IssuerRole role,
        uint256 timestamp
    );

    /**
     * @dev Emitted when an issuer authorization is revoked
     */
    event IssuerAuthorizationRevoked(
        address indexed issuer,
        uint256 timestamp
    );

    // ============ MODIFIERS ============

    modifier onlyAuthorizedIssuer(EventType eventType) {
        require(
            isAuthorizedIssuer(msg.sender, eventType),
            "Not authorized to issue this event type"
        );
        _;
    }

    // ============ CONSTRUCTOR ============

    constructor() MOBIVIDRegistry() {
        // Initialize allowed issuers for each event type
        _initializeAllowedIssuers();
    }

    // ============ ISSUER MANAGEMENT ============

    /**
     * @dev Authorize an issuer with a specific role
     * @param issuer Address to authorize
     * @param role Role to assign
     */
    function authorizeIssuer(address issuer, IssuerRole role)
        external
        onlyRegistryAuthority
    {
        require(issuer != address(0), "Invalid issuer address");
        require(role != IssuerRole.NONE, "Invalid role");

        authorizedIssuers[issuer] = role;
        emit IssuerAuthorized(issuer, role, block.timestamp);
    }

    /**
     * @dev Revoke issuer authorization
     * @param issuer Address to revoke
     */
    function revokeIssuerAuthorization(address issuer)
        external
        onlyRegistryAuthority
    {
        require(authorizedIssuers[issuer] != IssuerRole.NONE, "Issuer not authorized");

        authorizedIssuers[issuer] = IssuerRole.NONE;
        emit IssuerAuthorizationRevoked(issuer, block.timestamp);
    }

    /**
     * @dev Check if address is authorized to issue event type
     * @param issuer Address to check
     * @param eventType Type of event
     * @return True if authorized
     */
    function isAuthorizedIssuer(address issuer, EventType eventType)
        public
        view
        returns (bool)
    {
        IssuerRole role = authorizedIssuers[issuer];
        if (role == IssuerRole.NONE) return false;

        return allowedIssuers[eventType][role];
    }

    // ============ EVENT ISSUANCE (MOBI VID II) ============

    /**
     * @dev Record a lifecycle event
     *
     * This is the core MOBI VID II function
     *
     * @param vehicleIdentity Vehicle DID
     * @param eventType Type of event
     * @param odometer Odometer reading
     * @param dataHash IPFS hash of detailed event data
     * @param credentialHash Hash of W3C Verifiable Credential
     * @param jurisdiction Legal jurisdiction
     * @return eventId Unique event identifier
     */
    function recordLifecycleEvent(
        address vehicleIdentity,
        EventType eventType,
        uint256 odometer,
        bytes32 dataHash,
        bytes32 credentialHash,
        string calldata jurisdiction
    )
        external
        vehicleRegistered(vehicleIdentity)
        onlyAuthorizedIssuer(eventType)
        returns (bytes32 eventId)
    {
        require(!revoked[vehicleIdentity], "Vehicle identity is revoked");

        // Generate unique event ID
        eventId = keccak256(abi.encodePacked(
            vehicleIdentity,
            eventType,
            msg.sender,
            block.timestamp,
            vehicleEventCount[vehicleIdentity]
        ));

        // Create event
        lifecycleEvents[vehicleIdentity][eventId] = LifecycleEvent({
            eventId: eventId,
            eventType: eventType,
            issuer: msg.sender,
            timestamp: block.timestamp,
            odometer: odometer,
            dataHash: dataHash,
            credentialHash: credentialHash,
            verified: _isVerifiedIssuer(msg.sender),
            jurisdiction: jurisdiction,
            blockNumber: block.number
        });

        // Add to vehicle's event list
        vehicleEventIds[vehicleIdentity].push(eventId);

        // Update counters
        vehicleEventCount[vehicleIdentity]++;
        eventTypeCount[vehicleIdentity][eventType]++;

        emit LifecycleEventRecorded(
            vehicleIdentity,
            eventId,
            eventType,
            msg.sender,
            odometer,
            block.timestamp
        );

        return eventId;
    }

    /**
     * @dev Attest to an event
     * Allows multiple parties to sign off on an event
     *
     * @param eventId Event to attest
     * @param vehicleIdentity Vehicle DID
     * @param signature Signature of event data
     */
    function attestEvent(
        bytes32 eventId,
        address vehicleIdentity,
        bytes calldata signature
    )
        external
    {
        require(
            lifecycleEvents[vehicleIdentity][eventId].eventId == eventId,
            "Event does not exist"
        );
        require(
            authorizedIssuers[msg.sender] != IssuerRole.NONE,
            "Not authorized to attest"
        );

        // Create attestation
        EventAttestation memory attestation = EventAttestation({
            attester: msg.sender,
            role: authorizedIssuers[msg.sender],
            signature: signature,
            timestamp: block.timestamp
        });

        eventAttestations[eventId].push(attestation);

        emit EventAttested(
            eventId,
            msg.sender,
            authorizedIssuers[msg.sender],
            block.timestamp
        );
    }

    // ============ QUERY FUNCTIONS ============

    /**
     * @dev Get all event IDs for a vehicle
     * @param vehicleIdentity Vehicle DID
     * @return Array of event IDs
     */
    function getVehicleEvents(address vehicleIdentity)
        external
        view
        vehicleRegistered(vehicleIdentity)
        returns (bytes32[] memory)
    {
        return vehicleEventIds[vehicleIdentity];
    }

    /**
     * @dev Get event details
     * @param vehicleIdentity Vehicle DID
     * @param eventId Event ID
     * @return Event details
     */
    function getEvent(address vehicleIdentity, bytes32 eventId)
        external
        view
        returns (LifecycleEvent memory)
    {
        require(
            lifecycleEvents[vehicleIdentity][eventId].eventId == eventId,
            "Event does not exist"
        );
        return lifecycleEvents[vehicleIdentity][eventId];
    }

    /**
     * @dev Get event attestations
     * @param eventId Event ID
     * @return Array of attestations
     */
    function getEventAttestations(bytes32 eventId)
        external
        view
        returns (EventAttestation[] memory)
    {
        return eventAttestations[eventId];
    }

    /**
     * @dev Get event count by type
     * @param vehicleIdentity Vehicle DID
     * @param eventType Type of event
     * @return Count of events of that type
     */
    function getEventTypeCount(address vehicleIdentity, EventType eventType)
        external
        view
        returns (uint256)
    {
        return eventTypeCount[vehicleIdentity][eventType];
    }

    /**
     * @dev Get complete vehicle history (VID I + VID II)
     * @param vehicleIdentity Vehicle DID
     * @return birth Birth certificate
     * @return eventCount Number of lifecycle events
     * @return lastEvent Most recent event ID
     */
    function getCompleteHistory(address vehicleIdentity)
        external
        view
        vehicleRegistered(vehicleIdentity)
        returns (
            VehicleBirth memory birth,
            uint256 eventCount,
            bytes32 lastEvent
        )
    {
        birth = vehicleBirths[vehicleIdentity];
        eventCount = vehicleEventCount[vehicleIdentity];

        if (eventCount > 0) {
            lastEvent = vehicleEventIds[vehicleIdentity][eventCount - 1];
        }

        return (birth, eventCount, lastEvent);
    }

    /**
     * @dev Get events by type
     * @param vehicleIdentity Vehicle DID
     * @param eventType Type of events to retrieve
     * @return eventIds Array of event IDs of specified type
     */
    function getEventsByType(address vehicleIdentity, EventType eventType)
        external
        view
        returns (bytes32[] memory eventIds)
    {
        bytes32[] memory allEvents = vehicleEventIds[vehicleIdentity];
        uint256 count = eventTypeCount[vehicleIdentity][eventType];

        eventIds = new bytes32[](count);
        uint256 index = 0;

        for (uint256 i = 0; i < allEvents.length; i++) {
            if (lifecycleEvents[vehicleIdentity][allEvents[i]].eventType == eventType) {
                eventIds[index] = allEvents[i];
                index++;
            }
        }

        return eventIds;
    }

    /**
     * @dev Get odometer history (for fraud detection)
     * @param vehicleIdentity Vehicle DID
     * @return odometerReadings Array of odometer readings with timestamps
     */
    function getOdometerHistory(address vehicleIdentity)
        external
        view
        returns (uint256[] memory odometerReadings, uint256[] memory timestamps)
    {
        bytes32[] memory allEvents = vehicleEventIds[vehicleIdentity];
        odometerReadings = new uint256[](allEvents.length);
        timestamps = new uint256[](allEvents.length);

        for (uint256 i = 0; i < allEvents.length; i++) {
            LifecycleEvent memory evt = lifecycleEvents[vehicleIdentity][allEvents[i]];
            odometerReadings[i] = evt.odometer;
            timestamps[i] = evt.timestamp;
        }

        return (odometerReadings, timestamps);
    }

    // ============ INTERNAL FUNCTIONS ============

    /**
     * @dev Initialize allowed issuers for each event type
     */
    function _initializeAllowedIssuers() internal {
        // MAINTENANCE: Dealer, Service Center, Owner
        allowedIssuers[EventType.MAINTENANCE][IssuerRole.DEALER] = true;
        allowedIssuers[EventType.MAINTENANCE][IssuerRole.SERVICE_CENTER] = true;
        allowedIssuers[EventType.MAINTENANCE][IssuerRole.OWNER] = true;

        // REPAIR: Dealer, Service Center
        allowedIssuers[EventType.REPAIR][IssuerRole.DEALER] = true;
        allowedIssuers[EventType.REPAIR][IssuerRole.SERVICE_CENTER] = true;

        // ACCIDENT: Police, Insurance, Owner
        allowedIssuers[EventType.ACCIDENT][IssuerRole.POLICE] = true;
        allowedIssuers[EventType.ACCIDENT][IssuerRole.INSURANCE_COMPANY] = true;
        allowedIssuers[EventType.ACCIDENT][IssuerRole.OWNER] = true;

        // RECALL: Manufacturer only
        allowedIssuers[EventType.RECALL][IssuerRole.MANUFACTURER] = true;

        // INSPECTION: Inspection Station, Government DMV
        allowedIssuers[EventType.INSPECTION][IssuerRole.INSPECTION_STATION] = true;
        allowedIssuers[EventType.INSPECTION][IssuerRole.GOVERNMENT_DMV] = true;

        // MODIFICATION: Service Center, Owner
        allowedIssuers[EventType.MODIFICATION][IssuerRole.SERVICE_CENTER] = true;
        allowedIssuers[EventType.MODIFICATION][IssuerRole.OWNER] = true;

        // THEFT_REPORT: Police, Owner
        allowedIssuers[EventType.THEFT_REPORT][IssuerRole.POLICE] = true;
        allowedIssuers[EventType.THEFT_REPORT][IssuerRole.OWNER] = true;

        // RECOVERY: Police only
        allowedIssuers[EventType.RECOVERY][IssuerRole.POLICE] = true;

        // INSURANCE_CLAIM: Insurance, Owner
        allowedIssuers[EventType.INSURANCE_CLAIM][IssuerRole.INSURANCE_COMPANY] = true;
        allowedIssuers[EventType.INSURANCE_CLAIM][IssuerRole.OWNER] = true;

        // REGISTRATION: Government DMV only
        allowedIssuers[EventType.REGISTRATION][IssuerRole.GOVERNMENT_DMV] = true;

        // DECOMMISSION: Manufacturer, Government DMV
        allowedIssuers[EventType.DECOMMISSION][IssuerRole.MANUFACTURER] = true;
        allowedIssuers[EventType.DECOMMISSION][IssuerRole.GOVERNMENT_DMV] = true;
    }

    /**
     * @dev Check if issuer is verified (government, manufacturer, etc.)
     * @param issuer Address to check
     * @return True if verified issuer
     */
    function _isVerifiedIssuer(address issuer) internal view returns (bool) {
        IssuerRole role = authorizedIssuers[issuer];

        // Verified roles
        return (
            role == IssuerRole.MANUFACTURER ||
            role == IssuerRole.GOVERNMENT_DMV ||
            role == IssuerRole.POLICE ||
            role == IssuerRole.DEALER ||
            role == IssuerRole.INSPECTION_STATION
        );
    }
}
