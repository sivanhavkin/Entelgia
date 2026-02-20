#!/usr/bin/env python3
"""
Entelgia Deep Implementation Validator - IMPROVED VERSION
==========================================================
Validates that ALL promised features are actually implemented in code.
Enhanced with better pattern matching and detection.
"""

import re
import ast
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

class ImplementationStatus(Enum):
    FULLY_IMPLEMENTED = "✅"
    PARTIALLY_IMPLEMENTED = "⚠️"
    NOT_IMPLEMENTED = "❌"

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
            self.content = self.main_file.read_text(encoding='utf-8')
            try:
                self.tree = ast.parse(self.content)
            except SyntaxError:
                print("⚠ Could not parse main Python file")
    
    def find_classes(self, pattern: str) -> List[str]:
        """Find all classes matching pattern - IMPROVED"""
        classes = []
        if self.tree:
            for node in ast.walk(self.tree):
                if isinstance(node, ast.ClassDef):
                    if re.search(pattern, node.name, re.IGNORECASE):
                        classes.append(node.name)
        return classes
    
    def find_functions(self, pattern: str) -> List[str]:
        """Find all functions matching pattern - IMPROVED"""
        functions = []
        if self.tree:
            for node in ast.walk(self.tree):
                # Support both sync and async functions
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if re.search(pattern, node.name, re.IGNORECASE):
                        functions.append(node.name)
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
            # Pattern 1: param: type = value
            rf'{param_name}\s*:\s*(?:int|float|str|bool)\s*=\s*([^\n#]+)',
            # Pattern 2: param = value  
            rf'{param_name}\s*=\s*([^\n#]+)',
            # Pattern 3: Legacy format
            rf'{param_name}\s*[:=]\s*(?:int|float|str|bool)?\s*=\s*([^\n#]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                return match.group(1).strip()
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
        
        # IMPROVED: Search for multiple naming patterns
        socrates_patterns = [r'Socrates', r'SocratesAgent', r'Agent.*Socrates']
        athena_patterns = [r'Athena', r'AthenaAgent', r'Agent.*Athena']
        fixy_patterns = [r'Fixy', r'FixyAgent', r'FixyObserver', r'ObserverFixy']
        
        socrates = []
        for p in socrates_patterns:
            socrates.extend(self.find_classes(p))
        
        athena = []
        for p in athena_patterns:
            athena.extend(self.find_classes(p))
        
        fixy = []
        for p in fixy_patterns:
            fixy.extend(self.find_classes(p))
        
        # Remove duplicates
        socrates = list(set(socrates))
        athena = list(set(athena))
        fixy = list(set(fixy))
        
        if socrates:
            details.append(f"✓ Socrates: {', '.join(socrates)}")
            checks_passed += 1
        else:
            details.append("✗ Socrates not found")
        
        if athena:
            details.append(f"✓ Athena: {', '.join(athena)}")
            checks_passed += 1
        else:
            details.append("✗ Athena not found")
        
        if fixy:
            details.append(f"✓ Fixy: {', '.join(fixy)}")
            checks_passed += 1
        else:
            details.append("✗ Fixy not found")
        
        dialogue_funcs = self.find_functions(r'dialogue|speak|converse|turn')
        if dialogue_funcs:
            details.append(f"✓ Dialogue functions: {len(dialogue_funcs)}")
            checks_passed += 1
        else:
            details.append("✗ No dialogue functions")
        
        patterns = self.code_contains_patterns([
            r'agent.*respond|respond.*agent',
            r'speaker.*selection|select.*speaker'
        ])
        if any(patterns.values()):
            details.append("✓ Agent interaction logic")
            checks_passed += 1
        
        if re.search(r'persona|personality', self.content, re.IGNORECASE):
            details.append("✓ Agent personas defined")
            checks_passed += 1
        
        score = checks_passed / total_checks
        status = ImplementationStatus.FULLY_IMPLEMENTED if score >= 0.8 else \
                 ImplementationStatus.PARTIALLY_IMPLEMENTED if score >= 0.5 else \
                 ImplementationStatus.NOT_IMPLEMENTED
        
        return FeatureCheck("Multi-agent System", status, details, score)
    
    def validate_persistent_memory(self) -> FeatureCheck:
        """Validate Persistent memory"""
        details = []
        checks_passed = 0
        total_checks = 8
        
        memory_classes = self.find_classes(r'Memory')
        if memory_classes:
            details.append(f"✓ Memory classes: {', '.join(memory_classes[:3])}")
            checks_passed += 1
        
        imports = self.find_imports(['json', 'sqlite3', 'hmac'])
        if imports['json']:
            details.append("✓ JSON imported")
            checks_passed += 1
        
        if re.search(r'sqlite|\.db', self.content, re.IGNORECASE):
            details.append("✓ SQLite database")
            checks_passed += 1
        
        if imports['hmac'] and re.search(r'sha256', self.content, re.IGNORECASE):
            details.append("✓ HMAC-SHA256")
            checks_passed += 1
        
        stm_funcs = self.find_functions(r'stm|short')
        if stm_funcs:
            details.append(f"✓ STM functions: {len(stm_funcs)}")
            checks_passed += 1
        
        ltm_funcs = self.find_functions(r'ltm|long')
        if ltm_funcs:
            details.append(f"✓ LTM functions: {len(ltm_funcs)}")
            checks_passed += 1
        
        persist_funcs = self.find_functions(r'save|load|persist')
        if persist_funcs:
            details.append(f"✓ Persistence: {len(persist_funcs)}")
            checks_passed += 1
        
        if re.search(r'signature|verify|integrity', self.content, re.IGNORECASE):
            details.append("✓ Memory integrity")
            checks_passed += 1
        
        score = checks_passed / total_checks
        status = ImplementationStatus.FULLY_IMPLEMENTED if score >= 0.8 else \
                 ImplementationStatus.PARTIALLY_IMPLEMENTED if score >= 0.5 else \
                 ImplementationStatus.NOT_IMPLEMENTED
        
        return FeatureCheck("Persistent Memory", status, details, score)
    
    def validate_dream_cycles(self) -> FeatureCheck:
        """Validate Dream cycles - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 7
        
        dream_turns = self.check_config_value('dream_every_n_turns')
        if dream_turns:
            details.append(f"✓ dream_every_n_turns = {dream_turns}")
            checks_passed += 1
        
        dream_funcs = self.find_functions(r'dream')
        if dream_funcs:
            details.append(f"✓ Dream functions: {', '.join(dream_funcs[:2])}")
            checks_passed += 1
        
        # IMPROVED: More comprehensive promotion function search
        promote_funcs = self.find_functions(r'promote|consolidate|transfer.*memory|migrate')
        if promote_funcs:
            details.append(f"✓ Memory promotion: {', '.join(promote_funcs[:2])}")
            checks_passed += 1
        else:
            # Fallback: check in code text
            if re.search(r'promote.*memory|memory.*promotion|consolidat', self.content, re.IGNORECASE):
                details.append("✓ Memory promotion (found in code)")
                checks_passed += 1
        
        if re.search(r'importance.*score', self.content, re.IGNORECASE):
            details.append("✓ Importance scoring")
            checks_passed += 1
        
        if re.search(r'stm.*ltm|short.*long', self.content, re.IGNORECASE):
            details.append("✓ STM → LTM transfer")
            checks_passed += 1
        
        if re.search(r'turn.*%.*dream|dream_every', self.content, re.IGNORECASE):
            details.append("✓ Dream cycle triggering")
            checks_passed += 1
        
        if re.search(r'threshold', self.content, re.IGNORECASE):
            details.append("✓ Threshold filtering")
            checks_passed += 1
        
        score = checks_passed / total_checks
        status = ImplementationStatus.FULLY_IMPLEMENTED if score >= 0.8 else \
                 ImplementationStatus.PARTIALLY_IMPLEMENTED if score >= 0.5 else \
                 ImplementationStatus.NOT_IMPLEMENTED
        
        return FeatureCheck("Dream Cycles", status, details, score)
    
    def validate_emotion_tracking(self) -> FeatureCheck:
        """Validate Emotion tracking - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 5
        
        emotion_classes = self.find_classes(r'Emotion')
        if emotion_classes:
            details.append(f"✓ Emotion class: {', '.join(emotion_classes)}")
            checks_passed += 1
        
        # IMPROVED: Search for emotion methods/functions
        emotion_funcs = self.find_functions(r'emotion|affect|feeling|sentiment')
        if emotion_funcs:
            details.append(f"✓ Emotion functions: {len(emotion_funcs)}")
            checks_passed += 1
        else:
            # Check if EmotionCore has methods
            if re.search(r'class.*Emotion.*:.*def', self.content, re.DOTALL):
                details.append("✓ Emotion methods (in class)")
                checks_passed += 1
        
        if re.search(r'track.*emotion|emotion.*track', self.content, re.IGNORECASE):
            details.append("✓ Emotion tracking logic")
            checks_passed += 1
        
        importance_funcs = self.find_functions(r'importance|score|weight')
        if importance_funcs:
            details.append(f"✓ Importance scoring: {len(importance_funcs)}")
            checks_passed += 1
        
        if re.search(r'emotion.*memory|affect.*memory', self.content, re.IGNORECASE):
            details.append("✓ Emotion-memory integration")
            checks_passed += 1
        
        score = checks_passed / total_checks
        status = ImplementationStatus.FULLY_IMPLEMENTED if score >= 0.8 else \
                 ImplementationStatus.PARTIALLY_IMPLEMENTED if score >= 0.5 else \
                 ImplementationStatus.NOT_IMPLEMENTED
        
        return FeatureCheck("Emotion Tracking", status, details, score)
    
    def validate_psychological_drives(self) -> FeatureCheck:
        """Validate Id/Ego/Superego"""
        details = []
        checks_passed = 0
        total_checks = 4
        
        psycho_patterns = self.code_contains_patterns([r'\bid\b', r'\bego\b', r'\bsuperego\b'])
        found_drives = [k for k, v in psycho_patterns.items() if v]
        
        if len(found_drives) >= 2:
            details.append(f"✓ Drives found: {len(found_drives)}")
            checks_passed += len(found_drives)
        else:
            details.append("⚠ Limited psychological drives")
        
        if re.search(r'drive|motivation', self.content, re.IGNORECASE):
            details.append("✓ Drive modeling")
            checks_passed += 1
        
        score = checks_passed / total_checks
        status = ImplementationStatus.FULLY_IMPLEMENTED if score >= 0.75 else \
                 ImplementationStatus.PARTIALLY_IMPLEMENTED if score >= 0.5 else \
                 ImplementationStatus.NOT_IMPLEMENTED
        
        return FeatureCheck("Psychological Drives", status, details, score)
    
    def validate_observer_metacognition(self) -> FeatureCheck:
        """Validate Observer metacognition - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 5
        
        observer_classes = self.find_classes(r'Observer')
        if observer_classes:
            details.append(f"✓ Observer: {', '.join(observer_classes)}")
            checks_passed += 1
        
        fixy_funcs = self.find_functions(r'fixy|observe|monitor')
        if fixy_funcs:
            details.append(f"✓ Meta-cognitive functions: {len(fixy_funcs)}")
            checks_passed += 1
        
        if re.search(r'meta.*cognition|self.*monitor', self.content, re.IGNORECASE):
            details.append("✓ Meta-cognitive logic")
            checks_passed += 1
        
        # IMPROVED: Better intervention detection
        intervention_funcs = self.find_functions(r'interven|correct|adjust|fix')
        if intervention_funcs:
            details.append(f"✓ Intervention: {', '.join(intervention_funcs[:2])}")
            checks_passed += 1
        else:
            # Fallback: check in code
            if re.search(r'should_intervene|generate_intervention', self.content, re.IGNORECASE):
                details.append("✓ Intervention mechanisms (found in code)")
                checks_passed += 1
        
        fixy_config = self.check_config_value('fixy_every_n_turns')
        if fixy_config:
            details.append(f"✓ fixy_every_n_turns = {fixy_config}")
            checks_passed += 1
        
        score = checks_passed / total_checks
        status = ImplementationStatus.FULLY_IMPLEMENTED if score >= 0.8 else \
                 ImplementationStatus.PARTIALLY_IMPLEMENTED if score >= 0.6 else \
                 ImplementationStatus.NOT_IMPLEMENTED
        
        return FeatureCheck("Observer Meta-cognition", status, details, score)
    
    def validate_pii_redaction(self) -> FeatureCheck:
        """Validate PII redaction - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 4
        
        redact_funcs = self.find_functions(r'redact|sanitize|anonymize')
        if redact_funcs:
            details.append(f"✓ Redaction: {', '.join(redact_funcs)}")
            checks_passed += 1
        
        if re.search(r'pii|email|phone|ssn', self.content, re.IGNORECASE):
            details.append("✓ PII patterns")
            checks_passed += 1
        
        # IMPROVED: Better regex detection
        if re.search(r're\.compile|re\.search.*email|re\.search.*phone|@.*\.com', self.content, re.IGNORECASE):
            details.append("✓ Regex PII detection")
            checks_passed += 1
        else:
            # Check for inline regex patterns
            if re.search(r'r["\\'].*email|r["\\'].*phone', self.content, re.IGNORECASE):
                details.append("✓ Regex patterns (inline)")
                checks_passed += 1
        
        if re.search(r'privacy|gdpr|protect.*data', self.content, re.IGNORECASE):
            details.append("✓ Privacy safeguards")
            checks_passed += 1
        
        score = checks_passed / total_checks
        status = ImplementationStatus.FULLY_IMPLEMENTED if score >= 0.75 else \
                 ImplementationStatus.PARTIALLY_IMPLEMENTED if score >= 0.5 else \
                 ImplementationStatus.NOT_IMPLEMENTED
        
        return FeatureCheck("PII Redaction", status, details, score)
    
    def validate_error_handling(self) -> FeatureCheck:
        """Validate Error handling - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 5
        
        try_count = len(re.findall(r'\btry:', self.content))
        if try_count >= 5:
            details.append(f"✓ Error handling: {try_count} try blocks")
            checks_passed += 1
        
        if re.search(r'backoff|retry.*delay|exponential.*retry', self.content, re.IGNORECASE):
            details.append("✓ Exponential backoff")
            checks_passed += 1
        
        # IMPROVED: Better retry detection
        retry_funcs = self.find_functions(r'retry|backoff|attempt')
        if retry_funcs:
            details.append(f"✓ Retry functions: {', '.join(retry_funcs[:2])}")
            checks_passed += 1
        else:
            # Check for retry logic in code
            if re.search(r'for.*attempt|while.*retry|max.*retries', self.content, re.IGNORECASE):
                details.append("✓ Retry logic (found in code)")
                checks_passed += 1
        
        if re.search(r'timeout|time.*limit', self.content, re.IGNORECASE):
            details.append("✓ Timeout handling")
            checks_passed += 1
        
        log_imports = self.find_imports(['logging'])
        if log_imports['logging']:
            details.append("✓ Logging configured")
            checks_passed += 1
        
        score = checks_passed / total_checks
        status = ImplementationStatus.FULLY_IMPLEMENTED if score >= 0.8 else \
                 ImplementationStatus.PARTIALLY_IMPLEMENTED if score >= 0.6 else \
                 ImplementationStatus.NOT_IMPLEMENTED
        
        return FeatureCheck("Error Handling", status, details, score)
    
    def validate_enhanced_dialogue_engine(self) -> FeatureCheck:
        """Validate Enhanced Dialogue Engine"""
        details = []
        checks_passed = 0
        total_checks = 5
        
        entelgia_dir = self.root / "entelgia"
        if entelgia_dir.exists():
            details.append("✓ entelgia/ package exists")
            checks_passed += 1
            
            modules = ["dialogue_engine.py", "enhanced_personas.py", "context_manager.py", "fixy_interactive.py"]
            found = [m for m in modules if (entelgia_dir / m).exists()]
            if len(found) >= 3:
                details.append(f"✓ Modules: {len(found)}/4")
                checks_passed += 1
        
        if re.search(r'select.*speaker|dynamic.*turn', self.content, re.IGNORECASE):
            details.append("✓ Dynamic speaker selection")
            checks_passed += 1
        
        if re.search(r'seed.*strategy|analogy|disagree', self.content, re.IGNORECASE):
            details.append("✓ Varied seed generation")
            checks_passed += 1
        
        if re.search(r'context.*enrich|history', self.content, re.IGNORECASE):
            details.append("✓ Context enrichment")
            checks_passed += 1
        
        score = checks_passed / total_checks
        status = ImplementationStatus.FULLY_IMPLEMENTED if score >= 0.8 else \
                 ImplementationStatus.PARTIALLY_IMPLEMENTED if score >= 0.6 else \
                 ImplementationStatus.NOT_IMPLEMENTED
        
        return FeatureCheck("Enhanced Dialogue Engine", status, details, score)
    
    def validate_configuration(self) -> FeatureCheck:
        """Validate Configuration - IMPROVED"""
        details = []
        checks_passed = 0
        total_checks = 8
        
        config_params = ['max_turns', 'timeout_minutes', 'max_output_words', \
                        'llm_timeout', 'fixy_every_n_turns', 'dream_every_n_turns']
        
        for param in config_params:
            value = self.check_config_value(param)
            if value:
                details.append(f"✓ {param} = {value}")
                checks_passed += 1
            else:
                details.append(f"✗ {param} not found")
        
        config_classes = self.find_classes(r'^Config$')
        if config_classes:
            details.append("✓ Config class found")
            checks_passed += 1
        
        # IMPROVED: Better validation detection
        validate_funcs = self.find_functions(r'validate|__post_init__|check.*config')
        if validate_funcs or re.search(r'def __post_init__', self.content):
            details.append("✓ Config validation")
            checks_passed += 1
        else:
            details.append("✗ No config validation")
        
        score = checks_passed / total_checks
        status = ImplementationStatus.FULLY_IMPLEMENTED if score >= 0.8 else \
                 ImplementationStatus.PARTIALLY_IMPLEMENTED if score >= 0.6 else \
                 ImplementationStatus.NOT_IMPLEMENTED
        
        return FeatureCheck("Configuration", status, details, score)


def print_feature_report(feature: FeatureCheck):
    print(f"\n{feature.status.value} {feature.name} ({feature.score:.0%})")
    for detail in feature.details:
        print(f"   {detail}")


def print_summary(features: List[FeatureCheck]):
    print("\n" + "="*70)
    print("📊 IMPLEMENTATION VALIDATION SUMMARY")
    print("="*70)
    
    total_score = sum(f.score for f in features) / len(features)
    
    fully = len([f for f in features if f.status == ImplementationStatus.FULLY_IMPLEMENTED])
    partial = len([f for f in features if f.status == ImplementationStatus.PARTIALLY_IMPLEMENTED])
    missing = len([f for f in features if f.status == ImplementationStatus.NOT_IMPLEMENTED])
    
    print(f"\n✅ Fully Implemented:     {fully}/{len(features)}")
    print(f"⚠️  Partially Implemented: {partial}/{len(features)}")
    print(f"❌ Not Implemented:       {missing}/{len(features)}")
    print(f"\n🎯 Overall Score:         {total_score:.1%}")
    
    print("\n" + "="*70)
    
    if total_score >= 0.9:
        print("🏆 EXCELLENT: All features well-implemented!")
    elif total_score >= 0.75:
        print("✅ GOOD: Most features implemented")
    elif total_score >= 0.5:
        print("⚠️  FAIR: Some features need work")
    else:
        print("❌ POOR: Many features missing")
    
    print("="*70 + "\n")


def main():
    root = Path(__file__).parent.parent
    
    print("\n" + "="*70)
    print("🔍 ENTELGIA DEEP IMPLEMENTATION VALIDATOR v2.0 (IMPROVED)")
    print("="*70)
    print("\nAnalyzing with enhanced pattern matching...")
    
    validator = DeepValidator(root)
    
    if not validator.main_file.exists():
        print("❌ Entelgia_production_meta.py not found!")
        return
    
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