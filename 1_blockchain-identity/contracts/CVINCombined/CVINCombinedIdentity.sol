// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title CVINCombinedIdentity — the thesis's proposed hybrid (ERC-1056 + ERC-735)
 * @notice Single-contract composition of an event-based lightweight identity
 *         registry with on-chain claim storage for the safety-critical subset
 *         of vehicle credentials.
 *
 * @dev DESIGN RATIONALE (thesis hypothesis):
 *
 *      ERC-1056 side — EVENTS ARE CHEAP. The vast majority of vehicle
 *      identity operations (attribute updates, service endpoints, rotating
 *      session keys/delegates, ownership transfer) do not need on-chain
 *      readability by other contracts; they only need a tamper-evident,
 *      indexable history from which an off-chain resolver builds the DID
 *      document. Emitting events + a single `changed` block pointer per
 *      identity costs a fraction of SSTORE-based registries, and every
 *      address is an identity by default (zero-cost identity creation).
 *
 *      ERC-735 side — SAFETY-CRITICAL CLAIMS MUST BE O(1) ON-CHAIN
 *      VERIFIABLE. A vehicle interacting with road infrastructure or another
 *      vehicle cannot walk an event log inside the EVM; type-approval,
 *      manufacturer attestation and periodic-inspection credentials are
 *      therefore stored on-chain as ERC-735-style claims whose issuer
 *      signature is verified with ecrecover AT ADD TIME, so any contract can
 *      later check `getClaim` in O(1) without re-verifying signatures.
 *
 *      Combining both in ONE contract gives a shared ownership model (the
 *      ERC-1056 `identityOwner` gates both attribute events and claim
 *      management) and lets the gas benchmark measure the hybrid's combined
 *      cost in a single deployment.
 *
 *      Signature scheme for claims: the issuer signs the RAW keccak256 digest
 *      keccak256(abi.encodePacked(address(this), identity, topic, data))
 *      (no EIP-191 envelope), binding the claim to this registry instance and
 *      the subject identity. This mirrors the bare-digest signing pattern of
 *      the ERC-1056 reference registry's signed meta-transactions.
 */
contract CVINCombinedIdentity {
    // ============ Claim topics (safety-critical subset) ============

    uint256 public constant CLAIM_TOPIC_VIN = 1; // VIN attestation
    uint256 public constant CLAIM_TOPIC_MANUFACTURER = 2; // manufacturer / type approval
    uint256 public constant CLAIM_TOPIC_INSPECTION = 3; // periodic technical inspection

    /// @dev ECDSA over raw keccak256 digest (scheme id per ERC-735 convention).
    uint256 public constant SCHEME_ECDSA = 1;

    // ============ ERC-1056-style identity state ============

    /// @dev Explicit owner override; address(0) means self-owned (default).
    mapping(address => address) private _owners;

    /// @dev delegates[identity][delegateType][delegate] = validity expiry timestamp.
    mapping(address => mapping(bytes32 => mapping(address => uint256))) public delegates;

    /// @dev Block number of the identity's last change (event-log linked list).
    mapping(address => uint256) public changed;

    // ============ ERC-735-style claim state ============

    struct Claim {
        uint256 topic;
        uint256 scheme;
        address issuer;
        bytes signature;
        bytes data;
        string uri;
    }

    /// @dev claims[identity][claimId] where claimId = keccak256(issuer, topic).
    mapping(address => mapping(bytes32 => Claim)) private _claims;

    /// @dev claimIdsByTopic[identity][topic] -> list of claim ids.
    mapping(address => mapping(uint256 => bytes32[])) private _claimIdsByTopic;

    // ============ Events ============

    // ERC-1056-style
    event DIDOwnerChanged(address indexed identity, address owner, uint256 previousChange);
    event DIDDelegateChanged(
        address indexed identity,
        bytes32 delegateType,
        address delegate,
        uint256 validTo,
        uint256 previousChange
    );
    event DIDAttributeChanged(
        address indexed identity,
        bytes32 name,
        bytes value,
        uint256 validTo,
        uint256 previousChange
    );

    // ERC-735-style
    event ClaimAdded(
        bytes32 indexed claimId,
        address indexed identity,
        uint256 indexed topic,
        uint256 scheme,
        address issuer,
        bytes signature,
        bytes data,
        string uri
    );
    event ClaimRemoved(
        bytes32 indexed claimId,
        address indexed identity,
        uint256 indexed topic,
        address issuer
    );

    // ============ Modifiers ============

    modifier onlyIdentityOwner(address identity) {
        require(msg.sender == identityOwner(identity), "CVINCombined: unauthorized");
        _;
    }

    // ============ ERC-1056-style: ownership ============

    /// @notice Every address is an identity; it owns itself until changed.
    function identityOwner(address identity) public view returns (address) {
        address owner = _owners[identity];
        if (owner != address(0)) {
            return owner;
        }
        return identity;
    }

    /// @notice Transfer control of an identity (key rotation / vehicle sale).
    function changeOwner(
        address identity,
        address newOwner
    ) external onlyIdentityOwner(identity) {
        _owners[identity] = newOwner;
        emit DIDOwnerChanged(identity, newOwner, changed[identity]);
        changed[identity] = block.number;
    }

    // ============ ERC-1056-style: delegates ============

    /// @notice Add a delegate key (e.g. vehicle session/telematics key) with a TTL.
    function addDelegate(
        address identity,
        bytes32 delegateType,
        address delegate,
        uint256 validity
    ) external onlyIdentityOwner(identity) {
        uint256 validTo = block.timestamp + validity;
        delegates[identity][delegateType][delegate] = validTo;
        emit DIDDelegateChanged(identity, delegateType, delegate, validTo, changed[identity]);
        changed[identity] = block.number;
    }

    /// @notice Revoke a delegate immediately.
    function revokeDelegate(
        address identity,
        bytes32 delegateType,
        address delegate
    ) external onlyIdentityOwner(identity) {
        delegates[identity][delegateType][delegate] = block.timestamp;
        emit DIDDelegateChanged(identity, delegateType, delegate, block.timestamp, changed[identity]);
        changed[identity] = block.number;
    }

    /// @notice Check whether a delegate is currently valid.
    function validDelegate(
        address identity,
        bytes32 delegateType,
        address delegate
    ) external view returns (bool) {
        return delegates[identity][delegateType][delegate] > block.timestamp;
    }

    // ============ ERC-1056-style: attributes (event-only, cheap) ============

    /**
     * @notice Publish an identity attribute purely as an event — no storage
     *         write except the `changed` pointer. Off-chain resolvers rebuild
     *         the DID document by walking the event history.
     */
    function setAttribute(
        address identity,
        bytes32 name,
        bytes calldata value,
        uint256 validity
    ) external onlyIdentityOwner(identity) {
        emit DIDAttributeChanged(identity, name, value, block.timestamp + validity, changed[identity]);
        changed[identity] = block.number;
    }

    /// @notice Revoke a previously published attribute (validTo = 0).
    function revokeAttribute(
        address identity,
        bytes32 name,
        bytes calldata value
    ) external onlyIdentityOwner(identity) {
        emit DIDAttributeChanged(identity, name, value, 0, changed[identity]);
        changed[identity] = block.number;
    }

    // ============ ERC-735-style: on-chain claims ============

    /**
     * @notice Add a safety-critical claim about `identity`, issued (signed)
     *         by `issuer`. The issuer signature over the raw digest
     *         keccak256(abi.encodePacked(address(this), identity, topic, data))
     *         is verified with ecrecover before the claim is stored, so later
     *         reads are O(1) and need no re-verification.
     * @return claimId keccak256(abi.encodePacked(issuer, topic))
     */
    function addClaim(
        address identity,
        uint256 topic,
        uint256 scheme,
        address issuer,
        bytes calldata signature,
        bytes calldata data,
        string calldata uri
    ) external onlyIdentityOwner(identity) returns (bytes32 claimId) {
        require(scheme == SCHEME_ECDSA, "CVINCombined: unsupported scheme");
        require(issuer != address(0), "CVINCombined: zero issuer");
        require(
            _recoverRawDigest(identity, topic, data, signature) == issuer,
            "CVINCombined: invalid claim signature"
        );

        claimId = keccak256(abi.encodePacked(issuer, topic));

        // Only index the topic list on first insertion (re-adding updates in place).
        if (_claims[identity][claimId].issuer == address(0)) {
            _claimIdsByTopic[identity][topic].push(claimId);
        }

        _claims[identity][claimId] = Claim({
            topic: topic,
            scheme: scheme,
            issuer: issuer,
            signature: signature,
            data: data,
            uri: uri
        });

        emit ClaimAdded(claimId, identity, topic, scheme, issuer, signature, data, uri);
        changed[identity] = block.number;
    }

    /// @notice Remove a claim (identity owner or the claim's issuer).
    function removeClaim(address identity, bytes32 claimId) external {
        Claim memory claim = _claims[identity][claimId];
        require(claim.issuer != address(0), "CVINCombined: claim not found");
        require(
            msg.sender == identityOwner(identity) || msg.sender == claim.issuer,
            "CVINCombined: unauthorized"
        );

        // Remove from topic index (swap-and-pop).
        bytes32[] storage ids = _claimIdsByTopic[identity][claim.topic];
        for (uint256 i = 0; i < ids.length; i++) {
            if (ids[i] == claimId) {
                ids[i] = ids[ids.length - 1];
                ids.pop();
                break;
            }
        }

        delete _claims[identity][claimId];
        emit ClaimRemoved(claimId, identity, claim.topic, claim.issuer);
        changed[identity] = block.number;
    }

    /// @notice O(1) claim lookup for on-chain verifiers.
    function getClaim(
        address identity,
        bytes32 claimId
    )
        external
        view
        returns (
            uint256 topic,
            uint256 scheme,
            address issuer,
            bytes memory signature,
            bytes memory data,
            string memory uri
        )
    {
        Claim memory claim = _claims[identity][claimId];
        return (claim.topic, claim.scheme, claim.issuer, claim.signature, claim.data, claim.uri);
    }

    /// @notice All claim ids of a given topic for an identity.
    function getClaimIdsByTopic(
        address identity,
        uint256 topic
    ) external view returns (bytes32[] memory) {
        return _claimIdsByTopic[identity][topic];
    }

    /// @notice Convenience predicate: does `identity` hold a claim on `topic` from `issuer`?
    function hasValidClaim(
        address identity,
        uint256 topic,
        address issuer
    ) external view returns (bool) {
        bytes32 claimId = keccak256(abi.encodePacked(issuer, topic));
        Claim storage claim = _claims[identity][claimId];
        return claim.issuer == issuer && claim.topic == topic;
    }

    // ============ Internal ============

    /// @dev ecrecover over the raw (non-EIP-191) claim digest.
    function _recoverRawDigest(
        address identity,
        uint256 topic,
        bytes calldata data,
        bytes calldata signature
    ) internal view returns (address) {
        if (signature.length != 65) {
            return address(0);
        }
        bytes32 digest = keccak256(abi.encodePacked(address(this), identity, topic, data));
        bytes32 r = bytes32(signature[0:32]);
        bytes32 s = bytes32(signature[32:64]);
        uint8 v = uint8(signature[64]);
        if (v != 27 && v != 28) {
            return address(0);
        }
        return ecrecover(digest, v, r, s);
    }
}
