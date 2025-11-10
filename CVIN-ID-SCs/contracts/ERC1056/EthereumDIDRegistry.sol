// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title EthereumDIDRegistry
 * @dev ERC-1056 Lightweight Identity Registry
 * @notice Single shared contract for all DIDs (did:ethr method)
 * @dev Gas-efficient, event-based architecture with minimal on-chain storage
 *
 * Based on: https://github.com/uport-project/ethr-did-registry
 * EIP: https://github.com/ethereum/EIPs/issues/1056
 *
 * Features:
 * - Implicit DID creation (any Ethereum address is a valid DID)
 * - Off-chain DID Document resolution via events
 * - Temporary delegates (time-bound verification keys)
 * - Flexible attributes (service endpoints, custom properties)
 * - Meta-transactions (gasless operations via signatures)
 * - Minimal gas costs (events only, no storage for attributes)
 */
contract EthereumDIDRegistry {
    // ============ Events ============

    /**
     * @dev Emitted when DID owner changes
     * @param identity The DID being modified
     * @param owner The new owner address
     * @param previousChange Block number of previous change
     */
    event DIDOwnerChanged(
        address indexed identity,
        address owner,
        uint previousChange
    );

    /**
     * @dev Emitted when a delegate is added or revoked
     * @param identity The DID being modified
     * @param delegateType Type of delegate (e.g., "veriKey", "sigAuth")
     * @param delegate The delegate address
     * @param validTo Expiration timestamp (0 = revoked)
     * @param previousChange Block number of previous change
     */
    event DIDDelegateChanged(
        address indexed identity,
        bytes32 delegateType,
        address delegate,
        uint validTo,
        uint previousChange
    );

    /**
     * @dev Emitted when an attribute is set or revoked
     * @param identity The DID being modified
     * @param name Attribute name (e.g., "did/pub/Ed25519/veriKey")
     * @param value Attribute value (public key, endpoint URL, etc.)
     * @param validTo Expiration timestamp (0 = revoked)
     * @param previousChange Block number of previous change
     */
    event DIDAttributeChanged(
        address indexed identity,
        bytes32 name,
        bytes value,
        uint validTo,
        uint previousChange
    );

    // ============ State Variables ============

    /// @dev Mapping from identity address to owner address
    mapping(address => address) public owners;

    /// @dev Mapping from identity to block number of last change
    mapping(address => uint) public changed;

    /// @dev Mapping from identity to nonce (for meta-transactions)
    mapping(address => uint) public nonce;

    /// @dev Mapping from identity to delegate type to delegate address to validity
    mapping(address => mapping(bytes32 => mapping(address => uint)))
        public delegates;

    // ============ Modifiers ============

    /**
     * @dev Ensures sender is authorized to modify the identity
     * @param identity The DID being modified
     * @param actor The address attempting modification
     */
    modifier onlyOwner(address identity, address actor) {
        require(
            actor == identityOwner(identity),
            "DIDRegistry: unauthorized"
        );
        _;
    }

    // ============ Core Functions ============

    /**
     * @notice Get the owner of a DID
     * @param identity The DID address
     * @return The owner address (defaults to identity if no owner set)
     */
    function identityOwner(address identity) public view returns (address) {
        address owner = owners[identity];
        if (owner != address(0)) {
            return owner;
        }
        return identity;
    }

    /**
     * @notice Check if a delegate is currently valid
     * @param identity The DID address
     * @param delegateType Type of delegate
     * @param delegate The delegate address
     * @return True if delegate is valid (not expired)
     */
    function validDelegate(
        address identity,
        bytes32 delegateType,
        address delegate
    ) public view returns (bool) {
        uint validity = delegates[identity][delegateType][delegate];
        return (validity > block.timestamp);
    }

    // ============ Owner Management ============

    /**
     * @notice Change the owner of a DID
     * @param identity The DID to modify
     * @param newOwner The new owner address
     */
    function changeOwner(
        address identity,
        address newOwner
    ) public onlyOwner(identity, msg.sender) {
        owners[identity] = newOwner;
        emit DIDOwnerChanged(identity, newOwner, changed[identity]);
        changed[identity] = block.number;
    }

    /**
     * @notice Change owner via signed message (meta-transaction)
     * @param identity The DID to modify
     * @param sigV ECDSA signature V
     * @param sigR ECDSA signature R
     * @param sigS ECDSA signature S
     * @param newOwner The new owner address
     */
    function changeOwnerSigned(
        address identity,
        uint8 sigV,
        bytes32 sigR,
        bytes32 sigS,
        address newOwner
    ) public {
        bytes32 hash = keccak256(
            abi.encodePacked(
                bytes1(0x19),
                bytes1(0),
                this,
                nonce[identityOwner(identity)],
                identity,
                "changeOwner",
                newOwner
            )
        );

        address signer = ecrecover(hash, sigV, sigR, sigS);
        require(signer == identityOwner(identity), "DIDRegistry: invalid signature");

        nonce[signer]++;
        owners[identity] = newOwner;
        emit DIDOwnerChanged(identity, newOwner, changed[identity]);
        changed[identity] = block.number;
    }

    // ============ Delegate Management ============

    /**
     * @notice Add a delegate with specific validity period
     * @param identity The DID to modify
     * @param delegateType Type of delegate (e.g., keccak256("veriKey"))
     * @param delegate The delegate address
     * @param validity Validity period in seconds
     */
    function addDelegate(
        address identity,
        bytes32 delegateType,
        address delegate,
        uint validity
    ) public onlyOwner(identity, msg.sender) {
        uint validTo = block.timestamp + validity;
        delegates[identity][delegateType][delegate] = validTo;
        emit DIDDelegateChanged(
            identity,
            delegateType,
            delegate,
            validTo,
            changed[identity]
        );
        changed[identity] = block.number;
    }

    /**
     * @notice Add delegate via signed message (meta-transaction)
     */
    function addDelegateSigned(
        address identity,
        uint8 sigV,
        bytes32 sigR,
        bytes32 sigS,
        bytes32 delegateType,
        address delegate,
        uint validity
    ) public {
        bytes32 hash = keccak256(
            abi.encodePacked(
                bytes1(0x19),
                bytes1(0),
                this,
                nonce[identityOwner(identity)],
                identity,
                "addDelegate",
                delegateType,
                delegate,
                validity
            )
        );

        address signer = ecrecover(hash, sigV, sigR, sigS);
        require(signer == identityOwner(identity), "DIDRegistry: invalid signature");

        nonce[signer]++;
        uint validTo = block.timestamp + validity;
        delegates[identity][delegateType][delegate] = validTo;
        emit DIDDelegateChanged(
            identity,
            delegateType,
            delegate,
            validTo,
            changed[identity]
        );
        changed[identity] = block.number;
    }

    /**
     * @notice Revoke a delegate
     * @param identity The DID to modify
     * @param delegateType Type of delegate
     * @param delegate The delegate address
     */
    function revokeDelegate(
        address identity,
        bytes32 delegateType,
        address delegate
    ) public onlyOwner(identity, msg.sender) {
        delegates[identity][delegateType][delegate] = 0;
        emit DIDDelegateChanged(
            identity,
            delegateType,
            delegate,
            0,
            changed[identity]
        );
        changed[identity] = block.number;
    }

    /**
     * @notice Revoke delegate via signed message
     */
    function revokeDelegateSigned(
        address identity,
        uint8 sigV,
        bytes32 sigR,
        bytes32 sigS,
        bytes32 delegateType,
        address delegate
    ) public {
        bytes32 hash = keccak256(
            abi.encodePacked(
                bytes1(0x19),
                bytes1(0),
                this,
                nonce[identityOwner(identity)],
                identity,
                "revokeDelegate",
                delegateType,
                delegate
            )
        );

        address signer = ecrecover(hash, sigV, sigR, sigS);
        require(signer == identityOwner(identity), "DIDRegistry: invalid signature");

        nonce[signer]++;
        delegates[identity][delegateType][delegate] = 0;
        emit DIDDelegateChanged(identity, delegateType, delegate, 0, changed[identity]);
        changed[identity] = block.number;
    }

    // ============ Attribute Management ============

    /**
     * @notice Set an attribute for a DID
     * @param identity The DID to modify
     * @param name Attribute name (e.g., keccak256("did/pub/Ed25519/veriKey"))
     * @param value Attribute value (encoded public key, URL, etc.)
     * @param validity Validity period in seconds
     */
    function setAttribute(
        address identity,
        bytes32 name,
        bytes memory value,
        uint validity
    ) public onlyOwner(identity, msg.sender) {
        uint validTo = block.timestamp + validity;
        emit DIDAttributeChanged(identity, name, value, validTo, changed[identity]);
        changed[identity] = block.number;
    }

    /**
     * @notice Set attribute via signed message
     */
    function setAttributeSigned(
        address identity,
        uint8 sigV,
        bytes32 sigR,
        bytes32 sigS,
        bytes32 name,
        bytes memory value,
        uint validity
    ) public {
        bytes32 hash = keccak256(
            abi.encodePacked(
                bytes1(0x19),
                bytes1(0),
                this,
                nonce[identityOwner(identity)],
                identity,
                "setAttribute",
                name,
                value,
                validity
            )
        );

        address signer = ecrecover(hash, sigV, sigR, sigS);
        require(signer == identityOwner(identity), "DIDRegistry: invalid signature");

        nonce[signer]++;
        uint validTo = block.timestamp + validity;
        uint previousChange = changed[identity];
        changed[identity] = block.number;
        emit DIDAttributeChanged(identity, name, value, validTo, previousChange);
    }

    /**
     * @notice Revoke an attribute
     * @param identity The DID to modify
     * @param name Attribute name
     * @param value Attribute value (must match to revoke)
     */
    function revokeAttribute(
        address identity,
        bytes32 name,
        bytes memory value
    ) public onlyOwner(identity, msg.sender) {
        emit DIDAttributeChanged(identity, name, value, 0, changed[identity]);
        changed[identity] = block.number;
    }

    /**
     * @notice Revoke attribute via signed message
     */
    function revokeAttributeSigned(
        address identity,
        uint8 sigV,
        bytes32 sigR,
        bytes32 sigS,
        bytes32 name,
        bytes memory value
    ) public {
        bytes32 hash = keccak256(
            abi.encodePacked(
                bytes1(0x19),
                bytes1(0),
                this,
                nonce[identityOwner(identity)],
                identity,
                "revokeAttribute",
                name,
                value
            )
        );

        address signer = ecrecover(hash, sigV, sigR, sigS);
        require(signer == identityOwner(identity), "DIDRegistry: invalid signature");

        nonce[signer]++;
        uint previousChange = changed[identity];
        changed[identity] = block.number;
        emit DIDAttributeChanged(identity, name, value, 0, previousChange);
    }
}
