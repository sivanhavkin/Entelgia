# tests/test_memory_security.py
"""
Tests for memory security module.

Tests HMAC-SHA256 signature creation and validation
to ensure memory integrity and tamper detection.
"""

import pytest
from memory_security import create_signature, validate_signature


class TestSignatureCreation:
    """Tests for signature creation."""

    def test_create_signature_success(self, test_secret_key, sample_message):
        """Test successful signature creation."""
        signature = create_signature(sample_message, test_secret_key)

        assert signature is not None
        assert len(signature) == 64  # SHA256 hex = 64 characters
        assert isinstance(signature, str)
        assert all(c in "0123456789abcdef" for c in signature)

    def test_create_signature_deterministic(self, test_secret_key, sample_message):
        """Test that signature creation is deterministic."""
        sig1 = create_signature(sample_message, test_secret_key)
        sig2 = create_signature(sample_message, test_secret_key)

        assert sig1 == sig2

    def test_create_signature_different_messages(self, test_secret_key):
        """Test that different messages produce different signatures."""
        sig1 = create_signature("message 1", test_secret_key)
        sig2 = create_signature("message 2", test_secret_key)

        assert sig1 != sig2

    def test_create_signature_empty_message(self, test_secret_key):
        """Test that empty message raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            create_signature("", test_secret_key)

    def test_create_signature_empty_key(self, sample_message):
        """Test that empty key raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            create_signature(sample_message, "")

    def test_create_signature_none_message(self, test_secret_key):
        """Test that None message raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            create_signature(None, test_secret_key)

    def test_create_signature_none_key(self, sample_message):
        """Test that None key raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            create_signature(sample_message, None)


class TestSignatureValidation:
    """Tests for signature validation."""

    def test_validate_signature_success(self, test_secret_key, sample_message):
        """Test successful signature validation."""
        signature = create_signature(sample_message, test_secret_key)
        is_valid = validate_signature(sample_message, test_secret_key, signature)

        assert is_valid is True

    def test_validate_signature_wrong_key(self, test_secret_key, sample_message):
        """Test that wrong key fails validation."""
        signature = create_signature(sample_message, test_secret_key)
        is_valid = validate_signature(sample_message, "wrong_key", signature)

        assert is_valid is False

    def test_validate_signature_tampered_message(self, test_secret_key, sample_message):
        """Test that tampered message fails validation."""
        signature = create_signature(sample_message, test_secret_key)
        is_valid = validate_signature("Tampered message!", test_secret_key, signature)

        assert is_valid is False

    def test_validate_signature_tampered_signature(
        self, test_secret_key, sample_message
    ):
        """Test that tampered signature fails validation."""
        signature = create_signature(sample_message, test_secret_key)
        tampered_sig = signature[:-1] + "x"  # Change last character
        is_valid = validate_signature(sample_message, test_secret_key, tampered_sig)

        assert is_valid is False

    def test_validate_signature_none_message(self, test_secret_key):
        """Test that None message returns False."""
        is_valid = validate_signature(None, test_secret_key, "somesig")
        assert is_valid is False

    def test_validate_signature_none_key(self, sample_message):
        """Test that None key returns False."""
        is_valid = validate_signature(sample_message, None, "somesig")
        assert is_valid is False

    def test_validate_signature_none_signature(self, test_secret_key, sample_message):
        """Test that None signature returns False."""
        is_valid = validate_signature(sample_message, test_secret_key, None)
        assert is_valid is False

    def test_validate_signature_empty_values(self):
        """Test that empty strings return False."""
        assert validate_signature("", "key", "sig") is False
        assert validate_signature("msg", "", "sig") is False
        assert validate_signature("msg", "key", "") is False

    def test_validate_signature_invalid_hex(self, test_secret_key, sample_message):
        """Test that invalid hex signature returns False."""
        is_valid = validate_signature(
            sample_message, test_secret_key, "not_hex_string!"
        )
        assert is_valid is False


class TestSecurityProperties:
    """Tests for cryptographic security properties."""

    def test_signature_uniqueness(self, test_secret_key):
        """Test that different inputs produce different signatures."""
        messages = ["msg1", "msg2", "msg3", "msg4", "msg5"]
        signatures = [create_signature(msg, test_secret_key) for msg in messages]

        # All signatures should be unique
        assert len(set(signatures)) == len(signatures)

    def test_key_sensitivity(self, sample_message):
        """Test that different keys produce different signatures."""
        keys = ["key1", "key2", "key3", "key4", "key5"]
        signatures = [create_signature(sample_message, key) for key in keys]

        # All signatures should be unique
        assert len(set(signatures)) == len(signatures)

    def test_unicode_support(self, test_secret_key):
        """Test that unicode messages are handled correctly."""
        messages = [
            "שלום עולם",  # Hebrew
            "Hello 世界",  # Mixed
            "مرحبا",  # Arabic
            "🎉🎊✨",  # Emojis
        ]

        for msg in messages:
            signature = create_signature(msg, test_secret_key)
            assert len(signature) == 64
            assert validate_signature(msg, test_secret_key, signature)
