#!/usr/bin/env python3
"""Pre-specified v4 rank-displacement x discrepancy-budget sensitivity surface.

This module implements rank_epsilon_surface_v4_spec.adoc.  It reuses the v3
scientific LP exactly and evaluates the Cartesian product of the already
committed v3 Delta grid and v2 epsilon grid.  It does not minimize epsilon.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import io
import math
import sys

import numpy as np
import scipy

import run_rank_bridge_lp_v3 as v3

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

CONFIG = HERE / "rank_epsilon_surface_v4_config.csv"
OUT_FEAS = HERE / "rank_epsilon_surface_v4_feasibility.csv"
OUT_END = HERE / "rank_epsilon_surface_v4_endpoints.csv"
OUT_SUMMARY = HERE / "rank_epsilon_surface_v4_summary.csv"

SPEC_VERSION = "rank_epsilon_surface_v4"
STATUS = "MODEL_CONTINGENT_RANK_EPSILON_SURFACE"
BRIDGE_SCHEME = "rank_transport_budget_fixed_epsilon_surface"

HISTORICAL_V6_REPRODUCED = False
P1C13_V1_MODIFIED = False
P1C14_V2_MODIFIED = False
P1C15_V3_MODIFIED = False

EXPECTED_DELTAS = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
EXPECTED_EPSILONS = [
    0.0, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15,
    0.175, 0.20, 0.225, 0.25, 0.275, 0.30,
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_config() -> dict[str, str]:
    rows = read_csv(CONFIG)
    cfg = {r["key"]: r["value"] for r in rows}
    required = {
        "spec_version": SPEC_VERSION,
        "base_model": "rank_bridge_lp_v3",
        "input_pseudofiler_scenarios": "all_13_committed_pseudofiler_scenarios",
        "input_nta_artifact": "nta_income_class_primary_type_filing_status_2024.csv",
        "nta_income_class_count": "25",
        "bridge_scheme": BRIDGE_SCHEME,
        "rank_bin_mass": "0.1",
        "within_class_positive_allocation": "free_within_overlap_capacity",
        "transport_positive_allocation": "free_within_transport_capacity",
        "rank_cost": "absolute_decile_index_distance",
        "surface_point_count": "104",
        "feasibility_rule": "report_all_surface_points",
        "endpoint_rule": "all_84_objectives_for_each_feasible_point",
        "overall_weight_scheme": "equal_decile",
        "v2_delta_zero_regression": "required",
        "v3_frontier_boundary_regression": "required",
        "public_diagnostics_role": "interpretation_only_no_hard_crosswalk",
        "solver": "scipy.optimize.linprog",
        "solver_method": "highs-ds",
        "solver_crosscheck_method": "highs-ipm",
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "historical_v6_restricted_lp_reproduced": "false",
        "p1c13_v1_modified": "false",
        "p1c14_v2_modified": "false",
        "p1c15_v3_modified": "false",
        "paper1_claim_before_ci": "false",
    }
    for key, expected in required.items():
        if cfg.get(key) != expected:
            raise RuntimeError(
                f"v4 pre-specification mismatch: {key}={cfg.get(key)!r}, "
                f"expected {expected!r}"
            )

    # Grid inheritance is checked directly against the committed predecessor
    # configs, not merely against constants in this implementation.
    v2cfg = {
        r["key"]: r["value"]
        for r in read_csv(HERE / "rank_bridge_lp_v2_config.csv")
    }
    v3cfg = {
        r["key"]: r["value"]
        for r in read_csv(HERE / "rank_bridge_lp_v3_config.csv")
    }
    if cfg["epsilon_grid"] != v2cfg["epsilon_grid"]:
        raise RuntimeError("v4 epsilon grid no longer exactly inherits v2")
    if cfg["delta_grid"] != v3cfg["delta_grid"]:
        raise RuntimeError("v4 Delta grid no longer exactly inherits v3")
    return cfg


def parse_grid(cfg: dict[str, str]) -> tuple[list[float], list[float]]:
    deltas = [float(x) for x in cfg["delta_grid"].split(";")]
    epsilons = [float(x) for x in cfg["epsilon_grid"].split(";")]
    if deltas != EXPECTED_DELTAS:
        raise RuntimeError(f"unexpected inherited Delta grid: {deltas}")
    if epsilons != EXPECTED_EPSILONS:
        raise RuntimeError(f"unexpected inherited epsilon grid: {epsilons}")
    if len(deltas) * len(epsilons) != int(cfg["surface_point_count"]):
        raise RuntimeError("surface point count mismatch")
    return deltas, epsilons


def fmt(x) -> str:
    if isinstance(x, bool):
        return "True" if x else "False"
    if isinstance(x, str):
        return x
    if x is None:
        return ""
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    x = float(x)
    if math.isnan(x):
        return ""
    return f"{x:.12g}"


def render(rows: list[dict]) -> str:
    if not rows:
        raise RuntimeError("cannot render empty v4 output")
    b = io.StringIO()
    fields = list(rows[0])
    w = csv.DictWriter(b, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for row in rows:
        w.writerow({k: fmt(v) for k, v in row.items()})
    return b.getvalue()


def flags() -> dict:
    return {
        "scientific_status": STATUS,
        "historical_v6_restricted_lp_reproduced": HISTORICAL_V6_REPRODUCED,
        "p1c13_v1_modified": P1C13_V1_MODIFIED,
        "p1c14_v2_modified": P1C14_V2_MODIFIED,
        "p1c15_v3_modified": P1C15_V3_MODIFIED,
    }


def load_data(cfg: dict[str, str]):
    v3cfg = v3.read_config()
    data = v3.load_data(v3cfg)
    if len(data.class_index) != int(cfg["nta_income_class_count"]):
        raise RuntimeError("NTA class count mismatch")
    return data


def solved_diagnostics(
    model,
    res,
    delta: float,
    epsilon: float,
    eq_tol: float,
    ineq_tol: float,
) -> dict:
    diag = v3.diagnostics(model, res.x, delta, epsilon)
    v3.assert_solution(diag, eq_tol, ineq_tol)
    return diag


def feasibility_rows(
    data,
    deltas: list[float],
    epsilons: list[float],
    eq_tol: float,
    ineq_tol: float,
) -> list[dict]:
    rows = []
    model = v3.make_model(data, include_epsilon=False)
    zero = np.zeros(model.nvars)

    for delta in deltas:
        for epsilon in epsilons:
            ds = v3.solve_lp(
                model, zero, delta=delta, epsilon=epsilon, method="highs-ds"
            )
            ipm = v3.solve_lp(
                model, zero, delta=delta, epsilon=epsilon, method="highs-ipm"
            )
            ds_feasible = bool(ds.success)
            ipm_feasible = bool(ipm.success)
            if ds_feasible != ipm_feasible:
                raise RuntimeError(
                    "HiGHS feasibility classification disagreement at "
                    f"delta={delta}, epsilon={epsilon}: "
                    f"highs-ds={ds_feasible}, highs-ipm={ipm_feasible}"
                )

            diag = None
            if ds_feasible:
                diag = solved_diagnostics(
                    model, ds, delta, epsilon, eq_tol, ineq_tol
                )

            row = {
                "spec_version": SPEC_VERSION,
                "base_model": "rank_bridge_lp_v3",
                "bridge_scheme": BRIDGE_SCHEME,
                "delta": delta,
                "average_percentile_rank_displacement_pp": 10.0 * delta,
                "epsilon": epsilon,
                "feasible": ds_feasible,
                "solver_status_code": int(ds.status),
                "solver_message": str(ds.message),
                "crosscheck_method": "highs-ipm",
                "crosscheck_feasible": ipm_feasible,
                "crosscheck_status_code": int(ipm.status),
                "classification_agrees": ds_feasible == ipm_feasible,
                "max_scenario_sum_residual":
                    None if diag is None else diag["max_scenario_sum_residual"],
                "max_class_positive_mass_residual":
                    None if diag is None else diag["max_class_positive_mass_residual"],
                "max_overlap_capacity_excess":
                    None if diag is None else diag["max_overlap_capacity_excess"],
                "max_transport_row_margin_residual":
                    None if diag is None else diag["max_transport_row_margin_residual"],
                "max_transport_column_margin_residual":
                    None if diag is None else diag["max_transport_column_margin_residual"],
                "max_positive_transport_capacity_excess":
                    None if diag is None else diag["max_positive_transport_capacity_excess"],
                "max_nta_rank_positive_margin_residual":
                    None if diag is None else diag["max_nta_rank_positive_margin_residual"],
                "transport_cost_at_one_feasible_solution":
                    None if diag is None else diag["transport_cost"],
                "rank_displacement_budget_excess":
                    None if diag is None else diag["rank_displacement_budget_excess"],
                "max_rank_bridge_gap_at_one_feasible_solution":
                    None if diag is None else diag["max_rank_bridge_gap"],
                "max_rank_bridge_inequality_excess":
                    None if diag is None else diag["max_rank_bridge_inequality_excess"],
                "minimum_decision_variable":
                    None if diag is None else diag["minimum_decision_variable"],
                "numpy_version": np.__version__,
                "scipy_version": scipy.__version__,
                "solver_method": "highs-ds",
                **flags(),
            }
            rows.append(row)
    return rows


def endpoint_rows_at(
    data,
    delta: float,
    epsilon: float,
    eq_tol: float,
    ineq_tol: float,
    objective_tol: float,
) -> list[dict]:
    model = v3.make_model(data, include_epsilon=False)
    zero = np.zeros(model.nvars)
    feas = v3.solve_lp(
        model, zero, delta=delta, epsilon=epsilon, method="highs-ds"
    )
    if not feas.success:
        return []
    solved_diagnostics(model, feas, delta, epsilon, eq_tol, ineq_tol)

    objectives = []
    for di, d in enumerate(data.deciles):
        for metric in v3.DECILE_METRICS:
            objectives.append(("decile", d, di, metric, False))
    for metric in v3.OVERALL_METRICS:
        objectives.append(("overall", "", None, metric, True))

    rows = []
    for scope, d_label, di, metric, overall in objectives:
        c = v3.objective_vector(model, metric, di, overall)
        for bound_name, sign in (("min", 1.0), ("max", -1.0)):
            res = v3.solve_lp(
                model, sign * c, delta=delta, epsilon=epsilon,
                method="highs-ds"
            )
            if not res.success:
                raise RuntimeError(
                    "v4 endpoint failed at "
                    f"delta={delta}, epsilon={epsilon}, {scope}, "
                    f"decile={d_label}, metric={metric}, bound={bound_name}: "
                    f"{res.status} {res.message}"
                )
            diag = solved_diagnostics(
                model, res, delta, epsilon, eq_tol, ineq_tol
            )
            raw = float(np.dot(c, res.x))
            solver_value = float(sign * res.fun)
            if abs(raw - solver_value) > objective_tol:
                raise RuntimeError(
                    "v4 objective recomputation mismatch at "
                    f"delta={delta}, epsilon={epsilon}: "
                    f"{raw} vs {solver_value}"
                )
            rows.append({
                "spec_version": SPEC_VERSION,
                "base_model": "rank_bridge_lp_v3",
                "bridge_scheme": BRIDGE_SCHEME,
                "delta": delta,
                "average_percentile_rank_displacement_pp": 10.0 * delta,
                "epsilon": epsilon,
                "scope": scope,
                "decile": d_label,
                "metric": metric,
                "bound": bound_name,
                "endpoint_value": raw,
                "solver_status_code": int(res.status),
                "solver_message": str(res.message),
                **diag,
                "numpy_version": np.__version__,
                "scipy_version": scipy.__version__,
                "solver_method": "highs-ds",
                **flags(),
            })
    if len(rows) != 84:
        raise RuntimeError(f"expected 84 v4 endpoints, got {len(rows)}")
    return rows


def all_endpoint_rows(
    data,
    feas_rows: list[dict],
    eq_tol: float,
    ineq_tol: float,
    objective_tol: float,
) -> list[dict]:
    rows = []
    for fr in feas_rows:
        if not fr["feasible"]:
            continue
        rows.extend(endpoint_rows_at(
            data,
            float(fr["delta"]),
            float(fr["epsilon"]),
            eq_tol,
            ineq_tol,
            objective_tol,
        ))
    return rows


def summary_rows(
    feas_rows: list[dict],
    endpoints: list[dict],
) -> list[dict]:
    by_point: dict[tuple[float, float], list[dict]] = {}
    for r in endpoints:
        key = (float(r["delta"]), float(r["epsilon"]))
        by_point.setdefault(key, []).append(r)

    out = []
    for fr in feas_rows:
        delta = float(fr["delta"])
        epsilon = float(fr["epsilon"])
        key = (delta, epsilon)
        feasible = bool(fr["feasible"])
        rows = by_point.get(key, [])
        if feasible and len(rows) != 84:
            raise RuntimeError(
                f"feasible point {key} has {len(rows)} endpoints, expected 84"
            )
        if not feasible and rows:
            raise RuntimeError(f"infeasible point {key} has endpoint rows")

        values = {}
        if feasible:
            overall = [r for r in rows if r["scope"] == "overall"]
            for metric, prefix in (
                ("taxable_income_weighted_mean_MTR", "overall_taxable_mtr"),
                ("income_tax_liability_weighted_mean_MTR", "overall_liability_mtr"),
            ):
                q = [r for r in overall if r["metric"] == metric]
                if len(q) != 2:
                    raise RuntimeError(f"missing overall endpoint pair {key} {metric}")
                pair = {r["bound"]: float(r["endpoint_value"]) for r in q}
                values[f"{prefix}_min"] = pair["min"]
                values[f"{prefix}_max"] = pair["max"]
                values[f"{prefix}_width"] = pair["max"] - pair["min"]

        out.append({
            "spec_version": SPEC_VERSION,
            "bridge_scheme": BRIDGE_SCHEME,
            "delta": delta,
            "average_percentile_rank_displacement_pp": 10.0 * delta,
            "epsilon": epsilon,
            "feasible": feasible,
            "endpoint_row_count": len(rows),
            "overall_taxable_mtr_min":
                values.get("overall_taxable_mtr_min"),
            "overall_taxable_mtr_max":
                values.get("overall_taxable_mtr_max"),
            "overall_taxable_mtr_width":
                values.get("overall_taxable_mtr_width"),
            "overall_liability_mtr_min":
                values.get("overall_liability_mtr_min"),
            "overall_liability_mtr_max":
                values.get("overall_liability_mtr_max"),
            "overall_liability_mtr_width":
                values.get("overall_liability_mtr_width"),
            **flags(),
        })
    return out


def build_outputs():
    cfg = read_config()
    deltas, epsilons = parse_grid(cfg)
    eq_tol = float(cfg["equality_residual_tolerance"])
    ineq_tol = float(cfg["inequality_residual_tolerance"])
    objective_tol = float(cfg["objective_recompute_tolerance"])
    data = load_data(cfg)

    feas = feasibility_rows(data, deltas, epsilons, eq_tol, ineq_tol)
    if len(feas) != 104:
        raise RuntimeError(f"expected 104 feasibility rows, got {len(feas)}")
    endpoints = all_endpoint_rows(
        data, feas, eq_tol, ineq_tol, objective_tol
    )
    summary = summary_rows(feas, endpoints)
    if len(summary) != 104:
        raise RuntimeError(f"expected 104 summary rows, got {len(summary)}")
    return [
        (OUT_FEAS, feas),
        (OUT_END, endpoints),
        (OUT_SUMMARY, summary),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    outputs = build_outputs()
    if args.check:
        stale = []
        for path, rows in outputs:
            expected = render(rows)
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if expected != actual:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            print("ERROR: stale v4 surface outputs: " + ", ".join(stale))
            sys.exit(1)
        feasible = sum(
            1 for r in outputs[0][1] if bool(r["feasible"])
        )
        print(
            "rank-epsilon surface v4: current "
            f"(104 points; {feasible} feasible; "
            f"{len(outputs[1][1])} endpoints)"
        )
        return

    for path, rows in outputs:
        path.write_text(render(rows), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")

    feas_rows = outputs[0][1]
    feasible = [r for r in feas_rows if r["feasible"]]
    print(
        f"\nv4 surface: {len(feasible)}/104 feasible points; "
        f"{len(outputs[1][1])} endpoint rows"
    )
    for delta in EXPECTED_DELTAS:
        eps = [
            float(r["epsilon"]) for r in feasible
            if float(r["delta"]) == delta
        ]
        print(
            "delta=", fmt(delta),
            "minimum_feasible_grid_epsilon=",
            fmt(min(eps) if eps else None),
            "feasible_grid_points=", len(eps),
        )


if __name__ == "__main__":
    main()
