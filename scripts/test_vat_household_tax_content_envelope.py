#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/vat_household_tax_content_envelope.csv"
CAT = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(OUT)
catalog = {r["source_id"]: r for r in read(CAT)}
assert len(rows) == 80
assert {int(r["annual_income_decile"]) for r in rows} == set(range(1, 11))
assert len({r["scenario_id"] for r in rows}) == 8
assert all(r["rank_concept"] == "HOUSEHOLD_ANNUAL_INCOME_DECILE" for r in rows)
assert all(
    r["rank_bridge_status"] == "NOT_LINKED_DO_NOT_TREAT_AS_OBJECTIVE_DECILE"
    for r in rows
)


def row(sid, decile):
    hits = [r for r in rows if r["scenario_id"] == sid and int(r["annual_income_decile"]) == decile]
    assert len(hits) == 1
    return hits[0]

for decile in (1, 10):
    assert row("current_8_10", decile)["current_standard_rate"] == "0.10"
    assert row("current_8_10", decile)["current_reduced_rate"] == "0.08"

assert row("current_8_10", 1)["current_embedded_consumption_tax_upper_bound_yen_month_ceiling"] == "11770"
assert row("current_8_10", 10)["current_embedded_consumption_tax_upper_bound_yen_month_ceiling"] == "39968"
assert row("current_8_10", 1)["current_embedded_consumption_tax_upper_bound_yen_year_ceiling"] == "141230"
assert row("current_8_10", 10)["current_embedded_consumption_tax_upper_bound_yen_year_ceiling"] == "479613"

assert row("current_8_10", 1)["mechanical_price_relief_share_current_spending_envelope"] == "0"
assert row("current_8_10", 1)["mechanical_price_relief_upper_envelope_yen_month_ceiling"] == "0"
assert row("reduced_5", 1)["scenario_rate_envelope"] == "0.05"
assert row("reduced_5", 1)["maximum_standard_rate_reduction"] == "0.05"
assert row("reduced_5", 1)["mechanical_price_relief_share_current_spending_envelope"] == "0.045454545455"
assert row("reduced_5", 1)["mechanical_price_relief_upper_envelope_yen_month_ceiling"] == "5885"
assert row("reduced_5", 10)["mechanical_price_relief_upper_envelope_yen_month_ceiling"] == "19984"
assert row("reduced_5", 1)["mechanical_price_relief_upper_envelope_yen_year_ceiling"] == "70615"
assert row("reduced_5", 10)["mechanical_price_relief_upper_envelope_yen_year_ceiling"] == "239807"
for sid in (
    "zero_rate_admin_retained",
    "full_abolition",
    "full_abolition_jgb",
    "full_abolition_income_tax",
    "full_abolition_asset_tax",
    "full_abolition_mixed",
):
    assert row(sid, 1)["scenario_rate_envelope"] == "0"
    assert row(sid, 1)["maximum_standard_rate_reduction"] == "0.10"
    assert row(sid, 1)["mechanical_price_relief_share_current_spending_envelope"] == "0.090909090909"
    assert row(sid, 1)["mechanical_price_relief_upper_envelope_yen_month_ceiling"] == "11770"
    assert row(sid, 10)["mechanical_price_relief_upper_envelope_yen_month_ceiling"] == "39968"
    assert row(sid, 1)["mechanical_price_relief_upper_envelope_yen_year_ceiling"] == "141230"
    assert row(sid, 10)["mechanical_price_relief_upper_envelope_yen_year_ceiling"] == "479613"

for r in rows:
    assert r["current_embedded_consumption_tax_lower_bound_yen_month"] == "0"
    assert r["tax_content_bound_status"] == "ACCOUNTING_UPPER_BOUND_FROM_10_PERCENT_STATUTORY_RATE_CAP"
    assert r["price_relief_envelope_status"] == (
        "STATIC_CURRENT_BASKET_FULL_PASS_THROUGH_NO_OVERSHIFT_ENVELOPE_NOT_ACTUAL_PRICE_EFFECT"
    )
    assert r["actual_distribution_effect_status"] == (
        "NOT_IDENTIFIED_TAXABLE_MIX_PASS_THROUGH_BEHAVIOR_AND_OBJECTIVE_RANK_BRIDGE_REQUIRED"
    )
assert catalog["NTA-CONSUMPTION-TAX-BASIC"]["sha256"] == (
    "b5ecdc37b7b5de3376fe64c7bb30f420b0938fe4835dd4d1d7bdfb46184921f1"
)

subprocess.run(
    [
        sys.executable,
        str(ROOT / "scripts/build_vat_household_tax_content_envelope.py"),
        "--check",
    ],
    cwd=ROOT,
    check=True,
)
print(
    "VAT household tax-content envelope tests: OK "
    "(80 rows; current embedded-tax accounting cap; 5%/0% static rate-only relief envelopes)"
)
