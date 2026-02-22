#!/usr/bin/env python3
"""
Entelgia Implementation vs. Documentation Validator
=====================================================
Parses all project markdown files to extract documented identifiers
(classes, functions, config parameters, module files) and compares
them against the actual Python source code.

Reports:
  - Documented items that are MISSING from code  (stale docs)
  - Code items that are NOT documented in any markdown file
"""

import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Markdown files considered authoritative for documentation coverage
MARKDOWN_FILES = [
    "README.md",
    "ARCHITECTURE.md",
    "SPEC.md",
    "whitepaper.md",
]

# Python source files / directories to inspect
PY_MAIN_FILE = "Entelgia_production_meta.py"
PY_PACKAGE_DIR = "entelgia"

# Classes that are intentionally internal and do not require documentation
INTERNAL_CLASSES: Set[str] = {
    "Agent",           # generic stub / base inside dialogue_engine.py
    "LRUCache",        # caching implementation detail
    "MetricsTracker",  # internal metrics collector
    "LLM",             # thin HTTP wrapper
    "TopicManager",    # internal topic rotation helper
    "VersionTracker",  # internal version snapshot helper
    "DefenseMechanism",
    "FreudianSlip",
    "SelfReplication",
    "ImplementationStatus",  # used only in validate_project.py
    "FeatureCheck",
    "MarkdownConsistencyChecker",
    "ConsistencyIssue",
    "DeepValidator",
    # validate_implementations.py own classes
    "ComparisonResult",
    "MarkdownExtractor",
    "CodeInspector",
    "ImplementationComparator",
}

# Public functions that are small helpers, test utilities, or entry points
# not requiring dedicated documentation entries
INTERNAL_FUNCTIONS: Set[str] = {
    "main",
    "setup_logging",
    "now_iso",
    "ensure_dirs",
    "sha256_text",
    "safe_json_dump",
    "load_json",
    "append_csv_row",
    "esc",
    "_first_sentence",
    "_topic_signature",
    "_trim_to_word_limit",
    "_is_question_resolved",
    "safe_ltm_payload",
    "create_signature",
    "validate_signature",
    "print_feature_report",
    "print_summary",
    # Entry-point / CLI helpers
    "run_api",
    "run_cli",
    "run_tests",
    # Utility functions that are implementation details, not user-facing API
    "compute_drive_pressure",
    "export_gexf_placeholder",
    "format_persona_for_prompt",
    "get_persona",
    "get_typical_opening",
    "is_sensitive_text",
    "redact_pii",
    "safe_apply_patch",
    # Inline test helpers defined inside the main file
    "test_behavior_core",
    "test_config_validation",
    "test_language_core",
    "test_lru_cache",
    "test_memory_signatures",
    "test_metrics_tracker",
    "test_redaction",
    "test_session_manager",
    "test_topic_manager",
    "test_validation",
    # validate_implementations.py own helpers
    "_print_result",
    "_print_summary",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ComparisonResult:
    """Holds the outcome of a single comparison category."""
    category: str
    in_code_not_docs: List[str] = field(default_factory=list)
    in_docs_not_code: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.in_code_not_docs and not self.in_docs_not_code


# ---------------------------------------------------------------------------
# Markdown extractor
# ---------------------------------------------------------------------------

class MarkdownExtractor:
    """Extracts documented identifiers from a set of markdown files."""

    # Matches backtick-quoted identifiers: `IdentifierName`
    _BACKTICK_RE = re.compile(r"`([A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*)`")
    # Matches bare .py filenames (not inside URLs)
    _PY_FILE_RE = re.compile(r"(?<![/\w])([a-z_][a-z_0-9]*\.py)\b")

    def __init__(self, root: Path, md_files: List[str]) -> None:
        self.root = root
        self.md_files = md_files
        self._raw: str = ""
        self._files_found: List[str] = []
        self._load()

    def _load(self) -> None:
        parts: List[str] = []
        for rel in self.md_files:
            p = self.root / rel
            if p.exists():
                parts.append(p.read_text(encoding="utf-8"))
                self._files_found.append(rel)
        self._raw = "\n".join(parts)

    @property
    def files_found(self) -> List[str]:
        return list(self._files_found)

    def identifiers(self) -> Set[str]:
        """All identifier tokens found in backticks across all docs."""
        found: Set[str] = set()
        for m in self._BACKTICK_RE.finditer(self._raw):
            token = m.group(1).split(".")[0]  # take first part of dotted names
            found.add(token)
        return found

    def py_filenames(self) -> Set[str]:
        """All *.py filenames mentioned in the docs (excluding __init__.py)."""
        found: Set[str] = set()
        for m in self._PY_FILE_RE.finditer(self._raw):
            fname = m.group(1)
            if fname != "__init__.py":
                found.add(fname)
        return found

    def raw_text(self) -> str:
        return self._raw

    def contains(self, token: str) -> bool:
        return token in self._raw


# ---------------------------------------------------------------------------
# Python source inspector
# ---------------------------------------------------------------------------

class CodeInspector:
    """Extracts public symbols from Python source files."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._sources: Dict[str, str] = {}
        self._trees: Dict[str, ast.Module] = {}
        self._load()

    def _load(self) -> None:
        candidates: List[Path] = []
        main = self.root / PY_MAIN_FILE
        if main.exists():
            candidates.append(main)
        pkg = self.root / PY_PACKAGE_DIR
        if pkg.exists():
            candidates.extend(sorted(pkg.glob("*.py")))
        for path in candidates:
            src = path.read_text(encoding="utf-8")
            self._sources[path.name] = src
            try:
                self._trees[path.name] = ast.parse(src)
            except SyntaxError:
                pass

    @property
    def source_files(self) -> List[str]:
        return list(self._sources.keys())

    def class_names(self) -> Set[str]:
        names: Set[str] = set()
        for tree in self._trees.values():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    names.add(node.name)
        return names

    def top_level_function_names(self) -> Set[str]:
        """Return module-level function names (not methods)."""
        names: Set[str] = set()
        for tree in self._trees.values():
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(node.name)
        return names

    def config_attr_names(self) -> Set[str]:
        """Return field names of the Config dataclass."""
        attrs: Set[str] = set()
        for tree in self._trees.values():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "Config":
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(
                            item.target, ast.Name
                        ):
                            attrs.add(item.target.id)
        return attrs

    def module_filenames(self) -> Set[str]:
        """Return *.py filenames present in the entelgia/ package."""
        pkg = self.root / PY_PACKAGE_DIR
        if not pkg.exists():
            return set()
        return {
            p.name
            for p in pkg.glob("*.py")
            if p.name != "__init__.py"
        }

    def all_project_py_filenames(self) -> Set[str]:
        """Return all *.py filenames anywhere in the project (for doc cross-check)."""
        names: Set[str] = set()
        for p in self.root.rglob("*.py"):
            # Skip hidden dirs and common non-project dirs
            parts = p.parts
            if any(part.startswith(".") or part in ("__pycache__",) for part in parts):
                continue
            names.add(p.name)
        return names

    def all_combined_text(self) -> str:
        return "\n".join(self._sources.values())


# ---------------------------------------------------------------------------
# Comparator
# ---------------------------------------------------------------------------

class ImplementationComparator:
    """Cross-compares code symbols with markdown documentation."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.extractor = MarkdownExtractor(root, MARKDOWN_FILES)
        self.inspector = CodeInspector(root)

    # ------------------------------------------------------------------
    # Individual category checks
    # ------------------------------------------------------------------

    def compare_classes(self) -> ComparisonResult:
        result = ComparisonResult(category="Classes")
        code_classes = self.inspector.class_names() - INTERNAL_CLASSES
        doc_ids = self.extractor.identifiers()

        for cls in sorted(code_classes):
            if not self.extractor.contains(cls):
                result.in_code_not_docs.append(f"class {cls}")

        # Documented identifiers (backtick-quoted, CamelCase) that do NOT appear in code
        code_all = self.inspector.class_names()
        # Exclude known Python builtins and common non-class tokens
        builtin_names: Set[str] = {
            "True", "False", "None", "ValueError", "TypeError", "KeyError",
            "IndexError", "AttributeError", "RuntimeError", "Exception",
            "NotImplementedError", "StopIteration", "OSError", "IOError",
            "LICENSE",  # file name, not a class
        }
        for token in sorted(doc_ids):
            # Only consider CamelCase tokens that look like class names
            if not re.match(r"^[A-Z][A-Za-z0-9]+$", token):
                continue
            if token in builtin_names:
                continue
            # Accept if exact name exists, or if any code class starts with the token
            # (e.g., "Memory" matches "MemoryCore", "Emotion" matches "EmotionCore")
            if not any(
                cls == token or cls.startswith(token)
                for cls in code_all
            ):
                result.in_docs_not_code.append(f"class {token}")

        return result

    def compare_config_attrs(self) -> ComparisonResult:
        result = ComparisonResult(category="Config Parameters")
        code_attrs = self.inspector.config_attr_names()
        raw_md = self.extractor.raw_text()

        for attr in sorted(code_attrs):
            if attr not in raw_md:
                result.in_code_not_docs.append(f"Config.{attr}")

        return result

    def compare_module_files(self) -> ComparisonResult:
        result = ComparisonResult(category="Module Files (entelgia/)")
        code_files = self.inspector.module_filenames()
        doc_files = self.extractor.py_filenames()
        all_project_files = self.inspector.all_project_py_filenames()

        for fname in sorted(code_files):
            if not self.extractor.contains(fname):
                result.in_code_not_docs.append(fname)

        for fname in sorted(doc_files):
            # Only flag .py files that are neither in the package nor anywhere in the project
            if fname not in code_files and fname not in all_project_files:
                result.in_docs_not_code.append(fname)

        return result

    def compare_key_functions(self) -> ComparisonResult:
        """Check that important public functions are mentioned in docs."""
        result = ComparisonResult(category="Key Public Functions")
        code_funcs = self.inspector.top_level_function_names() - INTERNAL_FUNCTIONS
        raw_md = self.extractor.raw_text()

        for fn in sorted(code_funcs):
            if fn.startswith("_"):
                continue  # skip private functions
            if fn not in raw_md:
                result.in_code_not_docs.append(f"def {fn}()")

        return result

    # ------------------------------------------------------------------
    # Full run
    # ------------------------------------------------------------------

    def run(self) -> List[ComparisonResult]:
        return [
            self.compare_classes(),
            self.compare_config_attrs(),
            self.compare_module_files(),
            self.compare_key_functions(),
        ]


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def _print_result(result: ComparisonResult) -> None:
    status = "✅" if result.ok else "⚠️ "
    print(f"\n{status} {result.category}")

    if result.in_code_not_docs:
        print(f"   In code but NOT documented ({len(result.in_code_not_docs)}):")
        for item in result.in_code_not_docs:
            print(f"      • {item}")

    if result.in_docs_not_code:
        print(f"   In docs but NOT found in code ({len(result.in_docs_not_code)}):")
        for item in result.in_docs_not_code:
            print(f"      • {item}")

    if result.ok:
        print("   All items accounted for.")


def _print_summary(results: List[ComparisonResult], md_files: List[str]) -> int:
    """Print overall summary and return exit code (0 = clean, 1 = issues)."""
    total_missing_docs = sum(len(r.in_code_not_docs) for r in results)
    total_stale = sum(len(r.in_docs_not_code) for r in results)
    total_issues = total_missing_docs + total_stale

    print("\n" + "=" * 70)
    print("IMPLEMENTATION vs. DOCUMENTATION — SUMMARY")
    print(f"   Markdown files scanned : {', '.join(md_files)}")
    print(f"   Categories checked     : {len(results)}")
    print(f"   Missing documentation  : {total_missing_docs} item(s)")
    print(f"   Stale doc references   : {total_stale} item(s)")
    print(f"   Total issues           : {total_issues}")
    print("=" * 70)

    if total_issues == 0:
        print("\n✅  PASS — Code and documentation are fully in sync.\n")
        return 0
    else:
        suffix = "y" if total_issues == 1 else "ies"
        print(f"\n⚠️   ISSUES FOUND — {total_issues} discrepanc{suffix} between code and docs.\n")
        return 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    root = Path(__file__).parent.parent

    print("\n" + "=" * 70)
    print("ENTELGIA — Implementation vs. Documentation Validator")
    print("   Compares Python source code against project markdown files")
    print("=" * 70)

    comparator = ImplementationComparator(root)

    print(
        f"\nMarkdown files : {', '.join(comparator.extractor.files_found) or '(none found)'}"
    )
    print(
        f"Python sources : {', '.join(comparator.inspector.source_files) or '(none found)'}"
    )

    results = comparator.run()

    for result in results:
        _print_result(result)

    return _print_summary(results, comparator.extractor.files_found)


if __name__ == "__main__":
    sys.exit(main())
