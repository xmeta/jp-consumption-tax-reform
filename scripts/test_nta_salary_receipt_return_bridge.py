#!/usr/bin/env python3
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CLASS = ROOT / "data/derived/nta_positive_balance_salary_receipt_class_2024.csv"
SUMMARY = ROOT / "data/derived/nta_salary_receipt_return_bridge_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


classes = read(CLASS)
summary = {r["metric_id"]: r for r in read(SUMMARY)}
catalog = {r["source_id"]: r for r in read(CATALOG)}

assert len(classes) == 72
assert len(summary) == 19
assert {r["income_earner_category"] for r in classes} == {
    "all", "business", "real_estate", "salary", "miscellaneous", "other"
}
for category in ("all", "business", "real_estate", "salary", "miscellaneous", "other"):
    q = [r for r in classes if r["income_earner_category"] == category]
    assert len(q) == 12
    assert [int(r["salary_receipt_class_index"]) for r in q] == list(range(1, 13))
    for r in q:
        assert int(r["salary_receipt_persons_estimated"]) == (
            int(r["salary_withholding_persons_estimated"])
            + int(r["no_salary_withholding_persons_estimated"])
        )
        assert r["cell_nature"] == (
            "SURVEY_ESTIMATED_POSITIVE_SELF_ASSESSED_BALANCE_SALARY_RECEIPT_CELL"
        )
        assert "not a complete-survey count" in r["identification_warning"]

totals = {}
for category in ("all", "business", "real_estate", "salary", "miscellaneous", "other"):
    q = [r for r in classes if r["income_earner_category"] == category]
    totals[category] = {
        key: sum(int(r[key]) for r in q)
        for key in (
            "salary_receipt_persons_estimated",
            "salary_withholding_persons_estimated",
            "no_salary_withholding_persons_estimated",
        )
    }

assert totals["all"]["salary_receipt_persons_estimated"] == 3_368_241
assert totals["salary"]["salary_receipt_persons_estimated"] == 2_412_316
assert totals["all"]["salary_receipt_persons_estimated"] == sum(
    totals[c]["salary_receipt_persons_estimated"]
    for c in ("business", "real_estate", "salary", "miscellaneous", "other")
)
high = [
    r for r in classes
    if int(r["salary_receipt_class_index"]) >= 10
]
high_all = [r for r in high if r["income_earner_category"] == "all"]
high_salary = [r for r in high if r["income_earner_category"] == "salary"]
high_other = [
    r for r in high
    if r["income_earner_category"] not in ("all", "salary")
]

def s(rows, key):
    return sum(int(r[key]) for r in rows)

assert s(high_all, "salary_receipt_persons_estimated") == 235_287
assert s(high_salary, "salary_receipt_persons_estimated") == 225_050
assert s(high_other, "salary_receipt_persons_estimated") == 10_237
assert s(high_all, "salary_withholding_persons_estimated") == 227_606
assert s(high_all, "no_salary_withholding_persons_estimated") == 7_681
assert 227_606 + 7_681 == 235_287

anchors = {
    "private_salary_full_year_receipts_gt20m": "320983",
    "positive_balance_salary_receipts_gt20m_all_categories": "235287",
    "positive_balance_salary_receipts_gt20m_salary_category": "225050",
    "positive_balance_salary_receipts_gt20m_non_salary_categories": "10237",
    "positive_balance_salary_receipts_gt20m_with_salary_withholding": "227606",
    "positive_balance_salary_receipts_gt20m_without_salary_withholding": "7681",
    "annual_return_employment_income_persons_all": "13184714",
    "annual_return_employment_income_persons_main": "11425783",
    "annual_return_employment_income_persons_secondary": "1758931",
    "annual_positive_balance_employment_income_persons": "3143364",
    "annual_positive_balance_employment_income_persons_main": "2384138",
    "annual_positive_balance_employment_income_persons_secondary": "759226",
    "annual_refund_employment_income_persons": "8532771",
    "annual_refund_employment_income_persons_main": "7700263",
    "annual_refund_employment_income_persons_secondary": "832508",
    "t23_main_minus_t22_salary_category_all": "2196",
    "t23_main_minus_t22_salary_category_positive_balance": "-1588",
    "t23_main_minus_t22_salary_category_refund": "3245",
    "private_salary_to_positive_balance_gt20m_person_overlap": "NOT_IDENTIFIED",
}
for key, expected in anchors.items():
    assert summary[key]["value"] == expected, (key, summary[key]["value"], expected)

for key in (
    "t23_main_minus_t22_salary_category_all",
    "t23_main_minus_t22_salary_category_positive_balance",
    "t23_main_minus_t22_salary_category_refund",
):
    assert summary[key]["identification_status"] == (
        "DEFINITION_DIFFERENCE_NOT_RECONCILIATION_ERROR"
    )

assert summary["private_salary_to_positive_balance_gt20m_person_overlap"][
    "identification_status"
] == "SAME_THRESHOLD_BUT_NO_PERSON_LINK"
assert all("rate" not in k.lower() for k in summary)
# The tempting ratio 235,287 / 320,983 is descriptive only and must never be
# promoted to a matched-person probability by this artifact.
naive_ratio = 235_287 / 320_983
assert 0 < naive_ratio < 1
assert not any(
    r["unit"] in ("rate", "share", "probability")
    and "gt20m" in r["metric_id"]
    for r in summary.values()
)

hashes = {
    "NTA-2024-SHINKOKU-T7-XLSX":
        "626eec739f998eddfffcada85061d8050073d43a4fb05f5f7532603001213680",
    "NTA-2024-SHINKOKU-T7-PDF":
        "edb9e08376628e9b8de1f3815e6198a6ab96cfdb73ebbc5b4074ac8af3376ebc",
    "NTA-2024-ANNUAL-T23-INCOME-TYPE":
        "70bb66e22010b9642d7015c9e765432c01b017caa2e1498c25013bdd95e4e5ce",
    "NTA-2024-ANNUAL-TABLE-NOTES":
        "24cd4a7bcd745a83d343f53837b21e26f3a34af13ecde519b4e885e0b1c690f9",
}
for source_id, expected in hashes.items():
    assert catalog[source_id]["sha256"] == expected

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_salary_receipt_return_bridge.py"), "--check"],
    cwd=ROOT,
    check=True,
)
print(
    "NTA salary-receipt return bridge tests: OK "
    "(72 Table 7 cells; >20m positive-balance estimate=235,287; "
    "annual employment-income persons=13,184,714; exact overlap not identified)"
)
