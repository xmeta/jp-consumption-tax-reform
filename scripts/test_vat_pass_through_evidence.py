#!/usr/bin/env python3
if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv, subprocess, sys
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/vat_pass_through_evidence.csv"

def read(path):
    with path.open(encoding="utf-8", newline="") as f: return list(csv.DictReader(f))
rows = read(OUT); by = {r["evidence_id"]: r for r in rows}
assert len(rows) == 5 and len(by) == 5
assert by["PT-2014-POS-HETEROGENEITY"]["identification_status"] == "OBSERVED_HISTORICAL_MICRO_HETEROGENEITY"
assert by["PT-2014-POS-HETEROGENEITY"]["pass_through_point"] == ""
assert by["PT-2019-BOJ-FULL-PASS-THROUGH-ASSUMPTION"]["pass_through_point"] == "1"
assert by["PT-2019-BOJ-FULL-PASS-THROUGH-ASSUMPTION"]["identification_status"] == "MECHANICAL_ASSUMPTION_NOT_EMPIRICAL_ESTIMATE"
assert by["QR-2014-CAO-FRONTLOAD-REBOUND"]["quantity_effect_low"] == "2500000000000"
assert by["QR-2014-CAO-FRONTLOAD-REBOUND"]["quantity_effect_high"] == "3300000000000"
assert by["QR-2014-CAO-FRONTLOAD-REBOUND"]["quantity_response_status"] == "TEMPORARY_FRONTLOAD_AND_REBOUND_NOT_STEADY_STATE_ELASTICITY"
assert by["BASE-2019-MOF-RATE-SCOPE"]["vat_base_status"] == "STANDARD_AND_REDUCED_RATE_SCOPE_RULE_IDENTIFIED_HOUSEHOLD_EXPENDITURE_SHARES_NOT_IDENTIFIED"
for r in rows:
    assert "ABOLITION_PARAMETER" not in r["identification_status"]
    if r["evidence_dimension"] == "PRICE_PASS_THROUGH" and r["identification_status"].startswith("OBSERVED"):
        assert r["pass_through_point"] == ""
subprocess.run([sys.executable, str(ROOT / "scripts/build_vat_pass_through_evidence.py"), "--check"], cwd=ROOT, check=True)
print("VAT pass-through evidence tests: OK (historical heterogeneity; BOJ assumption separated; quantity timing and base uncertainty explicit)")
