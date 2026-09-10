#!/usr/bin/env python3
"""Fail if a Git worktree contains tracked or unexpected untracked changes."""
from pathlib import Path
import argparse
import subprocess
import sys

DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def dirty_entries(root: Path) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignored=no",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    entries = dirty_entries(root)
    if entries:
        print("ERROR: repository working tree is not clean", file=sys.stderr)
        for entry in entries:
            print(f"ERROR: {entry}", file=sys.stderr)
        raise SystemExit(1)
    print("repository clean-tree validation: OK")


if __name__ == "__main__":
    main()
