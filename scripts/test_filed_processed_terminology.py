#!/usr/bin/env python3
"""Guard canonical filed-vs-processed terminology for NTA Table 2-2/2-3 artifacts.

Stage-1 intentionally uses the pure Final return row (23,090,075) and is not
part of this migration.  This test covers the partial-identification artifacts
whose underlying NTA populations include later processing categories.
"""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    ROOT / "scripts/extract_nta_salary_return_overlap.py",
    ROOT / "scripts/extract_nta_salary_receipt_return_bridge.py",
    ROOT / "scripts/extract_nta_salary_source_system_coverage.py",
    ROOT / "scripts/build_derived_catalog.py",
    ROOT / "research/income_tax_partial_identification/salary_return_overlap_audit.adoc",
    ROOT / "research/income_tax_partial_identification/salary_receipt_return_bridge_audit.adoc",
    ROOT / "research/income_tax_partial_identification/salary_source_system_coverage_audit.adoc",
    ROOT / "research/income_tax_partial_identification/README.adoc",
    ROOT / "data/derived/nta_salary_return_overlap_audit_2024.csv",
    ROOT / "data/derived/nta_salary_receipt_return_bridge_2024.csv",
    ROOT / "data/derived/nta_salary_source_system_coverage_2024.csv",
    ROOT / "data/derived_catalog.csv",
]

BANNED = [
    "final-return/processed population",
    "Refund final-return population",
    "salary-primary final-return population",
    "Final returns, primary income category salary",
    "overlap with final-return statistics",
    "union with final-return persons",
    "final-return linkage",
]

for path in TARGETS:
    text = path.read_text(encoding="utf-8")
    for phrase in BANNED:
        assert phrase.lower() not in text.lower(), (path, phrase)

# Canonical processed-population language must be present in the generated
# Table 2-3 bridge.
with (ROOT / "data/derived/nta_salary_receipt_return_bridge_2024.csv").open(
    encoding="utf-8", newline=""
) as f:
    bridge = list(csv.DictReader(f))
assert bridge
assert any("filed-or-processed income-tax population" in r["population"] for r in bridge)
assert all("final-return/processed" not in r["population"].lower() for r in bridge)

# PR #19 established the pure Final-return row versus the broader processed
# total.  Keep both anchors and ensure they are not conflated.
with (ROOT / "data/derived/nta_salary_processing_status_audit_2024.csv").open(
    encoding="utf-8", newline=""
) as f:
    processing = {r["metric_id"]: r for r in csv.DictReader(f)}
assert processing["salary_table22_filed_or_processed_population"]["value"] == "11423587"
assert processing["salary_final_return_row_population"]["value"] == "11293442"
assert (
    processing["salary_primary_final_return_population_alias"]["identification_status"]
    == "DEPRECATED_ALIAS_NOT_PURE_FINAL_RETURN_ROW"
)

# Stage-1 is intentionally different: it uses the exact pure Final-return row.
with (ROOT / "data/derived/stage1_official_inputs.csv").open(
    encoding="utf-8", newline=""
) as f:
    stage1 = {r["value_id"]: r for r in csv.DictReader(f)}
assert stage1["nta_final_return_filers_2024"]["value"] == "23090075"
assert "final return" in stage1["nta_final_return_filers_2024"]["source_locator"].lower()

print(
    "filed-vs-processed terminology tests: OK "
    "(Table 2-2/2-3 artifacts canonicalized; stage-1 pure Final-return row preserved)"
)
