#!/usr/bin/env python3
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/nta_salary_source_system_coverage_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(OUT)
metrics = {r["metric_id"]: r for r in rows}
catalog = {r["source_id"]: r for r in read(CATALOG)}

assert len(rows) == 20
assert len(metrics) == 20

anchors = {
    "source_salary_public_offices_payment": "28282710",
    "source_salary_other_payment": "325610351",
    "source_salary_total_payment": "353893061",
    "source_salary_public_offices_withholding": "917029",
    "source_salary_other_withholding": "11021742",
    "source_salary_total_withholding": "11938771",
    "source_day_labor_total_payment": "1232032",
    "source_day_labor_total_withholding": "20909",
    "private_salary_survey_average_monthly_salary_earners": "60184788",
    "private_salary_survey_salary_amount": "241438813",
    "private_salary_survey_tax_amount": "11183370",
    "source_public_offices_payment_share": "0.079918803494",
    "source_public_offices_withholding_share": "0.076811005086",
    "private_salary_to_source_other_payment_ratio": "0.741496123383",
    "private_salary_to_source_other_tax_ratio": "1.014664469555",
    "source_other_minus_private_salary_payment": "84171538",
    "source_total_minus_private_salary_payment": "112454248",
    "source_other_minus_private_salary_tax": "-161628",
    "public_offices_salary_person_share": "NOT_IDENTIFIED",
    "table7_gt20m_private_sector_adjustment_from_public_amount_share": "PROHIBITED",
}
for key, expected in anchors.items():
    assert metrics[key]["value"] == expected, (key, metrics[key]["value"], expected)
assert 28_282_710 + 325_610_351 == 353_893_061
assert 917_029 + 11_021_742 == 11_938_771

public_amount_share = float(metrics["source_public_offices_payment_share"]["value"])
public_tax_share = float(metrics["source_public_offices_withholding_share"]["value"])
assert 0 < public_amount_share < 1
assert 0 < public_tax_share < 1
assert metrics["source_public_offices_payment_share"]["identification_status"] == (
    "AMOUNT_SHARE_NOT_PERSON_SHARE"
)
assert metrics["source_public_offices_withholding_share"]["identification_status"] == (
    "AMOUNT_SHARE_NOT_PERSON_SHARE"
)

private_to_other_pay = float(metrics["private_salary_to_source_other_payment_ratio"]["value"])
private_to_other_tax = float(metrics["private_salary_to_source_other_tax_ratio"]["value"])
assert private_to_other_pay < 1
assert private_to_other_tax > 1
assert metrics["private_salary_to_source_other_payment_ratio"]["identification_status"] == (
    "CROSS_STATISTIC_RATIO_NOT_COVERAGE_RATE"
)
assert metrics["private_salary_to_source_other_tax_ratio"]["identification_status"] == (
    "CROSS_STATISTIC_RATIO_NOT_SUBSET_RATE"
)
assert int(metrics["source_other_minus_private_salary_tax"]["value"]) < 0
assert metrics["source_other_minus_private_salary_tax"]["identification_status"] == (
    "NEGATIVE_DIFFERENCE_PROVES_NON_NESTED_PUBLISHED_AGGREGATES"
)
assert metrics["public_offices_salary_person_share"]["value"] == "NOT_IDENTIFIED"
assert metrics["public_offices_salary_person_share"]["identification_status"] == (
    "NO_PERSON_COUNT_IN_SOURCE_TABLE"
)
assert metrics["table7_gt20m_private_sector_adjustment_from_public_amount_share"][
    "value"
] == "PROHIBITED"
assert metrics["table7_gt20m_private_sector_adjustment_from_public_amount_share"][
    "identification_status"
] == "DO_NOT_APPLY_AMOUNT_SHARE_TO_PERSON_COUNT"

# The public-office amount share must not be silently converted to a person
# correction for the Table 7 >20m estimate.
table7_gt20m = 235_287
naive_private_adjustment = table7_gt20m * (1 - public_amount_share)
assert naive_private_adjustment > 0
assert not any(
    r["unit"] in ("person_share", "person_ratio", "person_probability")
    for r in rows
)

# Average-monthly Private Salary Survey persons are not annual unique persons.
assert metrics["private_salary_survey_average_monthly_salary_earners"][
    "identification_status"
] == "SURVEY_STOCK_AVERAGE_NOT_ANNUAL_UNIQUE_PERSON_COUNT"
assert catalog["NTA-FY2024-WITHHOLDING-STATUS"]["sha256"] == (
    "87133c85ecaa3ea0a16953ebadb52d25e7b99de85a839148b127179877eb11fb"
)
assert catalog["NTA-MINKAN-2024-T1"]["sha256"] == (
    "e4d957dc0c115a42a8a34dc2cd58a2044c41b237697b2ede23574637a42b3904"
)

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_salary_source_system_coverage.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA salary source-system coverage tests: OK "
    "(public payment share=7.991880%; private/source-other pay=74.149612%; "
    "private/source-other tax=101.466447%; no person-share inference)"
)
