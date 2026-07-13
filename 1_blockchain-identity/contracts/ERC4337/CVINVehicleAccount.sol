// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title CVINVehicleAccount (ERC-4337 Account Abstraction — research implementation)
 * @notice A smart-contract account representing a connected-vehicle identity.
 *         Deploying this account IS the act of creating the vehicle identity:
 *         the contract address is the vehicle's stable on-chain identifier,
 *         while the signing key (owner) can be rotated or recovered without
 *         the identity/address ever changing — the headline identity property
 *         of ERC-4337 evaluated in this thesis.
 *
 * @dev SELF-CONTAINED MINIMAL ERC-4337 SETUP — SIMPLIFICATIONS vs the
 *      canonical v0.7 stack (@account-abstraction/contracts), documented for
 *      the thesis security/gas analysis:
 *
 *      1. PackedUserOperation matches the v0.7 struct shape (sender, nonce,
 *         initCode, callData, accountGasLimits, preVerificationGas, gasFees,
 *         paymasterAndData, signature) but the gas-limit fields are carried
 *         only so the userOpHash matches the v0.7 hashing scheme — they are
 *         NOT enforced by the minimal entry point (no gas accounting).
 *      2. IAccount keeps the canonical validateUserOp(userOp, userOpHash,
 *         missingAccountFunds) signature, but the minimal entry point always
 *         passes missingAccountFunds = 0 (no deposit/prefund system). The
 *         prefund-payment branch is still implemented for shape-fidelity.
 *      3. Signature validation follows SimpleAccount v0.7: the owner signs
 *         the EIP-191 ("\x19Ethereum Signed Message:\n32") envelope of the
 *         userOpHash; validation returns 0 on success and 1
 *         (SIG_VALIDATION_FAILED) on failure instead of reverting, exactly
 *         like the canonical account. Time-range packing of validationData
 *         (validAfter/validUntil) is omitted.
 *      4. No initCode-based counterfactual deployment via an AccountFactory;
 *         the account is deployed directly (identity creation is measured as
 *         the constructor cost).
 *      5. No paymaster, no signature aggregation, no EIP-1271.
 *
 *      Identity features on top of the raw account:
 *      - setAttribute(bytes32,bytes): ERC-725Y-flavoured attribute store for
 *        vehicle metadata (VIN, make/model, firmware hash, ...), gated to
 *        owner-or-entryPoint, with an event for off-chain indexing.
 *      - transferOwnership: signing-key rotation (identity address unchanged).
 *      - setGuardian / recoverOwner: social-recovery mechanism — a designated
 *        guardian (e.g. manufacturer or fleet operator) can install a new
 *        signing key if the vehicle's key is lost or compromised. This is the
 *        recovery capability unique to contract accounts among the standards
 *        compared in the thesis.
 */

/// @dev v0.7-shaped packed user operation (see simplification note 1 above).
struct PackedUserOperation {
    address sender;
    uint256 nonce;
    bytes initCode;
    bytes callData;
    bytes32 accountGasLimits; // packed verificationGasLimit | callGasLimit
    uint256 preVerificationGas;
    bytes32 gasFees; // packed maxPriorityFeePerGas | maxFeePerGas
    bytes paymasterAndData;
    bytes signature;
}

/// @dev Minimal ERC-4337 account interface (v0.7 shape).
interface IAccount {
    function validateUserOp(
        PackedUserOperation calldata userOp,
        bytes32 userOpHash,
        uint256 missingAccountFunds
    ) external returns (uint256 validationData);
}

contract CVINVehicleAccount is IAccount {
    // ============ Constants ============

    /// @dev Canonical ERC-4337 return value for a failed signature check.
    uint256 internal constant SIG_VALIDATION_FAILED = 1;
    uint256 internal constant SIG_VALIDATION_SUCCESS = 0;

    // ============ State ============

    /// @notice Current signing key controlling this vehicle identity.
    address public owner;

    /// @notice Trusted entry point allowed to relay validated user operations.
    address public immutable entryPoint;

    /// @notice Social-recovery guardian (e.g. manufacturer / fleet operator).
    address public guardian;

    /// @dev Vehicle metadata store (ERC-725Y-flavoured key/value).
    mapping(bytes32 => bytes) private _attributes;

    // ============ Events ============

    event VehicleAccountCreated(address indexed account, address indexed owner, address indexed entryPoint);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event GuardianChanged(address indexed previousGuardian, address indexed newGuardian);
    event OwnerRecovered(address indexed guardian, address indexed previousOwner, address indexed newOwner);
    event AttributeChanged(bytes32 indexed key, bytes value);
    event Executed(address indexed target, uint256 value, bytes data);

    // ============ Modifiers ============

    /**
     * @dev Gates state-changing identity functions to: the owner key (direct
     *      call), the entry point (validated 4337 path), or the account
     *      itself (self-call via execute(), the canonical way a UserOperation
     *      reaches an account's admin functions).
     */
    modifier onlyOwnerOrEntryPoint() {
        require(
            msg.sender == owner || msg.sender == entryPoint || msg.sender == address(this),
            "CVINVehicleAccount: not owner or entryPoint"
        );
        _;
    }

    // ============ Constructor (identity creation) ============

    constructor(address _entryPoint, address _owner) {
        require(_entryPoint != address(0), "CVINVehicleAccount: zero entryPoint");
        require(_owner != address(0), "CVINVehicleAccount: zero owner");
        entryPoint = _entryPoint;
        owner = _owner;
        emit VehicleAccountCreated(address(this), _owner, _entryPoint);
    }

    receive() external payable {}

    // ============ ERC-4337 validation ============

    /**
     * @notice Validate a user operation's signature (called by the entry point).
     * @dev The owner signs the EIP-191 envelope of userOpHash. Returns 0 on
     *      success, 1 on signature failure (does not revert), per ERC-4337.
     */
    function validateUserOp(
        PackedUserOperation calldata userOp,
        bytes32 userOpHash,
        uint256 missingAccountFunds
    ) external override returns (uint256 validationData) {
        require(msg.sender == entryPoint, "CVINVehicleAccount: not entryPoint");

        validationData = _validateSignature(userOp.signature, userOpHash);

        // Shape-fidelity prefund branch (minimal entry point always passes 0).
        if (missingAccountFunds > 0) {
            (bool ok, ) = payable(msg.sender).call{value: missingAccountFunds}("");
            (ok); // ignore failure, per canonical account behaviour
        }
    }

    function _validateSignature(
        bytes calldata signature,
        bytes32 userOpHash
    ) internal view returns (uint256) {
        if (signature.length != 65) {
            return SIG_VALIDATION_FAILED;
        }
        // EIP-191 personal-sign envelope over the userOpHash (SimpleAccount pattern).
        bytes32 digest = keccak256(
            abi.encodePacked("\x19Ethereum Signed Message:\n32", userOpHash)
        );
        (bytes32 r, bytes32 s, uint8 v) = _splitSignature(signature);
        address recovered = ecrecover(digest, v, r, s);
        if (recovered == address(0) || recovered != owner) {
            return SIG_VALIDATION_FAILED;
        }
        return SIG_VALIDATION_SUCCESS;
    }

    function _splitSignature(
        bytes calldata signature
    ) internal pure returns (bytes32 r, bytes32 s, uint8 v) {
        r = bytes32(signature[0:32]);
        s = bytes32(signature[32:64]);
        v = uint8(signature[64]);
    }

    // ============ Execution ============

    /**
     * @notice Execute an arbitrary call from this vehicle identity.
     * @dev Callable by the owner key directly, or by the entry point after
     *      validateUserOp succeeded (the 4337 path).
     */
    function execute(
        address target,
        uint256 value,
        bytes calldata data
    ) external onlyOwnerOrEntryPoint returns (bytes memory result) {
        (bool success, bytes memory ret) = target.call{value: value}(data);
        if (!success) {
            // bubble up revert reason
            assembly {
                revert(add(ret, 32), mload(ret))
            }
        }
        emit Executed(target, value, data);
        return ret;
    }

    // ============ Key rotation ============

    /**
     * @notice Rotate the signing key. The vehicle identity (this address)
     *         is unchanged — only the controlling key moves.
     */
    function transferOwnership(address newOwner) external onlyOwnerOrEntryPoint {
        require(newOwner != address(0), "CVINVehicleAccount: zero owner");
        address previous = owner;
        owner = newOwner;
        emit OwnershipTransferred(previous, newOwner);
    }

    // ============ Social recovery ============

    /// @notice Designate (or clear, with address(0)) the recovery guardian.
    function setGuardian(address newGuardian) external onlyOwnerOrEntryPoint {
        address previous = guardian;
        guardian = newGuardian;
        emit GuardianChanged(previous, newGuardian);
    }

    /**
     * @notice Guardian-driven recovery: installs a new signing key when the
     *         vehicle's key is lost or compromised.
     */
    function recoverOwner(address newOwner) external {
        require(msg.sender == guardian, "CVINVehicleAccount: not guardian");
        require(newOwner != address(0), "CVINVehicleAccount: zero owner");
        address previous = owner;
        owner = newOwner;
        emit OwnerRecovered(msg.sender, previous, newOwner);
    }

    // ============ Vehicle attribute store ============

    /// @notice Set a vehicle metadata attribute (VIN, make, firmware hash, ...).
    function setAttribute(bytes32 key, bytes calldata value) external onlyOwnerOrEntryPoint {
        _attributes[key] = value;
        emit AttributeChanged(key, value);
    }

    /// @notice Read a vehicle metadata attribute.
    function getAttribute(bytes32 key) external view returns (bytes memory) {
        return _attributes[key];
    }
}
