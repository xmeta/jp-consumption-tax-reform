#!/usr/bin/env python3
"""Regression tests for capability-based repository migration."""
from __future__ import annotations

import csv
import importlib.util
import shutil
import tempfile
from pathlib import Path

if not __debug__:
    raise RuntimeError("repository-migration regression tests require non-optimized Python")

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts/validate_repository_migration.py"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_validator():
    spec = importlib.util.spec_from_file_location("repository_migration_validator", VALIDATOR_PATH)
    check(spec is not None and spec.loader is not None, "validator import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_validator()
check(validator.validate(ROOT) == ([], "COMPLETE"), "repository migration state is invalid")


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_fixture(root: Path) -> None:
    for rel in (validator.MATRIX, validator.CLAIMS, validator.STATUS, validator.RELEASE):
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    with (root / validator.MATRIX).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for value in validator.split(row["replacement_paths"]):
            src = ROOT / value
            dst = root / value
            if dst.exists():
                continue
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text("fixture\n", encoding="utf-8")


def mutate(root: Path, fn) -> None:
    path = root / validator.MATRIX
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fn(rows)
    write_csv(path, rows, validator.FIELDS)


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "missing"
    make_fixture(root)
    mutate(root, lambda rows: rows.pop())
    errors, state = validator.validate(root)
    check(state == "COMPLETE", "missing-row fixture changed state unexpectedly")
    check(any("expected 45" in error for error in errors), "missing artifact passed")

    root = Path(tmp) / "replacement"
    make_fixture(root)
    mutate(
        root,
        lambda rows: next(row for row in rows if row["artifact_id"] == "legacy-18").update(
            replacement_paths="missing/path"
        ),
    )
    errors, _ = validator.validate(root)
    check(any("missing/unsafe replacement" in error for error in errors), "missing replacement passed")

    root = Path(tmp) / "unknown-claim"
    make_fixture(root)
    mutate(
        root,
        lambda rows: next(row for row in rows if row["artifact_id"] == "legacy-18").update(
            claim_ids="P1-NOT-A-CLAIM"
        ),
    )
    errors, _ = validator.validate(root)
    check(any("unknown claim_ids" in error for error in errors), "unknown claim passed")

    root = Path(tmp) / "blocking-gap"
    make_fixture(root)
    mutate(
        root,
        lambda rows: next(row for row in rows if row["artifact_id"] == "legacy-39").update(
            active_claim_dependency="true"
        ),
    )
    errors, state = validator.validate(root)
    check(state == "PARTIAL", "active unresolved gap did not force PARTIAL")
    check(any("expected repository_migration |PARTIAL" in error for error in errors), "status mismatch not detected")

    root = Path(tmp) / "active-link-hidden"
    make_fixture(root)
    mutate(
        root,
        lambda rows: next(row for row in rows if row["artifact_id"] == "legacy-39").update(
            claim_ids="VAT-C02", active_claim_dependency="false"
        ),
    )
    errors, _ = validator.validate(root)
    check(any("unresolved gap links active claim" in error for error in errors), "active unresolved claim was hidden")

    root = Path(tmp) / "retired-active"
    make_fixture(root)
    mutate(
        root,
        lambda rows: next(row for row in rows if row["artifact_id"] == "legacy-01").update(
            active_claim_dependency="true"
        ),
    )
    errors, _ = validator.validate(root)
    check(any("retired artifact cannot remain active dependency" in error for error in errors), "retired active dependency passed")

print("repository-migration capability tests: OK")
