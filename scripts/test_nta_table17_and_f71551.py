#!/usr/bin/env python3
from pathlib import Path
import csv
import hashlib
import math
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NTA_RAW = ROOT / "data/raw/nta/nta_minkan2024_table17.xlsx"
F71551_RAW = ROOT / "data/raw/estat/000040490418.xlsx"

SOCIAL = ROOT / "data/derived/nta_salary_class_social_deduction_schedule_2024.csv"
FAMILY = ROOT / "data/derived/nta_salary_class_family_deduction_validation_2024.csv"
AGE = ROOT / "data/derived/income_tax_age_income_source_shares_2024.csv"
STATUTORY = ROOT / "data/derived/income_tax_2026_statutory_parameters.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


social = read(SOCIAL)
family = read(FAMILY)
age = read(AGE)
params = read(STATUTORY)

assert len(social) == 12
assert len(family) == 12
assert len(age) == 10

expected_upper = [
    1_000_000, 2_000_000, 3_000_000, 4_000_000,
    5_000_000, 6_000_000, 7_000_000, 8_000_000,
    9_000_000, 10_000_000, 15_000_000, 20_000_000,
]
assert [int(r["upper_salary_yen_inclusive"]) for r in social] == expected_upper
assert [int(r["upper_salary_yen_inclusive"]) for r in family] == expected_upper

nta_sha = sha(NTA_RAW)
f71551_sha = sha(F71551_RAW)

for r in social:
    emp = float(r["full_year_employee_count"])
    rec = float(r["social_insurance_deduction_recipient_count"])
    amount = float(r["social_insurance_deduction_amount_million_yen"]) * 1_000_000
    assert emp > 0
    assert 0 <= rec <= emp
    assert math.isclose(
        float(r["average_social_insurance_deduction_per_employee_yen"]),
        amount / emp,
        rel_tol=1e-10,
    )
    if rec > 0:
        assert math.isclose(
            float(r["average_social_insurance_deduction_per_recipient_yen"]),
            amount / rec,
            rel_tol=1e-10,
        )
    assert r["source_sha256"] == nta_sha
    assert r["model_status"] == "EXTERNAL_SENSITIVITY_ONLY"
    for c in [
        "full_year_employee_count_source_cell",
        "social_insurance_deduction_recipient_count_source_cell",
        "social_insurance_deduction_amount_source_cell",
    ]:
        assert r[c]

dep = {
    r["rule_id"]: int(float(r["constant_yen"]))
    for r in params if r["parameter_group"] == "dependent_deduction"
}
assert dep == {
    "D_GENERAL": 380000,
    "D_SPECIFIED": 630000,
    "D_ELDERLY_OTHER": 480000,
    "D_ELDERLY_CORESIDENT": 580000,
}

for r in family:
    general = float(r["general_dependent_count"])
    specified = float(r["specified_dependent_count"])
    co = float(r["elderly_co_resident_dependent_count"])
    other = float(r["elderly_other_dependent_count"])
    total = float(r["observed_dependent_count_total"])
    component = general + specified + co + other
    # Public-table totals differ from component sums by at most one person in
    # several salary classes because of source rounding.
    assert abs(component - total) <= 1.0
    expected = (
        general * 380000
        + specified * 630000
        + co * 580000
        + other * 480000
    )
    assert math.isclose(
        float(r["dependent_deduction_2026_amounts_on_2024_composition_total_yen"]),
        expected,
        abs_tol=1e-6,
    )
    assert math.isclose(
        float(r["dependent_deduction_2026_amounts_on_2024_composition_per_employee_yen"]),
        expected / float(r["full_year_employee_count"]),
        rel_tol=1e-10,
    )
    assert r["source_sha256_composition"] == nta_sha
    assert r["source_sha256_statutory_amounts"]
    assert r["composition_year"] == "2024"
    assert r["statutory_amount_year"] == "2026"
    assert r["model_status"] == "EXTERNAL_SENSITIVITY_ONLY"

assert {int(r["decile"]) for r in age} == set(range(1, 11))
for r in age:
    share = float(r["age65p_share_of_public_pension_amount_proxy"])
    overlap = float(r["recap_count_overlap_ratio_to_all_age"])
    assert 0 <= share <= 1
    # The recap counts are intentionally documented as overlapping; they are
    # not silently forced to partition the all-age count.
    assert overlap >= 1.0
    assert r["source_sha256"] == f71551_sha
    assert r["model_status"] == "SENSITIVITY_PROXY_NOT_IDENTIFIED"
    assert "overlap" in r["identification_warning"]
    for c in [
        "all_age_household_count_source_cell",
        "age18_64_recap_household_count_source_cell",
        "age65p_recap_household_count_source_cell",
        "age18_64_public_pension_source_cell",
        "age65p_public_pension_source_cell",
    ]:
        assert r[c]

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_table17_and_f71551.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA Table17 / F71551 tests: OK "
    "(12 salary classes; 2026 dependent amounts; 10 decile pension-age proxies)"
)
