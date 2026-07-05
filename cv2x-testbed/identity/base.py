"""
Modular Identity Architecture for V2X

This module provides an abstract interface for vehicle identity systems,
enabling seamless comparison between centralized (PKI) and decentralized (DID)
approaches.

Design Principles:
1. Identity Backend Agnostic: Applications don't know/care about identity type
2. Hot-Swappable: Change identity system at runtime
3. Metric Collection: Unified metrics across all identity types
4. Production Ready: Real implementations, not mocks
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import time
import json


class IdentityType(Enum):
    """Supported identity system types"""
    CENTRALIZED_PKI = "centralized_pki"
    ERC1056_DID = "erc1056_did"
    HYBRID = "hybrid"  # PKI + blockchain anchoring
    FEDERATED = "federated"  # Consortium


@dataclass
class IdentityMetrics:
    """Unified metrics for all identity systems"""

    # Performance (milliseconds)
    registration_time_ms: float = 0.0
    authentication_time_ms: float = 0.0
    verification_time_ms: float = 0.0
    revocation_time_ms: float = 0.0
    resolution_time_ms: float = 0.0  # DID document lookup

    # Cost
    registration_cost: float = 0.0  # Gas for DID, $ for PKI CA fees
    update_cost: float = 0.0
    revocation_cost: float = 0.0

    # Size (bytes)
    credential_size: int = 0
    signature_size: int = 0
    message_overhead: int = 0

    # Security
    signature_algorithm: str = ""
    key_size_bits: int = 0
    revocation_mechanism: str = ""

    # Privacy
    pseudonymity_support: bool = False
    unlinkability_score: float = 0.0  # 0-1, higher is better
    tracking_resistance_time_s: float = 0.0

    # Scalability
    max_operations_per_second: float = 0.0
    concurrent_verifications: int = 0

    # Reliability
    single_point_of_failure: bool = True
    availability_percentage: float = 0.0

    # Blockchain specific (0 for centralized)
    gas_used: int = 0
    transaction_hash: str = ""
    block_number: int = 0
    network_congestion_impact: float = 0.0  # latency increase under load

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VehicleCredential:
    """Universal credential representation"""
    vehicle_id: str
    public_key: str  # Hex encoded
    credential_data: Dict[str, Any]  # Identity-specific data
    signature: str
    issuer: str
    issued_at: int  # Unix timestamp
    expires_at: int
    revoked: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class IdentityProvider(ABC):
    """
    Abstract base class for all identity providers.

    Any identity system (PKI, DID, hybrid) must implement this interface.
    """

    def __init__(self, identity_type: IdentityType):
        self.identity_type = identity_type
        self.metrics = IdentityMetrics()
        self._operation_count = 0

    @abstractmethod
    def register_vehicle(self, vehicle_id: str, metadata: Dict = None) -> VehicleCredential:
        """
        Register a new vehicle identity.

        Args:
            vehicle_id: Unique vehicle identifier
            metadata: Additional metadata (VIN, make, model, etc.)

        Returns:
            VehicleCredential: Issued credential
        """
        pass

    @abstractmethod
    def sign_message(self, vehicle_id: str, message: Dict) -> Dict:
        """
        Sign a V2X message.

        Args:
            vehicle_id: Vehicle identifier
            message: Message to sign (BSM, DENM, etc.)

        Returns:
            Signed message with authentication data
        """
        pass

    @abstractmethod
    def verify_message(self, signed_message: Dict) -> Tuple[bool, IdentityMetrics]:
        """
        Verify a signed V2X message.

        Args:
            signed_message: Message with signature/credential

        Returns:
            Tuple of (is_valid, metrics_for_this_operation)
        """
        pass

    @abstractmethod
    def revoke_credential(self, vehicle_id: str, reason: str = "") -> bool:
        """
        Revoke a vehicle's credential.

        Args:
            vehicle_id: Vehicle to revoke
            reason: Revocation reason

        Returns:
            Success status
        """
        pass

    @abstractmethod
    def check_revocation_status(self, vehicle_id: str) -> Tuple[bool, float]:
        """
        Check if credential is revoked.

        Args:
            vehicle_id: Vehicle to check

        Returns:
            Tuple of (is_revoked, check_time_ms)
        """
        pass

    @abstractmethod
    def update_credential(self, vehicle_id: str, updates: Dict) -> bool:
        """
        Update credential data (e.g., new public key, metadata).

        Args:
            vehicle_id: Vehicle identifier
            updates: Data to update

        Returns:
            Success status
        """
        pass

    @abstractmethod
    def get_credential(self, vehicle_id: str) -> Optional[VehicleCredential]:
        """
        Retrieve vehicle credential.

        Args:
            vehicle_id: Vehicle identifier

        Returns:
            VehicleCredential or None if not found
        """
        pass

    @abstractmethod
    def resolve_identity(self, vehicle_id: str) -> Tuple[Optional[Dict], float]:
        """
        Resolve identity to get public key and metadata.

        For DID: Resolve DID document
        For PKI: Lookup certificate

        Args:
            vehicle_id: Vehicle identifier

        Returns:
            Tuple of (identity_data, resolution_time_ms)
        """
        pass

    def get_metrics(self) -> IdentityMetrics:
        """Get accumulated metrics for this identity provider"""
        return self.metrics

    def reset_metrics(self):
        """Reset metrics counters"""
        self.metrics = IdentityMetrics()
        self._operation_count = 0

    def get_type(self) -> IdentityType:
        """Get identity type"""
        return self.identity_type

    def get_display_name(self) -> str:
        """Get human-readable name"""
        return self.identity_type.value.replace("_", " ").title()


class IdentityManager:
    """
    Identity Manager: Orchestrates multiple identity providers.

    Allows running experiments with different identity backends
    and collecting comparative metrics.
    """

    def __init__(self):
        self.providers: Dict[IdentityType, IdentityProvider] = {}
        self.active_provider: Optional[IdentityProvider] = None
        self.comparison_mode = False

    def register_provider(self, provider: IdentityProvider):
        """Register an identity provider"""
        self.providers[provider.get_type()] = provider

        # Set as active if first provider
        if self.active_provider is None:
            self.active_provider = provider

    def set_active_provider(self, identity_type: IdentityType):
        """Switch active identity provider"""
        if identity_type not in self.providers:
            raise ValueError(f"Provider {identity_type} not registered")

        self.active_provider = self.providers[identity_type]

    def enable_comparison_mode(self):
        """
        Enable comparison mode: operations run on ALL providers
        and metrics are collected for each.
        """
        self.comparison_mode = True

    def disable_comparison_mode(self):
        """Disable comparison mode"""
        self.comparison_mode = False

    def register_vehicle(self, vehicle_id: str, metadata: Dict = None) -> VehicleCredential:
        """Register vehicle with active or all providers"""
        if self.comparison_mode:
            credentials = {}
            for identity_type, provider in self.providers.items():
                credentials[identity_type] = provider.register_vehicle(vehicle_id, metadata)
            return credentials
        else:
            return self.active_provider.register_vehicle(vehicle_id, metadata)

    def sign_message(self, vehicle_id: str, message: Dict) -> Dict:
        """Sign message with active provider"""
        return self.active_provider.sign_message(vehicle_id, message)

    def verify_message(self, signed_message: Dict) -> Tuple[bool, IdentityMetrics]:
        """Verify message with active provider"""
        return self.active_provider.verify_message(signed_message)

    def compare_all_providers(self, operation: str, *args, **kwargs) -> Dict[IdentityType, Any]:
        """
        Run an operation on all registered providers and return results.

        Useful for benchmarking and comparison.
        """
        results = {}

        for identity_type, provider in self.providers.items():
            start = time.time()

            try:
                if operation == "register":
                    result = provider.register_vehicle(*args, **kwargs)
                elif operation == "sign":
                    result = provider.sign_message(*args, **kwargs)
                elif operation == "verify":
                    result = provider.verify_message(*args, **kwargs)
                elif operation == "revoke":
                    result = provider.revoke_credential(*args, **kwargs)
                elif operation == "resolve":
                    result = provider.resolve_identity(*args, **kwargs)
                else:
                    raise ValueError(f"Unknown operation: {operation}")

                elapsed = (time.time() - start) * 1000

                results[identity_type] = {
                    'result': result,
                    'time_ms': elapsed,
                    'success': True
                }

            except Exception as e:
                results[identity_type] = {
                    'error': str(e),
                    'success': False
                }

        return results

    def get_comparative_metrics(self) -> Dict[str, IdentityMetrics]:
        """Get metrics from all providers for comparison"""
        return {
            provider.get_display_name(): provider.get_metrics()
            for provider in self.providers.values()
        }

    def reset_all_metrics(self):
        """Reset metrics on all providers"""
        for provider in self.providers.values():
            provider.reset_metrics()

    def export_comparison_report(self, filepath: str):
        """Export comparison metrics to JSON"""
        metrics = self.get_comparative_metrics()

        report = {
            'timestamp': time.time(),
            'providers': list(self.providers.keys()),
            'metrics': {
                name: metrics_obj.to_dict()
                for name, metrics_obj in metrics.items()
            }
        }

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)


class IdentityBenchmark:
    """
    Benchmark suite for comparing identity providers.
    """

    def __init__(self, manager: IdentityManager):
        self.manager = manager
        self.results = []

    def benchmark_registration(self, num_vehicles: int = 100) -> Dict:
        """Benchmark vehicle registration across all providers"""
        print(f"\n{'='*60}")
        print(f"BENCHMARKING: Vehicle Registration ({num_vehicles} vehicles)")
        print(f"{'='*60}\n")

        results = {}

        for identity_type, provider in self.manager.providers.items():
            print(f"Testing {provider.get_display_name()}...")
            provider.reset_metrics()

            times = []
            for i in range(num_vehicles):
                vehicle_id = f"BENCH_{identity_type.value}_{i}"
                start = time.time()

                try:
                    provider.register_vehicle(vehicle_id, {"benchmark": True})
                    elapsed = (time.time() - start) * 1000
                    times.append(elapsed)
                except Exception as e:
                    print(f"  Error: {e}")
                    break

            if times:
                import statistics
                results[identity_type] = {
                    'mean_ms': statistics.mean(times),
                    'median_ms': statistics.median(times),
                    'min_ms': min(times),
                    'max_ms': max(times),
                    'std_ms': statistics.stdev(times) if len(times) > 1 else 0,
                    'total_cost': provider.get_metrics().registration_cost * num_vehicles,
                    'success_count': len(times)
                }

                print(f"  Mean: {results[identity_type]['mean_ms']:.2f} ms")
                print(f"  Median: {results[identity_type]['median_ms']:.2f} ms")
                print(f"  Total Cost: ${results[identity_type]['total_cost']:.4f}")

        return results

    def benchmark_signing(self, num_messages: int = 1000) -> Dict:
        """Benchmark message signing"""
        print(f"\n{'='*60}")
        print(f"BENCHMARKING: Message Signing ({num_messages} messages)")
        print(f"{'='*60}\n")

        results = {}
        test_message = {
            'type': 'BSM',
            'position': {'lat': 49.2827, 'lon': -123.1207},
            'speed': 50,
            'heading': 90
        }

        for identity_type, provider in self.manager.providers.items():
            print(f"Testing {provider.get_display_name()}...")

            # Register test vehicle
            vehicle_id = f"SIGN_TEST_{identity_type.value}"
            provider.register_vehicle(vehicle_id)

            times = []
            sizes = []

            for i in range(num_messages):
                start = time.time()

                try:
                    signed = provider.sign_message(vehicle_id, test_message)
                    elapsed = (time.time() - start) * 1000
                    times.append(elapsed)

                    # Measure size
                    size = len(json.dumps(signed).encode())
                    sizes.append(size)

                except Exception as e:
                    print(f"  Error: {e}")
                    break

            if times:
                import statistics
                results[identity_type] = {
                    'mean_ms': statistics.mean(times),
                    'median_ms': statistics.median(times),
                    'p95_ms': statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times),
                    'mean_size_bytes': statistics.mean(sizes),
                    'overhead_bytes': statistics.mean(sizes) - len(json.dumps(test_message).encode()),
                }

                print(f"  Mean: {results[identity_type]['mean_ms']:.3f} ms")
                print(f"  95th percentile: {results[identity_type]['p95_ms']:.3f} ms")
                print(f"  Overhead: {results[identity_type]['overhead_bytes']:.0f} bytes")

        return results

    def benchmark_verification(self, num_verifications: int = 1000) -> Dict:
        """Benchmark message verification"""
        print(f"\n{'='*60}")
        print(f"BENCHMARKING: Message Verification ({num_verifications} messages)")
        print(f"{'='*60}\n")

        results = {}
        test_message = {
            'type': 'BSM',
            'position': {'lat': 49.2827, 'lon': -123.1207},
            'speed': 50,
            'heading': 90
        }

        for identity_type, provider in self.manager.providers.items():
            print(f"Testing {provider.get_display_name()}...")

            # Create signed message
            vehicle_id = f"VERIFY_TEST_{identity_type.value}"
            provider.register_vehicle(vehicle_id)
            signed_message = provider.sign_message(vehicle_id, test_message)

            times = []
            success_count = 0

            for i in range(num_verifications):
                is_valid, metrics = provider.verify_message(signed_message)

                if is_valid:
                    times.append(metrics.verification_time_ms)
                    success_count += 1

            if times:
                import statistics
                results[identity_type] = {
                    'mean_ms': statistics.mean(times),
                    'median_ms': statistics.median(times),
                    'p95_ms': statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times),
                    'success_rate': success_count / num_verifications,
                }

                print(f"  Mean: {results[identity_type]['mean_ms']:.3f} ms")
                print(f"  95th percentile: {results[identity_type]['p95_ms']:.3f} ms")
                print(f"  Success Rate: {results[identity_type]['success_rate']*100:.1f}%")

        return results

    def run_full_benchmark_suite(self) -> Dict:
        """Run complete benchmark suite"""
        print("\n" + "="*60)
        print("COMPLETE IDENTITY SYSTEM BENCHMARK SUITE")
        print("="*60)

        results = {
            'registration': self.benchmark_registration(num_vehicles=100),
            'signing': self.benchmark_signing(num_messages=1000),
            'verification': self.benchmark_verification(num_verifications=1000),
        }

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}\n")

        for operation, data in results.items():
            print(f"{operation.upper()}:")
            for identity_type, metrics in data.items():
                print(f"  {identity_type.value}:")
                for metric, value in metrics.items():
                    print(f"    {metric}: {value}")
            print()

        return results


if __name__ == "__main__":
    print("Modular Identity Architecture")
    print("This module defines the abstract interface for identity providers.")
    print("\nSupported Identity Types:")
    for it in IdentityType:
        print(f"  - {it.value}")
