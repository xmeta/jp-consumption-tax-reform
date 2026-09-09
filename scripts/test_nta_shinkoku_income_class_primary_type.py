#!/usr/bin/env python3
from pathlib import Path
import csv
import math
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "data/derived"
    / "nta_positive_self_assessed_balance_income_class_primary_type_2024.csv"
)
STAGE2 = ROOT / "data/derived/nta_primary_type_stage2_2024.csv"

CATEGORIES = {
    "business",
    "real_estate",
    "salary",
    "miscellaneous",
    "other",
}
EXPECTED_TOTALS = {
    "business": 1_174_065,
    "real_estate": 804_398,
    "salary": 2_385_726,
    "miscellaneous": 411_376,
    "other": 382_695,
}


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(OUT)
stage2 = {
    r["primary_income_type"]: int(r["positive_self_assessed_balance_persons_exact"])
    for r in read(STAGE2)
}

assert len(rows) == 125
assert {r["primary_income_type"] for r in rows} == CATEGORIES
assert {int(r["income_class_index"]) for r in rows} == set(range(1, 26))

# Each income class is a full five-category partition of the survey-estimated
# positive-self-assessed-balance population.
grand = 0
for i in range(1, 26):
    q = [r for r in rows if int(r["income_class_index"]) == i]
    assert len(q) == 5
    assert {r["primary_income_type"] for r in q} == CATEGORIES
    total = int(q[0]["income_class_positive_self_assessed_balance_total_estimated"])
    assert total > 0
    assert all(
        int(r["income_class_positive_self_assessed_balance_total_estimated"]) == total
        for r in q
    )
    assert sum(int(r["positive_self_assessed_balance_persons_estimated"]) for r in q) == total
    assert math.isclose(
        sum(float(r["share_within_income_class"]) for r in q),
        1.0,
        abs_tol=5e-10,
    )
    grand += total

assert grand == 5_158_260

# Category totals reconcile exactly to the independently reproduced annual
# administrative positive-self-assessed-balance category totals.
for category in CATEGORIES:
    q = [r for r in rows if r["primary_income_type"] == category]
    assert len(q) == 25
    observed = sum(int(r["positive_self_assessed_balance_persons_estimated"]) for r in q)
    assert observed == EXPECTED_TOTALS[category]
    assert observed == stage2[category]
    assert all(
        int(r["category_positive_self_assessed_balance_total"]) == observed
        for r in q
    )
    assert math.isclose(
        sum(float(r["share_within_primary_type"]) for r in q),
        1.0,
        abs_tol=5e-10,
    )

# Bounds are monotone and only the last class is open-ended/top-coded.
by_class = {}
for r in rows:
    by_class.setdefault(int(r["income_class_index"]), r)

prev_upper = None
for i in range(1, 26):
    r = by_class[i]
    lower = r["lower_bound_yen_exclusive"]
    upper = r["upper_bound_yen_inclusive"]
    top = r["is_topcoded"]
    if i == 1:
        assert lower == ""
    else:
        assert int(lower) == prev_upper
    if i < 25:
        assert top == "False"
        assert upper != ""
        current_upper = int(upper)
        assert current_upper > (prev_upper or -1)
        prev_upper = current_upper
    else:
        assert top == "True"
        assert upper == ""

# Source locators and SHA provenance are fully populated.
cells = [r["source_cell"] for r in rows]
assert len(cells) == len(set(cells))
assert "D37" in cells
assert "D72" in cells
assert "D100" in cells
assert "D135" in cells
assert "D163" in cells

xlsx_shas = {r["source_sha256_xlsx"] for r in rows}
pdf_shas = {r["visual_source_sha256_pdf"] for r in rows}
assert len(xlsx_shas) == 1 and next(iter(xlsx_shas))
assert len(pdf_shas) == 1 and next(iter(pdf_shas))

for r in rows:
    assert r["cell_nature"] == "SURVEY_ESTIMATED_POPULATION_CELL"
    assert r["evidence_status"] == "REPRODUCED_OFFICIAL_SURVEY_ESTIMATE_CROSSTAB"
    assert "F71561" in r["identification_warning"]
    assert "transport assumption" in r["identification_warning"]
    assert r["target_population"].endswith(
        "persons with positive self-assessed income tax"
    )

# A few stable anchors from the official workbook.
anchors = {
    (1, "business"): 5797,
    (1, "other"): 947,
    (12, "salary"): 165535,
    (18, "other"): 26729,
    (25, "other"): 66,
}
by_key = {
    (int(r["income_class_index"]), r["primary_income_type"]): r
    for r in rows
}
for key, expected in anchors.items():
    assert int(by_key[key]["positive_self_assessed_balance_persons_estimated"]) == expected

subprocess.run(
    [
        sys.executable,
        str(ROOT / "scripts/extract_nta_shinkoku_income_class_primary_type.py"),
        "--check",
    ],
    cwd=ROOT,
    check=True,
)

print(
    "NTA income-class x primary-type tests: OK "
    "(25 classes x 5 types; row/column reconciliation; 5,158,260 total)"
)
