"""
Standard PKI-Based Vehicle Identity System

This implements a traditional PKI system for vehicle authentication,
serving as a baseline for comparison with DID/SSI approaches.
"""

import hashlib
import time
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
import json


class VehiclePKIIdentity:
    """
    Standard PKI-based vehicle identity implementation.

    Based on IEEE 1609.2 and ETSI TS 102 940/941 standards for V2X PKI.
    """

    def __init__(self, vehicle_id: str):
        self.vehicle_id = vehicle_id
        self.private_key = None
        self.long_term_certificate = None
        self.pseudonym_certificates = []
        self.current_pseudonym_index = 0
        self.certificate_revocation_list = set()

    def generate_keypair(self):
        """Generate ECDSA P-256 keypair for vehicle."""
        self.private_key = ec.generate_private_key(
            ec.SECP256R1(),
            default_backend()
        )
        return self.private_key.public_key()

    def request_enrollment_certificate(self, ca):
        """
        Request long-term enrollment certificate from CA.

        Args:
            ca: Certificate Authority instance

        Returns:
            x509.Certificate: Long-term enrollment certificate
        """
        if not self.private_key:
            self.generate_keypair()

        # Create certificate signing request
        csr = x509.CertificateSigningRequestBuilder().subject_name(
            x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, f"Vehicle-{self.vehicle_id}"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CVIN Testbed"),
            ])
        ).sign(self.private_key, hashes.SHA256(), default_backend())

        # CA issues enrollment certificate
        self.long_term_certificate = ca.issue_enrollment_certificate(csr)
        return self.long_term_certificate

    def request_pseudonym_certificates(self, ca, count: int = 20):
        """
        Request batch of pseudonym certificates for privacy.

        Pseudonym certificates are short-lived and frequently rotated
        to prevent vehicle tracking.

        Args:
            ca: Certificate Authority instance
            count: Number of pseudonym certificates to request

        Returns:
            list: List of pseudonym certificates
        """
        self.pseudonym_certificates = []

        for i in range(count):
            # Generate ephemeral keypair for each pseudonym
            pseudonym_key = ec.generate_private_key(
                ec.SECP256R1(),
                default_backend()
            )

            # Create CSR with pseudonym identifier
            pseudonym_id = hashlib.sha256(
                f"{self.vehicle_id}-{i}-{time.time()}".encode()
            ).hexdigest()[:16]

            csr = x509.CertificateSigningRequestBuilder().subject_name(
                x509.Name([
                    x509.NameAttribute(NameOID.COMMON_NAME, f"Pseudonym-{pseudonym_id}"),
                ])
            ).sign(pseudonym_key, hashes.SHA256(), default_backend())

            # CA issues pseudonym certificate
            cert = ca.issue_pseudonym_certificate(
                csr,
                validity_hours=1  # Short-lived for privacy
            )

            self.pseudonym_certificates.append({
                'certificate': cert,
                'private_key': pseudonym_key,
                'valid_until': datetime.utcnow() + timedelta(hours=1),
                'usage_count': 0
            })

        return self.pseudonym_certificates

    def get_current_pseudonym(self):
        """
        Get current active pseudonym certificate.

        Rotates pseudonyms based on:
        - Time expiration (typically 5 minutes)
        - Usage count (number of messages signed)
        - Geographic zone change
        """
        if not self.pseudonym_certificates:
            raise ValueError("No pseudonym certificates available")

        current = self.pseudonym_certificates[self.current_pseudonym_index]

        # Check if rotation is needed
        if (datetime.utcnow() > current['valid_until'] or
            current['usage_count'] > 100):
            self.current_pseudonym_index = (
                (self.current_pseudonym_index + 1) %
                len(self.pseudonym_certificates)
            )
            current = self.pseudonym_certificates[self.current_pseudonym_index]

        return current

    def sign_message(self, message: dict) -> dict:
        """
        Sign V2X message using current pseudonym certificate.

        Args:
            message: V2X message dictionary (BSM, DENM, etc.)

        Returns:
            dict: Signed message with certificate chain
        """
        pseudonym = self.get_current_pseudonym()

        # Serialize message for signing
        message_bytes = json.dumps(message, sort_keys=True).encode()

        # Sign with pseudonym private key
        signature = pseudonym['private_key'].sign(
            message_bytes,
            ec.ECDSA(hashes.SHA256())
        )

        # Increment usage counter
        pseudonym['usage_count'] += 1

        # Return signed message package
        signed_message = {
            'message': message,
            'signature': signature.hex(),
            'certificate': pseudonym['certificate'].public_bytes(
                serialization.Encoding.PEM
            ).decode(),
            'timestamp': datetime.utcnow().isoformat()
        }

        return signed_message

    def verify_message(self, signed_message: dict, crl: set) -> tuple:
        """
        Verify incoming V2X message.

        Args:
            signed_message: Signed message package
            crl: Certificate Revocation List

        Returns:
            tuple: (is_valid: bool, verification_time_ms: float)
        """
        start_time = time.time()

        try:
            # Extract components
            message = signed_message['message']
            signature = bytes.fromhex(signed_message['signature'])
            cert_pem = signed_message['certificate']

            # Load certificate
            cert = x509.load_pem_x509_certificate(
                cert_pem.encode(),
                default_backend()
            )

            # Check certificate revocation
            cert_serial = cert.serial_number
            if cert_serial in crl:
                return False, (time.time() - start_time) * 1000

            # Check certificate validity period
            now = datetime.utcnow()
            if now < cert.not_valid_before or now > cert.not_valid_after:
                return False, (time.time() - start_time) * 1000

            # Verify signature
            message_bytes = json.dumps(message, sort_keys=True).encode()
            public_key = cert.public_key()

            public_key.verify(
                signature,
                message_bytes,
                ec.ECDSA(hashes.SHA256())
            )

            verification_time = (time.time() - start_time) * 1000
            return True, verification_time

        except Exception as e:
            verification_time = (time.time() - start_time) * 1000
            print(f"Verification failed: {e}")
            return False, verification_time


class VehiclePKI_CA:
    """
    Certificate Authority for Vehicle PKI.

    Implements a simplified CA based on ETSI TS 102 940/941.
    """

    def __init__(self, name: str = "CVIN-Test-CA"):
        self.name = name
        self.ca_private_key = None
        self.ca_certificate = None
        self.issued_certificates = {}
        self.certificate_revocation_list = set()
        self._initialize_ca()

    def _initialize_ca(self):
        """Initialize CA with self-signed root certificate."""
        # Generate CA keypair
        self.ca_private_key = ec.generate_private_key(
            ec.SECP256R1(),
            default_backend()
        )

        # Create self-signed root certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, self.name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CVIN Testbed"),
        ])

        self.ca_certificate = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            self.ca_private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=3650)  # 10 years
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).sign(self.ca_private_key, hashes.SHA256(), default_backend())

    def issue_enrollment_certificate(self, csr: x509.CertificateSigningRequest):
        """
        Issue long-term enrollment certificate to vehicle.

        Args:
            csr: Certificate Signing Request from vehicle

        Returns:
            x509.Certificate: Issued enrollment certificate
        """
        cert = x509.CertificateBuilder().subject_name(
            csr.subject
        ).issuer_name(
            self.ca_certificate.subject
        ).public_key(
            csr.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)  # 1 year
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        ).sign(self.ca_private_key, hashes.SHA256(), default_backend())

        self.issued_certificates[cert.serial_number] = cert
        return cert

    def issue_pseudonym_certificate(self, csr: x509.CertificateSigningRequest,
                                   validity_hours: int = 1):
        """
        Issue short-lived pseudonym certificate.

        Args:
            csr: Certificate Signing Request
            validity_hours: Certificate validity period

        Returns:
            x509.Certificate: Issued pseudonym certificate
        """
        cert = x509.CertificateBuilder().subject_name(
            csr.subject
        ).issuer_name(
            self.ca_certificate.subject
        ).public_key(
            csr.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(hours=validity_hours)
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        ).sign(self.ca_private_key, hashes.SHA256(), default_backend())

        self.issued_certificates[cert.serial_number] = cert
        return cert

    def revoke_certificate(self, serial_number: int):
        """Add certificate to revocation list."""
        self.certificate_revocation_list.add(serial_number)

    def get_crl(self) -> set:
        """Get current Certificate Revocation List."""
        return self.certificate_revocation_list.copy()


# Performance metrics collection
class IdentityMetrics:
    """Collect performance metrics for identity operations."""

    def __init__(self):
        self.metrics = {
            'enrollment_time': [],
            'pseudonym_request_time': [],
            'signing_time': [],
            'verification_time': [],
            'certificate_size': [],
            'signature_size': []
        }

    def record_metric(self, metric_name: str, value: float):
        """Record a metric value."""
        if metric_name in self.metrics:
            self.metrics[metric_name].append(value)

    def get_statistics(self) -> dict:
        """Get statistical summary of metrics."""
        import numpy as np

        stats = {}
        for metric_name, values in self.metrics.items():
            if values:
                stats[metric_name] = {
                    'mean': np.mean(values),
                    'median': np.median(values),
                    'std': np.std(values),
                    'min': np.min(values),
                    'max': np.max(values),
                    'count': len(values)
                }
        return stats


if __name__ == "__main__":
    # Example usage
    print("=== Standard PKI Identity System Test ===\n")

    # Initialize CA
    ca = VehiclePKI_CA("CVIN-Test-CA")
    print(f"✓ Certificate Authority initialized: {ca.name}")

    # Create vehicle identity
    vehicle = VehiclePKIIdentity("V001")
    print(f"✓ Vehicle identity created: {vehicle.vehicle_id}")

    # Enrollment
    vehicle.generate_keypair()
    enrollment_cert = vehicle.request_enrollment_certificate(ca)
    print(f"✓ Enrollment certificate issued (Serial: {enrollment_cert.serial_number})")

    # Request pseudonym certificates
    pseudonyms = vehicle.request_pseudonym_certificates(ca, count=20)
    print(f"✓ {len(pseudonyms)} pseudonym certificates issued")

    # Sign a message (BSM)
    bsm = {
        'msgID': 'BasicSafetyMessage',
        'timestamp': datetime.utcnow().isoformat(),
        'position': {'lat': 49.2827, 'lon': -123.1207},
        'speed': 50,  # km/h
        'heading': 90
    }

    signed_bsm = vehicle.sign_message(bsm)
    print(f"✓ BSM signed with pseudonym certificate")

    # Verify message
    is_valid, verify_time = vehicle.verify_message(signed_bsm, ca.get_crl())
    print(f"✓ Message verification: {is_valid} (took {verify_time:.2f} ms)")

    print("\n=== Test Complete ===")
