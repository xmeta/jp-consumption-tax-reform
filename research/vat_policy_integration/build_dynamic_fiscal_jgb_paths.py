#!/usr/bin/env python3
"""Build model-contingent incremental fiscal/JGB paths for Issue #56.

The module tracks debt created by the VAT-financing choice relative to the
baseline. It deliberately does not infer Japan's total debt stock or forecast
interest rates, nominal GDP, or market feedback.
"""
from pathlib import Path
from decimal import Decimal
import argparse
import csv
import io

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSUMPTIONS = HERE / "dynamic_fiscal_assumptions.csv"
SCENARIOS = HERE / "scenarios.csv"
FISCAL = ROOT / "data/derived/vat_policy_fiscal_replacement_reference.csv"
STATIC_JGB = ROOT / "data/derived/vat_jgb_debt_gdp_reference.csv"
OUT = ROOT / "data/derived/vat_dynamic_fiscal_paths.csv"
SUMMARY = ROOT / "data/derived/vat_dynamic_fiscal_summary.csv"

D = Decimal
MODELED_SHARES = {
    "current_8_10": D("0"),
    "full_abolition_jgb": D("1"),
    "full_abolition_income_tax": D("0"),
    "full_abolition_asset_tax": D("0"),
    "full_abolition_mixed": D("0.5"),
}
STATUS = {
    "current_8_10": "BASELINE_INCREMENTAL_PATH_ZERO",
    "reduced_5": "NOT_MODELED_STATIC_REVENUE_GAP_NOT_IDENTIFIED",
    "zero_rate_admin_retained": "NOT_MODELED_FINANCING_STRATEGY_UNSPECIFIED",
    "full_abolition": "NOT_MODELED_FINANCING_STRATEGY_UNSPECIFIED",
    "full_abolition_jgb": "MODEL_CONTINGENT_INCREMENTAL_DEBT_PATH_SENSITIVITY",
    "full_abolition_income_tax": "CONDITIONAL_FULL_REPLACEMENT_ZERO_INCREMENTAL_DEBT_PATH",
    "full_abolition_asset_tax": "CONDITIONAL_FULL_REPLACEMENT_ZERO_INCREMENTAL_DEBT_PATH",
    "full_abolition_mixed": "MODEL_CONTINGENT_HALF_PRIMARY_JGB_SHARE_SENSITIVITY",
}


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader(); w.writerows(rows)
    return b.getvalue()


def fmt(x, places="0.000000000001"):
    q = x.quantize(D(places))
    s = format(q, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def money(x):
    s = format(x, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def build():
    assumptions = read(ASSUMPTIONS)
    if len(assumptions) != 9 or len({r["assumption_set_id"] for r in assumptions}) != 9:
        raise RuntimeError("dynamic fiscal assumption grid must contain 9 unique rows")
    expected_rates = {"0.01", "0.02", "0.04"}
    expected_growth = {"0", "0.02", "0.04"}
    if {r["effective_interest_rate"] for r in assumptions} != expected_rates:
        raise RuntimeError("unexpected interest-rate sensitivity grid")
    if {r["nominal_gdp_growth"] for r in assumptions} != expected_growth:
        raise RuntimeError("unexpected nominal-GDP sensitivity grid")
    if not all(r["annual_redemption_rate"] == "0.20" and r["mixed_primary_jgb_share"] == "0.50" for r in assumptions):
        raise RuntimeError("unexpected refinancing/mixed-financing assumptions")
    if not all(r["financial_asset_change_yen"] == "0" and r["horizon_years"] == "10" for r in assumptions):
        raise RuntimeError("unexpected asset/horizon assumptions")

    scenarios = read(SCENARIOS)
    fiscal = {r["scenario_id"]: r for r in read(FISCAL)}
    static = {r["scenario_id"]: r for r in read(STATIC_JGB)}
    expected = {r["scenario_id"] for r in scenarios}
    if set(fiscal) != expected or set(static) != expected or set(STATUS) != expected:
        raise RuntimeError("dynamic fiscal scenario set drift")
    gap = D(fiscal["full_abolition_jgb"]["full_jgb_financing_reference_yen"])
    base_gdp = D(static["full_abolition_jgb"]["fy2024_nominal_gdp_yen"])
    if gap != D("25021206715000") or base_gdp != D("642414700000000"):
        raise RuntimeError("static fiscal/JGB anchor drift")
    if static["full_abolition_jgb"]["static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp"] != "3.894868333":
        raise RuntimeError("static 3.894868333 percent benchmark was reinterpreted")

    paths = []
    for scenario in scenarios:
        sid = scenario["scenario_id"]
        if sid not in MODELED_SHARES:
            continue
        primary_jgb_share = MODELED_SHARES[sid]
        annual_gap = D("0") if sid == "current_8_10" else gap
        for a in assumptions:
            r = D(a["effective_interest_rate"])
            g = D(a["nominal_gdp_growth"])
            redemption_rate = D(a["annual_redemption_rate"])
            opening = D("0")
            cumulative_interest = D("0")
            for year in range(1, 11):
                policy_primary_gap = annual_gap * primary_jgb_share
                replacement_revenue = annual_gap - policy_primary_gap
                interest = opening * r
                redemptions = opening * redemption_rate
                asset_change = D(a["financial_asset_change_yen"])
                net_new = policy_primary_gap + interest + asset_change
                gross_new = redemptions + net_new
                closing = opening - redemptions + gross_new
                nominal_gdp = base_gdp * ((D("1") + g) ** year)
                cumulative_interest += interest
                if closing != opening + net_new:
                    raise RuntimeError("stock-flow identity failed")
                paths.append({
                    "scenario_id": sid,
                    "assumption_set_id": a["assumption_set_id"],
                    "year": year,
                    "fy2024_static_gap_reference_yen": money(annual_gap),
                    "primary_jgb_share": fmt(primary_jgb_share),
                    "replacement_revenue_share": fmt(D("1") - primary_jgb_share) if annual_gap else "0",
                    "policy_primary_gap_yen": money(policy_primary_gap),
                    "replacement_revenue_yen": money(replacement_revenue),
                    "opening_incremental_debt_yen": money(opening),
                    "effective_interest_rate": a["effective_interest_rate"],
                    "incremental_interest_expense_yen": money(interest),
                    "annual_redemption_rate": a["annual_redemption_rate"],
                    "redemptions_yen": money(redemptions),
                    "financial_asset_change_yen": a["financial_asset_change_yen"],
                    "net_new_issuance_yen": money(net_new),
                    "gross_new_issuance_yen": money(gross_new),
                    "closing_incremental_debt_yen": money(closing),
                    "nominal_gdp_growth": a["nominal_gdp_growth"],
                    "nominal_gdp_sensitivity_yen": money(nominal_gdp),
                    "incremental_debt_gdp_ratio": fmt(closing / nominal_gdp),
                    "cumulative_incremental_interest_yen": money(cumulative_interest),
                    "path_status": STATUS[sid],
                    "assumption_status": a["assumption_status"],
                    "total_debt_gdp_status": "NOT_COMPUTED_BASELINE_TOTAL_DEBT_STOCK_OUTSIDE_THIS_INCREMENTAL_MODULE",
                    "market_feedback_status": "NOT_IDENTIFIED_INTEREST_AND_GDP_PATHS_ARE_EXOGENOUS_SENSITIVITIES",
                })
                opening = closing

    summary = []
    for scenario in scenarios:
        sid = scenario["scenario_id"]
        rr = [r for r in paths if r["scenario_id"] == sid and r["year"] == 10]
        if rr:
            ratios = [D(r["incremental_debt_gdp_ratio"]) for r in rr]
            interest = [D(r["cumulative_incremental_interest_yen"]) for r in rr]
            assumptions_count = str(len(rr))
            ratio_min, ratio_max = fmt(min(ratios)), fmt(max(ratios))
            int_min, int_max = money(min(interest)), money(max(interest))
        else:
            assumptions_count = "0"
            ratio_min = ratio_max = int_min = int_max = ""
        summary.append({
            "scenario_id": sid,
            "dynamic_fiscal_status": STATUS[sid],
            "modeled_assumption_sets": assumptions_count,
            "horizon_years": "10" if rr else "",
            "year10_incremental_debt_gdp_ratio_min": ratio_min,
            "year10_incremental_debt_gdp_ratio_max": ratio_max,
            "year10_cumulative_incremental_interest_yen_min": int_min,
            "year10_cumulative_incremental_interest_yen_max": int_max,
            "static_fy2024_jgb_gdp_pct_benchmark": static[sid]["static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp"],
            "identification_status": "MODEL_CONTINGENT_ACCOUNTING_SENSITIVITY_NOT_FORECAST" if rr else "NOT_MODELED",
            "note": "Paths are incremental to baseline and repeat the FY2024 nominal VAT receipt gap without indexing. Interest/GDP assumptions are exogenous sensitivities; no total-debt stock, endogenous rate response, VAT-demand effect, or institutional-productivity effect is inserted.",
        })
    if len(paths) != 450 or len(summary) != 8:
        raise RuntimeError("unexpected dynamic fiscal output dimensions")
    return paths, summary


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); args = ap.parse_args()
    paths, summary = build()
    outputs = [(OUT, render(paths)), (SUMMARY, render(summary))]
    if args.check:
        stale = [str(p.relative_to(ROOT)) for p, text in outputs if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            raise SystemExit("stale generated artifacts: " + ", ".join(stale))
        print("dynamic fiscal/JGB paths: current (450 path rows; 8 scenario summaries; incremental-debt sensitivity only)")
    else:
        for p, text in outputs:
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")
            print(f"wrote {p.relative_to(ROOT)}: {len(paths) if p == OUT else len(summary)} rows")


if __name__ == "__main__":
    main()
