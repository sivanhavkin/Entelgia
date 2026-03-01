# tests/test_chat_endpoint.py
"""
Tests for the POST /api/v1/chat endpoint.

Validates that the endpoint:
- Returns a response with the "response" key
- Does not start the dialogue engine or multi-agent loops
- Returns 400 for empty messages
- Does not block the /api/health endpoint
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

import pytest

try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
class TestChatEndpoint:
    """Tests for POST /api/v1/chat."""

    def _get_app(self):
        """Import and return the FastAPI app."""
        import Entelgia_production_meta as epm
        assert epm.FASTAPI_AVAILABLE, "FastAPI must be available for these tests"
        return epm.app

    def test_chat_returns_response_key(self):
        """Endpoint returns a JSON object with a 'response' key."""
        app = self._get_app()
        client = TestClient(app)

        with patch("Entelgia_production_meta.LLM") as MockLLM:
            mock_instance = MagicMock()
            mock_instance.generate.return_value = "Fixy's answer here."
            MockLLM.return_value = mock_instance

            resp = client.post("/api/v1/chat", json={"message": "What is truth?"})

        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert data["response"] == "Fixy's answer here."

    def test_chat_empty_message_returns_400(self):
        """Endpoint returns HTTP 400 when 'message' is empty."""
        app = self._get_app()
        client = TestClient(app)

        resp = client.post("/api/v1/chat", json={"message": ""})
        assert resp.status_code == 400

    def test_chat_whitespace_message_returns_400(self):
        """Endpoint returns HTTP 400 when 'message' is whitespace only."""
        app = self._get_app()
        client = TestClient(app)

        resp = client.post("/api/v1/chat", json={"message": "   "})
        assert resp.status_code == 400

    def test_chat_accepts_optional_session_id(self):
        """Endpoint accepts an optional session_id field without error."""
        app = self._get_app()
        client = TestClient(app)

        with patch("Entelgia_production_meta.LLM") as MockLLM:
            mock_instance = MagicMock()
            mock_instance.generate.return_value = "Response with session."
            MockLLM.return_value = mock_instance

            resp = client.post(
                "/api/v1/chat",
                json={"message": "Hello Fixy", "session_id": "test-session-123"},
            )

        assert resp.status_code == 200
        assert "response" in resp.json()

    def test_chat_does_not_call_main_script(self):
        """Endpoint must not instantiate MainScript (the dialogue engine)."""
        app = self._get_app()
        client = TestClient(app)

        with patch("Entelgia_production_meta.LLM") as MockLLM, \
             patch("Entelgia_production_meta.MainScript") as MockMain:
            mock_instance = MagicMock()
            mock_instance.generate.return_value = "OK"
            MockLLM.return_value = mock_instance

            client.post("/api/v1/chat", json={"message": "Test"})

        MockMain.assert_not_called()

    def test_health_endpoint_still_responds(self):
        """The /api/health endpoint must remain reachable after adding /api/v1/chat."""
        app = self._get_app()
        client = TestClient(app)

        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
