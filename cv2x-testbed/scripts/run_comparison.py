#!/usr/bin/env python3
"""
Run comparison between PKI and DID identity systems.

This script benchmarks both standard PKI and DID/SSI identity systems
and generates a comprehensive comparison report.
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from identity.standard.pki_identity import VehiclePKIIdentity, VehiclePKI_CA
from identity.comparison_framework import (
    IdentitySystemBenchmark,
    ComparisonReport,
    IdentityMetrics
)


def run_pki_benchmark():
    """Run benchmark for PKI identity system."""
    print("\nInitializing PKI system...")

    # Create CA
    ca = VehiclePKI_CA("Benchmark-CA")

    # Create vehicle identity
    vehicle = VehiclePKIIdentity("BENCHMARK_V001")
    vehicle.generate_keypair()
    vehicle.request_enrollment_certificate(ca)
    vehicle.request_pseudonym_certificates(ca, count=20)

    # Run benchmark
    benchmark = IdentitySystemBenchmark("PKI-Benchmark")
    metrics = benchmark.run_full_benchmark(vehicle, "PKI")

    return metrics


def run_did_benchmark():
    """
    Run benchmark for DID identity system.

    NOTE: This is a placeholder. Actual DID implementation will be
    integrated from the CVIN-ID-SCs repository.
    """
    print("\nDID/SSI benchmark not yet implemented.")
    print("This will be integrated with the DID implementations from CVIN-ID-SCs/")
    print("")

    # Return placeholder metrics
    metrics = IdentityMetrics()
    metrics.enrollment_time_ms = 0.0
    metrics.credential_request_time_ms = 0.0
    metrics.signing_time_ms = 0.0
    metrics.verification_time_ms = 0.0
    metrics.privacy_level = "high"
    metrics.decentralization = "decentralized"
    metrics.scalability = "moderate"
    metrics.revocation_mechanism = "blockchain_registry"

    return metrics


def main():
    """Main comparison function."""
    print("=" * 80)
    print("CV2X IDENTITY SYSTEM COMPARISON")
    print("=" * 80)
    print("")
    print("This benchmark compares standard PKI-based identity with")
    print("blockchain-based DID/SSI for connected vehicle applications.")
    print("")

    # Run PKI benchmark
    print("\n" + "=" * 80)
    print("PHASE 1: PKI BENCHMARK")
    print("=" * 80)
    pki_metrics = run_pki_benchmark()

    # Run DID benchmark (placeholder)
    print("\n" + "=" * 80)
    print("PHASE 2: DID/SSI BENCHMARK")
    print("=" * 80)
    did_metrics = run_did_benchmark()

    # Generate comparison report
    print("\n" + "=" * 80)
    print("GENERATING COMPARISON REPORT")
    print("=" * 80)

    report = ComparisonReport()
    report.add_system("Standard PKI", pki_metrics)
    # report.add_system("DID/SSI", did_metrics)  # Uncomment when implemented

    # Print report
    print("\n" + report.generate_report())

    # Save reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = "reports"

    if not os.path.exists(report_dir):
        os.makedirs(report_dir)

    txt_file = os.path.join(report_dir, f"comparison_{timestamp}.txt")
    json_file = os.path.join(report_dir, f"metrics_{timestamp}.json")

    report.save_report(txt_file)
    report.save_metrics_json(json_file)

    print(f"\nReports saved:")
    print(f"  - {txt_file}")
    print(f"  - {json_file}")
    print("")


if __name__ == "__main__":
    main()
