// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title CVINVehicleLSP8
 * @dev Minimal, self-contained LSP8-flavored (LUKSO LSP8 Identifiable Digital
 *      Asset) vehicle identity contract for the CVIN thesis gas comparison.
 *      Does NOT import the LUKSO lsp-smart-contracts npm package.
 *
 * Model: each vehicle is a non-fungible token identified by
 *   bytes32 tokenId = keccak256(bytes(VIN))
 * with an LSP8-style per-token key-value metadata store
 * (setDataForTokenId / getDataForTokenId, DataChanged event).
 *
 * ============================================================================
 * REPRESENTATIVE IMPLEMENTATION — LSP8 feature coverage
 * ============================================================================
 * Implemented (LSP8-conformant signatures/semantics):
 * - bytes32 tokenIds (LSP8_TOKENID_FORMAT: hash of the VIN)
 * - totalSupply(), balanceOf(address), tokenOwnerOf(bytes32), tokenIdsOf(address)
 * - transfer(address from, address to, bytes32 tokenId, bool force, bytes data)
 *   with the LSP8 Transfer event shape
 *   (operator, from, to, tokenId, force, data)
 * - mint via mintVehicle() and burn/revoke via revokeVehicle() emitting
 *   Transfer from/to the zero address
 * - setDataForTokenId(bytes32,bytes32,bytes) / getDataForTokenId(bytes32,bytes32)
 *   and batch variants, emitting TokenIdDataChanged(tokenId, dataKey, dataValue)
 *   (LSP8's event name; a generic DataChanged is emitted as well for tooling)
 *
 * OMITTED relative to the full LSP8 standard (intentional — this contract is a
 * representative implementation for gas benchmarking, not a spec-complete one):
 * - LSP1 UniversalReceiver hooks: no _notifyTokenSender/_notifyTokenReceiver
 *   calls; the `force` flag is accepted but only checked against code-less
 *   recipients (no LSP1 interface probing).
 * - Operator management: authorizeOperator / revokeOperator / isOperatorFor /
 *   getOperatorsOf are not implemented; only the token owner (or the contract
 *   owner for revocation) can move a token.
 * - ERC725Y contract-level data store (setData/getData on the collection) and
 *   LSP4 DigitalAssetMetadata keys.
 * - ERC-165 interfaceId registration for LSP8 (0x3a271706).
 *
 * Access model: contract `owner` = issuing authority (mints, revokes, writes
 * token metadata); token owner = current vehicle owner (transfers the vehicle).
 * ============================================================================
 */
contract CVINVehicleLSP8 {
    // ============ Well-known metadata data keys (convenience constants) ============
    // keccak256("CVIN_VIN")
    bytes32 public constant DATA_KEY_VIN = keccak256("CVIN_VIN");
    // keccak256("CVIN_REGISTRATION")
    bytes32 public constant DATA_KEY_REGISTRATION = keccak256("CVIN_REGISTRATION");
    // keccak256("CVIN_INSPECTION")
    bytes32 public constant DATA_KEY_INSPECTION = keccak256("CVIN_INSPECTION");
    // keccak256("CVIN_INSURANCE")
    bytes32 public constant DATA_KEY_INSURANCE = keccak256("CVIN_INSURANCE");

    // ============ State ============

    /// @notice Contract owner = issuing authority
    address public owner;

    string public name;
    string public symbol;

    uint256 private _existingTokens;

    /// @dev tokenId => token owner
    mapping(bytes32 => address) private _tokenOwners;

    /// @dev owner => list of owned tokenIds
    mapping(address => bytes32[]) private _ownedTokens;

    /// @dev tokenId => index in _ownedTokens[owner]
    mapping(bytes32 => uint256) private _ownedTokensIndex;

    /// @dev LSP8-style per-token key-value store: tokenId => dataKey => value
    mapping(bytes32 => mapping(bytes32 => bytes)) private _tokenIdData;

    // ============ Events ============

    /// @dev LSP8 Transfer event shape
    event Transfer(
        address operator,
        address indexed from,
        address indexed to,
        bytes32 indexed tokenId,
        bool force,
        bytes data
    );

    /// @dev LSP8 event name for per-token data updates
    event TokenIdDataChanged(
        bytes32 indexed tokenId,
        bytes32 indexed dataKey,
        bytes dataValue
    );

    /// @dev Generic ERC725Y-style event (emitted alongside TokenIdDataChanged)
    event DataChanged(bytes32 indexed dataKey, bytes dataValue);

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    event VehicleMinted(bytes32 indexed tokenId, string vin, address indexed vehicleOwner);
    event VehicleRevoked(bytes32 indexed tokenId, address indexed previousOwner);

    // ============ Modifiers ============

    modifier onlyOwner() {
        require(msg.sender == owner, "LSP8: caller is not the contract owner");
        _;
    }

    // ============ Constructor ============

    constructor(string memory _name, string memory _symbol) {
        name = _name;
        symbol = _symbol;
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    // ============ Views ============

    function totalSupply() external view returns (uint256) {
        return _existingTokens;
    }

    function balanceOf(address tokenOwner) external view returns (uint256) {
        return _ownedTokens[tokenOwner].length;
    }

    function tokenOwnerOf(bytes32 tokenId) public view returns (address) {
        address tokenOwner = _tokenOwners[tokenId];
        require(tokenOwner != address(0), "LSP8: tokenId does not exist");
        return tokenOwner;
    }

    function tokenIdsOf(address tokenOwner) external view returns (bytes32[] memory) {
        return _ownedTokens[tokenOwner];
    }

    /// @notice Compute the tokenId for a VIN (keccak256 of the VIN string)
    function tokenIdForVIN(string calldata vin) public pure returns (bytes32) {
        return keccak256(bytes(vin));
    }

    function exists(bytes32 tokenId) public view returns (bool) {
        return _tokenOwners[tokenId] != address(0);
    }

    // ============ Identity creation (mint) ============

    /**
     * @notice Mint a vehicle identity token to `vehicleOwner`.
     *         tokenId = keccak256(bytes(vin)). The VIN is stored in the
     *         token's data store under DATA_KEY_VIN.
     */
    function mintVehicle(address vehicleOwner, string calldata vin)
        external
        onlyOwner
        returns (bytes32 tokenId)
    {
        require(vehicleOwner != address(0), "LSP8: mint to zero address");
        require(bytes(vin).length > 0, "LSP8: empty VIN");
        tokenId = keccak256(bytes(vin));
        require(_tokenOwners[tokenId] == address(0), "LSP8: tokenId already minted");

        _addTokenTo(vehicleOwner, tokenId);
        _existingTokens += 1;

        _tokenIdData[tokenId][DATA_KEY_VIN] = bytes(vin);
        emit TokenIdDataChanged(tokenId, DATA_KEY_VIN, bytes(vin));
        emit DataChanged(DATA_KEY_VIN, bytes(vin));

        emit Transfer(msg.sender, address(0), vehicleOwner, tokenId, true, "");
        emit VehicleMinted(tokenId, vin, vehicleOwner);
    }

    // ============ Transfer (LSP8 signature) ============

    /**
     * @notice Transfer a vehicle identity token. LSP8 function signature.
     * @dev Operators are not implemented: msg.sender must be the current token
     *      owner. `force` is only checked against code-less recipients (no
     *      LSP1 probing — see header).
     */
    function transfer(
        address from,
        address to,
        bytes32 tokenId,
        bool force,
        bytes calldata data
    ) external {
        address tokenOwner = tokenOwnerOf(tokenId);
        require(tokenOwner == from, "LSP8: transfer from incorrect owner");
        require(msg.sender == tokenOwner, "LSP8: caller is not the token owner");
        require(to != address(0), "LSP8: transfer to zero address");
        require(to != from, "LSP8: cannot transfer to self");
        if (!force) {
            require(to.code.length > 0, "LSP8: recipient is an EOA (use force=true)");
        }

        _removeTokenFrom(from, tokenId);
        _addTokenTo(to, tokenId);

        emit Transfer(msg.sender, from, to, tokenId, force, data);
    }

    // ============ Revocation (burn) ============

    /**
     * @notice Revoke (burn) a vehicle identity token. Callable by the issuing
     *         authority (contract owner) or the current token owner.
     *         The token's data store entries remain readable off-chain via
     *         past events but are not cleared on-chain (gas-representative).
     */
    function revokeVehicle(bytes32 tokenId, bytes calldata data) external {
        address tokenOwner = tokenOwnerOf(tokenId);
        require(
            msg.sender == owner || msg.sender == tokenOwner,
            "LSP8: caller is not authority nor token owner"
        );

        _removeTokenFrom(tokenOwner, tokenId);
        _existingTokens -= 1;

        emit Transfer(msg.sender, tokenOwner, address(0), tokenId, true, data);
        emit VehicleRevoked(tokenId, tokenOwner);
    }

    // ============ LSP8 per-token data store ============

    /**
     * @notice Set a data key-value pair for a specific tokenId (LSP8 signature).
     *         Only the issuing authority may write vehicle metadata.
     */
    function setDataForTokenId(
        bytes32 tokenId,
        bytes32 dataKey,
        bytes calldata dataValue
    ) external onlyOwner {
        require(exists(tokenId), "LSP8: tokenId does not exist");
        _tokenIdData[tokenId][dataKey] = dataValue;
        emit TokenIdDataChanged(tokenId, dataKey, dataValue);
        emit DataChanged(dataKey, dataValue);
    }

    function getDataForTokenId(bytes32 tokenId, bytes32 dataKey)
        external
        view
        returns (bytes memory)
    {
        return _tokenIdData[tokenId][dataKey];
    }

    /// @notice Batch variant (LSP8 signature)
    function setDataBatchForTokenIds(
        bytes32[] calldata tokenIds,
        bytes32[] calldata dataKeys,
        bytes[] calldata dataValues
    ) external onlyOwner {
        require(
            tokenIds.length == dataKeys.length && dataKeys.length == dataValues.length,
            "LSP8: array length mismatch"
        );
        for (uint256 i = 0; i < tokenIds.length; i++) {
            require(exists(tokenIds[i]), "LSP8: tokenId does not exist");
            _tokenIdData[tokenIds[i]][dataKeys[i]] = dataValues[i];
            emit TokenIdDataChanged(tokenIds[i], dataKeys[i], dataValues[i]);
            emit DataChanged(dataKeys[i], dataValues[i]);
        }
    }

    /// @notice Batch read variant (LSP8 signature)
    function getDataBatchForTokenIds(
        bytes32[] calldata tokenIds,
        bytes32[] calldata dataKeys
    ) external view returns (bytes[] memory dataValues) {
        require(tokenIds.length == dataKeys.length, "LSP8: array length mismatch");
        dataValues = new bytes[](tokenIds.length);
        for (uint256 i = 0; i < tokenIds.length; i++) {
            dataValues[i] = _tokenIdData[tokenIds[i]][dataKeys[i]];
        }
    }

    // ============ Contract ownership (issuing authority) ============

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "LSP8: new owner is zero address");
        address previousOwner = owner;
        owner = newOwner;
        emit OwnershipTransferred(previousOwner, newOwner);
    }

    // ============ Internal enumeration helpers ============

    function _addTokenTo(address to, bytes32 tokenId) private {
        _tokenOwners[tokenId] = to;
        _ownedTokensIndex[tokenId] = _ownedTokens[to].length;
        _ownedTokens[to].push(tokenId);
    }

    function _removeTokenFrom(address from, bytes32 tokenId) private {
        // swap and pop
        bytes32[] storage tokens = _ownedTokens[from];
        uint256 index = _ownedTokensIndex[tokenId];
        uint256 lastIndex = tokens.length - 1;
        if (index != lastIndex) {
            bytes32 lastTokenId = tokens[lastIndex];
            tokens[index] = lastTokenId;
            _ownedTokensIndex[lastTokenId] = index;
        }
        tokens.pop();
        delete _ownedTokensIndex[tokenId];
        delete _tokenOwners[tokenId];
    }
}
