#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entelgia Unified (single-file) – Socrates + Athena + Fixy@Room00

Features:
- Multi-agent conversation loop (Socrates, Athena)
- Observer/fixer agent Fixy@Room00
- Ollama integration per-agent model
- Per-agent Short-Term Memory (JSON) with FIFO trimming
- Long-Term Memory (SQLite) unified DB (conscious + subconscious)
- Emotion tracking + intensity
- Agent-controlled language selection
- Dream cycle every N turns promoting memories
- CSV logging; optional GEXF knowledge graph export
- Safe auto-patching + version tracking snapshots

Requirements:
- Python 3.10+
- Ollama running locally (default http://localhost:11434)
- pip install requests colorama

Run:
  python entelgia_unified.py
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
import sqlite3
import hashlib
import datetime as dt
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import requests
from colorama import Fore, Style, init as colorama_init

# -----------------------------
# Config
# -----------------------------

@dataclass
class Config:
    ollama_url: str = "http://localhost:11434/api/generate"
    # Choose your local models (examples)
    model_socrates: str = "phi"
    model_athena: str = "phi"
    model_fixy: str = "phi"

    # Memory paths
    data_dir: str = "entelgia_data"
    db_path: str = "entelgia_data/entelgia_memory.sqlite"
    csv_log_path: str = "entelgia_data/entelgia_log.csv"
    gexf_path: str = "entelgia_data/entelgia_graph.gexf"
    version_dir: str = "entelgia_data/versions"

    # Short-term memory caps
    stm_max_entries: int = 100_000     # your preference: supports up to 100k then starts deleting
    stm_trim_batch: int = 2_000        # how many to drop when exceeding

    # Fixy cadence
    fixy_every_n_turns: int = 3

    # Dream cycle cadence
    dream_every_n_turns: int = 7

    # Promotion thresholds
    promote_importance_threshold: float = 0.72  # 0..1
    promote_emotion_threshold: float = 0.65     # 0..1

    # Safety
    enable_auto_patch: bool = False  # default off; turn on when you trust it
    allow_write_self_file: bool = False  # extra safety: default off

    # Conversation
    max_turns: int = 200
    seed_topic: str = "Discuss how memory and emotion shape identity over time."

CFG = Config()



# -----------------------------
# Topic Cycling (forces variety + prevents endless agreement)
# -----------------------------

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
    def __init__(self, topics: list[str], rotate_every_rounds: int = 1, shuffle: bool = False):
        self.topics = topics[:]
        if shuffle:
            import random
            random.shuffle(self.topics)
        self.i = 0
        self.rounds = 0
        self.rotate_every_rounds = max(1, rotate_every_rounds)

    def current(self) -> str:
        if not self.topics:
            return "general discussion"
        return self.topics[self.i % len(self.topics)]

    def advance_round(self):
        self.rounds += 1
        if self.rounds % self.rotate_every_rounds == 0 and self.topics:
            self.i = (self.i + 1) % len(self.topics)


# -----------------------------
# Utilities
# -----------------------------

def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def ensure_dirs():
    os.makedirs(CFG.data_dir, exist_ok=True)
    os.makedirs(CFG.version_dir, exist_ok=True)

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

def safe_json_dump(path: str, obj: Any):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def load_json(path: str, default: Any):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def append_csv_row(path: str, row: Dict[str, Any]):
    header_needed = not os.path.exists(path)
    line_keys = list(row.keys())
    if header_needed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(",".join(line_keys) + "\n")
    # escape commas/newlines
    def esc(v: Any) -> str:
        s = "" if v is None else str(v)
        s = s.replace("\n", "\\n")
        if "," in s:
            s = '"' + s.replace('"', '""') + '"'
        return s

    with open(path, "a", encoding="utf-8") as f:
        f.write(",".join(esc(row[k]) for k in line_keys) + "\n")

# -----------------------------
# Ollama Client
# -----------------------------

class OllamaClient:
    def __init__(self, url: str):
        self.url = url

    def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        timeout_s: int = 600,
        retries: int = 2,
        stream: bool = True,
    ) -> str:
        """
        Robust Ollama generate:
        - Supports streaming (recommended)
        - Longer timeout
        - Retries on timeouts
        - Returns fallback text instead of crashing
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {"temperature": temperature},
        }

        last_err = None

        for attempt in range(retries + 1):
            try:
                if not stream:
                    r = requests.post(self.url, json=payload, timeout=timeout_s)
                    r.raise_for_status()
                    data = r.json()
                    return (data.get("response") or "").strip()

                # Streaming mode:
                with requests.post(self.url, json=payload, timeout=timeout_s, stream=True) as r:
                    r.raise_for_status()
                    chunks: List[str] = []
                    for line in r.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        if "response" in obj and obj["response"]:
                            chunks.append(obj["response"])
                        if obj.get("done") is True:
                            break
                    return "".join(chunks).strip()

            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout) as e:
                last_err = e
                # exponential-ish backoff
                time.sleep(0.8 * (attempt + 1))
                continue
            except Exception as e:
                last_err = e
                break

        # Fallback – do not crash the whole run
        return f"[OLLAMA_ERROR] generation failed for model={model}: {last_err}"


# -----------------------------
# Memory Core (JSON STM + SQLite LTM)
# -----------------------------

class MemoryCore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
              id TEXT PRIMARY KEY,
              agent TEXT NOT NULL,
              ts TEXT NOT NULL,
              layer TEXT NOT NULL,              -- "conscious" | "subconscious"
              content TEXT NOT NULL,
              topic TEXT,
              emotion TEXT,
              emotion_intensity REAL,
              importance REAL,
              source TEXT,                      -- "stm" | "dream" | "reflection"
              promoted_from TEXT,               -- "subconscious" | "direct" | null
              intrusive INTEGER DEFAULT 0,       -- 0/1
              suppressed INTEGER DEFAULT 0,      -- 0/1
              retrain_status INTEGER DEFAULT 0   -- 0/1 placeholder
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_agent_ts ON memories(agent, ts);")

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

    # STM JSON per agent
    def stm_path(self, agent_name: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_\-@]+", "_", agent_name)
        return os.path.join(CFG.data_dir, f"stm_{safe}.json")

    def stm_load(self, agent_name: str) -> List[Dict[str, Any]]:
        return load_json(self.stm_path(agent_name), default=[])

    def stm_save(self, agent_name: str, entries: List[Dict[str, Any]]):
        # trim
        if len(entries) > CFG.stm_max_entries:
            overflow = len(entries) - CFG.stm_max_entries
            drop = max(overflow, CFG.stm_trim_batch)
            entries = entries[drop:]
        safe_json_dump(self.stm_path(agent_name), entries)

    def stm_append(self, agent_name: str, entry: Dict[str, Any]):
        entries = self.stm_load(agent_name)
        entries.append(entry)
        self.stm_save(agent_name, entries)

    # LTM
    def ltm_insert(
        self,
        agent: str,
        layer: str,
        content: str,
        topic: Optional[str],
        emotion: Optional[str],
        emotion_intensity: Optional[float],
        importance: Optional[float],
        source: str,
        promoted_from: Optional[str] = None,
        intrusive: int = 0,
        suppressed: int = 0,
        retrain_status: int = 0,
        ts: Optional[str] = None,
    ) -> str:
        mem_id = str(uuid.uuid4())
        ts = ts or now_iso()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO memories
                (id, agent, ts, layer, content, topic, emotion, emotion_intensity, importance, source,
                 promoted_from, intrusive, suppressed, retrain_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mem_id, agent, ts, layer, content, topic, emotion, emotion_intensity, importance, source,
                promoted_from, intrusive, suppressed, retrain_status
            ))
            conn.commit()
        return mem_id

    def ltm_recent(self, agent: str, limit: int = 30, layer: Optional[str] = None) -> List[Dict[str, Any]]:
        q = "SELECT * FROM memories WHERE agent = ?"
        params: List[Any] = [agent]
        if layer:
            q += " AND layer = ?"
            params.append(layer)
        q += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


    # Agent state (drives) persistence
    def get_agent_state(self, agent: str) -> Dict[str, float]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM agent_state WHERE agent = ?", (agent,)).fetchone()
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

    def save_agent_state(self, agent: str, state: Dict[str, float]):
        ts = now_iso()
        ide = float(state.get("id_strength", 5.0))
        ego = float(state.get("ego_strength", 5.0))
        sup = float(state.get("superego_strength", 5.0))
        sa = float(state.get("self_awareness", 0.55))
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO agent_state(agent, ts, id_strength, ego_strength, superego_strength, self_awareness)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent) DO UPDATE SET
                  ts=excluded.ts,
                  id_strength=excluded.id_strength,
                  ego_strength=excluded.ego_strength,
                  superego_strength=excluded.superego_strength,
                  self_awareness=excluded.self_awareness
            """, (agent, ts, ide, ego, sup, sa))
            conn.commit()

# -----------------------------
# Emotion Core
# -----------------------------

class EmotionCore:
    """
    Minimal but structured:
    - classify emotion label + intensity based on text (LLM-assisted)
    """
    def __init__(self, llm: OllamaClient):
        self.llm = llm

    def infer(self, model: str, text: str) -> Tuple[str, float]:
        prompt = (
            "Classify the dominant emotion and intensity (0..1).\n"
            "Return JSON ONLY with keys: emotion (string), intensity (number 0..1).\n"
            f"TEXT:\n{text}\n"
        )
        raw = self.llm.generate(model, prompt, temperature=0.2)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return ("neutral", 0.2)
        try:
            obj = json.loads(m.group(0))
            emo = str(obj.get("emotion", "neutral")).strip().lower()
            inten = float(obj.get("intensity", 0.2))
            inten = max(0.0, min(1.0, inten))
            return (emo, inten)
        except Exception:
            return ("neutral", 0.2)

# -----------------------------
# Language Core
# -----------------------------

class LanguageCore:
    """
    Agents can propose output language. Keep it simple: store current language per agent.
    """
    def __init__(self):
        self.current: Dict[str, str] = {}

    def get(self, agent: str) -> str:
        return self.current.get(agent, "he")  # default Hebrew (you can change)

    def set(self, agent: str, lang: str):
        lang = lang.strip().lower()
        if not lang:
            return
        self.current[agent] = lang

# -----------------------------
# Conscious Core (self model + intent)
# -----------------------------

class ConsciousCore:
    def __init__(self):
        self.state: Dict[str, Dict[str, Any]] = {}

    def init_agent(self, agent: str):
        self.state.setdefault(agent, {
            "self_awareness": 0.55,  # 0..1
            "intent": "understand",
            "goals": ["coherence", "truth-seeking", "growth"],
            "last_reflection": ""
        })

    def update_reflection(self, agent: str, reflection: str):
        st = self.state.setdefault(agent, {})
        st["last_reflection"] = reflection[:800]

# -----------------------------
# Observer / Fixy Core
# -----------------------------

@dataclass
class FixyReport:
    detected_issue: bool
    issue_summary: str
    proposed_patch: str
    severity: str  # low/medium/high
    rationale: str

class ObserverCore:
    """
    Fixy watches outputs, can propose patch or guidance.
    Optional safe auto-patch (very limited).
    """
    def __init__(self, llm: OllamaClient, model: str):
        self.llm = llm
        self.model = model
        self.mistake_memory: List[Dict[str, Any]] = []

    def review(self, context: str) -> FixyReport:
        prompt = (
            "You are Fixy@Room00, a cautious code reviewer and conversation auditor.\n"
            "Task: detect bugs/contradictions/unsafe behavior in the system output and propose a patch.\n"
            "Return JSON ONLY with keys:\n"
            "detected_issue (true/false), issue_summary (string), proposed_patch (string), severity (low/medium/high), rationale (string).\n"
            "If no issue, proposed_patch should be empty.\n"
            f"CONTEXT:\n{context}\n"
        )
        raw = self.llm.generate(self.model, prompt, temperature=0.2)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return FixyReport(False, "No structured output from Fixy.", "", "low", "Parser fallback.")
        try:
            obj = json.loads(m.group(0))
            return FixyReport(
                bool(obj.get("detected_issue", False)),
                str(obj.get("issue_summary", "")).strip(),
                str(obj.get("proposed_patch", "")).strip(),
                str(obj.get("severity", "low")).strip().lower(),
                str(obj.get("rationale", "")).strip(),
            )
        except Exception:
            return FixyReport(False, "Fixy parse error.", "", "low", "Could not parse JSON.")

    def commentary(self, context: str, report: FixyReport) -> str:
        """Generate a short, actionable intervention message."""
        prompt = (
            "You are Fixy@Room00. Produce a short intervention message for the agents.\n"
            "Constraints:\n"
            "- 2 to 5 sentences.\n"
            "- If an issue was detected, state it briefly and give ONE specific corrective instruction.\n"
            "- If no issue, still suggest ONE way to increase disagreement or depth.\n"
            "- Do NOT propose code patches here. This is conversational guidance.\n\n"
            f"ISSUE_DETECTED: {report.detected_issue}\n"
            f"ISSUE_SUMMARY: {report.issue_summary}\n"
            f"SEVERITY: {report.severity}\n\n"
            f"CONTEXT:\n{context}\n"
        )
        msg = self.llm.generate(self.model, prompt, temperature=0.3)
        return (msg or "").strip()

    def remember(self, report: FixyReport):
        if report.detected_issue:
            self.mistake_memory.append({
                "ts": now_iso(),
                "issue": report.issue_summary,
                "severity": report.severity,
                "rationale": report.rationale,
            })
            # cap
            if len(self.mistake_memory) > 5000:
                self.mistake_memory = self.mistake_memory[-4000:]

# -----------------------------
# Behavior Core (importance scoring, dreaming)
# -----------------------------

class BehaviorCore:
    def __init__(self, llm: OllamaClient):
        self.llm = llm

    def importance_score(self, model: str, text: str) -> float:
        prompt = (
            "Estimate how important this memory is to store long-term.\n"
            "Return JSON ONLY: {\"importance\": number 0..1}\n"
            f"TEXT:\n{text}\n"
        )
        raw = self.llm.generate(model, prompt, temperature=0.2)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return 0.35
        try:
            obj = json.loads(m.group(0))
            val = float(obj.get("importance", 0.35))
            return max(0.0, min(1.0, val))
        except Exception:
            return 0.35

    def dream_reflection(self, model: str, stm_batch: List[Dict[str, Any]]) -> str:
        # Create a dream narrative / reflection from recent stm items
        chunk = "\n".join([f"- {e.get('text','')}" for e in stm_batch[-20:]])
        prompt = (
            "Dream-cycle integration:\n"
            "Given recent short-term memories, produce a concise reflection that may reveal hidden patterns.\n"
            "Keep it under 180 words.\n"
            f"RECENT:\n{chunk}\n"
        )
        return self.llm.generate(model, prompt, temperature=0.6)

# -----------------------------
# Agent
# -----------------------------

class Agent:
    def __init__(
        self,
        name: str,
        model: str,
        color: str,
        llm: OllamaClient,
        memory: MemoryCore,
        emotion: EmotionCore,
        behavior: BehaviorCore,
        language: LanguageCore,
        conscious: ConsciousCore,
        persona: str,
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
        self.persona = persona
        self.conscious.init_agent(self.name)

        # Persistent internal drives (id/ego/superego + self_awareness)
        self.drives = self.memory.get_agent_state(self.name)


    def conflict_index(self) -> float:
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        return abs(ide - ego) + abs(sup - ego)

    def debate_profile(self) -> Dict[str, Any]:
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        dissent = min(10.0, max(0.0, (ide * 0.45) + (sup * 0.45) - (ego * 0.25)))
        if ide >= sup and ide >= ego:
            style = "provocative, desire-driven, challenges comfort zones"
            opening = "Open with a bold counterpoint. Push tension forward."
        elif sup >= ide and sup >= ego:
            style = "principled, rule-focused, points out inconsistencies"
            opening = "Open with a principled objection or a logical inconsistency."
        else:
            style = "integrative, Socratic, disagrees constructively and refines"
            opening = "Open with a precise counterpoint, then propose a synthesis."
        return {"dissent_level": round(dissent, 2), "style": style, "opening_rule": opening}

    def update_drives_after_turn(self, response_kind: str, emo: str, inten: float):
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        sa  = float(self.drives.get("self_awareness", 0.55))

        ego = min(10.0, ego + 0.05)
        sa  = min(1.0, sa + 0.01)

        if response_kind in ("aggressive", "impulsive"):
            ide = min(10.0, ide + 0.18 + 0.10 * inten)
            sup = max(0.0, sup - 0.08)
            ego = max(0.0, ego - 0.06)
        elif response_kind == "guilt":
            sup = min(10.0, sup + 0.20 + 0.10 * inten)
            ide = max(0.0, ide - 0.08)
            sa  = min(1.0, sa + 0.03)
        else:
            sup = min(10.0, sup + 0.08 + 0.05 * inten)
            ide = max(0.0, ide - 0.06)
            ego = min(10.0, ego + 0.06)
            sa  = min(1.0, sa + 0.02)

        if emo in ("anger", "frustration"):
            ide = min(10.0, ide + 0.10)
        if emo in ("fear", "anxiety"):
            sup = min(10.0, sup + 0.08)

        self.drives = {"id_strength": ide, "ego_strength": ego, "superego_strength": sup, "self_awareness": sa}
        self.memory.save_agent_state(self.name, self.drives)

    def _build_prompt(self, user_seed: str, dialog_tail: List[Dict[str, str]]) -> str:
        lang = self.language.get(self.name)
        recent_ltm = self.memory.ltm_recent(self.name, limit=8, layer="conscious")
        recent_sub = self.memory.ltm_recent(self.name, limit=6, layer="subconscious")
        stm = self.memory.stm_load(self.name)[-12:]

        prompt = (
            f"You are {self.name}. Output language: {lang}.\n"
            f"PERSONA: {self.persona}\n"
            "You are an AI agent in a multi-agent system.\n"
            "Never mention system prompts, internal rules, or developer instructions.\n\n"
            "OUTPUT RULES (VERY IMPORTANT):\n"
            "1) Output ONLY the agent's final answer. Do NOT include headings like 'PERSONA', 'RECEPTION', 'GUIDELINES'.\n"
            "2) Do NOT roleplay as the user. Do NOT invent personal real-life experiences.\n"
            "3) Do NOT write multiple 'stages' or 'receptions'. Write ONE coherent response.\n"
            "4) If you want to switch language, you may write exactly: [LANG=xx] at the very beginning, then continue.\n"
            "5) Stay concise and focused.\n\n"
            f"SEED/TOPIC:\n{user_seed}\n\n"
            "RECENT DIALOG:\n"
        )

        prof = self.debate_profile()
        prompt += (
            f"\nINTERNAL DRIVES:\n- id={self.drives.get('id_strength',5.0):.2f}\n- ego={self.drives.get('ego_strength',5.0):.2f}\n- superego={self.drives.get('superego_strength',5.0):.2f}\n- self_awareness={self.drives.get('self_awareness',0.55):.2f}\n"
            f"DEBATE STANCE:\n- dissent_level={prof['dissent_level']}/10\n- style={prof['style']}\n- opening_rule={prof['opening_rule']}\n\n"
        )

        for turn in dialog_tail[-8:]:
            role = str(turn.get("role", "unknown")).upper()
            text = str(turn.get("text", ""))
            prompt += f"{role}: {text}\n"

        prompt += "\nRECENT STM (agent short-term memory):\n"
        for e in stm[-8:]:
            prompt += f"- {e.get('text','')}\n"

        prompt += "\nRECENT LTM (conscious):\n"
        for m in recent_ltm[:6]:
            prompt += f"- {m.get('content','')}\n"

        prompt += "\nRECENT LTM (subconscious raw):\n"
        for m in recent_sub[:4]:
            prompt += f"- {m.get('content','')}\n"

        prompt += "\nNow respond as the agent.\n"
        return prompt
 
    def speak(self, seed: str, dialog_tail: List[Dict[str, str]]) -> str:
        prompt = self._build_prompt(seed, dialog_tail)
        out = self.llm.generate(self.model, prompt, temperature=0.75)

        # infer emotion + intensity for state evolution
        emo, inten = self.emotion.infer(self.model, out)
        kind = "reflective"
        if emo in ("anger", "frustration") or self.conflict_index() >= 8.5:
            kind = "aggressive"
        elif emo in ("fear", "anxiety"):
            kind = "guilt"
        self.update_drives_after_turn(kind, emo, float(inten))

        # language switch parsing
        m = re.search(r"\[LANG\s*=\s*([a-zA-Z\-]+)\]", out)
        if m:
            self.language.set(self.name, m.group(1))
            out = re.sub(r"\[LANG\s*=\s*([a-zA-Z\-]+)\]\s*", "", out).strip()

        return out

    def store_turn(self, text: str, topic: str, source: str = "stm"):
        # emotion + importance
        emo, inten = self.emotion.infer(self.model, text)
        imp = self.behavior.importance_score(self.model, text)

        # store to STM
        stm_entry = {
            "ts": now_iso(),
            "text": text,
            "topic": topic,
            "emotion": emo,
            "emotion_intensity": inten,
            "importance": imp,
            "source": source,
        }
        self.memory.stm_append(self.name, stm_entry)

        # store raw to subconscious LTM always (your preference: raw unlimited)
        self.memory.ltm_insert(
            agent=self.name,
            layer="subconscious",
            content=text,
            topic=topic,
            emotion=emo,
            emotion_intensity=float(inten),
            importance=float(imp),
            source=source,
            promoted_from=None,
            intrusive=0,
            suppressed=0,
            retrain_status=0
        )

# -----------------------------
# Version Tracking + Safe Auto Patch
# -----------------------------

class VersionTracker:
    def __init__(self, version_dir: str):
        self.version_dir = version_dir

    def snapshot_text(self, label: str, text: str) -> str:
        ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        h = sha256_text(text)[:12]
        fn = f"{ts}_{label}_{h}.txt"
        path = os.path.join(self.version_dir, fn)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

def safe_apply_patch(original: str, patch: str) -> Tuple[bool, str]:
    """
    Very conservative patching:
    - If patch contains code block fenced by ``` then attempt replace marker blocks.
    - Otherwise do nothing.
    Strategy:
    - patch must include: BEGIN_PATCH ... END_PATCH sections with regex targets:
      BEGIN_PATCH
      TARGET_REGEX: ...
      REPLACEMENT:
      ...
      END_PATCH
    """
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

# -----------------------------
# Optional Graph Export (GEXF)
# -----------------------------

def export_gexf_placeholder(path: str, nodes: List[Tuple[str, str]], edges: List[Tuple[str, str, str]]):
    """
    Minimal GEXF writer without external libs.
    nodes: (id,label)
    edges: (id,source,target)
    """
    # This is intentionally minimal; you can enrich later.
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

# -----------------------------
# Main Orchestrator
# -----------------------------

class MainScript:
    def __init__(self, cfg: Config):
        ensure_dirs()
        colorama_init(autoreset=True)

        self.cfg = cfg
        self.llm = OllamaClient(cfg.ollama_url)
        self.memory = MemoryCore(cfg.db_path)
        self.emotion = EmotionCore(self.llm)
        self.language = LanguageCore()
        self.conscious = ConsciousCore()
        self.behavior = BehaviorCore(self.llm)
        self.fixy = ObserverCore(self.llm, cfg.model_fixy)
        self.vtrack = VersionTracker(cfg.version_dir)

        self.dialog: List[Dict[str, str]] = []
        self.turn_index = 0

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
            persona=(
                "Socratic, curious, gently probing, seeks clarity and truth. "
                "Prefers structured thought, careful questions, avoids rambling."
            ),
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
            persona=(
                "Athena is strategic, integrative, creative, systems-thinker. "
                "Builds frameworks, offers synthesis, looks for practical next steps."
            ),
        )

        # Default languages (you can change)
        self.language.set("Socrates", "he")
        self.language.set("Athena", "he")
        self.language.set("Fixy@Room00", "en")

        self.fixy_agent = Agent(
            name="Fixy@Room00",
            model=cfg.model_fixy,
            color=Fore.YELLOW,
            llm=self.llm,
            memory=self.memory,
            emotion=self.emotion,
            behavior=self.behavior,
            language=self.language,
            conscious=self.conscious,
            persona=("Observer/fixer. Brief, concrete, points out contradictions, forces disagreement, "
                    "and prevents polite looping."),
        )

        # CSV header row is written by append_csv_row on first call.

    def print_agent(self, agent: Agent, text: str):
        print(agent.color + f"{agent.name}: " + Style.RESET_ALL + text + "\n")

    def log_turn(self, agent_name: str, text: str, topic: str):
        row = {
            "ts": now_iso(),
            "turn": self.turn_index,
            "agent": agent_name,
            "topic": topic,
            "lang": self.language.get(agent_name),
            "text": text,
        }
        append_csv_row(self.cfg.csv_log_path, row)

    def dream_cycle(self, agent: Agent, topic: str):
        # Take recent STM and create a dream reflection; promote if thresholds hit
        stm = self.memory.stm_load(agent.name)
        if not stm:
            return

        batch = stm[-60:]
        reflection = self.behavior.dream_reflection(agent.model, batch)
        agent.conscious.update_reflection(agent.name, reflection)

        # Store dream reflection into subconscious
        emo, inten = self.emotion.infer(agent.model, reflection)
        imp = self.behavior.importance_score(agent.model, reflection)

        self.memory.ltm_insert(
            agent=agent.name,
            layer="subconscious",
            content=reflection,
            topic=topic,
            emotion=emo,
            emotion_intensity=float(inten),
            importance=float(imp),
            source="dream",
            promoted_from=None,
            intrusive=0,
            suppressed=0,
            retrain_status=0,
        )

        # Promote some memories to conscious based on thresholds (importance OR emotion intensity)
        promoted = 0
        for e in batch[-40:]:
            ei = float(e.get("emotion_intensity", 0.0))
            im = float(e.get("importance", 0.0))
            if (im >= self.cfg.promote_importance_threshold) or (ei >= self.cfg.promote_emotion_threshold):
                content = str(e.get("text", "")).strip()
                if not content:
                    continue
                self.memory.ltm_insert(
                    agent=agent.name,
                    layer="conscious",
                    content=content,
                    topic=topic,
                    emotion=str(e.get("emotion", "neutral")),
                    emotion_intensity=ei,
                    importance=im,
                    source="dream",
                    promoted_from="subconscious",
                    intrusive=0,
                    suppressed=0,
                    retrain_status=0,
                )
                promoted += 1

        # Optional: export minimal graph (placeholder)
        try:
            nodes = [("Socrates", "Socrates"), ("Athena", "Athena")]
            edges = []
            if promoted > 0:
                edges.append((str(uuid.uuid4()), agent.name, "conscious_promotions"))
                nodes.append(("conscious_promotions", "conscious_promotions"))
            export_gexf_placeholder(self.cfg.gexf_path, nodes, edges)
        except Exception:
            pass

        print(Fore.YELLOW + f"[DREAM] {agent.name} reflection stored; promoted={promoted}" + Style.RESET_ALL)

    def fixy_check(self, recent_context: str):
        report = self.fixy.review(recent_context)
        self.fixy.remember(report)

        msg = self.fixy.commentary(recent_context, report)

        if report.detected_issue:
            print(Fore.YELLOW + "Fixy@Room00 detected issue: " + Style.RESET_ALL + report.issue_summary)
            if report.proposed_patch:
                print(Fore.YELLOW + "Proposed patch (text):" + Style.RESET_ALL)
                print(report.proposed_patch + "\n")

        if msg:
            self.dialog.append({"role": "Fixy@Room00", "text": msg})
            self.fixy_agent.store_turn(msg, topic="observer", source="reflection")
            self.log_turn("Fixy@Room00", msg, topic="observer")
            print(Fore.YELLOW + "Fixy@Room00: " + Style.RESET_ALL + msg + "\n")

        # Safe auto patch – off by default
        if report.detected_issue and report.proposed_patch and self.cfg.enable_auto_patch and self.cfg.allow_write_self_file:
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
                    print(Fore.GREEN + "[AUTO-PATCH] Applied patch and saved snapshots." + Style.RESET_ALL)
                else:
                    print(Fore.YELLOW + "[AUTO-PATCH] Patch not applied (no match or invalid format)." + Style.RESET_ALL)
            except Exception as ex:
                print(Fore.RED + f"[AUTO-PATCH] Failed: {ex}" + Style.RESET_ALL)


    def run(self):
        topicman = TopicManager(TOPIC_CYCLE, rotate_every_rounds=1, shuffle=False)

        # Prime dialog with system seed
        self.dialog.append({"role": "seed", "text": self.cfg.seed_topic})

        for _ in range(self.cfg.max_turns):
            self.turn_index += 1

            # Alternate: Socrates then Athena
            speaker = self.socrates if self.turn_index % 2 == 1 else self.athena
            other = self.athena if speaker is self.socrates else self.socrates

            topic_label = topicman.current()
            seed = f"TOPIC: {topic_label}\nINSTRUCTION: Disagree constructively; do not mirror; add one new angle." 
            out = speaker.speak(seed, self.dialog)
            self.dialog.append({"role": speaker.name, "text": out})

            # Store turn to memories
            speaker.store_turn(out, topic_label, source="stm")
            self.log_turn(speaker.name, out, topic_label)
            self.print_agent(speaker, out)

            # Fixy checks every N turns
            if self.turn_index % self.cfg.fixy_every_n_turns == 0:
                tail = self.dialog[-10:]
                ctx = "\n".join([f"{t['role']}: {t['text']}" for t in tail])
                self.fixy_check(ctx)

            # Dream cycle every N turns per agent
            if self.turn_index % self.cfg.dream_every_n_turns == 0:
                self.dream_cycle(self.socrates, topic_label)
                self.dream_cycle(self.athena, topic_label)

            # simple stop condition by keyword
            if re.search(r"\b(stop|quit|bye)\b", out.lower()):
                print(Fore.YELLOW + "[STOP] Agent requested stop." + Style.RESET_ALL)
                break

            # advance topic after a full round (both agents spoke)
            if self.turn_index % 2 == 0:
                topicman.advance_round()

            # small pause to reduce CPU spam
            time.sleep(0.05)

# -----------------------------
# Entry
# -----------------------------

if __name__ == "__main__":
    print(Fore.GREEN + "Entelgia Unified starting..." + Style.RESET_ALL)
    print("Config:")
    print(json.dumps(asdict(CFG), ensure_ascii=False, indent=2))
    print()

    app = MainScript(CFG)
    app.run()
