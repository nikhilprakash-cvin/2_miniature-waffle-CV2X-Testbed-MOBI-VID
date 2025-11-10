"""
Identity System Comparison Framework

Compares standard PKI-based identity with DID/SSI-based identity
for connected vehicle applications.
"""

import time
import json
import statistics
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict


@dataclass
class IdentityMetrics:
    """Metrics for identity system evaluation"""

    # Performance Metrics
    enrollment_time_ms: float = 0.0
    credential_request_time_ms: float = 0.0
    signing_time_ms: float = 0.0
    verification_time_ms: float = 0.0
    revocation_check_time_ms: float = 0.0

    # Size Metrics (bytes)
    credential_size: int = 0
    signature_size: int = 0
    public_key_size: int = 0
    signed_message_size: int = 0

    # Functional Metrics
    privacy_level: str = "unknown"  # low, medium, high
    decentralization: str = "centralized"  # centralized, federated, decentralized
    scalability: str = "unknown"  # poor, moderate, good, excellent
    revocation_mechanism: str = "unknown"  # CRL, OCSP, blockchain, etc.

    # Resource Metrics
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    network_overhead_kb: float = 0.0
    storage_per_vehicle_kb: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class IdentitySystemBenchmark:
    """
    Benchmark framework for identity systems.

    Tests both PKI and DID/SSI systems with identical workloads.
    """

    def __init__(self, name: str):
        self.name = name
        self.results = []

    def benchmark_enrollment(self, identity_system, vehicle_id: str,
                           iterations: int = 100) -> List[float]:
        """
        Benchmark vehicle enrollment/registration.

        Args:
            identity_system: Identity system to test
            vehicle_id: Vehicle identifier
            iterations: Number of test iterations

        Returns:
            List of enrollment times in milliseconds
        """
        times = []

        for i in range(iterations):
            start = time.time()

            # Perform enrollment
            if hasattr(identity_system, 'enroll_vehicle'):
                identity_system.enroll_vehicle(f"{vehicle_id}_{i}")
            elif hasattr(identity_system, 'request_enrollment_certificate'):
                identity_system.request_enrollment_certificate(None)

            elapsed = (time.time() - start) * 1000
            times.append(elapsed)

        return times

    def benchmark_credential_request(self, identity_system,
                                    iterations: int = 100) -> List[float]:
        """
        Benchmark credential/certificate request.

        For PKI: pseudonym certificate request
        For DID: verifiable credential issuance
        """
        times = []

        for i in range(iterations):
            start = time.time()

            if hasattr(identity_system, 'request_pseudonym_certificates'):
                identity_system.request_pseudonym_certificates(None, count=20)
            elif hasattr(identity_system, 'request_credential'):
                identity_system.request_credential()

            elapsed = (time.time() - start) * 1000
            times.append(elapsed)

        return times

    def benchmark_message_signing(self, identity_system, message: dict,
                                  iterations: int = 1000) -> List[float]:
        """
        Benchmark message signing performance.

        Critical metric as BSMs are sent at 10 Hz.
        """
        times = []

        for i in range(iterations):
            start = time.time()

            if hasattr(identity_system, 'sign_message'):
                identity_system.sign_message(message)
            else:
                raise ValueError("Identity system must implement sign_message()")

            elapsed = (time.time() - start) * 1000
            times.append(elapsed)

        return times

    def benchmark_verification(self, identity_system, signed_message: dict,
                              crl_or_registry, iterations: int = 1000) -> List[float]:
        """
        Benchmark message verification performance.

        Critical metric as vehicles receive many BSMs per second.
        """
        times = []

        for i in range(iterations):
            start = time.time()

            if hasattr(identity_system, 'verify_message'):
                identity_system.verify_message(signed_message, crl_or_registry)
            else:
                raise ValueError("Identity system must implement verify_message()")

            elapsed = (time.time() - start) * 1000
            times.append(elapsed)

        return times

    def measure_sizes(self, identity_system, signed_message: dict) -> Dict[str, int]:
        """
        Measure credential and signature sizes.

        Important for bandwidth efficiency in V2X.
        """
        sizes = {}

        # Credential size
        if hasattr(identity_system, 'get_credential_size'):
            sizes['credential'] = identity_system.get_credential_size()
        elif 'certificate' in signed_message:
            sizes['credential'] = len(signed_message['certificate'].encode())

        # Signature size
        if 'signature' in signed_message:
            sizes['signature'] = len(signed_message['signature'])

        # Full signed message size
        sizes['signed_message'] = len(json.dumps(signed_message).encode())

        # Overhead (signature + credential)
        base_message_size = len(json.dumps(signed_message.get('message', {})).encode())
        sizes['overhead'] = sizes['signed_message'] - base_message_size

        return sizes

    def run_full_benchmark(self, identity_system, system_type: str) -> IdentityMetrics:
        """
        Run complete benchmark suite.

        Args:
            identity_system: Identity system instance to test
            system_type: "PKI" or "DID"

        Returns:
            IdentityMetrics with all measured values
        """
        print(f"\n{'='*60}")
        print(f"BENCHMARKING: {system_type} Identity System")
        print(f"{'='*60}\n")

        metrics = IdentityMetrics()

        # Test message (BSM)
        test_message = {
            'msgID': 'BasicSafetyMessage',
            'timestamp': datetime.utcnow().isoformat(),
            'position': {'lat': 49.2827, 'lon': -123.1207},
            'speed': 50,
            'heading': 90
        }

        # 1. Enrollment benchmark
        print("1. Testing enrollment...")
        try:
            enrollment_times = self.benchmark_enrollment(
                identity_system, "TEST_VEHICLE", iterations=50
            )
            metrics.enrollment_time_ms = statistics.mean(enrollment_times)
            print(f"   Mean enrollment time: {metrics.enrollment_time_ms:.2f} ms")
        except Exception as e:
            print(f"   Error: {e}")

        # 2. Credential request benchmark
        print("2. Testing credential request...")
        try:
            cred_times = self.benchmark_credential_request(
                identity_system, iterations=50
            )
            metrics.credential_request_time_ms = statistics.mean(cred_times)
            print(f"   Mean credential request time: {metrics.credential_request_time_ms:.2f} ms")
        except Exception as e:
            print(f"   Error: {e}")

        # 3. Message signing benchmark
        print("3. Testing message signing (1000 iterations)...")
        try:
            signing_times = self.benchmark_message_signing(
                identity_system, test_message, iterations=1000
            )
            metrics.signing_time_ms = statistics.mean(signing_times)
            print(f"   Mean signing time: {metrics.signing_time_ms:.3f} ms")
            print(f"   Median: {statistics.median(signing_times):.3f} ms")
            print(f"   95th percentile: {statistics.quantiles(signing_times, n=20)[18]:.3f} ms")
        except Exception as e:
            print(f"   Error: {e}")

        # 4. Get signed message for verification test
        signed_message = None
        try:
            if hasattr(identity_system, 'sign_message'):
                signed_message = identity_system.sign_message(test_message)
        except:
            pass

        # 5. Message verification benchmark
        if signed_message:
            print("4. Testing message verification (1000 iterations)...")
            try:
                # Create empty CRL/registry for testing
                crl = set()

                verification_times = self.benchmark_verification(
                    identity_system, signed_message, crl, iterations=1000
                )

                # Filter out failed verifications (if any returned None)
                verification_times = [t for t in verification_times if t is not None]

                if verification_times:
                    metrics.verification_time_ms = statistics.mean(verification_times)
                    print(f"   Mean verification time: {metrics.verification_time_ms:.3f} ms")
                    print(f"   Median: {statistics.median(verification_times):.3f} ms")
                    print(f"   95th percentile: {statistics.quantiles(verification_times, n=20)[18]:.3f} ms")
            except Exception as e:
                print(f"   Error: {e}")

        # 6. Size measurements
        if signed_message:
            print("5. Measuring sizes...")
            try:
                sizes = self.measure_sizes(identity_system, signed_message)
                metrics.credential_size = sizes.get('credential', 0)
                metrics.signature_size = sizes.get('signature', 0)
                metrics.signed_message_size = sizes.get('signed_message', 0)

                print(f"   Credential size: {metrics.credential_size} bytes")
                print(f"   Signature size: {metrics.signature_size} bytes")
                print(f"   Total overhead: {sizes.get('overhead', 0)} bytes")
            except Exception as e:
                print(f"   Error: {e}")

        # 7. Qualitative metrics
        if system_type == "PKI":
            metrics.privacy_level = "medium"  # Pseudonym certificates
            metrics.decentralization = "centralized"  # CA-based
            metrics.scalability = "good"
            metrics.revocation_mechanism = "CRL"
        elif system_type == "DID":
            metrics.privacy_level = "high"  # Self-sovereign
            metrics.decentralization = "decentralized"  # Blockchain-based
            metrics.scalability = "moderate"  # Blockchain queries
            metrics.revocation_mechanism = "blockchain_registry"

        print(f"\n{'='*60}\n")

        return metrics


class ComparisonReport:
    """Generate comparison report between identity systems."""

    def __init__(self):
        self.systems = {}

    def add_system(self, name: str, metrics: IdentityMetrics):
        """Add identity system results."""
        self.systems[name] = metrics

    def generate_report(self) -> str:
        """Generate comparison report."""
        report = []
        report.append("=" * 80)
        report.append("IDENTITY SYSTEM COMPARISON REPORT")
        report.append("=" * 80)
        report.append("")

        if len(self.systems) < 2:
            report.append("Need at least 2 systems to compare.")
            return "\n".join(report)

        # Performance comparison
        report.append("PERFORMANCE METRICS")
        report.append("-" * 80)
        report.append("")

        metrics_to_compare = [
            ('enrollment_time_ms', 'Enrollment Time', 'ms'),
            ('credential_request_time_ms', 'Credential Request Time', 'ms'),
            ('signing_time_ms', 'Message Signing Time', 'ms'),
            ('verification_time_ms', 'Message Verification Time', 'ms'),
        ]

        for metric, label, unit in metrics_to_compare:
            report.append(f"{label}:")
            for name, sys_metrics in self.systems.items():
                value = getattr(sys_metrics, metric)
                report.append(f"  {name:20s}: {value:8.3f} {unit}")

            # Calculate speedup/difference
            if len(self.systems) == 2:
                names = list(self.systems.keys())
                val1 = getattr(self.systems[names[0]], metric)
                val2 = getattr(self.systems[names[1]], metric)
                if val1 > 0 and val2 > 0:
                    ratio = val1 / val2
                    faster = names[0] if ratio > 1 else names[1]
                    report.append(f"  → {faster} is {abs(ratio):.2f}x faster")

            report.append("")

        # Size comparison
        report.append("SIZE METRICS")
        report.append("-" * 80)
        report.append("")

        size_metrics = [
            ('credential_size', 'Credential Size', 'bytes'),
            ('signature_size', 'Signature Size', 'bytes'),
            ('signed_message_size', 'Signed Message Size', 'bytes'),
        ]

        for metric, label, unit in size_metrics:
            report.append(f"{label}:")
            for name, sys_metrics in self.systems.items():
                value = getattr(sys_metrics, metric)
                report.append(f"  {name:20s}: {value:8d} {unit}")
            report.append("")

        # Qualitative comparison
        report.append("QUALITATIVE COMPARISON")
        report.append("-" * 80)
        report.append("")

        qual_metrics = [
            ('privacy_level', 'Privacy Level'),
            ('decentralization', 'Decentralization'),
            ('scalability', 'Scalability'),
            ('revocation_mechanism', 'Revocation Mechanism'),
        ]

        for metric, label in qual_metrics:
            report.append(f"{label}:")
            for name, sys_metrics in self.systems.items():
                value = getattr(sys_metrics, metric)
                report.append(f"  {name:20s}: {value}")
            report.append("")

        # V2X Suitability Analysis
        report.append("V2X SUITABILITY ANALYSIS")
        report.append("-" * 80)
        report.append("")

        for name, sys_metrics in self.systems.items():
            report.append(f"{name}:")

            # Check if signing is fast enough for 10 Hz BSM
            if sys_metrics.signing_time_ms < 10:  # Must be < 100ms for 10 Hz
                report.append(f"  ✓ Signing speed suitable for 10 Hz BSM")
            else:
                report.append(f"  ✗ Signing too slow for real-time BSM")

            # Check verification speed
            # Assume vehicle receives ~10 BSMs/sec from nearby vehicles
            if sys_metrics.verification_time_ms < 5:
                report.append(f"  ✓ Verification speed suitable for dense traffic")
            else:
                report.append(f"  ⚠ Verification may struggle in dense traffic")

            # Check message overhead
            # BSM base size ~200 bytes, overhead should be < 50%
            if sys_metrics.signed_message_size > 0:
                overhead_ratio = (sys_metrics.signed_message_size - 200) / 200
                if overhead_ratio < 0.5:
                    report.append(f"  ✓ Message overhead acceptable ({overhead_ratio*100:.0f}%)")
                else:
                    report.append(f"  ⚠ High message overhead ({overhead_ratio*100:.0f}%)")

            report.append("")

        report.append("=" * 80)

        return "\n".join(report)

    def save_report(self, filename: str):
        """Save report to file."""
        with open(filename, 'w') as f:
            f.write(self.generate_report())

    def save_metrics_json(self, filename: str):
        """Save raw metrics to JSON file."""
        data = {
            name: metrics.to_dict()
            for name, metrics in self.systems.items()
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)


if __name__ == "__main__":
    print("Identity System Comparison Framework")
    print("This module provides tools to compare PKI and DID/SSI identity systems")
    print("for connected vehicle applications.")
