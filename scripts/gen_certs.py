"""
Generate self-signed mTLS certificates for FedPedia-XAI Flower federation.

Usage:
    python scripts/gen_certs.py

Outputs to certs/ directory:
    certs/ca.crt          — Certificate Authority public cert (shared with everyone)
    certs/server.crt      — FL server public cert
    certs/server.key      — FL server private key
    certs/hospital_1.crt  — Hospital-1 client public cert
    certs/hospital_1.key  — Hospital-1 client private key
    certs/hospital_2.crt  — Hospital-2 client public cert
    certs/hospital_2.key  — Hospital-2 client private key
    certs/hospital_3.crt  — Hospital-3 client public cert
    certs/hospital_3.key  — Hospital-3 client private key

Requires: cryptography>=42 (pip install cryptography)
"""

import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERTS_DIR = Path(__file__).parent.parent / "certs"
KEY_SIZE = 4096
VALIDITY_DAYS = 825  # ~2.25 years — Apple/Chrome max for server certs


def _generate_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)


def _save_key(key: rsa.RSAPrivateKey, path: Path) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    print(f"  [key]  {path}")


def _save_cert(cert: x509.Certificate, path: Path) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"  [cert] {path}")


def _subject(cn: str) -> x509.Name:
    return x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "FedPedia-XAI"),
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
        ]
    )


def _validity() -> tuple[datetime.datetime, datetime.datetime]:
    now = datetime.datetime.now(datetime.UTC)
    return now, now + datetime.timedelta(days=VALIDITY_DAYS)


def generate_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    """Create the root Certificate Authority."""
    print("\n[1/4] Generating Certificate Authority (CA)...")
    key = _generate_key()
    not_before, not_after = _validity()
    subject = issuer = _subject("FedPedia-XAI Root CA")
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    _save_key(key, CERTS_DIR / "ca.key")
    _save_cert(cert, CERTS_DIR / "ca.crt")
    return key, cert


def generate_server_cert(
    ca_key: rsa.RSAPrivateKey,
    ca_cert: x509.Certificate,
) -> None:
    """Create the FL server certificate, signed by the CA."""
    print("\n[2/4] Generating FL Server certificate...")
    key = _generate_key()
    not_before, not_after = _validity()
    cert = (
        x509.CertificateBuilder()
        .subject_name(_subject("fl-server"))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("fl_server"),
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    _save_key(key, CERTS_DIR / "server.key")
    _save_cert(cert, CERTS_DIR / "server.crt")


def generate_client_cert(
    node_id: str,
    ca_key: rsa.RSAPrivateKey,
    ca_cert: x509.Certificate,
) -> None:
    """Create a hospital node client certificate, signed by the CA."""
    key = _generate_key()
    not_before, not_after = _validity()
    cert = (
        x509.CertificateBuilder()
        .subject_name(_subject(node_id))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    _save_key(key, CERTS_DIR / f"{node_id}.key")
    _save_cert(cert, CERTS_DIR / f"{node_id}.crt")


def main() -> None:
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Certificate output directory: {CERTS_DIR.resolve()}")

    ca_key, ca_cert = generate_ca()
    generate_server_cert(ca_key, ca_cert)

    hospital_nodes = ["hospital_1", "hospital_2", "hospital_3"]
    print(f"\n[3/4] Generating {len(hospital_nodes)} hospital node client certificates...")
    for node_id in hospital_nodes:
        generate_client_cert(node_id, ca_key, ca_cert)
        print(f"  Generated certs for {node_id}")

    print("\n[4/4] Done! Add 'certs/' to your .gitignore to keep keys private.")
    print("\nSet these env vars before running FL:")
    print("  FL_USE_MTLS=true")
    print(f"  FL_CA_CERT_PATH={CERTS_DIR / 'ca.crt'}")
    print(f"  FL_SERVER_CERT_PATH={CERTS_DIR / 'server.crt'}")
    print(f"  FL_SERVER_KEY_PATH={CERTS_DIR / 'server.key'}")
    print(f"  FL_CLIENT_CERT_PATH={CERTS_DIR / 'hospital_1.crt'}  (per node)")
    print(f"  FL_CLIENT_KEY_PATH={CERTS_DIR / 'hospital_1.key'}   (per node)")


if __name__ == "__main__":
    main()
