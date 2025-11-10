"""
Basic V2V Communication Scenario

Tests basic vehicle-to-vehicle communication with BSM exchange.
"""

import sys
import time
from datetime import datetime
sys.path.append('..')

from protocols.cv2x_stack import (
    CV2XStack, VehicleState, Position, CommunicationMode
)
from identity.standard.pki_identity import VehiclePKIIdentity, VehiclePKI_CA


def run_basic_v2v_scenario(use_identity: bool = True,
                           num_vehicles: int = 2,
                           simulation_time: int = 10):
    """
    Run basic V2V scenario with multiple vehicles exchanging BSMs.

    Args:
        use_identity: Whether to use PKI identity system
        num_vehicles: Number of vehicles in simulation
        simulation_time: Duration in seconds
    """
    print("=" * 60)
    print("BASIC V2V COMMUNICATION SCENARIO")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  - Vehicles: {num_vehicles}")
    print(f"  - Identity System: {'PKI' if use_identity else 'None'}")
    print(f"  - Simulation Time: {simulation_time}s")
    print(f"  - BSM Frequency: 10 Hz")
    print("=" * 60)
    print()

    # Initialize PKI CA if using identity
    ca = None
    if use_identity:
        print("Initializing PKI Certificate Authority...")
        ca = VehiclePKI_CA("CVIN-Testbed-CA")
        print(f"✓ CA initialized: {ca.name}\n")

    # Create vehicles
    vehicles = []
    stacks = []

    for i in range(num_vehicles):
        vehicle_id = f"V{i+1:03d}"

        # Create vehicle state (evenly spaced along a road)
        state = VehicleState(
            vehicle_id=vehicle_id,
            timestamp=datetime.utcnow().isoformat(),
            position=Position(
                latitude=49.2827 + (i * 0.001),  # ~111m spacing
                longitude=-123.1207,
                elevation=50.0
            ),
            speed=15.0 + (i * 2.0),  # Varying speeds
            heading=90.0,
            acceleration=0.0
        )

        # Create identity if enabled
        identity_mgr = None
        if use_identity:
            print(f"Setting up identity for {vehicle_id}...")
            identity_mgr = VehiclePKIIdentity(vehicle_id)
            identity_mgr.generate_keypair()
            identity_mgr.request_enrollment_certificate(ca)
            identity_mgr.request_pseudonym_certificates(ca, count=20)
            print(f"  ✓ Identity configured with 20 pseudonym certificates")

        # Create CV2X stack
        stack = CV2XStack(
            vehicle_id,
            identity_manager=identity_mgr,
            mode=CommunicationMode.MODE_4
        )

        vehicles.append(state)
        stacks.append(stack)

    print(f"\n✓ {num_vehicles} vehicles initialized\n")

    # Simulation loop
    print("Starting simulation...")
    print("-" * 60)

    bsm_interval = 0.1  # 10 Hz
    start_time = time.time()
    iteration = 0

    # Metrics collection
    all_metrics = {
        'total_transmissions': 0,
        'successful_receptions': 0,
        'failed_receptions': 0,
        'latencies': [],
        'distances': [],
        'verification_times': []
    }

    while time.time() - start_time < simulation_time:
        iteration += 1

        # Update vehicle positions (simple constant velocity model)
        for i, vehicle in enumerate(vehicles):
            # Update position based on speed and heading
            distance_moved = vehicle.speed * bsm_interval
            # Simplified: assume heading 90° = eastward movement
            vehicle.position.longitude += (distance_moved / 111000.0)
            vehicle.timestamp = datetime.utcnow().isoformat()

        # Each vehicle transmits BSM
        transmissions = []
        for i, (vehicle, stack) in enumerate(zip(vehicles, stacks)):
            tx_info = stack.send_bsm(vehicle)
            if tx_info:
                transmissions.append((i, vehicle, tx_info))
                all_metrics['total_transmissions'] += 1

        # Each vehicle tries to receive BSMs from others
        for rx_idx, (rx_vehicle, rx_stack) in enumerate(zip(vehicles, stacks)):
            for tx_idx, tx_vehicle, tx_info in transmissions:
                if rx_idx == tx_idx:
                    continue  # Don't receive own message

                success, rx_info = rx_stack.receive_message(
                    tx_info,
                    rx_vehicle.position,
                    tx_vehicle.position,
                    ca.get_crl() if ca else set()
                )

                if success:
                    all_metrics['successful_receptions'] += 1
                    all_metrics['latencies'].append(rx_info['latency_ms'])
                    all_metrics['distances'].append(rx_info['distance'])

                    if 'verification_time_ms' in rx_info:
                        all_metrics['verification_times'].append(
                            rx_info['verification_time_ms']
                        )

                    # Print occasional messages
                    if iteration % 10 == 0 and rx_idx == 0 and tx_idx == 1:
                        print(f"[{time.time()-start_time:.1f}s] "
                              f"{rx_vehicle.vehicle_id} ← {tx_vehicle.vehicle_id}: "
                              f"d={rx_info['distance']:.0f}m, "
                              f"lat={rx_info['latency_ms']:.2f}ms")
                else:
                    all_metrics['failed_receptions'] += 1

        # Sleep until next BSM interval
        time.sleep(bsm_interval)

    print("-" * 60)
    print("Simulation complete\n")

    # Print final statistics
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    # Communication metrics
    print("\nCommunication Metrics:")
    print(f"  Total Transmissions: {all_metrics['total_transmissions']}")
    print(f"  Successful Receptions: {all_metrics['successful_receptions']}")
    print(f"  Failed Receptions: {all_metrics['failed_receptions']}")

    if all_metrics['successful_receptions'] > 0:
        pdr = (all_metrics['successful_receptions'] /
               (all_metrics['successful_receptions'] + all_metrics['failed_receptions'])) * 100
        print(f"  Packet Delivery Ratio: {pdr:.2f}%")

    # Latency metrics
    if all_metrics['latencies']:
        import statistics
        print(f"\nLatency Statistics:")
        print(f"  Mean: {statistics.mean(all_metrics['latencies']):.2f} ms")
        print(f"  Median: {statistics.median(all_metrics['latencies']):.2f} ms")
        print(f"  Min: {min(all_metrics['latencies']):.2f} ms")
        print(f"  Max: {max(all_metrics['latencies']):.2f} ms")

    # Distance metrics
    if all_metrics['distances']:
        print(f"\nCommunication Distance:")
        print(f"  Mean: {statistics.mean(all_metrics['distances']):.0f} m")
        print(f"  Max: {max(all_metrics['distances']):.0f} m")

    # Identity verification metrics
    if all_metrics['verification_times']:
        print(f"\nIdentity Verification (PKI):")
        print(f"  Mean Time: {statistics.mean(all_metrics['verification_times']):.2f} ms")
        print(f"  Median Time: {statistics.median(all_metrics['verification_times']):.2f} ms")
        print(f"  Overhead: {(statistics.mean(all_metrics['verification_times']) /
                              statistics.mean(all_metrics['latencies']) * 100):.1f}% of total latency")

    # Per-vehicle statistics
    print(f"\nPer-Vehicle Statistics:")
    for stack in stacks:
        stats = stack.get_statistics()
        print(f"\n  {stack.vehicle_id}:")
        print(f"    Messages Sent: {stats['messages_sent']}")
        print(f"    Messages Received: {stats['messages_received']}")
        if use_identity:
            print(f"    Messages Verified: {stats['messages_verified']}")
            print(f"    Verification Failures: {stats['verification_failures']}")

    print("\n" + "=" * 60)

    return all_metrics


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run basic V2V communication scenario"
    )
    parser.add_argument(
        "--vehicles",
        type=int,
        default=2,
        help="Number of vehicles (default: 2)"
    )
    parser.add_argument(
        "--time",
        type=int,
        default=10,
        help="Simulation time in seconds (default: 10)"
    )
    parser.add_argument(
        "--no-identity",
        action="store_true",
        help="Disable PKI identity system"
    )

    args = parser.parse_args()

    run_basic_v2v_scenario(
        use_identity=not args.no_identity,
        num_vehicles=args.vehicles,
        simulation_time=args.time
    )
