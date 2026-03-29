#!/usr/bin/env python3
"""Coverage gate script.

Runs pytest with coverage and exits with a non-zero code if coverage is below
the required threshold (80%).  Used by the pre-push git hook.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

THRESHOLD = 80
PROJECT_ROOT = Path(__file__).parent.parent


def main() -> int:
    print("Running coverage check …")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov=agents",
            "--cov=common",
            "--cov=integrator",
            "--cov-report=term-missing",
            f"--cov-fail-under={THRESHOLD}",
            "-q",
        ],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        print(
            f"\n\033[91m[COVERAGE GATE] Push blocked: coverage is below {THRESHOLD}%.\033[0m",
            file=sys.stderr,
        )
        print(
            "Fix failing tests or increase coverage before pushing.",
            file=sys.stderr,
        )
        return 1
    print(f"\033[92m[COVERAGE GATE] Coverage OK (>= {THRESHOLD}%). Push allowed.\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
