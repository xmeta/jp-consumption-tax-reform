#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data/derived/nta_salary_filing_bridge_source_matrix_2024.csv"
AUDIT = ROOT / "data/derived/nta_salary_filing_bridge_identification_audit_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(MATRIX)
by = {r["source_family_id"]: r for r in rows}
audit = {r["metric_id"]: r for r in read(AUDIT)}
catalog = {r["source_id"]: r for r in read(CATALOG)}

expected_families = {
    "private_salary_table16",
    "private_salary_table19",
    "salary_filing_legal_rule",
    "positive_balance_salary_receipt_table7",
    "annual_processing_table21",
    "submitted_return_press_table31",
    "annual_income_type_table23",
    "withholding_public_other_table7",
    "nagoya_regional_table21",
    "nagoya_regional_table22",
}
assert len(rows) == 10
assert set(by) == expected_families
assert all(r["cross_family_person_link"] == "NO" for r in rows)
assert all(r["direct_bridge_status"] == "NO_DIRECT_PERSON_BRIDGE" for r in rows)

t19 = by["private_salary_table19"]
assert t19["salary_receipts_gt20m_dimension"] == "YES_EXPLICIT_GT20_PANEL"
assert t19["year_end_adjustment_dimension"] == "YES_NO_YEAR_END_ADJUSTMENT"
assert t19["submitted_return_dimension"] == "NO"
assert t19["processing_status_dimension"] == "NO"
assert t19["employer_sector_dimension"] == "PRIVATE_SECTOR_ONLY"

t7 = by["positive_balance_salary_receipt_table7"]
assert t7["salary_receipts_gt20m_dimension"] == "YES"
assert t7["positive_refund_dimension"] == "POSITIVE_BALANCE_TARGET_ONLY_NO_REFUND"
assert t7["salary_source_withholding_person_dimension"] == (
    "YES_WITHIN_POSITIVE_BALANCE_TARGET"
)
assert t7["processing_status_dimension"] == "NO_PROCESSING_CATEGORY"

t21 = by["annual_processing_table21"]
assert t21["salary_receipts_gt20m_dimension"] == "NO"
assert t21["processing_status_dimension"] == "YES_EXACT"
assert t21["positive_refund_dimension"] == "YES_EXACT_POSITIVE_REFUND_RESIDUAL"

press = by["submitted_return_press_table31"]
assert press["submitted_return_dimension"] == "YES_ROUNDED_SUBMITTED_RETURN_COUNT"
assert press["salary_receipts_gt20m_dimension"] == "NO"
assert press["processing_status_dimension"] == "NO"

withholding = by["withholding_public_other_table7"]
assert withholding["person_population"] == "NO_CURRENT_PERSON_COUNT"
assert withholding["employer_sector_dimension"] == "YES_PUBLIC_OFFICES_VS_OTHERS_AMOUNTS"
assert withholding["salary_source_withholding_person_dimension"] == "WITHHOLDING_AMOUNT_ONLY"

for family in ("nagoya_regional_table21", "nagoya_regional_table22"):
    assert by[family]["geographic_tax_office_dimension"] == "YES_TAX_OFFICE"
    assert by[family]["salary_receipts_gt20m_dimension"] == "NO"
    assert by[family]["year_end_adjustment_dimension"] == "NO"
expected_audit = {
    "examined_official_source_families": "10",
    "sources_with_gt20_and_submitted_return_person_count": "0",
    "sources_with_gt20_and_processing_status": "0",
    "sources_with_year_end_adjustment_and_processing_status": "0",
    "sources_with_employer_sector_and_return_status": "0",
    "cross_family_person_link_sources": "0",
    "table7_gt20_positive_balance_is_full_filing_bridge": "NO",
    "salary_gt20_legal_rule_is_observed_person_link": "NO",
    "regional_tables_close_salary_filing_bridge": "NO",
    "direct_salary_receipt_processing_status_bridge":
        "NOT_FOUND_IN_EXAMINED_OFFICIAL_SOURCE_FAMILIES",
}
assert set(audit) == set(expected_audit)
for key, expected in expected_audit.items():
    assert audit[key]["value"] == expected, (key, audit[key]["value"], expected)

assert audit["direct_salary_receipt_processing_status_bridge"]["identification_status"] == (
    "PUBLIC_AGGREGATE_BRIDGE_NOT_IDENTIFIED"
)
assert "does not claim" in audit["direct_salary_receipt_processing_status_bridge"]["note"]

hashes = {
    "NTA-NAGOYA-2024-SHINKOKU-21-XLSX":
        "0322d55bdc3c7b07373519bcbd38ae6762098435658222a3ca3be9fbfe5b4e2f",
    "NTA-NAGOYA-2024-SHINKOKU-22-XLSX":
        "6afa9f4cf9235401e5f12aa642fcf293e868a3e3acd09c2a8454ca558feec42e",
}
for sid, expected in hashes.items():
    assert catalog[sid]["sha256"] == expected
    assert (ROOT / catalog[sid]["raw_file"]).exists()

# Guard against the two most tempting invalid inferences.
assert not any(
    r["salary_receipts_gt20m_dimension"].startswith("YES")
    and r["processing_status_dimension"].startswith("YES")
    for r in rows
)
assert not any(
    r["salary_receipts_gt20m_dimension"].startswith("YES")
    and r["submitted_return_dimension"].startswith("YES")
    for r in rows
)

subprocess.run(
    [sys.executable, str(ROOT / "scripts/build_nta_salary_filing_bridge_source_matrix.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA salary-filing bridge source-matrix tests: OK "
    "(10 source families; no direct >20m/year-end-adjustment x submission/processing bridge)"
)
