#!/usr/bin/env python3
from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

if not __debug__:
    raise RuntimeError("scientific-state regression tests require non-optimized Python")

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/validate_scientific_state.py"
FIELDS = [
    "component_id",
    "module_path",
    "display_name",
    "status",
    "phase",
    "maturity",
    "causal_status",
    "policy_usable",
    "evidence_paths",
    "output_paths",
    "blockers",
    "supersedes",
    "superseded_by",
    "active",
]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir()
    (root / "research/a").mkdir(parents=True)
    (root / "research/b").mkdir(parents=True)
    (root / "research/a/README.adoc").write_text("STATUS_A\n", encoding="utf-8")
    (root / "research/b/README.adoc").write_text("STATUS_B\n", encoding="utf-8")
    (root / "research/a/run.py").write_text("print('a')\n", encoding="utf-8")
    (root / "research/b/run.py").write_text("print('b')\n", encoding="utf-8")
    (root / "evidence-a.txt").write_text("a\n", encoding="utf-8")
    (root / "evidence-b.txt").write_text("b\n", encoding="utf-8")
    (root / "output-a.txt").write_text("a\n", encoding="utf-8")
    (root / "output-b.txt").write_text("b\n", encoding="utf-8")
    (root / "STATUS.adoc").write_text("STATUS_A\nSTATUS_B\n", encoding="utf-8")
    rows = [
        {
            "component_id": "a",
            "module_path": "research/a",
            "display_name": "A",
            "status": "STATUS_A",
            "phase": "PHASE1_COMPLETE",
            "maturity": "SENSITIVITY_ONLY",
            "causal_status": "NOT_CAUSAL",
            "policy_usable": "false",
            "evidence_paths": "evidence-a.txt",
            "output_paths": "output-a.txt",
            "blockers": "latent link missing",
            "supersedes": "",
            "superseded_by": "",
            "active": "true",
        },
        {
            "component_id": "b",
            "module_path": "research/b",
            "display_name": "B",
            "status": "STATUS_B",
            "phase": "PHASE2_ACTIVE",
            "maturity": "PARTIALLY_IDENTIFIED",
            "causal_status": "DESCRIPTIVE_ONLY",
            "policy_usable": "false",
            "evidence_paths": "evidence-b.txt",
            "output_paths": "output-b.txt",
            "blockers": "counterfactual missing",
            "supersedes": "",
            "superseded_by": "",
            "active": "true",
        },
    ]
    with (root / "data/scientific_state.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def mutate_csv(root: Path, fn) -> None:
    path = root / "data/scientific_state.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fn(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


with tempfile.TemporaryDirectory() as tmp:
    fixture = Path(tmp)
    write_fixture(fixture)

    valid = run_validator(fixture)
    check(valid.returncode == 0, f"valid fixture failed:\n{valid.stdout}{valid.stderr}")

    mutate_csv(fixture, lambda rows: rows.__setitem__(1, {**rows[1], "component_id": "a"}))
    duplicate = run_validator(fixture)
    check(duplicate.returncode != 0, "duplicate component_id unexpectedly passed")
    check("duplicate component_id" in duplicate.stdout, "duplicate diagnostic missing")

    write_fixture(fixture := Path(tmp) / "conflict")
    mutate_csv(fixture, lambda rows: rows[1].__setitem__("module_path", "research/a"))
    conflict = run_validator(fixture)
    check(conflict.returncode != 0, "conflicting module state unexpectedly passed")
    check(
        "duplicate active module_path" in conflict.stdout,
        "conflicting module-state diagnostic missing",
    )

    write_fixture(fixture := Path(tmp) / "coverage")
    mutate_csv(fixture, lambda rows: rows.pop())
    coverage = run_validator(fixture)
    check(coverage.returncode != 0, "missing active module unexpectedly passed")
    check("active module coverage mismatch" in coverage.stdout, "coverage diagnostic missing")

    write_fixture(fixture := Path(tmp) / "blocker")
    mutate_csv(fixture, lambda rows: rows[0].__setitem__("blockers", ""))
    blocker = run_validator(fixture)
    check(blocker.returncode != 0, "empty blocker list unexpectedly passed")
    check("active module must list blockers" in blocker.stdout, "blocker diagnostic missing")

    write_fixture(fixture := Path(tmp) / "sync")
    (fixture / "STATUS.adoc").write_text("STATUS_B\n", encoding="utf-8")
    sync = run_validator(fixture)
    check(sync.returncode != 0, "STATUS drift unexpectedly passed")
    check("status token absent from STATUS.adoc" in sync.stdout, "sync diagnostic missing")

print("scientific-state authority tests: OK")
