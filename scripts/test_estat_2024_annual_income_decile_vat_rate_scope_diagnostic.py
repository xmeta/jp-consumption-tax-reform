#!/usr/bin/env python3
if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/estat_2024_annual_income_decile_vat_rate_scope_diagnostic.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(OUT)
by = {int(r["annual_income_decile"]): r for r in rows}
assert len(rows) == 10 and set(by) == set(range(1, 11))
assert all(r["rank_concept"] == "HOUSEHOLD_ANNUAL_INCOME_DECILE" for r in rows)
assert all(r["rank_bridge_status"] == "NOT_LINKED_DO_NOT_TREAT_AS_OBJECTIVE_DECILE" for r in rows)
assert by[1]["food_yen_month"] == "39658"
assert by[1]["alcohol_yen_month"] == "1414"
assert by[1]["dining_out_yen_month"] == "5049"
assert by[1]["newspaper_yen_month"] == "1421"
assert by[1]["reduced_rate_scope_proxy_core_yen_month"] == "33195"
assert by[1]["reduced_rate_scope_proxy_with_all_newspaper_yen_month"] == "34616"
assert by[10]["reduced_rate_scope_proxy_core_yen_month"] == "80594"
assert by[10]["reduced_rate_scope_proxy_with_all_newspaper_yen_month"] == "82537"
assert float(by[1]["reduced_rate_scope_proxy_core_share_of_consumption"]) > float(by[10]["reduced_rate_scope_proxy_core_share_of_consumption"])
for r in rows:
    assert r["rate_scope_proxy_status"] == "SURVEY_CATEGORY_PROXY_NOT_TRANSACTION_LEVEL_VAT_BASE"
    assert r["actual_vat_base_status"].startswith("NOT_IDENTIFIED_")
    assert int(r["reduced_rate_scope_proxy_core_yen_month"]) <= int(r["reduced_rate_scope_proxy_with_all_newspaper_yen_month"])
subprocess.run(
    [sys.executable, str(ROOT / "scripts/build_estat_2024_annual_income_decile_vat_rate_scope_diagnostic.py"), "--check"],
    cwd=ROOT,
    check=True,
)
print("VAT rate-scope diagnostic tests: OK (10 deciles; food/alcohol/dining/newspaper proxy; actual VAT base not identified)")
