#!/usr/bin/env python3
"""
MOBI VID Registry — web3.py v7 binding for MOBIVIDRegistryV2
=============================================================

Thin, typed Python client for the MOBIVIDRegistryV2 smart contract
(MOBI VID I birth certificates + MOBI VID II lifecycle events).

ABI and bytecode are loaded from the Hardhat build artifacts in
`1_blockchain-identity/artifacts/contracts/MOBI/` — run
`npx hardhat compile` in `1_blockchain-identity/` first.

The EventType and IssuerRole enums below mirror the Solidity enums in
MOBIVIDRegistryV2.sol EXACTLY (same names, same ordinal values). The
contract is the source of truth; earlier documentation used divergent
role names (GOVERNMENT_INSPECTION, FLEET_MANAGER) which do not exist
on-chain and are not used here.

Author: Nikhil Prakash
Thesis: MASc, UBC ECE
"""

import json
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.logs import DISCARD
from web3.middleware import ExtraDataToPOAMiddleware

# ---------------------------------------------------------------------------
# Contract enums (MUST stay in sync with MOBIVIDRegistryV2.sol)
# ---------------------------------------------------------------------------


class EventType(IntEnum):
    """Solidity `enum EventType` in MOBIVIDRegistryV2.sol (11 types)."""
    MAINTENANCE = 0      # Regular service (oil change, tire rotation, ...)
    REPAIR = 1           # Breakdown repair
    ACCIDENT = 2         # Collision or damage
    RECALL = 3           # Manufacturer recall
    INSPECTION = 4       # Safety or emissions inspection
    MODIFICATION = 5     # Aftermarket modifications
    THEFT_REPORT = 6     # Vehicle reported stolen
    RECOVERY = 7         # Stolen vehicle recovered
    INSURANCE_CLAIM = 8  # Insurance claim filed
    REGISTRATION = 9     # DMV registration/renewal
    DECOMMISSION = 10    # Vehicle scrapped/totaled


class IssuerRole(IntEnum):
    """Solidity `enum IssuerRole` in MOBIVIDRegistryV2.sol (NONE + 8 roles)."""
    NONE = 0
    MANUFACTURER = 1
    DEALER = 2
    SERVICE_CENTER = 3
    INSURANCE_COMPANY = 4
    GOVERNMENT_DMV = 5
    POLICE = 6
    INSPECTION_STATION = 7
    OWNER = 8


# Default artifact location (relative to this file):
#   <repo>/1_blockchain-identity/artifacts/contracts/MOBI/...
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT = (
    _REPO_ROOT / "1_blockchain-identity" / "artifacts" / "contracts"
    / "MOBI" / "MOBIVIDRegistryV2.sol" / "MOBIVIDRegistryV2.json"
)


def load_artifact(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the Hardhat artifact (ABI + bytecode) for MOBIVIDRegistryV2."""
    artifact_path = Path(path) if path else DEFAULT_ARTIFACT
    if not artifact_path.exists():
        raise FileNotFoundError(
            f"Hardhat artifact not found: {artifact_path}\n"
            "Run `npx hardhat compile` in 1_blockchain-identity/ first."
        )
    with open(artifact_path) as f:
        return json.load(f)


class MOBIVIDRegistryClient:
    """
    web3.py v7 client for MOBIVIDRegistryV2.

    All state-changing calls take an `eth_account` LocalAccount and sign
    transactions locally (no unlocked-node accounts assumed).
    """

    def __init__(self,
                 rpc_url: str = "http://127.0.0.1:8545",
                 contract_address: Optional[str] = None,
                 artifact_path: Optional[Path] = None,
                 poa: bool = False):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
        if poa:
            # Geth/Clique dev chains put >32 bytes in extraData
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot reach Ethereum node at {rpc_url}")

        artifact = load_artifact(artifact_path)
        self.abi = artifact["abi"]
        self.bytecode = artifact["bytecode"]
        self.contract = None
        if contract_address:
            self.connect(contract_address)

    # ------------------------------------------------------------------
    # Deployment / connection
    # ------------------------------------------------------------------

    def deploy(self, deployer: LocalAccount) -> str:
        """Deploy MOBIVIDRegistryV2 and bind this client to it."""
        factory = self.w3.eth.contract(abi=self.abi, bytecode=self.bytecode)
        tx = factory.constructor().build_transaction(self._tx_params(deployer))
        receipt = self._sign_and_send(tx, deployer)
        self.connect(receipt["contractAddress"])
        return receipt["contractAddress"]

    def connect(self, contract_address: str) -> None:
        """Bind this client to an already-deployed registry."""
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address), abi=self.abi
        )

    @property
    def address(self) -> str:
        self._require_contract()
        return self.contract.address

    def chain_id(self) -> int:
        return self.w3.eth.chain_id

    def vehicle_did(self, vehicle_address: str) -> str:
        """did:ethr DID for a vehicle identity address on this chain."""
        return f"did:ethr:{hex(self.chain_id())}:{Web3.to_checksum_address(vehicle_address)}"

    # ------------------------------------------------------------------
    # Issuer / manufacturer management
    # ------------------------------------------------------------------

    def authorize_manufacturer(self, authority: LocalAccount,
                               manufacturer: str) -> Dict[str, Any]:
        return self._transact(
            self.contract.functions.authorizeManufacturer(
                Web3.to_checksum_address(manufacturer)), authority)

    def authorize_issuer(self, authority: LocalAccount, issuer: str,
                         role: IssuerRole) -> Dict[str, Any]:
        return self._transact(
            self.contract.functions.authorizeIssuer(
                Web3.to_checksum_address(issuer), int(role)), authority)

    def revoke_issuer(self, authority: LocalAccount,
                      issuer: str) -> Dict[str, Any]:
        return self._transact(
            self.contract.functions.revokeIssuerAuthorization(
                Web3.to_checksum_address(issuer)), authority)

    def issuer_role(self, issuer: str) -> IssuerRole:
        return IssuerRole(self.contract.functions.authorizedIssuers(
            Web3.to_checksum_address(issuer)).call())

    def is_authorized_issuer(self, issuer: str, event_type: EventType) -> bool:
        return self.contract.functions.isAuthorizedIssuer(
            Web3.to_checksum_address(issuer), int(event_type)).call()

    # ------------------------------------------------------------------
    # MOBI VID I — birth registration
    # ------------------------------------------------------------------

    def register_vehicle_birth(self, manufacturer: LocalAccount,
                               vehicle_identity: str, vin_hash: bytes,
                               encrypted_vin: str, birth_cert_hash: bytes,
                               first_owner: str,
                               birth_attributes: bytes = b"") -> Dict[str, Any]:
        """Register a MOBI VID I birth certificate on-chain."""
        return self._transact(
            self.contract.functions.registerVehicleBirth(
                Web3.to_checksum_address(vehicle_identity),
                vin_hash, encrypted_vin, birth_cert_hash,
                Web3.to_checksum_address(first_owner), birth_attributes),
            manufacturer)

    def get_vehicle_birth(self, vehicle_identity: str) -> Dict[str, Any]:
        b = self.contract.functions.getVehicleBirth(
            Web3.to_checksum_address(vehicle_identity)).call()
        return {
            "vinHash": bytes(b[0]), "encryptedVIN": b[1],
            "birthCertHash": bytes(b[2]), "timestamp": b[3],
            "manufacturer": b[4], "firstOwner": b[5],
            "blockNumber": b[6], "exists": b[7],
        }

    def lookup_by_vin_hash(self, vin_hash: bytes) -> str:
        return self.contract.functions.lookupByVINHash(vin_hash).call()

    def vehicle_exists(self, vehicle_identity: str) -> bool:
        return self.contract.functions.vehicleExists(
            Web3.to_checksum_address(vehicle_identity)).call()

    def identity_owner(self, vehicle_identity: str) -> str:
        return self.contract.functions.identityOwner(
            Web3.to_checksum_address(vehicle_identity)).call()

    # ------------------------------------------------------------------
    # MOBI VID II — lifecycle events
    # ------------------------------------------------------------------

    def record_lifecycle_event(self, issuer: LocalAccount,
                               vehicle_identity: str, event_type: EventType,
                               odometer: int, data_hash: bytes,
                               credential_hash: bytes,
                               jurisdiction: str
                               ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Record a lifecycle event. Returns (event_id, receipt).
        The event_id is recovered from the LifecycleEventRecorded log.
        """
        receipt = self._transact(
            self.contract.functions.recordLifecycleEvent(
                Web3.to_checksum_address(vehicle_identity), int(event_type),
                odometer, data_hash, credential_hash, jurisdiction),
            issuer)
        logs = self.contract.events.LifecycleEventRecorded().process_receipt(
            receipt, errors=DISCARD)
        if not logs:
            raise RuntimeError("LifecycleEventRecorded log not found in receipt")
        return bytes(logs[0]["args"]["eventId"]), receipt

    def attest_event(self, attester: LocalAccount, event_id: bytes,
                     vehicle_identity: str,
                     signature: bytes) -> Dict[str, Any]:
        """Add a multi-party attestation to an existing event."""
        return self._transact(
            self.contract.functions.attestEvent(
                event_id, Web3.to_checksum_address(vehicle_identity),
                signature), attester)

    def get_event(self, vehicle_identity: str,
                  event_id: bytes) -> Dict[str, Any]:
        e = self.contract.functions.getEvent(
            Web3.to_checksum_address(vehicle_identity), event_id).call()
        return {
            "eventId": bytes(e[0]), "eventType": EventType(e[1]),
            "issuer": e[2], "timestamp": e[3], "odometer": e[4],
            "dataHash": bytes(e[5]), "credentialHash": bytes(e[6]),
            "verified": e[7], "jurisdiction": e[8], "blockNumber": e[9],
        }

    def get_vehicle_events(self, vehicle_identity: str) -> List[bytes]:
        ids = self.contract.functions.getVehicleEvents(
            Web3.to_checksum_address(vehicle_identity)).call()
        return [bytes(i) for i in ids]

    def get_events_by_type(self, vehicle_identity: str,
                           event_type: EventType) -> List[bytes]:
        ids = self.contract.functions.getEventsByType(
            Web3.to_checksum_address(vehicle_identity), int(event_type)).call()
        return [bytes(i) for i in ids]

    def get_event_attestations(self, event_id: bytes) -> List[Dict[str, Any]]:
        raw = self.contract.functions.getEventAttestations(event_id).call()
        return [{"attester": a[0], "role": IssuerRole(a[1]),
                 "signature": bytes(a[2]), "timestamp": a[3]} for a in raw]

    def get_complete_history(self, vehicle_identity: str) -> Dict[str, Any]:
        birth, event_count, last_event = \
            self.contract.functions.getCompleteHistory(
                Web3.to_checksum_address(vehicle_identity)).call()
        return {
            "birth": {
                "vinHash": bytes(birth[0]), "encryptedVIN": birth[1],
                "birthCertHash": bytes(birth[2]), "timestamp": birth[3],
                "manufacturer": birth[4], "firstOwner": birth[5],
                "blockNumber": birth[6], "exists": birth[7],
            },
            "eventCount": event_count,
            "lastEvent": bytes(last_event),
        }

    def get_odometer_history(self, vehicle_identity: str
                             ) -> List[Dict[str, int]]:
        readings, timestamps = self.contract.functions.getOdometerHistory(
            Web3.to_checksum_address(vehicle_identity)).call()
        return [{"odometer": r, "timestamp": t}
                for r, t in zip(readings, timestamps)]

    # ------------------------------------------------------------------
    # Event-log queries (indexed, no contract storage reads)
    # ------------------------------------------------------------------

    def query_lifecycle_logs(self, vehicle_identity: Optional[str] = None,
                             from_block: int = 0,
                             to_block: str = "latest") -> List[Dict[str, Any]]:
        """Fetch LifecycleEventRecorded logs, optionally per-vehicle."""
        argument_filters = {}
        if vehicle_identity:
            argument_filters["vehicleIdentity"] = \
                Web3.to_checksum_address(vehicle_identity)
        logs = self.contract.events.LifecycleEventRecorded.get_logs(
            from_block=from_block, to_block=to_block,
            argument_filters=argument_filters or None)
        return [
            {
                "vehicleIdentity": lg["args"]["vehicleIdentity"],
                "eventId": bytes(lg["args"]["eventId"]),
                "eventType": EventType(lg["args"]["eventType"]),
                "issuer": lg["args"]["issuer"],
                "odometer": lg["args"]["odometer"],
                "timestamp": lg["args"]["timestamp"],
                "blockNumber": lg["blockNumber"],
                "txHash": lg["transactionHash"].hex(),
            }
            for lg in logs
        ]

    def query_birth_logs(self, from_block: int = 0,
                         to_block: str = "latest") -> List[Dict[str, Any]]:
        """Fetch VehicleBirthRegistered logs."""
        logs = self.contract.events.VehicleBirthRegistered.get_logs(
            from_block=from_block, to_block=to_block)
        return [
            {
                "vehicleIdentity": lg["args"]["vehicleIdentity"],
                "vinHash": bytes(lg["args"]["vinHash"]),
                "manufacturer": lg["args"]["manufacturer"],
                "firstOwner": lg["args"]["firstOwner"],
                "birthCertHash": bytes(lg["args"]["birthCertHash"]),
                "timestamp": lg["args"]["timestamp"],
                "blockNumber": lg["blockNumber"],
            }
            for lg in logs
        ]

    # ------------------------------------------------------------------
    # Transaction plumbing (web3 v7: signed.raw_transaction)
    # ------------------------------------------------------------------

    def _require_contract(self) -> None:
        if self.contract is None:
            raise RuntimeError(
                "Client is not bound to a contract — call deploy() or connect()")

    def _tx_params(self, account: LocalAccount) -> Dict[str, Any]:
        return {
            "from": account.address,
            "nonce": self.w3.eth.get_transaction_count(account.address),
            "chainId": self.chain_id(),
            "gasPrice": self.w3.eth.gas_price,
        }

    def _transact(self, fn, account: LocalAccount) -> Dict[str, Any]:
        self._require_contract()
        tx = fn.build_transaction(self._tx_params(account))
        return self._sign_and_send(tx, account)

    def _sign_and_send(self, tx: Dict[str, Any],
                       account: LocalAccount) -> Dict[str, Any]:
        if "gas" not in tx:
            tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.2)
        signed = self.w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if receipt["status"] != 1:
            raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
        return receipt


if __name__ == "__main__":
    from eth_account import Account

    print("MOBI VID Registry client — smoke test against a local node")
    client = MOBIVIDRegistryClient()
    deployer = Account.from_key(
        # Hardhat default account #0 (test-only key)
        "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    )
    addr = client.deploy(deployer)
    print(f"Deployed MOBIVIDRegistryV2 at {addr} (chain {client.chain_id()})")
    print(f"Deployer issuer role: {client.issuer_role(deployer.address).name}")
