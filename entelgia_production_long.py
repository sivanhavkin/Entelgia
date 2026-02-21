#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entelgia Unified – PRODUCTION LONG Edition - By Sivan Havkin
=============================================================

Extended dialogue session: runs for exactly 200 turns without any time-based
stopping.  Based on Entelgia_production_meta.py but uses a turn-count loop so
the dialogue always completes all 200 turns regardless of how long it takes.

Advanced Multi-Agent Dialogue System with:
- Full unit tests with pytest
- Async/concurrent agent processing
- Proper logging with levels
- Config validation
- Session persistence
- REST API (FastAPI)
- Better monitoring
- NO TIME-BASED TIMEOUT – runs exactly max_turns turns
- MEMORY SECURITY with HMAC-SHA256 signatures
- Freudian slip memory surfacing
- Self-replication memory promotion
- Agent stop-signal detection
- Drive-aware cognition (dynamic LLM temperature from Freudian drives)
- Drive-triggered behavioral rules (Socrates conflict → binary choice; Athena dissent → exactly one dissent sentence)
- Energy-based dream cycles (automatic recovery when energy ≤ energy_safety_threshold)
- Meta-cognitive state display per turn (drives, energy, emotion, tone)
- Coherent Freudian drive correlations (conflict → ego erosion, temperature spike, energy drain)
- Superego persona fix: agent identity anchored in persona prompt via "Current mode (as {name})"; drive label uses s_ego= to avoid LLM persona confusion; Superego: prefix stripped from LLM output as safety net
- Output quality rules: forbidden meta-commentary phrases removed, hard word truncation removed

Version Note: Latest release: 2.5.0.

Requirements:
- Python 3.10+
- Ollama running locally (http://localhost:11434)

Run:
  python entelgia_production_long.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict

from colorama import Fore, Style

import Entelgia_production_meta as _meta
from Entelgia_production_meta import (
    Config,
    MainScript,
    TopicManager,
    TOPIC_CYCLE,
    logger,
)


class MainScriptLong(MainScript):
    """MainScript variant that runs exactly max_turns turns with no time-based stopping."""

    def run(self):
        """Main execution loop – iterates exactly max_turns turns, no timeout."""
        topicman = TopicManager(TOPIC_CYCLE, rotate_every_rounds=1, shuffle=False)

        self.dialog.append({"role": "seed", "text": self.cfg.seed_topic})

        print(
            Fore.GREEN
            + f"\n[Session {self.session_id}] Starting {self.cfg.max_turns}-turn long dialogue (no timeout)..."
            + Style.RESET_ALL
        )
        logger.info(
            f"Starting long session {self.session_id} for {self.cfg.max_turns} turns"
        )

        while self.turn_index < self.cfg.max_turns:
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
                    # Find last non-Fixy speaker so Fixy interventions don't break alternation
                    last_speaker = self.athena  # default
                    for turn in reversed(self.dialog):
                        role = turn.get("role", "")
                        if role == "Socrates":
                            last_speaker = self.socrates
                            break
                        elif role == "Athena":
                            last_speaker = self.athena
                            break
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

            # Collect meta-actions performed this turn
            _meta_actions: List[str] = []

            # Freudian slip attempt after each non-Fixy turn
            if speaker.name != "Fixy":
                slip = speaker.apply_freudian_slip(topic_label)
                if slip is not None:
                    _meta_actions.append("freudian_slip")

            # Display meta-cognitive state for this speaker
            self.print_meta_state(speaker, _meta_actions)

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
                    if self.cfg.show_meta:
                        print(
                            Fore.WHITE
                            + Style.DIM
                            + f"[META-ACTION] Fixy intervened: {reason}"
                            + Style.RESET_ALL
                            + "\n"
                        )

            if self.turn_index % self.cfg.dream_every_n_turns == 0:
                self.dream_cycle(self.socrates, topic_label)
                self.dream_cycle(self.athena, topic_label)
                if self.cfg.show_meta:
                    print(
                        Fore.WHITE
                        + Style.DIM
                        + "[META-ACTION] Dream cycle completed; energy restored to 100"
                        + Style.RESET_ALL
                        + "\n"
                    )

            # Energy-based dream cycle: Fixy forces agents to sleep when energy is critically low
            for _agent in (self.socrates, self.athena):
                if _agent.energy_level <= self.cfg.energy_safety_threshold:
                    self.dream_cycle(_agent, topic_label)
                    if self.cfg.show_meta:
                        print(
                            Fore.WHITE
                            + Style.DIM
                            + f"[META-ACTION] {_agent.name} energy critical ({_agent.energy_level:.1f}); dream cycle forced"
                            + Style.RESET_ALL
                            + "\n"
                        )

            # Self-replication cycle
            if self.turn_index % self.cfg.self_replicate_every_n_turns == 0:
                count_s = self.self_replicate_cycle(self.socrates, topic_label)
                count_a = self.self_replicate_cycle(self.athena, topic_label)
                if self.cfg.show_meta and (count_s + count_a) > 0:
                    print(
                        Fore.WHITE
                        + Style.DIM
                        + f"[META-ACTION] Self-replication: Socrates promoted={count_s}, Athena promoted={count_a}"
                        + Style.RESET_ALL
                        + "\n"
                    )

            if re.search(r"\b(stop|quit|bye)\b", out.lower()):
                logger.info("Stop signal received from agent")
                print(Fore.YELLOW + "[STOP] Agent requested stop." + Style.RESET_ALL)
                break

            if self.turn_index % 2 == 0:
                topicman.advance_round()

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
            f"Long session {self.session_id} completed: {self.turn_index} turns, {elapsed:.1f}s"
        )


_NO_TIMEOUT_MINUTES = 9999  # Effectively disables time-based stopping


def run_cli_long():
    """Run 200-turn long dialogue without time-based stopping."""
    cfg = Config(max_turns=200, timeout_minutes=_NO_TIMEOUT_MINUTES, show_meta=True)
    _meta.CFG = cfg

    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print(
        Fore.GREEN
        + "Entelgia Unified – PRODUCTION LONG Edition By Sivan Havkin"
        + Style.RESET_ALL
    )
    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print("\nConfiguration:")
    config_dict = asdict(cfg)
    config_display = {k: v for k, v in config_dict.items() if not k.startswith("_")}
    print(json.dumps(config_display, ensure_ascii=False, indent=2))
    print()

    try:
        app_script = MainScriptLong(cfg)
        app_script.run()
        print(Fore.GREEN + "\nLong session completed successfully!" + Style.RESET_ALL)
    except KeyboardInterrupt:
        print(
            Fore.YELLOW + "\n[INTERRUPTED] Session cancelled by user" + Style.RESET_ALL
        )
        logger.info("Long session interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(Fore.RED + f"[FATAL ERROR] {e}" + Style.RESET_ALL)
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_cli_long()
