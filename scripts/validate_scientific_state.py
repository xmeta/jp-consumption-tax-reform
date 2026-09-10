#!/usr/bin/env python3
"""Validate the repository-wide machine-readable scientific-state authority."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

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
PHASES = {"PHASE1_COMPLETE", "PHASE2_ACTIVE", "MAINTENANCE"}
MATURITY = {"NOT_IDENTIFIED", "SENSITIVITY_ONLY", "PARTIALLY_IDENTIFIED", "READY"}
CAUSAL = {"NOT_CAUSAL", "DESCRIPTIVE_ONLY", "CAUSAL_IDENTIFIED"}
BOOL = {"true", "false"}


def split_paths(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def discover_active_modules(root: Path) -> set[str]:
    research = root / "research"
    if not research.is_dir():
        return set()
    modules: set[str] = set()
    for child in research.iterdir():
        if not child.is_dir():
            continue
        if not (child / "README.adoc").is_file():
            continue
        if any(child.glob("*.py")):
            modules.add(child.relative_to(root).as_posix())
    return modules


def validate(root: Path) -> list[str]:
    authority = root / "data/scientific_state.csv"
    status_doc = root / "STATUS.adoc"
    errors: list[str] = []

    if not authority.is_file():
        return ["schema: missing data/scientific_state.csv"]
    if not status_doc.is_file():
        return ["sync: missing STATUS.adoc"]

    with authority.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            errors.append(
                "schema: scientific_state.csv fields must be exactly: "
                + ",".join(FIELDS)
            )
            return errors
        rows = list(reader)

    if not rows:
        errors.append("schema: scientific_state.csv must contain at least one row")
        return errors

    component_ids = [row["component_id"].strip() for row in rows]
    if len(component_ids) != len(set(component_ids)):
        errors.append("schema: duplicate component_id")

    active_rows = [row for row in rows if row["active"].strip().lower() == "true"]
    active_paths = [row["module_path"].strip() for row in active_rows]
    if len(active_paths) != len(set(active_paths)):
        errors.append("schema: duplicate active module_path (conflicting module state)")

    status_text = status_doc.read_text(encoding="utf-8")
    for lineno, row in enumerate(rows, 2):
        prefix = f"row {lineno} ({row['component_id'] or '<blank>'})"
        for field in (
            "component_id",
            "module_path",
            "display_name",
            "status",
            "phase",
            "maturity",
            "causal_status",
            "policy_usable",
            "active",
        ):
            if not row[field].strip():
                errors.append(f"schema: {prefix}: empty {field}")
        if row["phase"].strip() not in PHASES:
            errors.append(f"schema: {prefix}: invalid phase {row['phase']!r}")
        if row["maturity"].strip() not in MATURITY:
            errors.append(f"schema: {prefix}: invalid maturity {row['maturity']!r}")
        if row["causal_status"].strip() not in CAUSAL:
            errors.append(
                f"schema: {prefix}: invalid causal_status {row['causal_status']!r}"
            )
        if row["policy_usable"].strip().lower() not in BOOL:
            errors.append(f"schema: {prefix}: policy_usable must be true/false")
        if row["active"].strip().lower() not in BOOL:
            errors.append(f"schema: {prefix}: active must be true/false")

        module_path = root / row["module_path"].strip()
        if row["active"].strip().lower() == "true":
            if not module_path.is_dir():
                errors.append(f"coverage: {prefix}: missing module_path")
            elif not (module_path / "README.adoc").is_file():
                errors.append(f"coverage: {prefix}: missing module README.adoc")
            if not row["blockers"].strip():
                errors.append(f"schema: {prefix}: active module must list blockers")
            if row["status"].strip() not in status_text:
                errors.append(
                    f"sync: {prefix}: status token absent from STATUS.adoc: "
                    f"{row['status'].strip()}"
                )

        for field in ("evidence_paths", "output_paths"):
            paths = split_paths(row[field])
            if not paths:
                errors.append(f"schema: {prefix}: {field} must not be empty")
            for rel in paths:
                if not (root / rel).exists():
                    errors.append(f"provenance: {prefix}: missing {field}: {rel}")

    discovered = discover_active_modules(root)
    declared = set(active_paths)
    if discovered != declared:
        missing = sorted(discovered - declared)
        extra = sorted(declared - discovered)
        detail = []
        if missing:
            detail.append("undeclared=" + ",".join(missing))
        if extra:
            detail.append("not-discovered=" + ",".join(extra))
        errors.append("coverage: active module coverage mismatch: " + "; ".join(detail))

    by_id = {
        row["component_id"].strip(): row
        for row in rows
        if row["component_id"].strip()
    }
    for row in rows:
        cid = row["component_id"].strip()
        for field, inverse in (
            ("supersedes", "superseded_by"),
            ("superseded_by", "supersedes"),
        ):
            for target in split_paths(row[field]):
                if target not in by_id:
                    errors.append(
                        f"schema: {cid}: unknown {field} component_id {target}"
                    )
                elif cid not in split_paths(by_id[target][inverse]):
                    errors.append(
                        f"schema: {cid}: {field}={target} lacks reciprocal {inverse}"
                    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (used by regression fixtures)",
    )
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    if errors:
        print("\n".join("ERROR: " + error for error in errors))
        return 1
    print("machine-readable scientific-state validation: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
