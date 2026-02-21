#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entelgia Unified – PRODUCTION LONG Edition - By Sivan Havkin
=============================================================

Extended dialogue session: runs for exactly 200 turns without any time-based
stopping.  Based on Entelgia_production_meta.py but uses a turn-count loop so
the dialogue always completes all 200 turns regardless of how long it takes.

Run:
  python entelgia_production_long.py
"""

from __future__ import annotations

import json
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
                allow_fixy, fixy_prob = self.dialogue_engine.should_allow_fixy(
                    self.dialog, self.turn_index
                )

                if self.turn_index == 1:
                    speaker = self.socrates
                else:
                    last_speaker = self.athena
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
            elif (
                not self.interactive_fixy
                and self.turn_index % self.cfg.fixy_every_n_turns == 0
            ):
                tail = self.dialog[-10:]
                ctx = "\n".join([f"{t['role']}: {t['text'][:50]}" for t in tail])
                self.fixy_check(ctx)

            if self.turn_index % self.cfg.dream_every_n_turns == 0:
                self.dream_cycle(self.socrates, topic_label)
                self.dream_cycle(self.athena, topic_label)

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
    cfg = Config(max_turns=200, timeout_minutes=_NO_TIMEOUT_MINUTES)
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
