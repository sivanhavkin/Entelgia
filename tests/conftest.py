"""Pytest configuration and fixtures."""
import pytest
import os

@pytest.fixture
def test_secret_key():
    """Provide a test secret key."""
    return "test_secret_key_12345"

@pytest.fixture
def sample_message():
    """Provide a sample message for testing."""
    return "Hello, Entelgia!"
