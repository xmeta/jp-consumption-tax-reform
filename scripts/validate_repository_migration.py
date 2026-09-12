#!/usr/bin/env python3
"""Validate legacy-artifact migration by scientific capability coverage."""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = Path("data/recovery/legacy_artifact_capability.csv")
CLAIMS = Path("data/claim_graph.csv")
STATUS = Path("STATUS.adoc")
RELEASE = Path("releases/V6_RECOVERED_2026-09-08.adoc")
FIELDS = [
    "artifact_id", "legacy_path", "capability_id", "historical_recovery_status",
    "migration_state", "claim_ids", "active_claim_dependency", "replacement_paths",
    "disposition_reason", "recovery_basis",
]
STATES = {
    "RESTORED_BYTE_OR_FUNCTIONALLY_EQUIVALENT",
    "SCIENTIFICALLY_SUPERSEDED",
    "RETIRED_WITH_JUSTIFICATION",
    "UNRESOLVED_RECOVERY_GAP",
}
RECOVERY = {"PRESERVED_EXACT", "RECOVERABLE_FILE_LIBRARY", "NOT_RECOVERED"}
SHA = "6878d12710be50b6876a8fdf07b03f86ac7d83a7d9445d42259776d38ba0b1ae"
PATH_RE = re.compile(r"^scripts/(\d{2})_[A-Za-z0-9_]+\.py$")


def read_csv(path: Path, fields: list[str] | None = None) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if fields is not None and reader.fieldnames != fields:
            raise ValueError(f"{path.name} schema mismatch")
        return list(reader)


def split(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def validate(root: Path = ROOT) -> tuple[list[str], str]:
    errors: list[str] = []
    try:
        rows = read_csv(root / MATRIX, FIELDS)
        claims = read_csv(root / CLAIMS)
    except (OSError, ValueError) as exc:
        return [f"schema: {exc}"], "PARTIAL"

    claim_rows = {row["claim_id"]: row for row in claims}
    if len(claim_rows) != len(claims):
        errors.append("claim graph contains duplicate claim_id")
    if len(rows) != 45:
        errors.append(f"coverage: expected 45 numbered legacy artifacts, found {len(rows)}")

    seen_ids: set[str] = set()
    seen_numbers: set[int] = set()
    blocking: list[str] = []
    for row in rows:
        artifact_id = row["artifact_id"]
        if not artifact_id or artifact_id in seen_ids:
            errors.append(f"schema: duplicate/empty artifact_id {artifact_id!r}")
        seen_ids.add(artifact_id)

        match = PATH_RE.fullmatch(row["legacy_path"])
        if not match:
            errors.append(f"schema: {artifact_id}: invalid legacy_path")
            continue
        number = int(match.group(1))
        seen_numbers.add(number)
        if artifact_id != f"legacy-{number:02d}":
            errors.append(f"schema: {artifact_id}: artifact_id/path number mismatch")
        if not row["capability_id"]:
            errors.append(f"schema: {artifact_id}: capability_id required")
        if row["historical_recovery_status"] not in RECOVERY:
            errors.append(f"schema: {artifact_id}: invalid historical recovery status")
        if row["migration_state"] not in STATES:
            errors.append(f"schema: {artifact_id}: invalid migration_state")
        if row["active_claim_dependency"] not in {"true", "false"}:
            errors.append(f"schema: {artifact_id}: active_claim_dependency must be true/false")
        if not row["disposition_reason"]:
            errors.append(f"schema: {artifact_id}: disposition_reason required")
        if SHA not in row["recovery_basis"]:
            errors.append(f"provenance: {artifact_id}: V6 archive SHA missing from recovery_basis")
        linked_claims = split(row["claim_ids"])
        unknown = [claim_id for claim_id in linked_claims if claim_id not in claim_rows]
        if unknown:
            errors.append(f"claim: {artifact_id}: unknown claim_ids {';'.join(unknown)}")

        replacements = split(row["replacement_paths"])
        if row["migration_state"] in {
            "RESTORED_BYTE_OR_FUNCTIONALLY_EQUIVALENT", "SCIENTIFICALLY_SUPERSEDED"
        }:
            if not replacements:
                errors.append(f"coverage: {artifact_id}: replacement_paths required")
            for value in replacements:
                path = Path(value)
                if path.is_absolute() or ".." in path.parts or not (root / path).exists():
                    errors.append(f"coverage: {artifact_id}: missing/unsafe replacement {value}")

        active_dependency = row["active_claim_dependency"] == "true"
        if row["migration_state"] == "RETIRED_WITH_JUSTIFICATION" and active_dependency:
            errors.append(f"coverage: {artifact_id}: retired artifact cannot remain active dependency")
        if row["migration_state"] == "UNRESOLVED_RECOVERY_GAP":
            if active_dependency:
                blocking.append(artifact_id)
            elif any(claim_rows[cid].get("active") == "true" for cid in linked_claims if cid in claim_rows):
                errors.append(f"coverage: {artifact_id}: unresolved gap links active claim but dependency=false")

    if seen_numbers != set(range(1, 46)):
        missing = sorted(set(range(1, 46)) - seen_numbers)
        extra = sorted(seen_numbers - set(range(1, 46)))
        errors.append(f"coverage: numbered artifact set mismatch missing={missing} extra={extra}")
    migration_state = "PARTIAL" if blocking else "COMPLETE"
    try:
        status = (root / STATUS).read_text(encoding="utf-8")
        release = (root / RELEASE).read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"provenance: {exc}")
        return errors, migration_state

    marker = f"repository_migration |{migration_state}"
    if marker not in status:
        errors.append(f"status: expected {marker}")
    if SHA not in release:
        errors.append("provenance: registered V6 recovered archive SHA missing from release record")
    return errors, migration_state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors, state = validate(args.root)
    if errors:
        raise SystemExit("\n".join("ERROR: " + error for error in errors))
    print(f"repository migration validation: OK state={state} artifacts=45")


if __name__ == "__main__":
    main()
