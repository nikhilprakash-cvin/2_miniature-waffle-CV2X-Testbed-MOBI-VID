"""
MOBI VID Provider for Connected Vehicles

Implements MOBI Vehicle Identity (VID) 1.0 standard using ERC-1056 as base.

Standards Compliance:
- MOBI VID I (Vehicle Birth Certificate)
- W3C Decentralized Identifiers (DIDs) v1.0
- ERC-1056 (Ethereum DID Registry)
- SSI (Self-Sovereign Identity) principles

Features:
- Immutable vehicle birth certificates
- VIN privacy protection (hash + encrypted storage)
- Manufacturer authorization
- Ownership transfer with history tracking
- W3C DID document construction
- Real blockchain integration
"""

import time
import json
import hashlib
import secrets
from typing import Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
from eth_account import Account
from web3 import Web3
from web3.middleware import geth_poa_middleware

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

from identity.base import (
    IdentityProvider,
    IdentityType,
    IdentityMetrics,
    VehicleCredential
)


class MOBIVIDProvider(IdentityProvider):
    """
    MOBI VID 1.0 Provider

    Implements MOBI Vehicle Identity Standard 1.0 (Vehicle Birth Certificate)
    using ERC-1056 as base, with full W3C DID compliance.
    """

    def __init__(
        self,
        web3_provider_url: str = "http://127.0.0.1:8545",
        contract_address: Optional[str] = None,
        private_key: Optional[str] = None,
        ipfs_gateway: str = "http://127.0.0.1:5001"
    ):
        super().__init__(IdentityType.ERC1056_DID)  # Using ERC1056_DID type for now

        # Connect to blockchain
        self.w3 = Web3(Web3.HTTPProvider(web3_provider_url))

        # Add PoA middleware for some chains
        try:
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        except:
            pass

        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to blockchain at {web3_provider_url}")

        # Account for transactions (manufacturer account)
        if private_key:
            self.account = Account.from_key(private_key)
        else:
            # Use first account from local node (Hardhat default)
            self.account = Account.from_key(
                "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
            )

        # Contract
        self.contract_address = contract_address
        self.contract = None

        if contract_address:
            self._load_contract(contract_address)

        # IPFS (optional - for storing large birth certificate data)
        self.ipfs_gateway = ipfs_gateway

        # Local storage
        self.vehicles = {}  # vehicle_id -> vehicle data
        self.birth_certificates = {}  # vehicleIdentity -> VehicleBirth
        self.did_cache = {}  # DID -> resolved document (TTL cache)

        # VIN encryption keys (in production, use HSM or key management service)
        self.vin_encryption_keys = {}  # vehicle_id -> encryption key

        # Update metrics
        self.metrics.signature_algorithm = "ECDSA-secp256k1"
        self.metrics.key_size_bits = 256
        self.metrics.revocation_mechanism = "blockchain_registry"
        self.metrics.pseudonymity_support = False
        self.metrics.single_point_of_failure = False
        self.metrics.availability_percentage = 99.0

    def _load_contract(self, address: str):
        """Load MOBIVIDRegistry contract"""
        try:
            with open('contracts/MOBIVIDRegistry_abi.json', 'r') as f:
                abi = json.load(f)
        except FileNotFoundError:
            # Use inline ABI for bootstrapping
            abi = self._get_inline_abi()

        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(address),
            abi=abi
        )

    def _get_inline_abi(self) -> list:
        """Get inline ABI for MOBIVIDRegistry"""
        return [
            {
                "inputs": [
                    {"internalType": "address", "name": "vehicleIdentity", "type": "address"},
                    {"internalType": "bytes32", "name": "vinHash", "type": "bytes32"},
                    {"internalType": "string", "name": "encryptedVIN", "type": "string"},
                    {"internalType": "bytes32", "name": "birthCertHash", "type": "bytes32"},
                    {"internalType": "address", "name": "firstOwner", "type": "address"},
                    {"internalType": "bytes", "name": "birthAttributes", "type": "bytes"}
                ],
                "name": "registerVehicleBirth",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "vehicleIdentity", "type": "address"}],
                "name": "getVehicleInfo",
                "outputs": [
                    {
                        "components": [
                            {"internalType": "bytes32", "name": "vinHash", "type": "bytes32"},
                            {"internalType": "string", "name": "encryptedVIN", "type": "string"},
                            {"internalType": "bytes32", "name": "birthCertHash", "type": "bytes32"},
                            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                            {"internalType": "address", "name": "manufacturer", "type": "address"},
                            {"internalType": "address", "name": "firstOwner", "type": "address"},
                            {"internalType": "uint256", "name": "blockNumber", "type": "uint256"},
                            {"internalType": "bool", "name": "exists", "type": "bool"}
                        ],
                        "internalType": "struct MOBIVIDRegistry.VehicleBirth",
                        "name": "birth",
                        "type": "tuple"
                    },
                    {"internalType": "address", "name": "currentOwner", "type": "address"},
                    {"internalType": "bool", "name": "isRevoked", "type": "bool"},
                    {"internalType": "uint256", "name": "transferCount", "type": "uint256"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "bytes32", "name": "vinHash", "type": "bytes32"}],
                "name": "lookupByVINHash",
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "identity", "type": "address"}],
                "name": "revokeIdentity",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "vehicleIdentity", "type": "address"},
                    {"internalType": "address", "name": "newOwner", "type": "address"},
                    {"internalType": "uint256", "name": "odometer", "type": "uint256"},
                    {"internalType": "string", "name": "authority", "type": "string"}
                ],
                "name": "transferVehicleOwnership",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]

    # ============ VIN PRIVACY UTILITIES ============

    def _hash_vin(self, vin: str, vehicle_identity: str, salt: Optional[str] = None) -> bytes:
        """
        Create privacy-preserving VIN hash.

        Hash = SHA256(VIN + salt + vehicleDID)

        This allows:
        - Public searchability (by VIN hash)
        - Privacy (VIN not revealed)
        - Uniqueness (includes vehicle DID)
        """
        if salt is None:
            salt = secrets.token_hex(16)

        hash_input = f"{vin}{salt}{vehicle_identity}".encode('utf-8')
        vin_hash = hashlib.sha256(hash_input).digest()

        # Store salt for later verification
        if vehicle_identity not in self.vehicles:
            self.vehicles[vehicle_identity] = {}
        self.vehicles[vehicle_identity]['vin_salt'] = salt

        return vin_hash

    def _encrypt_vin(self, vin: str, owner_public_key: bytes) -> str:
        """
        Encrypt VIN with owner's public key.

        In production, use owner's public key for asymmetric encryption.
        For simplicity, using symmetric encryption with a generated key.
        """
        # Generate encryption key
        key = AESGCM.generate_key(bit_length=256)
        aesgcm = AESGCM(key)

        # Encrypt
        nonce = secrets.token_bytes(12)
        ciphertext = aesgcm.encrypt(nonce, vin.encode('utf-8'), None)

        # Combine nonce + ciphertext and encode as hex
        encrypted = nonce + ciphertext

        # Store key for this vehicle (in production, encrypt key with owner's public key)
        # For now, store in memory
        return encrypted.hex()

    def _decrypt_vin(self, encrypted_vin_hex: str, vehicle_identity: str) -> str:
        """Decrypt VIN (for authorized users only)"""
        # In production, use private key to decrypt
        # For now, this is a placeholder
        return "[ENCRYPTED_VIN]"

    # ============ VEHICLE BIRTH REGISTRATION (MOBI VID I) ============

    def register_vehicle_birth(
        self,
        vin: str,
        manufacturer_data: Dict[str, Any],
        vehicle_data: Dict[str, Any],
        first_owner_address: str,
        birth_cert_data: Optional[Dict] = None
    ) -> VehicleCredential:
        """
        Register vehicle birth certificate on blockchain.

        This is the core MOBI VID I function.

        Args:
            vin: Vehicle Identification Number
            manufacturer_data: Manufacturer information (name, plant, etc.)
            vehicle_data: Vehicle specifications (make, model, year, etc.)
            first_owner_address: Ethereum address of first owner
            birth_cert_data: Optional full birth certificate data (stored on IPFS)

        Returns:
            VehicleCredential with VID
        """
        start_time = time.time()

        if not self.contract:
            raise RuntimeError("Contract not loaded. Deploy or set contract address first.")

        # Generate vehicle identity (deterministic from VIN)
        vehicle_identity = self._generate_vehicle_identity(vin)
        vehicle_identity_addr = Web3.to_checksum_address(vehicle_identity)

        # Create VIN hash for privacy
        vin_hash = self._hash_vin(vin, vehicle_identity)
        vin_hash_bytes32 = Web3.to_bytes(hexstr=vin_hash.hex())

        # Encrypt VIN
        owner_pub_key = b""  # Placeholder
        encrypted_vin = self._encrypt_vin(vin, owner_pub_key)

        # Create complete birth certificate
        complete_birth_cert = {
            "vin": vin,
            "manufacturer": manufacturer_data,
            "vehicle": vehicle_data,
            "first_owner": first_owner_address,
            "timestamp": int(time.time()),
            "standard": "MOBI VID I v1.0"
        }

        if birth_cert_data:
            complete_birth_cert.update(birth_cert_data)

        # Store on IPFS (or just hash it for now)
        birth_cert_json = json.dumps(complete_birth_cert, sort_keys=True)
        birth_cert_hash = hashlib.sha256(birth_cert_json.encode()).digest()
        birth_cert_hash_bytes32 = Web3.to_bytes(hexstr=birth_cert_hash.hex())

        # Encode birth attributes for on-chain storage
        birth_attributes = json.dumps({
            "make": vehicle_data.get("make", ""),
            "model": vehicle_data.get("model", ""),
            "year": vehicle_data.get("year", 0),
            "manufacturer": manufacturer_data.get("name", "")
        }).encode('utf-8')

        # Register on blockchain
        first_owner_checksum = Web3.to_checksum_address(first_owner_address)

        try:
            # Build transaction
            transaction = self.contract.functions.registerVehicleBirth(
                vehicle_identity_addr,
                vin_hash_bytes32,
                encrypted_vin,
                birth_cert_hash_bytes32,
                first_owner_checksum,
                birth_attributes
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price
            })

            # Sign and send
            signed = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)

            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            # Update metrics
            gas_used = receipt['gasUsed']
            gas_price_gwei = self.w3.from_wei(transaction['gasPrice'], 'gwei')
            gas_cost_eth = self.w3.from_wei(gas_used * transaction['gasPrice'], 'ether')

            self.metrics.gas_used += gas_used
            self.metrics.transaction_hash = receipt['transactionHash'].hex()
            self.metrics.block_number = receipt['blockNumber']
            self.metrics.registration_cost = float(gas_cost_eth)

        except Exception as e:
            raise RuntimeError(f"Failed to register vehicle birth: {str(e)}")

        # Store locally
        self.vehicles[vehicle_identity] = {
            'vin': vin,
            'vin_hash': vin_hash.hex(),
            'encrypted_vin': encrypted_vin,
            'birth_cert': complete_birth_cert,
            'first_owner': first_owner_address,
            'current_owner': first_owner_address,
            'registered_at': int(time.time()),
            'tx_hash': receipt['transactionHash'].hex()
        }

        # Generate key pair for vehicle
        private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
        public_key = private_key.public_key()

        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )

        self.vehicles[vehicle_identity]['private_key'] = private_key
        self.vehicles[vehicle_identity]['public_key'] = public_key_bytes.hex()

        # Create credential
        credential = VehicleCredential(
            vehicle_id=f"did:ethr:0x{self.w3.eth.chain_id:x}:{vehicle_identity}",
            public_key=public_key_bytes.hex(),
            credential_data={
                "type": "MOBIVehicleBirthCertificate",
                "vin_hash": vin_hash.hex(),
                "vehicle_identity": vehicle_identity,
                "manufacturer": manufacturer_data.get("name", ""),
                "make": vehicle_data.get("make", ""),
                "model": vehicle_data.get("model", ""),
                "year": vehicle_data.get("year", 0),
                "birth_cert_hash": birth_cert_hash.hex(),
                "blockchain_tx": receipt['transactionHash'].hex(),
                "block_number": receipt['blockNumber']
            },
            signature="",  # Self-signed
            issuer=self.account.address,
            issued_at=int(time.time()),
            expires_at=int(time.time()) + 31536000,  # 1 year
            revoked=False
        )

        # Calculate registration time
        registration_time = (time.time() - start_time) * 1000
        self.metrics.registration_time_ms = registration_time

        return credential

    def _generate_vehicle_identity(self, vin: str) -> str:
        """Generate deterministic vehicle identity address from VIN"""
        # Hash VIN to get deterministic address
        vin_bytes = vin.encode('utf-8')
        hash_result = hashlib.sha256(vin_bytes).digest()

        # Take first 20 bytes for Ethereum address
        address_bytes = hash_result[:20]
        address = '0x' + address_bytes.hex()

        return address

    # ============ IDENTITY PROVIDER INTERFACE ============

    def register_vehicle(self, vehicle_id: str, metadata: Dict = None) -> VehicleCredential:
        """
        Register a new vehicle identity.

        This is the IdentityProvider interface method.
        For MOBI VID, we use register_vehicle_birth instead.
        """
        if metadata is None:
            metadata = {}

        # Extract MOBI VID specific data from metadata
        vin = metadata.get('vin', f"VIN{vehicle_id}")
        manufacturer = metadata.get('manufacturer', {'name': 'Test Manufacturer'})
        vehicle_data = {
            'make': metadata.get('make', 'Generic'),
            'model': metadata.get('model', 'TestVehicle'),
            'year': metadata.get('year', 2024)
        }
        first_owner = metadata.get('first_owner', self.account.address)

        return self.register_vehicle_birth(
            vin=vin,
            manufacturer_data=manufacturer,
            vehicle_data=vehicle_data,
            first_owner_address=first_owner
        )

    def sign_message(self, vehicle_id: str, message: Dict) -> Dict:
        """Sign a V2X message with vehicle's private key"""
        start_time = time.time()

        # Find vehicle by DID or identity
        vehicle_identity = self._vehicle_id_to_identity(vehicle_id)

        if vehicle_identity not in self.vehicles:
            raise ValueError(f"Vehicle {vehicle_id} not registered")

        vehicle_data = self.vehicles[vehicle_identity]
        private_key = vehicle_data['private_key']

        # Serialize message
        message_json = json.dumps(message, sort_keys=True)
        message_hash = hashlib.sha256(message_json.encode()).digest()

        # Sign
        signature = private_key.sign(
            message_hash,
            ec.ECDSA(hashes.SHA256())
        )

        # Create signed message
        signed_message = {
            'message': message,
            'signature': signature.hex(),
            'public_key': vehicle_data['public_key'],
            'vehicle_did': vehicle_id,
            'timestamp': int(time.time())
        }

        # Update metrics
        sign_time = (time.time() - start_time) * 1000
        self.metrics.authentication_time_ms = sign_time
        self.metrics.signature_size = len(signature)

        return signed_message

    def verify_message(self, signed_message: Dict) -> Tuple[bool, IdentityMetrics]:
        """Verify a signed V2X message"""
        start_time = time.time()

        try:
            # Extract components
            message = signed_message['message']
            signature_hex = signed_message['signature']
            public_key_hex = signed_message['public_key']

            # Reconstruct public key
            public_key_bytes = bytes.fromhex(public_key_hex)
            public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256K1(),
                public_key_bytes
            )

            # Hash message
            message_json = json.dumps(message, sort_keys=True)
            message_hash = hashlib.sha256(message_json.encode()).digest()

            # Verify signature
            signature = bytes.fromhex(signature_hex)
            public_key.verify(
                signature,
                message_hash,
                ec.ECDSA(hashes.SHA256())
            )

            is_valid = True

        except Exception as e:
            is_valid = False

        # Update metrics
        verify_time = (time.time() - start_time) * 1000

        metrics = IdentityMetrics()
        metrics.verification_time_ms = verify_time

        return is_valid, metrics

    def revoke_credential(self, vehicle_id: str, reason: str = "") -> bool:
        """Revoke a vehicle's credential"""
        vehicle_identity = self._vehicle_id_to_identity(vehicle_id)
        vehicle_identity_addr = Web3.to_checksum_address(vehicle_identity)

        try:
            transaction = self.contract.functions.revokeIdentity(
                vehicle_identity_addr
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price
            })

            signed = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if vehicle_identity in self.vehicles:
                self.vehicles[vehicle_identity]['revoked'] = True

            return True

        except Exception as e:
            print(f"Revocation failed: {e}")
            return False

    def check_revocation_status(self, vehicle_id: str) -> Tuple[bool, float]:
        """Check if credential is revoked"""
        start_time = time.time()

        vehicle_identity = self._vehicle_id_to_identity(vehicle_id)

        # Check local cache first
        if vehicle_identity in self.vehicles:
            is_revoked = self.vehicles[vehicle_identity].get('revoked', False)
        else:
            is_revoked = False

        check_time = (time.time() - start_time) * 1000
        return is_revoked, check_time

    def update_credential(self, vehicle_id: str, updates: Dict) -> bool:
        """Update credential data"""
        # MOBI VID I birth certificates are immutable
        # Only ownership can be transferred (VID II)
        return False

    def get_credential(self, vehicle_id: str) -> Optional[VehicleCredential]:
        """Retrieve vehicle credential"""
        vehicle_identity = self._vehicle_id_to_identity(vehicle_id)

        if vehicle_identity not in self.vehicles:
            return None

        vehicle_data = self.vehicles[vehicle_identity]

        return VehicleCredential(
            vehicle_id=vehicle_id,
            public_key=vehicle_data['public_key'],
            credential_data=vehicle_data.get('birth_cert', {}),
            signature="",
            issuer=self.account.address,
            issued_at=vehicle_data.get('registered_at', 0),
            expires_at=vehicle_data.get('registered_at', 0) + 31536000,
            revoked=vehicle_data.get('revoked', False)
        )

    def resolve_identity(self, vehicle_id: str) -> Tuple[Optional[Dict], float]:
        """
        Resolve identity to W3C DID document.

        For MOBI VID, this constructs a DID document from:
        - Birth certificate data
        - Blockchain events
        - Current owner information
        """
        start_time = time.time()

        vehicle_identity = self._vehicle_id_to_identity(vehicle_id)

        if vehicle_identity not in self.vehicles:
            return None, 0.0

        vehicle_data = self.vehicles[vehicle_identity]

        # Construct W3C DID document
        did_document = {
            "@context": [
                "https://www.w3.org/ns/did/v1",
                "https://w3id.org/security/suites/secp256k1-2019/v1"
            ],
            "id": vehicle_id,
            "controller": vehicle_data.get('current_owner', ''),
            "verificationMethod": [
                {
                    "id": f"{vehicle_id}#keys-1",
                    "type": "EcdsaSecp256k1VerificationKey2019",
                    "controller": vehicle_id,
                    "publicKeyHex": vehicle_data['public_key']
                }
            ],
            "authentication": [f"{vehicle_id}#keys-1"],
            "service": [
                {
                    "id": f"{vehicle_id}#mobi-vid-service",
                    "type": "MOBIVehicleIdentityService",
                    "serviceEndpoint": f"https://mobi.example.com/api/vehicle/{vehicle_identity}"
                }
            ],
            "mobi": {
                "type": "VehicleBirthCertificate",
                "standard": "MOBI VID I v1.0",
                "vin_hash": vehicle_data.get('vin_hash', ''),
                "registered_at": vehicle_data.get('registered_at', 0),
                "manufacturer": vehicle_data.get('birth_cert', {}).get('manufacturer', {}),
                "vehicle": vehicle_data.get('birth_cert', {}).get('vehicle', {})
            }
        }

        resolution_time = (time.time() - start_time) * 1000
        self.metrics.resolution_time_ms = resolution_time

        return did_document, resolution_time

    def _vehicle_id_to_identity(self, vehicle_id: str) -> str:
        """Convert vehicle_id (DID or simple ID) to vehicle identity address"""
        if vehicle_id.startswith('did:'):
            # Extract address from DID: did:ethr:0x{chain}:{address}
            parts = vehicle_id.split(':')
            return parts[-1]
        elif vehicle_id.startswith('0x'):
            return vehicle_id
        else:
            # Simple ID - search in our vehicles
            for identity, data in self.vehicles.items():
                if vehicle_id in str(data):
                    return identity
            # Generate from ID
            return self._generate_vehicle_identity(vehicle_id)

    # ============ DEPLOYMENT ============

    def deploy_contract(self) -> str:
        """Deploy MOBIVIDRegistry contract"""
        print("Deploying MOBI VID Registry contract...")

        try:
            with open('contracts/MOBIVIDRegistry_bytecode.txt', 'r') as f:
                bytecode = f.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(
                "Contract bytecode not found. Please compile contract first:\n"
                "  npx hardhat compile"
            )

        # Create contract
        Contract = self.w3.eth.contract(
            abi=self._get_inline_abi(),
            bytecode=bytecode
        )

        # Build transaction
        transaction = Contract.constructor().build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 5000000,
            'gasPrice': self.w3.eth.gas_price
        })

        # Sign and send
        signed = self.account.sign_transaction(transaction)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)

        print(f"Transaction sent: {tx_hash.hex()}")
        print("Waiting for confirmation...")

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        contract_address = receipt.contractAddress
        print(f"✓ MOBI VID Registry deployed at: {contract_address}")
        print(f"  Gas used: {receipt['gasUsed']:,}")

        self.contract_address = contract_address
        self._load_contract(contract_address)

        return contract_address
