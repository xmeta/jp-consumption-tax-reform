#!/usr/bin/env python3
"""Fast structural regression tests for scripts/reproduce.py."""
from __future__ import annotations

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/reproduce.py"

spec = importlib.util.spec_from_file_location("reproduce", MODULE_PATH)
assert spec and spec.loader
reproduce = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reproduce)

EXPECTED = {
    "source-integrity",
    "vat",
    "income-tax",
    "provenance",
    "paper1",
    "integrity",
}
assert set(reproduce.TARGETS) == EXPECTED
assert reproduce.ALL_ORDER == (
    "source-integrity",
    "income-tax",
    "vat",
    "provenance",
    "paper1",
    "docs",
    "integrity",
)
assert reproduce.ALL_ORDER.index("income-tax") < reproduce.ALL_ORDER.index("vat")

terminology_guard = ("scripts/test_filed_processed_terminology.py",)
assert terminology_guard not in reproduce.INCOME_TAX
assert reproduce.PROVENANCE[-1] == terminology_guard

generators = [row[0] for row in reproduce.PAPER1_GENERATORS]
paper1 = list(reproduce.PAPER1)
for path in generators:
    assert (path,) in paper1
    assert (path, "--check") in paper1

assert "data/derived/*.csv" in reproduce.CLEAN_ROOM_GLOBS
assert "data/source_catalog.csv" in reproduce.CLEAN_ROOM_GLOBS
assert "paper1/data/stage1_frontier_table.csv" in reproduce.CLEAN_ROOM_GLOBS
assert "data/derived/stage1_official_inputs.csv" in reproduce.CLEAN_ROOM_KEEP

listed = subprocess.run(
    [sys.executable, str(MODULE_PATH), "--list"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
).stdout.splitlines()
assert listed == [
    "source-integrity",
    "vat",
    "income-tax",
    "provenance",
    "paper1",
    "integrity",
    "docs",
    "all",
    "clean-room",
]

dry = subprocess.run(
    [sys.executable, str(MODULE_PATH), "all", "--dry-run"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
).stdout
assert "scripts/build_source_catalog.py" in dry
assert "research/vat_compliance_productivity/run_vat_compliance_productivity.py" in dry
assert "research/income_tax_pseudofiler/run_pseudofiler_core.py" in dry
assert dry.index("scripts/extract_estat_income_tax_tables.py") < dry.index("scripts/build_estat_objective_rank_household_margin_audit.py")
assert "scripts/validate_provenance.py" in dry
assert dry.index("scripts/build_derived_catalog.py") < dry.index("scripts/test_filed_processed_terminology.py")
assert "paper1/scripts/generate_frontier_table.py --check" in dry
assert "paper1/index.adoc" in dry
assert "scripts/check_manifest.py" in dry

print("reproduction entrypoint structural tests: OK")
