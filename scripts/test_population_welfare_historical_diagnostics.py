#!/usr/bin/env python3
if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests; assertions must remain active")

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/population_welfare_historical_diagnostics.csv"

with OUT.open(encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))


def one(metric_id):
    hits = [r for r in rows if r["metric_id"] == metric_id]
    assert len(hits) == 1
    return hits[0]

assert float(one("real_gdp_growth")["value"]) < 0
assert float(one("real_gdp_per_capita_growth")["value"]) > 0
assert abs(float(one("gdp_person_productivity_identity_residual")["value"])) < 1e-8
assert one("gdp_deflator")["source_ids"] == "ESRI-SNA-2024-GDP-DEFLATOR-CY"
assert one("cpi_all_items")["source_ids"] == "ESTAT-CPI-2024-NATIONAL-ALL-ITEMS"
assert float(one("equivalized_disposable_income_gini")["value"]) == 0.3233
assert one("median_equivalized_disposable_income")["identification_status"] == (
    "OBSERVED_HOUSEHOLD_QUANTILE_NOT_HEADLINE_PERSON_WEIGHTED_EFFECT"
)
assert one("fgt2_relative")["value"] == ""
assert one("fgt2_relative")["identification_status"] == "NOT_IDENTIFIED_FROM_AGGREGATE_PUBLICATION"
assert all(r["optimizer_usable"] == "false" for r in rows)

subprocess.run(
    [sys.executable, str(ROOT / "scripts/build_population_welfare_historical_diagnostics.py"), "--check"],
    cwd=ROOT,
    check=True,
)
print("population/welfare historical diagnostics tests: OK")
