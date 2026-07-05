#!/usr/bin/env python3
"""
Identity System Comparison Test

Compares centralized PKI with ERC-1056 DID for V2X applications.

This script:
1. Initializes both identity providers
2. Registers test vehicles
3. Performs signing/verification benchmarks
4. Generates comparison report
"""

import sys
import os
import json
import time

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from identity.base import IdentityManager, IdentityBenchmark
from identity.centralized_provider import CentralizedIdentityProvider
from identity.erc1056_provider import ERC1056Provider


def load_contract_address():
    """Load deployed contract address from deployment file"""
    deployment_file = os.path.join(
        os.path.dirname(__file__),
        '..',
        'deployments',
        'localhost.json'
    )

    if not os.path.exists(deployment_file):
        print("❌ Contract not deployed. Please run:")
        print("   ./scripts/start_testbed.sh")
        print("   or")
        print("   npx hardhat run scripts/deploy.js --network localhost")
        return None

    with open(deployment_file, 'r') as f:
        deployment = json.load(f)

    return deployment['contractAddress']


def main():
    print("=" * 80)
    print("CV2X TESTBED - IDENTITY SYSTEM COMPARISON")
    print("=" * 80)
    print("")
    print("Comparing: Centralized PKI vs ERC-1056 DID")
    print("")

    # Initialize Identity Manager
    manager = IdentityManager()

    # 1. Register Centralized PKI Provider
    print("1. Initializing Centralized PKI Provider...")
    pki_provider = CentralizedIdentityProvider("CVIN-Research-CA")
    manager.register_provider(pki_provider)
    print(f"   ✓ {pki_provider.get_display_name()} initialized")

    # 2. Register ERC-1056 DID Provider
    print("\n2. Initializing ERC-1056 DID Provider...")

    contract_address = load_contract_address()

    if contract_address:
        try:
            did_provider = ERC1056Provider(
                web3_provider_url="http://127.0.0.1:8545",
                contract_address=contract_address
            )
            manager.register_provider(did_provider)
            print(f"   ✓ {did_provider.get_display_name()} initialized")
            print(f"   ✓ Contract: {contract_address}")
            print(f"   ✓ Chain ID: {did_provider.w3.eth.chain_id}")

            has_did = True

        except Exception as e:
            print(f"   ✗ Failed to initialize DID provider: {e}")
            print(f"   ⚠ Continuing with PKI only...")
            has_did = False
    else:
        print("   ⚠ Skipping DID provider (contract not deployed)")
        has_did = False

    # 3. Run Benchmarks
    print("\n" + "=" * 80)
    print("RUNNING BENCHMARKS")
    print("=" * 80)

    benchmark = IdentityBenchmark(manager)

    # Registration benchmark
    registration_results = benchmark.benchmark_registration(num_vehicles=10)

    # Signing benchmark
    signing_results = benchmark.benchmark_signing(num_messages=100)

    # Verification benchmark
    verification_results = benchmark.benchmark_verification(num_verifications=100)

    # 4. Detailed Comparison
    print("\n" + "=" * 80)
    print("DETAILED COMPARISON")
    print("=" * 80)

    print("\n📊 REGISTRATION")
    print("-" * 80)
    print(f"{'Metric':<30} {'PKI':>20} {'DID':>20}")
    print("-" * 80)

    pki_reg = registration_results.get(pki_provider.get_type(), {})

    if has_did and did_provider.get_type() in registration_results:
        did_reg = registration_results[did_provider.get_type()]

        print(f"{'Mean Time (ms)':<30} {pki_reg.get('mean_ms', 0):>19.2f} {did_reg.get('mean_ms', 0):>20.2f}")
        print(f"{'Median Time (ms)':<30} {pki_reg.get('median_ms', 0):>19.2f} {did_reg.get('median_ms', 0):>20.2f}")
        print(f"{'Total Cost ($)':<30} {pki_reg.get('total_cost', 0):>19.4f} {did_reg.get('total_cost', 0):>20.8f}")

        # Winner
        if pki_reg.get('mean_ms', 0) < did_reg.get('mean_ms', 0):
            print(f"\n⚡ Faster: PKI ({pki_reg['mean_ms'] / did_reg['mean_ms']:.1f}x)")
        else:
            print(f"\n⚡ Faster: DID ({did_reg['mean_ms'] / pki_reg['mean_ms']:.1f}x)")

    else:
        print(f"{'Mean Time (ms)':<30} {pki_reg.get('mean_ms', 0):>19.2f} {'N/A':>20}")
        print(f"{'Total Cost ($)':<30} {pki_reg.get('total_cost', 0):>19.4f} {'N/A':>20}")

    print("\n📝 SIGNING")
    print("-" * 80)
    print(f"{'Metric':<30} {'PKI':>20} {'DID':>20}")
    print("-" * 80)

    pki_sign = signing_results.get(pki_provider.get_type(), {})

    if has_did and did_provider.get_type() in signing_results:
        did_sign = signing_results[did_provider.get_type()]

        print(f"{'Mean Time (ms)':<30} {pki_sign.get('mean_ms', 0):>19.3f} {did_sign.get('mean_ms', 0):>20.3f}")
        print(f"{'95th Percentile (ms)':<30} {pki_sign.get('p95_ms', 0):>19.3f} {did_sign.get('p95_ms', 0):>20.3f}")
        print(f"{'Mean Size (bytes)':<30} {pki_sign.get('mean_size_bytes', 0):>19.0f} {did_sign.get('mean_size_bytes', 0):>20.0f}")
        print(f"{'Overhead (bytes)':<30} {pki_sign.get('overhead_bytes', 0):>19.0f} {did_sign.get('overhead_bytes', 0):>20.0f}")

        # Check V2X suitability (< 10ms for 10 Hz BSM)
        print("\n🚗 V2X Suitability (< 10ms for 10 Hz BSM):")
        pki_suitable = pki_sign.get('p95_ms', 0) < 10
        did_suitable = did_sign.get('p95_ms', 0) < 10

        print(f"   PKI: {'✅ Suitable' if pki_suitable else '❌ Too Slow'}")
        print(f"   DID: {'✅ Suitable' if did_suitable else '❌ Too Slow'}")

    else:
        print(f"{'Mean Time (ms)':<30} {pki_sign.get('mean_ms', 0):>19.3f} {'N/A':>20}")
        print(f"{'Overhead (bytes)':<30} {pki_sign.get('overhead_bytes', 0):>19.0f} {'N/A':>20}")

    print("\n✅ VERIFICATION")
    print("-" * 80)
    print(f"{'Metric':<30} {'PKI':>20} {'DID':>20}")
    print("-" * 80)

    pki_ver = verification_results.get(pki_provider.get_type(), {})

    if has_did and did_provider.get_type() in verification_results:
        did_ver = verification_results[did_provider.get_type()]

        print(f"{'Mean Time (ms)':<30} {pki_ver.get('mean_ms', 0):>19.3f} {did_ver.get('mean_ms', 0):>20.3f}")
        print(f"{'95th Percentile (ms)':<30} {pki_ver.get('p95_ms', 0):>19.3f} {did_ver.get('p95_ms', 0):>20.3f}")
        print(f"{'Success Rate (%)':<30} {pki_ver.get('success_rate', 0)*100:>19.1f} {did_ver.get('success_rate', 0)*100:>20.1f}")

        # Check V2X suitability (< 5ms for dense traffic)
        print("\n🚗 V2X Suitability (< 5ms for dense traffic):")
        pki_suitable = pki_ver.get('p95_ms', 0) < 5
        did_suitable = did_ver.get('p95_ms', 0) < 5

        print(f"   PKI: {'✅ Suitable' if pki_suitable else '⚠ May struggle in dense traffic'}")
        print(f"   DID: {'✅ Suitable' if did_suitable else '⚠ May struggle in dense traffic'}")

    else:
        print(f"{'Mean Time (ms)':<30} {pki_ver.get('mean_ms', 0):>19.3f} {'N/A':>20}")

    # 5. Qualitative Comparison
    print("\n" + "=" * 80)
    print("QUALITATIVE COMPARISON")
    print("=" * 80)

    comparison_table = [
        ("Architecture", "Centralized CA", "Decentralized Blockchain"),
        ("Trust Model", "CA-based", "Cryptographic"),
        ("Single Point of Failure", "Yes", "No"),
        ("Privacy", "Pseudonyms", "Native DID"),
        ("Revocation", "CRL/OCSP", "On-chain Registry"),
        ("Scalability", "High (local)", "Moderate (blockchain)"),
        ("Setup Cost", "Medium", "High (deployment)"),
        ("Per-Operation Cost", "Low", "Gas fees"),
        ("Censorship Resistance", "No", "Yes"),
        ("Regulatory Compliance", "Easier", "Complex"),
    ]

    print(f"\n{'Feature':<30} {'PKI':>20} {'DID':>20}")
    print("-" * 80)
    for feature, pki_val, did_val in comparison_table:
        print(f"{feature:<30} {pki_val:>20} {did_val:>20}")

    # 6. Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    print("\n✅ Use Centralized PKI when:")
    print("   • Lowest latency is critical")
    print("   • Predictable costs required")
    print("   • Regulatory compliance is important")
    print("   • Centralized authority is acceptable")

    if has_did:
        print("\n✅ Use ERC-1056 DID when:")
        print("   • Decentralization is required")
        print("   • Censorship resistance needed")
        print("   • Self-sovereign identity desired")
        print("   • Can tolerate blockchain costs/latency")

        print("\n✅ Hybrid Approach:")
        print("   • PKI for real-time V2X messages")
        print("   • DID for vehicle registration/identity")
        print("   • Periodic DID anchoring of PKI certificates")

    # 7. Save Results
    results = {
        'timestamp': time.time(),
        'registration': registration_results,
        'signing': signing_results,
        'verification': verification_results,
    }

    output_file = os.path.join(
        os.path.dirname(__file__),
        '..',
        'results',
        f'comparison_{int(time.time())}.json'
    )

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n💾 Results saved to: {output_file}")

    print("\n" + "=" * 80)
    print("COMPARISON COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
