# tests/test_memory_signing_migration.py
"""
Tests for MemoryCore signature migration (_migrate_signing_key).

Verifies that:
- A key fingerprint is persisted in the settings table on first init.
- When the stored fingerprint mismatches the current key, all LTM rows are
  re-signed so that ltm_recent() can retrieve them without INVALID SIGNATURE
  warnings.
- Memories inserted with the old "None"-literal payload format are recovered.
"""

import hashlib
import os
import sqlite3
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Entelgia_production_meta import (  # noqa: E402
    MemoryCore,
    MEMORY_SECRET_KEY_BYTES,
    create_signature,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_fingerprint() -> str:
    return hashlib.sha256(MEMORY_SECRET_KEY_BYTES).hexdigest()


def _stored_fingerprint(db_path: str) -> str | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT value FROM settings WHERE key='key_fingerprint'"
    ).fetchone()
    conn.close()
    return row["value"] if row else None


def _insert_legacy_row(
    db_path: str,
    agent: str,
    content: str,
    topic: str | None,
    emotion: str | None,
    ts: str,
) -> str:
    """Insert a memory row signed with the legacy f-string payload format."""
    mem_id = str(uuid.uuid4())
    legacy_payload = f"{content}|{topic}|{emotion}|{ts}"
    sig = create_signature(legacy_payload.encode("utf-8"), MEMORY_SECRET_KEY_BYTES)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO memories (id, agent, ts, layer, content, topic, emotion, signature_hex)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (mem_id, agent, ts, "conscious", content, topic, emotion, sig.hex()),
    )
    conn.commit()
    conn.close()
    return mem_id


def _corrupt_fingerprint(db_path: str) -> None:
    """Simulate a key change by replacing the stored fingerprint."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE settings SET value='stale-fake-fingerprint' WHERE key='key_fingerprint'"
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMigrateSigningKey:
    """Tests for MemoryCore._migrate_signing_key()."""

    def test_fingerprint_stored_on_first_init(self, temp_db_path):
        """A fresh DB should have the current key fingerprint in settings."""
        MemoryCore(temp_db_path)
        assert _stored_fingerprint(temp_db_path) == _current_fingerprint()

    def test_no_re_sign_when_fingerprint_matches(self, temp_db_path):
        """If the fingerprint is already correct, no rows are re-signed."""
        mc = MemoryCore(temp_db_path)
        mc.ltm_insert("agent", "conscious", "hello", topic="t", emotion="joy")

        # Fetch the signature before a second init
        conn = sqlite3.connect(temp_db_path)
        conn.row_factory = sqlite3.Row
        sig_before = conn.execute("SELECT signature_hex FROM memories").fetchone()[
            "signature_hex"
        ]
        conn.close()

        # Second init should be a no-op (fingerprint already matches)
        MemoryCore(temp_db_path)

        conn = sqlite3.connect(temp_db_path)
        conn.row_factory = sqlite3.Row
        sig_after = conn.execute("SELECT signature_hex FROM memories").fetchone()[
            "signature_hex"
        ]
        conn.close()

        assert sig_before == sig_after

    def test_re_sign_on_fingerprint_mismatch(self, temp_db_path):
        """When the fingerprint mismatches, all rows are re-signed."""
        mc = MemoryCore(temp_db_path)
        mc.ltm_insert("agent", "conscious", "test memory")

        _corrupt_fingerprint(temp_db_path)

        # Second init must detect mismatch and re-sign
        mc2 = MemoryCore(temp_db_path)
        assert _stored_fingerprint(temp_db_path) == _current_fingerprint()

        # Memory should still be retrievable without INVALID SIGNATURE
        mems = mc2.ltm_recent("agent")
        assert len(mems) == 1
        assert mems[0]["content"] == "test memory"

    def test_legacy_format_memory_recovered_after_migration(self, temp_db_path):
        """Legacy rows (signed with 'None' literal) are recovered via migration."""
        import datetime

        # Create the schema first (without inserting via MemoryCore so the row
        # bypasses _migrate_signing_key on creation).
        MemoryCore(temp_db_path)  # schema + sets fingerprint

        ts = datetime.datetime.utcnow().isoformat()
        _insert_legacy_row(
            temp_db_path, "Socrates", "Memory about truth", None, None, ts
        )

        # Corrupt the fingerprint so migration runs on next init
        _corrupt_fingerprint(temp_db_path)

        mc = MemoryCore(temp_db_path)
        mems = mc.ltm_recent("Socrates")
        assert len(mems) == 1
        assert mems[0]["content"] == "Memory about truth"

    def test_settings_table_exists(self, temp_db_path):
        """The settings table is created by _init_db."""
        MemoryCore(temp_db_path)
        conn = sqlite3.connect(temp_db_path)
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        assert "settings" in tables
