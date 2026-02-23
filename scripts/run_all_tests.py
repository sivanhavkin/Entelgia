#!/usr/bin/env python3
"""
Entelgia – Run All Tests
========================
A single script that discovers and runs every test in the ``tests/``
directory using pytest.

Usage (from the repository root)::

    python scripts/run_all_tests.py

Optional pytest arguments can be passed directly::

    python scripts/run_all_tests.py -v --tb=short

Exit codes mirror pytest:
    0  – all tests passed
    1  – one or more tests failed (or collection error)
"""

import sys
import subprocess
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    tests_dir = repo_root / "tests"

    if not tests_dir.exists():
        print(f"Error: tests directory not found at {tests_dir}")
        sys.exit(1)

    cmd = [sys.executable, "-m", "pytest", str(tests_dir)] + sys.argv[1:]

    print("=" * 60)
    print("  Entelgia – Running All Tests")
    print("=" * 60)
    print(f"Command: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=str(repo_root))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
