#!/usr/bin/env python3
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/estat_2024_annual_income_decile_expenditure_diagnostic.csv"
CAT = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(OUT)
by = {int(r["annual_income_decile"]): r for r in rows}
catalog = {r["source_id"]: r for r in read(CAT)}

assert len(rows) == 10
assert set(by) == set(range(1, 11))
assert all(r["rank_concept"] == "HOUSEHOLD_ANNUAL_INCOME_DECILE" for r in rows)
assert all(
    r["rank_bridge_status"] == "NOT_LINKED_DO_NOT_TREAT_AS_OBJECTIVE_DECILE"
    for r in rows
)
assert all(r["population_households"] == "5355441" for r in rows)
assert [by[d]["approx_sample_households"] for d in range(1, 11)] == [
    "2920", "3100", "3820", "4100", "4030",
    "4010", "4350", "4520", "4480", "4250",
]
assert [by[d]["monthly_consumption_expenditure_yen"] for d in range(1, 11)] == [
    "129460", "165620", "190968", "211445", "230625",
    "239100", "267551", "298918", "339084", "439645",
]
assert [by[d]["food_yen"] for d in range(1, 11)] == [
    "39658", "47640", "56053", "63863", "64802",
    "70159", "77140", "86895", "94293", "114333",
]
assert [by[d]["annual_income_decile_upper_10k_yen"] for d in range(1, 11)] == [
    "186", "259", "328", "400", "483", "577", "699", "850", "1100", "",
]
assert by[10]["annual_income_upper_status"] == "OPEN_TOP_DECILE_NO_UPPER_BOUND"
assert by[1]["household_members"] == "1.18"
assert by[10]["household_members"] == "3.26"
assert by[1]["household_head_age"] == "66.7"
assert by[10]["household_head_age"] == "53.8"
assert by[1]["major_category_rounding_gap_yen"] == "0"
assert by[2]["major_category_rounding_gap_yen"] == "1"
assert by[5]["major_category_rounding_gap_yen"] == "-1"
assert max(abs(int(r["major_category_rounding_gap_yen"])) for r in rows) <= 1
assert by[1]["food_share_of_consumption"] == "0.306334002781"
assert by[10]["food_share_of_consumption"] == "0.26005754643"
assert by[1]["consumption_relative_to_all_household_average"] == "0.51528008852"
assert by[10]["consumption_relative_to_all_household_average"] == "1.749886563552"

for r in rows:
    assert r["vat_base_status"] == (
        "NOT_IDENTIFIED_BROAD_FOOD_INCLUDES_ALCOHOL_AND_EATING_OUT_OTHER_EXEMPTIONS_UNMAPPED"
    )
    assert r["gini_fgt2_use"] == (
        "PROHIBITED_DIRECT_MAPPING_WITHOUT_RANK_BRIDGE_AND_VAT_INCIDENCE_MODEL"
    )
    assert r["scientific_status"] == "OBSERVED_ANNUAL_INCOME_DECILE_EXPENDITURE_DIAGNOSTIC"

assert catalog["ESTAT-NSFCW-2024-T1-21-ANNUAL-INCOME-DECILE-EXPENDITURE"]["sha256"] == (
    "189e1e777ffa8aed1a37f26709c8918dc35a2adfe42126465b973ac6f6f5acb0"
)
subprocess.run(
    [
        sys.executable,
        str(ROOT / "scripts/build_estat_2024_annual_income_decile_expenditure_diagnostic.py"),
        "--check",
    ],
    cwd=ROOT,
    check=True,
)
print(
    "NSFCW annual-income-decile expenditure diagnostic tests: OK "
    "(10 deciles; 129,460 to 439,645 JPY/month; annual-income rank kept separate from objective rank)"
)
