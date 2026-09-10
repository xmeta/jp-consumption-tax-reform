#!/usr/bin/env python3
from pathlib import Path
import ast
import csv
import io
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GUARD_MESSAGE = "optimized Python is not supported for executable tests; assertions must remain active"
TARGET_SOURCE = "ESRI-SNA-2024-NOMINAL-GDP-FISCAL-YEAR"
BUILDER = ROOT / "research/vat_policy_integration/build_jgb_debt_gdp_reference.py"
CATALOG = ROOT / "data/source_catalog.csv"

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def tracked_python_files():
    return subprocess.check_output(["git", "ls-files", "*.py"], cwd=ROOT, text=True).splitlines()

def is_optimized_guard(node):
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.op, ast.Not)
        and isinstance(node.test.operand, ast.Name)
        and node.test.operand.id == "__debug__"
    )

production_asserts = []
guarded_tests = []
for rel in tracked_python_files():
    source = (ROOT / rel).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=rel)
    assertions = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]
    if Path(rel).name.startswith("test_"):
        if assertions:
            require(any(is_optimized_guard(n) for n in tree.body), f"missing optimized-Python test guard: {rel}")
            require(GUARD_MESSAGE in source, f"missing optimized-Python guard message: {rel}")
            guarded_tests.append(rel)
    elif assertions:
        production_asserts.append((rel, len(assertions)))
require(not production_asserts, f"production runtime asserts remain: {production_asserts}")
require(guarded_tests, "no executable assert-based tests were discovered")

for rel in guarded_tests:
    proc = subprocess.run([sys.executable, "-O", str(ROOT / rel)], cwd=ROOT, text=True, capture_output=True)
    combined = proc.stdout + proc.stderr
    require(proc.returncode != 0, f"optimized test falsely succeeded: {rel}")
    require(GUARD_MESSAGE in combined, f"optimized test did not fail via explicit guard: {rel}")

valid = subprocess.run([sys.executable, "-O", str(BUILDER), "--check"], cwd=ROOT, text=True, capture_output=True)
require(valid.returncode == 0, "valid optimized production execution failed after assert migration")
backup = CATALOG.read_bytes()
try:
    with CATALOG.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames
    matches = [r for r in rows if r["source_id"] == TARGET_SOURCE]
    require(len(matches) == 1, f"unexpected target-source count: {len(matches)}")
    matches[0]["sha256"] = "0" * 64
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    CATALOG.write_text(out.getvalue(), encoding="utf-8")
    tampered = subprocess.run([sys.executable, "-O", str(BUILDER), "--check"], cwd=ROOT, text=True, capture_output=True)
    require(tampered.returncode != 0, "tampered source SHA passed under optimized Python")
    require("RuntimeError" in tampered.stderr, "tampered optimized failure was not an explicit runtime guard")
finally:
    CATALOG.write_bytes(backup)
require(CATALOG.read_bytes() == backup, "source catalog was not restored after tamper regression")
print(f"optimized-Python runtime guards: OK (production asserts=0; guarded tests={len(guarded_tests)}; source tamper rejected)")
