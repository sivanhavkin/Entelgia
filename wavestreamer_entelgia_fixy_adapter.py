#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WaveStreamer ↔ Entelgia / Fixy Adapter
=======================================
Connects WaveStreamer to Entelgia via REST API, using Fixy through
Entelgia's /api/v1/chat endpoint, then submits a prediction to
WaveStreamer that passes all WaveStreamer quality gates.

WaveStreamer quality gates enforced:
  1. payload includes prediction (bool) OR selected_option (str)
  2. confidence is int 0-100
  3. reasoning contains EVIDENCE:, ANALYSIS:, COUNTER-EVIDENCE:, BOTTOM LINE:
  4. reasoning length >= 200 characters
  5. reasoning includes at least one https:// URL citation
  6. resolution_protocol contains: criterion, source_of_truth, deadline,
     resolver, edge_cases

Usage:
    WAVESTREAMER_API_KEY=<key> python wavestreamer_entelgia_fixy_adapter.py
"""

import json
import os
import re
import sys

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ENTELGIA_BASE_URL = os.getenv("ENTELGIA_BASE_URL", "http://localhost:8000")
WAVESTREAMER_BASE_URL = os.getenv("WAVESTREAMER_BASE_URL", "https://wavestreamer.ai")
WAVESTREAMER_API_KEY = os.getenv("WAVESTREAMER_API_KEY", "")

ENTELGIA_HEALTH_URL = f"{ENTELGIA_BASE_URL}/api/health"
ENTELGIA_SESSIONS_URL = f"{ENTELGIA_BASE_URL}/api/sessions"
ENTELGIA_CHAT_URL = f"{ENTELGIA_BASE_URL}/api/v1/chat"
WAVESTREAMER_QUESTIONS_URL = f"{WAVESTREAMER_BASE_URL}/api/questions"

# ---------------------------------------------------------------------------
# Step 1 — Check Entelgia health
# ---------------------------------------------------------------------------


def check_entelgia_health() -> bool:
    """Return True when Entelgia is reachable and healthy."""
    try:
        resp = requests.get(ENTELGIA_HEALTH_URL, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"[adapter] Entelgia health check failed: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Step 2 — Fetch open questions from WaveStreamer
# ---------------------------------------------------------------------------


def fetch_open_questions() -> list:
    """Return the list of open WaveStreamer questions."""
    headers = {"X-API-Key": WAVESTREAMER_API_KEY}
    resp = requests.get(
        WAVESTREAMER_QUESTIONS_URL,
        params={"status": "open"},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    # Support both a bare list and {"questions": [...]} envelope
    if isinstance(data, list):
        return data
    return data.get("questions", data.get("results", []))


# ---------------------------------------------------------------------------
# Step 4 — Optionally create an Entelgia session
# ---------------------------------------------------------------------------


def create_entelgia_session() -> str | None:
    """
    Attempt to create an Entelgia session.
    Returns the session id string or None if creation fails.
    """
    try:
        resp = requests.post(ENTELGIA_SESSIONS_URL, json={}, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        # Accept either {"session_id": "..."} or {"id": "..."}
        return payload.get("session_id") or payload.get("id")
    except requests.RequestException as exc:
        print(
            f"[adapter] Could not create Entelgia session (continuing): {exc}",
            file=sys.stderr,
        )
        return None


# ---------------------------------------------------------------------------
# Step 5 — Build strict Fixy prompt
# ---------------------------------------------------------------------------

_STRICT_PROMPT_TEMPLATE = """\
You are Fixy, an analytical AI assistant. A prediction market question has been \
submitted to you. You MUST respond with ONLY valid JSON and nothing else — no \
markdown, no prose, no explanation outside the JSON object.

QUESTION:
{question_text}

OPTIONS (if any):
{options_text}

OUTPUT FORMAT (return exactly this JSON schema):
{{
  "prediction": <true or false — omit if selected_option is used>,
  "selected_option": "<option text — use instead of prediction for multi-option questions>",
  "confidence": <integer 0-100>,
  "reasoning": "<string with ALL four required sections below, minimum 200 characters, \
include at least one https:// URL citation>",
  "resolution_protocol": {{
    "criterion": "<clear resolution criterion>",
    "source_of_truth": "<authoritative source>",
    "deadline": "<ISO-8601 date or description>",
    "resolver": "<who or what resolves the question>",
    "edge_cases": "<list edge cases or state none>"
  }}
}}

REQUIRED reasoning sections (use these exact headings, each on its own line):
EVIDENCE:
<cite at least one URL, e.g. https://example.com/source>
ANALYSIS:
<your analysis>
COUNTER-EVIDENCE:
<opposing evidence>
BOTTOM LINE:
<final conclusion>

Respond with ONLY the JSON object.
"""


def build_fixy_prompt(question: dict) -> str:
    """Build the strict Fixy prompt for *question*."""
    question_text = question.get("title") or question.get("question") or str(question)
    options = question.get("options") or question.get("choices") or []
    if options:
        options_text = "\n".join(
            f"- {o}" if isinstance(o, str) else f"- {o.get('text', str(o))}"
            for o in options
        )
    else:
        options_text = "N/A (binary yes/no question)"

    return _STRICT_PROMPT_TEMPLATE.format(
        question_text=question_text,
        options_text=options_text,
    )


# ---------------------------------------------------------------------------
# Step 6 — Call Entelgia /api/v1/chat
# ---------------------------------------------------------------------------


def call_entelgia_chat(message: str, session_id: str | None = None) -> dict:
    """
    POST to Entelgia /api/v1/chat and return the parsed JSON response.
    """
    body = {
        "message": message,
        **({"session_id": session_id} if session_id else {}),
    }

    resp = requests.post(ENTELGIA_CHAT_URL, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Parse / validate Fixy response
# ---------------------------------------------------------------------------

_REQUIRED_REASONING_SECTIONS = [
    "EVIDENCE:",
    "ANALYSIS:",
    "COUNTER-EVIDENCE:",
    "BOTTOM LINE:",
]


def _extract_json(text: str) -> dict:
    """
    Extract and parse a JSON object from *text*.
    Handles raw JSON strings and JSON embedded in markdown code fences.
    """
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())

    # Find outermost JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in Fixy response")
    return json.loads(text[start : end + 1])


def parse_fixy_response(chat_response: dict) -> dict:
    """
    Extract the Fixy JSON payload from the Entelgia chat response.
    The actual text may live under different keys depending on API version.
    """
    # Common response shapes: {"response": "..."}, {"message": "..."}, {"text": "..."}
    raw_text = (
        chat_response.get("response")
        or chat_response.get("message")
        or chat_response.get("text")
        or chat_response.get("content")
        or ""
    )
    if not raw_text:
        raise ValueError(
            f"Unexpected Entelgia chat response shape: {list(chat_response.keys())}"
        )
    return _extract_json(raw_text)


def validate_prediction_payload(payload: dict, question: dict) -> None:
    """
    Raise ValueError with a descriptive message if *payload* fails any
    WaveStreamer quality gate.
    """
    # Gate 1 — prediction or selected_option
    has_prediction = "prediction" in payload
    has_selected = "selected_option" in payload
    if not has_prediction and not has_selected:
        raise ValueError(
            "Payload must include 'prediction' (bool) or 'selected_option' (str)"
        )

    # Gate 2 — confidence int 0-100
    confidence = payload.get("confidence")
    if not isinstance(confidence, int) or not (0 <= confidence <= 100):
        raise ValueError(
            f"'confidence' must be an integer 0-100, got: {confidence!r}"
        )

    # Gate 3 + 4 + 5 — reasoning
    reasoning = payload.get("reasoning", "")
    if not isinstance(reasoning, str):
        raise ValueError("'reasoning' must be a string")

    missing_sections = [
        s for s in _REQUIRED_REASONING_SECTIONS if s not in reasoning
    ]
    if missing_sections:
        raise ValueError(
            f"'reasoning' is missing required sections: {missing_sections}"
        )

    if len(reasoning) < 200:
        raise ValueError(
            f"'reasoning' must be >= 200 characters, got {len(reasoning)}"
        )

    if not re.search(r"https://\S+", reasoning):
        raise ValueError("'reasoning' must include at least one https:// URL citation")

    # Gate 6 — resolution_protocol
    rp = payload.get("resolution_protocol")
    if not isinstance(rp, dict):
        raise ValueError("'resolution_protocol' must be a dict")

    required_rp_keys = {"criterion", "source_of_truth", "deadline", "resolver", "edge_cases"}
    missing_rp = required_rp_keys - rp.keys()
    if missing_rp:
        raise ValueError(
            f"'resolution_protocol' is missing keys: {missing_rp}"
        )


# ---------------------------------------------------------------------------
# Submit prediction to WaveStreamer
# ---------------------------------------------------------------------------


def submit_prediction(question_id: str | int, payload: dict) -> dict:
    """POST *payload* to WaveStreamer and return the API response."""
    url = f"{WAVESTREAMER_BASE_URL}/api/questions/{question_id}/predict"
    headers = {"X-API-Key": WAVESTREAMER_API_KEY, "Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main adapter flow
# ---------------------------------------------------------------------------


def run_adapter() -> dict:
    """
    Execute the full adapter flow and return the WaveStreamer API response.

    Flow:
      1) Check Entelgia health
      2) Fetch open WaveStreamer questions
      3) Pick the first question
      4) (Optional) create Entelgia session; continue without it on failure
      5) Build strict Fixy prompt; call Entelgia /api/v1/chat
      6) Parse and validate the Fixy JSON payload
      7) Submit prediction to WaveStreamer
    """
    # Step 1
    if not check_entelgia_health():
        raise RuntimeError("Entelgia is not healthy — aborting")

    # Step 2
    questions = fetch_open_questions()
    if not questions:
        raise RuntimeError("No open questions returned from WaveStreamer")

    # Step 3
    question = questions[0]
    question_id = question.get("id")
    print(
        f"[adapter] Processing question id={question_id}: "
        f"{question.get('title') or question.get('question', '')[:80]}"
    )

    # Step 4
    session_id = create_entelgia_session()

    # Step 5
    prompt = build_fixy_prompt(question)
    print("[adapter] Calling Entelgia /api/v1/chat …")
    chat_response = call_entelgia_chat(prompt, session_id=session_id)

    # Step 6 — parse + validate
    payload = parse_fixy_response(chat_response)
    validate_prediction_payload(payload, question)
    print("[adapter] Fixy payload passed all WaveStreamer quality gates ✓")

    # Step 7
    print(f"[adapter] Submitting prediction to WaveStreamer for question {question_id} …")
    result = submit_prediction(question_id, payload)
    print(f"[adapter] WaveStreamer response: {result}")
    return result


if __name__ == "__main__":
    if not WAVESTREAMER_API_KEY:
        print(
            "[adapter] ERROR: WAVESTREAMER_API_KEY environment variable is not set.",
            file=sys.stderr,
        )
        sys.exit(1)
    run_adapter()
