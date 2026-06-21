#!/usr/bin/env python3
"""
W3C DID Core v1.0 Compliant Resolver
====================================

Resolves Decentralized Identifiers (DIDs) to DID Documents for all 9 blockchain
identity standards implemented in this thesis.

W3C DID Core Specification: https://www.w3.org/TR/did-core/

Supported DID Methods:
- did:ethr: (ERC-1056 Lightweight Identity)
- did:nft:  (ERC-721 NFT-based Identity)
- did:key:  (ERC-725 Proxy Account)
- did:mobi: (MOBI VID compliant)

Author: Nikhil Prakash
Thesis: MASc, UBC ECE
"""

import json
import hashlib
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum


class DIDMethod(str, Enum):
    """Supported DID methods"""
    ETHR = "ethr"  # ERC-1056
    NFT = "nft"    # ERC-721
    KEY = "key"    # ERC-725
    MOBI = "mobi"  # MOBI VID
    WEB = "web"    # did:web for testing


class VerificationRelationship(str, Enum):
    """W3C DID Core verification relationships"""
    AUTHENTICATION = "authentication"
    ASSERTION_METHOD = "assertionMethod"
    KEY_AGREEMENT = "keyAgreement"
    CAPABILITY_INVOCATION = "capabilityInvocation"
    CAPABILITY_DELEGATION = "capabilityDelegation"


@dataclass
class VerificationMethod:
    """W3C DID Core Verification Method"""
    id: str
    type: str  # e.g., "EcdsaSecp256k1VerificationKey2019"
    controller: str
    publicKeyHex: Optional[str] = None
    publicKeyBase58: Optional[str] = None
    publicKeyJwk: Optional[Dict] = None
    blockchainAccountId: Optional[str] = None  # For ERC-1056


@dataclass
class Service:
    """W3C DID Core Service Endpoint"""
    id: str
    type: str  # e.g., "LinkedDomains", "CredentialRegistry"
    serviceEndpoint: str  # URL or blockchain address


@dataclass
class DIDDocument:
    """
    W3C DID Core v1.0 Compliant DID Document

    Reference: https://www.w3.org/TR/did-core/#core-properties
    """
    context: List[str] = field(default_factory=lambda: [
        "https://www.w3.org/ns/did/v1",
        "https://w3id.org/security/suites/secp256k1-2019/v1"
    ])
    id: str = ""  # DID
    controller: Optional[str] = None
    verificationMethod: List[VerificationMethod] = field(default_factory=list)
    authentication: List[str] = field(default_factory=list)
    assertionMethod: List[str] = field(default_factory=list)
    keyAgreement: List[str] = field(default_factory=list)
    capabilityInvocation: List[str] = field(default_factory=list)
    capabilityDelegation: List[str] = field(default_factory=list)
    service: List[Service] = field(default_factory=list)

    # Optional properties
    alsoKnownAs: List[str] = field(default_factory=list)

    # Metadata (not part of DID Document, but useful for resolution)
    created: Optional[str] = None
    updated: Optional[str] = None
    versionId: Optional[str] = None
    deactivated: bool = False

    def to_dict(self) -> Dict:
        """Convert to W3C compliant dictionary"""
        doc = {
            "@context": self.context,
            "id": self.id
        }

        if self.controller:
            doc["controller"] = self.controller

        if self.verificationMethod:
            doc["verificationMethod"] = [
                {k: v for k, v in asdict(vm).items() if v is not None}
                for vm in self.verificationMethod
            ]

        # Add verification relationships
        for rel in ["authentication", "assertionMethod", "keyAgreement",
                    "capabilityInvocation", "capabilityDelegation"]:
            val = getattr(self, rel)
            if val:
                doc[rel] = val

        if self.service:
            doc["service"] = [asdict(s) for s in self.service]

        if self.alsoKnownAs:
            doc["alsoKnownAs"] = self.alsoKnownAs

        return doc


@dataclass
class DIDResolutionMetadata:
    """W3C DID Resolution metadata"""
    contentType: str = "application/did+ld+json"
    retrieved: Optional[str] = None
    error: Optional[str] = None
    errorMessage: Optional[str] = None


@dataclass
class DIDDocumentMetadata:
    """W3C DID Document metadata"""
    created: Optional[str] = None
    updated: Optional[str] = None
    deactivated: bool = False
    versionId: Optional[str] = None
    nextUpdate: Optional[str] = None
    nextVersionId: Optional[str] = None
    equivalentId: List[str] = field(default_factory=list)
    canonicalId: Optional[str] = None


@dataclass
class DIDResolutionResult:
    """W3C DID Resolution Result"""
    didResolutionMetadata: DIDResolutionMetadata
    didDocument: Optional[DIDDocument]
    didDocumentMetadata: DIDDocumentMetadata

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "didResolutionMetadata": asdict(self.didResolutionMetadata),
            "didDocument": self.didDocument.to_dict() if self.didDocument else None,
            "didDocumentMetadata": asdict(self.didDocumentMetadata)
        }


class DIDResolver:
    """
    Universal DID Resolver for all thesis blockchain identity standards

    Implements W3C DID Core Resolution specification:
    https://www.w3.org/TR/did-core/#resolution
    """

    def __init__(self, blockchain_provider=None):
        """
        Initialize DID Resolver

        Args:
            blockchain_provider: Web3 provider for blockchain lookups
        """
        self.blockchain_provider = blockchain_provider
        self.cache = {}  # Simple cache for resolved DIDs

    def resolve(self, did: str) -> DIDResolutionResult:
        """
        Resolve a DID to a DID Document

        Args:
            did: The DID to resolve (e.g., "did:ethr:0x123...")

        Returns:
            DIDResolutionResult with document or error
        """
        start_time = time.time()

        try:
            # Parse DID
            method, identifier = self._parse_did(did)

            # Check cache
            if did in self.cache:
                cached = self.cache[did]
                # Update retrieval time
                cached.didResolutionMetadata.retrieved = datetime.now(timezone.utc).isoformat()
                return cached

            # Resolve based on method
            if method == DIDMethod.ETHR:
                result = self._resolve_ethr(did, identifier)
            elif method == DIDMethod.NFT:
                result = self._resolve_nft(did, identifier)
            elif method == DIDMethod.KEY:
                result = self._resolve_key(did, identifier)
            elif method == DIDMethod.MOBI:
                result = self._resolve_mobi(did, identifier)
            else:
                # Method not supported
                result = DIDResolutionResult(
                    didResolutionMetadata=DIDResolutionMetadata(
                        error="methodNotSupported",
                        errorMessage=f"DID method '{method}' is not supported"
                    ),
                    didDocument=None,
                    didDocumentMetadata=DIDDocumentMetadata()
                )

            # Set retrieval time
            result.didResolutionMetadata.retrieved = datetime.now(timezone.utc).isoformat()

            # Cache successful resolutions
            if not result.didResolutionMetadata.error:
                self.cache[did] = result

            # Log resolution time
            elapsed_ms = (time.time() - start_time) * 1000
            print(f"✅ Resolved {did} in {elapsed_ms:.2f}ms")

            return result

        except Exception as e:
            return DIDResolutionResult(
                didResolutionMetadata=DIDResolutionMetadata(
                    error="internalError",
                    errorMessage=str(e)
                ),
                didDocument=None,
                didDocumentMetadata=DIDDocumentMetadata()
            )

    def _parse_did(self, did: str) -> Tuple[DIDMethod, str]:
        """Parse DID into method and identifier"""
        parts = did.split(":")

        if len(parts) < 3 or parts[0] != "did":
            raise ValueError(f"Invalid DID format: {did}")

        method = parts[1]
        identifier = ":".join(parts[2:])  # Everything after method

        try:
            method_enum = DIDMethod(method)
        except ValueError:
            raise ValueError(f"Unsupported DID method: {method}")

        return method_enum, identifier

    def _resolve_ethr(self, did: str, identifier: str) -> DIDResolutionResult:
        """
        Resolve did:ethr (ERC-1056 Lightweight Identity)

        Format: did:ethr:<chainId>:<address>
        Example: did:ethr:0x1:0x1234567890abcdef1234567890abcdef12345678
        """
        # Parse chain ID and address
        parts = identifier.split(":")
        if len(parts) == 2:
            chain_id, address = parts
        else:
            # Default to mainnet
            chain_id = "0x1"
            address = identifier

        # In production, would query ERC-1056 registry on blockchain
        # For thesis demo, construct minimal valid DID document

        verification_method_id = f"{did}#controller"

        verification_method = VerificationMethod(
            id=verification_method_id,
            type="EcdsaSecp256k1VerificationKey2019",
            controller=did,
            blockchainAccountId=f"eip155:{chain_id}:{address}"
        )

        did_document = DIDDocument(
            id=did,
            controller=did,
            verificationMethod=[verification_method],
            authentication=[verification_method_id],
            assertionMethod=[verification_method_id],
            created=datetime.now(timezone.utc).isoformat(),
            versionId="1"
        )

        return DIDResolutionResult(
            didResolutionMetadata=DIDResolutionMetadata(),
            didDocument=did_document,
            didDocumentMetadata=DIDDocumentMetadata(
                created=did_document.created,
                versionId=did_document.versionId
            )
        )

    def _resolve_nft(self, did: str, identifier: str) -> DIDResolutionResult:
        """
        Resolve did:nft (ERC-721 NFT-based Identity)

        Format: did:nft:<chainId>:<contractAddress>:<tokenId>
        """
        parts = identifier.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid did:nft format: {did}")

        chain_id, contract_address, token_id = parts

        # Would query ERC-721 contract for token owner
        verification_method_id = f"{did}#owner"

        verification_method = VerificationMethod(
            id=verification_method_id,
            type="EcdsaSecp256k1VerificationKey2019",
            controller=did,
            blockchainAccountId=f"eip155:{chain_id}:{contract_address}"
        )

        # Add NFT metadata service
        service = Service(
            id=f"{did}#nft-metadata",
            type="NFTMetadata",
            serviceEndpoint=f"https://api.opensea.io/api/v1/asset/{contract_address}/{token_id}"
        )

        did_document = DIDDocument(
            id=did,
            verificationMethod=[verification_method],
            authentication=[verification_method_id],
            service=[service],
            created=datetime.now(timezone.utc).isoformat(),
            versionId="1"
        )

        return DIDResolutionResult(
            didResolutionMetadata=DIDResolutionMetadata(),
            didDocument=did_document,
            didDocumentMetadata=DIDDocumentMetadata(
                created=did_document.created
            )
        )

    def _resolve_key(self, did: str, identifier: str) -> DIDResolutionResult:
        """
        Resolve did:key (ERC-725 Proxy Account)

        Format: did:key:<chainId>:<proxyAddress>
        """
        parts = identifier.split(":")
        if len(parts) == 2:
            chain_id, proxy_address = parts
        else:
            chain_id = "0x1"
            proxy_address = identifier

        verification_method_id = f"{did}#keys-1"

        verification_method = VerificationMethod(
            id=verification_method_id,
            type="EcdsaSecp256k1VerificationKey2019",
            controller=did,
            blockchainAccountId=f"eip155:{chain_id}:{proxy_address}"
        )

        did_document = DIDDocument(
            id=did,
            verificationMethod=[verification_method],
            authentication=[verification_method_id],
            assertionMethod=[verification_method_id],
            capabilityInvocation=[verification_method_id],
            created=datetime.now(timezone.utc).isoformat()
        )

        return DIDResolutionResult(
            didResolutionMetadata=DIDResolutionMetadata(),
            didDocument=did_document,
            didDocumentMetadata=DIDDocumentMetadata(
                created=did_document.created
            )
        )

    def _resolve_mobi(self, did: str, identifier: str) -> DIDResolutionResult:
        """
        Resolve did:mobi (MOBI VID compliant)

        Format: did:mobi:<vin>
        Example: did:mobi:5YJ3E1EA0PF123456
        """
        vin = identifier

        # MOBI VID uses VIN as identifier
        # Would query MOBI VID registry for birth certificate

        verification_method_id = f"{did}#manufacturer-key"

        verification_method = VerificationMethod(
            id=verification_method_id,
            type="EcdsaSecp256k1VerificationKey2019",
            controller=did,
            publicKeyHex="0x..."  # Would be from birth certificate
        )

        # MOBI VID service endpoints
        services = [
            Service(
                id=f"{did}#birth-certificate",
                type="MobiVidBirthCertificate",
                serviceEndpoint="ipfs://Qm..."  # IPFS hash of birth cert
            ),
            Service(
                id=f"{did}#lifecycle-events",
                type="MobiVidLifecycleEvents",
                serviceEndpoint="https://mobi-vid-registry.example.com/events"
            )
        ]

        did_document = DIDDocument(
            id=did,
            verificationMethod=[verification_method],
            authentication=[verification_method_id],
            service=services,
            created=datetime.now(timezone.utc).isoformat(),
            alsoKnownAs=[f"vin:{vin}"]
        )

        return DIDResolutionResult(
            didResolutionMetadata=DIDResolutionMetadata(),
            didDocument=did_document,
            didDocumentMetadata=DIDDocumentMetadata(
                created=did_document.created
            )
        )

    def create_did(self, method: DIDMethod, **kwargs) -> Tuple[str, DIDDocument]:
        """
        Create a new DID

        Args:
            method: DID method to use
            **kwargs: Method-specific parameters

        Returns:
            Tuple of (DID string, DID Document)
        """
        if method == DIDMethod.ETHR:
            address = kwargs.get("address")
            chain_id = kwargs.get("chain_id", "0x1")
            did = f"did:ethr:{chain_id}:{address}"

        elif method == DIDMethod.MOBI:
            vin = kwargs.get("vin")
            did = f"did:mobi:{vin}"

        elif method == DIDMethod.NFT:
            chain_id = kwargs.get("chain_id", "0x1")
            contract = kwargs.get("contract_address")
            token_id = kwargs.get("token_id")
            did = f"did:nft:{chain_id}:{contract}:{token_id}"

        else:
            raise ValueError(f"Unsupported DID method: {method}")

        # Resolve to get DID document
        result = self.resolve(did)

        return did, result.didDocument


# ============ CLI Interface ============

def main():
    """CLI for testing DID resolution"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python did_resolver.py <DID>")
        print("\nExamples:")
        print("  python did_resolver.py did:ethr:0x1:0x1234567890abcdef1234567890abcdef12345678")
        print("  python did_resolver.py did:mobi:5YJ3E1EA0PF123456")
        print("  python did_resolver.py did:nft:0x1:0xabc:123")
        sys.exit(1)

    did = sys.argv[1]

    print(f"🔍 Resolving DID: {did}\n")

    resolver = DIDResolver()
    result = resolver.resolve(did)

    if result.didResolutionMetadata.error:
        print(f"❌ Error: {result.didResolutionMetadata.error}")
        print(f"   {result.didResolutionMetadata.errorMessage}")
    else:
        print("✅ DID Document:")
        print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
