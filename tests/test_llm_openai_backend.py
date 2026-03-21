# tests/test_llm_openai_backend.py
"""
Tests for LLM.generate() with the OpenAI backend.

Validates:
  1. Normal response: choices[0].message.content is returned and stripped.
  2. None content (tool-call response): returns empty string without crashing.
  3. Empty choices list: returns empty string.
  4. Missing choices key in response: returns empty string.
  5. Missing message key in choice: returns empty string.
  6. Correct endpoint URL is used (Chat Completions, not Responses API).
  7. Correct request body format (messages, not input).
  8. Authorization header uses the openai_api_key.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch

import Entelgia_production_meta as _meta
from Entelgia_production_meta import LLM, Config, MetricsTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _make_openai_cfg() -> Config:
    """Return a minimal Config wired for the OpenAI backend."""
    cfg = object.__new__(Config)
    cfg.llm_backend = "openai"
    cfg.openai_url = _OPENAI_URL
    cfg.openai_api_key = "sk-test-key"
    cfg.ollama_url = "http://localhost:11434/api/generate"
    cfg.grok_url = "https://api.x.ai/v1/responses"
    cfg.grok_api_key = ""
    cfg.llm_max_retries = 1
    cfg.llm_timeout = 30
    cfg.emotion_cache_ttl = 3600
    cfg.cache_size = 100
    cfg.debug = False
    return cfg


def _make_llm(cfg: Config) -> LLM:
    metrics = MagicMock(spec=MetricsTracker)
    return LLM(cfg, metrics)


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Return a mock requests.Response."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# 1. Normal response
# ---------------------------------------------------------------------------


class TestOpenAINormalResponse:
    def test_returns_content_string(self):
        cfg = _make_openai_cfg()
        llm = _make_llm(cfg)
        resp = _mock_response({
            "choices": [
                {"message": {"role": "assistant", "content": "  Hello world  "}, "finish_reason": "stop"}
            ]
        })
        with patch.object(llm._executor, "submit", return_value=_future(resp)):
            result = llm.generate("gpt-4.1", "Say hello.", use_cache=False)
        assert result == "Hello world"

    def test_strips_whitespace(self):
        cfg = _make_openai_cfg()
        llm = _make_llm(cfg)
        resp = _mock_response({
            "choices": [
                {"message": {"role": "assistant", "content": "\n  Padded response.\n\n"}, "finish_reason": "stop"}
            ]
        })
        with patch.object(llm._executor, "submit", return_value=_future(resp)):
            result = llm.generate("gpt-4.1", "Test.", use_cache=False)
        assert result == "Padded response."


# ---------------------------------------------------------------------------
# 2. None content — must NOT crash (the bug fixed by this PR)
# ---------------------------------------------------------------------------


class TestOpenAINoneContent:
    def test_none_content_returns_empty_string(self):
        """When content is null (e.g. tool-call response), generate() must
        return '' rather than crashing with AttributeError on None.strip()."""
        cfg = _make_openai_cfg()
        llm = _make_llm(cfg)
        resp = _mock_response({
            "choices": [
                {"message": {"role": "assistant", "content": None}, "finish_reason": "tool_calls"}
            ]
        })
        with patch.object(llm._executor, "submit", return_value=_future(resp)):
            result = llm.generate("gpt-4.1", "Use a tool.", use_cache=False)
        assert result == ""


# ---------------------------------------------------------------------------
# 3–5. Malformed / empty response shapes
# ---------------------------------------------------------------------------


class TestOpenAIEdgeCases:
    def test_empty_choices_list(self):
        cfg = _make_openai_cfg()
        llm = _make_llm(cfg)
        resp = _mock_response({"choices": []})
        with patch.object(llm._executor, "submit", return_value=_future(resp)):
            result = llm.generate("gpt-4.1", "Test.", use_cache=False)
        assert result == ""

    def test_missing_choices_key(self):
        cfg = _make_openai_cfg()
        llm = _make_llm(cfg)
        resp = _mock_response({})
        with patch.object(llm._executor, "submit", return_value=_future(resp)):
            result = llm.generate("gpt-4.1", "Test.", use_cache=False)
        assert result == ""

    def test_missing_message_key_in_choice(self):
        cfg = _make_openai_cfg()
        llm = _make_llm(cfg)
        resp = _mock_response({"choices": [{"finish_reason": "stop"}]})
        with patch.object(llm._executor, "submit", return_value=_future(resp)):
            result = llm.generate("gpt-4.1", "Test.", use_cache=False)
        assert result == ""

    def test_empty_content_string(self):
        cfg = _make_openai_cfg()
        llm = _make_llm(cfg)
        resp = _mock_response({
            "choices": [
                {"message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}
            ]
        })
        with patch.object(llm._executor, "submit", return_value=_future(resp)):
            result = llm.generate("gpt-4.1", "Test.", use_cache=False)
        assert result == ""


# ---------------------------------------------------------------------------
# 6–8. Request shape verification
# ---------------------------------------------------------------------------


class TestOpenAIRequestShape:
    def test_uses_chat_completions_url(self):
        """The request must go to /v1/chat/completions, not /v1/responses."""
        cfg = _make_openai_cfg()
        llm = _make_llm(cfg)
        resp = _mock_response({
            "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]
        })

        captured = {}

        def fake_submit(fn, url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return _future(resp)

        with patch.object(llm._executor, "submit", side_effect=fake_submit):
            llm.generate("gpt-4.1", "prompt", use_cache=False)

        assert captured["url"] == _OPENAI_URL
        assert "/v1/chat/completions" in captured["url"]
        assert "/v1/responses" not in captured["url"]

    def test_request_body_uses_messages_not_input(self):
        """The JSON body must use 'messages', not 'input' (Responses API key)."""
        cfg = _make_openai_cfg()
        llm = _make_llm(cfg)
        resp = _mock_response({
            "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]
        })

        captured = {}

        def fake_submit(fn, url, **kwargs):
            captured["json"] = kwargs.get("json", {})
            return _future(resp)

        with patch.object(llm._executor, "submit", side_effect=fake_submit):
            llm.generate("gpt-4.1", "hello", use_cache=False)

        body = captured["json"]
        assert "messages" in body, "Request body must contain 'messages' key"
        assert "input" not in body, "Request body must NOT contain 'input' key (Responses API)"
        assert body["messages"] == [{"role": "user", "content": "hello"}]

    def test_authorization_header_uses_openai_api_key(self):
        """Bearer token must be the openai_api_key."""
        cfg = _make_openai_cfg()
        llm = _make_llm(cfg)
        resp = _mock_response({
            "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]
        })

        captured = {}

        def fake_submit(fn, url, **kwargs):
            captured["headers"] = kwargs.get("headers", {})
            return _future(resp)

        with patch.object(llm._executor, "submit", side_effect=fake_submit):
            llm.generate("gpt-4.1", "hello", use_cache=False)

        auth = captured["headers"].get("Authorization", "")
        assert auth == f"Bearer {cfg.openai_api_key}"


# ---------------------------------------------------------------------------
# Utility — wrap a value in a completed Future
# ---------------------------------------------------------------------------


def _future(value):
    """Return a concurrent.futures.Future that is already resolved with *value*."""
    import concurrent.futures
    f = concurrent.futures.Future()
    f.set_result(value)
    return f
