"""
Centralized Vehicle Registry

Traditional centralized vehicle identity and lifecycle management system.
This serves as the CONTROL/BASELINE for comparison with MOBI VID (blockchain-based).

Features:
- Vehicle birth certificate registration
- Lifecycle event tracking
- Service history database
- Ownership transfer tracking
- Multi-party event issuance
- Performance metrics

Architecture:
- In-memory database (simulating PostgreSQL/MySQL)
- PKI-based authentication
- RESTful API (simulated)
- Centralized authority

This system provides feature parity with MOBI VID for fair comparison.
"""

import time
import hashlib
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend


# ============ ENUMS ============

class EventType(Enum):
    """Types of lifecycle events (matches MOBI VID II)"""
    MAINTENANCE = "maintenance"
    REPAIR = "repair"
    ACCIDENT = "accident"
    RECALL = "recall"
    INSPECTION = "inspection"
    MODIFICATION = "modification"
    THEFT_REPORT = "theft_report"
    RECOVERY = "recovery"
    INSURANCE_CLAIM = "insurance_claim"
    REGISTRATION = "registration"
    DECOMMISSION = "decommission"


class IssuerRole(Enum):
    """Issuer roles (matches MOBI VID II)"""
    MANUFACTURER = "manufacturer"
    DEALER = "dealer"
    SERVICE_CENTER = "service_center"
    INSURANCE_COMPANY = "insurance_company"
    GOVERNMENT_DMV = "government_dmv"
    POLICE = "police"
    INSPECTION_STATION = "inspection_station"
    OWNER = "owner"


# ============ DATA MODELS ============

@dataclass
class VehicleBirthCertificate:
    """Vehicle birth certificate (like MOBI VID I)"""
    certificate_id: str
    vin: str  # Plain text in centralized system
    manufacturer: str
    make: str
    model: str
    year: int
    color: str
    first_owner: str
    registered_at: datetime
    registry_authority: str = "Central Vehicle Registry"

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['registered_at'] = self.registered_at.isoformat()
        return data


@dataclass
class LifecycleEvent:
    """Lifecycle event (like MOBI VID II)"""
    event_id: str
    vehicle_id: str
    event_type: EventType
    issuer_id: str
    issuer_role: IssuerRole
    timestamp: datetime
    odometer: int
    data: Dict[str, Any]
    verified: bool
    jurisdiction: str

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['issuer_role'] = self.issuer_role.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class OwnershipTransfer:
    """Ownership transfer record"""
    transfer_id: str
    vehicle_id: str
    from_owner: str
    to_owner: str
    timestamp: datetime
    odometer: int
    sale_price: float
    authority: str

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class AuthorizedIssuer:
    """Authorized issuer"""
    issuer_id: str
    name: str
    role: IssuerRole
    license_number: str
    authorized_by: str
    authorized_at: datetime

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['role'] = self.role.value
        data['authorized_at'] = self.authorized_at.isoformat()
        return data


# ============ CENTRALIZED VEHICLE REGISTRY ============

class CentralizedVehicleRegistry:
    """
    Centralized Vehicle Identity and Lifecycle System

    This is the CONTROL/BASELINE for comparison with MOBI VID blockchain system.

    Advantages:
    - Fast (no blockchain consensus)
    - Cheap (no gas fees)
    - High throughput
    - Complex queries easy

    Disadvantages:
    - Single point of failure
    - Trust required in central authority
    - Can be censored/manipulated
    - Not transparent
    - Geographic limitations
    """

    def __init__(self, registry_name: str = "Central Vehicle Registry"):
        self.registry_name = registry_name

        # In-memory "database" (simulating PostgreSQL)
        self.birth_certificates: Dict[str, VehicleBirthCertificate] = {}
        self.lifecycle_events: Dict[str, List[LifecycleEvent]] = {}  # vehicle_id -> events
        self.ownership_history: Dict[str, List[OwnershipTransfer]] = {}  # vehicle_id -> transfers
        self.authorized_issuers: Dict[str, AuthorizedIssuer] = {}
        self.current_owners: Dict[str, str] = {}  # vehicle_id -> owner_id

        # VIN index for fast lookup
        self.vin_to_vehicle_id: Dict[str, str] = {}

        # Performance metrics
        self.metrics = {
            'registrations': 0,
            'events_recorded': 0,
            'queries': 0,
            'total_registration_time_ms': 0.0,
            'total_query_time_ms': 0.0,
            'total_event_time_ms': 0.0
        }

    # ============ BIRTH CERTIFICATE (VID I equivalent) ============

    def register_vehicle_birth(
        self,
        vin: str,
        manufacturer: str,
        make: str,
        model: str,
        year: int,
        color: str,
        first_owner: str,
        manufacturer_id: str
    ) -> VehicleBirthCertificate:
        """
        Register vehicle birth certificate

        Args:
            vin: Vehicle Identification Number (plain text, no privacy)
            manufacturer: Manufacturer name
            make: Vehicle make
            model: Vehicle model
            year: Manufacturing year
            color: Vehicle color
            first_owner: First owner ID
            manufacturer_id: Manufacturer's issuer ID

        Returns:
            VehicleBirthCertificate
        """
        start_time = time.time()

        # Verify manufacturer is authorized
        if manufacturer_id not in self.authorized_issuers:
            raise ValueError(f"Manufacturer {manufacturer_id} not authorized")

        issuer = self.authorized_issuers[manufacturer_id]
        if issuer.role != IssuerRole.MANUFACTURER:
            raise ValueError(f"Issuer {manufacturer_id} is not a manufacturer")

        # Check if VIN already registered
        if vin in self.vin_to_vehicle_id:
            raise ValueError(f"VIN {vin} already registered")

        # Generate certificate ID (like database primary key)
        certificate_id = hashlib.sha256(
            f"{vin}{int(time.time())}".encode()
        ).hexdigest()[:16]

        # Generate vehicle ID
        vehicle_id = f"vehicle_{certificate_id}"

        # Create birth certificate
        cert = VehicleBirthCertificate(
            certificate_id=certificate_id,
            vin=vin,
            manufacturer=manufacturer,
            make=make,
            model=model,
            year=year,
            color=color,
            first_owner=first_owner,
            registered_at=datetime.utcnow()
        )

        # Store in "database"
        self.birth_certificates[vehicle_id] = cert
        self.vin_to_vehicle_id[vin] = vehicle_id
        self.current_owners[vehicle_id] = first_owner
        self.lifecycle_events[vehicle_id] = []
        self.ownership_history[vehicle_id] = []

        # Update metrics
        elapsed = (time.time() - start_time) * 1000
        self.metrics['registrations'] += 1
        self.metrics['total_registration_time_ms'] += elapsed

        return cert

    # ============ LIFECYCLE EVENTS (VID II equivalent) ============

    def record_lifecycle_event(
        self,
        vehicle_id: str,
        event_type: EventType,
        issuer_id: str,
        odometer: int,
        event_data: Dict[str, Any],
        jurisdiction: str = "USA"
    ) -> LifecycleEvent:
        """
        Record lifecycle event

        Args:
            vehicle_id: Vehicle ID
            event_type: Type of event
            issuer_id: Issuer ID
            odometer: Odometer reading
            event_data: Event-specific data
            jurisdiction: Legal jurisdiction

        Returns:
            LifecycleEvent
        """
        start_time = time.time()

        # Verify vehicle exists
        if vehicle_id not in self.birth_certificates:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        # Verify issuer is authorized
        if issuer_id not in self.authorized_issuers:
            raise ValueError(f"Issuer {issuer_id} not authorized")

        issuer = self.authorized_issuers[issuer_id]

        # Verify issuer can issue this event type
        if not self._can_issue_event_type(issuer.role, event_type):
            raise ValueError(
                f"Issuer role {issuer.role.value} cannot issue {event_type.value} events"
            )

        # Generate event ID
        event_id = hashlib.sha256(
            f"{vehicle_id}{event_type.value}{int(time.time())}".encode()
        ).hexdigest()[:16]

        # Create event
        event = LifecycleEvent(
            event_id=event_id,
            vehicle_id=vehicle_id,
            event_type=event_type,
            issuer_id=issuer_id,
            issuer_role=issuer.role,
            timestamp=datetime.utcnow(),
            odometer=odometer,
            data=event_data,
            verified=self._is_verified_issuer(issuer.role),
            jurisdiction=jurisdiction
        )

        # Store in "database"
        self.lifecycle_events[vehicle_id].append(event)

        # Update metrics
        elapsed = (time.time() - start_time) * 1000
        self.metrics['events_recorded'] += 1
        self.metrics['total_event_time_ms'] += elapsed

        return event

    # ============ OWNERSHIP MANAGEMENT ============

    def transfer_ownership(
        self,
        vehicle_id: str,
        new_owner: str,
        odometer: int,
        sale_price: float,
        authority: str = "DMV"
    ) -> OwnershipTransfer:
        """
        Transfer vehicle ownership

        Args:
            vehicle_id: Vehicle ID
            new_owner: New owner ID
            odometer: Odometer at transfer
            sale_price: Sale price
            authority: Registration authority

        Returns:
            OwnershipTransfer
        """
        if vehicle_id not in self.birth_certificates:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        current_owner = self.current_owners[vehicle_id]

        # Generate transfer ID
        transfer_id = hashlib.sha256(
            f"{vehicle_id}{new_owner}{int(time.time())}".encode()
        ).hexdigest()[:16]

        # Create transfer record
        transfer = OwnershipTransfer(
            transfer_id=transfer_id,
            vehicle_id=vehicle_id,
            from_owner=current_owner,
            to_owner=new_owner,
            timestamp=datetime.utcnow(),
            odometer=odometer,
            sale_price=sale_price,
            authority=authority
        )

        # Update ownership
        self.current_owners[vehicle_id] = new_owner
        self.ownership_history[vehicle_id].append(transfer)

        return transfer

    # ============ ISSUER MANAGEMENT ============

    def authorize_issuer(
        self,
        issuer_id: str,
        name: str,
        role: IssuerRole,
        license_number: str
    ) -> AuthorizedIssuer:
        """
        Authorize an issuer

        Args:
            issuer_id: Unique issuer ID
            name: Issuer name
            role: Issuer role
            license_number: License/certification number

        Returns:
            AuthorizedIssuer
        """
        issuer = AuthorizedIssuer(
            issuer_id=issuer_id,
            name=name,
            role=role,
            license_number=license_number,
            authorized_by=self.registry_name,
            authorized_at=datetime.utcnow()
        )

        self.authorized_issuers[issuer_id] = issuer

        return issuer

    def revoke_issuer(self, issuer_id: str) -> bool:
        """Revoke issuer authorization"""
        if issuer_id in self.authorized_issuers:
            del self.authorized_issuers[issuer_id]
            return True
        return False

    # ============ QUERY FUNCTIONS ============

    def get_vehicle_by_vin(self, vin: str) -> Optional[str]:
        """Get vehicle ID by VIN"""
        start_time = time.time()

        vehicle_id = self.vin_to_vehicle_id.get(vin)

        elapsed = (time.time() - start_time) * 1000
        self.metrics['queries'] += 1
        self.metrics['total_query_time_ms'] += elapsed

        return vehicle_id

    def get_birth_certificate(self, vehicle_id: str) -> Optional[VehicleBirthCertificate]:
        """Get vehicle birth certificate"""
        start_time = time.time()

        cert = self.birth_certificates.get(vehicle_id)

        elapsed = (time.time() - start_time) * 1000
        self.metrics['queries'] += 1
        self.metrics['total_query_time_ms'] += elapsed

        return cert

    def get_vehicle_history(self, vehicle_id: str) -> Dict[str, Any]:
        """
        Get complete vehicle history (birth + events + owners)

        This demonstrates the advantage of centralized systems: easy complex queries
        """
        start_time = time.time()

        if vehicle_id not in self.birth_certificates:
            return {}

        history = {
            'birth_certificate': self.birth_certificates[vehicle_id].to_dict(),
            'current_owner': self.current_owners[vehicle_id],
            'lifecycle_events': [e.to_dict() for e in self.lifecycle_events[vehicle_id]],
            'ownership_history': [t.to_dict() for t in self.ownership_history[vehicle_id]],
            'event_count': len(self.lifecycle_events[vehicle_id]),
            'transfer_count': len(self.ownership_history[vehicle_id])
        }

        elapsed = (time.time() - start_time) * 1000
        self.metrics['queries'] += 1
        self.metrics['total_query_time_ms'] += elapsed

        return history

    def get_events_by_type(
        self,
        vehicle_id: str,
        event_type: EventType
    ) -> List[LifecycleEvent]:
        """Get events of specific type"""
        if vehicle_id not in self.lifecycle_events:
            return []

        return [
            e for e in self.lifecycle_events[vehicle_id]
            if e.event_type == event_type
        ]

    def get_odometer_history(self, vehicle_id: str) -> List[Tuple[datetime, int]]:
        """Get odometer history for fraud detection"""
        if vehicle_id not in self.lifecycle_events:
            return []

        history = [
            (e.timestamp, e.odometer)
            for e in self.lifecycle_events[vehicle_id]
        ]

        return sorted(history, key=lambda x: x[0])

    def search_vehicles(
        self,
        make: Optional[str] = None,
        model: Optional[str] = None,
        year: Optional[int] = None,
        owner: Optional[str] = None
    ) -> List[VehicleBirthCertificate]:
        """
        Search vehicles by criteria

        This demonstrates centralized advantage: flexible searching
        """
        results = []

        for vehicle_id, cert in self.birth_certificates.items():
            match = True

            if make and cert.make != make:
                match = False
            if model and cert.model != model:
                match = False
            if year and cert.year != year:
                match = False
            if owner and self.current_owners[vehicle_id] != owner:
                match = False

            if match:
                results.append(cert)

        return results

    # ============ ANALYTICS (Centralized Advantage) ============

    def get_fleet_statistics(self, owner: str) -> Dict[str, Any]:
        """
        Get fleet statistics for an owner

        Easy in centralized system, hard in blockchain
        """
        fleet_vehicles = [
            vid for vid, owner_id in self.current_owners.items()
            if owner_id == owner
        ]

        total_events = sum(
            len(self.lifecycle_events[vid])
            for vid in fleet_vehicles
        )

        maintenance_events = sum(
            len(self.get_events_by_type(vid, EventType.MAINTENANCE))
            for vid in fleet_vehicles
        )

        return {
            'owner': owner,
            'vehicle_count': len(fleet_vehicles),
            'total_events': total_events,
            'maintenance_events': maintenance_events,
            'average_events_per_vehicle': total_events / len(fleet_vehicles) if fleet_vehicles else 0
        }

    def detect_odometer_fraud(self, vehicle_id: str) -> List[str]:
        """
        Detect odometer fraud

        Returns list of suspicious events
        """
        history = self.get_odometer_history(vehicle_id)
        suspicious = []

        for i in range(1, len(history)):
            prev_timestamp, prev_odometer = history[i-1]
            curr_timestamp, curr_odometer = history[i]

            # Check for rollback
            if curr_odometer < prev_odometer:
                suspicious.append(
                    f"Odometer rollback detected: {prev_odometer} -> {curr_odometer} "
                    f"between {prev_timestamp.date()} and {curr_timestamp.date()}"
                )

        return suspicious

    # ============ PERFORMANCE METRICS ============

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for comparison with blockchain

        Returns:
            Dictionary of metrics
        """
        avg_registration_time = (
            self.metrics['total_registration_time_ms'] / self.metrics['registrations']
            if self.metrics['registrations'] > 0 else 0
        )

        avg_query_time = (
            self.metrics['total_query_time_ms'] / self.metrics['queries']
            if self.metrics['queries'] > 0 else 0
        )

        avg_event_time = (
            self.metrics['total_event_time_ms'] / self.metrics['events_recorded']
            if self.metrics['events_recorded'] > 0 else 0
        )

        return {
            'registrations': self.metrics['registrations'],
            'events_recorded': self.metrics['events_recorded'],
            'queries': self.metrics['queries'],
            'avg_registration_time_ms': avg_registration_time,
            'avg_query_time_ms': avg_query_time,
            'avg_event_time_ms': avg_event_time,
            'total_vehicles': len(self.birth_certificates),
            'total_issuers': len(self.authorized_issuers),
            'storage_size_estimate_mb': self._estimate_storage_size()
        }

    def _estimate_storage_size(self) -> float:
        """Estimate storage size in MB"""
        # Simple estimation based on JSON size
        total_data = {
            'certificates': [c.to_dict() for c in self.birth_certificates.values()],
            'events': [e.to_dict() for events in self.lifecycle_events.values() for e in events],
            'transfers': [t.to_dict() for transfers in self.ownership_history.values() for t in transfers]
        }

        json_str = json.dumps(total_data)
        size_mb = len(json_str.encode('utf-8')) / (1024 * 1024)

        return size_mb

    # ============ INTERNAL HELPERS ============

    def _can_issue_event_type(self, role: IssuerRole, event_type: EventType) -> bool:
        """Check if role can issue event type"""
        allowed = {
            EventType.MAINTENANCE: [IssuerRole.DEALER, IssuerRole.SERVICE_CENTER, IssuerRole.OWNER],
            EventType.REPAIR: [IssuerRole.DEALER, IssuerRole.SERVICE_CENTER],
            EventType.ACCIDENT: [IssuerRole.POLICE, IssuerRole.INSURANCE_COMPANY, IssuerRole.OWNER],
            EventType.RECALL: [IssuerRole.MANUFACTURER],
            EventType.INSPECTION: [IssuerRole.INSPECTION_STATION, IssuerRole.GOVERNMENT_DMV],
            EventType.MODIFICATION: [IssuerRole.SERVICE_CENTER, IssuerRole.OWNER],
            EventType.THEFT_REPORT: [IssuerRole.POLICE, IssuerRole.OWNER],
            EventType.RECOVERY: [IssuerRole.POLICE],
            EventType.INSURANCE_CLAIM: [IssuerRole.INSURANCE_COMPANY, IssuerRole.OWNER],
            EventType.REGISTRATION: [IssuerRole.GOVERNMENT_DMV],
            EventType.DECOMMISSION: [IssuerRole.MANUFACTURER, IssuerRole.GOVERNMENT_DMV]
        }

        return role in allowed.get(event_type, [])

    def _is_verified_issuer(self, role: IssuerRole) -> bool:
        """Check if issuer is verified (government, manufacturer, etc.)"""
        verified_roles = [
            IssuerRole.MANUFACTURER,
            IssuerRole.GOVERNMENT_DMV,
            IssuerRole.POLICE,
            IssuerRole.DEALER,
            IssuerRole.INSPECTION_STATION
        ]

        return role in verified_roles
