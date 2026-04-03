# tests/test_session_turn_selector.py
"""
Tests for the interactive session-turn selector introduced in
Entelgia_production_meta.py.

Covers:
  1. Pressing Enter with no input returns the default (15 turns).
  2. An invalid entry (non-numeric / out-of-range) causes a re-prompt and the
     next valid entry is returned.
  3. A valid numeric entry returns the corresponding turn count.
  4. _pick_numbered_option is shared logic reused by select_session_turns.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch

from Entelgia_production_meta import (
    _pick_numbered_option,
    select_session_turns,
    _SESSION_TURN_OPTIONS,
    _SESSION_TURN_DEFAULT,
)


class TestPickNumberedOption:
    """Unit tests for the shared _pick_numbered_option() helper."""

    def test_enter_returns_default(self, capsys):
        """Empty input (Enter) must return the supplied default."""
        with patch("builtins.input", return_value=""):
            result = _pick_numbered_option("Title:", [5, 15, 25], 15, "turns")
        assert result == 15

    def test_valid_choice_returns_correct_value(self, capsys):
        """Entering '1' must return the first option."""
        with patch("builtins.input", return_value="1"):
            result = _pick_numbered_option("Title:", [5, 15, 25], 15, "turns")
        assert result == 5

    def test_valid_choice_last_item(self, capsys):
        """Entering the last index must return the last option."""
        options = [5, 15, 25]
        with patch("builtins.input", return_value=str(len(options))):
            result = _pick_numbered_option("Title:", options, 15, "turns")
        assert result == 25

    def test_invalid_then_valid_entry(self, capsys):
        """Non-numeric input must be rejected; the next valid entry is returned."""
        inputs = iter(["bad", "2"])
        with patch("builtins.input", side_effect=inputs):
            result = _pick_numbered_option("Title:", [5, 15, 25], 15, "turns")
        assert result == 15
        captured = capsys.readouterr()
        assert "[WARN]" in captured.out

    def test_out_of_range_then_valid_entry(self, capsys):
        """Out-of-range numeric input must be rejected; valid entry succeeds."""
        inputs = iter(["99", "3"])
        with patch("builtins.input", side_effect=inputs):
            result = _pick_numbered_option("Title:", [5, 15, 25], 15, "turns")
        assert result == 25
        captured = capsys.readouterr()
        assert "[WARN]" in captured.out

    def test_zero_rejected(self, capsys):
        """'0' is out of range and must be rejected (unlike _pick_from_list)."""
        inputs = iter(["0", "1"])
        with patch("builtins.input", side_effect=inputs):
            result = _pick_numbered_option("Title:", [5, 15, 25], 15, "turns")
        assert result == 5


class TestSelectSessionTurns:
    """Integration tests for select_session_turns() against the real constants."""

    def test_enter_returns_default(self):
        """Empty input returns _SESSION_TURN_DEFAULT."""
        with patch("builtins.input", return_value=""):
            result = select_session_turns()
        assert result == _SESSION_TURN_DEFAULT

    def test_valid_selection_maps_to_correct_turn_count(self):
        """Each valid index maps back to the expected turn-count option."""
        for idx, expected in enumerate(_SESSION_TURN_OPTIONS, 1):
            with patch("builtins.input", return_value=str(idx)):
                result = select_session_turns()
            assert result == expected, (
                f"index {idx} should map to {expected} turns, got {result}"
            )

    def test_invalid_then_default(self, capsys):
        """Invalid input followed by Enter returns the default turn count."""
        inputs = iter(["xyz", ""])
        with patch("builtins.input", side_effect=inputs):
            result = select_session_turns()
        assert result == _SESSION_TURN_DEFAULT
        captured = capsys.readouterr()
        assert "[WARN]" in captured.out
