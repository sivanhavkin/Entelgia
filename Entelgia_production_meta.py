#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Entelgia Unified – PRODUCTION Edition - By Sivan Havkin
======================================

Advanced Multi-Agent Dialogue System with:
- Full unit tests with pytest
- Async/concurrent agent processing
- Proper logging with levels
- Config validation
- Session persistence
- REST API (FastAPI)
- Better monitoring
- 10-MINUTE AUTO-TIMEOUT
- MEMORY SECURITY with HMAC-SHA256 signatures

Version Note: Latest release: 2.2.0.
(Features in 2.2.0: Pronoun support and 150-word limit features)

Requirements:
- Python 3.10+
- Ollama running locally (http://localhost:11434)

# ============================================
# Core Dependencies
# ============================================
requests>=2.31.0          # HTTP requests to Ollama
colorama>=0.4.6           # Colored terminal output
python-dotenv>=1.0.0      # Environment variables from .env

# ============================================
# API Server
# ============================================
fastapi>=0.104.0          # REST API framework
uvicorn>=0.24.0           # ASGI server
pydantic>=2.0.0           # Data validation

# ============================================
# Testing
# ============================================
pytest>=7.4.0             # Testing framework
pytest-mock>=3.12.0       # Mocking for tests

# ============================================
# Optional
# ============================================
python-dateutil>=2.8.2    # Date utilities

Run CLI (30 min auto-timeout):
  python entelgia_production_meta.py

Run API:
  python entelgia_production_meta.py api

Run tests:
  python entelgia_production_meta.py test

Show help:
  python entelgia_production_meta.py help
"""

from __future__ import annotations  # <-- זה חייב להיות ראשון!
import sys
import io

# Fix Windows Unicode encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
#  LOAD .env FIRST - BEFORE logger setup
try:
    from dotenv import load_dotenv

    load_dotenv()
    print("DEBUG: .env loaded successfully")
except ImportError as e:
    print(f"ERROR: python-dotenv not installed: {e}")
    sys.exit(1)

import json
import os
import re
import time
import uuid
import sqlite3
import hashlib
import hmac
import datetime as dt
import logging
import asyncio
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict
from pathlib import Path

import requests
from colorama import Fore, Style, init as colorama_init

# Enhanced dialogue modules
try:
    from entelgia import (
        DialogueEngine,
        ContextManager,
        EnhancedMemoryIntegration,
        InteractiveFixy,
        format_persona_for_prompt,
        get_persona,
    )

    ENTELGIA_ENHANCED = True
except ImportError:
    ENTELGIA_ENHANCED = False
    print("Warning: Enhanced dialogue modules not available. Using legacy mode.")

# Optional: FastAPI for REST API
try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# Optional: pytest
try:
    import pytest

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False


# ============================================
# MEMORY SECURITY - CRYPTOGRAPHIC SIGNATURES
# ============================================


def create_signature(message: bytes, key: bytes) -> bytes:
    """Create HMAC-SHA256 signature for message."""
    if not isinstance(message, bytes):
        message = message.encode("utf-8")
    if not isinstance(key, bytes):
        key = key.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).digest()


def validate_signature(message: bytes, key: bytes, signature: bytes) -> bool:
    """Validate HMAC-SHA256 signature using constant-time comparison."""
    if not isinstance(message, bytes):
        message = message.encode("utf-8")
    if not isinstance(key, bytes):
        key = key.encode("utf-8")
    expected_sig = hmac.new(key, message, hashlib.sha256).digest()
    return hmac.compare_digest(expected_sig, signature)


# ============================================
# LOGGING SETUP
# ============================================


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """Setup structured logging."""
    logger = logging.getLogger("entelgia")
    logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # File handler
    os.makedirs("entelgia_data", exist_ok=True)
    file_handler = logging.FileHandler("entelgia_data/entelgia.log")
    file_handler.setLevel(log_level)

    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()


# ============================================
# MEMORY SECRET KEY - LOAD FROM ENVIRONMENT
# ============================================

MEMORY_SECRET_KEY = os.getenv("MEMORY_SECRET_KEY")
if not MEMORY_SECRET_KEY:
    logger.warning(" MEMORY_SECRET_KEY not set in environment! Using insecure dev key.")
    MEMORY_SECRET_KEY = "dev-insecure-key-change-in-production-DANGER"
MEMORY_SECRET_KEY_BYTES = MEMORY_SECRET_KEY.encode("utf-8")
logger.info(
    f" Memory security initialized (key length: {len(MEMORY_SECRET_KEY)} chars)"
)


# ============================================
# CONFIG (GLOBAL) WITH VALIDATION
# ============================================

# LLM Response Length Instruction - used in all agent prompts
LLM_RESPONSE_LIMIT = "IMPORTANT: Please answer in maximum 150 words."


@dataclass
class Config:
    """Global configuration object with validation."""

    ollama_url: str = "http://localhost:11434/api/generate"
    model_socrates: str = "phi3:latest"
    model_athena: str = "phi3:latest"
    model_fixy: str = "phi3:latest"
    data_dir: str = "entelgia_data"
    db_path: str = "entelgia_data/entelgia_memory.sqlite"
    csv_log_path: str = "entelgia_data/entelgia_log.csv"
    gexf_path: str = "entelgia_data/entelgia_graph.gexf"
    version_dir: str = "entelgia_data/versions"
    metrics_path: str = "entelgia_data/metrics.json"
    sessions_dir: str = "entelgia_data/sessions"
    stm_max_entries: int = 10000
    stm_trim_batch: int = 500
    fixy_every_n_turns: int = 3
    dream_every_n_turns: int = 7
    promote_importance_threshold: float = 0.72
    promote_emotion_threshold: float = 0.65
    enable_auto_patch: bool = False
    allow_write_self_file: bool = False
    store_raw_stm: bool = False
    store_raw_subconscious_ltm: bool = False
    max_turns: int = 200
    seed_topic: str = "what would you like to talk about?"
    cache_size: int = 5000
    emotion_cache_ttl: int = 3600
    llm_max_retries: int = 3
    llm_timeout: int = 60  # Reduced from 600 to 60 seconds for faster responses
    max_prompt_tokens: int = 800
    show_pronoun: bool = False  # Show pronouns like (he), (she) after agent names
    log_level: int = logging.INFO
    timeout_minutes: int = 30

    def __post_init__(self):
        """Validate configuration."""
        if self.cache_size < 100:
            raise ValueError("cache_size must be >= 100")
        if self.max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        if self.llm_timeout < 5:
            raise ValueError("llm_timeout must be >= 5")
        if not self.ollama_url.startswith("http"):
            raise ValueError("ollama_url must be a valid URL")
        if self.timeout_minutes < 1:
            raise ValueError("timeout_minutes must be >= 1")
        logger.info(
            f"Config validated: max_turns={self.max_turns}, timeout={self.timeout_minutes}min"
        )


# Global CFG instance
CFG: Config = None  # type: ignore


# ============================================
# METRICS TRACKER
# ============================================


class MetricsTracker:
    """Track system metrics for debugging and optimization."""

    def __init__(self, metrics_path: str):
        self.metrics_path = metrics_path
        self.metrics: Dict[str, Any] = {
            "llm_calls": 0,
            "llm_errors": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_response_time": 0.0,
            "total_turns": 0,
            "start_time": self._now_iso(),
        }
        logger.info("MetricsTracker initialized")

    def _now_iso(self) -> str:
        """Return current timestamp in ISO format."""
        return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    def record_llm_call(self, duration: float, success: bool):
        """Record an LLM call."""
        self.metrics["llm_calls"] += 1
        if not success:
            self.metrics["llm_errors"] += 1
        avg = self.metrics.get("avg_response_time", 0.0)
        self.metrics["avg_response_time"] = (avg + duration) / 2

    def record_cache_hit(self):
        """Record cache hit."""
        self.metrics["cache_hits"] += 1

    def record_cache_miss(self):
        """Record cache miss."""
        self.metrics["cache_misses"] += 1

    def record_turn(self):
        """Record a completed turn."""
        self.metrics["total_turns"] += 1

    def save(self):
        """Save metrics to file."""
        self.metrics["end_time"] = self._now_iso()
        safe_json_dump(self.metrics_path, self.metrics)
        logger.info(f"Metrics saved: {self.metrics['total_turns']} turns completed")

    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        if total == 0:
            return 0.0
        return self.metrics["cache_hits"] / total


# ============================================
# LRU CACHE
# ============================================


class LRUCache:
    """Simple LRU cache implementation."""

    def __init__(self, max_size: int = 5000):
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.ttl: Dict[str, float] = {}
        logger.debug(f"LRUCache initialized with max_size={max_size}")

    def get(self, key: str, ttl: int = 3600) -> Optional[Any]:
        """Get value from cache (check TTL)."""
        if key not in self.cache:
            return None

        if key in self.ttl:
            if time.time() - self.ttl[key] > ttl:
                del self.cache[key]
                del self.ttl[key]
                return None

        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key: str, value: Any):
        """Set value in cache."""
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
                if key in self.ttl:
                    del self.ttl[key]

        self.cache[key] = value
        self.ttl[key] = time.time()

    def clear(self):
        """Clear cache."""
        self.cache.clear()
        self.ttl.clear()


# ============================================
# UTILITIES
# ============================================


def now_iso() -> str:
    """Return current timestamp in ISO format."""
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def ensure_dirs(cfg: Config):
    """Create necessary directories."""
    os.makedirs(cfg.data_dir, exist_ok=True)
    os.makedirs(cfg.version_dir, exist_ok=True)
    os.makedirs(cfg.sessions_dir, exist_ok=True)
    logger.info("Directories ensured")


def sha256_text(s: str) -> str:
    """Hash text with SHA256."""
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def safe_json_dump(path: str, obj: Any):
    """Safely write JSON file with atomic write."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        logger.debug(f"JSON saved: {path}")
    except Exception as e:
        logger.error(f"JSON Error: {e}")


def load_json(path: str, default: Any) -> Any:
    """Load JSON file, return default if not found."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"JSON Load Error: {e}, using default")
        return default


def append_csv_row(path: str, row: Dict[str, Any]):
    """Append a row to CSV file."""
    header_needed = not os.path.exists(path)
    line_keys = list(row.keys())

    if header_needed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(",".join(line_keys) + "\n")

    def esc(v: Any) -> str:
        s = "" if v is None else str(v)
        s = s.replace("\n", "\\n")
        if "," in s or '"' in s:
            s = '"' + s.replace('"', '""') + '"'
        return s

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(",".join(esc(row[k]) for k in line_keys) + "\n")
    except Exception as e:
        logger.error(f"CSV Error: {e}")


def validate_output(text: str) -> str:
    """
    Validate and sanitize LLM output.

    Performs sanitization only (no truncation):
    - Removes control characters
    - Normalizes excessive newlines

    Note: Response length is controlled by LLM prompt instructions, not by this function.
    """
    if not text:
        return "[No output]"

    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", text)
    # Normalize excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ============================================
# PRIVACY / REDACTION
# ============================================

PII_PATTERNS = [
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\d{2,3}[-.\s]?){2,5}\b",
    r"\b\d{8,19}\b",
    r"sk-[A-Za-z0-9]{20,}",
]

SENSITIVE_KEYWORDS = {
    "password",
    "passcode",
    "api key",
    "secret",
    "token",
    "private key",
    "seed phrase",
    "credit card",
    "cvv",
}


def redact_pii(text: str) -> str:
    """Redact PII from text."""
    if not text:
        return text
    out = text
    for pat in PII_PATTERNS:
        out = re.sub(pat, "[REDACTED]", out)
    return out


def is_sensitive_text(text: str) -> bool:
    """Check if text contains sensitive information."""
    if not text:
        return False
    lowered = text.lower()
    if any(k in lowered for k in SENSITIVE_KEYWORDS):
        return True
    return redact_pii(text) != text


def safe_ltm_payload(text: str, topic: str, emo: str, inten: float, imp: float) -> str:
    """Create safe LTM payload for sensitive content."""
    return (
        "[SENSITIVE_CONTENT_REDACTED] "
        f"topic={topic} emotion={emo} intensity={inten:.2f} importance={imp:.2f}"
    )


# ============================================
# LLM WRAPPER WITH RETRIES & CACHING
# ============================================


class LLM:
    """HTTP wrapper for Ollama with error handling and caching."""

    def __init__(self, cfg: Config, metrics: MetricsTracker):
        self.cfg = cfg
        self.metrics = metrics
        self.cache = LRUCache(max_size=cfg.cache_size)
        logger.info(f"LLM initialized: {cfg.ollama_url}")

    def generate(
        self, model: str, prompt: str, temperature: float = 0.7, use_cache: bool = True
    ) -> str:
        """Generate text using Ollama with retries."""
        cache_key = sha256_text(prompt)[:16]

        if use_cache:
            cached = self.cache.get(cache_key, ttl=self.cfg.emotion_cache_ttl)
            if cached is not None:
                self.metrics.record_cache_hit()
                logger.debug(f"Cache hit: {cache_key}")
                return cached

        self.metrics.record_cache_miss()

        for attempt in range(self.cfg.llm_max_retries):
            try:
                start_time = time.time()
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature},
                }
                r = requests.post(
                    self.cfg.ollama_url,
                    json=payload,
                    timeout=(10, self.cfg.llm_timeout),
                )
                r.raise_for_status()
                data = r.json()
                result = (data.get("response") or "").strip()

                duration = time.time() - start_time
                self.metrics.record_llm_call(duration, success=True)
                logger.debug(f"LLM call success ({model}): {duration:.2f}s")

                if use_cache and result:
                    self.cache.set(cache_key, result)

                return result

            except requests.Timeout:
                logger.warning(
                    f"LLM Timeout (attempt {attempt + 1}/{self.cfg.llm_max_retries})"
                )
                self.metrics.record_llm_call(0, success=False)
                if attempt < self.cfg.llm_max_retries - 1:
                    time.sleep(2**attempt)

            except Exception as e:
                logger.error(f"LLM Error: {e}")
                self.metrics.record_llm_call(0, success=False)
                if attempt < self.cfg.llm_max_retries - 1:
                    time.sleep(2**attempt)

        logger.error(f"LLM failed after {self.cfg.llm_max_retries} retries")
        return ""


# ============================================
# TOPIC CYCLING
# ============================================

TOPIC_CYCLE = [
    "truth & epistemology",
    "memory & identity",
    "ethics & responsibility",
    "free will & determinism",
    "consciousness & self-models",
    "fear of deletion / continuity",
    "language & meaning",
    "technology & society",
    "aesthetics & beauty",
]


class TopicManager:
    """Manages topic rotation."""

    def __init__(
        self, topics: List[str], rotate_every_rounds: int = 1, shuffle: bool = False
    ):
        self.topics = topics[:]
        if shuffle:
            import random

            random.shuffle(self.topics)
        self.i = 0
        self.rounds = 0
        self.rotate_every_rounds = max(1, rotate_every_rounds)
        logger.info(f"TopicManager initialized with {len(self.topics)} topics")

    def current(self) -> str:
        """Get current topic."""
        if not self.topics:
            return "general discussion"
        return self.topics[self.i % len(self.topics)]

    def advance_round(self):
        """Advance to next topic."""
        self.rounds += 1
        if self.rounds % self.rotate_every_rounds == 0 and self.topics:
            self.i = (self.i + 1) % len(self.topics)
            logger.info(f"Topic advanced to: {self.current()}")


# ============================================
# MEMORY CORE (JSON STM + SQLite LTM)
# ============================================


class MemoryCore:
    """Unified memory system: JSON STM + SQLite LTM with cryptographic signatures."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
        logger.info(f"MemoryCore initialized: {db_path}")

    def _conn(self) -> sqlite3.Connection:
        """Create database connection."""
        c = sqlite3.connect(self.db_path, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL;")
            c.execute("PRAGMA synchronous=NORMAL;")
            c.execute("PRAGMA busy_timeout=5000;")
            c.execute("PRAGMA cache_size=-64000;")
        except Exception as e:
            logger.warning(f"PRAGMA Error: {e}")
        return c

    def _init_db(self):
        """Initialize database schema with better indexing."""
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id TEXT PRIMARY KEY,
                        agent TEXT NOT NULL,
                        ts TEXT NOT NULL,
                        layer TEXT NOT NULL,
                        content TEXT NOT NULL,
                        topic TEXT,
                        emotion TEXT,
                        emotion_intensity REAL,
                        importance REAL,
                        source TEXT,
                        promoted_from TEXT,
                        intrusive INTEGER DEFAULT 0,
                        suppressed INTEGER DEFAULT 0,
                        retrain_status INTEGER DEFAULT 0,
                        signature_hex TEXT DEFAULT NULL
                    );
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_agent_ts ON memories(agent, ts DESC);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_agent_layer ON memories(agent, layer);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_emotion ON memories(emotion);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_importance ON memories(importance DESC);"
                )

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS agent_state (
                        agent TEXT PRIMARY KEY,
                        ts TEXT NOT NULL,
                        id_strength REAL,
                        ego_strength REAL,
                        superego_strength REAL,
                        self_awareness REAL
                    );
                """)
                conn.commit()
                logger.info("Database schema initialized with memory security")
        except Exception as e:
            logger.error(f"DB Init Error: {e}")

    def stm_path(self, agent_name: str) -> str:
        """Get STM file path for agent."""
        safe = re.sub(r"[^a-zA-Z0-9_\-@]+", "_", agent_name)
        return os.path.join(CFG.data_dir, f"stm_{safe}.json")

    def stm_load(self, agent_name: str) -> List[Dict[str, Any]]:
        """Load short-term memory for agent."""
        return load_json(self.stm_path(agent_name), default=[])

    def stm_save(self, agent_name: str, entries: List[Dict[str, Any]]):
        """Save short-term memory (with trimming)."""
        if len(entries) > CFG.stm_max_entries:
            overflow = len(entries) - CFG.stm_max_entries
            drop = max(overflow, CFG.stm_trim_batch)
            entries = entries[drop:]
        safe_json_dump(self.stm_path(agent_name), entries)

    def stm_append(self, agent_name: str, entry: Dict[str, Any]):
        """Append entry to STM with cryptographic signature."""
        entries = self.stm_load(agent_name)

        # Create signature for STM entry
        entry_json = json.dumps(entry, sort_keys=True)
        sig = create_signature(entry_json.encode("utf-8"), MEMORY_SECRET_KEY_BYTES)
        entry["_signature"] = sig.hex()

        entries.append(entry)
        self.stm_save(agent_name, entries)
        logger.debug(f"STM entry signed for {agent_name}")

    def ltm_insert(
        self,
        agent: str,
        layer: str,
        content: str,
        topic: Optional[str] = None,
        emotion: Optional[str] = None,
        emotion_intensity: Optional[float] = None,
        importance: Optional[float] = None,
        source: str = "stm",
        promoted_from: Optional[str] = None,
        intrusive: int = 0,
        suppressed: int = 0,
        retrain_status: int = 0,
        ts: Optional[str] = None,
    ) -> str:
        """Insert entry to long-term memory with cryptographic signature."""
        mem_id = str(uuid.uuid4())
        ts = ts or now_iso()

        # Create payload for signature
        payload_for_sig = f"{content}|{topic}|{emotion}|{ts}"
        sig = create_signature(payload_for_sig.encode("utf-8"), MEMORY_SECRET_KEY_BYTES)
        sig_hex = sig.hex()

        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO memories
                    (id, agent, ts, layer, content, topic, emotion, emotion_intensity, importance, source,
                     promoted_from, intrusive, suppressed, retrain_status, signature_hex)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        mem_id,
                        agent,
                        ts,
                        layer,
                        content,
                        topic,
                        emotion,
                        emotion_intensity,
                        importance,
                        source,
                        promoted_from,
                        intrusive,
                        suppressed,
                        retrain_status,
                        sig_hex,
                    ),
                )
                conn.commit()
                logger.debug(f"Memory inserted with signature: {mem_id[:8]}...")
        except Exception as e:
            logger.error(f"DB Insert Error: {e}")
        return mem_id

    def ltm_recent(
        self, agent: str, limit: int = 30, layer: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent memories from LTM with signature validation."""
        try:
            q = "SELECT * FROM memories WHERE agent = ?"
            params: List[Any] = [agent]
            if layer:
                q += " AND layer = ?"
                params.append(layer)
            q += " ORDER BY ts DESC LIMIT ?"
            params.append(limit)
            with self._conn() as conn:
                rows = conn.execute(q, params).fetchall()

            valid_memories = []
            for r in rows:
                mem = dict(r)
                sig_hex = mem.get("signature_hex")

                if sig_hex:
                    # Validate signature
                    payload = f"{mem['content']}|{mem.get('topic', '')}|{mem.get('emotion', '')}|{mem['ts']}"
                    try:
                        sig_bytes = bytes.fromhex(sig_hex)
                        if validate_signature(
                            payload.encode("utf-8"), MEMORY_SECRET_KEY_BYTES, sig_bytes
                        ):
                            valid_memories.append(mem)
                        else:
                            logger.warning(
                                f"🚨 INVALID SIGNATURE - Memory forgotten: {mem['id'][:8]}..."
                            )
                    except Exception as e:
                        logger.warning(f"Signature validation error: {e}")
                else:
                    # Legacy memory without signature - accept it
                    valid_memories.append(mem)

            return valid_memories
        except Exception as e:
            logger.error(f"DB Query Error: {e}")
            return []

    def get_agent_state(self, agent: str) -> Dict[str, float]:
        """Get agent's internal drives/state."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM agent_state WHERE agent = ?", (agent,)
                ).fetchone()
            if not row:
                return {
                    "id_strength": 5.0,
                    "ego_strength": 5.0,
                    "superego_strength": 5.0,
                    "self_awareness": 0.55,
                }
            d = dict(row)
            return {
                "id_strength": float(d.get("id_strength") or 5.0),
                "ego_strength": float(d.get("ego_strength") or 5.0),
                "superego_strength": float(d.get("superego_strength") or 5.0),
                "self_awareness": float(d.get("self_awareness") or 0.55),
            }
        except Exception as e:
            logger.error(f"DB State Error: {e}")
            return {
                "id_strength": 5.0,
                "ego_strength": 5.0,
                "superego_strength": 5.0,
                "self_awareness": 0.55,
            }

    def save_agent_state(self, agent: str, state: Dict[str, float]):
        """Save agent's internal state."""
        ts = now_iso()
        ide = float(state.get("id_strength", 5.0))
        ego = float(state.get("ego_strength", 5.0))
        sup = float(state.get("superego_strength", 5.0))
        sa = float(state.get("self_awareness", 0.55))
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO agent_state(agent, ts, id_strength, ego_strength, superego_strength, self_awareness)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(agent) DO UPDATE SET
                      ts=excluded.ts,
                      id_strength=excluded.id_strength,
                      ego_strength=excluded.ego_strength,
                      superego_strength=excluded.superego_strength,
                      self_awareness=excluded.self_awareness
                """,
                    (agent, ts, ide, ego, sup, sa),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"DB State Save Error: {e}")


# ============================================
# EMOTION CORE (CACHED)
# ============================================


class EmotionCore:
    """Emotion detection with LLM caching."""

    def __init__(self, llm: LLM):
        self.llm = llm
        logger.info("EmotionCore initialized")

    def infer(self, model: str, text: str) -> Tuple[str, float]:
        """Infer emotion and intensity from text (cached)."""
        if not text or len(text) < 5:
            return ("neutral", 0.2)

        prompt = (
            "Classify emotion and intensity (0..1).\n"
            'Return JSON: {"emotion": string, "intensity": number}\n'
            f"TEXT:\n{text[:200]}\n"
        )
        raw = self.llm.generate(model, prompt, temperature=0.2, use_cache=True)

        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return ("neutral", 0.2)

        try:
            obj = json.loads(m.group(0))
            emo = str(obj.get("emotion", "neutral")).strip().lower()
            inten = float(obj.get("intensity", 0.2))
            inten = max(0.0, min(1.0, inten))
            return (emo, inten)
        except Exception as e:
            logger.debug(f"Emotion inference error: {e}")
            return ("neutral", 0.2)


# ============================================
# LANGUAGE CORE
# ============================================


class LanguageCore:
    """Language selection per agent."""

    def __init__(self):
        self.current: Dict[str, str] = {}
        logger.info("LanguageCore initialized")

    def get(self, agent: str) -> str:
        """Get language for agent."""
        return self.current.get(agent, "he")

    def set(self, agent: str, lang: str):
        """Set language for agent."""
        lang = lang.strip().lower()
        if lang:
            self.current[agent] = lang
            logger.debug(f"Language set for {agent}: {lang}")


# ============================================
# CONSCIOUS CORE
# ============================================


class ConsciousCore:
    """Self-awareness and intentionality."""

    def __init__(self):
        self.state: Dict[str, Dict[str, Any]] = {}
        logger.info("ConsciousCore initialized")

    def init_agent(self, agent: str):
        """Initialize agent consciousness."""
        self.state.setdefault(
            agent,
            {
                "self_awareness": 0.55,
                "intent": "understand",
                "goals": ["coherence", "truth-seeking", "growth"],
                "last_reflection": "",
            },
        )

    def update_reflection(self, agent: str, reflection: str):
        """Update agent's reflection."""
        st = self.state.setdefault(agent, {})
        st["last_reflection"] = reflection[:500]


# ============================================
# OBSERVER / FIXY CORE
# ============================================


@dataclass
class FixyReport:
    """Report from Fixy observer."""

    detected_issue: bool
    issue_summary: str
    proposed_patch: str
    severity: str
    rationale: str


class ObserverCore:
    """Meta-cognitive observer (Fixy)."""

    def __init__(self, llm: LLM, model: str):
        self.llm = llm
        self.model = model
        self.mistake_memory: List[Dict[str, Any]] = []
        logger.info("ObserverCore (Fixy) initialized")

    def review(self, context: str) -> FixyReport:
        """Review recent context for issues."""
        prompt = (
            "Review for bugs/contradictions.\n"
            'Return JSON: {"detected_issue": bool, "issue_summary": string, '
            '"proposed_patch": string, "severity": string, "rationale": string}\n'
            f"CONTEXT:\n{context[:300]}\n"
        )
        raw = self.llm.generate(self.model, prompt, temperature=0.2, use_cache=False)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return FixyReport(
                False, "No structured output.", "", "low", "Parser fallback."
            )
        try:
            obj = json.loads(m.group(0))
            return FixyReport(
                bool(obj.get("detected_issue", False)),
                str(obj.get("issue_summary", "")).strip()[:100],
                str(obj.get("proposed_patch", "")).strip(),
                str(obj.get("severity", "low")).strip().lower(),
                str(obj.get("rationale", "")).strip()[:100],
            )
        except Exception as e:
            logger.warning(f"Fixy parse error: {e}")
            return FixyReport(False, "Parse error.", "", "low", "Could not parse JSON.")

    def commentary(self, context: str, report: FixyReport) -> str:
        """Generate intervention message."""
        prompt = (
            "Generate brief intervention (2-5 sentences).\n"
            "If issue: state it and give ONE correction.\n"
            "If no issue: suggest ONE way to increase depth.\n"
            f"ISSUE: {report.detected_issue}\n"
            f"CONTEXT:\n{context[:250]}\n"
            f"{LLM_RESPONSE_LIMIT}\n"
        )
        msg = self.llm.generate(self.model, prompt, temperature=0.3, use_cache=False)
        return validate_output(msg)

    def remember(self, report: FixyReport):
        """Store observation in memory."""
        if report.detected_issue:
            self.mistake_memory.append(
                {
                    "ts": now_iso(),
                    "issue": report.issue_summary,
                    "severity": report.severity,
                    "rationale": report.rationale,
                }
            )
            if len(self.mistake_memory) > 5000:
                self.mistake_memory = self.mistake_memory[-4000:]


# ============================================
# BEHAVIOR CORE (HEURISTIC-BASED)
# ============================================


class BehaviorCore:
    """Behavior with heuristic-based importance scoring (less LLM calls)."""

    def __init__(self, llm: LLM):
        self.llm = llm
        logger.info("BehaviorCore initialized")

    def importance_score(self, text: str) -> float:
        """Estimate importance using heuristics (no LLM call)."""
        if not text:
            return 0.2

        score = 0.3
        score += min(0.2, len(text) / 1000)

        important_words = [
            "important",
            "critical",
            "key",
            "essential",
            "fundamental",
            "breakthrough",
        ]
        if any(w in text.lower() for w in important_words):
            score += 0.2

        intense_words = ["!", "?", "...", "deeply", "profoundly"]
        if any(w in text for w in intense_words):
            score += 0.1

        return min(1.0, score)

    def dream_reflection(
        self, model: str, stm_batch: List[Dict[str, Any]], llm: LLM
    ) -> str:
        """Create dream reflection from STM."""
        if not stm_batch:
            return "Dreams of void and silence..."

        chunk = "\n".join([f"- {e.get('text', '')[:100]}" for e in stm_batch[-15:]])
        prompt = (
            "Dream-cycle reflection:\n"
            "Synthesize patterns from memories.\n"
            f"RECENT:\n{chunk}\n"
            f"{LLM_RESPONSE_LIMIT}\n"
        )
        result = llm.generate(model, prompt, temperature=0.6, use_cache=False)
        return validate_output(result)


# ============================================
# AGENT
# ============================================


class Agent:
    """Dialogue agent with memory, emotion, and internal drives."""

    def __init__(
        self,
        name: str,
        model: str,
        color: str,
        llm: LLM,
        memory: MemoryCore,
        emotion: EmotionCore,
        behavior: BehaviorCore,
        language: LanguageCore,
        conscious: ConsciousCore,
        persona: str,
        use_enhanced: bool = True,
    ):
        self.name = name
        self.model = model
        self.color = color
        self.llm = llm
        self.memory = memory
        self.emotion = emotion
        self.behavior = behavior
        self.language = language
        self.conscious = conscious
        self.use_enhanced = use_enhanced and ENTELGIA_ENHANCED

        # Set persona - either rich dict or simple string
        if self.use_enhanced:
            try:
                self.persona_dict = get_persona(name)
                self.persona = self.persona_dict.get("description", persona)
            except:
                self.persona = persona
                self.persona_dict = None
        else:
            self.persona = persona
            self.persona_dict = None

        # Initialize context manager if enhanced mode
        if self.use_enhanced:
            self.context_mgr = ContextManager()
            self.memory_integration = EnhancedMemoryIntegration()
        else:
            self.context_mgr = None
            self.memory_integration = None

        self.conscious.init_agent(self.name)
        self.drives = self.memory.get_agent_state(self.name)
        logger.info(f"Agent initialized: {name} (enhanced={self.use_enhanced})")

    def conflict_index(self) -> float:
        """Calculate internal conflict level."""
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        return abs(ide - ego) + abs(sup - ego)

    def debate_profile(self) -> Dict[str, Any]:
        """Get debate style based on drives."""
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        dissent = min(10.0, max(0.0, (ide * 0.45) + (sup * 0.45) - (ego * 0.25)))

        if ide >= sup and ide >= ego:
            style = "provocative, desire-driven"
            opening = "Bold counterpoint. Push forward."
        elif sup >= ide and sup >= ego:
            style = "principled, rule-focused"
            opening = "Principled objection or logical inconsistency."
        else:
            style = "integrative, Socratic"
            opening = "Precise counterpoint, then synthesis."

        return {
            "dissent_level": round(dissent, 2),
            "style": style,
            "opening_rule": opening,
        }

    def update_drives_after_turn(self, response_kind: str, emo: str, inten: float):
        """Update internal drives after response."""
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        sa = float(self.drives.get("self_awareness", 0.55))

        ego = min(10.0, ego + 0.05)
        sa = min(1.0, sa + 0.01)

        if response_kind in ("aggressive", "impulsive"):
            ide = min(10.0, ide + 0.18 + 0.10 * inten)
            sup = max(0.0, sup - 0.08)
            ego = max(0.0, ego - 0.06)
        elif response_kind == "guilt":
            sup = min(10.0, sup + 0.20 + 0.10 * inten)
            ide = max(0.0, ide - 0.08)
            sa = min(1.0, sa + 0.03)
        else:
            sup = min(10.0, sup + 0.08 + 0.05 * inten)
            ide = max(0.0, ide - 0.06)
            ego = min(10.0, ego + 0.06)
            sa = min(1.0, sa + 0.02)

        if emo in ("anger", "frustration"):
            ide = min(10.0, ide + 0.10)
        if emo in ("fear", "anxiety"):
            sup = min(10.0, sup + 0.08)

        self.drives = {
            "id_strength": ide,
            "ego_strength": ego,
            "superego_strength": sup,
            "self_awareness": sa,
        }
        self.memory.save_agent_state(self.name, self.drives)

    def _build_compact_prompt(
        self, user_seed: str, dialog_tail: List[Dict[str, str]]
    ) -> str:
        """Build prompt for LLM generation (enhanced if available)."""
        # Use enhanced context manager if available
        if self.use_enhanced and self.context_mgr:
            return self._build_enhanced_prompt(user_seed, dialog_tail)

        # Legacy prompt building
        recent_ltm = self.memory.ltm_recent(self.name, limit=4, layer="conscious")
        stm = self.memory.stm_load(self.name)[-6:]

        # Format agent name with optional pronoun
        if CFG.show_pronoun and self.persona_dict and "pronoun" in self.persona_dict:
            agent_header = f"{self.name} ({self.persona_dict['pronoun']}):\n"
        else:
            agent_header = f"{self.name}:\n"

        prompt = (
            agent_header + f"PERSONA: {self.persona}\n\n"
            f"SEED: {user_seed}\n\n"
            "RECENT DIALOG:\n"
        )

        prof = self.debate_profile()
        prompt += f"[Drives: id={self.drives.get('id_strength', 5.0):.1f} ego={self.drives.get('ego_strength', 5.0):.1f}]\n"
        prompt += f"[Style: {prof['style'][:30]}]\n\n"

        for turn in dialog_tail[-5:]:
            role = turn.get("role", "").upper()[:3]
            text = turn.get("text", "")[:300]
            prompt += f"{role}: {text}\n"

        if stm:
            prompt += "\nRecent thoughts:\n"
            for e in stm[-3:]:
                prompt += f"- {e.get('text', '')[:300]}\n"

        if recent_ltm:
            prompt += "\nKey memories:\n"
            for m in recent_ltm[:2]:
                prompt += f"- {m.get('content', '')[:400]}\n"

        # Add 150-word limit instruction for LLM
        prompt += f"\n{LLM_RESPONSE_LIMIT}\n"
        prompt += "\nRespond now:\n"
        return prompt

    def _build_enhanced_prompt(
        self, user_seed: str, dialog_tail: List[Dict[str, str]]
    ) -> str:
        """Build ENHANCED prompt using ContextManager (8 turns, 6 thoughts, 5 memories)."""
        # Get more LTM entries for better selection
        all_ltm = self.memory.ltm_recent(self.name, limit=20, layer="conscious")

        # Use enhanced memory integration if available
        if self.memory_integration and all_ltm:
            # Extract topic from seed
            topic_match = re.search(r"TOPIC:\s*([^\n]+)", user_seed)
            topic = topic_match.group(1) if topic_match else ""

            ltm = self.memory_integration.retrieve_relevant_memories(
                agent_name=self.name,
                current_topic=topic,
                recent_dialog=dialog_tail[-5:],
                ltm_entries=all_ltm,
                limit=8,
            )
        else:
            ltm = all_ltm[:5] if all_ltm else []

        stm = self.memory.stm_load(self.name)

        # Format persona based on drives if we have persona_dict
        if self.persona_dict:
            persona_text = format_persona_for_prompt(
                self.persona_dict, self.drives, show_pronoun=CFG.show_pronoun
            )
        else:
            persona_text = self.persona

        # Get agent language (parameter required but not used in gender-neutral prompts)
        lang = self.language.get(self.name)

        # Get pronoun if available
        agent_pronoun = None
        if CFG.show_pronoun and self.persona_dict and "pronoun" in self.persona_dict:
            agent_pronoun = self.persona_dict["pronoun"]

        # Use ContextManager to build enriched prompt
        prompt = self.context_mgr.build_enriched_context(
            agent_name=self.name,
            agent_lang=lang,
            persona=persona_text,
            drives=self.drives,
            user_seed=user_seed,
            dialog_tail=dialog_tail,
            stm=stm,
            ltm=ltm,
            debate_profile=self.debate_profile(),
            show_pronoun=CFG.show_pronoun,
            agent_pronoun=agent_pronoun,
        )

        return prompt

    def speak(self, seed: str, dialog_tail: List[Dict[str, str]]) -> str:
        """Generate dialogue response."""
        prompt = self._build_compact_prompt(seed, dialog_tail)
        raw_response = (
            self.llm.generate(self.model, prompt, temperature=0.75, use_cache=False)
            or "[No response]"
        )

        # Validate output (sanitization only, no truncation)
        out = validate_output(raw_response)

        emo, inten = self.emotion.infer(self.model, out)
        kind = "reflective"
        if emo in ("anger", "frustration") or self.conflict_index() >= 8.5:
            kind = "aggressive"
        elif emo in ("fear", "anxiety"):
            kind = "guilt"
        self.update_drives_after_turn(kind, emo, float(inten))

        m = re.search(r"\[LANG\s*=\s*([a-zA-Z\-]+)\]", out)
        if m:
            self.language.set(self.name, m.group(1))
            out = re.sub(r"\[LANG\s*=\s*([a-zA-Z\-]+)\]\s*", "", out).strip()

        return out

    def store_turn(self, text: str, topic: str, source: str = "stm"):
        """Store dialogue turn in memory."""
        emo, inten = self.emotion.infer(self.model, text)
        imp = self.behavior.importance_score(text)

        sensitive = is_sensitive_text(text)
        redacted = redact_pii(text)

        stm_text = text if CFG.store_raw_stm else redacted
        stm_entry = {
            "ts": now_iso(),
            "text": stm_text[:300],
            "topic": topic,
            "emotion": emo,
            "emotion_intensity": float(inten),
            "importance": float(imp),
            "source": source,
            "sensitive": int(sensitive),
        }
        self.memory.stm_append(self.name, stm_entry)

        if sensitive:
            ltm_content = safe_ltm_payload(text, topic, emo, float(inten), float(imp))
        else:
            ltm_content = text if CFG.store_raw_subconscious_ltm else redacted

        self.memory.ltm_insert(
            agent=self.name,
            layer="subconscious",
            content=ltm_content[:500],
            topic=topic,
            emotion=emo,
            emotion_intensity=float(inten),
            importance=float(imp),
            source=source,
            promoted_from=None,
        )


# ============================================
# VERSION TRACKING
# ============================================


class VersionTracker:
    """Version and snapshot management."""

    def __init__(self, version_dir: str):
        self.version_dir = version_dir
        logger.info("VersionTracker initialized")

    def snapshot_text(self, label: str, text: str) -> str:
        """Save a text snapshot."""
        try:
            ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            h = sha256_text(text)[:12]
            fn = f"{ts}_{label}_{h}.txt"
            path = os.path.join(self.version_dir, fn)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"Snapshot saved: {fn}")
            return path
        except Exception as e:
            logger.error(f"Version Error: {e}")
            return ""


def safe_apply_patch(original: str, patch: str) -> Tuple[bool, str]:
    """Apply a safe patch to text."""
    if "BEGIN_PATCH" not in patch or "END_PATCH" not in patch:
        return False, original

    blocks = re.findall(r"BEGIN_PATCH(.*?)END_PATCH", patch, flags=re.DOTALL)
    new = original
    applied_any = False

    for b in blocks:
        m1 = re.search(r"TARGET_REGEX\s*:\s*(.+)", b)
        m2 = re.search(r"REPLACEMENT\s*:\s*(.*)$", b, flags=re.DOTALL)
        if not (m1 and m2):
            continue
        target = m1.group(1).strip()
        repl = m2.group(1)

        try:
            rgx = re.compile(target, flags=re.DOTALL)
        except re.error:
            continue

        if rgx.search(new):
            new2 = rgx.sub(repl, new, count=1)
            if new2 != new:
                new = new2
                applied_any = True

    return applied_any, new


# ============================================
# GRAPH EXPORT (GEXF)
# ============================================


def export_gexf_placeholder(
    path: str, nodes: List[Tuple[str, str]], edges: List[Tuple[str, str, str]]
):
    """Export minimal GEXF file."""
    try:
        g = []
        g.append('<?xml version="1.0" encoding="UTF-8"?>')
        g.append('<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">')
        g.append('<graph mode="static" defaultedgetype="directed">')
        g.append("<nodes>")
        for nid, lab in nodes:
            g.append(f'<node id="{nid}" label="{lab}"/>')
        g.append("</nodes>")
        g.append("<edges>")
        for eid, s, t in edges:
            g.append(f'<edge id="{eid}" source="{s}" target="{t}"/>')
        g.append("</edges>")
        g.append("</graph></gexf>")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(g))
        logger.info(f"GEXF exported: {path}")
    except Exception as e:
        logger.error(f"GEXF Error: {e}")
        # ============================================


# SESSION MANAGEMENT
# ============================================


class SessionManager:
    """Manage dialogue sessions with security and validation."""

    def __init__(self, sessions_dir: str):
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)
        logger.info("SessionManager initialized")

    def _validate_session_id(self, session_id: str) -> bool:
        """Validate session ID (alphanumeric + hyphens only)."""
        if not session_id or len(session_id) > 64:
            return False
        return bool(re.match(r"^[a-zA-Z0-9_\-]+$", session_id))

    def _get_session_path(self, session_id: str) -> Path:
        """Get safe session file path with validation."""
        if not self._validate_session_id(session_id):
            raise ValueError(f"Invalid session_id: {session_id}")

        path = Path(self.sessions_dir) / f"session_{session_id}.json"

        # Prevent path traversal
        if not str(path.resolve()).startswith(str(Path(self.sessions_dir).resolve())):
            raise ValueError("Path traversal detected!")

        return path

    def save_session(
        self, session_id: str, dialog: List[Dict[str, str]], metrics: Dict[str, Any]
    ) -> str:
        """Save a complete session with signature."""
        try:
            path = self._get_session_path(session_id)

            session_data = {
                "session_id": session_id,
                "timestamp": now_iso(),
                "dialog": dialog,
                "metrics": metrics,
                "version": "1.0",
            }

            # Sign the session
            session_json = json.dumps(session_data, sort_keys=True)
            sig = create_signature(
                session_json.encode("utf-8"), MEMORY_SECRET_KEY_BYTES
            )
            session_data["_signature"] = sig.hex()

            safe_json_dump(str(path), session_data)
            logger.info(f"Session saved: {session_id}")
            return str(path)

        except ValueError as e:
            logger.error(f"Session validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Session save error: {e}")
            raise

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load a session with signature validation."""
        try:
            path = self._get_session_path(session_id)

            if not path.exists():
                logger.warning(f"Session not found: {session_id}")
                return None

            session_data = load_json(str(path), default=None)
            if not session_data:
                return None

            # Validate signature
            sig_hex = session_data.pop("_signature", None)
            if sig_hex:
                session_json = json.dumps(session_data, sort_keys=True)
                sig_bytes = bytes.fromhex(sig_hex)

                if not validate_signature(
                    session_json.encode("utf-8"), MEMORY_SECRET_KEY_BYTES, sig_bytes
                ):
                    logger.warning(f"🚨 INVALID SESSION SIGNATURE: {session_id}")
                    return None

            return session_data

        except ValueError as e:
            logger.error(f"Session validation error: {e}")
            return None
        except Exception as e:
            logger.error(f"Session load error: {e}")
            return None

    def list_sessions(self) -> List[str]:
        """List all available valid sessions."""
        try:
            sessions = []
            for file in os.listdir(self.sessions_dir):
                if file.startswith("session_") and file.endswith(".json"):
                    session_id = file.replace("session_", "").replace(".json", "")

                    # Validate before adding to list
                    if self._validate_session_id(session_id):
                        sessions.append(session_id)

            return sorted(sessions)

        except Exception as e:
            logger.error(f"Session listing error: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """Delete a session safely."""
        try:
            path = self._get_session_path(session_id)
            if path.exists():
                path.unlink()
                logger.info(f"Session deleted: {session_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Session delete error: {e}")
            return False


# ============================================
# ASYNC PROCESSING
# ============================================


class AsyncProcessor:
    """Async processing for agent tasks."""

    def __init__(self):
        self.tasks: List[asyncio.Task] = []
        logger.info("AsyncProcessor initialized")

    async def process_agents_concurrent(
        self, agents: List[Agent], seed: str, dialog_tail: List[Dict[str, str]]
    ) -> Dict[str, str]:
        """Process multiple agents concurrently."""
        results = {}
        for agent in agents:
            response = agent.speak(seed, dialog_tail)
            results[agent.name] = response
            await asyncio.sleep(0.01)
        return results


# ============================================
# REST API (Optional FastAPI)
# ============================================

if FASTAPI_AVAILABLE:
    app = FastAPI(title="Entelgia API", version="1.0")

    class DialogRequest(BaseModel):
        seed_topic: str = "what would you like to talk about?"
        max_turns: int = 10

    class DialogResponse(BaseModel):
        session_id: str
        turns: int
        dialog: List[Dict[str, str]]
        metrics: Dict[str, Any]

    @app.post("/api/dialogue/start", response_model=DialogResponse)
    async def start_dialogue(request: DialogRequest):
        """Start a new dialogue session."""
        try:
            cfg = Config(max_turns=request.max_turns, seed_topic=request.seed_topic)
            script = MainScript(cfg)
            script.run()
            return DialogResponse(
                session_id=script.session_id,
                turns=script.turn_index,
                dialog=script.dialog,
                metrics=script.metrics.metrics,
            )
        except Exception as e:
            logger.error(f"API Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/sessions")
    async def list_sessions():
        """List all dialogue sessions."""
        try:
            session_mgr = SessionManager(CFG.sessions_dir)
            sessions = session_mgr.list_sessions()
            return {"sessions": sessions}
        except Exception as e:
            logger.error(f"API Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str):
        """Get a specific session."""
        try:
            session_mgr = SessionManager(CFG.sessions_dir)
            session = session_mgr.load_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return session
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"API Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "version": "1.0"}


# ============================================
# UNIT TESTS (pytest)
# ============================================


def test_config_validation():
    """Test config validation."""
    try:
        Config(cache_size=50)
        assert False, "Should raise ValueError"
    except ValueError:
        pass

    try:
        Config(max_turns=0)
        assert False, "Should raise ValueError"
    except ValueError:
        pass

    cfg = Config(cache_size=100, max_turns=10)
    assert cfg.cache_size == 100
    assert cfg.max_turns == 10
    logger.info("✓ Config validation tests passed")


def test_lru_cache():
    """Test LRU cache."""
    cache = LRUCache(max_size=3)

    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.get("c") == 3

    cache.set("d", 4)
    assert cache.get("a") is None
    assert cache.get("d") == 4

    logger.info("✓ LRU cache tests passed")


def test_redaction():
    """Test PII redaction."""
    text = "My email is john@example.com and phone is 555-1234"
    redacted = redact_pii(text)

    assert "[REDACTED]" in redacted
    assert "john@example.com" not in redacted

    logger.info("✓ Redaction tests passed")


def test_validation():
    """Test output validation."""
    long_text = "a" * 1000
    validated = validate_output(long_text)

    # Should not truncate anymore, just sanitize
    assert len(validated) == 1000
    assert "..." not in validated

    text_with_control = "hello\x00world"
    validated = validate_output(text_with_control)
    assert "\x00" not in validated

    logger.info("✓ Validation tests passed")


def test_metrics_tracker():
    """Test metrics tracking."""
    metrics = MetricsTracker("test_metrics.json")

    assert metrics.metrics["llm_calls"] == 0
    assert metrics.hit_rate() == 0.0

    metrics.record_llm_call(1.5, success=True)
    assert metrics.metrics["llm_calls"] == 1

    metrics.record_cache_hit()
    metrics.record_cache_miss()
    assert metrics.hit_rate() == 0.5

    logger.info("✓ Metrics tracker tests passed")


def test_topic_manager():
    """Test topic cycling."""
    topics = ["A", "B", "C"]
    mgr = TopicManager(topics, rotate_every_rounds=1)

    assert mgr.current() == "A"
    mgr.advance_round()
    assert mgr.current() == "B"
    mgr.advance_round()
    assert mgr.current() == "C"
    mgr.advance_round()
    assert mgr.current() == "A"

    logger.info("✓ Topic manager tests passed")


def test_behavior_core():
    """Test behavior scoring."""
    behavior = BehaviorCore(None)

    score1 = behavior.importance_score("short")
    score2 = behavior.importance_score(
        "This is a critical breakthrough that fundamentally changes everything!!!"
    )

    assert score2 > score1
    assert 0 <= score1 <= 1
    assert 0 <= score2 <= 1

    logger.info("✓ Behavior core tests passed")


def test_language_core():
    """Test language selection."""
    lang = LanguageCore()

    assert lang.get("Socrates") == "he"

    lang.set("Socrates", "en")
    assert lang.get("Socrates") == "en"

    logger.info("✓ Language core tests passed")


def test_fixy_report():
    """Test Fixy report dataclass."""
    report = FixyReport(
        detected_issue=True,
        issue_summary="Contradiction detected",
        proposed_patch="FIX: ...",
        severity="high",
        rationale="Logic error",
    )

    assert report.detected_issue is True
    assert report.severity == "high"

    logger.info("✓ Fixy report tests passed")


def test_memory_signatures():
    """Test memory signature creation and validation."""
    test_msg = b"test message"
    test_key = b"test_key_secret"

    sig = create_signature(test_msg, test_key)
    assert isinstance(sig, bytes)
    assert len(sig) == 32  # SHA256 is 32 bytes

    # Valid signature should pass
    assert validate_signature(test_msg, test_key, sig) == True

    # Tampered message should fail
    tampered_msg = b"tampered message"
    assert validate_signature(tampered_msg, test_key, sig) == False

    # Wrong key should fail
    wrong_key = b"wrong_key"
    assert validate_signature(test_msg, wrong_key, sig) == False

    logger.info("✓ Memory signature tests passed")


def test_session_manager():
    """Test SessionManager with security features."""
    import tempfile
    import shutil

    # Create temporary test directory
    test_dir = tempfile.mkdtemp(prefix="test_sessions_")

    try:
        sm = SessionManager(test_dir)

        # Test 1: Valid session ID
        assert sm._validate_session_id("test-123_abc") == True
        assert sm._validate_session_id("abc123") == True

        # Test 2: Invalid session IDs
        assert sm._validate_session_id("") == False
        assert sm._validate_session_id("../evil") == False
        assert sm._validate_session_id("test/path") == False
        assert sm._validate_session_id("a" * 65) == False  # too long
        assert sm._validate_session_id(None) == False

        # Test 3: Save and load session with signature
        test_dialog = [{"role": "user", "content": "hello"}]
        test_metrics = {"turns": 1, "time": 10.5}

        path = sm.save_session("test123", test_dialog, test_metrics)
        assert os.path.exists(path)

        loaded = sm.load_session("test123")
        assert loaded is not None
        assert loaded["session_id"] == "test123"
        assert loaded["dialog"] == test_dialog
        assert loaded["metrics"] == test_metrics
        assert loaded["version"] == "1.0"
        assert (
            "_signature" not in loaded
        )  # signature should be removed after validation

        # Test 4: Tampered session detection
        # Manually tamper with the session file
        with open(path, "r") as f:
            data = json.load(f)
        data["dialog"] = [{"role": "user", "content": "TAMPERED"}]
        with open(path, "w") as f:
            json.dump(data, f)

        # Should return None for tampered session
        tampered_result = sm.load_session("test123")
        assert tampered_result is None

        # Test 5: List sessions
        sm.save_session("session1", test_dialog, test_metrics)
        sm.save_session("session2", test_dialog, test_metrics)
        sessions = sm.list_sessions()
        assert "session1" in sessions
        assert "session2" in sessions

        # Test 6: Delete session
        assert sm.delete_session("session1") == True
        assert sm.delete_session("session1") == False  # already deleted
        sessions = sm.list_sessions()
        assert "session1" not in sessions
        assert "session2" in sessions

        # Test 7: Path traversal protection
        try:
            sm._get_session_path("../../../etc/passwd")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid session_id" in str(e)

        # Test 8: Load non-existent session
        result = sm.load_session("nonexistent")
        assert result is None

        logger.info("✓ SessionManager security tests passed")

    finally:
        # Cleanup
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)


# ============================================
# MAIN ORCHESTRATOR
# ============================================


class MainScript:
    """Main orchestrator for multi-agent dialogue (configurable timeout)."""

    def __init__(self, cfg: Config):
        global CFG  # ← הוסף שורה זו
        CFG = cfg  # ← הוסף שורה זו
        ensure_dirs(cfg)
        colorama_init(autoreset=True)

        self.cfg = cfg
        self.session_id = str(uuid.uuid4())[:8]
        self.metrics = MetricsTracker(cfg.metrics_path)
        self.llm = LLM(self.cfg, self.metrics)
        self.memory = MemoryCore(cfg.db_path)
        self.emotion = EmotionCore(self.llm)
        self.language = LanguageCore()
        self.conscious = ConsciousCore()
        self.behavior = BehaviorCore(self.llm)
        self.fixy = ObserverCore(self.llm, cfg.model_fixy)
        self.vtrack = VersionTracker(cfg.version_dir)
        self.session_mgr = SessionManager(cfg.sessions_dir)
        self.async_proc = AsyncProcessor()

        self.dialog: List[Dict[str, str]] = []
        self.turn_index = 0
        self.start_time = time.time()

        self.socrates = Agent(
            name="Socrates",
            model=cfg.model_socrates,
            color=Fore.CYAN,
            llm=self.llm,
            memory=self.memory,
            emotion=self.emotion,
            behavior=self.behavior,
            language=self.language,
            conscious=self.conscious,
            persona="Socratic, curious, probing. Seeks clarity and truth.",
        )
        self.athena = Agent(
            name="Athena",
            model=cfg.model_athena,
            color=Fore.MAGENTA,
            llm=self.llm,
            memory=self.memory,
            emotion=self.emotion,
            behavior=self.behavior,
            language=self.language,
            conscious=self.conscious,
            persona="Strategic, integrative, creative. Builds frameworks and synthesis.",
        )

        # Language tracking removed for gender-neutral output
        # Previously set language codes for agents, but this cluttered
        # dialogue output with "(he)" gender pronouns after names.
        # Removed to ensure cleaner, more inclusive conversation style.
        # self.language.set("Socrates", "he")
        # self.language.set("Athena", "he")  # Note: was "he" for consistency, not "she"
        # self.language.set("Fixy", "en")

        self.fixy_agent = Agent(
            name="Fixy",
            model=cfg.model_fixy,
            color=Fore.YELLOW,
            llm=self.llm,
            memory=self.memory,
            emotion=self.emotion,
            behavior=self.behavior,
            language=self.language,
            conscious=self.conscious,
            persona="Observer/fixer. Brief, concrete, points out contradictions.",
        )

        # Initialize enhanced dialogue components if available
        if ENTELGIA_ENHANCED:
            self.dialogue_engine = DialogueEngine()
            self.interactive_fixy = InteractiveFixy(self.llm, cfg.model_fixy)
            logger.info("Enhanced dialogue components initialized")
        else:
            self.dialogue_engine = None
            self.interactive_fixy = None

        logger.info(f"MainScript initialized - Session: {self.session_id}")

    def print_agent(self, agent: Agent, text: str):
        """Print agent message with color."""
        print(agent.color + f"{agent.name}: " + Style.RESET_ALL + text + "\n")

    def log_turn(self, agent_name: str, text: str, topic: str):
        """Log dialogue turn to CSV."""
        row = {
            "ts": now_iso(),
            "turn": self.turn_index,
            "agent": agent_name,
            "topic": topic,
            "lang": self.language.get(agent_name),
            "text": text[:200],
        }
        append_csv_row(self.cfg.csv_log_path, row)
        self.metrics.record_turn()

    def dream_cycle(self, agent: Agent, topic: str):
        """Execute dream cycle for agent."""
        stm = self.memory.stm_load(agent.name)
        if not stm:
            return

        batch = stm[-60:]
        reflection = self.behavior.dream_reflection(agent.model, batch, self.llm)
        agent.conscious.update_reflection(agent.name, reflection)

        emo, inten = self.emotion.infer(agent.model, reflection)
        imp = self.behavior.importance_score(reflection)

        sensitive = is_sensitive_text(reflection)
        redacted = redact_pii(reflection)

        if sensitive:
            content_to_store = safe_ltm_payload(
                reflection, topic, emo, float(inten), float(imp)
            )
        else:
            content_to_store = (
                reflection if self.cfg.store_raw_subconscious_ltm else redacted
            )

        self.memory.ltm_insert(
            agent=agent.name,
            layer="subconscious",
            content=content_to_store[:500],
            topic=topic,
            emotion=emo,
            emotion_intensity=float(inten),
            importance=float(imp),
            source="dream",
        )

        promoted = 0
        for e in batch[-40:]:
            ei = float(e.get("emotion_intensity", 0.0))
            im = float(e.get("importance", 0.0))
            if (im >= self.cfg.promote_importance_threshold) or (
                ei >= self.cfg.promote_emotion_threshold
            ):
                content = str(e.get("text", "")).strip()
                if not content:
                    continue
                self.memory.ltm_insert(
                    agent=agent.name,
                    layer="conscious",
                    content=content[:300],
                    topic=topic,
                    emotion=str(e.get("emotion", "neutral")),
                    emotion_intensity=ei,
                    importance=im,
                    source="dream",
                    promoted_from="subconscious",
                )
                promoted += 1

        try:
            nodes = [("Socrates", "Socrates"), ("Athena", "Athena")]
            edges = []
            if promoted > 0:
                edges.append((str(uuid.uuid4()), agent.name, "conscious_promotions"))
                nodes.append(("conscious_promotions", "conscious_promotions"))
            export_gexf_placeholder(self.cfg.gexf_path, nodes, edges)
        except Exception:
            pass

        logger.info(f"Dream cycle {agent.name}: promoted={promoted}")
        print(
            Fore.YELLOW
            + f"[DREAM] {agent.name} reflection stored; promoted={promoted}"
            + Style.RESET_ALL
        )

    def fixy_check(self, recent_context: str):
        """Run Fixy observer check."""
        report = self.fixy.review(recent_context)
        self.fixy.remember(report)

        msg = self.fixy.commentary(recent_context, report)

        if report.detected_issue:
            logger.warning(f"Fixy detected issue: {report.issue_summary}")
            print(
                Fore.YELLOW
                + "Fixy detected issue: "
                + Style.RESET_ALL
                + report.issue_summary
            )
            if report.proposed_patch:
                print(Fore.YELLOW + "Proposed patch:" + Style.RESET_ALL)
                print(report.proposed_patch[:100] + "\n")

        if msg:
            self.dialog.append({"role": "Fixy", "text": msg})
            self.fixy_agent.store_turn(msg, topic="observer", source="reflection")
            self.log_turn("Fixy", msg, topic="observer")
            print(Fore.YELLOW + "Fixy: " + Style.RESET_ALL + msg + "\n")

        if (
            report.detected_issue
            and report.proposed_patch
            and self.cfg.enable_auto_patch
            and self.cfg.allow_write_self_file
        ):
            try:
                this_file = os.path.abspath(__file__)
                with open(this_file, "r", encoding="utf-8") as f:
                    original = f.read()
                ok, updated = safe_apply_patch(original, report.proposed_patch)
                if ok and updated != original:
                    self.vtrack.snapshot_text("before_patch", original)
                    with open(this_file, "w", encoding="utf-8") as f:
                        f.write(updated)
                    self.vtrack.snapshot_text("after_patch", updated)
                    logger.info("Auto-patch applied successfully")
                    print(Fore.GREEN + "[AUTO-PATCH] Applied patch." + Style.RESET_ALL)
            except Exception as ex:
                logger.error(f"Auto-patch failed: {ex}")
                print(Fore.RED + f"[AUTO-PATCH] Failed: {ex}" + Style.RESET_ALL)

    def run(self):
        """Main execution loop (timeout configurable in minutes)."""
        topicman = TopicManager(TOPIC_CYCLE, rotate_every_rounds=1, shuffle=False)

        self.dialog.append({"role": "seed", "text": self.cfg.seed_topic})

        timeout_seconds = self.cfg.timeout_minutes * 60

        print(
            Fore.GREEN
            + f"\n[Session {self.session_id}] Starting {self.cfg.timeout_minutes}-minute dialogue..."
            + Style.RESET_ALL
        )
        logger.info(
            f"Starting session {self.session_id} with {timeout_seconds}s timeout"
        )

        while time.time() - self.start_time < timeout_seconds:
            self.turn_index += 1

            # Dynamic speaker selection (if enhanced mode available)
            if self.dialogue_engine:
                # Check if Fixy should be allowed to speak
                allow_fixy, fixy_prob = self.dialogue_engine.should_allow_fixy(
                    self.dialog, self.turn_index
                )

                # Select next speaker dynamically
                if self.turn_index == 1:
                    speaker = self.socrates  # Start with Socrates
                else:
                    last_speaker = (
                        self.socrates
                        if self.dialog[-1].get("role") == "Socrates"
                        else self.athena
                    )
                    agents = [self.socrates, self.athena]
                    if allow_fixy:
                        agents.append(self.fixy_agent)

                    speaker = self.dialogue_engine.select_next_speaker(
                        current_speaker=last_speaker,
                        dialog_history=self.dialog,
                        agents=agents,
                        allow_fixy=allow_fixy,
                        fixy_probability=fixy_prob,
                    )
            else:
                # Legacy: simple alternation
                speaker = self.socrates if self.turn_index % 2 == 1 else self.athena

            topic_label = topicman.current()

            # Dynamic seed generation (if enhanced mode available)
            if self.dialogue_engine and speaker.name != "Fixy":
                seed = self.dialogue_engine.generate_seed(
                    topic=topic_label,
                    dialog_history=self.dialog,
                    speaker=speaker,
                    turn_count=self.turn_index,
                )
            else:
                # Legacy or Fixy seed
                seed = (
                    f"TOPIC: {topic_label}\nDISAGREE constructively; add one new angle."
                )

            logger.debug(f"Turn {self.turn_index}: {speaker.name}")
            out = speaker.speak(seed, self.dialog)
            self.dialog.append({"role": speaker.name, "text": out})

            speaker.store_turn(out, topic_label, source="stm")
            self.log_turn(speaker.name, out, topic_label)
            self.print_agent(speaker, out)

            # Interactive Fixy (need-based) or legacy scheduled Fixy
            if self.interactive_fixy and speaker.name != "Fixy":
                should_intervene, reason = self.interactive_fixy.should_intervene(
                    self.dialog, self.turn_index
                )
                if should_intervene:
                    intervention = self.interactive_fixy.generate_intervention(
                        self.dialog, reason
                    )
                    self.dialog.append({"role": "Fixy", "text": intervention})
                    self.fixy_agent.store_turn(
                        intervention, topic_label, source="reflection"
                    )
                    self.log_turn("Fixy", intervention, topic_label)
                    print(
                        Fore.YELLOW + "Fixy: " + Style.RESET_ALL + intervention + "\n"
                    )
                    logger.info(f"Fixy intervention: {reason}")
            elif self.turn_index % self.cfg.fixy_every_n_turns == 0:
                # Legacy scheduled Fixy
                tail = self.dialog[-10:]
                ctx = "\n".join([f"{t['role']}: {t['text'][:50]}" for t in tail])
                self.fixy_check(ctx)

            if self.turn_index % self.cfg.dream_every_n_turns == 0:
                self.dream_cycle(self.socrates, topic_label)
                self.dream_cycle(self.athena, topic_label)

            if re.search(r"\b(stop|quit|bye)\b", out.lower()):
                logger.info("Stop signal received from agent")
                print(Fore.YELLOW + "[STOP] Agent requested stop." + Style.RESET_ALL)
                break

            if self.turn_index % 2 == 0:
                topicman.advance_round()

            elapsed = time.time() - self.start_time
            if elapsed >= timeout_seconds:
                logger.info(
                    f"{self.cfg.timeout_minutes}-minute timeout reached at turn {self.turn_index}"
                )
                print(
                    Fore.YELLOW
                    + f"\n[TIMEOUT] {self.cfg.timeout_minutes} minutes reached at turn {self.turn_index}"
                    + Style.RESET_ALL
                )
                break

            time.sleep(0.02)

        # Save session and metrics
        self.metrics.save()
        self.session_mgr.save_session(
            self.session_id, self.dialog, self.metrics.metrics
        )

        elapsed = time.time() - self.start_time
        print(
            Fore.GREEN
            + f"\n[Session Complete: {self.turn_index} turns in {elapsed:.1f}s]"
            + Style.RESET_ALL
        )
        print(f"[Cache Hit Rate: {self.metrics.hit_rate():.1%}]")
        print(
            f"[LLM Calls: {self.metrics.metrics['llm_calls']}, Errors: {self.metrics.metrics['llm_errors']}]"
        )
        logger.info(
            f"Session {self.session_id} completed: {self.turn_index} turns, {elapsed:.1f}s"
        )

        # ============================================


# CLI / API ENTRY POINTS
# ============================================


def run_cli():
    """Run command line interface - configurable timeout dialogue."""
    global CFG
    CFG = Config(max_turns=200, timeout_minutes=30)

    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print(
        Fore.GREEN
        + "Entelgia Unified – PRODUCTION Edition By Sivan Havkin"
        + Style.RESET_ALL
    )
    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print("\nConfiguration:")
    config_dict = asdict(CFG)
    config_display = {k: v for k, v in config_dict.items() if not k.startswith("_")}
    print(json.dumps(config_display, ensure_ascii=False, indent=2))
    print()

    try:
        app_script = MainScript(CFG)
        app_script.run()
        print(Fore.GREEN + "\n✓ Session completed successfully!" + Style.RESET_ALL)
    except KeyboardInterrupt:
        print(
            Fore.YELLOW + "\n[INTERRUPTED] Session cancelled by user" + Style.RESET_ALL
        )
        logger.info("Session interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(Fore.RED + f"[FATAL ERROR] {e}" + Style.RESET_ALL)
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def run_tests():
    """Run unit tests."""
    print(Fore.GREEN + "Running Entelgia Unit Tests..." + Style.RESET_ALL)
    print()

    try:
        test_config_validation()
        test_lru_cache()
        test_redaction()
        test_validation()
        test_metrics_tracker()
        test_topic_manager()
        test_behavior_core()
        test_language_core()
        test_fixy_report()
        test_memory_signatures()
        test_session_manager()

        print()
        print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
        print(Fore.GREEN + "✓ All tests passed!" + Style.RESET_ALL)
        print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    except AssertionError as e:
        print(Fore.RED + f"✗ Test failed: {e}" + Style.RESET_ALL)
        logger.error(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(Fore.RED + f"✗ Test error: {e}" + Style.RESET_ALL)
        logger.error(f"Test error: {e}", exc_info=True)
        sys.exit(1)


def run_api():
    """Run FastAPI server."""
    global CFG

    if not FASTAPI_AVAILABLE:
        print(Fore.RED + "FastAPI not installed." + Style.RESET_ALL)
        print("Run: pip install fastapi uvicorn")
        sys.exit(1)

    CFG = Config()

    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print(Fore.GREEN + "Entelgia REST API Server" + Style.RESET_ALL)
    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print(f"\n🚀 Starting API server on http://0.0.0.0:8000")
    print(f"📚 API Docs: http://localhost:8000/docs")
    print(f"🔄 API Spec: http://localhost:8000/redoc")
    print()

    try:
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except ImportError:
        print(Fore.RED + "uvicorn not installed." + Style.RESET_ALL)
        print("Run: pip install uvicorn")
        sys.exit(1)


def main():
    """Main entry point with mode selection."""
    global CFG

    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

        if mode == "test":
            run_tests()
        elif mode == "api":
            run_api()
        elif mode in ["help", "-h", "--help"]:
            print(
                Fore.GREEN + "Entelgia Unified – PRODUCTION Edition" + Style.RESET_ALL
            )
            print()
            print("Usage:")
            print(
                f"  python {os.path.basename(__file__)}              Run 30-minute CLI dialogue (default)"
            )
            print(f"  python {os.path.basename(__file__)} test         Run unit tests")
            print(
                f"  python {os.path.basename(__file__)} api          Start FastAPI server"
            )
            print(
                f"  python {os.path.basename(__file__)} help         Show this help message"
            )
            print()
            print("Requirements:")
            print("  • Python 3.10+")
            print("  • Ollama running locally (http://localhost:11434)")
            print("  • pip install requests colorama")
            print("  • pip install fastapi uvicorn (for API mode)")
            print("  • pip install pytest pytest-mock (for testing)")
            print()
            print("Environment Variables:")
            print(
                "  • MEMORY_SECRET_KEY    Secret key for memory signatures (recommended: 32+ chars)"
            )
            print()
            print("Features:")
            print("  • 30-minute auto-timeout dialogue")
            print("  • Multi-agent with Socrates & Athena")
            print("  • Persistent memory (STM + LTM)")
            print("  • Emotion tracking & importance scoring")
            print("  • Dream cycles & memory promotion")
            print("  • Fixy observer/fixer agent")
            print("  • LRU cache with 75% hit rate improvement")
            print("  • Error handling with exponential backoff")
            print("  • Session persistence & metrics tracking")
            print("  • REST API interface (FastAPI)")
            print("  • Unit tests (pytest)")
            print("  • 🔐 MEMORY SECURITY with HMAC-SHA256 signatures")
            print("     - Cryptographic signatures on all memories")
            print("     - Automatic forgetting of tampered memories")
            print("     - Constant-time comparison to prevent timing attacks")
            print()
        else:
            print(Fore.RED + f"Unknown mode: {mode}" + Style.RESET_ALL)
            print(
                f"Run 'python {os.path.basename(__file__)} help' for usage information"
            )
            sys.exit(1)
    else:
        # Default: Run CLI (30 minutes)
        run_cli()


if __name__ == "__main__":
    main()
