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

import platform
import sys
import subprocess
from pathlib import Path


def _fix_pyreadline_windows() -> None:
    """Replace the broken ``pyreadline`` package with ``pyreadline3`` on Windows.

    ``pyreadline`` (unmaintained) uses ``collections.Callable`` which was
    removed in Python 3.10, causing pytest to crash during startup on Windows
    when it tries the readline workaround.  ``pyreadline3`` is the maintained
    fork that supports Python 3.10+.
    """
    if platform.system() != "Windows":
        return
    check = subprocess.run(
        [sys.executable, "-m", "pip", "show", "pyreadline"],
        capture_output=True,
    )
    if check.returncode != 0:
        # returncode 1 means the package is not installed – nothing to do.
        # Any other value (e.g. pip unavailable) is also safely skipped here,
        # because without pyreadline the readline crash cannot occur.
        return
    print("Replacing incompatible 'pyreadline' with 'pyreadline3' for Python 3.10+ …")
    uninstall = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "pyreadline", "-y", "-q"],
    )
    if uninstall.returncode != 0:
        print("Warning: failed to uninstall pyreadline; continuing anyway.")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyreadline3", "-q"],
    )
    if result.returncode != 0:
        print("Warning: failed to install pyreadline3.")


def _install_requirements(repo_root: Path) -> None:
    """Install project dependencies so imports work during test collection."""
    _fix_pyreadline_windows()
    req_file = repo_root / "requirements.txt"
    if req_file.exists():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"],
            cwd=str(repo_root),
        )
        if result.returncode != 0:
            print("Warning: failed to install requirements.txt dependencies.")
    # Install dev extras (pytest-cov etc.) defined in pyproject.toml
    if (repo_root / "pyproject.toml").exists():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".[dev]", "-q"],
            cwd=str(repo_root),
        )
        if result.returncode != 0:
            print("Warning: failed to install dev extras from pyproject.toml.")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    tests_dir = repo_root / "tests"

    if not tests_dir.exists():
        print(f"Error: tests directory not found at {tests_dir}")
        sys.exit(1)

    print("=" * 60)
    print("  Entelgia – Running All Tests")
    print("=" * 60)

    _install_requirements(repo_root)

    cmd = [sys.executable, "-m", "pytest", str(tests_dir)] + sys.argv[1:]
    print(f"Command: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=str(repo_root))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
