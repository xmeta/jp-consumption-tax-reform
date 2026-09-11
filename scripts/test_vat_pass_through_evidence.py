#!/usr/bin/env python3
if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv, subprocess, sys
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/vat_pass_through_evidence.csv"
AUDIT = ROOT / "data/derived/vat_rate_cut_transport_audit.csv"

def read(path):
    with path.open(encoding="utf-8", newline="") as f: return list(csv.DictReader(f))
rows = read(OUT); by = {r["evidence_id"]: r for r in rows}
audit = {r["metric_id"]: r for r in read(AUDIT)}
assert len(rows) == 7 and len(by) == 7
assert len(audit) == 8
assert by["PT-2014-POS-HETEROGENEITY"]["identification_status"] == "OBSERVED_HISTORICAL_MICRO_HETEROGENEITY"
assert by["PT-2014-POS-HETEROGENEITY"]["pass_through_point"] == ""
assert by["PT-2019-BOJ-FULL-PASS-THROUGH-ASSUMPTION"]["pass_through_point"] == "1"
assert by["PT-2019-BOJ-FULL-PASS-THROUGH-ASSUMPTION"]["identification_status"] == "MECHANICAL_ASSUMPTION_NOT_EMPIRICAL_ESTIMATE"
assert by["QR-2014-CAO-FRONTLOAD-REBOUND"]["quantity_effect_low"] == "2500000000000"
assert by["QR-2014-CAO-FRONTLOAD-REBOUND"]["quantity_effect_high"] == "3300000000000"
assert by["QR-2014-CAO-FRONTLOAD-REBOUND"]["quantity_response_status"] == "TEMPORARY_FRONTLOAD_AND_REBOUND_NOT_STEADY_STATE_ELASTICITY"
assert by["BASE-2019-MOF-RATE-SCOPE"]["vat_base_status"] == "STANDARD_AND_REDUCED_RATE_SCOPE_RULE_IDENTIFIED_HOUSEHOLD_EXPENDITURE_SHARES_NOT_IDENTIFIED"
assert by["PT-2020-GERMANY-TEMP-CUT"]["pass_through_point"] == "0.70"
assert by["PT-2020-GERMANY-TEMP-CUT"]["policy_transfer_status"] == "EXTERNAL_SENSITIVITY_ONLY_NO_JAPAN_PARAMETER_OR_BOUND"
assert by["QR-2008-UK-TEMP-CUT"]["quantity_effect_low"] == "0.01"
assert by["QR-2008-UK-TEMP-CUT"]["quantity_response_status"] == "TEMPORARY_INTERTEMPORAL_SUBSTITUTION_NOT_STEADY_STATE_RESPONSE"
assert audit["japan_nationwide_standard_rate_cut_episode"]["value"] == "NONE_IN_ENUMERATED_1989_2019_STANDARD_RATE_HISTORY"
assert audit["increase_to_decrease_symmetry_status"]["value"] == "NOT_ADOPTED"
assert audit["japan_5_0_abolition_pass_through_parameter"]["value"] == "NOT_IDENTIFIED"
assert audit["japan_5_0_abolition_pass_through_parameter"]["japan_policy_parameter_effect"] == "KEEP_POLICY_MATRIX_PARAMETER_BLANK"
assert audit["rate_cut_public_search_stop"]["value"] == "STOP_GENERAL_RATE_CUT_EVIDENCE_ACCUMULATION"
for r in rows:
    assert "ABOLITION_PARAMETER" not in r["identification_status"]
    if r["evidence_dimension"] == "PRICE_PASS_THROUGH" and r["identification_status"].startswith("OBSERVED"):
        assert r["pass_through_point"] == ""
subprocess.run([sys.executable, str(ROOT / "scripts/build_vat_pass_through_evidence.py"), "--check"], cwd=ROOT, check=True)
print("VAT pass-through evidence tests: OK (Japan cut parameter unidentified; external temporary-cut evidence sensitivity-only; symmetry not assumed)")
