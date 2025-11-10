// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title ERC1056 DID Registry for Connected Vehicles
 * @dev Lightweight Ethereum DID Registry (ERC-1056 compliant)
 *
 * Based on: https://github.com/uport-project/ethr-did-registry
 *
 * This contract manages decentralized identifiers (DIDs) for vehicles
 * in a gas-efficient manner suitable for V2X applications.
 *
 * Key Features:
 * - Minimal on-chain storage (gas efficient)
 * - Event-based DID document construction
 * - Delegate management for key rotation
 * - Attribute storage for metadata
 * - Revocation support
 */
contract ERC1056Registry {

    // Events for DID document changes
    event DIDOwnerChanged(
        address indexed identity,
        address owner,
        uint previousChange
    );

    event DIDDelegateChanged(
        address indexed identity,
        bytes32 delegateType,
        address delegate,
        uint validTo,
        uint previousChange
    );

    event DIDAttributeChanged(
        address indexed identity,
        bytes32 name,
        bytes value,
        uint validTo,
        uint previousChange
    );

    event DIDRevoked(
        address indexed identity,
        uint revokedAt
    );

    // Storage
    mapping(address => address) public owners;
    mapping(address => uint) public changed;
    mapping(address => uint) public nonce;
    mapping(address => bool) public revoked;

    // Revocation tracking
    mapping(address => uint) public revokedAt;

    modifier onlyOwner(address identity, address actor) {
        require(
            actor == identityOwner(identity),
            "Only owner can perform this action"
        );
        _;
    }

    /**
     * @dev Get the owner of an identity
     * @param identity The identity address
     * @return The owner address (defaults to identity itself)
     */
    function identityOwner(address identity) public view returns (address) {
        address owner = owners[identity];
        if (owner != address(0)) {
            return owner;
        }
        return identity;
    }

    /**
     * @dev Check if identity is revoked
     */
    function isRevoked(address identity) public view returns (bool) {
        return revoked[identity];
    }

    /**
     * @dev Transfer ownership of an identity
     */
    function changeOwner(
        address identity,
        address actor,
        address newOwner
    ) internal onlyOwner(identity, actor) {
        owners[identity] = newOwner;
        emit DIDOwnerChanged(identity, newOwner, changed[identity]);
        changed[identity] = block.number;
    }

    function changeOwner(address identity, address newOwner) public {
        changeOwner(identity, msg.sender, newOwner);
    }

    /**
     * @dev Add a delegate to an identity
     * Delegates can be used for key rotation without changing the DID
     *
     * @param identity The identity address
     * @param delegateType Type of delegate (e.g., "sigAuth" for signing)
     * @param delegate The delegate address
     * @param validity Validity period in seconds
     */
    function addDelegate(
        address identity,
        address actor,
        bytes32 delegateType,
        address delegate,
        uint validity
    ) internal onlyOwner(identity, actor) {
        require(!revoked[identity], "Identity is revoked");

        uint validTo = block.timestamp + validity;

        emit DIDDelegateChanged(
            identity,
            delegateType,
            delegate,
            validTo,
            changed[identity]
        );

        changed[identity] = block.number;
    }

    function addDelegate(
        address identity,
        bytes32 delegateType,
        address delegate,
        uint validity
    ) public {
        addDelegate(identity, msg.sender, delegateType, delegate, validity);
    }

    /**
     * @dev Revoke a delegate
     */
    function revokeDelegate(
        address identity,
        address actor,
        bytes32 delegateType,
        address delegate
    ) internal onlyOwner(identity, actor) {
        emit DIDDelegateChanged(
            identity,
            delegateType,
            delegate,
            block.timestamp,  // validTo = now (expired)
            changed[identity]
        );

        changed[identity] = block.number;
    }

    function revokeDelegate(
        address identity,
        bytes32 delegateType,
        address delegate
    ) public {
        revokeDelegate(identity, msg.sender, delegateType, delegate);
    }

    /**
     * @dev Set an attribute for an identity
     * Attributes store metadata like public keys, service endpoints, etc.
     *
     * @param identity The identity address
     * @param name Attribute name (e.g., "did/pub/secp256k1/veriKey")
     * @param value Attribute value (e.g., public key)
     * @param validity Validity period in seconds
     */
    function setAttribute(
        address identity,
        address actor,
        bytes32 name,
        bytes memory value,
        uint validity
    ) internal onlyOwner(identity, actor) {
        require(!revoked[identity], "Identity is revoked");

        uint validTo = block.timestamp + validity;

        emit DIDAttributeChanged(
            identity,
            name,
            value,
            validTo,
            changed[identity]
        );

        changed[identity] = block.number;
    }

    function setAttribute(
        address identity,
        bytes32 name,
        bytes calldata value,
        uint validity
    ) public {
        setAttribute(identity, msg.sender, name, value, validity);
    }

    /**
     * @dev Revoke an attribute
     */
    function revokeAttribute(
        address identity,
        address actor,
        bytes32 name,
        bytes memory value
    ) internal onlyOwner(identity, actor) {
        emit DIDAttributeChanged(
            identity,
            name,
            value,
            block.timestamp,  // validTo = now (expired)
            changed[identity]
        );

        changed[identity] = block.number;
    }

    function revokeAttribute(
        address identity,
        bytes32 name,
        bytes calldata value
    ) public {
        revokeAttribute(identity, msg.sender, name, value);
    }

    /**
     * @dev Revoke entire identity (for vehicle decommissioning or security)
     */
    function revokeIdentity(address identity) public onlyOwner(identity, msg.sender) {
        revoked[identity] = true;
        revokedAt[identity] = block.timestamp;

        emit DIDRevoked(identity, block.timestamp);
        changed[identity] = block.number;
    }

    /**
     * @dev Get the block number when identity was last changed
     */
    function lastChanged(address identity) public view returns (uint) {
        return changed[identity];
    }

    /**
     * @dev Utility: Register a new vehicle identity with public key
     * This is a convenience function for vehicle registration
     */
    function registerVehicle(
        address vehicleIdentity,
        bytes calldata publicKey
    ) public {
        require(!revoked[vehicleIdentity], "Identity already revoked");
        require(identityOwner(vehicleIdentity) == vehicleIdentity, "Identity already registered");

        // Set public key as attribute
        bytes32 keyName = keccak256("did/pub/secp256k1/veriKey/base64");
        setAttribute(
            vehicleIdentity,
            msg.sender,
            keyName,
            publicKey,
            31536000  // 1 year validity
        );
    }

    /**
     * @dev Utility: Update vehicle public key (key rotation)
     */
    function updateVehicleKey(
        address vehicleIdentity,
        bytes calldata newPublicKey
    ) public onlyOwner(vehicleIdentity, msg.sender) {
        require(!revoked[vehicleIdentity], "Identity is revoked");

        bytes32 keyName = keccak256("did/pub/secp256k1/veriKey/base64");

        // Revoke old key
        // In a full implementation, we'd fetch the old key value
        // For simplicity, we just set a new one

        // Set new key
        setAttribute(
            vehicleIdentity,
            msg.sender,
            keyName,
            newPublicKey,
            31536000  // 1 year validity
        );
    }

    /**
     * @dev Get identity metadata
     */
    function getIdentityInfo(address identity) public view returns (
        address owner,
        uint lastChangedBlock,
        bool isRevoked,
        uint revokedTimestamp
    ) {
        return (
            identityOwner(identity),
            changed[identity],
            revoked[identity],
            revokedAt[identity]
        );
    }
}
