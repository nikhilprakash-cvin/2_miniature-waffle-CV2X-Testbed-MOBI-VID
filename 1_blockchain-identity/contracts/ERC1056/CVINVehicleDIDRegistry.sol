// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./EthereumDIDRegistry.sol";

/**
 * @title CVINVehicleDIDRegistry
 * @dev Vehicle-specific DID management using ERC-1056
 * @notice Provides convenience functions for vehicle identity lifecycle
 *
 * Features:
 * - VIN-to-DID mapping
 * - Vehicle-specific attributes
 * - Ownership transfer tracking
 * - Service history references
 * - Credential issuance delegation
 */
contract CVINVehicleDIDRegistry {
    // ============ State Variables ============

    /// @dev The underlying ERC-1056 registry
    EthereumDIDRegistry public didRegistry;

    /// @dev Mapping from VIN hash to DID address
    mapping(bytes32 => address) public vinToDID;

    /// @dev Mapping from DID to VIN (for reverse lookup)
    mapping(address => string) public didToVIN;

    /// @dev Authorized manufacturers who can create vehicle DIDs
    mapping(address => bool) public authorizedManufacturers;

    /// @dev Contract owner
    address public owner;

    // ============ Attribute Keys (bytes32) ============

    bytes32 public constant DID_VIN = keccak256("did/vehicle/vin");
    bytes32 public constant DID_MAKE = keccak256("did/vehicle/make");
    bytes32 public constant DID_MODEL = keccak256("did/vehicle/model");
    bytes32 public constant DID_YEAR = keccak256("did/vehicle/year");
    bytes32 public constant DID_COLOR = keccak256("did/vehicle/color");
    bytes32 public constant DID_ENGINE = keccak256("did/vehicle/engineNumber");
    bytes32 public constant DID_MANUFACTURING_DATE =
        keccak256("did/vehicle/manufacturingDate");
    bytes32 public constant DID_AUTONOMY_LEVEL =
        keccak256("did/vehicle/autonomyLevel");

    // Service Endpoints
    bytes32 public constant SVC_CREDENTIAL_SERVICE =
        keccak256("did/svc/CredentialService");
    bytes32 public constant SVC_MESSAGING = keccak256("did/svc/MessagingService");
    bytes32 public constant SVC_TELEMETRY = keccak256("did/svc/TelemetryService");

    // Delegate Types
    bytes32 public constant DELEGATE_VERIKEY = keccak256("veriKey");
    bytes32 public constant DELEGATE_SIGAUTH = keccak256("sigAuth");

    // ============ Events ============

    event VehicleDIDCreated(
        address indexed did,
        string vin,
        address indexed owner,
        address indexed manufacturer
    );

    event VehicleOwnershipTransferred(
        address indexed did,
        address indexed previousOwner,
        address indexed newOwner
    );

    event ManufacturerAuthorized(address indexed manufacturer, bool authorized);

    // ============ Modifiers ============

    modifier onlyContractOwner() {
        require(msg.sender == owner, "CVINRegistry: not owner");
        _;
    }

    modifier onlyAuthorizedManufacturer() {
        require(
            authorizedManufacturers[msg.sender],
            "CVINRegistry: not authorized manufacturer"
        );
        _;
    }

    modifier onlyVehicleOwner(address did) {
        require(
            msg.sender == didRegistry.identityOwner(did),
            "CVINRegistry: not vehicle owner"
        );
        _;
    }

    // ============ Constructor ============

    constructor(address _didRegistry) {
        didRegistry = EthereumDIDRegistry(_didRegistry);
        owner = msg.sender;
        authorizedManufacturers[msg.sender] = true;
    }

    // ============ Admin Functions ============

    function setAuthorizedManufacturer(
        address manufacturer,
        bool authorized
    ) external onlyContractOwner {
        authorizedManufacturers[manufacturer] = authorized;
        emit ManufacturerAuthorized(manufacturer, authorized);
    }

    // ============ Vehicle DID Creation ============

    /**
     * @notice Create a new vehicle DID with comprehensive attributes
     * @param vin Vehicle Identification Number
     * @param vehicleOwner Initial owner address
     * @param make Vehicle make (e.g., "Honda")
     * @param model Vehicle model (e.g., "Accord")
     * @param year Manufacturing year
     * @param color Vehicle color
     * @param engineNumber Engine identification number
     * @param manufacturingDate Date of manufacture (timestamp)
     * @param autonomyLevel SAE autonomy level
     * @return did The created DID address
     */
    function createVehicleDID(
        string memory vin,
        address vehicleOwner,
        string memory make,
        string memory model,
        uint16 year,
        string memory color,
        string memory engineNumber,
        uint256 manufacturingDate,
        string memory autonomyLevel
    ) external onlyAuthorizedManufacturer returns (address did) {
        // Validate VIN
        require(bytes(vin).length == 17, "CVINRegistry: invalid VIN length");

        bytes32 vinHash = keccak256(abi.encodePacked(vin));
        require(vinToDID[vinHash] == address(0), "CVINRegistry: VIN already registered");

        // In ERC-1056, the vehicleOwner's address IS the DID
        // Any Ethereum address is implicitly a valid DID
        did = vehicleOwner;

        // Store VIN mapping
        vinToDID[vinHash] = did;
        didToVIN[did] = vin;

        // Note: In ERC-1056, attributes are set by the DID owner (vehicle owner)
        // The manufacturer just creates the registration mapping
        // Vehicle owner will call setVehicleAttributes() to add attributes

        emit VehicleDIDCreated(did, vin, vehicleOwner, msg.sender);

        return did;
    }

    /**
     * @notice Set vehicle attributes (called by vehicle owner after registration)
     * @param make Vehicle make
     * @param model Vehicle model
     * @param year Manufacturing year
     * @param color Vehicle color
     * @param engineNumber Engine identification
     * @param manufacturingDate Manufacturing date
     * @param autonomyLevel SAE autonomy level
     */
    function setVehicleAttributes(
        string memory make,
        string memory model,
        uint16 year,
        string memory color,
        string memory engineNumber,
        uint256 manufacturingDate,
        string memory autonomyLevel
    ) external {
        // Caller's address is their DID in ERC-1056
        address did = msg.sender;

        // Verify this DID has a registered VIN
        require(bytes(didToVIN[did]).length > 0, "CVINRegistry: DID not registered");

        uint256 permanentValidity = type(uint256).max;

        // Set all vehicle attributes
        didRegistry.setAttribute(did, DID_VIN, bytes(didToVIN[did]), permanentValidity);
        didRegistry.setAttribute(did, DID_MAKE, bytes(make), permanentValidity);
        didRegistry.setAttribute(did, DID_MODEL, bytes(model), permanentValidity);
        didRegistry.setAttribute(did, DID_YEAR, abi.encodePacked(year), permanentValidity);
        didRegistry.setAttribute(did, DID_COLOR, bytes(color), permanentValidity);
        didRegistry.setAttribute(did, DID_ENGINE, bytes(engineNumber), permanentValidity);
        didRegistry.setAttribute(did, DID_MANUFACTURING_DATE, abi.encodePacked(manufacturingDate), permanentValidity);
        didRegistry.setAttribute(did, DID_AUTONOMY_LEVEL, bytes(autonomyLevel), permanentValidity);
    }

    // ============ Ownership Management ============

    /**
     * @notice Transfer vehicle ownership
     * @dev In ERC-1056, the owner must call didRegistry.changeOwner() directly
     * @dev This function updates the VIN mapping after ownership transfer
     * @param oldOwnerDID Old owner's DID (address)
     * @param newOwnerDID New owner's DID (address)
     */
    function updateOwnershipMapping(
        address oldOwnerDID,
        address newOwnerDID
    ) external {
        // Get VIN from old owner
        string memory vin = didToVIN[oldOwnerDID];
        require(bytes(vin).length > 0, "CVINRegistry: VIN not found");

        // Verify caller is the new owner (they should have completed changeOwner on DID registry)
        require(
            didRegistry.identityOwner(oldOwnerDID) == newOwnerDID,
            "CVINRegistry: ownership not transferred in DID registry"
        );

        bytes32 vinHash = keccak256(abi.encodePacked(vin));

        // Update mappings
        delete didToVIN[oldOwnerDID];
        vinToDID[vinHash] = newOwnerDID;
        didToVIN[newOwnerDID] = vin;

        emit VehicleOwnershipTransferred(oldOwnerDID, oldOwnerDID, newOwnerDID);
    }

    // ============ Service Endpoints ============

    /**
     * @notice Set service endpoint for vehicle
     * @param did Vehicle DID
     * @param endpointType Type of endpoint (CREDENTIAL_SERVICE, MESSAGING, etc.)
     * @param endpointURL URL of the service
     * @param validity Validity period in seconds
     */
    function setServiceEndpoint(
        address did,
        bytes32 endpointType,
        string memory endpointURL,
        uint validity
    ) external onlyVehicleOwner(did) {
        didRegistry.setAttribute(did, endpointType, bytes(endpointURL), validity);
    }

    // ============ Delegate Management (Verification Keys) ============

    /**
     * @notice Add verification key delegate for credential issuance
     * @param did Vehicle DID
     * @param delegateAddress Address of the delegate
     * @param delegateType Type of delegate (VERIKEY, SIGAUTH)
     * @param validity Validity period in seconds
     */
    function addVerificationDelegate(
        address did,
        address delegateAddress,
        bytes32 delegateType,
        uint validity
    ) external onlyVehicleOwner(did) {
        didRegistry.addDelegate(did, delegateType, delegateAddress, validity);
    }

    /**
     * @notice Revoke verification delegate
     * @param did Vehicle DID
     * @param delegateAddress Address of the delegate
     * @param delegateType Type of delegate
     */
    function revokeVerificationDelegate(
        address did,
        address delegateAddress,
        bytes32 delegateType
    ) external onlyVehicleOwner(did) {
        didRegistry.revokeDelegate(did, delegateType, delegateAddress);
    }

    // ============ Query Functions ============

    /**
     * @notice Get DID address from VIN
     * @param vin Vehicle Identification Number
     * @return DID address (address(0) if not found)
     */
    function getDIDFromVIN(string memory vin) external view returns (address) {
        bytes32 vinHash = keccak256(abi.encodePacked(vin));
        return vinToDID[vinHash];
    }

    /**
     * @notice Get VIN from DID address
     * @param did DID address
     * @return VIN string (empty if not found)
     */
    function getVINFromDID(address did) external view returns (string memory) {
        return didToVIN[did];
    }

    /**
     * @notice Get vehicle owner
     * @param did Vehicle DID
     * @return Owner address
     */
    function getVehicleOwner(address did) external view returns (address) {
        return didRegistry.identityOwner(did);
    }

    /**
     * @notice Check if a delegate is valid
     * @param did Vehicle DID
     * @param delegateType Type of delegate
     * @param delegateAddress Delegate address
     * @return True if delegate is currently valid
     */
    function isValidDelegate(
        address did,
        bytes32 delegateType,
        address delegateAddress
    ) external view returns (bool) {
        return didRegistry.validDelegate(did, delegateType, delegateAddress);
    }
}
