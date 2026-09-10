#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import math
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGE2 = ROOT / "data/derived/nta_primary_type_stage2_2024.csv"
T31 = ROOT / "data/derived/nta_table31_primary_type_rounded_2024.csv"
VALID = (
    ROOT
    / "research/income_tax_partial_identification"
    / "nta_table31_composition_validation.csv"
)
CATEGORIES = {"business", "real_estate", "salary", "miscellaneous", "other"}


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


stage2 = read(STAGE2)
t31 = read(T31)
valid = read(VALID)

assert len(stage2) == len(t31) == len(valid) == 5
assert {r["primary_income_type"] for r in stage2} == CATEGORIES
assert {r["primary_income_type"] for r in t31} == CATEGORIES
assert {r["primary_income_type"] for r in valid} == CATEGORIES

assert sum(int(r["table22_population_persons_exact"]) for r in stage2) == 23_362_184
assert all(
    r["final_return_persons_exact"] == r["table22_population_persons_exact"]
    for r in stage2
)
assert sum(int(r["positive_self_assessed_balance_persons_exact"]) for r in stage2) == 5_158_260
assert sum(int(r["refund_persons_exact"]) for r in stage2) == 13_527_496

for r in stage2:
    total = int(r["table22_population_persons_exact"])
    pos = int(r["positive_self_assessed_balance_persons_exact"])
    refund = int(r["refund_persons_exact"])
    residual = int(r["zero_or_other_persons_exact_residual"])
    assert total == pos + refund + residual
    rate = float(r["positive_self_assessed_balance_rate"])
    assert math.isclose(rate, pos / total, rel_tol=1e-11)
    assert 0 <= rate <= 1
    assert r["source_id"] == "NTA-R06"
    assert r["source_sha256"]
    assert "processed" in r["population_definition"]
    assert "stage-1 Table 2-1 Final-return processing-row numerator" in r["interpretation"]
    assert "not F71561" in r["interpretation"]

displayed_pos = sum(
    int(r["positive_self_assessed_balance_thousand_displayed"]) for r in t31
)
displayed_total = sum(
    int(r["final_return_thousand_displayed"]) for r in t31
)
displayed_refund = sum(int(r["refund_thousand_displayed"]) for r in t31)
displayed_zero = sum(int(r["zero_thousand_displayed"]) for r in t31)
assert displayed_pos == 5_174
assert displayed_total == 23_390
assert displayed_refund == 13_534
assert displayed_zero == 4_681

for r in t31:
    assert int(r["displayed_positive_self_assessed_balance_grand_total_thousand"]) == 5_175
    assert int(r["five_category_minus_grand_total_thousand"]) == -1
    assert "renormalizes displayed five categories" in r["rounding_note"]

shares_exact = sum(float(r["annual_positive_self_assessed_balance_composition_exact"]) for r in valid)
shares_t31 = sum(
    float(r["table31_positive_self_assessed_balance_composition_five_category_normalized"])
    for r in valid
)
assert math.isclose(shares_exact, 1.0, abs_tol=1e-10)
assert math.isclose(shares_t31, 1.0, abs_tol=1e-10)

max_abs = max(float(r["absolute_difference_percentage_point"]) for r in valid)
assert math.isclose(max_abs, 0.0844360351758805, rel_tol=0, abs_tol=5e-12)
assert round(max_abs, 5) == 0.08444
assert max_abs < 0.1
for r in valid:
    assert r["validation_status"] == "CROSS_PUBLICATION_POINT_CHECK_ONLY"
    assert "not statistical coverage" in r["interpretation"]

# The category that determines the historical max is miscellaneous income.
worst = max(valid, key=lambda r: float(r["absolute_difference_percentage_point"]))
assert worst["primary_income_type"] == "miscellaneous"

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_stage2_holdout.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA stage2/holdout tests: OK "
    "(5 primary types; exact stage2 rates; 0.08444pp rounded-table point check reproduced)"
)
