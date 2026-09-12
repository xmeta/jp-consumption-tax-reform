#!/usr/bin/env python3
"""Regression checks for publication-facing metadata."""
from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path

if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests; assertions must remain active")

ROOT = Path(__file__).resolve().parents[1]
from validate_publication_metadata import validate

FIXTURE_FILES = (
    "CITATION.cff",
    "REPRODUCE.adoc",
    "data/research_products.csv",
    "data/research_product_files.csv",
    "docs/data_availability.adoc",
    "docs/licensing.adoc",
    "docs/research_products.adoc",
)


def fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="publication-metadata-"))
    for rel in FIXTURE_FILES:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    return root


def remove_boundary(path: Path, product_id: str, target_path: str) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames
    rows = [row for row in rows if not (row["product_id"] == product_id and row["path"] == target_path)]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


assert validate(ROOT) == []

root = fixture()
citation = root / "CITATION.cff"
citation.write_text(citation.read_text(encoding="utf-8").replace("cff-version: 1.2.0", "cff-version: 1.1.0"), encoding="utf-8")
assert any("cff-version" in error for error in validate(root))
shutil.rmtree(root)

root = fixture()
remove_boundary(root / "data/research_product_files.csv", "paper1", "CITATION.cff")
assert any("paper1: release metadata missing" in error for error in validate(root))
shutil.rmtree(root)

print("publication metadata tests: OK")
