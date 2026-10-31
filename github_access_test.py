#!/usr/bin/env python3
"""Safe Python and GitHub HTTPS connectivity diagnostic.

No credentials or API tokens are used. This script does not access private
repository contents, modify project files, or contact cryptocurrency services.
"""

import platform
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

URLS = (
    ("GitHub website", "https://github.com/"),
    ("GitHub API public rate-limit endpoint", "https://api.github.com/rate_limit"),
)


def check_https(label: str, url: str) -> bool:
    print(f"\nChecking HTTPS: {label}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "safe-github-connectivity-test/1.0"},
        method="GET",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            status = response.status
            elapsed = time.monotonic() - started
            response.read(128)
            print(f"PASS: HTTPS request succeeded (HTTP {status}, {elapsed:.2f}s).")
            return 200 <= status < 400
    except urllib.error.HTTPError as exc:
        elapsed = time.monotonic() - started
        print(f"FAIL: HTTP error {exc.code} after {elapsed:.2f}s.")
    except Exception as exc:
        elapsed = time.monotonic() - started
        print(f"FAIL: {type(exc).__name__} after {elapsed:.2f}s: {exc}")
    return False


def main() -> int:
    print("=== Python + GitHub HTTPS diagnostic (v2) ===")
    print(f"Python version : {sys.version.split()[0]}")
    print(f"Executable     : {sys.executable}")
    print(f"Operating system: {platform.platform()}")
    print(f"Current folder : {Path.cwd()}")

    if sys.version_info < (3, 8):
        print("FAIL: Python 3.8 or newer is required.")
        return 1
    print("PASS: supported Python version.")

    try:
        import json  # noqa: F401
        import pathlib  # noqa: F401
        import urllib.request  # noqa: F401
        print("PASS: standard-library imports are available.")
    except Exception as exc:
        print(f"FAIL: standard-library import: {type(exc).__name__}: {exc}")
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="python_server_test_") as temp_dir:
            test_file = Path(temp_dir) / "diagnostic_test.txt"
            test_file.write_text("python-server-diagnostic-ok", encoding="utf-8")
            if test_file.read_text(encoding="utf-8") != "python-server-diagnostic-ok":
                print("FAIL: temporary-file read-back did not match.")
                return 1
        print("PASS: temporary-file write/read/cleanup.")
    except Exception as exc:
        print(f"FAIL: temporary-file operation: {type(exc).__name__}: {exc}")
        return 1

    network_results = [check_https(label, url) for label, url in URLS]

    print("\n=== Summary ===")
    if all(network_results):
        print("RESULT: PASS — Python basics and HTTPS access to GitHub work.")
        print("Note: this does not test authenticated access to private repositories.")
        return 0

    print("RESULT: PARTIAL/FAIL — Python basics passed, but one or more GitHub HTTPS checks failed.")
    print("Send the complete output for troubleshooting. Do not send passwords or tokens.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
