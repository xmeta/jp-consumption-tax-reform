#!/usr/bin/env python3
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/public_sector_person_coverage_audit_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(OUT)
metrics = {r["metric_id"]: r for r in rows}
catalog = {r["source_id"]: r for r in read(CATALOG)}

assert len(rows) == 13
assert len(metrics) == 13

anchors = {
    "national_public_salary_survey_covered_persons": "250434",
    "local_public_employee_survey_total": "2813939",
    "local_public_employee_regular_subtotal": "2754139",
    "local_public_employee_general_staff": "1637851",
    "local_public_employee_education": "856644",
    "local_public_employee_police": "259644",
    "local_public_employee_temporary": "59800",
    "observed_national_plus_local_public_workforce_subtotal": "3064373",
    "nta_public_offices_salary_payment": "28282710",
    "nta_public_offices_salary_withholding": "917029",
    "nta_public_offices_salary_person_count": "NOT_IDENTIFIED",
    "nta_public_offices_average_salary_using_external_subtotal": "PROHIBITED",
    "table7_gt20m_public_sector_person_adjustment": "PROHIBITED",
}
for key, expected in anchors.items():
    assert metrics[key]["value"] == expected, (key, metrics[key]["value"], expected)
assert 2_754_139 + 59_800 == 2_813_939
assert 1_637_851 + 856_644 + 259_644 == 2_754_139
assert 250_434 + 2_813_939 == 3_064_373

assert metrics["national_public_salary_survey_covered_persons"][
    "identification_status"
] == "EXTERNAL_NATIONAL_PUBLIC_WORKFORCE_BENCHMARK"
assert metrics["local_public_employee_survey_total"][
    "identification_status"
] == "EXTERNAL_LOCAL_PUBLIC_WORKFORCE_BENCHMARK"
assert metrics["observed_national_plus_local_public_workforce_subtotal"][
    "identification_status"
] == "EXTERNAL_PUBLIC_WORKFORCE_BENCHMARK_NOT_NTA_DENOMINATOR"

assert metrics["nta_public_offices_salary_person_count"][
    "identification_status"
] == "NTA_PUBLIC_OFFICES_PERSON_COUNT_NOT_IDENTIFIED"
assert metrics["nta_public_offices_average_salary_using_external_subtotal"][
    "identification_status"
] == "DO_NOT_DIVIDE_CROSS_FRAME_AMOUNT_BY_PERSON_SUBTOTAL"
assert metrics["table7_gt20m_public_sector_person_adjustment"][
    "identification_status"
] == "NO_PUBLIC_SECTOR_HIGH_SALARY_CROSSTAB"

# Tempting arithmetic is deliberately not promoted to a scientific metric.
naive_avg_yen = 28_282_710 * 1_000_000 / 3_064_373
assert naive_avg_yen > 0
assert not any(
    r["unit"] in ("yen_per_person", "million_yen_per_person", "person_share")
    for r in rows
)

# Nor may the external subtotal be treated as an NTA Public Offices denominator.
assert not any(
    r["metric_id"] == "nta_public_offices_salary_person_count"
    and r["value"].isdigit()
    for r in rows
)
hashes = {
    "ESTAT-LOCAL-PUBLIC-SALARY-2024-T1":
        "c55545c73c96713aa59c70c4c902431aea79029f2da1f8b7278dc5d4916dd17b",
    "ESTAT-LOCAL-PUBLIC-SALARY-2024-METADATA":
        "9cc66f668f0126977aad94133cf3b397c4b010978f4acd3887808409e54cb0d0",
    "JINJI-2024-PUBLIC-SALARY-SURVEY-SUMMARY":
        "11e94371337b4c17d8b13b6f64db7df85ccb1e979e6ad1a362a9693ddc4a4e5c",
    "JINJI-2024-PUBLIC-SALARY-SURVEY-T1":
        "3b060fa5412e39df21409214c70a7ab8c6a2fcb09c30ca709f5b50f8d64e8019",
    "JINJI-2024-PUBLIC-SALARY-SURVEY-RESULTS":
        "ff9c8b9c43429f84463e50cac72069283b4aab83ad9e8c00ec6fe4c459d604e4",
}
for source_id, expected in hashes.items():
    assert catalog[source_id]["sha256"] == expected

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_public_sector_person_coverage.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "public-sector person coverage tests: OK "
    "(national covered=250,434; local total=2,813,939; "
    "external subtotal=3,064,373; NTA Public Offices persons not identified)"
)
