#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import math
import subprocess
import sys

import cryptography
import pypdf

ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "data/derived"
    / "nta_income_class_primary_type_filing_status_2024.csv"
)
SAMPLE = (
    ROOT
    / "data/derived"
    / "nta_positive_self_assessed_balance_income_class_primary_type_2024.csv"
)

CATEGORIES = {
    "business",
    "real_estate",
    "salary",
    "miscellaneous",
    "other",
}

EXPECTED = {
    "business": (3_785_184, 1_174_065, 962_359),
    "real_estate": (1_497_102, 804_398, 174_282),
    "salary": (11_423_587, 2_385_726, 7_697_018),
    "miscellaneous": (5_819_853, 411_376, 4_300_467),
    "other": (836_458, 382_695, 393_370),
}


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(OUT)
sample = {
    (int(r["income_class_index"]), r["primary_income_type"]):
        int(r["positive_self_assessed_balance_persons_estimated"])
    for r in read(SAMPLE)
}

assert len(rows) == 125
assert {r["primary_income_type"] for r in rows} == CATEGORIES
assert {int(r["income_class_index"]) for r in rows} == set(range(1, 26))

# Every class is a complete five-category partition for all/positive/refund.
grand_all = 0
grand_pos = 0
grand_refund = 0
grand_residual = 0

for i in range(1, 26):
    q = [r for r in rows if int(r["income_class_index"]) == i]
    assert len(q) == 5

    all_total = int(q[0]["income_class_all_categories_table22_population_persons"])
    pos_total = int(
        q[0]["income_class_all_categories_positive_self_assessed_balance_persons"]
    )
    refund_total = int(q[0]["income_class_all_categories_refund_persons"])

    assert all(
        int(r["income_class_all_categories_table22_population_persons"]) == all_total
        for r in q
    )
    assert all(
        int(r["income_class_all_categories_positive_self_assessed_balance_persons"])
        == pos_total
        for r in q
    )
    assert all(
        int(r["income_class_all_categories_refund_persons"]) == refund_total
        for r in q
    )

    assert sum(int(r["table22_population_persons"]) for r in q) == all_total
    assert sum(int(r["positive_self_assessed_balance_persons"]) for r in q) == pos_total
    assert sum(int(r["refund_persons"]) for r in q) == refund_total

    residual = sum(
        int(r["neither_positive_nor_refund_residual"]) for r in q
    )
    assert residual == all_total - pos_total - refund_total
    assert residual >= 0

    grand_all += all_total
    grand_pos += pos_total
    grand_refund += refund_total
    grand_residual += residual

assert grand_all == 23_362_184
assert grand_pos == 5_158_260
assert grand_refund == 13_527_496
assert grand_residual == 4_676_428

# Category totals reproduce Table 2-2(1) exact annual counts.
for category, expected in EXPECTED.items():
    q = [r for r in rows if r["primary_income_type"] == category]
    assert len(q) == 25
    got = (
        sum(int(r["table22_population_persons"]) for r in q),
        sum(int(r["positive_self_assessed_balance_persons"]) for r in q),
        sum(int(r["refund_persons"]) for r in q),
    )
    assert got == expected, (category, got, expected)

# All 125 positive-self-assessed-balance cells independently equal Sample Survey Table 2.
for r in rows:
    key = (int(r["income_class_index"]), r["primary_income_type"])
    pos = int(r["positive_self_assessed_balance_persons"])
    assert pos == sample[key]
    assert int(r["sample_survey_positive_self_assessed_balance_cell"]) == sample[key]
    assert int(r["sample_crosscheck_difference"]) == 0

    all_persons = int(r["table22_population_persons"])
    refund = int(r["refund_persons"])
    residual = int(r["neither_positive_nor_refund_residual"])
    assert all_persons == pos + refund + residual

    if all_persons:
        assert math.isclose(
            float(r["positive_self_assessed_balance_rate"]),
            pos / all_persons,
            rel_tol=1e-10,
        )
        assert math.isclose(
            float(r["refund_rate"]),
            refund / all_persons,
            rel_tol=1e-10,
        )
        assert math.isclose(
            float(r["residual_rate"]),
            residual / all_persons,
            rel_tol=1e-10,
        )
        assert math.isclose(
            float(r["positive_self_assessed_balance_rate"])
            + float(r["refund_rate"])
            + float(r["residual_rate"]),
            1.0,
            abs_tol=5e-10,
        )
    else:
        assert r["positive_self_assessed_balance_rate"] == ""
        assert r["refund_rate"] == ""
        assert r["residual_rate"] == ""

    assert r["cell_nature"] == "ADMINISTRATIVE_ANNUAL_STATISTICS_COUNT"
    assert r["evidence_status"] == "REPRODUCED_OFFICIAL_ADMINISTRATIVE_CROSSTAB"
    assert r["source_id"] == "NTA-R06"
    assert r["source_sha256"]
    assert r["source_printed_page"] in {"61", "62"}
    assert r["source_pdf_page_1based"] in {"71", "72"}
    assert r["pypdf_version"] == pypdf.__version__
    assert r["cryptography_version"] == cryptography.__version__
    assert "processed" in r["population_definition"]
    assert "not the stage-1 NTA Table 2-1 Final-return processing-row numerator" in r["denominator_note"]
    assert "F71561" in r["identification_warning"]
    assert "bridge assumption" in r["identification_warning"]

# Stable stage-2 rate anchors illustrate the substantial income-class gradient.
by_key = {
    (int(r["income_class_index"]), r["primary_income_type"]): r
    for r in rows
}
assert math.isclose(
    float(by_key[(1, "salary")]["positive_self_assessed_balance_rate"]),
    2218 / 942026,
    rel_tol=1e-10,
)
assert math.isclose(
    float(by_key[(12, "real_estate")]["positive_self_assessed_balance_rate"]),
    62030 / 62901,
    rel_tol=1e-10,
)
assert math.isclose(
    float(by_key[(25, "other")]["positive_self_assessed_balance_rate"]),
    66 / 67,
    rel_tol=1e-10,
)

subprocess.run(
    [
        sys.executable,
        str(ROOT / "scripts/extract_nta_annual_income_class_filing_status.py"),
        "--check",
    ],
    cwd=ROOT,
    check=True,
)

print(
    "NTA annual income-class filing-status tests: OK "
    "(25 x 5; exact annual margins; 125/125 sample positive-cell matches)"
)
