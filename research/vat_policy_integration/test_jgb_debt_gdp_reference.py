#!/usr/bin/env python3
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/derived/vat_jgb_debt_gdp_reference.csv"
CAT = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = {r["scenario_id"]: r for r in read(OUT)}
catalog = {r["source_id"]: r for r in read(CAT)}

assert len(rows) == 8
assert all(r["fy2024_nominal_gdp_yen"] == "642414700000000" for r in rows.values())
jgb = rows["full_abolition_jgb"]
assert jgb["full_jgb_financing_reference_yen"] == "25021206715000"
assert jgb["static_incremental_jgb_financing_share_of_fy2024_nominal_gdp"] == "0.038948683327"
assert jgb["static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp"] == "3.894868333"
assert jgb["debt_gdp_reference_status"] == "STATIC_INCREMENTAL_JGB_FINANCING_SHARE_OF_FY2024_NOMINAL_GDP"
for sid, row in rows.items():
    if sid == "full_abolition_jgb":
        continue
    assert row["full_jgb_financing_reference_yen"] == ""
    assert row["static_incremental_jgb_financing_share_of_fy2024_nominal_gdp"] == ""
    assert row["static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp"] == ""
    assert row["debt_gdp_reference_status"] == "NOT_APPLICABLE_OR_JGB_SHARE_NOT_DEFINED_FOR_THIS_SCENARIO"

assert catalog["ESRI-SNA-2024-NOMINAL-GDP-FISCAL-YEAR"]["sha256"] == "a0cd9e5e973360e704c2a4abbe3208239884559310d4df045c345cc3b9f17ae5"

subprocess.run(
    [
        sys.executable,
        str(ROOT / "research/vat_policy_integration/build_jgb_debt_gdp_reference.py"),
        "--check",
    ],
    cwd=ROOT,
    check=True,
)
print(
    "JGB debt/GDP reference tests: OK "
    "(FY2024 nominal GDP 642.4147tr JPY; full-JGB static financing reference 3.894868333% of GDP)"
)
