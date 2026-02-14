#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for Athena response truncation feature."""

import pytest
import re
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Entelgia_production_meta import (
    smart_truncate_response,
    _smart_truncate_athena_response,
    _truncate_at_boundary,
)


class TestTruncateAtBoundary:
    """Tests for the _truncate_at_boundary helper function."""

    def test_short_text_unchanged(self):
        """Short text under limit should remain unchanged."""
        text = "This is a short text."
        result = _truncate_at_boundary(text, max_words=20)
        assert result == text

    def test_long_text_truncated(self):
        """Long text should be truncated at sentence boundary."""
        text = " ".join(["word"] * 50) + ". More text here."
        result = _truncate_at_boundary(text, max_words=20)
        words = result.split()
        # Allow some variance for sentence boundary finding (might be slightly over)
        assert len(words) <= 22

    def test_empty_text(self):
        """Empty text should return empty string."""
        result = _truncate_at_boundary("", max_words=20)
        assert result == ""

    def test_sentence_boundary_respected(self):
        """Truncation should respect sentence boundaries."""
        text = "First sentence. Second sentence. Third sentence."
        result = _truncate_at_boundary(text, max_words=3)
        # Should end at a period
        assert result.endswith(".") or result.endswith("...")


class TestSmartTruncateAthenaResponse:
    """Tests for Athena-specific response truncation."""

    def test_explicit_thoughts_format(self):
        """Response with explicit thoughts should be parsed correctly."""
        text = "[Athena's thoughts: This is a test thought.]\n\nThis is the main response."
        result = _smart_truncate_athena_response(text)
        assert "[Athena's thoughts:" in result
        assert "main response" in result

    def test_thoughts_truncation(self):
        """Thoughts should be truncated to 20 words max."""
        # Create thoughts longer than 20 words
        thoughts = " ".join(["thought"] * 30)
        main = "This is the main response."
        text = f"[Athena's thoughts: {thoughts}]\n\n{main}"
        
        result = _smart_truncate_athena_response(text)
        
        # Extract thoughts section
        match = re.match(r"^\[Athena's thoughts:\s*([^\]]+)\]", result)
        assert match
        thoughts_part = match.group(1).strip()
        thoughts_words = len(thoughts_part.split())
        
        # Should be around 20 words (allow slight variance for sentence boundaries)
        assert thoughts_words <= 22

    def test_main_response_truncation(self):
        """Main response should be truncated to 130 words max."""
        thoughts = "Short thought."
        # Create main response longer than 130 words
        main = " ".join(["word"] * 150) + "."
        text = f"[Athena's thoughts: {thoughts}]\n\n{main}"
        
        result = _smart_truncate_athena_response(text)
        
        # Extract main response section
        match = re.match(r"^\[Athena's thoughts:[^\]]+\]\s*\n?\s*(.*)", result, re.DOTALL)
        assert match
        main_part = match.group(1).strip()
        main_words = len(main_part.split())
        
        # Should be around 130 words (allow slight variance)
        assert main_words <= 135

    def test_no_explicit_thoughts(self):
        """Response without explicit thoughts should still be handled."""
        text = "First sentence. " + " ".join(["word"] * 140) + "."
        result = _smart_truncate_athena_response(text)
        
        # Should have thoughts added from first sentence
        assert "[Athena's thoughts:" in result

    def test_very_short_response(self):
        """Very short response should not be modified excessively."""
        text = "Short response."
        result = _smart_truncate_athena_response(text)
        assert "Short response" in result

    def test_hebrew_thoughts_format(self):
        """Hebrew format for thoughts should also be recognized."""
        text = "[מחשבות של אתנה: זוהי מחשבה בעברית.]\n\nזוהי התשובה הראשית."
        result = _smart_truncate_athena_response(text)
        # Should recognize and preserve the format
        assert "מחשבות של אתנה" in result or "Athena's thoughts" in result


class TestSmartTruncateResponse:
    """Tests for the main smart_truncate_response function."""

    def test_regular_agent_truncation(self):
        """Regular agents (not Athena) should use standard truncation."""
        text = " ".join(["word"] * 200) + "."
        result = smart_truncate_response(text, max_words=150, agent_name="Socrates")
        words = result.split()
        # Should be around 150 words (allow slight variance)
        assert len(words) <= 155

    def test_athena_special_handling(self):
        """Athena should use special truncation with thoughts."""
        text = "[Athena's thoughts: Testing.]\n\n" + " ".join(["word"] * 140) + "."
        result = smart_truncate_response(text, max_words=150, agent_name="Athena")
        assert "[Athena's thoughts:" in result

    def test_athena_without_explicit_thoughts(self):
        """Athena without explicit thoughts should still get special handling."""
        text = "First sentence. " + " ".join(["word"] * 140) + "."
        result = smart_truncate_response(text, max_words=150, agent_name="Athena")
        # Should have thoughts section added
        assert "[Athena's thoughts:" in result

    def test_fixy_normal_truncation(self):
        """Fixy should use normal truncation like other agents."""
        text = " ".join(["word"] * 200) + "."
        result = smart_truncate_response(text, max_words=150, agent_name="Fixy")
        words = result.split()
        assert len(words) <= 155
        assert "[Athena's thoughts:" not in result

    def test_empty_agent_name(self):
        """Empty agent name should use normal truncation."""
        text = " ".join(["word"] * 200) + "."
        result = smart_truncate_response(text, max_words=150, agent_name="")
        words = result.split()
        assert len(words) <= 155


class TestWordCountLimits:
    """Tests to verify word count limits are respected."""

    def test_combined_word_limit(self):
        """Total words (thoughts + main) should not exceed 150."""
        # Create long thoughts and long main response
        thoughts = " ".join(["thought"] * 30)
        main = " ".join(["response"] * 140)
        text = f"[Athena's thoughts: {thoughts}]\n\n{main}."
        
        result = _smart_truncate_athena_response(text)
        
        # Count total words
        total_words = len(result.split())
        # Should be around 150 words total (allow slight variance)
        assert total_words <= 160

    def test_thoughts_limit_20_words(self):
        """Thoughts should be limited to approximately 20 words."""
        thoughts = " ".join(["thought"] * 50)  # Way over limit
        main = "Short main response."
        text = f"[Athena's thoughts: {thoughts}]\n\n{main}"
        
        result = _smart_truncate_athena_response(text)
        
        # Extract thoughts
        match = re.match(r"^\[Athena's thoughts:\s*([^\]]+)\]", result)
        assert match
        thoughts_part = match.group(1).strip()
        thoughts_words = len(thoughts_part.split())
        
        # Should be around 20 (allow slight variance)
        assert thoughts_words <= 22
        assert thoughts_words >= 15  # Should have some content

    def test_main_response_limit_130_words(self):
        """Main response should be limited to approximately 130 words."""
        thoughts = "Short thought."
        main = " ".join(["word"] * 200)  # Way over limit
        text = f"[Athena's thoughts: {thoughts}]\n\n{main}."
        
        result = _smart_truncate_athena_response(text)
        
        # Extract main response
        match = re.match(r"^\[Athena's thoughts:[^\]]+\]\s*\n?\s*(.*)", result, re.DOTALL)
        assert match
        main_part = match.group(1).strip()
        main_words = len(main_part.split())
        
        # Should be around 130 (allow slight variance)
        assert main_words <= 135
        assert main_words >= 100  # Should have substantial content
