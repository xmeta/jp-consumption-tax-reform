#!/usr/bin/env python3
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
M = ROOT / "data/derived/vat_fiscal_receipt_reference.csv"
S = ROOT / "data/derived/vat_policy_fiscal_replacement_reference.csv"
C = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


metrics = {r["metric_id"]: r for r in read(M)}
scenarios = {r["scenario_id"]: r for r in read(S)}
catalog = {r["source_id"]: r for r in read(C)}

assert len(metrics) == 5
assert len(scenarios) == 8
assert metrics["fy2024_total_tax_receipts_yen"]["value"] == "74187865765000"
assert metrics["fy2024_consumption_tax_receipts_yen"]["value"] == "25021206715000"
assert metrics["fy2024_consumption_tax_budget_yen"]["value"] == "24343000000000"
assert metrics["fy2024_consumption_tax_receipts_minus_budget_yen"]["value"] == "678206715000"
assert metrics["fy2024_consumption_tax_share_of_total_tax_receipts"]["value"] == "0.337268183375"
assert metrics["fy2024_consumption_tax_receipts_yen"]["model_use"] == "STATIC_VAT_REPLACEMENT_SCALE_REFERENCE"

assert scenarios["current_8_10"]["static_consumption_tax_receipt_effect_yen"] == "0"
assert scenarios["current_8_10"]["gross_replacement_requirement_reference_yen"] == "0"
assert scenarios["reduced_5"]["static_consumption_tax_receipt_effect_yen"] == ""
assert scenarios["reduced_5"]["gross_replacement_requirement_reference_yen"] == ""
assert scenarios["reduced_5"]["fiscal_reference_status"] == "NOT_IDENTIFIED_RATE_BASE_MIX_AND_BEHAVIOR_REQUIRED"

for sid in (
    "zero_rate_admin_retained", "full_abolition", "full_abolition_jgb",
    "full_abolition_income_tax", "full_abolition_asset_tax", "full_abolition_mixed",
):
    assert scenarios[sid]["static_consumption_tax_receipt_effect_yen"] == "-25021206715000"
    assert scenarios[sid]["gross_replacement_requirement_reference_yen"] == "25021206715000"
assert scenarios["full_abolition_jgb"]["full_jgb_financing_reference_yen"] == "25021206715000"
assert scenarios["full_abolition_jgb"]["replacement_tax_target_reference_yen"] == ""
for sid in ("full_abolition_income_tax", "full_abolition_asset_tax", "full_abolition_mixed"):
    assert scenarios[sid]["replacement_tax_target_reference_yen"] == "25021206715000"
    assert scenarios[sid]["full_jgb_financing_reference_yen"] == ""

assert catalog["MOF-FY2024-TREASURY-REVENUE-2025-07"]["sha256"] == "20670bb317eeef1e69a8a910cb43efc50b7df7ae58c6324a23909c7433f1c243"

subprocess.run(
    [
        sys.executable,
        str(ROOT / "research/vat_policy_integration/build_vat_fiscal_replacement_reference.py"),
        "--check",
    ],
    cwd=ROOT,
    check=True,
)
print(
    "VAT fiscal replacement reference tests: OK "
    "(FY2024 receipts parsed from MOF HTML; 0/full-abolition static gap mapped; 5% not linearly imputed)"
)
