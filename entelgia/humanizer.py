import re
import random
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class HumanizerConfig:
    enabled: bool = True
    aggressive: bool = False
    preserve_meaning: bool = True
    max_sentence_length: int = 26
    split_long_sentences: bool = True
    remove_opening_scaffolds: bool = True
    diversify_agent_voice: bool = True
    randomness: float = 0.3
    seed: Optional[int] = None
    min_score: float = 0.15


@dataclass
class HumanizerResult:
    original_text: str
    humanized_text: str
    changed: bool
    flags: List[str] = field(default_factory=list)
    score_before: float = 0.0
    score_after: float = 0.0


class TextHumanizer:

    _OPENING_SCAFFOLDS = [
        r"\bin examining\b",
        r"\bin considering\b",
        r"\bin reflecting on\b",
        r"\bit is crucial to\b",
        r"\bit is essential to\b",
        r"\bit is important to\b",
        r"\bit is imperative to\b",
        r"\bit becomes clear that\b",
        r"\boften overlooked is\b",
        r"\bone might argue that\b",
        r"\bit is worth noting that\b",
        r"\bwe must consider\b",
        r"\blet us consider\b",
        r"\bit is necessary to\b",
        r"\bthis assumption fails to account for\b",
        r"\ban alternative perspective might consider\b",
    ]

    _WEAKENERS = {
        "significantly": "",
        "profoundly": "",
        "substantially": "",
        "indeed": "",
        "moreover": "also",
        "furthermore": "also",
        "thus": "so",
        "therefore": "so",
        "however": "but",
        "nevertheless": "still",
    }

    _ABSTRACT = {
        "individuals": "people",
        "societal": "social",
        "utilize": "use",
        "facilitate": "help",
        "demonstrate": "show",
        "numerous": "many",
        "obtain": "get",
        "commence": "start",
        "terminate": "end",
        "regarding": "about",
        "capacity": "ability",
        "outcomes": "results",
        "accessibility": "access",
        "socioeconomic background": "class background",
    }

    _LLM_PATTERNS = [
        r"\bit is (?:crucial|essential|important|imperative) to\b",
        r"\boften overlooked is\b",
        r"\bin (?:examining|considering|reflecting on)\b",
        r"\ban alternative perspective\b",
        r"\bunderlying assumptions\b",
        r"\bprevailing notion\b",
    ]

    _AGENT_VOICE = {
        "Socrates": [
            "The real issue is",
            "What gets missed is",
            "The harder question is",
        ],
        "Athena": [
            "A more balanced view is",
            "What matters here is",
        ],
        "Fixy": [
            "Plainly:",
            "Bottom line:",
        ],
    }

    def __init__(self, config: Optional[HumanizerConfig] = None):
        self.config = config or HumanizerConfig()
        if self.config.seed:
            random.seed(self.config.seed)

    def humanize(self, text: str, agent_name: Optional[str] = None) -> HumanizerResult:
        original = text.strip()
        if not original or not self.config.enabled:
            return HumanizerResult(original, original, False)

        flags = []
        score_before = self._score(original)

        if score_before < self.config.min_score:
            flags.append("score_skip")
            return HumanizerResult(
                original, original, False, flags, score_before, score_before
            )

        out = self._remove_scaffolds(original)
        if out != original:
            flags.append("scaffold_removed")

        new_out = self._replace_words(out)
        if new_out != out:
            flags.append("word_replace")
        out = new_out

        new_out = self._reduce_fillers(out)
        if new_out != out:
            flags.append("filler_reduce")
        out = new_out

        new_out = self._rewrite_opening(out)
        if new_out != out:
            flags.append("opening_rewrite")
        out = new_out

        if self.config.split_long_sentences:
            new_out = self._split_sentences(out)
            if new_out != out:
                flags.append("split")
            out = new_out

        if agent_name and self.config.diversify_agent_voice:
            new_out = self._apply_voice(out, agent_name)
            if new_out != out:
                flags.append(f"voice_{agent_name}")
            out = new_out

        score_after = self._score(out)

        return HumanizerResult(
            original, out, original != out, flags, score_before, score_after
        )

    def _score(self, text: str) -> float:
        hits = sum(bool(re.search(p, text.lower())) for p in self._LLM_PATTERNS)
        return min(1.0, hits * 0.2)

    def _remove_scaffolds(self, text: str) -> str:
        out = text
        for p in self._OPENING_SCAFFOLDS:
            out = re.sub(p, "", out, flags=re.IGNORECASE)
        out = out.strip(" ,.")
        if out:
            out = out[0].upper() + out[1:] if len(out) > 1 else out.upper()
        return out

    def _replace_words(self, text: str) -> str:
        out = text
        for k, v in self._ABSTRACT.items():
            out = re.sub(rf"\b{k}\b", v, out, flags=re.IGNORECASE)
        return out

    def _reduce_fillers(self, text: str) -> str:
        out = text
        for k, v in self._WEAKENERS.items():
            if v:
                out = re.sub(rf"\b{k}\b", v, out, flags=re.IGNORECASE)
            else:
                out = re.sub(rf"\b{k}\b", "", out, flags=re.IGNORECASE)
        return out

    def _rewrite_opening(self, text: str) -> str:
        return re.sub(r"^(It is .*? to )", "", text, flags=re.IGNORECASE)

    _SPLIT_SAFE_CONJUNCTIONS = frozenset(
        {
            "or",
            "nor",
            "and",
            "but",
            "yet",
            "so",
            "on",
            "in",
            "at",
            "of",
            "to",
            "by",
            "as",
            "if",
            "is",
            "it",
            "a",
        }
    )

    def _split_sentences(self, text: str) -> str:
        parts = re.split(r"(?<=[.!?])\s+", text)
        out = []
        for p in parts:
            words = p.split()
            if len(words) > self.config.max_sentence_length:
                mid = len(words) // 2
                # Slide mid forward to avoid the second half starting with a
                # conjunction/preposition, or the first half ending with one.
                while mid < len(words) - 1 and (
                    words[mid].lower() in self._SPLIT_SAFE_CONJUNCTIONS
                    or (
                        mid > 0
                        and words[mid - 1].rstrip(".,;:").lower()
                        in self._SPLIT_SAFE_CONJUNCTIONS
                    )
                ):
                    mid += 1
                first_half = " ".join(words[:mid])
                second_half = " ".join(words[mid:])
                # Ensure first half ends with terminal punctuation
                if first_half and first_half[-1] not in ".!?":
                    first_half += "."
                # Ensure second half starts with a capital letter
                if second_half:
                    second_half = (
                        second_half[0].upper() + second_half[1:]
                        if len(second_half) > 1
                        else second_half.upper()
                    )
                out.append(first_half)
                out.append(second_half)
            else:
                out.append(p)
        return " ".join(out)

    def _apply_voice(self, text: str, agent_name: str) -> str:
        if agent_name not in self._AGENT_VOICE:
            return text
        if random.random() > self.config.randomness:
            return text

        sentences = re.split(r"(?<=[.!?])\s+", text)
        if not sentences:
            return text

        starter = random.choice(self._AGENT_VOICE[agent_name])
        first = sentences[0].strip()
        if first:
            lowered = first[0].lower() + first[1:] if len(first) > 1 else first.lower()
            # Preserve standalone "I" — never lowercase it
            if first.startswith("I ") or first == "I":
                lowered = first
            first = starter + " " + lowered
        sentences[0] = first

        return " ".join(sentences)
