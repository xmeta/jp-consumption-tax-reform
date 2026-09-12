#!/usr/bin/env python3
"""Guard the current VAT integration vocabulary against ambiguous E2E wording."""
from __future__ import annotations

import csv
from pathlib import Path

if not __debug__:
    raise RuntimeError("VAT status terminology tests require non-optimized Python")

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_COMPONENT_STATUS = (
    "SCENARIO_SCHEMA_INTEGRATED_WITH_STATIC_REFERENCES_AND_UNRESOLVED_MACRO_OUTCOMES"
)
CANONICAL_JOINT_STATUS = (
    "SCENARIO_SCHEMA_REPORT_WITH_STATIC_REFERENCES_AND_UNRESOLVED_MACRO_OUTCOMES"
)
FORBIDDEN = ("PARTIAL_" + "E2E", "partial end-to-" + "end", "部分" + "E2E")


def rows(rel: str) -> list[dict[str, str]]:
    with (ROOT / rel).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


scientific = {row["component_id"]: row for row in rows("data/scientific_state.csv")}
if scientific["vat_policy_integration"]["status"] != CANONICAL_COMPONENT_STATUS:
    raise RuntimeError("VAT scientific-state terminology drift")

claims = {row["claim_id"]: row for row in rows("data/claim_graph.csv")}
if claims["VAT-C02"]["empirical_status"] != CANONICAL_COMPONENT_STATUS:
    raise RuntimeError("VAT-C02 terminology drift")

for rel in (
    "data/derived/vat_policy_scenario_matrix.csv",
    "data/derived/vat_policy_scenario_summary.csv",
):
    observed = {row["joint_outcome_status"] for row in rows(rel)}
    if observed != {CANONICAL_JOINT_STATUS}:
        raise RuntimeError(f"{rel}: unexpected joint_outcome_status {sorted(observed)}")

catalog = {row["artifact_id"]: row for row in rows("data/derived_catalog.csv")}
expected_catalog = {
    "VAT-POLICY-SCENARIO-MATRIX": "MODEL_CONTINGENT_SCENARIO_SCHEMA_MATRIX_WITH_STATIC_REFERENCES",
    "VAT-POLICY-SCENARIO-SUMMARY": "MODEL_CONTINGENT_SCENARIO_SCHEMA_SUMMARY_WITH_STATIC_REFERENCES",
}
for artifact_id, expected in expected_catalog.items():
    if catalog[artifact_id]["status"] != expected:
        raise RuntimeError(f"{artifact_id}: derived-catalog terminology drift")

current_surfaces = (
    "STATUS.adoc",
    "data/scientific_state.csv",
    "data/claim_graph.csv",
    "data/claim_evidence.csv",
    "data/derived_catalog.csv",
    "data/derived/vat_policy_scenario_matrix.csv",
    "data/derived/vat_policy_scenario_summary.csv",
    "research/vat_claim_registry.csv",
    "research/vat_compliance_productivity/README.adoc",
    "research/vat_policy_integration/README.adoc",
    "research/vat_policy_integration/run_vat_policy_scenario_matrix.py",
    "research/vat_policy_integration/test_vat_policy_scenario_matrix.py",
    "scripts/build_derived_catalog.py",
    "scripts/test_claim_graph.py",
)
for rel in current_surfaces:
    text = (ROOT / rel).read_text(encoding="utf-8")
    for token in FORBIDDEN:
        if token.casefold() in text.casefold():
            raise RuntimeError(f"{rel}: ambiguous VAT integration wording reintroduced")

print("VAT status terminology: OK")
