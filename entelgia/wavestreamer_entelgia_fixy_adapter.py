#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WaveStreamer → Entelgia Fixy Adapter
=====================================

Bridges the WaveStreamer prediction-market question feed with the Entelgia
Fixy agent.  For each pending WaveStreamer question the adapter:

  1. Creates (or reuses) an Entelgia session via POST /api/sessions.
  2. Sends the question text to Fixy via POST /api/v1/chat.
  3. Submits Fixy's response back to the WaveStreamer API.

Configuration (environment variables or .env file):

  ENTELGIA_BASE_URL     Base URL of the running Entelgia API server.
                        Default: http://localhost:8000

  WAVESTREAMER_API_URL  Base URL of the WaveStreamer API server.
                        Default: http://localhost:9000

  WAVESTREAMER_API_KEY  Optional bearer token for WaveStreamer auth.

Usage:
  python entelgia/wavestreamer_entelgia_fixy_adapter.py
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [adapter] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ENTELGIA_BASE_URL: str = os.getenv("ENTELGIA_BASE_URL", "http://localhost:8000").rstrip(
    "/"
)
WAVESTREAMER_API_URL: str = os.getenv(
    "WAVESTREAMER_API_URL", "http://localhost:9000"
).rstrip("/")
WAVESTREAMER_API_KEY: Optional[str] = os.getenv("WAVESTREAMER_API_KEY")

def _get_int_env(name: str, default: int) -> int:
    """Return an integer environment variable, falling back to *default*."""
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("Invalid value for %s; using default %d", name, default)
        return default


# HTTP timeout (seconds) for Entelgia chat calls – Ollama can be slow
CHAT_TIMEOUT: int = _get_int_env("CHAT_TIMEOUT", 120)
# HTTP timeout (seconds) for fast admin calls (session creation, WaveStreamer fetch)
ADMIN_TIMEOUT: int = _get_int_env("ADMIN_TIMEOUT", 15)


def _wavestreamer_headers() -> Dict[str, str]:
    """Return request headers for the WaveStreamer API."""
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if WAVESTREAMER_API_KEY:
        headers["Authorization"] = f"Bearer {WAVESTREAMER_API_KEY}"
    return headers


# ---------------------------------------------------------------------------
# Entelgia helpers
# ---------------------------------------------------------------------------


def create_entelgia_session() -> Optional[str]:
    """Create a new Entelgia dialogue session.

    Returns the session_id string on success, or None if the call fails
    (the adapter continues without a session in that case).
    """
    url = f"{ENTELGIA_BASE_URL}/api/sessions"
    try:
        resp = requests.post(url, timeout=ADMIN_TIMEOUT)
        resp.raise_for_status()
        session_id = resp.json().get("session_id")
        if not session_id:
            logger.warning(
                "Unexpected response from /api/sessions – no session_id in payload"
            )
        return session_id
    except Exception as exc:
        logger.warning(
            "Could not create Entelgia session (continuing): %s", exc
        )
        return None


def call_entelgia_chat(
    prompt: str, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Send *prompt* to the Entelgia /api/v1/chat endpoint.

    Args:
        prompt:     The message text to send to Fixy.
        session_id: Optional session identifier returned by
                    :func:`create_entelgia_session`.

    Returns:
        The parsed JSON response dict, which includes at minimum:
        ``{"response": str, "session_id": str, "agent": str}``.

    Raises:
        requests.HTTPError: if the server returns a non-2xx status.
    """
    url = f"{ENTELGIA_BASE_URL}/api/v1/chat"
    logger.info("Calling Entelgia /api/v1/chat …")
    payload: Dict[str, Any] = {"message": prompt}
    if session_id:
        payload["session_id"] = session_id
    resp = requests.post(url, json=payload, timeout=CHAT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# WaveStreamer helpers
# ---------------------------------------------------------------------------


def fetch_wavestreamer_questions() -> List[Dict[str, Any]]:
    """Fetch the list of pending questions from WaveStreamer.

    Returns an empty list if the request fails so that the adapter can
    degrade gracefully.
    """
    url = f"{WAVESTREAMER_API_URL}/api/questions/pending"
    try:
        resp = requests.get(
            url, headers=_wavestreamer_headers(), timeout=ADMIN_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        # Support both {"questions": [...]} and a bare list
        if isinstance(data, list):
            return data
        return data.get("questions", [])
    except Exception as exc:
        logger.error("Could not fetch WaveStreamer questions: %s", exc)
        return []


def submit_wavestreamer_answer(question_id: str, answer: str) -> bool:
    """Submit *answer* for *question_id* back to WaveStreamer.

    Returns True on success, False on failure.
    """
    url = f"{WAVESTREAMER_API_URL}/api/questions/{question_id}/answer"
    try:
        resp = requests.post(
            url,
            json={"answer": answer, "agent": "Fixy"},
            headers=_wavestreamer_headers(),
            timeout=ADMIN_TIMEOUT,
        )
        resp.raise_for_status()
        logger.info("Answer submitted for question %s", question_id)
        return True
    except Exception as exc:
        logger.error(
            "Could not submit answer for question %s: %s", question_id, exc
        )
        return False


# ---------------------------------------------------------------------------
# Main adapter loop
# ---------------------------------------------------------------------------


def run_adapter() -> None:
    """Process all pending WaveStreamer questions through the Entelgia Fixy agent."""
    logger.info(
        "Entelgia WaveStreamer adapter starting (server: %s)", ENTELGIA_BASE_URL
    )

    # Create a shared Entelgia session for this run
    session_id = create_entelgia_session()
    if session_id:
        logger.info("Entelgia session created: %s", session_id)

    questions = fetch_wavestreamer_questions()
    if not questions:
        logger.info("No pending questions found – nothing to do.")
        return

    logger.info("Processing %d question(s) …", len(questions))
    success_count = 0
    fail_count = 0

    for question in questions:
        question_id: str = question.get("id", "")
        question_text: str = question.get("text", question.get("question", ""))

        if not question_text:
            logger.warning("Skipping question with no text: %s", question)
            continue

        logger.info(
            "Processing question id=%s: %s…", question_id, question_text[:80]
        )

        prompt = (
            f"Please analyze and answer the following prediction-market question "
            f"as concisely as possible:\n\n{question_text}"
        )

        try:
            chat_response = call_entelgia_chat(prompt, session_id=session_id)
            answer = chat_response.get("response", "").strip()
            if not answer:
                logger.warning("Empty response from Entelgia for question %s", question_id)
                fail_count += 1
                continue
            if submit_wavestreamer_answer(question_id, answer):
                success_count += 1
            else:
                fail_count += 1
        except requests.HTTPError as exc:
            logger.error(
                "HTTP error processing question %s: %s", question_id, exc
            )
            fail_count += 1
        except Exception as exc:
            logger.error(
                "Unexpected error processing question %s: %s", question_id, exc
            )
            fail_count += 1

    logger.info(
        "Adapter finished – success: %d, failed: %d", success_count, fail_count
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        run_adapter()
    except KeyboardInterrupt:
        logger.info("Adapter interrupted by user.")
        sys.exit(0)
    except Exception as exc:
        logger.error("Adapter failed: %s", exc, exc_info=True)
        sys.exit(1)
