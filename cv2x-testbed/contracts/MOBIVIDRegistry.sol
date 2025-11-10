// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./ERC1056Registry.sol";

/**
 * @title MOBI VID Registry
 * @dev Implements MOBI Vehicle Identity (VID) 1.0 standard on top of ERC-1056
 *
 * Standards Compliance:
 * - MOBI VID I (Vehicle Birth Certificate)
 * - W3C Decentralized Identifiers (DIDs) v1.0
 * - ERC-1056 (Ethereum DID Registry)
 * - SSI (Self-Sovereign Identity) principles
 *
 * Key Features:
 * - Immutable vehicle birth certificates
 * - VIN privacy protection (hash + encrypted storage)
 * - Manufacturer authorization system
 * - Ownership transfer with complete history
 * - W3C DID compliance
 * - Gas-optimized storage
 */
contract MOBIVIDRegistry is ERC1056Registry {

    // ============ STRUCTS ============

    /**
     * @dev Vehicle Birth Certificate (MOBI VID I)
     * Immutable anchor for vehicle identity
     */
    struct VehicleBirth {
        bytes32 vinHash;              // SHA256(VIN + salt + vehicleDID) - for searchability
        string encryptedVIN;          // Encrypted VIN - only owner can decrypt
        bytes32 birthCertHash;        // IPFS hash of full birth certificate data
        uint256 timestamp;            // Birth registration timestamp
        address manufacturer;         // Authorized manufacturer address
        address firstOwner;           // First owner DID
        uint256 blockNumber;          // Block when registered
        bool exists;                  // True if vehicle birth was registered
    }

    /**
     * @dev Ownership Transfer Record (MOBI VID II support)
     */
    struct OwnershipTransfer {
        address from;
        address to;
        uint256 timestamp;
        uint256 blockNumber;
        uint256 odometer;             // Odometer reading at transfer
        string registrationAuthority; // Government authority that processed transfer
    }

    // ============ STORAGE ============

    // Registry authority (can authorize manufacturers)
    address public registryAuthority;

    // Authorized manufacturers (can register vehicle births)
    mapping(address => bool) public authorizedManufacturers;

    // VIN hash to vehicle identity mapping (for lookups)
    mapping(bytes32 => address) public vinHashToIdentity;

    // Vehicle birth certificates (vehicleIdentity => VehicleBirth)
    mapping(address => VehicleBirth) public vehicleBirths;

    // Ownership history (vehicleIdentity => array of transfers)
    mapping(address => OwnershipTransfer[]) public ownershipHistory;

    // ============ EVENTS ============

    /**
     * @dev Emitted when a vehicle birth certificate is registered
     */
    event VehicleBirthRegistered(
        address indexed vehicleIdentity,
        bytes32 indexed vinHash,
        address indexed manufacturer,
        address firstOwner,
        bytes32 birthCertHash,
        uint256 timestamp
    );

    /**
     * @dev Emitted when vehicle ownership is transferred
     */
    event VehicleOwnershipTransferred(
        address indexed vehicleIdentity,
        address indexed from,
        address indexed to,
        uint256 odometer,
        uint256 timestamp
    );

    /**
     * @dev Emitted when a manufacturer is authorized
     */
    event ManufacturerAuthorized(
        address indexed manufacturer,
        uint256 timestamp
    );

    /**
     * @dev Emitted when manufacturer authorization is revoked
     */
    event ManufacturerAuthorizationRevoked(
        address indexed manufacturer,
        uint256 timestamp
    );

    // ============ MODIFIERS ============

    modifier onlyRegistryAuthority() {
        require(
            msg.sender == registryAuthority,
            "Only registry authority can perform this action"
        );
        _;
    }

    modifier onlyAuthorizedManufacturer() {
        require(
            authorizedManufacturers[msg.sender],
            "Only authorized manufacturers can register vehicles"
        );
        _;
    }

    modifier vehicleNotRegistered(address vehicleIdentity) {
        require(
            !vehicleBirths[vehicleIdentity].exists,
            "Vehicle already registered"
        );
        _;
    }

    modifier vehicleRegistered(address vehicleIdentity) {
        require(
            vehicleBirths[vehicleIdentity].exists,
            "Vehicle not registered"
        );
        _;
    }

    // ============ CONSTRUCTOR ============

    constructor() {
        registryAuthority = msg.sender;
        // Automatically authorize deployer as first manufacturer (for testing)
        authorizedManufacturers[msg.sender] = true;
        emit ManufacturerAuthorized(msg.sender, block.timestamp);
    }

    // ============ MANUFACTURER MANAGEMENT ============

    /**
     * @dev Authorize a manufacturer to register vehicle births
     * @param manufacturer Address of manufacturer to authorize
     */
    function authorizeManufacturer(address manufacturer)
        external
        onlyRegistryAuthority
    {
        require(manufacturer != address(0), "Invalid manufacturer address");
        require(!authorizedManufacturers[manufacturer], "Manufacturer already authorized");

        authorizedManufacturers[manufacturer] = true;
        emit ManufacturerAuthorized(manufacturer, block.timestamp);
    }

    /**
     * @dev Revoke manufacturer authorization
     * @param manufacturer Address of manufacturer to revoke
     */
    function revokeManufacturerAuthorization(address manufacturer)
        external
        onlyRegistryAuthority
    {
        require(authorizedManufacturers[manufacturer], "Manufacturer not authorized");

        authorizedManufacturers[manufacturer] = false;
        emit ManufacturerAuthorizationRevoked(manufacturer, block.timestamp);
    }

    /**
     * @dev Transfer registry authority (e.g., to a DAO or government)
     * @param newAuthority Address of new registry authority
     */
    function transferRegistryAuthority(address newAuthority)
        external
        onlyRegistryAuthority
    {
        require(newAuthority != address(0), "Invalid authority address");
        registryAuthority = newAuthority;
    }

    // ============ VEHICLE BIRTH REGISTRATION (MOBI VID I) ============

    /**
     * @dev Register vehicle birth certificate
     *
     * This is the core MOBI VID I function. It creates an immutable
     * birth certificate that serves as the anchor for all future
     * vehicle identity operations.
     *
     * @param vehicleIdentity Address that will represent this vehicle (vehicle DID)
     * @param vinHash Hash of VIN for privacy-preserving searchability
     * @param encryptedVIN Encrypted VIN (only owner can decrypt)
     * @param birthCertHash IPFS hash of complete birth certificate data
     * @param firstOwner DID of first owner
     * @param birthAttributes Additional attributes (manufacturer data, specs, etc.)
     */
    function registerVehicleBirth(
        address vehicleIdentity,
        bytes32 vinHash,
        string calldata encryptedVIN,
        bytes32 birthCertHash,
        address firstOwner,
        bytes calldata birthAttributes
    )
        external
        onlyAuthorizedManufacturer
        vehicleNotRegistered(vehicleIdentity)
    {
        require(vehicleIdentity != address(0), "Invalid vehicle identity");
        require(vinHash != bytes32(0), "Invalid VIN hash");
        require(firstOwner != address(0), "Invalid first owner");
        require(vinHashToIdentity[vinHash] == address(0), "VIN hash already registered");

        // Create birth certificate
        vehicleBirths[vehicleIdentity] = VehicleBirth({
            vinHash: vinHash,
            encryptedVIN: encryptedVIN,
            birthCertHash: birthCertHash,
            timestamp: block.timestamp,
            manufacturer: msg.sender,
            firstOwner: firstOwner,
            blockNumber: block.number,
            exists: true
        });

        // Map VIN hash to vehicle identity for lookups
        vinHashToIdentity[vinHash] = vehicleIdentity;

        // Set initial owner in ERC-1056
        owners[vehicleIdentity] = firstOwner;

        // Store birth attributes as ERC-1056 attributes
        // This allows W3C DID document construction from events
        if (birthAttributes.length > 0) {
            bytes32 attrName = keccak256("mobi/vid/birth/attributes");
            setAttribute(
                vehicleIdentity,
                msg.sender,
                attrName,
                birthAttributes,
                type(uint256).max  // Permanent attribute
            );
        }

        emit VehicleBirthRegistered(
            vehicleIdentity,
            vinHash,
            msg.sender,
            firstOwner,
            birthCertHash,
            block.timestamp
        );

        // Also emit DIDOwnerChanged for DID resolution
        emit DIDOwnerChanged(vehicleIdentity, firstOwner, changed[vehicleIdentity]);
        changed[vehicleIdentity] = block.number;
    }

    // ============ VEHICLE OWNERSHIP (MOBI VID II) ============

    /**
     * @dev Transfer vehicle ownership
     *
     * This implements MOBI VID II functionality by tracking
     * ownership changes while preserving the immutable birth certificate.
     *
     * @param vehicleIdentity Vehicle DID
     * @param newOwner New owner DID
     * @param odometer Odometer reading at transfer
     * @param authority Registration authority (e.g., "CA DMV")
     */
    function transferVehicleOwnership(
        address vehicleIdentity,
        address newOwner,
        uint256 odometer,
        string calldata authority
    )
        external
        vehicleRegistered(vehicleIdentity)
        onlyOwner(vehicleIdentity, msg.sender)
    {
        require(newOwner != address(0), "Invalid new owner");
        require(!revoked[vehicleIdentity], "Vehicle identity is revoked");

        address currentOwner = identityOwner(vehicleIdentity);

        // Record ownership transfer
        ownershipHistory[vehicleIdentity].push(OwnershipTransfer({
            from: currentOwner,
            to: newOwner,
            timestamp: block.timestamp,
            blockNumber: block.number,
            odometer: odometer,
            registrationAuthority: authority
        }));

        // Update owner in ERC-1056
        changeOwner(vehicleIdentity, msg.sender, newOwner);

        emit VehicleOwnershipTransferred(
            vehicleIdentity,
            currentOwner,
            newOwner,
            odometer,
            block.timestamp
        );
    }

    // ============ QUERY FUNCTIONS ============

    /**
     * @dev Get vehicle birth certificate
     * @param vehicleIdentity Vehicle DID
     * @return Birth certificate data
     */
    function getVehicleBirth(address vehicleIdentity)
        external
        view
        returns (VehicleBirth memory)
    {
        require(vehicleBirths[vehicleIdentity].exists, "Vehicle not registered");
        return vehicleBirths[vehicleIdentity];
    }

    /**
     * @dev Lookup vehicle identity by VIN hash
     * @param vinHash Hash of VIN
     * @return vehicleIdentity Vehicle DID (or zero address if not found)
     */
    function lookupByVINHash(bytes32 vinHash)
        external
        view
        returns (address)
    {
        return vinHashToIdentity[vinHash];
    }

    /**
     * @dev Get ownership history for a vehicle
     * @param vehicleIdentity Vehicle DID
     * @return Array of ownership transfers
     */
    function getOwnershipHistory(address vehicleIdentity)
        external
        view
        vehicleRegistered(vehicleIdentity)
        returns (OwnershipTransfer[] memory)
    {
        return ownershipHistory[vehicleIdentity];
    }

    /**
     * @dev Get ownership history count
     * @param vehicleIdentity Vehicle DID
     * @return Number of ownership transfers
     */
    function getOwnershipHistoryCount(address vehicleIdentity)
        external
        view
        returns (uint256)
    {
        return ownershipHistory[vehicleIdentity].length;
    }

    /**
     * @dev Check if vehicle exists
     * @param vehicleIdentity Vehicle DID
     * @return True if vehicle birth certificate exists
     */
    function vehicleExists(address vehicleIdentity)
        external
        view
        returns (bool)
    {
        return vehicleBirths[vehicleIdentity].exists;
    }

    /**
     * @dev Get complete vehicle information (combines birth + ERC-1056 data)
     * @param vehicleIdentity Vehicle DID
     * @return birth Birth certificate
     * @return currentOwner Current owner address
     * @return isRevoked Whether identity is revoked
     * @return transferCount Number of ownership transfers
     */
    function getVehicleInfo(address vehicleIdentity)
        external
        view
        vehicleRegistered(vehicleIdentity)
        returns (
            VehicleBirth memory birth,
            address currentOwner,
            bool isRevoked,
            uint256 transferCount
        )
    {
        return (
            vehicleBirths[vehicleIdentity],
            identityOwner(vehicleIdentity),
            revoked[vehicleIdentity],
            ownershipHistory[vehicleIdentity].length
        );
    }

    // ============ W3C DID COMPLIANCE HELPERS ============

    /**
     * @dev Get DID string for vehicle
     * @param vehicleIdentity Vehicle address
     * @return DID string in format: did:ethr:0x{chainId}:{address}
     *
     * Note: This is a view helper. In practice, DID resolution
     * happens off-chain by parsing events.
     */
    function getVehicleDID(address vehicleIdentity)
        external
        view
        returns (string memory)
    {
        // Format: did:ethr:0x{chainId}:{address}
        // Chain ID is retrieved from block.chainid
        // In production, implement proper DID string formatting
        return string(abi.encodePacked(
            "did:ethr:0x",
            _toHexString(block.chainid),
            ":",
            _toHexString(uint256(uint160(vehicleIdentity)), 20)
        ));
    }

    // ============ INTERNAL HELPERS ============

    /**
     * @dev Convert uint to hex string
     * @param value Value to convert
     * @return Hex string
     */
    function _toHexString(uint256 value) internal pure returns (string memory) {
        if (value == 0) {
            return "0";
        }
        uint256 temp = value;
        uint256 length = 0;
        while (temp != 0) {
            length++;
            temp >>= 4;
        }
        bytes memory buffer = new bytes(length);
        while (value != 0) {
            length -= 1;
            buffer[length] = bytes1(uint8(48 + uint256(value & 0xf)));
            if (uint8(buffer[length]) > 57) {
                buffer[length] = bytes1(uint8(buffer[length]) + 39);
            }
            value >>= 4;
        }
        return string(buffer);
    }

    /**
     * @dev Convert uint to hex string with padding
     * @param value Value to convert
     * @param length Desired string length
     * @return Hex string
     */
    function _toHexString(uint256 value, uint256 length) internal pure returns (string memory) {
        bytes memory buffer = new bytes(2 * length);
        for (uint256 i = 2 * length; i > 0; --i) {
            buffer[i - 1] = bytes1(uint8(48 + uint256(value & 0xf)));
            if (uint8(buffer[i - 1]) > 57) {
                buffer[i - 1] = bytes1(uint8(buffer[i - 1]) + 39);
            }
            value >>= 4;
        }
        require(value == 0, "Hex length insufficient");
        return string(buffer);
    }
}
