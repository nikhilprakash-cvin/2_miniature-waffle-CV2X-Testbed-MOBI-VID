#!/usr/bin/env python3
"""
Automotive Credential Schemas — W3C VC Data Model v2.0
======================================================

Defines the credential schemas for all 10 thesis use cases. Each schema
declares required/optional claim properties and per-property type checks,
and is referenced from issued credentials via `credentialSchema`.

Schemas map 1:1 to the thesis use-case suite:

  UC1  VehicleBirthCertificate   — manufacturing (MOBI VID I)
  UC2  OwnershipTransfer         — dealership sale
  UC3  OwnershipTransfer         — private-party sale (same schema, roles differ)
  UC4  InsuranceClaim            — post-accident claim
  UC5  MaintenanceRecord         — service-center visit
  UC6  SafetyRecall              — manufacturer recall notice
  UC7  TheftReport               — police theft report
  UC8  RegistrationCredential    — (cross-border) registration
  UC9  DecommissionCertificate   — end-of-life
  UC10 V2VSafetyCredential       — real-time V2V message authorization
  +    EmissionsCompliance       — periodic inspection (supporting)

Author: Nikhil Prakash
Thesis: MASc, UBC ECE
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# W3C VC Data Model v2.0 base context
VC_CONTEXT_V2 = "https://www.w3.org/ns/credentials/v2"
# Thesis-specific vocabulary context (published with the repository)
CVIN_CONTEXT = "https://cvin.ubc.ca/credentials/automotive/v1"

# VIN: 17 chars, ISO 3779 alphabet (no I, O, Q)
VIN_ALPHABET = set("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")


def is_valid_vin(vin: Any) -> bool:
    """ISO 3779 structural VIN check (length + alphabet)."""
    return (
        isinstance(vin, str)
        and len(vin) == 17
        and all(c in VIN_ALPHABET for c in vin.upper())
    )


def is_did(value: Any) -> bool:
    """Loose DID syntax check: did:<method>:<method-specific-id>."""
    return (
        isinstance(value, str)
        and value.startswith("did:")
        and len(value.split(":", 2)) == 3
        and all(part for part in value.split(":", 2))
    )


@dataclass
class PropertySpec:
    """Specification for a single claim property."""
    name: str
    types: Tuple[type, ...]        # accepted python types
    required: bool = True
    validator: Optional[Any] = None  # callable(value) -> bool
    description: str = ""


@dataclass
class CredentialSchema:
    """A named schema with property specs and a validate() method."""
    schema_id: str
    credential_type: str
    description: str
    properties: List[PropertySpec] = field(default_factory=list)

    @property
    def required_properties(self) -> List[str]:
        return [p.name for p in self.properties if p.required]

    def validate(self, claims: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a claims dict against this schema.

        Returns (is_valid, errors). Unknown properties are permitted (VC DM
        is an open-world model) but required properties must be present and
        every known property must satisfy its type/validator.
        """
        errors: List[str] = []
        specs = {p.name: p for p in self.properties}

        for name in self.required_properties:
            if name not in claims:
                errors.append(f"missing required property '{name}'")

        for name, value in claims.items():
            spec = specs.get(name)
            if spec is None:
                continue  # open-world: extra claims allowed
            if not isinstance(value, spec.types):
                expected = "/".join(t.__name__ for t in spec.types)
                errors.append(
                    f"property '{name}' expected {expected}, "
                    f"got {type(value).__name__}"
                )
                continue
            if spec.validator is not None and not spec.validator(value):
                errors.append(f"property '{name}' failed validation: {value!r}")

        return (len(errors) == 0, errors)

    def to_credential_schema_entry(self) -> Dict[str, str]:
        """The `credentialSchema` entry embedded in issued credentials."""
        return {"id": self.schema_id, "type": "JsonSchema"}


def _schema(cred_type: str, description: str,
            props: List[PropertySpec]) -> CredentialSchema:
    return CredentialSchema(
        schema_id=f"{CVIN_CONTEXT}/schemas/{cred_type}",
        credential_type=cred_type,
        description=description,
        properties=props,
    )


# ---------------------------------------------------------------------------
# Schema definitions (10 use cases + 1 supporting)
# ---------------------------------------------------------------------------

VEHICLE_BIRTH_CERTIFICATE = _schema(
    "VehicleBirthCertificate",
    "MOBI VID I birth certificate issued by the manufacturer at production.",
    [
        PropertySpec("vin", (str,), True, is_valid_vin, "ISO 3779 VIN"),
        PropertySpec("make", (str,), True),
        PropertySpec("model", (str,), True),
        PropertySpec("year", (int,), True, lambda y: 1980 <= y <= 2100),
        PropertySpec("manufacturingDate", (str,), True),
        PropertySpec("manufacturerDid", (str,), True, is_did),
        PropertySpec("plantCode", (str,), False),
        PropertySpec("engineType", (str,), False),
        PropertySpec("bodyType", (str,), False),
        PropertySpec("color", (str,), False),
    ],
)

OWNERSHIP_TRANSFER = _schema(
    "OwnershipTransfer",
    "Transfer of vehicle ownership (dealership or private-party sale).",
    [
        PropertySpec("vin", (str,), True, is_valid_vin),
        PropertySpec("previousOwnerDid", (str,), True, is_did),
        PropertySpec("newOwnerDid", (str,), True, is_did),
        PropertySpec("transferDate", (str,), True),
        PropertySpec("transferType", (str,), True,
                     lambda v: v in ("dealership_sale", "private_sale",
                                     "lease", "inheritance", "auction")),
        PropertySpec("salePrice", (int, float), False),
        PropertySpec("odometerKm", (int,), False, lambda v: v >= 0),
        PropertySpec("jurisdiction", (str,), False),
    ],
)

INSURANCE_CLAIM = _schema(
    "InsuranceClaim",
    "Insurance claim recorded against the vehicle after an incident.",
    [
        PropertySpec("vin", (str,), True, is_valid_vin),
        PropertySpec("policyNumber", (str,), True),
        PropertySpec("insurerDid", (str,), True, is_did),
        PropertySpec("incidentDate", (str,), True),
        PropertySpec("claimType", (str,), True,
                     lambda v: v in ("collision", "theft", "vandalism",
                                     "weather", "liability", "comprehensive")),
        PropertySpec("damageDescription", (str,), True),
        PropertySpec("claimAmount", (int, float), False, lambda v: v >= 0),
        PropertySpec("totalLoss", (bool,), False),
    ],
)

MAINTENANCE_RECORD = _schema(
    "MaintenanceRecord",
    "Service-center maintenance event (MOBI VID II event).",
    [
        PropertySpec("vin", (str,), True, is_valid_vin),
        PropertySpec("serviceCenterDid", (str,), True, is_did),
        PropertySpec("serviceDate", (str,), True),
        PropertySpec("serviceType", (str,), True),
        PropertySpec("odometerKm", (int,), True, lambda v: v >= 0),
        PropertySpec("partsReplaced", (list,), False),
        PropertySpec("technicianId", (str,), False),
        PropertySpec("cost", (int, float), False, lambda v: v >= 0),
    ],
)

SAFETY_RECALL = _schema(
    "SafetyRecall",
    "Manufacturer/regulator safety recall notification.",
    [
        PropertySpec("vin", (str,), True, is_valid_vin),
        PropertySpec("recallId", (str,), True),
        PropertySpec("issuingAuthorityDid", (str,), True, is_did),
        PropertySpec("component", (str,), True),
        PropertySpec("severity", (str,), True,
                     lambda v: v in ("low", "medium", "high", "critical")),
        PropertySpec("description", (str,), True),
        PropertySpec("remedyDeadline", (str,), False),
    ],
)

THEFT_REPORT = _schema(
    "TheftReport",
    "Police-issued vehicle theft report.",
    [
        PropertySpec("vin", (str,), True, is_valid_vin),
        PropertySpec("reportingAuthorityDid", (str,), True, is_did),
        PropertySpec("reportNumber", (str,), True),
        PropertySpec("theftDate", (str,), True),
        PropertySpec("jurisdiction", (str,), True),
        PropertySpec("recovered", (bool,), False),
        PropertySpec("recoveryDate", (str,), False),
    ],
)

REGISTRATION_CREDENTIAL = _schema(
    "RegistrationCredential",
    "Vehicle registration, including cross-border re-registration.",
    [
        PropertySpec("vin", (str,), True, is_valid_vin),
        PropertySpec("registrationAuthorityDid", (str,), True, is_did),
        PropertySpec("ownerDid", (str,), True, is_did),
        PropertySpec("jurisdiction", (str,), True),
        PropertySpec("plateNumber", (str,), True),
        PropertySpec("registrationDate", (str,), True),
        PropertySpec("previousJurisdiction", (str,), False),
        PropertySpec("importDeclarationId", (str,), False),
    ],
)

DECOMMISSION_CERTIFICATE = _schema(
    "DecommissionCertificate",
    "End-of-life decommission / scrappage certificate.",
    [
        PropertySpec("vin", (str,), True, is_valid_vin),
        PropertySpec("facilityDid", (str,), True, is_did),
        PropertySpec("decommissionDate", (str,), True),
        PropertySpec("reason", (str,), True,
                     lambda v: v in ("end_of_life", "total_loss",
                                     "export", "regulatory")),
        PropertySpec("finalOdometerKm", (int,), False, lambda v: v >= 0),
        PropertySpec("recyclingRate", (int, float), False,
                     lambda v: 0 <= v <= 100),
    ],
)

V2V_SAFETY_CREDENTIAL = _schema(
    "V2VSafetyCredential",
    "Short-lived credential authorizing a vehicle to send V2V safety "
    "messages (FCW/EEBL/IMA). Verified in the real-time message path.",
    [
        PropertySpec("vehicleDid", (str,), True, is_did),
        PropertySpec("pseudonymId", (str,), True),
        PropertySpec("authorizedApplications", (list,), True,
                     lambda apps: len(apps) > 0 and
                     all(a in ("FCW", "EEBL", "IMA", "BSW", "LCW")
                         for a in apps)),
        PropertySpec("region", (str,), True),
        PropertySpec("securityLevel", (int,), True, lambda v: 1 <= v <= 5),
    ],
)

EMISSIONS_COMPLIANCE = _schema(
    "EmissionsCompliance",
    "Periodic emissions inspection result (supporting schema).",
    [
        PropertySpec("vin", (str,), True, is_valid_vin),
        PropertySpec("inspectionStationDid", (str,), True, is_did),
        PropertySpec("inspectionDate", (str,), True),
        PropertySpec("passed", (bool,), True),
        PropertySpec("co2GramsPerKm", (int, float), False, lambda v: v >= 0),
        PropertySpec("standard", (str,), False),
    ],
)


SCHEMA_REGISTRY: Dict[str, CredentialSchema] = {
    s.credential_type: s
    for s in (
        VEHICLE_BIRTH_CERTIFICATE,
        OWNERSHIP_TRANSFER,
        INSURANCE_CLAIM,
        MAINTENANCE_RECORD,
        SAFETY_RECALL,
        THEFT_REPORT,
        REGISTRATION_CREDENTIAL,
        DECOMMISSION_CERTIFICATE,
        V2V_SAFETY_CREDENTIAL,
        EMISSIONS_COMPLIANCE,
    )
}


def get_schema(credential_type: str) -> Optional[CredentialSchema]:
    """Look up a schema by credential type name."""
    return SCHEMA_REGISTRY.get(credential_type)


def validate_claims(credential_type: str,
                    claims: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate claims against the registered schema for the given type."""
    schema = get_schema(credential_type)
    if schema is None:
        return False, [f"unknown credential type '{credential_type}'"]
    return schema.validate(claims)


if __name__ == "__main__":
    # Demo: validate a correct and an incorrect birth certificate
    good = {
        "vin": "5YJ3E1EA0PF123456",
        "make": "Tesla",
        "model": "Model 3",
        "year": 2024,
        "manufacturingDate": "2024-01-15",
        "manufacturerDid": "did:mobi:manufacturer:tesla",
    }
    bad = {"vin": "TOO_SHORT", "make": "Tesla"}

    for label, claims in (("valid", good), ("invalid", bad)):
        ok, errs = validate_claims("VehicleBirthCertificate", claims)
        print(f"[{label}] valid={ok}")
        for e in errs:
            print(f"    - {e}")

    print(f"\nRegistered schemas ({len(SCHEMA_REGISTRY)}):")
    for name, schema in SCHEMA_REGISTRY.items():
        print(f"  - {name}: required={schema.required_properties}")
