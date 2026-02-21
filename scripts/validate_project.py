#!/usr/bin/env python3
"""
Entelgia Deep Implementation Validator - IMPROVED
===================================================
Enhanced validation with better pattern matching and fallback detection.
"""

import re
import ast
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class ImplementationStatus(Enum):
    FULLY_IMPLEMENTED = ""
    PARTIALLY_IMPLEMENTED = ""
    NOT_IMPLEMENTED = ""


@dataclass
class FeatureCheck:
    name: str
    status: ImplementationStatus
    details: List[str]
    score: float


class DeepValidator:
    def __init__(self, project_root: Path):
        self.root = project_root
        self.main_file = project_root / "Entelgia_production_meta.py"
        self.content = ""
        self.tree = None

        if self.main_file.exists():
            self.content = self.main_file.read_text(encoding="utf-8")
            try:
                self.tree = ast.parse(self.content)
            except SyntaxError:
                print("Could not parse main Python file")

    def find_classes(self, patterns: List[str]) -> List[str]:
        """Find all classes matching any of the patterns"""
        classes = []
        if self.tree:
            for node in ast.walk(self.tree):
                if isinstance(node, ast.ClassDef):
                    for pattern in patterns:
                        if re.search(pattern, node.name, re.IGNORECASE):
                            if node.name not in classes:
                                classes.append(node.name)
                            break
        return classes

    def find_functions(self, patterns: List[str]) -> List[str]:
        """Find all functions/methods matching any pattern - IMPROVED"""
        functions = []
        if self.tree:
            for node in ast.walk(self.tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for pattern in patterns:
                        if re.search(pattern, node.name, re.IGNORECASE):
                            if node.name not in functions:
                                functions.append(node.name)
                            break
        return functions

    def find_imports(self, module_names: List[str]) -> Dict[str, bool]:
        """Check if specific modules are imported"""
        imports = {mod: False for mod in module_names}
        if self.tree:
            for node in ast.walk(self.tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in module_names:
                                imports[alias.name] = True
                    elif isinstance(node, ast.ImportFrom):
                        if node.module in module_names:
                            imports[node.module] = True
        return imports

    def check_config_value(self, param_name: str) -> Optional[str]:
        """Extract config parameter value - IMPROVED with multiple patterns"""
        patterns = [
            rf"{param_name}\s*:\s*(?:int|float|str|bool)\s*=\s*([^\n#]+)",
            rf"{param_name}\s*[:=]\s*(?:int|float|str|bool)?\s*=\s*([^\n#]+)",
            rf"{param_name}\s*=\s*([^\n#,\)]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                value = match.group(1).strip()
                # Clean up quotes and whitespace
                value = value.strip("\"'")
                return value
        return None

    def code_contains_patterns(self, patterns: List[str]) -> Dict[str, bool]:
        """Check if code contains specific patterns"""
        results = {}
        content_lower = self.content.lower()
        for pattern in patterns:
            results[pattern] = bool(re.search(pattern, content_lower, re.IGNORECASE))
        return results

    def validate_multi_agent_system(self) -> FeatureCheck:
        """Validate Multi-agent dialogue system - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 6

        # Enhanced pattern matching
        socrates = self.find_classes(
            [r"Socrates", r"SocratesAgent", r"Agent.*Socrates"]
        )
        athena = self.find_classes([r"Athena", r"AthenaAgent", r"Agent.*Athena"])
        fixy = self.find_classes(
            [r"Fixy", r"FixyAgent", r"InteractiveFixy"]
        )

        # Fallback: search in code text
        if not socrates and re.search(
            r"socrates.*agent|agent.*socrates", self.content, re.IGNORECASE
        ):
            socrates = ["[found in code]"]
        if not athena and re.search(
            r"athena.*agent|agent.*athena", self.content, re.IGNORECASE
        ):
            athena = ["[found in code]"]

        if socrates:
            details.append(f"Socrates: {', '.join(socrates)}")
            checks_passed += 1
        else:
            details.append("Socrates not found")

        if athena:
            details.append(f"Athena: {', '.join(athena)}")
            checks_passed += 1
        else:
            details.append("Athena not found")

        if fixy:
            details.append(f"Fixy: {', '.join(fixy)}")
            checks_passed += 1
        else:
            details.append("Fixy not found")

        dialogue_funcs = self.find_functions(
            [r"dialogue", r"speak", r"converse", r"respond"]
        )
        if dialogue_funcs:
            details.append(f"Dialogue functions: {len(dialogue_funcs)}")
            checks_passed += 1
        else:
            details.append("No dialogue functions")

        patterns = self.code_contains_patterns(
            [r"agent.*respond", r"speaker.*selection", r"turn.*taking"]
        )
        if any(patterns.values()):
            details.append("Agent interaction logic")
            checks_passed += 1

        if re.search(r"persona|personality|character", self.content, re.IGNORECASE):
            details.append("Agent personas defined")
            checks_passed += 1

        score = checks_passed / total_checks
        status = (
            ImplementationStatus.FULLY_IMPLEMENTED
            if score >= 0.8
            else (
                ImplementationStatus.PARTIALLY_IMPLEMENTED
                if score >= 0.5
                else ImplementationStatus.NOT_IMPLEMENTED
            )
        )

        return FeatureCheck("Multi-agent System", status, details, score)

    def validate_persistent_memory(self) -> FeatureCheck:
        """Validate Persistent memory"""
        details = []
        checks_passed = 0
        total_checks = 8

        memory_classes = self.find_classes([r"Memory", r"MemoryCore", r"MemoryManager"])
        if memory_classes:
            details.append(f"Memory classes: {', '.join(memory_classes[:3])}")
            checks_passed += 1

        imports = self.find_imports(["json", "sqlite3", "hmac"])
        if imports.get("json"):
            details.append("JSON imported")
            checks_passed += 1

        if re.search(r"sqlite|\.db", self.content, re.IGNORECASE):
            details.append("SQLite database")
            checks_passed += 1

        if imports.get("hmac") and re.search(r"sha256", self.content, re.IGNORECASE):
            details.append("HMAC-SHA256")
            checks_passed += 1

        stm_funcs = self.find_functions([r"stm", r"short.*term", r"temporary"])
        if stm_funcs:
            details.append(f"STM functions: {len(stm_funcs)}")
            checks_passed += 1

        ltm_funcs = self.find_functions([r"ltm", r"long.*term", r"permanent"])
        if ltm_funcs:
            details.append(f"LTM functions: {len(ltm_funcs)}")
            checks_passed += 1

        persist_funcs = self.find_functions(
            [r"save", r"load", r"persist", r"store", r"retrieve"]
        )
        if persist_funcs:
            details.append(f"Persistence: {len(persist_funcs)}")
            checks_passed += 1

        if re.search(r"signature|verify|integrity|hmac", self.content, re.IGNORECASE):
            details.append("Memory integrity")
            checks_passed += 1

        score = checks_passed / total_checks
        status = (
            ImplementationStatus.FULLY_IMPLEMENTED
            if score >= 0.8
            else (
                ImplementationStatus.PARTIALLY_IMPLEMENTED
                if score >= 0.5
                else ImplementationStatus.NOT_IMPLEMENTED
            )
        )

        return FeatureCheck("Persistent Memory", status, details, score)

    def validate_dream_cycles(self) -> FeatureCheck:
        """Validate Dream cycles - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 7

        dream_turns = self.check_config_value("dream_every_n_turns")
        if dream_turns:
            details.append(f"dream_every_n_turns = {dream_turns}")
            checks_passed += 1

        dream_funcs = self.find_functions(
            [r"dream", r"dream.*cycle", r"dream.*reflection"]
        )
        if dream_funcs:
            details.append(f"Dream functions: {', '.join(dream_funcs[:2])}")
            checks_passed += 1

        # IMPROVED: multiple promotion patterns
        promote_funcs = self.find_functions(
            [r"promote", r"consolidate", r"transfer.*memory", r"migrate"]
        )
        promote_in_code = re.search(
            r"promote|consolidate|transfer.*memory", self.content, re.IGNORECASE
        )
        if promote_funcs or promote_in_code:
            if promote_funcs:
                details.append(f"Memory promotion: {', '.join(promote_funcs[:2])}")
            else:
                details.append("Memory promotion: [found in code]")
            checks_passed += 1
        else:
            details.append("No promotion logic")

        if re.search(
            r"importance.*score|score.*importance", self.content, re.IGNORECASE
        ):
            details.append("Importance scoring")
            checks_passed += 1

        if re.search(
            r"stm.*ltm|short.*long|temporary.*permanent", self.content, re.IGNORECASE
        ):
            details.append("STM → LTM transfer")
            checks_passed += 1

        if re.search(
            r"turn.*%.*dream|dream_every|dream.*trigger", self.content, re.IGNORECASE
        ):
            details.append("Dream cycle triggering")
            checks_passed += 1

        if re.search(
            r"threshold|cutoff|minimum.*importance", self.content, re.IGNORECASE
        ):
            details.append("Threshold filtering")
            checks_passed += 1

        score = checks_passed / total_checks
        status = (
            ImplementationStatus.FULLY_IMPLEMENTED
            if score >= 0.8
            else (
                ImplementationStatus.PARTIALLY_IMPLEMENTED
                if score >= 0.5
                else ImplementationStatus.NOT_IMPLEMENTED
            )
        )

        return FeatureCheck("Dream Cycles", status, details, score)

    def validate_emotion_tracking(self) -> FeatureCheck:
        """Validate Emotion tracking - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 5

        emotion_classes = self.find_classes(
            [r"Emotion", r"EmotionCore", r"EmotionTracker"]
        )
        if emotion_classes:
            details.append(f"Emotion class: {', '.join(emotion_classes)}")
            checks_passed += 1

        emotion_funcs = self.find_functions(
            [r"emotion", r"affect", r"sentiment", r"feeling"]
        )
        # Fallback: check if emotion methods exist
        if not emotion_funcs:
            if re.search(
                r"def.*emotion|emotion.*score|track.*emotion",
                self.content,
                re.IGNORECASE,
            ):
                emotion_funcs = ["[found in code]"]

        if emotion_funcs:
            details.append(
                f"Emotion functions: {len(emotion_funcs) if isinstance(emotion_funcs, list) and emotion_funcs[0] != '[found in code]' else 'found'}"
            )
            checks_passed += 1

        if re.search(
            r"track.*emotion|emotion.*track|emotion.*state", self.content, re.IGNORECASE
        ):
            details.append("Emotion tracking logic")
            checks_passed += 1

        importance_funcs = self.find_functions(
            [r"importance", r"score", r"weight", r"priority"]
        )
        if importance_funcs:
            details.append(f"Importance scoring: {len(importance_funcs)}")
            checks_passed += 1

        if re.search(
            r"emotion.*memory|memory.*emotion|affect.*weight",
            self.content,
            re.IGNORECASE,
        ):
            details.append("Emotion-memory integration")
            checks_passed += 1

        score = checks_passed / total_checks
        status = (
            ImplementationStatus.FULLY_IMPLEMENTED
            if score >= 0.8
            else (
                ImplementationStatus.PARTIALLY_IMPLEMENTED
                if score >= 0.5
                else ImplementationStatus.NOT_IMPLEMENTED
            )
        )

        return FeatureCheck("Emotion Tracking", status, details, score)

    def validate_psychological_drives(self) -> FeatureCheck:
        """Validate Id/Ego/Superego"""
        details = []
        checks_passed = 0
        total_checks = 4

        psycho_patterns = self.code_contains_patterns(
            [r"\bid\b", r"\bego\b", r"\bsuperego\b"]
        )
        found_drives = [k for k, v in psycho_patterns.items() if v]

        if len(found_drives) >= 2:
            details.append(f"Drives found: {len(found_drives)}")
            checks_passed += len(found_drives)
        else:
            details.append("Limited psychological drives")

        if re.search(r"drive|motivation|impulse", self.content, re.IGNORECASE):
            details.append("Drive modeling")
            checks_passed += 1

        score = checks_passed / total_checks
        status = (
            ImplementationStatus.FULLY_IMPLEMENTED
            if score >= 0.75
            else (
                ImplementationStatus.PARTIALLY_IMPLEMENTED
                if score >= 0.5
                else ImplementationStatus.NOT_IMPLEMENTED
            )
        )

        return FeatureCheck("Psychological Drives", status, details, score)

    def validate_observer_metacognition(self) -> FeatureCheck:
        """Validate Observer metacognition - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 4

        observer_classes = self.find_classes(
            [r"Observer", r"InteractiveFixy", r"Fixy.*Observer"]
        )
        if observer_classes:
            details.append(f"Observer: {', '.join(observer_classes)}")
            checks_passed += 1

        fixy_funcs = self.find_functions([r"fixy", r"observe", r"monitor", r"watch"])
        if fixy_funcs:
            details.append(f"Meta-cognitive functions: {len(fixy_funcs)}")
            checks_passed += 1

        if re.search(
            r"meta.*cognition|metacognition|self.*monitor", self.content, re.IGNORECASE
        ):
            details.append("Meta-cognitive logic")
            checks_passed += 1

        # IMPROVED: check for intervention
        intervention_funcs = self.find_functions(
            [r"interven", r"correct", r"adjust", r"fix"]
        )
        intervention_in_code = re.search(
            r"should_intervene|generate_intervention|intervention.*logic",
            self.content,
            re.IGNORECASE,
        )
        if intervention_funcs or intervention_in_code:
            if intervention_funcs:
                details.append(f"Intervention: {len(intervention_funcs)}")
            else:
                details.append("Intervention: [found in code]")
            checks_passed += 1
        else:
            details.append("No intervention mechanisms")

        score = checks_passed / total_checks
        status = (
            ImplementationStatus.FULLY_IMPLEMENTED
            if score >= 0.8
            else (
                ImplementationStatus.PARTIALLY_IMPLEMENTED
                if score >= 0.6
                else ImplementationStatus.NOT_IMPLEMENTED
            )
        )

        return FeatureCheck("Observer Meta-cognition", status, details, score)

    def validate_pii_redaction(self) -> FeatureCheck:
        """Validate PII redaction - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 4

        redact_funcs = self.find_functions(
            [r"redact", r"sanitize", r"anonymize", r"mask"]
        )
        if redact_funcs:
            details.append(f"Redaction: {', '.join(redact_funcs)}")
            checks_passed += 1

        if re.search(
            r"pii|personal.*identif|email.*pattern|phone.*pattern",
            self.content,
            re.IGNORECASE,
        ):
            details.append("PII patterns")
            checks_passed += 1

        # IMPROVED: check for regex in multiple formats
        regex_patterns = [
            r"re\.compile.*email",
            r"re\.search.*email",
            r'r["\'].*@.*\\.',
            r"EMAIL_PATTERN|PHONE_PATTERN",
        ]
        if any(re.search(p, self.content, re.IGNORECASE) for p in regex_patterns):
            details.append("Regex PII detection")
            checks_passed += 1
        else:
            details.append("Limited regex detection")

        if re.search(
            r"privacy|gdpr|protect.*data|redacted", self.content, re.IGNORECASE
        ):
            details.append("Privacy safeguards")
            checks_passed += 1

        score = checks_passed / total_checks
        status = (
            ImplementationStatus.FULLY_IMPLEMENTED
            if score >= 0.75
            else (
                ImplementationStatus.PARTIALLY_IMPLEMENTED
                if score >= 0.5
                else ImplementationStatus.NOT_IMPLEMENTED
            )
        )

        return FeatureCheck("PII Redaction", status, details, score)

    def validate_error_handling(self) -> FeatureCheck:
        """Validate Error handling - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 5

        try_count = len(re.findall(r"\btry:", self.content))
        if try_count >= 5:
            details.append(f"Error handling: {try_count} try blocks")
            checks_passed += 1

        if re.search(
            r"backoff|exponential.*retry|retry.*delay", self.content, re.IGNORECASE
        ):
            details.append("Exponential backoff")
            checks_passed += 1

        # IMPROVED: check for retry logic
        retry_funcs = self.find_functions([r"retry", r"backoff", r"attempt"])
        retry_in_code = re.search(
            r"for.*attempt|while.*retry|max.*retries|llm_max_retries",
            self.content,
            re.IGNORECASE,
        )
        if retry_funcs or retry_in_code:
            if retry_funcs:
                details.append(f"Retry functions: {len(retry_funcs)}")
            else:
                details.append("Retry logic: [found in code]")
            checks_passed += 1
        else:
            details.append("Limited retry logic")

        if re.search(r"timeout|time.*limit|llm_timeout", self.content, re.IGNORECASE):
            details.append("Timeout handling")
            checks_passed += 1

        log_imports = self.find_imports(["logging"])
        if log_imports.get("logging"):
            details.append("Logging configured")
            checks_passed += 1

        score = checks_passed / total_checks
        status = (
            ImplementationStatus.FULLY_IMPLEMENTED
            if score >= 0.8
            else (
                ImplementationStatus.PARTIALLY_IMPLEMENTED
                if score >= 0.6
                else ImplementationStatus.NOT_IMPLEMENTED
            )
        )

        return FeatureCheck("Error Handling", status, details, score)

    def validate_enhanced_dialogue_engine(self) -> FeatureCheck:
        """Validate Enhanced Dialogue Engine"""
        details = []
        checks_passed = 0
        total_checks = 5

        entelgia_dir = self.root / "entelgia"
        if entelgia_dir.exists():
            details.append("entelgia/ package exists")
            checks_passed += 1

            modules = [
                "dialogue_engine.py",
                "enhanced_personas.py",
                "context_manager.py",
                "fixy_interactive.py",
            ]
            found = [m for m in modules if (entelgia_dir / m).exists()]
            if len(found) >= 3:
                details.append(f"Modules: {len(found)}/4")
                checks_passed += 1

        if re.search(
            r"select.*speaker|dynamic.*turn|speaker.*selection",
            self.content,
            re.IGNORECASE,
        ):
            details.append("Dynamic speaker selection")
            checks_passed += 1

        if re.search(
            r"seed.*strategy|analogy|disagree|reflect|question",
            self.content,
            re.IGNORECASE,
        ):
            details.append("Varied seed generation")
            checks_passed += 1

        if re.search(
            r"context.*enrich|history|dialogue.*context", self.content, re.IGNORECASE
        ):
            details.append("Context enrichment")
            checks_passed += 1

        score = checks_passed / total_checks
        status = (
            ImplementationStatus.FULLY_IMPLEMENTED
            if score >= 0.8
            else (
                ImplementationStatus.PARTIALLY_IMPLEMENTED
                if score >= 0.6
                else ImplementationStatus.NOT_IMPLEMENTED
            )
        )

        return FeatureCheck("Enhanced Dialogue Engine", status, details, score)

    def validate_configuration(self) -> FeatureCheck:
        """Validate Configuration - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 8

        config_params = [
            "max_turns",
            "timeout_minutes",
            "max_output_words",
            "llm_timeout",
            "dream_every_n_turns",
        ]

        for param in config_params:
            value = self.check_config_value(param)
            if value:
                details.append(f"{param} = {value}")
                checks_passed += 1
            else:
                details.append(f"{param} not found")

        config_classes = self.find_classes([r"^Config$", r"Configuration"])
        if config_classes:
            details.append("Config class found")
            checks_passed += 1

        # IMPROVED: check for validation method
        validate_funcs = self.find_functions([r"validate", r"__post_init__"])
        if validate_funcs or re.search(r"def __post_init__|def validate", self.content):
            details.append("Config validation")
            checks_passed += 1
        else:
            details.append("No validation method")

        score = checks_passed / total_checks
        status = (
            ImplementationStatus.FULLY_IMPLEMENTED
            if score >= 0.8
            else (
                ImplementationStatus.PARTIALLY_IMPLEMENTED
                if score >= 0.6
                else ImplementationStatus.NOT_IMPLEMENTED
            )
        )

        return FeatureCheck("Configuration", status, details, score)


def print_feature_report(feature: FeatureCheck):
    print(f"\n{feature.status.value} {feature.name} ({feature.score:.0%})")
    for detail in feature.details:
        print(f"   {detail}")


def print_summary(features: List[FeatureCheck]):
    print("\n" + "=" * 70)
    print("IMPLEMENTATION VALIDATION SUMMARY")
    print("=" * 70)

    total_score = sum(f.score for f in features) / len(features)

    fully = len(
        [f for f in features if f.status == ImplementationStatus.FULLY_IMPLEMENTED]
    )
    partial = len(
        [f for f in features if f.status == ImplementationStatus.PARTIALLY_IMPLEMENTED]
    )
    missing = len(
        [f for f in features if f.status == ImplementationStatus.NOT_IMPLEMENTED]
    )

    print(f"\nFully Implemented:     {fully}/{len(features)}")
    print(f" Partially Implemented: {partial}/{len(features)}")
    print(f"Not Implemented:       {missing}/{len(features)}")
    print(f"\nOverall Score:         {total_score:.1%}")

    print("\n" + "=" * 70)

    if total_score >= 0.9:
        print("EXCELLENT: All features well-implemented!")
    elif total_score >= 0.8:
        print("VERY GOOD: Strong implementation")
    elif total_score >= 0.75:
        print("GOOD: Most features implemented")
    elif total_score >= 0.5:
        print(" FAIR: Some features need work")
    else:
        print("POOR: Many features missing")

    print("=" * 70 + "\n")


def main():
    root = Path(__file__).parent.parent

    print("\n" + "=" * 70)
    print("ENTELGIA DEEP IMPLEMENTATION VALIDATOR v2.0")
    print("   Enhanced pattern matching & fallback detection")
    print("=" * 70)

    validator = DeepValidator(root)

    if not validator.main_file.exists():
        print("Entelgia_production_meta.py not found!")
        return

    print("\nAnalyzing code implementation...\n")

    features = [
        validator.validate_multi_agent_system(),
        validator.validate_persistent_memory(),
        validator.validate_dream_cycles(),
        validator.validate_emotion_tracking(),
        validator.validate_psychological_drives(),
        validator.validate_observer_metacognition(),
        validator.validate_pii_redaction(),
        validator.validate_error_handling(),
        validator.validate_enhanced_dialogue_engine(),
        validator.validate_configuration(),
    ]

    for feature in features:
        print_feature_report(feature)

    print_summary(features)


if __name__ == "__main__":
    main()
