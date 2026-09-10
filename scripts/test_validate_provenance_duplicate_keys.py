#!/usr/bin/env python3
"""Negative regression tests for authoritative provenance-registry primary keys."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/validate_provenance.py"


def run_validator():
    return subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def verify_duplicate(rel, expected):
    path = ROOT / rel
    original = path.read_bytes()
    rows = original.splitlines()
    if len(rows) < 2:
        raise RuntimeError(f"registry has no data row: {rel}")
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    mutated = original
    if not mutated.endswith((b"\n", b"\r")):
        mutated += newline
    mutated += rows[1] + newline
    try:
        path.write_bytes(mutated)
        result = run_validator()
        output = result.stdout + result.stderr
        if result.returncode == 0:
            raise RuntimeError(f"duplicate key unexpectedly accepted: {rel}")
        if expected not in output:
            raise RuntimeError(f"missing expected duplicate error {expected!r}: {output!r}")
    finally:
        path.write_bytes(original)


baseline = run_validator()
if baseline.returncode != 0:
    raise RuntimeError(
        f"baseline provenance validation failed: {baseline.stdout}{baseline.stderr}"
    )

cases = [
    ("data/source_catalog.csv", "duplicate source_id:"),
    ("data/derived_catalog.csv", "duplicate derived_file:"),
    ("data/derived/stage1_official_inputs.csv", "duplicate official value_id:"),
    ("data/recovery/v6_recovered_values.csv", "duplicate recovery value_id:"),
    ("research/stage1_filing_bound/inputs.csv", "duplicate stage1 input:"),
    ("data/input_provenance.csv", "duplicate provenance value_id:"),
    ("data/claim_graph.csv", "duplicate claim_id:"),
]
for rel, expected in cases:
    verify_duplicate(rel, expected)

subprocess.run(
    ["git", "-C", str(ROOT), "diff", "--exit-code", "--"]
    + [rel for rel, _ in cases],
    check=True,
)
print(f"provenance duplicate-key regression tests: OK ({len(cases)} registries)")
