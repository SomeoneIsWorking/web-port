#!/usr/bin/env python3
"""Verify the shared browser tooling separately from its shipping builder."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    temporary = ROOT / "scratch/tool-tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, TMPDIR=str(temporary))
    for source in sorted((ROOT / "tools").glob("*.py")):
        lines = len(source.read_text().splitlines())
        if lines > 500:
            raise ValueError(f"{source.relative_to(ROOT)}: {lines} lines exceeds 500-line source cap")
    for command in ([sys.executable, "-m", "ruff", "check", "tools", "tests"],
                    [sys.executable, "-m", "pytest", "-q", "tests"]):
        subprocess.run(command, cwd=ROOT, env=environment, check=True)


if __name__ == "__main__":
    main()
