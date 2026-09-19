"""Application-layer AES-256-GCM field encryption for sensitive patient PHI.

Why application-layer encryption (vs. TDE)?
--------------------------------------------
Transparent Database Encryption (TDE / pgcrypto at the storage level) protects
data *on disk* but any process or user with valid database credentials can still
read plaintext values.  Application-layer encryption additionally protects data
from:
  - Direct database access by DBAs or compromised DB credentials
  - Database backup files and snapshots
  - Read replicas or analytics exports

Algorithm choice — AES-256-GCM:
---------------------------------
AES-256-GCM is an authenticated encryption scheme (AEAD).  It provides:
  - Confidentiality: 256-bit AES key makes brute-force infeasible
  - Integrity: 128-bit authentication tag detects tampering or bit-flips
  - Random nonce: a fresh 96-bit nonce is generated per encryption, so two
    identical plaintext values always produce different ciphertexts.

Ciphertext wire format (base64-encoded):
    [ nonce (12 bytes) | tag (16 bytes) | ciphertext (variable) ]

Environment variable:
    PATIENT_FIELD_ENCRYPTION_KEY — 32 raw bytes encoded as URL-safe base64.
    Generate with: python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

SQLAlchemy integration:
    Use ``EncryptedFloat`` as the ``type_`` argument in ``mapped_column()``.
    It transparently encrypts on INSERT/UPDATE and decrypts on SELECT.
    ``None`` values are stored as SQL NULL without any encryption overhead.
"""

import base64
import os
import struct

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import String, TypeDecorator

_NONCE_BYTES = 12  # 96-bit nonce recommended for GCM
_ENV_KEY_NAME = "PATIENT_FIELD_ENCRYPTION_KEY"


def _load_key() -> bytes:
    """Load and validate the 32-byte AES key from the environment."""
    raw = os.environ.get(_ENV_KEY_NAME, "")
    if not raw:
        raise RuntimeError(
            f"Missing environment variable '{_ENV_KEY_NAME}'. "
            "Generate one with: python -c \"import secrets,base64; "
            "print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())\""
        )
    try:
        key = base64.urlsafe_b64decode(raw + "==")  # lenient padding
    except Exception as exc:
        raise RuntimeError(
            f"'{_ENV_KEY_NAME}' is not valid URL-safe base64."
        ) from exc
    if len(key) != 32:
        raise RuntimeError(
            f"'{_ENV_KEY_NAME}' must decode to exactly 32 bytes (got {len(key)})."
        )
    return key


class FieldEncryptor:
    """Encrypt and decrypt individual float PHI values using AES-256-GCM."""

    def __init__(self) -> None:
        self._key = _load_key()
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, value: float | None) -> str | None:
        """Encrypt a float value to a URL-safe base64 ciphertext string.

        Returns ``None`` if ``value`` is ``None`` (SQL NULL preservation).
        """
        if value is None:
            return None
        # Represent float as 8-byte IEEE 754 double-precision little-endian
        plaintext = struct.pack("<d", float(value))
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        # Wire format: nonce + ciphertext (GCM appends 16-byte tag internally)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, blob: str | None) -> float | None:
        """Decrypt a base64 ciphertext blob back to a float value.

        Returns ``None`` if ``blob`` is ``None`` (SQL NULL preservation).
        Raises ``ValueError`` on authentication failure (tampered data).
        """
        if blob is None:
            return None
        raw = base64.urlsafe_b64decode(blob + "==")
        nonce = raw[:_NONCE_BYTES]
        ciphertext = raw[_NONCE_BYTES:]
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as exc:
            raise ValueError(
                "Decryption failed — data may be corrupted or tampered with."
            ) from exc
        return struct.unpack("<d", plaintext)[0]


# Module-level singleton — created lazily on first use so that import of this
# module does not immediately crash if PATIENT_FIELD_ENCRYPTION_KEY is absent
# (e.g. in unit tests that mock the env).
_encryptor: FieldEncryptor | None = None


def get_encryptor() -> FieldEncryptor:
    """Return the process-wide FieldEncryptor instance (created on first call)."""
    global _encryptor  # noqa: PLW0603
    if _encryptor is None:
        _encryptor = FieldEncryptor()
    return _encryptor


class EncryptedFloat(TypeDecorator):
    """SQLAlchemy TypeDecorator that transparently encrypts floats as AES-256-GCM ciphertext.

    Stores values as ``Text`` (base64 ciphertext) in PostgreSQL.
    Reads values back as Python ``float | None``.

    Usage in a model::

        from backend.app.core.encryption import EncryptedFloat

        class Patient(Base):
            bp: Mapped[float | None] = mapped_column(EncryptedFloat, nullable=True)
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: float | None, dialect) -> str | None:  # noqa: ANN001
        """Called before INSERT/UPDATE — encrypt the Python float."""
        return get_encryptor().encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> float | None:  # noqa: ANN001
        """Called after SELECT — decrypt the stored ciphertext back to float."""
        return get_encryptor().decrypt(value)
