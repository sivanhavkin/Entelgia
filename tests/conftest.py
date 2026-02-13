# tests/conftest.py
"""
Pytest configuration and shared fixtures.

This file is automatically discovered by pytest and provides
fixtures that are available to all test modules.
"""

import pytest
import os
import tempfile
from pathlib import Path


@pytest.fixture
def test_secret_key():
    """Provide a test secret key for HMAC operations."""
    return "test_secret_key_for_hmac_operations_12345"


@pytest.fixture
def sample_message():
    """Provide a sample message for testing."""
    return "Hello, Entelgia! This is a test message."


@pytest.fixture
def temp_db_path():
    """Provide a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def mock_ollama_response():
    """Mock Ollama API response."""
    return {
        "model": "phi3",
        "response": "This is a test response from the agent.",
        "done": True,
        "context": []
    }


@pytest.fixture
def sample_memory_entry():
    """Sample memory entry for testing."""
    return {
        "id": "test_123",
        "content": "Test memory content",
        "emotion": "neutral",
        "importance": 0.5,
        "timestamp": "2026-02-13T10:30:00Z"
    }
