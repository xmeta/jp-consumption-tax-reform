#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')

from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/macro/real_gdp_quarterly.csv"
SOURCE_ID = "ESRI-QE-2026Q2-2-REAL-QOQ"

with DATA.open(encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

assert len(rows) == 130
assert rows[0]["quarter"] == "1994-Q1"
assert rows[0]["status"] == "source_baseline_no_qoq"
assert rows[0]["real_gdp_growth_qoq"] == ""
assert rows[-1]["quarter"] == "2026-Q2"
assert sum(r["status"] == "observed" for r in rows) == 129
assert all(r["source_id"] == SOURCE_ID for r in rows)
assert all(r["revision_date"] == "2026-09-08" for r in rows)
print("CAO quarterly real GDP dataset: OK (1994-Q1 baseline + 129 observed QoQ rates through 2026-Q2)")
