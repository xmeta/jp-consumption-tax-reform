#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
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
assert all(r["fy2024_end_general_government_gross_debt_yen"] == "1361030100000000" for r in rows.values())
assert all(r["fy2024_end_general_government_gross_debt_gdp_ratio"] == "2.118616059066" for r in rows.values())
assert all(r["fy2024_end_general_government_gross_debt_gdp_pct"] == "211.861605907" for r in rows.values())
assert all(r["baseline_debt_status"] == "OBSERVED_FY2024_END_GENERAL_GOVERNMENT_GROSS_DEBT_TO_FY2024_NOMINAL_GDP" for r in rows.values())
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
assert catalog["ESRI-SDDSPLUS-GGD-2026Q1"]["sha256"] == "85f50cc10893bcb43c208d4298fd59d770855bcaba283c4e8bc45747005e3285"
assert catalog["ESRI-SDDSPLUS-GGD-NOTES"]["sha256"] == "f3567fbe563c074538ec81531927152174d09980a1c2a79269ad7cc274932b21"

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
    "(FY2024-end GGD/GDP 211.861605907%; full-JGB static financing reference 3.894868333% of GDP)"
)
