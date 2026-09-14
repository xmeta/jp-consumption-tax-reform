#!/usr/bin/env python3
"""Issue #133: compare 2024 aggregates under 2024 vs 2026 income-tax law."""
from pathlib import Path
import argparse, csv, io, math, sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research/income_tax_pseudofiler"))
sys.path.insert(0, str(HERE))

import run_pseudofiler_core as pf  # noqa: E402
import run_rank_bridge_lp_v2 as v2  # noqa: E402
import run_rank_bridge_lp_v3 as v3  # noqa: E402
import run_rank_epsilon_surface_v4 as v4  # noqa: E402
import run_rank_one_sided_bridge_v5 as v5  # noqa: E402

OUT_PSEUDO = ROOT / "research/income_tax_pseudofiler/tax_law_year_pseudofiler_benchmark.csv"
OUT_BRIDGE = HERE / "tax_law_year_bridge_benchmark.csv"


def data_from_scenarios(rows):
    by = {}
    for r in rows:
        by.setdefault(int(r["decile"]), {})[r["scenario"]] = r
    deciles = tuple(range(1, 11))
    scenarios = v2.EXPECTED_SCENARIOS
    def matrix(field):
        return np.array([[float(by[d][s][field]) for s in scenarios] for d in deciles])
    idx, labels, A, P = v2.load_nta_classes()
    N = float(A.sum())
    a, p = A / N, P / N
    return v2.Data(
        deciles, scenarios, idx, labels, A, P, N, a, p, v2.build_overlap(a),
        matrix("pseudo_positive_modeled_annual_income_tax_share"),
        matrix("taxable_income_weighted_mean_MTR"),
        matrix("income_tax_liability_weighted_mean_MTR"),
    )


def overall_bounds(rows, metric):
    q = [r for r in rows if r["scope"] == "overall" and r["metric"] == metric]
    vals = {r["bound"]: float(r["endpoint_value"]) for r in q}
    return vals.get("min"), vals.get("max")


def build():
    pseudo_by_year = {}
    scenarios_by_year = {}
    for year in (2024, 2026):
        _, scenarios, _, _ = pf.build_outputs(year)
        scenarios_by_year[year] = scenarios
        pseudo_by_year[year] = {
            int(r["decile"]): r for r in scenarios if r["scenario"] == "central"
        }

    pseudo_rows = []
    for d in range(1, 11):
        a, b = pseudo_by_year[2024][d], pseudo_by_year[2026][d]
        p24 = float(a["pseudo_positive_modeled_annual_income_tax_share"])
        p26 = float(b["pseudo_positive_modeled_annual_income_tax_share"])
        m24 = float(a["taxable_income_weighted_mean_MTR"])
        m26 = float(b["taxable_income_weighted_mean_MTR"])
        pseudo_rows.append({
            "decile": d,
            "scenario": "central",
            "positive_share_2024_law": p24,
            "positive_share_2026_law": p26,
            "positive_share_2024_minus_2026_pp": 100.0 * (p24 - p26),
            "taxable_weighted_mtr_2024_law": m24,
            "taxable_weighted_mtr_2026_law": m26,
            "taxable_weighted_mtr_2024_minus_2026_pp": 100.0 * (m24 - m26),
            "status": "SENSITIVITY_ONLY_NOT_IDENTIFIED_TAX_LAW_YEAR_BENCHMARK",
        })

    bridge_rows = []
    for year in (2024, 2026):
        data = data_from_scenarios(scenarios_by_year[year])
        c2 = v2.read_config(); eq2=float(c2["equality_residual_tolerance"]); in2=float(c2["inequality_residual_tolerance"])
        v2row, _ = v2.solve_minimum(data, eq2, in2)

        c3 = v3.read_config(); eq3=float(c3["equality_residual_tolerance"]); in3=float(c3["inequality_residual_tolerance"])
        v3eps = {}
        for delta in (0.0, 0.25, 5.0):
            _, _, eps, _ = v3.solve_minimum_at_delta(data, delta, eq3, in3)
            v3eps[delta] = eps

        c4 = v4.read_config(); deltas, epsilons = v4.parse_grid(c4)
        eq4=float(c4["equality_residual_tolerance"]); in4=float(c4["inequality_residual_tolerance"])
        feas = v4.feasibility_rows(data, deltas, epsilons, eq4, in4)
        feasible = [r for r in feas if bool(r["feasible"])]
        d0_eps = [float(r["epsilon"]) for r in feasible if float(r["delta"]) == 0.0]
        pos_eps = [float(r["epsilon"]) for r in feasible if float(r["delta"]) == 0.25]
        objtol = float(c4["objective_recompute_tolerance"])
        v4e30 = v4.endpoint_rows_at(data, 0.25, 0.30, eq4, in4, objtol)
        v4tax = overall_bounds(v4e30, "taxable_income_weighted_mean_MTR")
        v4liab = overall_bounds(v4e30, "income_tax_liability_weighted_mean_MTR")

        c5 = v5.read_config(); eq5=float(c5["equality_residual_tolerance"]); in5=float(c5["inequality_residual_tolerance"])
        v5eta = {}
        for delta in (0.0, 0.25, 5.0):
            _, _, eta, _ = v5.solve_minimum_at_delta(data, delta, eq5, in5, c5["solver_method"])
            v5eta[delta] = eta
        v5end = v5.endpoint_rows_at(data, 0.0, v5eta[0.0], v5eta[0.0], eq5, in5)
        v5tax = overall_bounds(v5end, "taxable_income_weighted_mean_MTR")
        v5liab = overall_bounds(v5end, "income_tax_liability_weighted_mean_MTR")

        central = list(pseudo_by_year[year].values())
        bridge_rows.append({
            "tax_law_year": year,
            "aggregate_year": 2024,
            "central_equal_decile_mean_positive_share": sum(float(r["pseudo_positive_modeled_annual_income_tax_share"]) for r in central) / 10.0,
            "central_equal_decile_mean_taxable_weighted_mtr": sum(float(r["taxable_income_weighted_mean_MTR"]) for r in central) / 10.0,
            "v2_epsilon_star": float(v2row["epsilon_star"]),
            "v3_epsilon_star_delta_0": v3eps[0.0],
            "v3_epsilon_star_delta_0p25": v3eps[0.25],
            "v3_epsilon_star_delta_5": v3eps[5.0],
            "v4_feasible_grid_points_of_104": len(feasible),
            "v4_min_feasible_grid_epsilon_delta_0": min(d0_eps) if d0_eps else None,
            "v4_min_feasible_grid_epsilon_delta_0p25": min(pos_eps) if pos_eps else None,
            "v4_delta_0p25_epsilon_0p30_taxable_mtr_min": v4tax[0],
            "v4_delta_0p25_epsilon_0p30_taxable_mtr_max": v4tax[1],
            "v4_delta_0p25_epsilon_0p30_liability_mtr_min": v4liab[0],
            "v4_delta_0p25_epsilon_0p30_liability_mtr_max": v4liab[1],
            "v5_eta_star_delta_0": v5eta[0.0],
            "v5_eta_star_delta_0p25": v5eta[0.25],
            "v5_eta_star_delta_5": v5eta[5.0],
            "v5_delta_0_taxable_mtr_min": v5tax[0],
            "v5_delta_0_taxable_mtr_max": v5tax[1],
            "v5_delta_0_liability_mtr_min": v5liab[0],
            "v5_delta_0_liability_mtr_max": v5liab[1],
            "interpretation": "law-year sensitivity only; not identified decomposition of bridge discrepancy",
        })
    return pseudo_rows, bridge_rows


def render(rows):
    b=io.StringIO(); w=csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n"); w.writeheader()
    for r in rows:
        w.writerow({k: ("" if v is None else f"{v:.12g}" if isinstance(v,float) else v) for k,v in r.items()})
    return b.getvalue()


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); args=ap.parse_args()
    p,b=build(); outputs=((OUT_PSEUDO,p),(OUT_BRIDGE,b))
    stale=[]
    for path,rows in outputs:
        text=render(rows)
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text: stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(text, encoding="utf-8"); print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")
    if stale:
        raise SystemExit("ERROR: stale tax-law-year benchmark outputs: " + ", ".join(stale))
    if args.check: print("tax-law-year benchmark: current")

if __name__ == "__main__": main()
