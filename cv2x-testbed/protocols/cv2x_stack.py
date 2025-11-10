"""
CV2X Protocol Stack Implementation

Implements a simplified CV2X (Cellular Vehicle-to-Everything) protocol stack
for testbed simulation and research purposes.
"""

import time
import json
import random
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class MessageType(Enum):
    """V2X Message Types"""
    BSM = "BasicSafetyMessage"           # Basic Safety Message (SAE J2735)
    CAM = "CooperativeAwarenessMessage"  # Cooperative Awareness Message (ETSI)
    DENM = "DENM"                        # Decentralized Environmental Notification
    CPM = "CollectivePerceptionMessage"  # Collective Perception Message
    MCM = "ManueverCoordinationMessage"  # Maneuver Coordination


class CommunicationMode(Enum):
    """CV2X Communication Modes"""
    MODE_3 = "network_assisted"  # Network-assisted resource allocation
    MODE_4 = "autonomous"        # Autonomous resource selection


@dataclass
class Position:
    """Geographic position"""
    latitude: float
    longitude: float
    elevation: float = 0.0


@dataclass
class VehicleState:
    """Complete vehicle state information"""
    vehicle_id: str
    timestamp: str
    position: Position
    speed: float          # m/s
    heading: float        # degrees (0-360)
    acceleration: float   # m/s²
    vehicle_length: float = 4.5  # meters
    vehicle_width: float = 1.8   # meters


@dataclass
class BSM:
    """
    Basic Safety Message (BSM) / Cooperative Awareness Message (CAM)

    Transmitted periodically (typically 10 Hz) to announce vehicle presence
    and current state.
    """
    msg_type: str = "BasicSafetyMessage"
    msg_id: int = 0
    timestamp: str = ""
    vehicle_id: str = ""
    position: Dict = None
    speed: float = 0.0
    heading: float = 0.0
    acceleration: float = 0.0
    vehicle_size: Dict = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_bytes(self) -> bytes:
        """Serialize BSM to bytes for transmission"""
        return json.dumps(self.to_dict()).encode('utf-8')

    @classmethod
    def from_vehicle_state(cls, state: VehicleState, msg_id: int = 0):
        """Create BSM from vehicle state"""
        return cls(
            msg_id=msg_id,
            timestamp=state.timestamp,
            vehicle_id=state.vehicle_id,
            position={
                'latitude': state.position.latitude,
                'longitude': state.position.longitude,
                'elevation': state.position.elevation
            },
            speed=state.speed,
            heading=state.heading,
            acceleration=state.acceleration,
            vehicle_size={
                'length': state.vehicle_length,
                'width': state.vehicle_width
            }
        )


@dataclass
class DENM:
    """
    Decentralized Environmental Notification Message

    Event-triggered message for hazard warnings.
    """
    msg_type: str = "DENM"
    msg_id: int = 0
    timestamp: str = ""
    event_type: str = ""
    position: Dict = None
    severity: str = "medium"  # critical, high, medium, low
    relevance_distance: float = 300.0  # meters
    relevance_duration: float = 60.0   # seconds
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_dict()).encode('utf-8')


class ResourcePool:
    """
    Physical Resource Block (PRB) pool for CV2X Mode 4

    Manages resource allocation for autonomous V2V communication.
    """

    def __init__(self, num_prbs: int = 50, num_subchannels: int = 4):
        self.num_prbs = num_prbs
        self.num_subchannels = num_subchannels
        self.resources = {}  # {(prb, subchannel): occupancy_info}
        self.cbr = 0.0  # Channel Busy Ratio
        self._initialize_resources()

    def _initialize_resources(self):
        """Initialize resource grid"""
        for prb in range(self.num_prbs):
            for subchannel in range(self.num_subchannels):
                self.resources[(prb, subchannel)] = {
                    'occupied': False,
                    'rssi': -100,  # dBm
                    'last_update': time.time()
                }

    def sense_resources(self) -> List[Tuple[int, int]]:
        """
        Sensing-Based Semi-Persistent Scheduling (SB-SPS)

        Returns list of available resources with low interference.
        """
        available = []
        current_time = time.time()

        for (prb, subchannel), info in self.resources.items():
            # Resource is available if:
            # 1. Not currently occupied
            # 2. RSSI below threshold (low interference)
            # 3. Not reserved recently
            if (not info['occupied'] and
                info['rssi'] < -90 and
                current_time - info['last_update'] > 0.1):
                available.append((prb, subchannel))

        return available

    def allocate_resource(self, vehicle_id: str) -> Optional[Tuple[int, int]]:
        """
        Allocate resource for transmission

        Returns (prb, subchannel) tuple or None if no resources available
        """
        available = self.sense_resources()

        if not available:
            return None

        # Randomly select from available resources (simplified)
        # In real implementation, this would use sophisticated selection criteria
        resource = random.choice(available)
        prb, subchannel = resource

        self.resources[resource]['occupied'] = True
        self.resources[resource]['vehicle_id'] = vehicle_id
        self.resources[resource]['last_update'] = time.time()

        return resource

    def release_resource(self, resource: Tuple[int, int]):
        """Release allocated resource"""
        if resource in self.resources:
            self.resources[resource]['occupied'] = False
            self.resources[resource]['last_update'] = time.time()

    def update_cbr(self):
        """Update Channel Busy Ratio"""
        occupied = sum(1 for r in self.resources.values() if r['occupied'])
        total = len(self.resources)
        self.cbr = occupied / total if total > 0 else 0.0


class MACLayer:
    """
    CV2X MAC Layer

    Handles resource allocation and channel access.
    """

    def __init__(self, mode: CommunicationMode = CommunicationMode.MODE_4):
        self.mode = mode
        self.resource_pool = ResourcePool()
        self.transmission_queue = []
        self.tx_power = 23  # dBm (typical for CV2X)

    def allocate_resources(self, vehicle_id: str) -> Optional[dict]:
        """
        Allocate transmission resources

        Returns resource allocation information or None
        """
        if self.mode == CommunicationMode.MODE_4:
            # Autonomous resource selection
            resource = self.resource_pool.allocate_resource(vehicle_id)

            if resource:
                return {
                    'prb': resource[0],
                    'subchannel': resource[1],
                    'tx_power': self.tx_power,
                    'mode': 'autonomous'
                }
        else:
            # Mode 3: Network-assisted (simplified)
            # In real implementation, this would communicate with eNodeB
            prb = random.randint(0, 49)
            subchannel = random.randint(0, 3)

            return {
                'prb': prb,
                'subchannel': subchannel,
                'tx_power': self.tx_power,
                'mode': 'network_assisted'
            }

        return None

    def get_cbr(self) -> float:
        """Get current Channel Busy Ratio"""
        self.resource_pool.update_cbr()
        return self.resource_pool.cbr


class PHYLayer:
    """
    CV2X Physical Layer

    Handles actual transmission and reception with channel modeling.
    """

    def __init__(self):
        self.transmission_range = 300  # meters (typical for CV2X)
        self.path_loss_exponent = 2.0
        self.noise_floor = -110  # dBm

    def calculate_path_loss(self, distance: float, frequency: float = 5.9e9) -> float:
        """
        Calculate path loss using simplified model

        Args:
            distance: Distance in meters
            frequency: Carrier frequency in Hz (default 5.9 GHz for ITS-G5)

        Returns:
            Path loss in dB
        """
        if distance < 1:
            distance = 1

        # Free space path loss
        fspl = 20 * np.log10(distance) + 20 * np.log10(frequency) - 147.55

        # Add additional losses
        shadow_fading = random.gauss(0, 3)  # Log-normal shadowing

        return fspl + shadow_fading

    def transmit(self, message: bytes, tx_power: float, resource: dict) -> dict:
        """
        Transmit message over physical channel

        Args:
            message: Message bytes
            tx_power: Transmission power in dBm
            resource: Resource allocation info

        Returns:
            Transmission info dictionary
        """
        tx_time = time.time()

        return {
            'message': message,
            'tx_power': tx_power,
            'tx_time': tx_time,
            'resource': resource,
            'size_bytes': len(message)
        }

    def receive(self, tx_info: dict, rx_position: Position,
                tx_position: Position) -> Tuple[Optional[bytes], dict]:
        """
        Receive and decode message

        Args:
            tx_info: Transmission information
            rx_position: Receiver position
            tx_position: Transmitter position

        Returns:
            Tuple of (message_bytes, reception_info)
        """
        # Calculate distance
        distance = self._calculate_distance(tx_position, rx_position)

        # Check if in range
        if distance > self.transmission_range:
            return None, {'error': 'out_of_range', 'distance': distance}

        # Calculate received power
        path_loss = self.calculate_path_loss(distance)
        rx_power = tx_info['tx_power'] - path_loss

        # Check if above noise floor
        if rx_power < self.noise_floor:
            return None, {'error': 'below_noise_floor', 'rx_power': rx_power}

        # Calculate reception metrics
        rx_time = time.time()
        latency = (rx_time - tx_info['tx_time']) * 1000  # ms

        reception_info = {
            'distance': distance,
            'rx_power': rx_power,
            'latency_ms': latency,
            'success': True
        }

        return tx_info['message'], reception_info

    def _calculate_distance(self, pos1: Position, pos2: Position) -> float:
        """Calculate Euclidean distance between two positions (simplified)"""
        # Simplified 2D distance (for full implementation, use Haversine formula)
        lat_diff = (pos1.latitude - pos2.latitude) * 111000  # roughly meters
        lon_diff = (pos1.longitude - pos2.longitude) * 111000 * \
                   np.cos(np.radians(pos1.latitude))

        return np.sqrt(lat_diff**2 + lon_diff**2)


class CV2XStack:
    """
    Complete CV2X Protocol Stack

    Integrates PHY, MAC, and Application layers with identity management.
    """

    def __init__(self, vehicle_id: str, identity_manager=None,
                 mode: CommunicationMode = CommunicationMode.MODE_4):
        self.vehicle_id = vehicle_id
        self.identity_manager = identity_manager
        self.mode = mode

        # Layer initialization
        self.phy_layer = PHYLayer()
        self.mac_layer = MACLayer(mode)

        # Message counters
        self.bsm_counter = 0
        self.denm_counter = 0

        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'messages_verified': 0,
            'verification_failures': 0,
            'total_latency': 0.0
        }

    def send_bsm(self, vehicle_state: VehicleState) -> Optional[dict]:
        """
        Send Basic Safety Message

        Args:
            vehicle_state: Current vehicle state

        Returns:
            Transmission info or None if failed
        """
        # Create BSM
        bsm = BSM.from_vehicle_state(vehicle_state, self.bsm_counter)
        self.bsm_counter += 1

        # Sign message if identity manager available
        message_dict = bsm.to_dict()

        if self.identity_manager:
            signed_message = self.identity_manager.sign_message(message_dict)
            message_bytes = json.dumps(signed_message).encode('utf-8')
        else:
            message_bytes = bsm.to_bytes()

        # MAC layer resource allocation
        resource = self.mac_layer.allocate_resources(self.vehicle_id)

        if not resource:
            return None

        # PHY layer transmission
        tx_info = self.phy_layer.transmit(
            message_bytes,
            self.mac_layer.tx_power,
            resource
        )

        self.stats['messages_sent'] += 1

        return tx_info

    def send_denm(self, event_type: str, position: Position,
                  severity: str = "high", description: str = "") -> Optional[dict]:
        """
        Send Decentralized Environmental Notification Message

        Args:
            event_type: Type of event (e.g., "emergency_brake", "road_hazard")
            position: Event position
            severity: Event severity level
            description: Event description

        Returns:
            Transmission info or None if failed
        """
        denm = DENM(
            msg_id=self.denm_counter,
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            position={
                'latitude': position.latitude,
                'longitude': position.longitude,
                'elevation': position.elevation
            },
            severity=severity,
            description=description
        )
        self.denm_counter += 1

        message_dict = denm.to_dict()

        if self.identity_manager:
            signed_message = self.identity_manager.sign_message(message_dict)
            message_bytes = json.dumps(signed_message).encode('utf-8')
        else:
            message_bytes = denm.to_bytes()

        resource = self.mac_layer.allocate_resources(self.vehicle_id)

        if not resource:
            return None

        tx_info = self.phy_layer.transmit(
            message_bytes,
            self.mac_layer.tx_power,
            resource
        )

        self.stats['messages_sent'] += 1

        return tx_info

    def receive_message(self, tx_info: dict, rx_position: Position,
                       tx_position: Position, crl: set = None) -> Tuple[bool, dict]:
        """
        Receive and process V2X message

        Args:
            tx_info: Transmission information
            rx_position: Receiver position
            tx_position: Transmitter position
            crl: Certificate Revocation List (for PKI)

        Returns:
            Tuple of (success, result_info)
        """
        # PHY layer reception
        message_bytes, rx_info = self.phy_layer.receive(
            tx_info, rx_position, tx_position
        )

        if message_bytes is None:
            return False, rx_info

        self.stats['messages_received'] += 1

        # Parse message
        try:
            message_data = json.loads(message_bytes.decode('utf-8'))

            # Verify signature if identity manager available
            if self.identity_manager and 'signature' in message_data:
                is_valid, verify_time = self.identity_manager.verify_message(
                    message_data, crl or set()
                )

                if is_valid:
                    self.stats['messages_verified'] += 1
                else:
                    self.stats['verification_failures'] += 1

                rx_info['verification_time_ms'] = verify_time
                rx_info['signature_valid'] = is_valid

            # Update latency statistics
            if 'latency_ms' in rx_info:
                self.stats['total_latency'] += rx_info['latency_ms']

            rx_info['message'] = message_data
            rx_info['success'] = True

            return True, rx_info

        except Exception as e:
            return False, {'error': str(e)}

    def get_statistics(self) -> dict:
        """Get protocol stack statistics"""
        stats = self.stats.copy()

        if stats['messages_received'] > 0:
            stats['avg_latency_ms'] = (
                stats['total_latency'] / stats['messages_received']
            )
            stats['verification_success_rate'] = (
                stats['messages_verified'] /
                (stats['messages_verified'] + stats['verification_failures'])
                if (stats['messages_verified'] + stats['verification_failures']) > 0
                else 0.0
            )

        stats['cbr'] = self.mac_layer.get_cbr()

        return stats


# Utility imports
try:
    import numpy as np
except ImportError:
    # Fallback if numpy not available
    class np:
        @staticmethod
        def log10(x):
            import math
            return math.log10(x)

        @staticmethod
        def sqrt(x):
            import math
            return math.sqrt(x)

        @staticmethod
        def cos(x):
            import math
            return math.cos(x)

        @staticmethod
        def radians(x):
            import math
            return math.radians(x)


if __name__ == "__main__":
    print("=== CV2X Protocol Stack Test ===\n")

    # Create two vehicles
    vehicle_state_1 = VehicleState(
        vehicle_id="V001",
        timestamp=datetime.utcnow().isoformat(),
        position=Position(49.2827, -123.1207, 50.0),
        speed=15.0,  # m/s (~54 km/h)
        heading=90.0,
        acceleration=0.0
    )

    vehicle_state_2 = VehicleState(
        vehicle_id="V002",
        timestamp=datetime.utcnow().isoformat(),
        position=Position(49.2830, -123.1207, 50.0),  # ~33m north
        speed=12.0,
        heading=90.0,
        acceleration=0.0
    )

    # Create CV2X stacks
    stack_1 = CV2XStack("V001", mode=CommunicationMode.MODE_4)
    stack_2 = CV2XStack("V002", mode=CommunicationMode.MODE_4)

    # Vehicle 1 sends BSM
    print("Vehicle 1 sending BSM...")
    tx_info = stack_1.send_bsm(vehicle_state_1)

    if tx_info:
        print(f"  ✓ BSM transmitted ({tx_info['size_bytes']} bytes)")

        # Vehicle 2 receives BSM
        print("\nVehicle 2 receiving BSM...")
        success, rx_info = stack_2.receive_message(
            tx_info,
            vehicle_state_2.position,
            vehicle_state_1.position
        )

        if success:
            print(f"  ✓ BSM received successfully")
            print(f"  Distance: {rx_info['distance']:.1f} m")
            print(f"  RX Power: {rx_info['rx_power']:.1f} dBm")
            print(f"  Latency: {rx_info['latency_ms']:.2f} ms")

    # Print statistics
    print("\n=== Statistics ===")
    stats_1 = stack_1.get_statistics()
    stats_2 = stack_2.get_statistics()

    print(f"Vehicle 1: {stats_1['messages_sent']} sent")
    print(f"Vehicle 2: {stats_2['messages_received']} received")

    print("\n=== Test Complete ===")
