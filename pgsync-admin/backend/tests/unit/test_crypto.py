"""Unit tests for crypto service."""

import pytest
from backend.utils.crypto import crypto_service


class TestCryptoService:
    """Test encryption/decryption."""

    def test_encrypt_decrypt(self):
        """Test basic encrypt/decrypt cycle."""
        plaintext = "my-secret-password"

        encrypted = crypto_service.encrypt(plaintext)
        decrypted = crypto_service.decrypt(encrypted)

        assert encrypted != plaintext
        assert decrypted == plaintext

    def test_encrypt_different_each_time(self):
        """Test that encryption produces different ciphertexts."""
        plaintext = "password123"

        encrypted1 = crypto_service.encrypt(plaintext)
        encrypted2 = crypto_service.encrypt(plaintext)

        # Different ciphertexts (due to IV)
        assert encrypted1 != encrypted2

        # But both decrypt to same plaintext
        assert crypto_service.decrypt(encrypted1) == plaintext
        assert crypto_service.decrypt(encrypted2) == plaintext

    def test_decrypt_invalid_ciphertext(self):
        """Test decrypting invalid ciphertext."""
        with pytest.raises(Exception):
            crypto_service.decrypt("invalid-base64-ciphertext")
