#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import math
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/nta_positive_self_assessed_balance_tax_flow_income_class_primary_type_2024.csv"
CROSS = ROOT / "data/derived/nta_positive_self_assessed_balance_income_class_primary_type_2024.csv"

CATEGORIES = {"business", "real_estate", "salary", "miscellaneous", "other"}


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(OUT)
cross = {
    (int(r["income_class_index"]), r["primary_income_type"]): r
    for r in read(CROSS)
}

assert len(rows) == 125
assert {r["primary_income_type"] for r in rows} == CATEGORIES
assert {int(r["income_class_index"]) for r in rows} == set(range(1, 26))
assert len({(r["income_class_index"], r["primary_income_type"]) for r in rows}) == 125

# The tax-flow cells are the same positive-self-assessed-balance population
# partition as the already independently reconciled Table 2 cross-tab.
for r in rows:
    key = (int(r["income_class_index"]), r["primary_income_type"])
    assert int(r["positive_self_assessed_balance_persons_estimated"]) == int(
        cross[key]["positive_self_assessed_balance_persons_estimated"]
    )
    assert r["income_class_label"] == cross[key]["income_class_label"]
    assert r["cell_nature"] == (
        "SURVEY_ESTIMATED_POSITIVE_SELF_ASSESSED_BALANCE_TAX_FLOW_CELL"
    )
    assert r["evidence_status"] == "REPRODUCED_OFFICIAL_SURVEY_TAX_FLOW_DIAGNOSTIC"
    assert "already conditioned" in r["identification_warning"]
    assert "F71561" in r["identification_warning"]

# Exposure measures are conditional on the positive-balance survey target and
# therefore must be proper shares; they are not filing probabilities.
for r in rows:
    for c in (
        "tax_credit_exposure_share_within_positive_balance",
        "source_withholding_exposure_share_within_positive_balance",
        "self_assessed_balance_share_of_pre_withholding_tax",
    ):
        x = float(r[c])
        assert -1e-12 <= x <= 1.0 + 1e-12

# Positive-balance persons reconcile exactly; monetary sums across rounded
# category-by-class cells can differ from printed grand totals by a few million
# yen because every published cell is rounded independently.
assert sum(int(r["positive_self_assessed_balance_persons_estimated"]) for r in rows) == 5_158_260

expected_grand = {
    "calculated_income_tax_million_yen": 8_044_571.0,
    "tax_credits_million_yen": 352_866.0,
    "source_withholding_persons_estimated": 3_302_359.0,
    "source_withholding_tax_million_yen": 3_446_992.0,
    "self_assessed_balance_million_yen": 4_406_942.0,
}
for col, expected in expected_grand.items():
    observed = sum(float(r[col]) for r in rows)
    tolerance = 0.0 if col.endswith("persons_estimated") else 5.0
    assert abs(observed - expected) <= tolerance, (col, observed, expected)

# Table 1 implies a reconstruction-special-income-tax component:
# withholding + self-assessed balance - (calculated tax - tax credits).
# At aggregate scale its rate on post-credit income tax is close to the
# statutory 2.1%; cell-level rates are noisier because published amounts are
# rounded to million yen.
post_credit = sum(float(r["post_credit_income_tax_million_yen"]) for r in rows)
implied_reconstruction = sum(
    float(r["implied_reconstruction_special_income_tax_million_yen"]) for r in rows
)
rate = implied_reconstruction / post_credit
assert 0.0205 <= rate <= 0.0217, rate

# Withholding is common within the positive-balance target and especially high
# for salary-primary taxpayers.  This is a descriptive within-NTA diagnostic,
# not a cross-system identifying assumption.
salary = [r for r in rows if r["primary_income_type"] == "salary"]
salary_n = sum(int(r["positive_self_assessed_balance_persons_estimated"]) for r in salary)
salary_w = sum(int(r["source_withholding_persons_estimated"]) for r in salary)
assert salary_w / salary_n > 0.85

all_n = sum(int(r["positive_self_assessed_balance_persons_estimated"]) for r in rows)
all_w = sum(int(r["source_withholding_persons_estimated"]) for r in rows)
assert 0.60 < all_w / all_n < 0.70

# Stable source-cell anchors.
by_key = {
    (int(r["income_class_index"]), r["primary_income_type"]): r
    for r in rows
}
anchors = {
    (1, "business"): ("50", "3", "809", "11", "37"),
    (12, "salary"): ("143786", "16341", "162615", "89054", "41070"),
    (25, "other"): ("254371", "2937", "63", "19222", "237494"),
}
for key, expected in anchors.items():
    r = by_key[key]
    observed = (
        r["calculated_income_tax_million_yen"],
        r["tax_credits_million_yen"],
        r["source_withholding_persons_estimated"],
        r["source_withholding_tax_million_yen"],
        r["self_assessed_balance_million_yen"],
    )
    assert observed == expected, (key, observed, expected)

# Provenance is complete and each workbook has one pinned SHA across all cells.
for c in (
    "source_sha256_table1",
    "source_sha256_table4",
    "source_sha256_table5",
):
    vals = {r[c] for r in rows}
    assert len(vals) == 1 and next(iter(vals))

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_positive_balance_tax_flow.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA positive-balance tax-flow tests: OK "
    "(125 cells; Table 1/4/5 exact cell joins; 5,158,260 target persons; "
    f"aggregate implied reconstruction-tax rate={rate:.6%})"
)
