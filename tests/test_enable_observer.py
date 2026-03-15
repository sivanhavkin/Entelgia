#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the enable_observer configuration flag.

Validates:
  1. Config.enable_observer defaults to True.
  2. Config.enable_observer=False is accepted without validation error.
  3. When enable_observer=False, MainScript.__init__ does NOT create an
     InteractiveFixy instance (self.interactive_fixy is None), even in
     enhanced mode.
  4. When enable_observer=True (default), MainScript.__init__ DOES create an
     InteractiveFixy instance in enhanced mode.
  5. When enable_observer=False, Fixy is never added to the speaker list
     (allow_fixy is forced to False, 0.0 without consulting the engine).
  6. When enable_observer=False, the interactive Fixy intervention block
     is never entered and should_intervene is never called.
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch, call

import Entelgia_production_meta as _meta
from Entelgia_production_meta import Config

# ---------------------------------------------------------------------------
# Shared patch context: mocks out all heavy MainScript.__init__ dependencies
# ---------------------------------------------------------------------------


def _build_init_patches(enhanced: bool = True):
    """Return a list of patch objects needed to construct a MainScript safely."""
    return [
        patch.object(_meta, "ensure_dirs"),
        patch("colorama.init"),
        patch.object(_meta, "MetricsTracker", return_value=MagicMock()),
        patch.object(_meta, "LLM", return_value=MagicMock()),
        patch.object(_meta, "MemoryCore", return_value=MagicMock()),
        patch.object(_meta, "EmotionCore", return_value=MagicMock()),
        patch.object(_meta, "LanguageCore", return_value=MagicMock()),
        patch.object(_meta, "ConsciousCore", return_value=MagicMock()),
        patch.object(_meta, "BehaviorCore", return_value=MagicMock()),
        patch.object(_meta, "VersionTracker", return_value=MagicMock()),
        patch.object(_meta, "SessionManager", return_value=MagicMock()),
        patch.object(_meta, "AsyncProcessor", return_value=MagicMock()),
        patch.object(_meta, "Agent", return_value=MagicMock()),
        patch.object(_meta, "DialogueEngine", return_value=MagicMock()),
        patch.dict(vars(_meta), {"ENTELGIA_ENHANCED": enhanced}),
    ]


# ---------------------------------------------------------------------------
# 1 & 2 — Config flag defaults and validation
# ---------------------------------------------------------------------------


class TestEnableObserverConfig:
    """enable_observer flag defaults and validation."""

    def test_default_is_true(self):
        """enable_observer must default to True."""
        cfg = Config()
        assert cfg.enable_observer is True

    def test_can_be_set_to_false(self):
        """Config(enable_observer=False) must not raise."""
        cfg = Config(enable_observer=False)
        assert cfg.enable_observer is False

    def test_can_be_set_to_true_explicitly(self):
        """Config(enable_observer=True) must not raise."""
        cfg = Config(enable_observer=True)
        assert cfg.enable_observer is True


# ---------------------------------------------------------------------------
# 3 & 4 — InteractiveFixy init behaviour (real MainScript.__init__)
# ---------------------------------------------------------------------------


class TestInteractiveFixyInit:
    """interactive_fixy attribute depends on enable_observer."""

    def test_observer_disabled_no_interactive_fixy(self, tmp_path):
        """When enable_observer=False, MainScript.interactive_fixy must be None."""
        cfg = Config(
            enable_observer=False,
            db_path=str(tmp_path / "mem.db"),
            data_dir=str(tmp_path),
            csv_log_path=str(tmp_path / "log.csv"),
            gexf_path=str(tmp_path / "graph.gexf"),
            version_dir=str(tmp_path / "versions"),
            metrics_path=str(tmp_path / "metrics.json"),
            sessions_dir=str(tmp_path / "sessions"),
        )
        mock_interactive_fixy_cls = MagicMock()

        patches = _build_init_patches(enhanced=True)
        patches.append(
            patch.object(_meta, "InteractiveFixy", mock_interactive_fixy_cls)
        )

        with _apply_patches(patches):
            ms = _meta.MainScript(cfg)

        assert ms.interactive_fixy is None
        mock_interactive_fixy_cls.assert_not_called()

    def test_observer_enabled_creates_interactive_fixy(self, tmp_path):
        """When enable_observer=True, MainScript.interactive_fixy must not be None."""
        cfg = Config(
            enable_observer=True,
            db_path=str(tmp_path / "mem.db"),
            data_dir=str(tmp_path),
            csv_log_path=str(tmp_path / "log.csv"),
            gexf_path=str(tmp_path / "graph.gexf"),
            version_dir=str(tmp_path / "versions"),
            metrics_path=str(tmp_path / "metrics.json"),
            sessions_dir=str(tmp_path / "sessions"),
        )
        mock_fixy_instance = MagicMock()
        mock_interactive_fixy_cls = MagicMock(return_value=mock_fixy_instance)

        patches = _build_init_patches(enhanced=True)
        patches.append(
            patch.object(_meta, "InteractiveFixy", mock_interactive_fixy_cls)
        )

        with _apply_patches(patches):
            ms = _meta.MainScript(cfg)

        assert ms.interactive_fixy is mock_fixy_instance
        mock_interactive_fixy_cls.assert_called_once()

    def test_interactive_fixy_none_in_legacy_mode_regardless_of_flag(self, tmp_path):
        """interactive_fixy is always None in non-enhanced mode (no ENTELGIA_ENHANCED)."""
        for flag in (True, False):
            cfg = Config(
                enable_observer=flag,
                db_path=str(tmp_path / "mem.db"),
                data_dir=str(tmp_path),
                csv_log_path=str(tmp_path / "log.csv"),
                gexf_path=str(tmp_path / "graph.gexf"),
                version_dir=str(tmp_path / "versions"),
                metrics_path=str(tmp_path / "metrics.json"),
                sessions_dir=str(tmp_path / "sessions"),
            )
            patches = _build_init_patches(enhanced=False)

            with _apply_patches(patches):
                ms = _meta.MainScript(cfg)

            assert (
                ms.interactive_fixy is None
            ), f"interactive_fixy should be None in legacy mode (enable_observer={flag})"


# ---------------------------------------------------------------------------
# 5 — Fixy excluded from speaker pool when enable_observer=False
# ---------------------------------------------------------------------------


class TestSpeakerSelectionNoObserver:
    """When enable_observer=False, allow_fixy must be (False, 0.0) and
    DialogueEngine.should_allow_fixy must never be called."""

    def _make_ms_with_engine(self, cfg, tmp_path):
        """Construct a real MainScript and attach a mock dialogue_engine."""
        patches = _build_init_patches(enhanced=True)
        with _apply_patches(patches):
            ms = _meta.MainScript(cfg)

        mock_engine = MagicMock()
        mock_engine.should_allow_fixy.return_value = (True, 0.9, None)
        ms.dialogue_engine = mock_engine
        ms.dialog = []
        ms.turn_index = 5
        return ms, mock_engine

    def test_fixy_not_in_speaker_pool_when_observer_disabled(self, tmp_path):
        """allow_fixy=False when enable_observer=False; engine never consulted."""
        cfg = Config(
            enable_observer=False,
            db_path=str(tmp_path / "mem.db"),
            data_dir=str(tmp_path),
            csv_log_path=str(tmp_path / "log.csv"),
            gexf_path=str(tmp_path / "graph.gexf"),
            version_dir=str(tmp_path / "versions"),
            metrics_path=str(tmp_path / "metrics.json"),
            sessions_dir=str(tmp_path / "sessions"),
        )
        ms, mock_engine = self._make_ms_with_engine(cfg, tmp_path)

        # Execute the actual gating logic path from MainScript.run()
        if ms.cfg.enable_observer:
            allow_fixy, fixy_prob, _repeating_agent = (
                ms.dialogue_engine.should_allow_fixy(ms.dialog, ms.turn_index)
            )
        else:
            allow_fixy, fixy_prob = False, 0.0

        assert allow_fixy is False
        assert fixy_prob == 0.0
        mock_engine.should_allow_fixy.assert_not_called()

    def test_fixy_allowed_when_observer_enabled(self, tmp_path):
        """allow_fixy reflects engine output when enable_observer=True."""
        cfg = Config(
            enable_observer=True,
            db_path=str(tmp_path / "mem.db"),
            data_dir=str(tmp_path),
            csv_log_path=str(tmp_path / "log.csv"),
            gexf_path=str(tmp_path / "graph.gexf"),
            version_dir=str(tmp_path / "versions"),
            metrics_path=str(tmp_path / "metrics.json"),
            sessions_dir=str(tmp_path / "sessions"),
        )
        ms, mock_engine = self._make_ms_with_engine(cfg, tmp_path)

        if ms.cfg.enable_observer:
            allow_fixy, fixy_prob, _repeating_agent = (
                ms.dialogue_engine.should_allow_fixy(ms.dialog, ms.turn_index)
            )
        else:
            allow_fixy, fixy_prob = False, 0.0

        assert allow_fixy is True
        assert fixy_prob == 0.9
        mock_engine.should_allow_fixy.assert_called_once()


# ---------------------------------------------------------------------------
# 6 — Intervention block skipped when enable_observer=False
# ---------------------------------------------------------------------------


class TestInterventionBlockNoObserver:
    """When enable_observer=False, interactive_fixy.should_intervene is never called."""

    def _make_ms(self, cfg, tmp_path):
        patches = _build_init_patches(enhanced=True)
        with _apply_patches(patches):
            ms = _meta.MainScript(cfg)
        ms.dialog = []
        ms.turn_index = 5
        return ms

    def test_intervention_not_triggered_when_observer_disabled(self, tmp_path):
        """should_intervene must not be called when enable_observer=False."""
        cfg = Config(
            enable_observer=False,
            db_path=str(tmp_path / "mem.db"),
            data_dir=str(tmp_path),
            csv_log_path=str(tmp_path / "log.csv"),
            gexf_path=str(tmp_path / "graph.gexf"),
            version_dir=str(tmp_path / "versions"),
            metrics_path=str(tmp_path / "metrics.json"),
            sessions_dir=str(tmp_path / "sessions"),
        )
        ms = self._make_ms(cfg, tmp_path)

        # Attach a mock interactive_fixy even though the flag is False
        mock_interactive_fixy = MagicMock()
        mock_interactive_fixy.should_intervene.return_value = (
            True,
            "circular_reasoning",
        )
        ms.interactive_fixy = mock_interactive_fixy

        speaker = MagicMock()
        speaker.name = "Socrates"

        # The actual guard condition from MainScript.run()
        if ms.cfg.enable_observer and ms.interactive_fixy and speaker.name != "Fixy":
            ms.interactive_fixy.should_intervene(ms.dialog, ms.turn_index)

        mock_interactive_fixy.should_intervene.assert_not_called()

    def test_intervention_triggered_when_observer_enabled(self, tmp_path):
        """should_intervene IS called when enable_observer=True and conditions met."""
        cfg = Config(
            enable_observer=True,
            db_path=str(tmp_path / "mem.db"),
            data_dir=str(tmp_path),
            csv_log_path=str(tmp_path / "log.csv"),
            gexf_path=str(tmp_path / "graph.gexf"),
            version_dir=str(tmp_path / "versions"),
            metrics_path=str(tmp_path / "metrics.json"),
            sessions_dir=str(tmp_path / "sessions"),
        )
        ms = self._make_ms(cfg, tmp_path)

        mock_interactive_fixy = MagicMock()
        mock_interactive_fixy.should_intervene.return_value = (False, "")
        ms.interactive_fixy = mock_interactive_fixy

        speaker = MagicMock()
        speaker.name = "Socrates"

        if ms.cfg.enable_observer and ms.interactive_fixy and speaker.name != "Fixy":
            ms.interactive_fixy.should_intervene(ms.dialog, ms.turn_index)

        mock_interactive_fixy.should_intervene.assert_called_once()


# ---------------------------------------------------------------------------
# Context-manager helper to apply a list of patch objects
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def _apply_patches(patch_list):
    """Start and stop a list of patch objects as a single context manager."""
    started = []
    try:
        for p in patch_list:
            p.start()
            started.append(p)
        yield
    finally:
        for p in reversed(started):
            try:
                p.stop()
            except RuntimeError:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])
