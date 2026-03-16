# tests/conftest.py
"""
Pytest configuration and shared fixtures.

This file is automatically discovered by pytest and provides
fixtures that are available to all test modules.
"""

import os
import pytest
import tempfile


@pytest.fixture(autouse=True)
def reset_trigger_cooldown():
    """Reset the fixy_research_trigger cooldown state before every test.

    This prevents cooldown state set in one test from bleeding into another,
    ensuring deterministic test results regardless of execution order.
    Also resets the web_research module-level caches and the failed-URL
    blacklist in web_tool for the same reason.
    Also clears the circularity guard per-agent response history and rotation
    index so that previous test responses cannot influence circularity detection.
    """
    from entelgia.fixy_research_trigger import clear_trigger_cooldown
    from entelgia.web_research import clear_research_caches
    from entelgia.web_tool import clear_failed_urls
    from entelgia.circularity_guard import clear_history as _cg_clear_history
    import entelgia.circularity_guard as _cg

    clear_trigger_cooldown()
    clear_research_caches()
    clear_failed_urls()
    _cg_clear_history()
    _cg._new_angle_index = 0
    yield
    clear_trigger_cooldown()
    clear_research_caches()
    clear_failed_urls()
    _cg_clear_history()
    _cg._new_angle_index = 0


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
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
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
        "context": [],
    }


@pytest.fixture
def sample_memory_entry():
    """Sample memory entry for testing."""
    return {
        "id": "test_123",
        "content": "Test memory content",
        "emotion": "neutral",
        "importance": 0.5,
        "timestamp": "2026-02-13T10:30:00Z",
    }
