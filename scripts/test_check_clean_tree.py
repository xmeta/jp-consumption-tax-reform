#!/usr/bin/env python3
"""Regression tests for scripts/check_clean_tree.py."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check_clean_tree.py"


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def check(root: Path, expected_ok: bool, expected_fragment: str | None = None) -> None:
    result = run(sys.executable, str(CHECKER), "--root", str(root))
    if expected_ok:
        if result.returncode != 0:
            raise RuntimeError(f"clean-tree checker unexpectedly failed: {result.stderr}")
    else:
        if result.returncode == 0:
            raise RuntimeError("clean-tree checker unexpectedly succeeded")
        if expected_fragment and expected_fragment not in result.stderr:
            raise RuntimeError(
                f"missing dirty entry {expected_fragment!r}: {result.stderr!r}"
            )


with tempfile.TemporaryDirectory(prefix="jp-tax-clean-tree-") as tmp:
    repo = Path(tmp)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text("ignored.tmp\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "tracked.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=clean-tree-test",
            "-c",
            "user.email=clean-tree-test@example.invalid",
            "commit",
            "-qm",
            "baseline",
        ],
        check=True,
    )

    check(repo, True)

    (repo / "unexpected.tmp").write_text("unexpected\n", encoding="utf-8")
    check(repo, False, "?? unexpected.tmp")
    (repo / "unexpected.tmp").unlink()

    (repo / "tracked.txt").write_text("modified\n", encoding="utf-8")
    check(repo, False, " M tracked.txt")
    subprocess.run(["git", "-C", str(repo), "checkout", "--", "tracked.txt"], check=True)

    (repo / "tracked.txt").unlink()
    check(repo, False, " D tracked.txt")
    subprocess.run(["git", "-C", str(repo), "checkout", "--", "tracked.txt"], check=True)

    (repo / "ignored.tmp").write_text("ignored\n", encoding="utf-8")
    check(repo, True)

print("clean-tree checker tests: OK (untracked, modified, deleted, ignored)")
