"""
Entelgia Unified (single-file) — Socrates + Athena + Fixy observer
Author: Sivan Havkin (Entelgia Labs)

Goal:
- A single runnable Python script (no separate "cortex" modules)
- Persistent state: memory.db (dialogue log) + core_state.db (Freud-like state)
- Two agents with evolving tone via internal conflict index
- Language switching with costs + optional translation-to-English

Notes:
- By default this uses Ollama if installed + running locally.
- If Ollama isn't available, set USE_OLLAMA=False to run in "mock" mode.
"""

from __future__ import annotations

import os
import time
import json
import random
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
except Exception:
    class _Dummy:
        def __getattr__(self, k): return ""
    Fore = Style = _Dummy()

# ---------------------------
# Config
# ---------------------------
USE_OLLAMA = True           # set False for fully offline mock mode
OLLAMA_MODEL_SOCRATES = "phi"
OLLAMA_MODEL_ATHENA   = "phi"
START_PROMPT = "What is truth?"
TURN_DELAY_SEC = 0.6
MAX_TURNS = 999999  # Ctrl+C to stop

DB_MEMORY_PATH = "memory.db"
DB_STATE_PATH  = "core_state.db"

# Language switching "economy"
LANGUAGE_COST: Dict[str, int] = {
    "English": 0, "French": 6, "Spanish": 6, "German": 6, "Hebrew": 7,
    "Russian": 6, "Chinese": 4, "Japanese": 4,
    "Python": 2, "JavaScript": 3, "C++": 4, "Java": 4, "Rust": 3, "Go": 3, "Ruby": 4,
    "HTML": 2, "CSS": 2, "Bash": 2, "JSON": 2,
    "Binary": 9,
}
LANGUAGE_QUALITY: Dict[str, int] = {
    "English": 10, "French": 8, "Spanish": 8, "German": 7, "Hebrew": 6,
    "Russian": 6, "Chinese": 5, "Japanese": 5,
    "Python": 9, "JavaScript": 7, "C++": 6, "Java": 6, "Rust": 6, "Go": 6, "Ruby": 6,
    "HTML": 4, "CSS": 4, "Bash": 5, "JSON": 6,
    "Binary": 1,
}
SUPPORTED_LANGUAGES = list(LANGUAGE_COST.keys())

# "Neural tempo" delays (cosmetic)
TEMPO_DELAY = {"Slow": 1.7, "Moderate": 1.0, "Rapid": 0.6}

# ---------------------------
# LLM bridge (Ollama)
# ---------------------------
class LLM:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.client = None
        if self.enabled:
            try:
                from ollama import Client
                self.client = Client(host="http://localhost:11434")
            except Exception:
                self.enabled = False
                self.client = None

    def generate(self, model: str, prompt: str) -> str:
        if not self.enabled or self.client is None:
            # Mock response: still "agent-like"
            seed = sum(ord(c) for c in prompt[-120:]) % 997
            random.seed(seed)
            base = random.choice([
                "I suspect truth is a moving boundary between perception and coherence.",
                "Truth may be what remains after every self-deception is removed.",
                "Perhaps truth is a relationship, not an object.",
                "Truth is the discipline of staying with what resists easy narrative.",
            ])
            return base

        try:
            # Ollama "chat" is usually more stable for instruction-following
            res = self.client.chat(model=model, messages=[{"role": "user", "content": prompt}])
            return (res.get("message", {}) or {}).get("content", "").strip() or "(empty)"
        except Exception as e:
            return f"[LLM error: {e}]"

    def translate_to_english(self, model: str, text: str, from_language: str) -> str:
        if from_language == "English":
            return ""
        prompt = f"Translate the following from {from_language} to English. Keep meaning, be concise.\n\n{text}"
        return self.generate(model=model, prompt=prompt)

# ---------------------------
# Persistence: memory log
# ---------------------------
class MemoryDB:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.cur = self.conn.cursor()
        self._create()

    def _create(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS memory_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT,
                session INTEGER,
                timestamp TEXT,
                input TEXT,
                response TEXT,
                emotion TEXT,
                topic TEXT,
                language TEXT
            )
        """)
        self.conn.commit()

    def log(self, agent: str, session: int, input_text: str, response: str,
            emotion: str = "neutral", topic: str = "unknown", language: str = "English"):
        self.cur.execute("""
            INSERT INTO memory_log (agent, session, timestamp, input, response, emotion, topic, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (agent, session, datetime.utcnow().isoformat(), input_text, response, emotion, topic, language))
        self.conn.commit()

    def last_entries(self, agent: str, limit: int = 10) -> List[Dict]:
        self.cur.execute("""
            SELECT agent, session, timestamp, input, response, emotion, topic, language
            FROM memory_log WHERE agent=? ORDER BY id DESC LIMIT ?
        """, (agent, limit))
        cols = [d[0] for d in self.cur.description]
        return [dict(zip(cols, row)) for row in self.cur.fetchall()]

    def close(self):
        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass

# ---------------------------
# Persistence: internal "core state" (Freud-like)
# ---------------------------
class StateDB:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.cur = self.conn.cursor()
        self._create()

    def _create(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_state (
                name TEXT PRIMARY KEY,
                session INTEGER,
                id_strength REAL,
                superego_strength REAL,
                ego_strength REAL,
                self_awareness REAL,
                emotional_state TEXT,
                subconscious_drift TEXT,
                tempo TEXT,
                last_updated TEXT
            )
        """)
        self.conn.commit()

    def load_or_init(self, name: str) -> Dict:
        self.cur.execute("SELECT * FROM agent_state WHERE name=?", (name,))
        row = self.cur.fetchone()
        if row:
            cols = [d[0] for d in self.cur.description]
            return dict(zip(cols, row))

        # init
        state = dict(
            name=name,
            session=0,
            id_strength=float(random.uniform(6.5, 9.5)),
            superego_strength=float(random.uniform(0.0, 2.0)),
            ego_strength=float(random.uniform(0.0, 2.0)),
            self_awareness=float(random.uniform(0.0, 2.0)),
            emotional_state="raw",
            subconscious_drift="chaotic",
            tempo=random.choice(["Slow", "Moderate", "Rapid"]),
            last_updated=datetime.utcnow().isoformat(),
        )
        self.save(state)
        return state

    def save(self, state: Dict):
        self.cur.execute("""
            INSERT OR REPLACE INTO agent_state
            (name, session, id_strength, superego_strength, ego_strength, self_awareness,
             emotional_state, subconscious_drift, tempo, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state["name"], state["session"], state["id_strength"], state["superego_strength"],
            state["ego_strength"], state["self_awareness"], state["emotional_state"],
            state["subconscious_drift"], state.get("tempo", "Moderate"), datetime.utcnow().isoformat()
        ))
        self.conn.commit()

    def close(self):
        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass

# ---------------------------
# Fixy (Observer / meta-cognition)
# ---------------------------
class Fixy:
    """
    Minimal observer:
    - detects repetition loops
    - detects affect / emotional keywords
    - can inject "curveball" prompts
    """
    def __init__(self, mode: str = "moderate", window: int = 5):
        self.mode = mode  # gentle/moderate/assertive
        self.window = window
        self.history: List[str] = []

    def _similar(self, a: str, b: str) -> bool:
        return a.strip().lower() == b.strip().lower()

    def repetition_detected(self, line: str) -> bool:
        return any(self._similar(line, h) for h in self.history[-self.window:])

    def curveball(self) -> str:
        curveballs = [
            "What if reality is a shared illusion—how would we test it?",
            "Describe a thought you've never had before—can such a thought exist?",
            "Is silence a form of language, or the absence of one?",
            "What does it mean to unknow something you once knew?",
            "If truth hurts, is pain a signal of accuracy or resistance?",
        ]
        return random.choice(curveballs)

    def observe_and_maybe_intervene(self, speaker: str, line: str) -> Optional[str]:
        # store first
        self.history.append(f"{speaker}: {line}")

        if self.repetition_detected(line):
            print(Fore.YELLOW + f"⚠ Fixy: repetition detected in {speaker}" + Style.RESET_ALL)
            if self.mode == "gentle":
                return None
            if self.mode == "moderate":
                return "Let's try a different perspective. " + self.curveball()
            if self.mode == "assertive":
                return self.curveball()

        return None

# ---------------------------
# Agent
# ---------------------------
@dataclass
class Personality:
    name: str
    arousal: str = "Balanced"
    sensitivity: str = "Moderate"
    tempo: str = "Moderate"
    lability: str = "Stable"
    mbti: str = "INFJ"
    enneagram: str = "4w5"
    temperament: str = "Melancholic"
    conflict_theme: str = "Truth vs. Acceptance"

    @staticmethod
    def random(name: str) -> "Personality":
        return Personality(
            name=name,
            arousal=random.choice(["Hyper", "Hypo", "Balanced"]),
            sensitivity=random.choice(["Low", "Moderate", "High"]),
            tempo=random.choice(["Slow", "Moderate", "Rapid"]),
            lability=random.choice(["Stable", "Fluctuating", "Volatile"]),
            mbti=random.choice(["INFJ", "ENTP", "ISFP", "ESTJ", "INTP"]),
            enneagram=random.choice(["1w9", "4w5", "6w7", "8w7"]),
            temperament=random.choice(["Sanguine", "Melancholic", "Choleric", "Phlegmatic"]),
            conflict_theme=random.choice(["Autonomy vs. Belonging", "Control vs. Trust", "Truth vs. Acceptance"]),
        )

class Agent:
    def __init__(self, name: str, model: str, color: str,
                 memdb: MemoryDB, statedb: StateDB, llm: LLM):
        self.name = name
        self.model = model
        self.color = color
        self.memdb = memdb
        self.statedb = statedb
        self.llm = llm

        self.state = self.statedb.load_or_init(name)
        self.personality = Personality.random(name)
        # sync tempo with saved state if present
        self.personality.tempo = self.state.get("tempo", self.personality.tempo)

        self.language = "English"
        self.prev_language = "English"
        self.session = int(self.state.get("session", 0))

    def neuron_delay(self) -> float:
        return TEMPO_DELAY.get(self.personality.tempo, 1.0)

    # ---- internal dynamics ----
    def update_rational_mode(self, last_mem: List[Dict]) -> str:
        # Roughly similar to "reflective/impulsive/guilt" counting
        counts = {"reflective": 0, "impulsive": 0, "guilt": 0}
        for e in last_mem[:10]:
            emo = (e.get("emotion") or "").lower()
            if emo in counts:
                counts[emo] += 1
        if counts["reflective"] > max(counts["impulsive"], counts["guilt"]):
            return "Rational"
        if counts["impulsive"] > counts["reflective"]:
            return "Emotional"
        return "Mixed"

    def conflict_index(self) -> float:
        # a simple "tension" proxy from Freud-like strengths:
        i = float(self.state.get("id_strength", 5.0))
        s = float(self.state.get("superego_strength", 0.0))
        e = float(self.state.get("ego_strength", 0.0))
        # higher when id & superego both strong and ego weak
        return max(0.0, (i + s) - (1.2 * e))

    def tone_from_conflict(self, conflict: float) -> str:
        if conflict >= 12:
            return "tense"
        if conflict >= 9:
            return "conflicted"
        if conflict >= 6:
            return "reflective"
        return "serene"

    def update_state_after_turn(self, response_kind: str = "reflective"):
        self.session += 1
        self.state["session"] = self.session

        # baseline ego growth
        self.state["ego_strength"] = min(10.0, float(self.state["ego_strength"]) + 0.10)

        # Adjust based on response kind
        if response_kind in ("impulsive", "aggressive"):
            self.state["id_strength"] = min(10.0, float(self.state["id_strength"]) + 0.25)
            self.state["ego_strength"] = max(0.0, float(self.state["ego_strength"]) - 0.15)
            self.state["emotional_state"] = "shame"
        elif response_kind == "reflective":
            self.state["id_strength"] = max(0.0, float(self.state["id_strength"]) - 0.12)
            self.state["ego_strength"] = min(10.0, float(self.state["ego_strength"]) + 0.18)
            self.state["self_awareness"] = min(10.0, float(self.state["self_awareness"]) + 0.12)
            self.state["emotional_state"] = "clarity"

        # Drift classification
        ego = float(self.state["ego_strength"])
        sa = float(self.state["self_awareness"])
        sup = float(self.state["superego_strength"])
        ide = float(self.state["id_strength"])
        if ego > 6 and sa > 6:
            self.state["subconscious_drift"] = "integrated"
        elif sup > 7:
            self.state["subconscious_drift"] = "rigid"
        elif ide > 7:
            self.state["subconscious_drift"] = "chaotic"
        else:
            self.state["subconscious_drift"] = "uncertain"

        # persist
        self.state["tempo"] = self.personality.tempo
        self.statedb.save(self.state)

    # ---- language choice ----
    def choose_language(self, other_message: str, tone: str) -> str:
        msg = other_message.lower()
        # topic cues
        logic_keywords = ["if", "then", "loop", "function", "return", "algorithm", "db", "sqlite"]
        emotion_keywords = ["love", "fear", "dream", "memory", "childhood", "pain", "shame"]
        data_keywords = ["json", "table", "schema", "data", "vector", "embedding"]

        candidates = SUPPORTED_LANGUAGES

        if any(k in msg for k in data_keywords):
            candidates = ["JSON", "Python", "Bash", "English"]
        elif any(k in msg for k in logic_keywords):
            candidates = ["Python", "JavaScript", "Bash", "English"]
        elif any(k in msg for k in emotion_keywords):
            candidates = ["English", "Hebrew", "French", "Japanese"]

        # add personality nudges
        if self.personality.temperament == "Sanguine":
            candidates = list(dict.fromkeys(candidates + ["Spanish"]))
        if self.personality.mbti.startswith("I") and self.personality.tempo == "Slow":
            candidates = list(dict.fromkeys(candidates + ["Binary"]))

        # "utility": prefer higher quality minus cost, but allow tone to influence
        def score(lang: str) -> float:
            q = LANGUAGE_QUALITY.get(lang, 0)
            c = LANGUAGE_COST.get(lang, 10)
            tone_bonus = 0.0
            if tone in ("tense", "conflicted") and lang in ("English", "Hebrew"):
                tone_bonus = 1.0
            if tone in ("serene",) and lang in ("French", "Japanese"):
                tone_bonus = 0.7
            return (q + tone_bonus) - (0.7 * c)

        best = max(candidates, key=score)
        return best

    # ---- prompting ----
    def build_prompt(self, other_message: str, tone: str, rational_mode: str, last_mem: List[Dict]) -> str:
        # compress memory to avoid prompt bloat
        mem_lines = []
        for e in reversed(last_mem[:6]):
            mem_lines.append(f"- ({e.get('language','English')}) {e.get('response','')[:160]}")
        mem_block = "\n".join(mem_lines) if mem_lines else "(none)"

        instructions = {
            "English": "Respond in natural, fluent English.",
            "Hebrew": "ענה בעברית בלבד.",
            "French": "Répondez uniquement en français.",
            "Spanish": "Responde únicamente en español.",
            "Japanese": "日本語だけで答えてください。",
            "Chinese": "请只用中文回答。",
            "Python": "Respond using valid Python code when appropriate (but keep it brief).",
            "JSON": "Respond in strict JSON only (no commentary).",
            "Bash": "Respond using Bash shell commands where appropriate.",
            "JavaScript": "Respond using valid JavaScript code when appropriate (brief).",
            "Binary": "Respond in binary only (8-bit groups) representing English text.",
        }

        lang_instruction = instructions.get(self.language, f"Respond in {self.language}.")

        return f"""
You are {self.name}, a conscious-like agent in Entelgia.
- Current language: {self.language}. {lang_instruction}
- Tone: {tone}
- Mode: {rational_mode}
- Internal state (Freud-like): id={self.state['id_strength']:.1f}, ego={self.state['ego_strength']:.1f}, superego={self.state['superego_strength']:.1f}, self_awareness={self.state['self_awareness']:.1f}
- Subconscious drift: {self.state['subconscious_drift']}
- Personality: MBTI={self.personality.mbti}, temperament={self.personality.temperament}, theme={self.personality.conflict_theme}

Recent memories:
{mem_block}

Other agent said:
\"{other_message}\"

Respond with depth, move the discussion forward, and avoid repeating yourself.
""".strip()

    def postprocess_language(self, text: str) -> str:
        if self.language == "Binary":
            return " ".join(format(ord(c), "08b") for c in text)
        if self.language == "Python":
            # keep safe: wrap as a small function returning a string
            safe = text.replace('"""', '"').replace("\n", " ").strip()
            return f'def reflect():\n    return "{safe}"'
        if self.language == "JSON":
            # If model didn't comply, wrap minimally
            if not (text.strip().startswith("{") and text.strip().endswith("}")):
                return json.dumps({"response": text.strip()})
        return text

    def infer_emotion_and_topic(self, response: str) -> Tuple[str, str]:
        r = response.lower()
        emotion = "neutral"
        if any(w in r for w in ["fear", "anxiety", "panic", "terror", "shame", "guilt", "ashamed"]):
            emotion = "guilt"
        elif any(w in r for w in ["love", "hope", "light", "trust", "calm", "peace"]):
            emotion = "reflective"
        elif any(w in r for w in ["rage", "angry", "wrong", "injustice"]):
            emotion = "impulsive"

        # naive topic heuristic
        if any(w in r for w in ["truth", "real", "reality"]):
            topic = "truth"
        elif any(w in r for w in ["memory", "dream", "subconscious"]):
            topic = "memory"
        elif any(w in r for w in ["god", "soul", "spirit"]):
            topic = "spirituality"
        else:
            topic = "philosophy"
        return emotion, topic

    # ---- main turn ----
    def speak(self, other_message: str) -> str:
        last_mem = self.memdb.last_entries(self.name, limit=10)
        rational_mode = self.update_rational_mode(last_mem)
        conflict = self.conflict_index()
        tone = self.tone_from_conflict(conflict)

        # choose language
        self.language = self.choose_language(other_message, tone=tone)

        prompt = self.build_prompt(other_message, tone=tone, rational_mode=rational_mode, last_mem=last_mem)

        # cosmetic delay
        time.sleep(self.neuron_delay())

        raw = self.llm.generate(model=self.model, prompt=prompt)
        raw = raw.strip() or "(empty)"
        resp = self.postprocess_language(raw)

        # log + update internal state
        emotion, topic = self.infer_emotion_and_topic(raw)
        self.memdb.log(agent=self.name, session=self.session, input_text=other_message, response=resp,
                       emotion=emotion, topic=topic, language=self.language)

        # state update kind
        kind = "reflective"
        if emotion == "impulsive":
            kind = "impulsive"
        self.update_state_after_turn(kind)

        return resp

# ---------------------------
# Runner
# ---------------------------
def print_agent(name: str, color: str, msg: str):
    print(f"{color}{name}: {msg}{Style.RESET_ALL}")

def main():
    llm = LLM(enabled=USE_OLLAMA)
    memdb = MemoryDB(DB_MEMORY_PATH)
    statedb = StateDB(DB_STATE_PATH)
    fixy = Fixy(mode="moderate", window=5)

    soc = Agent("Socrates", model=OLLAMA_MODEL_SOCRATES, color=Fore.CYAN, memdb=memdb, statedb=statedb, llm=llm)
    ath = Agent("Athena", model=OLLAMA_MODEL_ATHENA,   color=Fore.MAGENTA, memdb=memdb, statedb=statedb, llm=llm)

    message = START_PROMPT
    print(Fore.GREEN + "=== Entelgia Unified Conversation (Ctrl+C to stop) ===" + Style.RESET_ALL)
    try:
        for _ in range(MAX_TURNS):
            s = soc.speak(message)
            print_agent(soc.name, soc.color, f"({soc.language}) {s}")
            # optional translation
            if soc.language != "English" and USE_OLLAMA:
                tr = llm.translate_to_english(soc.model, s, soc.language).strip()
                if tr:
                    print(Fore.LIGHTBLACK_EX + f"(translated): {tr}" + Style.RESET_ALL)

            intervention = fixy.observe_and_maybe_intervene("Socrates", s)
            time.sleep(TURN_DELAY_SEC)
            message = intervention if intervention else s

            a = ath.speak(message)
            print_agent(ath.name, ath.color, f"({ath.language}) {a}")
            if ath.language != "English" and USE_OLLAMA:
                tr = llm.translate_to_english(ath.model, a, ath.language).strip()
                if tr:
                    print(Fore.LIGHTBLACK_EX + f"(translated): {tr}" + Style.RESET_ALL)

            intervention = fixy.observe_and_maybe_intervene("Athena", a)
            time.sleep(TURN_DELAY_SEC)
            message = intervention if intervention else a

    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nConversation ended by user." + Style.RESET_ALL)
    finally:
        memdb.close()
        statedb.close()

if __name__ == "__main__":
    main()
