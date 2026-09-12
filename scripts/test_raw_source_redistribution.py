#!/usr/bin/env python3
"""Regression tests for raw-source redistribution governance."""
from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path

if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests; assertions must remain active")

ROOT = Path(__file__).resolve().parents[1]
from validate_raw_source_redistribution import validate


def fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="raw-rights-"))
    for rel in ("data/source_catalog.csv", "data/raw_source_redistribution_rules.csv", "data/raw_source_redistribution_audit.csv"):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    return root


def mutate(path: Path, source_id: str, field: str, value: str) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle)); fields = list(rows[0])
    for row in rows:
        if row["source_id"] == source_id:
            row[field] = value; break
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)


assert validate(ROOT) == []
root = fixture(); mutate(root / "data/raw_source_redistribution_audit.csv", "BOJ-OUTLOOK-2019-07-CONSUMPTION-TAX", "sha256", "0" * 64)
assert any("sha256 does not match" in e for e in validate(root)); shutil.rmtree(root)
root = fixture(); mutate(root / "data/raw_source_redistribution_audit.csv", "RIETI-2019-VAT-COMPLIANCE-FIRM-GROWTH", "public_release_action", "INCLUDE_RAW")
assert any("raw inclusion lacks explicit" in e for e in validate(root)); shutil.rmtree(root)
root = fixture();
with (root / "data/raw_source_redistribution_audit.csv").open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle)); fields = list(rows[0])
with (root / "data/raw_source_redistribution_audit.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows[1:])
assert any("coverage mismatch" in e for e in validate(root)); shutil.rmtree(root)
print("raw-source redistribution tests: OK")
