# tests/test_wavestreamer_adapter.py
"""
Tests for entelgia/wavestreamer_entelgia_fixy_adapter.py

Covers:
  - detect_server_mode: entelgia_api, fixy_remote, RuntimeError
  - create_entelgia_session: success, 404 (non-fatal), network error (non-fatal)
  - call_chat: correct URL + payload for each mode
  - parse_chat_response: entelgia_api uses "response", fixy_remote uses "reply"
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

import pytest
import requests

import entelgia.wavestreamer_entelgia_fixy_adapter as adapter

# ---------------------------------------------------------------------------
# detect_server_mode
# ---------------------------------------------------------------------------


class TestDetectServerMode:
    def _mock_resp(self, status_code: int) -> MagicMock:
        r = MagicMock()
        r.status_code = status_code
        return r

    def test_entelgia_api_when_api_health_returns_200(self):
        with patch("requests.get", return_value=self._mock_resp(200)) as mock_get:
            mode = adapter.detect_server_mode("http://localhost:8000")
        assert mode == "entelgia_api"
        mock_get.assert_called_once_with(
            "http://localhost:8000/api/health", timeout=adapter.ADMIN_TIMEOUT
        )

    def test_fixy_remote_when_api_health_fails_and_health_returns_200(self):
        responses = [self._mock_resp(404), self._mock_resp(200)]
        with patch("requests.get", side_effect=responses):
            mode = adapter.detect_server_mode("http://localhost:8000")
        assert mode == "fixy_remote"

    def test_fixy_remote_when_api_health_raises_and_health_returns_200(self):
        responses = [
            requests.RequestException("connection refused"),
            self._mock_resp(200),
        ]
        with patch("requests.get", side_effect=responses):
            mode = adapter.detect_server_mode("http://localhost:8000")
        assert mode == "fixy_remote"

    def test_raises_runtime_error_when_neither_responds(self):
        with patch(
            "requests.get",
            side_effect=requests.RequestException("unreachable"),
        ):
            with pytest.raises(RuntimeError, match="No known Entelgia/Fixy server"):
                adapter.detect_server_mode("http://nowhere:9999")

    def test_raises_runtime_error_when_both_non_200(self):
        with patch("requests.get", return_value=self._mock_resp(503)):
            with pytest.raises(RuntimeError, match="No known Entelgia/Fixy server"):
                adapter.detect_server_mode("http://localhost:8000")


# ---------------------------------------------------------------------------
# create_entelgia_session
# ---------------------------------------------------------------------------


class TestCreateEntelgiaSession:
    def test_returns_session_id_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"session_id": "abc-123"}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.post", return_value=mock_resp):
            sid = adapter.create_entelgia_session()
        assert sid == "abc-123"

    def test_returns_none_on_404(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("requests.post", return_value=mock_resp):
            sid = adapter.create_entelgia_session()
        assert sid is None

    def test_returns_none_on_network_error(self):
        with patch(
            "requests.post",
            side_effect=requests.RequestException("timeout"),
        ):
            sid = adapter.create_entelgia_session()
        assert sid is None

    def test_returns_none_when_session_id_missing_from_payload(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.post", return_value=mock_resp):
            sid = adapter.create_entelgia_session()
        assert sid is None


# ---------------------------------------------------------------------------
# call_chat
# ---------------------------------------------------------------------------


class TestCallChat:
    def _ok_resp(self, body: dict) -> MagicMock:
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = body
        return r

    def test_entelgia_api_uses_correct_url_and_message_payload(self):
        with patch(
            "requests.post", return_value=self._ok_resp({"response": "ok"})
        ) as mock_post:
            adapter.call_chat("hello", mode="entelgia_api")
        (url,) = mock_post.call_args.args
        kwargs = mock_post.call_args.kwargs
        assert url.endswith("/api/v1/chat")
        assert kwargs["json"] == {"message": "hello"}

    def test_entelgia_api_includes_session_id_when_provided(self):
        with patch(
            "requests.post", return_value=self._ok_resp({"response": "ok"})
        ) as mock_post:
            adapter.call_chat("hello", mode="entelgia_api", session_id="sess-99")
        kwargs = mock_post.call_args.kwargs
        assert kwargs["json"] == {"message": "hello", "session_id": "sess-99"}

    def test_fixy_remote_uses_correct_url_and_text_token_payload(self):
        with patch.dict(os.environ, {"FIXY_REMOTE_TOKEN": "my-token"}):
            # reload the token constant used inside the function
            with patch.object(adapter, "FIXY_REMOTE_TOKEN", "my-token"):
                with patch(
                    "requests.post", return_value=self._ok_resp({"reply": "answer"})
                ) as mock_post:
                    adapter.call_chat("question?", mode="fixy_remote")
        (url,) = mock_post.call_args.args
        kwargs = mock_post.call_args.kwargs
        assert url.endswith("/fixy/say")
        assert kwargs["json"]["text"] == "question?"
        assert kwargs["json"]["token"] == "my-token"

    def test_fixy_remote_does_not_send_message_or_session_id(self):
        with patch.object(adapter, "FIXY_REMOTE_TOKEN", "tok"):
            with patch(
                "requests.post", return_value=self._ok_resp({"reply": "ok"})
            ) as mock_post:
                adapter.call_chat("q", mode="fixy_remote", session_id="s")
        payload = mock_post.call_args.kwargs["json"]
        assert "message" not in payload
        assert "session_id" not in payload


# ---------------------------------------------------------------------------
# parse_chat_response
# ---------------------------------------------------------------------------


class TestParseChatResponse:
    def test_entelgia_api_uses_response_key(self):
        result = adapter.parse_chat_response(
            {"response": "  hello world  "}, mode="entelgia_api"
        )
        assert result == "hello world"

    def test_entelgia_api_returns_empty_string_when_key_missing(self):
        result = adapter.parse_chat_response({}, mode="entelgia_api")
        assert result == ""

    def test_fixy_remote_uses_reply_key(self):
        result = adapter.parse_chat_response(
            {"reply": "  fixy answer  "}, mode="fixy_remote"
        )
        assert result == "fixy answer"

    def test_fixy_remote_returns_empty_string_when_key_missing(self):
        result = adapter.parse_chat_response({}, mode="fixy_remote")
        assert result == ""

    def test_fixy_remote_ignores_response_key(self):
        # In fixy_remote mode the "response" field should be ignored
        result = adapter.parse_chat_response(
            {"response": "wrong", "reply": "correct"}, mode="fixy_remote"
        )
        assert result == "correct"
