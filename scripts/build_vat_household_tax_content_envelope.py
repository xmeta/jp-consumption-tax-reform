#!/usr/bin/env python3
"""Build annual-income-decile VAT tax-content and price-relief envelopes."""
from pathlib import Path
from decimal import Decimal, ROUND_CEILING
import argparse
import csv
import io

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data/source_catalog.csv"
HOUSEHOLD = ROOT / "data/derived/estat_2024_annual_income_decile_expenditure_diagnostic.csv"
SCENARIOS = ROOT / "research/vat_policy_integration/scenarios.csv"
OUT = ROOT / "data/derived/vat_household_tax_content_envelope.csv"
NTA_SOURCE = "NTA-CONSUMPTION-TAX-BASIC"
HOUSEHOLD_SOURCE = "ESTAT-NSFCW-2024-T1-21-ANNUAL-INCOME-DECILE-EXPENDITURE"
NTA_SHA = "b5ecdc37b7b5de3376fe64c7bb30f420b0938fe4835dd4d1d7bdfb46184921f1"
STANDARD = Decimal("0.10")
REDUCED = Decimal("0.08")
ONE_PLUS_STANDARD = Decimal("1.10")


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def ceil_yen(amount):
    return str(int(amount.to_integral_value(rounding=ROUND_CEILING)))


def rate_text(rate):
    return format(rate, "f")


def scenario_target_rate(sid):
    if sid == "current_8_10":
        return STANDARD
    if sid == "reduced_5":
        return Decimal("0.05")
    if sid in {
        "zero_rate_admin_retained",
        "full_abolition",
        "full_abolition_jgb",
        "full_abolition_income_tax",
        "full_abolition_asset_tax",
        "full_abolition_mixed",
    }:
        return Decimal("0")
    raise AssertionError(sid)


def validate_nta_rate_source(catalog):
    src = catalog[NTA_SOURCE]
    assert src["sha256"] == NTA_SHA
    raw = (ROOT / src["raw_file"]).read_text(encoding="utf-8")
    assert "標準税率10パーセント" in raw
    assert "軽減税率8パーセント" in raw
    assert "うち2.2パーセントは地方消費税" in raw


def build():
    catalog = {r["source_id"]: r for r in read_csv(CAT)}
    validate_nta_rate_source(catalog)
    households = read_csv(HOUSEHOLD)
    scenarios = read_csv(SCENARIOS)
    assert len(households) == 10
    assert len(scenarios) == 8
    assert {int(r["annual_income_decile"]) for r in households} == set(range(1, 11))
    assert all(
        r["rank_bridge_status"] == "NOT_LINKED_DO_NOT_TREAT_AS_OBJECTIVE_DECILE"
        for r in households
    )

    rows = []
    for scenario in scenarios:
        sid = scenario["scenario_id"]
        target_rate = scenario_target_rate(sid)
        rate_reduction = STANDARD - target_rate
        relief_share = rate_reduction / ONE_PLUS_STANDARD
        for hh in households:
            monthly = Decimal(hh["monthly_consumption_expenditure_yen"])
            annual = monthly * Decimal("12")
            embedded_upper_month = monthly * STANDARD / ONE_PLUS_STANDARD
            embedded_upper_year = annual * STANDARD / ONE_PLUS_STANDARD
            relief_upper_month = monthly * rate_reduction / ONE_PLUS_STANDARD
            relief_upper_year = annual * rate_reduction / ONE_PLUS_STANDARD
            rows.append({
                "scenario_id": sid,
                "annual_income_decile": hh["annual_income_decile"],
                "rank_concept": hh["rank_concept"],
                "objective_rank_concept": hh["objective_rank_concept"],
                "rank_bridge_status": hh["rank_bridge_status"],
                "monthly_consumption_expenditure_yen": hh["monthly_consumption_expenditure_yen"],
                "current_standard_rate": rate_text(STANDARD),
                "current_reduced_rate": rate_text(REDUCED),
                "scenario_rate_envelope": rate_text(target_rate),
                "maximum_standard_rate_reduction": rate_text(rate_reduction),
                "current_embedded_consumption_tax_lower_bound_yen_month": "0",
                "current_embedded_consumption_tax_upper_bound_yen_month_ceiling": ceil_yen(embedded_upper_month),
                "current_embedded_consumption_tax_upper_bound_yen_year_ceiling": ceil_yen(embedded_upper_year),
                "mechanical_price_relief_share_current_spending_envelope": (
                    f"{relief_share:.12f}".rstrip("0").rstrip(".")
                ),
                "mechanical_price_relief_upper_envelope_yen_month_ceiling": ceil_yen(relief_upper_month),
                "mechanical_price_relief_upper_envelope_yen_year_ceiling": ceil_yen(relief_upper_year),
                "tax_content_bound_status": "ACCOUNTING_UPPER_BOUND_FROM_10_PERCENT_STATUTORY_RATE_CAP",
                "price_relief_envelope_status": "STATIC_CURRENT_BASKET_FULL_PASS_THROUGH_NO_OVERSHIFT_ENVELOPE_NOT_ACTUAL_PRICE_EFFECT",
                "actual_distribution_effect_status": "NOT_IDENTIFIED_TAXABLE_MIX_PASS_THROUGH_BEHAVIOR_AND_OBJECTIVE_RANK_BRIDGE_REQUIRED",
                "source_ids": f"{HOUSEHOLD_SOURCE};{NTA_SOURCE}",
                "note": "Current embedded tax upper bound assigns the 10% statutory maximum to all observed consumption; exempt/reduced-rate items make actual tax content weakly smaller. Policy relief is a rate-only current-basket envelope, not an empirical price, welfare, Gini or FGT2 effect.",
            })

    assert len(rows) == 80
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = build()
    expected = render(rows)
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != expected:
            raise SystemExit("stale generated artifact: " + str(OUT.relative_to(ROOT)))
        print(
            "VAT household tax-content envelope: current "
            "(8 scenarios x 10 annual-income deciles; statutory-rate accounting envelope)"
        )
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(expected, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
