#!/usr/bin/env python3
"""A safe, dependency-free diagnostic for a Python server.

This script does not connect to the internet, access credentials, or modify
project files. It checks the Python runtime, standard-library imports, and
temporary-file read/write permissions.
"""

import os
import platform
import sys
import tempfile
from pathlib import Path


def main() -> int:
    print("=== Python server diagnostic ===")
    print(f"Python version : {sys.version.split()[0]}")
    print(f"Executable     : {sys.executable}")
    print(f"Operating system: {platform.platform()}")
    print(f"Current folder : {Path.cwd()}")
    print(f"Python version supported by this script: {sys.version_info >= (3, 8)}")

    if sys.version_info < (3, 8):
        print("FAIL: Python 3.8 or newer is required.")
        return 1

    print("\nChecking standard-library imports...")
    try:
        import json  # noqa: F401
        import pathlib  # noqa: F401
        import tempfile as tempfile_module  # noqa: F401
        print("PASS: standard-library imports are available.")
    except Exception as exc:
        print(f"FAIL: standard-library import failed: {type(exc).__name__}: {exc}")
        return 1

    print("\nChecking temporary-file write/read/delete...")
    try:
        with tempfile.TemporaryDirectory(prefix="python_server_test_") as temp_dir:
            test_file = Path(temp_dir) / "diagnostic_test.txt"
            expected = "python-server-diagnostic-ok"
            test_file.write_text(expected, encoding="utf-8")
            actual = test_file.read_text(encoding="utf-8")
            if actual != expected:
                print("FAIL: text read back from the temporary file did not match.")
                return 1
            print("PASS: temporary file was written and read correctly.")
        print("PASS: temporary test directory was cleaned up.")
    except Exception as exc:
        print(f"FAIL: temporary-file operation failed: {type(exc).__name__}: {exc}")
        return 1

    print("\nRESULT: PASS — basic Python runtime and local file operations work.")
    print("This test does not verify network access, exchange APIs, or trading logic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
