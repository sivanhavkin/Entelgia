# tests/test_memory_security.py
"""
Tests for memory security module.

Tests HMAC-SHA256 signature creation and validation
to ensure memory integrity and tamper detection.
"""

import os
import tempfile

import pytest
from entelgia.memory_security import create_signature, validate_signature


class TestSignatureCreation:
    """Tests for signature creation."""

    def test_create_signature_success(self, test_secret_key, sample_message):
        """Test successful signature creation."""
        signature = create_signature(sample_message, test_secret_key)

        assert signature is not None
        assert len(signature) == 64  # SHA256 hex = 64 characters
        assert isinstance(signature, str)
        assert all(c in "0123456789abcdef" for c in signature)

    def test_create_signature_deterministic(self, test_secret_key, sample_message):
        """Test that signature creation is deterministic."""
        sig1 = create_signature(sample_message, test_secret_key)
        sig2 = create_signature(sample_message, test_secret_key)

        assert sig1 == sig2

    def test_create_signature_different_messages(self, test_secret_key):
        """Test that different messages produce different signatures."""
        sig1 = create_signature("message 1", test_secret_key)
        sig2 = create_signature("message 2", test_secret_key)

        assert sig1 != sig2

    def test_create_signature_empty_message(self, test_secret_key):
        """Test that empty message raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            create_signature("", test_secret_key)

    def test_create_signature_empty_key(self, sample_message):
        """Test that empty key raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            create_signature(sample_message, "")

    def test_create_signature_none_message(self, test_secret_key):
        """Test that None message raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            create_signature(None, test_secret_key)

    def test_create_signature_none_key(self, sample_message):
        """Test that None key raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            create_signature(sample_message, None)


class TestSignatureValidation:
    """Tests for signature validation."""

    def test_validate_signature_success(self, test_secret_key, sample_message):
        """Test successful signature validation."""
        signature = create_signature(sample_message, test_secret_key)
        is_valid = validate_signature(sample_message, test_secret_key, signature)

        assert is_valid is True

    def test_validate_signature_wrong_key(self, test_secret_key, sample_message):
        """Test that wrong key fails validation."""
        signature = create_signature(sample_message, test_secret_key)
        is_valid = validate_signature(sample_message, "wrong_key", signature)

        assert is_valid is False

    def test_validate_signature_tampered_message(self, test_secret_key, sample_message):
        """Test that tampered message fails validation."""
        signature = create_signature(sample_message, test_secret_key)
        is_valid = validate_signature("Tampered message!", test_secret_key, signature)

        assert is_valid is False

    def test_validate_signature_tampered_signature(
        self, test_secret_key, sample_message
    ):
        """Test that tampered signature fails validation."""
        signature = create_signature(sample_message, test_secret_key)
        tampered_sig = signature[:-1] + "x"  # Change last character
        is_valid = validate_signature(sample_message, test_secret_key, tampered_sig)

        assert is_valid is False

    def test_validate_signature_none_message(self, test_secret_key):
        """Test that None message returns False."""
        is_valid = validate_signature(None, test_secret_key, "somesig")
        assert is_valid is False

    def test_validate_signature_none_key(self, sample_message):
        """Test that None key returns False."""
        is_valid = validate_signature(sample_message, None, "somesig")
        assert is_valid is False

    def test_validate_signature_none_signature(self, test_secret_key, sample_message):
        """Test that None signature returns False."""
        is_valid = validate_signature(sample_message, test_secret_key, None)
        assert is_valid is False

    def test_validate_signature_empty_values(self):
        """Test that empty strings return False."""
        assert validate_signature("", "key", "sig") is False
        assert validate_signature("msg", "", "sig") is False
        assert validate_signature("msg", "key", "") is False

    def test_validate_signature_invalid_hex(self, test_secret_key, sample_message):
        """Test that invalid hex signature returns False."""
        is_valid = validate_signature(
            sample_message, test_secret_key, "not_hex_string!"
        )
        assert is_valid is False


class TestSecurityProperties:
    """Tests for cryptographic security properties."""

    def test_signature_uniqueness(self, test_secret_key):
        """Test that different inputs produce different signatures."""
        messages = ["msg1", "msg2", "msg3", "msg4", "msg5"]
        signatures = [create_signature(msg, test_secret_key) for msg in messages]

        # All signatures should be unique
        assert len(set(signatures)) == len(signatures)

    def test_key_sensitivity(self, sample_message):
        """Test that different keys produce different signatures."""
        keys = ["key1", "key2", "key3", "key4", "key5"]
        signatures = [create_signature(sample_message, key) for key in keys]

        # All signatures should be unique
        assert len(set(signatures)) == len(signatures)

    def test_unicode_support(self, test_secret_key):
        """Test that unicode messages are handled correctly."""
        messages = [
            "Hello World",  # English
            "Hello 世界",  # Mixed
            "مرحبا",  # Arabic
            "🎉🎊✨",  # Emojis
        ]

        for msg in messages:
            signature = create_signature(msg, test_secret_key)
            assert len(signature) == 64
            assert validate_signature(msg, test_secret_key, signature)


class TestLtmPayloadConsistency:
    """Tests for LTM signature payload consistency in the production MemoryCore.

    Validates that insertion and validation always use the same canonical
    payload representation so that signatures never fail due to formatting
    differences (e.g. Python ``None`` becoming the string ``"None"``).
    """

    @pytest.fixture
    def memory_core(self, tmp_path):
        """Provide a MemoryCore backed by a temp SQLite database."""
        import sys
        import importlib.util

        # Isolate the environment key so we control it.
        original_key = os.environ.get("MEMORY_SECRET_KEY")
        os.environ["MEMORY_SECRET_KEY"] = "test-key-payload-consistency-1234"
        data_dir = str(tmp_path)
        os.environ["ENTELGIA_DATA_DIR"] = data_dir

        spec = importlib.util.spec_from_file_location(
            "Entelgia_production_meta_test",
            os.path.join(os.path.dirname(__file__), "..", "Entelgia_production_meta.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["Entelgia_production_meta_test"] = mod
        spec.loader.exec_module(mod)

        db_path = os.path.join(data_dir, "test_payload.db")
        mc = mod.MemoryCore(db_path)

        yield mc, mod

        # Cleanup
        sys.modules.pop("Entelgia_production_meta_test", None)
        if original_key is None:
            os.environ.pop("MEMORY_SECRET_KEY", None)
        else:
            os.environ["MEMORY_SECRET_KEY"] = original_key

    def test_build_ltm_payload_none_values(self, memory_core):
        """None topic/emotion must produce empty-string segments."""
        mc, mod = memory_core
        payload = mod.MemoryCore._build_ltm_payload(
            "content", None, None, "2026-01-01T00:00:00Z"
        )
        assert payload == "content|||2026-01-01T00:00:00Z"

    def test_build_ltm_payload_empty_string_same_as_none(self, memory_core):
        """Empty-string values must produce the same payload as None."""
        mc, mod = memory_core
        payload_none = mod.MemoryCore._build_ltm_payload(
            "content", None, None, "2026-01-01T00:00:00Z"
        )
        payload_empty = mod.MemoryCore._build_ltm_payload(
            "content", "", "", "2026-01-01T00:00:00Z"
        )
        assert payload_none == payload_empty

    def test_build_ltm_payload_non_null(self, memory_core):
        """Non-null values must appear verbatim in the payload."""
        mc, mod = memory_core
        payload = mod.MemoryCore._build_ltm_payload(
            "hello", "philosophy", "curious", "2026-01-01T00:00:00Z"
        )
        assert payload == "hello|philosophy|curious|2026-01-01T00:00:00Z"

    def test_insert_and_retrieve_validates_correctly(self, memory_core):
        """Memories inserted then retrieved must pass signature validation."""
        mc, _ = memory_core
        mc.ltm_insert(
            "TestAgent",
            "subconscious",
            "Test memory",
            topic="philosophy",
            emotion="curious",
            emotion_intensity=0.7,
            importance=0.8,
        )
        memories = mc.ltm_recent("TestAgent")
        assert len(memories) == 1
        assert memories[0]["content"] == "Test memory"

    def test_insert_with_none_topic_emotion_validates(self, memory_core):
        """Memories inserted with None topic/emotion must validate."""
        mc, _ = memory_core
        mc.ltm_insert(
            "TestAgent",
            "subconscious",
            "Memory without topic or emotion",
            topic=None,
            emotion=None,
        )
        memories = mc.ltm_recent("TestAgent")
        assert len(memories) == 1

    def test_key_rotation_re_signs_memories(self, tmp_path):
        """After MEMORY_SECRET_KEY changes, existing memories must still validate."""
        import sys
        import importlib.util

        db_path = os.path.join(str(tmp_path), "rotate_key.db")
        data_dir = str(tmp_path)

        def _load_core(key: str):
            """Load a fresh MemoryCore module instance with *key*."""
            os.environ["MEMORY_SECRET_KEY"] = key
            os.environ["ENTELGIA_DATA_DIR"] = data_dir
            mod_name = f"Entelgia_production_meta_rot_{key[:6]}"
            spec = importlib.util.spec_from_file_location(
                mod_name,
                os.path.join(
                    os.path.dirname(__file__), "..", "Entelgia_production_meta.py"
                ),
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            mc = mod.MemoryCore(db_path)
            return mc, mod_name

        # Phase 1: create memories with key-A
        mc1, mod_name1 = _load_core("key-A-original-secret-12345")
        mc1.ltm_insert(
            "Socrates", "subconscious", "Virtue is knowledge",
            topic="ethics", emotion="reflective"
        )
        mc1.ltm_insert(
            "Socrates", "subconscious", "Unexamined life",
            topic="existence", emotion="contemplative"
        )
        mems_phase1 = mc1.ltm_recent("Socrates")
        assert len(mems_phase1) == 2, "Both memories must validate with key-A"
        sys.modules.pop(mod_name1, None)

        # Phase 2: reload with key-B (simulates .env change / key rotation)
        mc2, mod_name2 = _load_core("key-B-new-rotated-secret-67890")
        mems_phase2 = mc2.ltm_recent("Socrates")
        assert len(mems_phase2) == 2, (
            "After key rotation, memories must still be accessible "
            "(re-signed during MemoryCore init)"
        )

        # Phase 3: new memories inserted after rotation must also validate
        mc2.ltm_insert("Socrates", "conscious", "Know thyself",
                       topic="wisdom", emotion="serene")
        mems_phase3 = mc2.ltm_recent("Socrates")
        assert len(mems_phase3) == 3, "New memory must also validate with key-B"
        sys.modules.pop(mod_name2, None)


class TestLtmTrimConscious:
    """Tests for MemoryCore.ltm_trim_conscious() — the dream-cycle forgetting phase."""

    @pytest.fixture
    def memory_core(self, tmp_path):
        """Provide a MemoryCore backed by a temp SQLite database."""
        import sys
        import importlib.util

        original_key = os.environ.get("MEMORY_SECRET_KEY")
        os.environ["MEMORY_SECRET_KEY"] = "test-key-trim-conscious-1234567890"
        data_dir = str(tmp_path)
        os.environ["ENTELGIA_DATA_DIR"] = data_dir

        spec = importlib.util.spec_from_file_location(
            "Entelgia_production_meta_trim",
            os.path.join(os.path.dirname(__file__), "..", "Entelgia_production_meta.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["Entelgia_production_meta_trim"] = mod
        spec.loader.exec_module(mod)

        db_path = os.path.join(data_dir, "test_trim.db")
        mc = mod.MemoryCore(db_path)

        yield mc, mod

        sys.modules.pop("Entelgia_production_meta_trim", None)
        if original_key is None:
            os.environ.pop("MEMORY_SECRET_KEY", None)
        else:
            os.environ["MEMORY_SECRET_KEY"] = original_key

    def _insert_conscious(self, mc, agent: str, count: int):
        """Insert *count* conscious memories for *agent* with distinct timestamps."""
        for i in range(count):
            ts = f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}Z"
            mc.ltm_insert(agent, "conscious", f"Conscious memory {i}",
                          topic="test", emotion="neutral", ts=ts)

    def test_trim_removes_old_entries(self, memory_core):
        """ltm_trim_conscious keeps only the N most recent conscious entries."""
        mc, _ = memory_core
        self._insert_conscious(mc, "Socrates", 10)
        assert len(mc.ltm_recent("Socrates", limit=50, layer="conscious")) == 10

        deleted = mc.ltm_trim_conscious("Socrates", keep=5)
        assert deleted == 5
        remaining = mc.ltm_recent("Socrates", limit=50, layer="conscious")
        assert len(remaining) == 5

    def test_trim_keeps_most_recent(self, memory_core):
        """ltm_trim_conscious retains the most recent entries."""
        mc, _ = memory_core
        self._insert_conscious(mc, "Athena", 6)
        mc.ltm_trim_conscious("Athena", keep=3)
        remaining = mc.ltm_recent("Athena", limit=50, layer="conscious")
        # The remaining 3 should be the most recent (highest-numbered content)
        contents = {m["content"] for m in remaining}
        assert "Conscious memory 5" in contents
        assert "Conscious memory 4" in contents
        assert "Conscious memory 3" in contents

    def test_trim_does_not_touch_subconscious(self, memory_core):
        """ltm_trim_conscious must not delete subconscious entries."""
        mc, _ = memory_core
        for i in range(8):
            mc.ltm_insert("Socrates", "subconscious", f"Subconscious {i}")
        self._insert_conscious(mc, "Socrates", 8)

        mc.ltm_trim_conscious("Socrates", keep=2)

        subconscious = mc.ltm_recent("Socrates", limit=50, layer="subconscious")
        assert len(subconscious) == 8  # Subconscious untouched

    def test_trim_keep_more_than_existing_no_deletion(self, memory_core):
        """When keep >= existing entries, nothing should be deleted."""
        mc, _ = memory_core
        self._insert_conscious(mc, "Socrates", 3)
        deleted = mc.ltm_trim_conscious("Socrates", keep=10)
        assert deleted == 0
        remaining = mc.ltm_recent("Socrates", limit=50, layer="conscious")
        assert len(remaining) == 3

    def test_trim_empty_conscious_layer(self, memory_core):
        """trim on an agent with no conscious memories returns 0."""
        mc, _ = memory_core
        deleted = mc.ltm_trim_conscious("NonExistentAgent", keep=5)
        assert deleted == 0

    def test_dream_cycle_config_default(self, memory_core):
        """dream_keep_memories default is 5 in Config."""
        _, mod = memory_core
        cfg = mod.Config()
        assert cfg.dream_keep_memories == 5
