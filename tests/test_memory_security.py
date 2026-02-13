"""Tests for memory security module."""
import pytest
from memory_security import create_signature, validate_signature


def test_create_signature(test_secret_key, sample_message):
    """Test signature creation."""
    signature = create_signature(sample_message, test_secret_key)
    
    assert signature is not None
    assert len(signature) == 64  # SHA256 hex = 64 chars
    assert isinstance(signature, str)


def test_validate_signature_success(test_secret_key, sample_message):
    """Test successful signature validation."""
    signature = create_signature(sample_message, test_secret_key)
    is_valid = validate_signature(sample_message, test_secret_key, signature)
    
    assert is_valid is True


def test_validate_signature_wrong_key(test_secret_key, sample_message):
    """Test signature validation with wrong key."""
    signature = create_signature(sample_message, test_secret_key)
    is_valid = validate_signature(sample_message, "wrong_key", signature)
    
    assert is_valid is False


def test_validate_signature_tampered_message(test_secret_key, sample_message):
    """Test signature validation with tampered message."""
    signature = create_signature(sample_message, test_secret_key)
    is_valid = validate_signature("Tampered message", test_secret_key, signature)
    
    assert is_valid is False


def test_create_signature_empty_message(test_secret_key):
    """Test signature creation with empty message."""
    with pytest.raises(ValueError):
        create_signature("", test_secret_key)


def test_create_signature_empty_key(sample_message):
    """Test signature creation with empty key."""
    with pytest.raises(ValueError):
        create_signature(sample_message, "")


def test_validate_signature_none_values():
    """Test signature validation with None values."""
    assert validate_signature(None, "key", "sig") is False
    assert validate_signature("msg", None, "sig") is False
    assert validate_signature("msg", "key", None) is False
