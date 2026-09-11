#!/usr/bin/env python3
"""Regression tests for scientific-review gates."""
from __future__ import annotations

import csv
import importlib.util
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts/validate_scientific_reviews.py"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_validator():
    spec = importlib.util.spec_from_file_location("scientific_review_validator", VALIDATOR_PATH)
    check(spec is not None and spec.loader is not None, "validator import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_validator()

def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def copy_fixture(root: Path) -> None:
    (root / "data").mkdir(parents=True)
    (root / "reviews").mkdir()
    for rel in (
        "data/research_products.csv",
        "data/scientific_review_gates.csv",
        "data/scientific_reviews.csv",
        "data/source_catalog.csv",
        "data/claim_graph.csv",
        "reviews/paper1_adversarial_2026-09-12.adoc",
    ):
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)


def mutate(path: Path, fields: list[str], fn) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fn(rows)
    write_csv(path, rows, fields)

check(validator.validate(ROOT) == [], "repository review state is invalid")

paper = "\n".join(
    path.read_text(encoding="utf-8") for path in sorted((ROOT / "paper1").rglob("*.adoc"))
)
check("positive self-assessed liability" not in paper.lower(), "reviewed liability/balance terminology regressed")
check("first-submission manuscript" not in (ROOT / "paper1/README.adoc").read_text(encoding="utf-8").lower(), "publication-readiness wording regressed")

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "track-mismatch"
    copy_fixture(root)
    mutate(
        root / "data/scientific_review_gates.csv",
        validator.GATE_FIELDS,
        lambda rows: next(
            row for row in rows
            if row["product_id"] == "paper1" and row["review_track"] == "ECONOMIC_IDENTIFICATION"
        ).update(status="SATISFIED", review_id="P1-AR-001"),
    )
    errors = validator.validate(root)
    check(any("track does not satisfy gate" in error for error in errors), "track mismatch passed")

    root = Path(tmp) / "independence"
    copy_fixture(root)
    mutate(
        root / "data/scientific_review_gates.csv",
        validator.GATE_FIELDS,
        lambda rows: next(
            row for row in rows
            if row["product_id"] == "paper1" and row["review_track"] == "ADVERSARIAL_CLAIM"
        ).update(minimum_independence="INDEPENDENT_REVIEWER"),
    )
    errors = validator.validate(root)
    check(any("independence below gate minimum" in error for error in errors), "weak review passed")

    root = Path(tmp) / "evidence-eligible"
    copy_fixture(root)
    mutate(
        root / "data/scientific_reviews.csv",
        validator.REVIEW_FIELDS,
        lambda rows: rows[0].update(evidence_eligible="true"),
    )
    errors = validator.validate(root)
    check(any("evidence_eligible=false" in error for error in errors), "review became evidence")

    root = Path(tmp) / "claim-source"
    copy_fixture(root)
    with (root / "data/claim_graph.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        claim_rows = list(reader)
        claim_fields = list(reader.fieldnames or [])
    claim_rows[0]["source"] = "reviews/paper1_adversarial_2026-09-12.adoc"
    write_csv(root / "data/claim_graph.csv", claim_rows, claim_fields)
    errors = validator.validate(root)
    check(any("review artifact used as claim source" in error for error in errors), "review source passed")

    root = Path(tmp) / "missing-artifact"
    copy_fixture(root)
    (root / "reviews/paper1_adversarial_2026-09-12.adoc").unlink()
    errors = validator.validate(root)
    check(any("missing findings_path" in error for error in errors), "missing review artifact passed")

print("scientific-review gate tests: OK")
