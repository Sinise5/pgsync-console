"""Cryptography utilities for password encryption/decryption."""

from cryptography.fernet import Fernet
from backend.config import settings


class CryptoService:
    """Encrypt/decrypt sensitive data using Fernet."""

    def __init__(self) -> None:
        """Initialize cipher with encryption key."""
        settings.validate_encryption_key()
        self.cipher = Fernet(settings.encryption_key.encode())

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext to ciphertext."""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext to plaintext."""
        return self.cipher.decrypt(ciphertext.encode()).decode()


# Global instance
crypto_service = CryptoService()
