#!/usr/bin/env python3
from pathlib import Path
import csv
import math
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CLASS = ROOT / "data/derived/nta_private_salary_taxpayer_status_by_salary_class_2024.csv"
SUMMARY = ROOT / "data/derived/nta_private_salary_taxpayer_status_summary_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"
SELF = ROOT / "data/derived/nta_calculated_tax_positive_denominator_audit_2024.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


classes = read(CLASS)
summary = read(SUMMARY)
assert len(classes) == 56
assert len(summary) == 5

expected_panels = {
    ("full_year", "False"),
    ("less_than_year", "False"),
    ("full_year", "True"),
    ("less_than_year", "True"),
}
assert {
    (r["employment_duration_group"], r["secondary_payroll_otsuran_excluded"])
    for r in classes
} == expected_panels

for panel in expected_panels:
    q = [
        r for r in classes
        if (r["employment_duration_group"], r["secondary_payroll_otsuran_excluded"]) == panel
    ]
    assert len(q) == 14
    assert [int(r["salary_class_index"]) for r in q] == list(range(1, 15))

expected_labels = [
    "100万円以下",
    "200 〃",
    "300 〃",
    "400 〃",
    "500 〃",
    "600 〃",
    "700 〃",
    "800 〃",
    "900 〃",
    "1,000 〃",
    "1,500 〃",
    "2,000 〃",
    "2,500 〃",
    "2,500万円超",
]
observed = [
    r["salary_class_label"]
    for r in classes
    if r["employment_duration_group"] == "full_year"
    and r["secondary_payroll_otsuran_excluded"] == "True"
]
assert observed == expected_labels, observed

# Year-end-adjusted values are unchanged by excluding secondary-payroll
# (乙欄) records, at every class and in panel totals.
for duration in ("full_year", "less_than_year"):
    inc = {
        int(r["salary_class_index"]): r
        for r in classes
        if r["employment_duration_group"] == duration
        and r["secondary_payroll_otsuran_excluded"] == "False"
    }
    exc = {
        int(r["salary_class_index"]): r
        for r in classes
        if r["employment_duration_group"] == duration
        and r["secondary_payroll_otsuran_excluded"] == "True"
    }
    for i in range(1, 15):
        for key in (
            "year_end_adjusted_taxpayer_persons",
            "year_end_adjusted_nontaxpayer_persons",
            "year_end_adjusted_total_persons",
            "year_end_adjusted_tax_million_yen",
        ):
            assert inc[i][key] == exc[i][key], (duration, i, key)
        # Excluding secondary payroll must not increase non-adjusted counts.
        assert int(exc[i]["not_year_end_adjusted_total_persons"]) <= int(
            inc[i]["not_year_end_adjusted_total_persons"]
        )

by_scope = {r["summary_scope"]: r for r in summary}
anchors = {
    "full_year_all_payroll_records": {
        "year_end_adjusted_taxpayer_persons": 33_796_714,
        "year_end_adjusted_total_persons": 47_213_036,
        "all_taxpayer_persons": 37_526_454,
        "all_total_persons": 51_365_699,
        "all_tax_million_yen": 11_036_310,
    },
    "less_than_year_all_payroll_records": {
        "year_end_adjusted_taxpayer_persons": 1_759_702,
        "year_end_adjusted_total_persons": 5_584_644,
        "all_taxpayer_persons": 4_613_882,
        "all_total_persons": 9_408_447,
        "all_tax_million_yen": 272_368,
    },
    "full_year_otsuran_excluded": {
        "year_end_adjusted_taxpayer_persons": 33_796_714,
        "year_end_adjusted_total_persons": 47_213_036,
        "all_taxpayer_persons": 35_826_258,
        "all_total_persons": 49_665_503,
        "all_tax_million_yen": 10_505_437,
    },
    "less_than_year_otsuran_excluded": {
        "year_end_adjusted_taxpayer_persons": 1_759_702,
        "year_end_adjusted_total_persons": 5_584_644,
        "all_taxpayer_persons": 2_579_986,
        "all_total_persons": 7_374_551,
        "all_tax_million_yen": 231_366,
    },
}
for scope, vals in anchors.items():
    r = by_scope[scope]
    for key, expected in vals.items():
        assert int(r[key]) == expected, (scope, key, r[key], expected)
    assert r["final_calculated_tax_positive_subset_status"] == (
        "NOT_STRICT_SUBSET_FINAL_RETURN_CAN_CHANGE_TAX"
    )
    assert r["cross_source_union_status"] == (
        "OVERLAP_WITH_SELF_ASSESSED_RETURNS_UNKNOWN_DO_NOT_SUM"
    )

c = by_scope["combined_year_end_adjusted_private_salary_otsuran_excluded"]
assert int(c["year_end_adjusted_taxpayer_persons"]) == 35_556_416
assert int(c["year_end_adjusted_nontaxpayer_persons"]) == 17_241_264
assert int(c["year_end_adjusted_total_persons"]) == 52_797_680
assert int(c["year_end_adjusted_tax_million_yen"]) == 7_280_879
assert int(c["not_year_end_adjusted_taxpayer_persons"]) == 2_849_828
assert int(c["all_taxpayer_persons"]) == 38_406_244
assert int(c["all_total_persons"]) == 57_040_054
assert int(c["all_tax_million_yen"]) == 10_736_803
assert math.isclose(
    float(c["year_end_adjusted_taxpayer_rate"]),
    35_556_416 / 52_797_680,
    abs_tol=5e-13,
    rel_tol=0.0,
)
assert math.isclose(
    float(c["all_taxpayer_rate"]),
    38_406_244 / 57_040_054,
    abs_tol=5e-13,
    rel_tol=0.0,
)
assert c["final_calculated_tax_positive_subset_status"] == (
    "NOT_STRICT_SUBSET_EXTERNAL_PAYROLL_SCALE_DIAGNOSTIC_ONLY"
)
assert c["cross_source_union_status"] == (
    "OVERLAP_WITH_SELF_ASSESSED_RETURNS_UNKNOWN_DO_NOT_SUM"
)

# Explicitly guard against the tempting but invalid additive union with the
# self-assessed positive-balance population.
self_rows = read(SELF)
assert len(self_rows) == 1
assert int(self_rows[0]["annual_positive_self_assessed_balance_persons"]) == 5_158_260
invalid_naive_sum = 35_556_416 + 5_158_260
assert invalid_naive_sum == 40_714_676
assert c["cross_source_union_status"].endswith("DO_NOT_SUM")

# Definitions and raw-source hashes are fixed.
catalog = {r["source_id"]: r for r in read(CATALOG)}
assert catalog["NTA-MINKAN-2024-T16"]["sha256"] == (
    "11b941a52dff3681f0e19415ba095746cd0ed24e54dd6b159521e2145b13c1e6"
)
assert catalog["NTA-MINKAN-METHODOLOGY"]["sha256"] == (
    "4ce6d9a50704b9035fa3e4f0522e519a63ad6f90acde54096326c536212319e8"
)
for r in classes:
    assert r["cross_system_status"] == (
        "EXTERNAL_WAGE_SIDE_DIAGNOSTIC_NO_ADDITIVE_JOIN_TO_SELF_ASSESSED_RETURNS"
    )
    assert "not a strict final calculated-tax-positive subset" in (
        r["year_end_adjusted_direction_note"]
    )
    assert "Do not add these taxpayer counts" in r["identification_warning"]

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_private_salary_taxpayer_status.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA private-salary taxpayer-status tests: OK "
    "(56 salary classes; adjusted taxpayers 35,556,416 / 52,797,680; "
    "external payroll-tax diagnostic only; no additive join to self-assessed returns)"
)
