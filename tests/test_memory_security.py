# tests/test_memory_security.py
"""
Tests for memory security module.

Tests HMAC-SHA256 signature creation and validation
to ensure memory integrity and tamper detection.
"""

import pytest
from entelgia.memory_security import create_signature, validate_signature

# ---------------------------------------------------------------------------
# Terminal display helpers – tables and ASCII bar charts
# ---------------------------------------------------------------------------


def _print_table(headers, rows, title=None):
    """Print a neatly formatted ASCII table to stdout."""
    if title:
        print(f"\n  ╔{'═' * (len(title) + 4)}╗")
        print(f"  ║  {title}  ║")
        print(f"  ╚{'═' * (len(title) + 4)}╝")
    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    sep = "─┼─".join("─" * w for w in col_widths)
    header_line = " │ ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
    print(f"  {header_line}")
    print(f"  {sep}")
    for row in rows:
        print(
            "  "
            + " │ ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        )
    print()


def _print_bar_chart(data_pairs, title=None, max_width=36):
    """Print a horizontal ASCII bar chart.  *data_pairs* is [(label, value), ...]."""
    if title:
        print(f"\n  📊 {title}")
        print(f"  {'─' * 52}")
    if not data_pairs:
        return
    max_val = max(v for _, v in data_pairs) or 1.0
    for label, value in data_pairs:
        bar_len = max(1, int(round((value / max_val) * max_width)))
        bar = "█" * bar_len
        print(f"  {str(label):>10} │ {bar:<{max_width}} {value:.4f}")
    print()


class TestSignatureCreation:
    """Tests for signature creation."""

    def test_create_signature_success(self, test_secret_key, sample_message):
        """Test successful signature creation."""
        signature = create_signature(sample_message, test_secret_key)
        is_hex = all(c in "0123456789abcdef" for c in signature)
        _print_table(
            ["field", "value"],
            [
                ["message (truncated)", sample_message[:30] + "..."],
                ["key (truncated)", test_secret_key[:12] + "..."],
                ["signature (first 16+...)", signature[:16] + "..."],
                ["length", len(signature)],
                ["is_hex?", str(is_hex)],
            ],
            title="Signature Creation Success",
        )
        assert signature is not None
        assert len(signature) == 64  # SHA256 hex = 64 characters
        assert isinstance(signature, str)
        assert is_hex

    def test_create_signature_deterministic(self, test_secret_key, sample_message):
        """Test that signature creation is deterministic."""
        sig1 = create_signature(sample_message, test_secret_key)
        sig2 = create_signature(sample_message, test_secret_key)
        _print_table(
            ["call", "signature (first 16+...)"],
            [
                ["sig1", sig1[:16] + "..."],
                ["sig2", sig2[:16] + "..."],
                ["match?", str(sig1 == sig2)],
            ],
            title="Deterministic Signatures – Same Input",
        )
        assert sig1 == sig2

    def test_create_signature_different_messages(self, test_secret_key):
        """Test that different messages produce different signatures."""
        sig1 = create_signature("message 1", test_secret_key)
        sig2 = create_signature("message 2", test_secret_key)
        _print_table(
            ["message", "signature (first 16+...)"],
            [
                ["'message 1'", sig1[:16] + "..."],
                ["'message 2'", sig2[:16] + "..."],
                ["differ?", str(sig1 != sig2)],
            ],
            title="Different Messages → Different Signatures",
        )
        assert sig1 != sig2

    def test_create_signature_empty_message(self, test_secret_key):
        """Test that empty message raises ValueError."""
        raised = False
        try:
            create_signature("", test_secret_key)
        except ValueError:
            raised = True
        _print_table(
            ["input_message", "raises_ValueError?"],
            [["'' (empty)", str(raised)]],
            title="Empty Message → ValueError",
        )
        with pytest.raises(ValueError, match="non-empty"):
            create_signature("", test_secret_key)

    def test_create_signature_empty_key(self, sample_message):
        """Test that empty key raises ValueError."""
        raised = False
        try:
            create_signature(sample_message, "")
        except ValueError:
            raised = True
        _print_table(
            ["input_key", "raises_ValueError?"],
            [["'' (empty)", str(raised)]],
            title="Empty Key → ValueError",
        )
        with pytest.raises(ValueError, match="non-empty"):
            create_signature(sample_message, "")

    def test_create_signature_none_message(self, test_secret_key):
        """Test that None message raises ValueError."""
        raised = False
        try:
            create_signature(None, test_secret_key)
        except ValueError:
            raised = True
        _print_table(
            ["input_message", "raises_ValueError?"],
            [["None", str(raised)]],
            title="None Message → ValueError",
        )
        with pytest.raises(ValueError, match="non-empty"):
            create_signature(None, test_secret_key)

    def test_create_signature_none_key(self, sample_message):
        """Test that None key raises ValueError."""
        raised = False
        try:
            create_signature(sample_message, None)
        except ValueError:
            raised = True
        _print_table(
            ["input_key", "raises_ValueError?"],
            [["None", str(raised)]],
            title="None Key → ValueError",
        )
        with pytest.raises(ValueError, match="non-empty"):
            create_signature(sample_message, None)


class TestSignatureValidation:
    """Tests for signature validation."""

    def test_validate_signature_success(self, test_secret_key, sample_message):
        """Test successful signature validation."""
        signature = create_signature(sample_message, test_secret_key)
        is_valid = validate_signature(sample_message, test_secret_key, signature)
        _print_table(
            ["message (truncated)", "key (truncated)", "is_valid?"],
            [
                [
                    sample_message[:30] + "...",
                    test_secret_key[:12] + "...",
                    str(is_valid),
                ],
            ],
            title="Validate Signature – Success",
        )
        assert is_valid is True

    def test_validate_signature_wrong_key(self, test_secret_key, sample_message):
        """Test that wrong key fails validation."""
        signature = create_signature(sample_message, test_secret_key)
        is_valid = validate_signature(sample_message, "wrong_key", signature)
        _print_table(
            ["message (truncated)", "key_used", "is_valid?", "expected"],
            [
                [sample_message[:20] + "...", "wrong_key", str(is_valid), "False"],
            ],
            title="Validate Signature – Wrong Key",
        )
        assert is_valid is False

    def test_validate_signature_tampered_message(self, test_secret_key, sample_message):
        """Test that tampered message fails validation."""
        signature = create_signature(sample_message, test_secret_key)
        tampered = "Tampered message!"
        is_valid = validate_signature(tampered, test_secret_key, signature)
        _print_table(
            ["original_msg (truncated)", "tampered_msg", "is_valid?", "expected"],
            [
                [sample_message[:20] + "...", tampered, str(is_valid), "False"],
            ],
            title="Validate Signature – Tampered Message",
        )
        assert is_valid is False

    def test_validate_signature_tampered_signature(
        self, test_secret_key, sample_message
    ):
        """Test that tampered signature fails validation."""
        signature = create_signature(sample_message, test_secret_key)
        tampered_sig = signature[:-1] + "x"  # Change last character
        is_valid = validate_signature(sample_message, test_secret_key, tampered_sig)
        _print_table(
            ["original_sig (first 16+...)", "tampered_sig (first 16+...)", "is_valid?"],
            [
                [signature[:16] + "...", tampered_sig[:16] + "...", str(is_valid)],
            ],
            title="Validate Signature – Tampered Signature",
        )
        assert is_valid is False

    def test_validate_signature_none_message(self, test_secret_key):
        """Test that None message returns False."""
        is_valid = validate_signature(None, test_secret_key, "somesig")
        _print_table(
            ["message", "key (truncated)", "sig", "is_valid?"],
            [["None", test_secret_key[:12] + "...", "somesig", str(is_valid)]],
            title="Validate – None Message",
        )
        assert is_valid is False

    def test_validate_signature_none_key(self, sample_message):
        """Test that None key returns False."""
        is_valid = validate_signature(sample_message, None, "somesig")
        _print_table(
            ["message (truncated)", "key", "sig", "is_valid?"],
            [[sample_message[:20] + "...", "None", "somesig", str(is_valid)]],
            title="Validate – None Key",
        )
        assert is_valid is False

    def test_validate_signature_none_signature(self, test_secret_key, sample_message):
        """Test that None signature returns False."""
        is_valid = validate_signature(sample_message, test_secret_key, None)
        _print_table(
            ["message (truncated)", "key (truncated)", "sig", "is_valid?"],
            [
                [
                    sample_message[:20] + "...",
                    test_secret_key[:12] + "...",
                    "None",
                    str(is_valid),
                ]
            ],
            title="Validate – None Signature",
        )
        assert is_valid is False

    def test_validate_signature_empty_values(self):
        """Test that empty strings return False."""
        r1 = validate_signature("", "key", "sig")
        r2 = validate_signature("msg", "", "sig")
        r3 = validate_signature("msg", "key", "")
        _print_table(
            ["message", "key", "sig", "is_valid?"],
            [
                ["'' (empty)", "key", "sig", str(r1)],
                ["msg", "'' (empty)", "sig", str(r2)],
                ["msg", "key", "'' (empty)", str(r3)],
            ],
            title="Validate – Empty Values All Return False",
        )
        assert r1 is False
        assert r2 is False
        assert r3 is False

    def test_validate_signature_invalid_hex(self, test_secret_key, sample_message):
        """Test that invalid hex signature returns False."""
        bad_sig = "not_hex_string!"
        is_valid = validate_signature(sample_message, test_secret_key, bad_sig)
        _print_table(
            ["signature_input", "is_valid?"],
            [[bad_sig, str(is_valid)]],
            title="Validate – Invalid Hex Signature",
        )
        assert is_valid is False


class TestSecurityProperties:
    """Tests for cryptographic security properties."""

    def test_signature_uniqueness(self, test_secret_key):
        """Test that different inputs produce different signatures."""
        messages = ["msg1", "msg2", "msg3", "msg4", "msg5"]
        signatures = [create_signature(msg, test_secret_key) for msg in messages]
        all_unique = len(set(signatures)) == len(signatures)
        rows = [[msg, sig[:16] + "..."] for msg, sig in zip(messages, signatures)]
        rows.append(["all_unique?", str(all_unique)])
        _print_table(
            ["message", "signature (first 16+...)"],
            rows,
            title="Signature Uniqueness – Different Inputs",
        )
        assert all_unique

    def test_key_sensitivity(self, sample_message):
        """Test that different keys produce different signatures."""
        keys = ["key1", "key2", "key3", "key4", "key5"]
        signatures = [create_signature(sample_message, key) for key in keys]
        all_unique = len(set(signatures)) == len(signatures)
        rows = [[key, sig[:16] + "..."] for key, sig in zip(keys, signatures)]
        rows.append(["all_unique?", str(all_unique)])
        _print_table(
            ["key", "signature (first 16+...)"],
            rows,
            title="Key Sensitivity – Different Keys",
        )
        assert all_unique

    def test_unicode_support(self, test_secret_key):
        """Test that unicode messages are handled correctly."""
        messages = [
            "Hello World",  # English
            "Hello 世界",  # Mixed
            "مرحبا",  # Arabic
            "αβγδ",  # Greek letters
        ]
        rows = []
        for msg in messages:
            signature = create_signature(msg, test_secret_key)
            is_valid = validate_signature(msg, test_secret_key, signature)
            rows.append([msg, len(signature), str(is_valid)])

        _print_table(
            ["message", "signature_length", "valid?"],
            rows,
            title="Unicode Support",
        )
        _print_bar_chart(
            [
                (msg[:8], float(len(create_signature(msg, test_secret_key))))
                for msg in messages
            ],
            title="Signature length per unicode message (all = 64 chars)",
        )
        for msg in messages:
            signature = create_signature(msg, test_secret_key)
            assert len(signature) == 64
            assert validate_signature(msg, test_secret_key, signature)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
