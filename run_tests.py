#!/usr/bin/env python3
"""
Test runner script for Broadcast Board Tracker.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py --no-gui     # Skip GUI tests
    python run_tests.py -k keyword   # Run tests matching keyword
    python run_tests.py tests/test_app.py  # Run specific test file
"""

import sys
import subprocess
from pathlib import Path


def run_tests(args=None, no_gui=False):
    """Run pytest with the given arguments."""
    project_root = Path(__file__).parent
    test_dir = project_root / "tests"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_dir),
        "-v",
    ]

    if no_gui:
        cmd.append("--no-gui")

    if args:
        cmd.extend(args)

    print(f"Running: {' '.join(cmd)}")
    print("-" * 80)

    result = subprocess.run(cmd, cwd=project_root)

    print("-" * 80)
    if result.returncode == 0:
        print("✓ All tests passed!")
    else:
        print(f"✗ Tests failed with exit code {result.returncode}")

    return result.returncode


def main():
    """Main entry point."""
    args = sys.argv[1:]
    no_gui = "--no-gui" in args

    if no_gui:
        args = [a for a in args if a != "--no-gui"]

    return run_tests(args, no_gui)


if __name__ == "__main__":
    sys.exit(main())
