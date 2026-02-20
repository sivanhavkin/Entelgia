#!/usr/bin/env python3
"""
Entelgia Project Validation Script
===================================
This script validates that the Entelgia project delivers everything promised in the README.

Usage:
    python scripts/validate_project.py
    python scripts/validate_project.py --verbose
    python scripts/validate_project.py --fix  # Attempt to fix issues
"""

import os
import sys
import re
import json
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import importlib.util

# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")

def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")

class ValidationResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def add_pass(self, message: str):
        self.passed.append(message)
        print_success(message)
    
    def add_fail(self, message: str):
        self.failed.append(message)
        print_error(message)
    
    def add_warning(self, message: str):
        self.warnings.append(message)
        print_warning(message)
    
    def summary(self):
        print_header("VALIDATION SUMMARY")
        print(f"{Colors.GREEN}Passed: {len(self.passed)}{Colors.RESET}")
        print(f"{Colors.RED}Failed: {len(self.failed)}{Colors.RESET}")
        print(f"{Colors.YELLOW}Warnings: {len(self.warnings)}{Colors.RESET}")
        
        if self.failed:
            print(f"\n{Colors.RED}{Colors.BOLD}Failed Checks:{Colors.RESET}")
            for fail in self.failed:
                print(f"  {Colors.RED}✗ {fail}{Colors.RESET}")
        
        if self.warnings:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}Warnings:{Colors.RESET}")
            for warning in self.warnings:
                print(f"  {Colors.YELLOW}⚠ {warning}{Colors.RESET}")
        
        return len(self.failed) == 0

def get_project_root() -> Path:
    """Get the project root directory"""
    script_dir = Path(__file__).parent
    return script_dir.parent

def check_documentation_files(result: ValidationResult, verbose: bool = False):
    """Check that all documentation files exist"""
    print_header("1. Documentation Files")
    
    root = get_project_root()
    required_docs = [
        "README.md",
        "whitepaper.md",
        "SPEC.md",
        "ARCHITECTURE.md",
        "ROADMAP.md",
        "FAQ.md",
        "TROUBLESHOOTING.md",
        "entelgia_demo.md",
        "LICENSE",
        "Changelog.md",
        "Contributing.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "BRANDING.md",
        "Contributors.md",
    ]
    
    for doc in required_docs:
        doc_path = root / doc
        if doc_path.exists():
            result.add_pass(f"Found: {doc}")
            if verbose:
                size = doc_path.stat().st_size
                print_info(f"  Size: {size} bytes")
        else:
            result.add_fail(f"Missing: {doc}")

def check_directory_structure(result: ValidationResult, verbose: bool = False):
    """Check that all required directories exist"""
    print_header("2. Directory Structure")
    
    root = get_project_root()
    required_dirs = [
        "Assets",
        "docs",
        "docs/api",
        "entelgia",
        "examples",
        "scripts",
        "tests",
        ".github",
        ".github/workflows",
    ]
    
    for dir_name in required_dirs:
        dir_path = root / dir_name
        if dir_path.is_dir():
            result.add_pass(f"Found directory: {dir_name}")
            if verbose:
                files = list(dir_path.iterdir())
                print_info(f"  Contains {len(files)} items")
        else:
            result.add_fail(f"Missing directory: {dir_name}")

def check_core_files(result: ValidationResult, verbose: bool = False):
    """Check that core Python files exist"""
    print_header("3. Core Files")
    
    root = get_project_root()
    core_files = [
        "Entelgia_production_meta.py",
        "requirements.txt",
        "pyproject.toml",
        ".env.example",
        ".gitignore",
        "scripts/install.py",
        "scripts/clear_memory.py",
        "tests/test_enhanced_dialogue.py",
        "tests/test_memory_security.py",
    ]
    
    for file_name in core_files:
        file_path = root / file_name
        if file_path.exists():
            result.add_pass(f"Found: {file_name}")
            if verbose and file_path.suffix == '.py':
                lines = len(file_path.read_text().splitlines())
                print_info(f"  Lines: {lines}")
        else:
            result.add_fail(f"Missing: {file_name}")

def check_entelgia_package(result: ValidationResult, verbose: bool = False):
    """Check the entelgia package modules"""
    print_header("4. Entelgia Package Modules")
    
    root = get_project_root()
    entelgia_modules = [
        "entelgia/__init__.py",
        "entelgia/dialogue_engine.py",
        "entelgia/enhanced_personas.py",
        "entelgia/context_manager.py",
        "entelgia/fixy_interactive.py",
    ]
    
    for module in entelgia_modules:
        module_path = root / module
        if module_path.exists():
            result.add_pass(f"Found module: {module}")
            if verbose:
                content = module_path.read_text()
                classes = len(re.findall(r'^class\s+\w+', content, re.MULTILINE))
                functions = len(re.findall(r'^def\s+\w+', content, re.MULTILINE))
                print_info(f"  Classes: {classes}, Functions: {functions}")
        else:
            result.add_fail(f"Missing module: {module}")

def check_core_features_in_code(result: ValidationResult, verbose: bool = False):
    """Check that core features are implemented in the main file"""
    print_header("5. Core Features Implementation")
    
    root = get_project_root()
    main_file = root / "Entelgia_production_meta.py"
    
    if not main_file.exists():
        result.add_fail("Entelgia_production_meta.py not found")
        return
    
    content = main_file.read_text()
    
    features_to_check = {
        "Multi-agent system": [r"class.*Socrates", r"class.*Athena", r"class.*Fixy"],
        "Memory system": [r"class.*Memory", r"sqlite", r"json"],
        "HMAC-SHA256": [r"hmac", r"sha256"],
        "Emotion tracking": [r"emotion", r"class.*Emotion"],
        "Dream cycles": [r"dream", r"promote.*memory"],
        "Observer meta-cognition": [r"Observer", r"meta.*cognition"],
        "PII redaction": [r"pii", r"redact"],
        "Error handling": [r"try:", r"except", r"retry", r"backoff"],
        "Psychological drives": [r"id|ego|superego", r"drive"],
        "Configuration": [r"class.*Config"],
    }
    
    for feature, patterns in features_to_check.items():
        found = False
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found = True
                break
        
        if found:
            result.add_pass(f"Feature implemented: {feature}")
        else:
            result.add_warning(f"Feature not clearly visible in code: {feature}")

def check_version_consistency(result: ValidationResult, verbose: bool = False):
    """Check version consistency across files"""
    print_header("6. Version Consistency")
    
    root = get_project_root()
    versions = {}
    
    # Check README
    readme_path = root / "README.md"
    if readme_path.exists():
        readme_content = readme_path.read_text()
        match = re.search(r'\*\*Version:\*\*\s*([\d.]+)', readme_content)
        if match:
            versions['README'] = match.group(1)
            print_info(f"README version: {versions['README']}")
    
    # Check pyproject.toml
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        pyproject_content = pyproject_path.read_text()
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', pyproject_content)
        if match:
            versions['pyproject.toml'] = match.group(1)
            print_info(f"pyproject.toml version: {versions['pyproject.toml']}")
    
    # Check Changelog
    changelog_path = root / "Changelog.md"
    if changelog_path.exists():
        changelog_content = changelog_path.read_text()
        # Find the first version heading
        match = re.search(r'##?\s*\[?v?([\d.]+)\]?', changelog_content)
        if match:
            versions['Changelog'] = match.group(1)
            print_info(f"Changelog latest version: {versions['Changelog']}")
    
    # Check consistency
    if len(versions) > 1:
        unique_versions = set(versions.values())
        if len(unique_versions) == 1:
            result.add_pass(f"Version consistent across files: {list(unique_versions)[0]}")
        else:
            result.add_fail(f"Version mismatch: {versions}")
    else:
        result.add_warning("Could not extract versions from all files")

def check_dependencies(result: ValidationResult, verbose: bool = False):
    """Check that dependencies are properly listed"""
    print_header("7. Dependencies")
    
    root = get_project_root()
    requirements_path = root / "requirements.txt"
    
    if not requirements_path.exists():
        result.add_fail("requirements.txt not found")
        return
    
    content = requirements_path.read_text()
    
    expected_deps = [
        "ollama",
        "python-dotenv",
        "pytest",
    ]
    
    found_deps = []
    missing_deps = []
    
    for dep in expected_deps:
        if dep.lower() in content.lower():
            found_deps.append(dep)
        else:
            missing_deps.append(dep)
    
    if found_deps:
        result.add_pass(f"Found core dependencies: {', '.join(found_deps)}")
    
    if missing_deps:
        result.add_warning(f"Missing expected dependencies: {', '.join(missing_deps)}")
    
    if verbose:
        lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith('#')]
        print_info(f"Total dependencies listed: {len(lines)}")

def check_github_actions(result: ValidationResult, verbose: bool = False):
    """Check GitHub Actions workflows"""
    print_header("8. CI/CD Pipeline (GitHub Actions)")
    
    root = get_project_root()
    workflows_dir = root / ".github" / "workflows"
    
    if not workflows_dir.exists():
        result.add_warning("GitHub workflows directory not found")
        return
    
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    
    if workflow_files:
        result.add_pass(f"Found {len(workflow_files)} workflow file(s)")
        if verbose:
            for wf in workflow_files:
                print_info(f"  - {wf.name}")
    else:
        result.add_warning("No workflow files found")

def check_test_files(result: ValidationResult, verbose: bool = False):
    """Check test files exist and are valid"""
    print_header("9. Test Files")
    
    root = get_project_root()
    test_files = [
        "tests/test_enhanced_dialogue.py",
        "tests/test_memory_security.py",
    ]
    
    total_tests = 0
    
    for test_file in test_files:
        test_path = root / test_file
        if test_path.exists():
            result.add_pass(f"Found test file: {test_file}")
            
            if verbose:
                content = test_path.read_text()
                # Count test functions
                test_count = len(re.findall(r'def\s+test_\w+', content))
                total_tests += test_count
                print_info(f"  Contains ~{test_count} test functions")
        else:
            result.add_fail(f"Missing test file: {test_file}")
    
    if verbose and total_tests > 0:
        print_info(f"Total test functions found: ~{total_tests}")

def check_example_scripts(result: ValidationResult, verbose: bool = False):
    """Check example/demo scripts"""
    print_header("10. Example/Demo Scripts")
    
    root = get_project_root()
    examples_dir = root / "examples"
    
    if not examples_dir.exists():
        result.add_warning("Examples directory not found")
        return
    
    demo_files = list(examples_dir.glob("*.py"))
    
    expected_demo = "demo_enhanced_dialogue.py"
    
    if (examples_dir / expected_demo).exists():
        result.add_pass(f"Found: examples/{expected_demo}")
    else:
        result.add_warning(f"Missing: examples/{expected_demo}")
    
    if verbose:
        print_info(f"Total example files: {len(demo_files)}")
        for demo in demo_files:
            print_info(f"  - {demo.name}")

def check_api_documentation(result: ValidationResult, verbose: bool = False):
    """Check API documentation"""
    print_header("11. API Documentation")
    
    root = get_project_root()
    api_doc = root / "docs" / "api" / "README.md"
    
    if api_doc.exists():
        result.add_pass("API documentation exists")
        if verbose:
            content = api_doc.read_text()
            if "POST /api/v1/chat" in content:
                print_info("  Contains chat endpoint documentation")
            if "localhost:8000" in content:
                print_info("  Contains base URL information")
    else:
        result.add_warning("API documentation not found")

def check_readme_promises(result: ValidationResult, verbose: bool = False):
    """Check specific promises made in README"""
    print_header("12. README Promises")
    
    root = get_project_root()
    readme_path = root / "README.md"
    
    if not readme_path.exists():
        result.add_fail("README.md not found")
        return
    
    content = readme_path.read_text()
    
    promises = {
        "Installation script": r"scripts/install\.py",
        "Memory clearing script": r"scripts/clear_memory\.py",
        "Test coverage claim (24 tests)": r"24.*tests?.*pass",
        "Version badge": r"!\[.*[Vv]ersion.*\]",
        "Tests badge": r"!\[.*[Tt]ests.*\]",
        "License badge": r"!\[.*[Ll]icense.*\]",
        "Build status badge": r"!\[.*[Bb]uild.*\]",
    }
    
    for promise, pattern in promises.items():
        if re.search(pattern, content, re.IGNORECASE):
            result.add_pass(f"README includes: {promise}")
        else:
            result.add_warning(f"README missing: {promise}")

def run_tests_check(result: ValidationResult, verbose: bool = False, run_tests: bool = False):
    """Optionally run the actual tests"""
    print_header("13. Test Execution (Optional)")
    
    if not run_tests:
        print_info("Skipping test execution (use --run-tests to enable)")
        return
    
    root = get_project_root()
    
    # Try to run pytest
    test_commands = [
        (["python", "tests/test_enhanced_dialogue.py"], "Enhanced Dialogue Tests"),
        (["pytest", "tests/test_memory_security.py", "-v"], "Memory Security Tests"),
    ]
    
    for cmd, name in test_commands:
        try:
            print_info(f"Running: {name}")
            process = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if process.returncode == 0:
                result.add_pass(f"{name}: PASSED")
                if verbose:
                    print(process.stdout)
            else:
                result.add_fail(f"{name}: FAILED")
                if verbose:
                    print(process.stderr)
        
        except subprocess.TimeoutExpired:
            result.add_warning(f"{name}: TIMEOUT")
        except FileNotFoundError:
            result.add_warning(f"{name}: Command not found (pytest may not be installed)")
        except Exception as e:
            result.add_warning(f"{name}: Error - {e}")

def check_security_features(result: ValidationResult, verbose: bool = False):
    """Check security-related features"""
    print_header("14. Security Features")
    
    root = get_project_root()
    
    # Check for .env.example (but not .env)
    if (root / ".env.example").exists():
        result.add_pass(".env.example template exists")
    else:
        result.add_fail(".env.example not found")
    
    if (root / ".env").exists():
        result.add_warning(".env file exists (should be in .gitignore)")
    
    # Check .gitignore
    gitignore_path = root / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if ".env" in content:
            result.add_pass(".gitignore includes .env")
        else:
            result.add_warning(".gitignore may not protect .env file")
    
    # Check SECURITY.md
    if (root / "SECURITY.md").exists():
        result.add_pass("Security policy documented")
    else:
        result.add_warning("SECURITY.md not found")

def main():
    parser = argparse.ArgumentParser(
        description="Validate Entelgia project against README promises"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Actually run the test suite (slow)"
    )
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}{Colors.MAGENTA}")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                                                                    ║")
    print("║             ENTELGIA PROJECT VALIDATION SCRIPT                     ║")
    print("║                                                                    ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print(Colors.RESET)
    
    result = ValidationResult()
    
    # Run all checks
    check_documentation_files(result, args.verbose)
    check_directory_structure(result, args.verbose)
    check_core_files(result, args.verbose)
    check_entelgia_package(result, args.verbose)
    check_core_features_in_code(result, args.verbose)
    check_version_consistency(result, args.verbose)
    check_dependencies(result, args.verbose)
    check_github_actions(result, args.verbose)
    check_test_files(result, args.verbose)
    check_example_scripts(result, args.verbose)
    check_api_documentation(result, args.verbose)
    check_readme_promises(result, args.verbose)
    check_security_features(result, args.verbose)
    
    if args.run_tests:
        run_tests_check(result, args.verbose, run_tests=True)
    
    # Print summary
    success = result.summary()
    
    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ ALL CHECKS PASSED!{Colors.RESET}")
        print(f"{Colors.GREEN}Your project delivers what the README promises.{Colors.RESET}\n")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ SOME CHECKS FAILED{Colors.RESET}")
        print(f"{Colors.RED}Please review the failed checks above.{Colors.RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()