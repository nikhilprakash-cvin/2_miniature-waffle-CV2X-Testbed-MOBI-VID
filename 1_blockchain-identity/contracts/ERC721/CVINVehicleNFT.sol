// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721Enumerable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

/**
 * @title CVINVehicleNFT
 * @dev ERC-721 based Vehicle Identity with DID integration
 * @notice Each NFT represents a unique vehicle identity
 *
 * Features:
 * - VIN-based vehicle identity
 * - Ownership tracking via NFT ownership
 * - Complete transfer history on-chain
 * - Vehicle metadata stored on IPFS
 * - DID resolution (did:nft:erc721:{contractAddress}:{tokenId})
 * - Role-based access (manufacturers, inspectors, service centers)
 * - Enumerable for efficient queries
 */
contract CVINVehicleNFT is ERC721, ERC721URIStorage, ERC721Enumerable, AccessControl {
    // ============ State Variables ============

    /// @dev Token ID counter (OpenZeppelin v5 pattern)
    uint256 private _nextTokenId = 1;

    /// @dev Role definitions
    bytes32 public constant MANUFACTURER_ROLE = keccak256("MANUFACTURER_ROLE");
    bytes32 public constant INSPECTOR_ROLE = keccak256("INSPECTOR_ROLE");
    bytes32 public constant SERVICE_CENTER_ROLE = keccak256("SERVICE_CENTER_ROLE");

    /// @dev Mapping from VIN to token ID
    mapping(string => uint256) public vinToTokenId;

    /// @dev Mapping from token ID to VIN
    mapping(uint256 => string) public tokenIdToVIN;

    /// @dev Vehicle metadata
    struct VehicleMetadata {
        string vin;
        string make;
        string model;
        uint16 year;
        string color;
        address manufacturer;
        uint256 mintTimestamp;
        bool active;
    }

    mapping(uint256 => VehicleMetadata) public vehicleMetadata;

    /// @dev Transfer history
    struct TransferRecord {
        address from;
        address to;
        uint256 timestamp;
        uint256 blockNumber;
    }

    mapping(uint256 => TransferRecord[]) public transferHistory;

    /// @dev Service records (references to off-chain data)
    mapping(uint256 => string[]) public serviceRecords;

    // ============ Events ============

    event VehicleMinted(
        uint256 indexed tokenId,
        string vin,
        address indexed owner,
        address indexed manufacturer
    );

    event VehicleTransferred(
        uint256 indexed tokenId,
        address indexed from,
        address indexed to,
        uint256 timestamp
    );

    event ServiceRecordAdded(
        uint256 indexed tokenId,
        string recordURI,
        address indexed addedBy
    );

    event VehicleDeactivated(uint256 indexed tokenId, address indexed by);

    // ============ Constructor ============

    constructor() ERC721("CVIN Vehicle Identity", "CVIN-VID") {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(MANUFACTURER_ROLE, msg.sender);
    }

    // ============ Minting Functions ============

    /**
     * @notice Mint a new vehicle NFT (manufacturer only)
     * @param to Initial owner address
     * @param vin Vehicle Identification Number
     * @param make Vehicle make
     * @param model Vehicle model
     * @param year Manufacturing year
     * @param color Vehicle color
     * @param metadataURI IPFS URI for comprehensive metadata
     * @return tokenId The minted token ID
     */
    function mintVehicle(
        address to,
        string memory vin,
        string memory make,
        string memory model,
        uint16 year,
        string memory color,
        string memory metadataURI
    ) external onlyRole(MANUFACTURER_ROLE) returns (uint256) {
        require(bytes(vin).length == 17, "CVINVehicleNFT: invalid VIN length");
        require(vinToTokenId[vin] == 0, "CVINVehicleNFT: VIN already minted");
        require(to != address(0), "CVINVehicleNFT: mint to zero address");

        uint256 tokenId = _nextTokenId++;


        // Mint NFT
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, metadataURI);

        // Store mappings
        vinToTokenId[vin] = tokenId;
        tokenIdToVIN[tokenId] = vin;

        // Store metadata
        vehicleMetadata[tokenId] = VehicleMetadata({
            vin: vin,
            make: make,
            model: model,
            year: year,
            color: color,
            manufacturer: msg.sender,
            mintTimestamp: block.timestamp,
            active: true
        });

        // Record initial "transfer" (mint)
        transferHistory[tokenId].push(TransferRecord({
            from: address(0),
            to: to,
            timestamp: block.timestamp,
            blockNumber: block.number
        }));

        emit VehicleMinted(tokenId, vin, to, msg.sender);

        return tokenId;
    }

    // ============ Transfer Override ============

    /**
     * @dev Override _update to track transfer history
     */
    function _update(address to, uint256 tokenId, address auth)
        internal
        override(ERC721, ERC721Enumerable)
        returns (address)
    {
        address from = _ownerOf(tokenId);

        // Record transfer if not minting
        if (from != address(0) && to != address(0)) {
            transferHistory[tokenId].push(TransferRecord({
                from: from,
                to: to,
                timestamp: block.timestamp,
                blockNumber: block.number
            }));

            emit VehicleTransferred(tokenId, from, to, block.timestamp);
        }

        return super._update(to, tokenId, auth);
    }

    // ============ Service Records ============

    /**
     * @notice Add service record reference
     * @param tokenId Vehicle token ID
     * @param recordURI IPFS URI of service record
     */
    function addServiceRecord(uint256 tokenId, string memory recordURI)
        external
        onlyRole(SERVICE_CENTER_ROLE)
    {
        require(_ownerOf(tokenId) != address(0), "CVINVehicleNFT: token does not exist");
        serviceRecords[tokenId].push(recordURI);
        emit ServiceRecordAdded(tokenId, recordURI, msg.sender);
    }

    /**
     * @notice Get all service records for a vehicle
     * @param tokenId Vehicle token ID
     * @return Array of service record URIs
     */
    function getServiceRecords(uint256 tokenId)
        external
        view
        returns (string[] memory)
    {
        return serviceRecords[tokenId];
    }

    // ============ Transfer History ============

    /**
     * @notice Get complete transfer history for a vehicle
     * @param tokenId Vehicle token ID
     * @return Array of transfer records
     */
    function getTransferHistory(uint256 tokenId)
        external
        view
        returns (TransferRecord[] memory)
    {
        return transferHistory[tokenId];
    }

    /**
     * @notice Get ownership chain (all previous owners)
     * @param tokenId Vehicle token ID
     * @return Array of owner addresses
     */
    function getOwnershipChain(uint256 tokenId)
        external
        view
        returns (address[] memory)
    {
        TransferRecord[] memory history = transferHistory[tokenId];
        address[] memory owners = new address[](history.length);

        for (uint i = 0; i < history.length; i++) {
            owners[i] = history[i].to;
        }

        return owners;
    }

    // ============ Vehicle Management ============

    /**
     * @notice Deactivate vehicle (end-of-life, total loss, etc.)
     * @param tokenId Vehicle token ID
     */
    function deactivateVehicle(uint256 tokenId)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        require(_ownerOf(tokenId) != address(0), "CVINVehicleNFT: token does not exist");
        vehicleMetadata[tokenId].active = false;
        emit VehicleDeactivated(tokenId, msg.sender);
    }

    /**
     * @notice Check if vehicle is active
     * @param tokenId Vehicle token ID
     * @return True if vehicle is active
     */
    function isVehicleActive(uint256 tokenId) external view returns (bool) {
        return vehicleMetadata[tokenId].active;
    }

    // ============ DID Resolution ============

    /**
     * @notice Get DID for a vehicle
     * @param tokenId Vehicle token ID
     * @return DID string (did:nft:erc721:{contractAddress}:{tokenId})
     */
    function getVehicleDID(uint256 tokenId) external view returns (string memory) {
        require(_ownerOf(tokenId) != address(0), "CVINVehicleNFT: token does not exist");

        return string(abi.encodePacked(
            "did:nft:erc721:",
            toHexString(address(this)),
            ":",
            Strings.toString(tokenId)
        ));
    }

    /**
     * @notice Get token ID from VIN
     * @param vin Vehicle Identification Number
     * @return Token ID
     */
    function getTokenIdFromVIN(string memory vin) external view returns (uint256) {
        uint256 tokenId = vinToTokenId[vin];
        require(tokenId != 0, "CVINVehicleNFT: VIN not found");
        return tokenId;
    }

    /**
     * @notice Get VIN from token ID
     * @param tokenId Token ID
     * @return VIN string
     */
    function getVINFromTokenId(uint256 tokenId) external view returns (string memory) {
        require(_ownerOf(tokenId) != address(0), "CVINVehicleNFT: token does not exist");
        return tokenIdToVIN[tokenId];
    }

    // ============ Query Functions ============

    /**
     * @notice Get all vehicles owned by an address
     * @param owner Owner address
     * @return Array of token IDs
     */
    function getVehiclesByOwner(address owner) external view returns (uint256[] memory) {
        uint256 balance = balanceOf(owner);
        uint256[] memory tokens = new uint256[](balance);

        for (uint256 i = 0; i < balance; i++) {
            tokens[i] = tokenOfOwnerByIndex(owner, i);
        }

        return tokens;
    }

    /**
     * @notice Get total number of vehicles minted
     * @return Total supply
     */
    function getTotalVehicles() external view returns (uint256) {
        return _nextTokenId - 1;
    }

    // ============ Role Management ============

    function grantManufacturerRole(address account) external onlyRole(DEFAULT_ADMIN_ROLE) {
        grantRole(MANUFACTURER_ROLE, account);
    }

    function grantInspectorRole(address account) external onlyRole(DEFAULT_ADMIN_ROLE) {
        grantRole(INSPECTOR_ROLE, account);
    }

    function grantServiceCenterRole(address account) external onlyRole(DEFAULT_ADMIN_ROLE) {
        grantRole(SERVICE_CENTER_ROLE, account);
    }

    // ============ Helper Functions ============

    function toHexString(address addr) internal pure returns (string memory) {
        bytes memory buffer = new bytes(40);
        for (uint256 i = 0; i < 20; i++) {
            bytes1 b = bytes1(uint8(uint256(uint160(addr)) / (2**(8*(19 - i)))));
            bytes1 hi = bytes1(uint8(b) / 16);
            bytes1 lo = bytes1(uint8(b) - 16 * uint8(hi));
            buffer[2*i] = char(hi);
            buffer[2*i+1] = char(lo);
        }
        return string(abi.encodePacked("0x", string(buffer)));
    }

    function char(bytes1 b) internal pure returns (bytes1 c) {
        if (uint8(b) < 10) return bytes1(uint8(b) + 0x30);
        else return bytes1(uint8(b) + 0x57);
    }

    // ============ Required Overrides ============

    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721Enumerable, ERC721URIStorage, AccessControl)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    function _increaseBalance(address account, uint128 value)
        internal
        override(ERC721, ERC721Enumerable)
    {
        super._increaseBalance(account, value);
    }
}
