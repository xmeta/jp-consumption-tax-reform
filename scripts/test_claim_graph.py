#!/usr/bin/env python3
"""Negative regression tests for repository-wide claim-graph invariants."""
from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path

from generate_claim_registries import GRAPH_FIELDS, generate
from validate_claim_graph import validate

EVIDENCE_FIELDS = [
    "claim_id",
    "evidence_status",
    "evidence_artifact",
    "source_ids",
    "value_ids",
    "locator",
    "note",
]
STATE_FIELDS = ["component_id", "maturity", "causal_status", "policy_usable", "active"]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def claim(cid: str, product: str = "paper1") -> dict[str, str]:
    return {
        "product_id": product,
        "claim_id": cid,
        "topic": f"topic {cid}",
        "empirical_status": "OBSERVED_PUBLIC",
        "identification_status": "READY",
        "causal_status": "NOT_CAUSAL",
        "policy_status": "NOT_POLICY_USABLE",
        "component_id": "",
        "evidence_scope": "fixture evidence",
        "allowed_claim": "A descriptive fixture claim is supported.",
        "forbidden_claim": "Do not promote this fixture into a causal or optimal-policy claim.",
        "source": "source.txt",
        "evidence_ids": "evidence.txt",
        "supersedes": "",
        "superseded_by": "",
        "active": "true",
    }


def build_fixture(root: Path) -> None:
    (root / "source.txt").write_text("source\n", encoding="utf-8")
    (root / "evidence.txt").write_text("evidence\n", encoding="utf-8")
    claims = [claim(f"P1-C{i:02d}") for i in range(1, 18)]
    claims[2]["component_id"] = "income_tax_pseudofiler"
    claims[2]["identification_status"] = "SENSITIVITY_ONLY"
    claims[2]["empirical_status"] = "SENSITIVITY_ONLY_REPRODUCED"
    claims.append(
        {
            **claim("VAT-C01", "vat_abolition"),
            "component_id": "vat_compliance_productivity",
            "identification_status": "SENSITIVITY_ONLY",
            "empirical_status": "MODEL_CONTINGENT_COMPLIANCE_PRODUCTIVITY_SENSITIVITY",
        }
    )
    claims.append(
        {
            **claim("VAT-C02", "vat_abolition"),
            "component_id": "vat_policy_integration",
            "identification_status": "PARTIALLY_IDENTIFIED",
            "empirical_status": "PARTIAL_E2E_POLICY_MATRIX",
        }
    )
    write_csv(root / "data/claim_graph.csv", GRAPH_FIELDS, claims)
    evidence = [
        {
            "claim_id": row["claim_id"],
            "evidence_status": "ACTIVE_OFFICIAL",
            "evidence_artifact": "evidence.txt",
            "source_ids": "",
            "value_ids": "",
            "locator": row["claim_id"],
            "note": "fixture",
        }
        for row in claims
    ]
    write_csv(root / "data/claim_evidence.csv", EVIDENCE_FIELDS, evidence)
    states = [
        {
            "component_id": "income_tax_pseudofiler",
            "maturity": "SENSITIVITY_ONLY",
            "causal_status": "NOT_CAUSAL",
            "policy_usable": "false",
            "active": "true",
        },
        {
            "component_id": "vat_compliance_productivity",
            "maturity": "SENSITIVITY_ONLY",
            "causal_status": "NOT_CAUSAL",
            "policy_usable": "false",
            "active": "true",
        },
        {
            "component_id": "vat_policy_integration",
            "maturity": "PARTIALLY_IDENTIFIED",
            "causal_status": "NOT_CAUSAL",
            "policy_usable": "false",
            "active": "true",
        },
    ]
    write_csv(root / "data/scientific_state.csv", STATE_FIELDS, states)
    generate(root)


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def assert_error(errors: list[str], needle: str) -> None:
    if not any(needle in error for error in errors):
        raise RuntimeError(f"missing expected diagnostic {needle!r}: {errors}")


def isolated_fixture() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    build_fixture(root)
    return temp, root


def main() -> None:
    temp, root = isolated_fixture()
    try:
        errors = validate(root)
        if errors:
            raise RuntimeError(f"valid fixture failed: {errors}")
    finally:
        temp.cleanup()

    temp, root = isolated_fixture()
    try:
        fields, rows = read_rows(root / "data/claim_graph.csv")
        rows.append(dict(rows[0]))
        write_csv(root / "data/claim_graph.csv", fields, rows)
        assert_error(validate(root, check_outputs=False), "duplicate repository-wide claim_id")
    finally:
        temp.cleanup()

    temp, root = isolated_fixture()
    try:
        fields, rows = read_rows(root / "data/claim_evidence.csv")
        rows.append({**rows[0], "claim_id": "ORPHAN-C01", "locator": "orphan"})
        write_csv(root / "data/claim_evidence.csv", fields, rows)
        assert_error(validate(root), "orphan evidence references unknown claim_id ORPHAN-C01")
    finally:
        temp.cleanup()

    temp, root = isolated_fixture()
    try:
        fields, rows = read_rows(root / "data/claim_evidence.csv")
        for row in rows:
            if row["claim_id"] == "P1-C01":
                row["evidence_status"] = "RECOVERY_ONLY"
        write_csv(root / "data/claim_evidence.csv", fields, rows)
        assert_error(validate(root), "active claim lacks active evidence")
        assert_error(validate(root), "active claim relies only on recovery evidence")
    finally:
        temp.cleanup()

    temp, root = isolated_fixture()
    try:
        fields, rows = read_rows(root / "data/claim_graph.csv")
        for row in rows:
            if row["claim_id"] == "P1-C03":
                row["identification_status"] = "READY"
        write_csv(root / "data/claim_graph.csv", fields, rows)
        assert_error(validate(root, check_outputs=False), "claim maturity READY exceeds component SENSITIVITY_ONLY")
    finally:
        temp.cleanup()

    temp, root = isolated_fixture()
    try:
        path = root / "paper1/data/claim_registry.csv"
        path.write_text(path.read_text(encoding="utf-8") + "stale\n", encoding="utf-8")
        assert_error(validate(root), "stale generated registry")
    finally:
        temp.cleanup()

    print("repository claim-graph tests: OK (duplicate, orphan, active evidence, state contradiction, projection)")


if __name__ == "__main__":
    main()
