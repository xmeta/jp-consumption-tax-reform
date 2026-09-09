#!/usr/bin/env python3
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CLASS = ROOT / "data/derived/nta_private_salary_not_year_end_adjusted_by_salary_class_2024.csv"
SUMMARY = ROOT / "data/derived/nta_salary_return_overlap_audit_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


classes = read(CLASS)
summary = {r["metric_id"]: r for r in read(SUMMARY)}
catalog = {r["source_id"]: r for r in read(CATALOG)}

assert len(classes) == 84
assert len(summary) == 12
assert {
    (r["employment_duration_group"], r["tax_status"]) for r in classes
} == {
    ("full_year", "taxpayer"), ("full_year", "nontaxpayer"), ("full_year", "all"),
    ("less_than_year", "taxpayer"), ("less_than_year", "nontaxpayer"), ("less_than_year", "all"),
}
for duration in ("full_year", "less_than_year"):
    for status in ("taxpayer", "nontaxpayer", "all"):
        q = [r for r in classes if r["employment_duration_group"] == duration and r["tax_status"] == status]
        assert len(q) == 14
        assert [int(r["salary_class_index"]) for r in q] == list(range(1, 15))
        for r in q:
            assert abs(
                int(r["secondary_payroll_persons"])
                + int(r["previous_employer_salary_unknown_persons"])
                + int(r["other_reason_persons"])
                - int(r["total_not_year_end_adjusted_persons"])
            ) <= 1
            assert r["identification_warning"].startswith("Payroll-survey rows do not identify")

full_tax = [r for r in classes if r["employment_duration_group"] == "full_year" and r["tax_status"] == "taxpayer"]
assert sum(int(r["total_not_year_end_adjusted_persons"]) for r in full_tax) == 3_729_740
assert abs(sum(int(r["secondary_payroll_persons"]) for r in full_tax) - 1_700_196) <= 1
assert sum(int(r["previous_employer_salary_unknown_persons"]) for r in full_tax) == 0
assert abs(sum(int(r["other_reason_persons"]) for r in full_tax) - 2_029_544) <= 1

less_tax = [r for r in classes if r["employment_duration_group"] == "less_than_year" and r["tax_status"] == "taxpayer"]
assert sum(int(r["total_not_year_end_adjusted_persons"]) for r in less_tax) == 2_854_180
assert abs(sum(int(r["secondary_payroll_persons"]) for r in less_tax) - 2_033_896) <= 1
assert abs(sum(int(r["previous_employer_salary_unknown_persons"]) for r in less_tax) - 102_891) <= 1
assert abs(sum(int(r["other_reason_persons"]) for r in less_tax) - 717_393) <= 1
anchors = {
    "private_salary_full_year_no_year_end_adjustment_taxpayers": "3729740",
    "private_salary_full_year_no_year_end_adjustment_secondary_payroll": "1700196",
    "private_salary_full_year_salary_receipts_gt20m": "320983",
    "salary_primary_table22_filed_or_processed_population": "11423587",
    "salary_primary_final_return_row_population": "11293442",
    "salary_primary_final_return_population": "11423587",
    "salary_primary_positive_self_assessed_balance": "2385726",
    "salary_primary_refund": "7697018",
    "salary_primary_neither_positive_nor_refund": "1340843",
    "salary_primary_positive_balance_any_withholding": "2161129",
    "salary_primary_positive_balance_salary_withholding": "2114353",
    "private_salary_to_final_return_person_overlap": "NOT_IDENTIFIED",
}
for key, expected in anchors.items():
    assert summary[key]["value"] == expected, (key, summary[key]["value"], expected)

assert summary["private_salary_full_year_salary_receipts_gt20m"]["identification_status"] == (
    "LEGAL_FILING_CANDIDATE_NOT_OBSERVED_MATCH"
)
assert summary["private_salary_to_final_return_person_overlap"]["identification_status"] == (
    "DO_NOT_SUM_OR_INFER_EXACT_OVERLAP"
)
assert summary["salary_primary_table22_filed_or_processed_population"]["identification_status"] == (
    "OBSERVED_FILED_OR_PROCESSED_POPULATION"
)
assert summary["salary_primary_final_return_row_population"]["identification_status"] == (
    "OBSERVED_FINAL_RETURN_ROW"
)
assert summary["salary_primary_final_return_population"]["identification_status"] == (
    "DEPRECATED_ALIAS_NOT_PURE_FINAL_RETURN_ROW"
)
assert summary["salary_primary_final_return_population"]["value"] != summary[
    "salary_primary_final_return_row_population"
]["value"]
assert "11,423,587" not in summary["private_salary_to_final_return_person_overlap"]["value"]

assert catalog["NTA-MINKAN-2024-T19"]["sha256"] == (
    "220b34508d4ff778cf375aabdd097d425aa7ded0f173c40022f51ad2cd2614e4"
)
assert catalog["NTA-2024-SALARY-FILING-REQUIREMENT"]["sha256"] == (
    "a759d06efa32cf73164dc8d6f6a3d74faf4409cf2988bdadeda9825b5f8a7c3a"
)
# Guard against reintroducing naive additive payroll + return-side unions.
payroll_adjusted_positive = 35_556_416
salary_primary_processed = int(summary["salary_primary_table22_filed_or_processed_population"]["value"])
salary_primary_final_row = int(summary["salary_primary_final_return_row_population"]["value"])
assert payroll_adjusted_positive + salary_primary_processed == 46_980_003
assert payroll_adjusted_positive + salary_primary_final_row == 46_849_858
assert summary["private_salary_to_final_return_person_overlap"]["value"] == "NOT_IDENTIFIED"

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_salary_return_overlap.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA salary-return overlap tests: OK "
    "(84 Table 19 class rows; >20m candidate=320,983; "
    "salary-primary filed/processed=11,423,587; pure final-return row=11,293,442; "
    "exact cross-source overlap not identified)"
)
