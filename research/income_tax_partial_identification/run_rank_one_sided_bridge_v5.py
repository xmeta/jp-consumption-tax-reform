#!/usr/bin/env python3
"""Pre-specified rank one-sided bridge LP v5.

Implements rank_one_sided_bridge_v5_spec.adoc without modifying the frozen
pre-specification.  v5 reuses the v3 rank-transport machinery but replaces the
symmetric event-rate gap with the directional compatibility constraint

    transported NTA positive-self-assessed-balance rate
      - pseudo modeled annual-income-tax-positive rate <= eta.

The 2024 NTA tax-flow diagnostic is used only to justify the event direction;
its observed withholding / tax-credit exposure rates do not calibrate eta.
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
from scipy.optimize import linprog

import run_rank_bridge_lp_v3 as v3

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

CONFIG = HERE / "rank_one_sided_bridge_v5_config.csv"
V3_FRONTIER = HERE / "rank_bridge_lp_v3_minimum_relaxation_frontier.csv"

OUT_FRONTIER = HERE / "rank_one_sided_bridge_v5_minimum_violation_frontier.csv"
OUT_DECILE = HERE / "rank_one_sided_bridge_v5_minimum_decile_diagnostics.csv"
OUT_ZERO = HERE / "rank_one_sided_bridge_v5_zero_violation_threshold.csv"
OUT_PLANS = HERE / "rank_one_sided_bridge_v5_transport_plans.csv"
OUT_END = HERE / "rank_one_sided_bridge_v5_endpoints.csv"

SPEC_VERSION = "rank_one_sided_bridge_v5"
BRIDGE_SCHEME = "rank_transport_one_sided_subset_compatibility"
STATUS = "MODEL_CONTINGENT_RANK_ONE_SIDED_SUBSET_COMPATIBILITY"
HISTORICAL_V6_REPRODUCED = False
P1C13_V1_MODIFIED = False
P1C14_V2_MODIFIED = False
P1C15_V3_MODIFIED = False
P1C16_V4_MODIFIED = False

DECILE_METRICS = v3.DECILE_METRICS
OVERALL_METRICS = v3.OVERALL_METRICS


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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
        raise RuntimeError("cannot render empty output")
    b = io.StringIO()
    fields = list(rows[0])
    w = csv.DictWriter(b, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for row in rows:
        w.writerow({k: fmt(v) for k, v in row.items()})
    return b.getvalue()


def read_config() -> dict[str, str]:
    rows = read_csv(CONFIG)
    cfg = {r["key"]: r["value"] for r in rows}
    if len(cfg) != len(rows):
        raise RuntimeError("duplicate v5 config key")

    required = {
        "spec_version": SPEC_VERSION,
        "input_pseudofiler_scenarios": "all_13_committed_pseudofiler_scenarios",
        "input_nta_artifact": "nta_income_class_primary_type_filing_status_2024.csv",
        "tax_flow_diagnostic_artifact":
            "nta_positive_self_assessed_balance_tax_flow_income_class_primary_type_2024.csv",
        "nta_income_class_count": "25",
        "bridge_scheme": BRIDGE_SCHEME,
        "directional_constraint":
            "transported_nta_positive_balance_minus_pseudo_calculated_tax_positive_le_eta",
        "eta_lower_bound": "0",
        "eta_upper_bound": "1",
        "rank_bin_mass": "0.1",
        "within_class_positive_allocation": "free_within_overlap_capacity",
        "transport_positive_allocation": "free_within_transport_capacity",
        "rank_cost": "absolute_decile_index_distance",
        "delta_unrestricted": "5",
        "zero_violation_threshold": "solve_minimum_delta_at_eta_0",
        "frontier_endpoint_rule": "eta_star_at_each_delta",
        "overall_weight_scheme": "equal_decile",
        "tax_flow_diagnostic_role": "semantic_direction_only_no_rate_calibration",
        "cross_year_status": "2024_observed_tax_flow_vs_2026_pseudo_tax_model",
        "v3_outer_set_regression": "eta_star_le_v3_epsilon_star_same_delta",
        "delta_monotonicity": "eta_star_nonincreasing",
        "solver": "scipy.optimize.linprog",
        "solver_method": "highs-ds",
        "solver_crosscheck_method": "highs-ipm",
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "historical_v6_restricted_lp_reproduced": "false",
        "p1c13_v1_modified": "false",
        "p1c14_v2_modified": "false",
        "p1c15_v3_modified": "false",
        "p1c16_v4_modified": "false",
        "paper1_claim_before_ci": "false",
        "paper1_claim_before_separate_promotion": "false",
    }
    for key, expected in required.items():
        if cfg.get(key) != expected:
            raise RuntimeError(
                f"pre-specification mismatch: {key}={cfg.get(key)!r}, "
                f"expected {expected!r}"
            )
    return cfg


def delta_grid(cfg: dict[str, str]) -> list[float]:
    vals = [float(x) for x in cfg["delta_grid"].split(";")]
    expected = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
    if len(vals) != len(expected) or any(
        abs(a - b) > 1e-15 for a, b in zip(vals, expected)
    ):
        raise RuntimeError(f"delta grid changed: {vals}")
    return vals


def flags() -> dict:
    return {
        "scientific_status": STATUS,
        "historical_v6_restricted_lp_reproduced": HISTORICAL_V6_REPRODUCED,
        "p1c13_v1_modified": P1C13_V1_MODIFIED,
        "p1c14_v2_modified": P1C14_V2_MODIFIED,
        "p1c15_v3_modified": P1C15_V3_MODIFIED,
        "p1c16_v4_modified": P1C16_V4_MODIFIED,
    }


def inequalities(
    model: v3.Model,
    delta: float | None,
    eta: float | None,
) -> tuple[np.ndarray, np.ndarray]:
    data = model.data
    D = len(data.deciles)
    S = len(data.scenarios)
    rows = []
    rhs = []

    # Positive self-assessed balance transport cannot exceed population
    # transport.  This is unchanged from v3.
    for di in range(D):
        for qi in range(D):
            a = np.zeros(model.nvars)
            a[model.z_index[(di, qi)]] = 1.0
            a[model.t_index[(di, qi)]] = -1.0
            rows.append(a)
            rhs.append(0.0)

    # Rank-displacement budget.  delta=None is used only for the minimum-cost
    # eta=0 threshold solve.
    if delta is not None:
        rows.append(v3.transport_cost_vector(model))
        rhs.append(float(delta))

    # One-sided event compatibility:
    #   transported NTA positive-balance rate - pseudo positive-calculated-tax
    #   rate <= eta.
    # There is deliberately no mirror inequality.
    for di in range(D):
        a = np.zeros(model.nvars)
        for si in range(S):
            a[model.lambda_index[(di, si)]] = -data.u[di, si]
        for qi in range(D):
            a[model.z_index[(di, qi)]] = 10.0

        if model.include_epsilon:
            # v3.Model names this generic scalar slot epsilon_index.  In v5 it
            # is semantically eta and is never exposed as epsilon in outputs.
            if not (model.epsilon_index is not None):
                raise RuntimeError('scientific runtime invariant failed: research/income_tax_partial_identification/run_rank_one_sided_bridge_v5.py:200')
            a[model.epsilon_index] = -1.0
            b = 0.0
        else:
            if not (eta is not None):
                raise RuntimeError('scientific runtime invariant failed: research/income_tax_partial_identification/run_rank_one_sided_bridge_v5.py:204')
            b = float(eta)
        rows.append(a)
        rhs.append(b)

    return np.vstack(rows), np.array(rhs)


def solve_lp(
    model: v3.Model,
    c: np.ndarray,
    delta: float | None,
    eta: float | None = None,
    method: str = "highs-ds",
):
    A_ub, b_ub = inequalities(model, delta, eta)
    options = {"presolve": True}
    if method == "highs-ds":
        options.update({
            "dual_feasibility_tolerance": 1e-9,
            "primal_feasibility_tolerance": 1e-9,
        })
    return linprog(
        c,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=model.A_eq,
        b_eq=model.b_eq,
        bounds=model.bounds,
        method=method,
        options=options,
    )


def diagnostics(
    model: v3.Model,
    x: np.ndarray,
    delta_requested: float | None,
    eta_requested: float,
) -> dict[str, float]:
    data = model.data
    lam, y, t, z = v3.unpack(model, x)

    scenario_res = float(np.max(np.abs(lam.sum(axis=1) - 1.0)))
    class_pos_res = float(
        np.max(np.abs(y.sum(axis=1) - data.class_positive_mass))
    )
    overlap_excess = float(np.max(np.maximum(0.0, y - data.overlap)))
    t_row_res = float(np.max(np.abs(t.sum(axis=1) - 0.1)))
    t_col_res = float(np.max(np.abs(t.sum(axis=0) - 0.1)))
    z_capacity_excess = float(np.max(np.maximum(0.0, z - t)))
    nta_rank_positive = y.sum(axis=0)
    z_col_res = float(np.max(np.abs(z.sum(axis=0) - nta_rank_positive)))

    transport_cost = float(
        sum(abs(di - qi) * t[di, qi] for di in range(10) for qi in range(10))
    )
    displacement_excess = (
        0.0
        if delta_requested is None
        else max(0.0, transport_cost - delta_requested)
    )

    pseudo = np.sum(lam * data.u, axis=1)
    transported = 10.0 * z.sum(axis=1)
    directional = transported - pseudo
    maximum_directional_violation = float(np.max(directional))
    maximum_directional_violation_excess = max(
        0.0, maximum_directional_violation - eta_requested
    )
    minimum_subset_margin = float(np.min(pseudo - transported))
    minimum_var = float(min(np.min(lam), np.min(y), np.min(t), np.min(z)))

    return {
        "max_scenario_sum_residual": scenario_res,
        "max_class_positive_mass_residual": class_pos_res,
        "max_overlap_capacity_excess": overlap_excess,
        "max_transport_row_margin_residual": t_row_res,
        "max_transport_column_margin_residual": t_col_res,
        "max_positive_self_assessed_balance_transport_capacity_excess":
            z_capacity_excess,
        "max_nta_rank_positive_margin_residual": z_col_res,
        "transport_cost": transport_cost,
        "rank_displacement_budget_excess": displacement_excess,
        "maximum_directional_violation_transported_minus_pseudo":
            maximum_directional_violation,
        "maximum_directional_violation_excess": maximum_directional_violation_excess,
        "minimum_subset_margin_pseudo_minus_transported": minimum_subset_margin,
        "minimum_decision_variable": minimum_var,
    }


def assert_solution(diag: dict, eq_tol: float, ineq_tol: float) -> None:
    for key in (
        "max_scenario_sum_residual",
        "max_class_positive_mass_residual",
        "max_transport_row_margin_residual",
        "max_transport_column_margin_residual",
        "max_nta_rank_positive_margin_residual",
    ):
        if diag[key] > eq_tol:
            raise RuntimeError(f"{key} exceeds tolerance: {diag[key]}")
    for key in (
        "max_overlap_capacity_excess",
        "max_positive_self_assessed_balance_transport_capacity_excess",
        "rank_displacement_budget_excess",
        "maximum_directional_violation_excess",
    ):
        if diag[key] > ineq_tol:
            raise RuntimeError(f"{key} exceeds tolerance: {diag[key]}")
    if diag["minimum_decision_variable"] < -eq_tol:
        raise RuntimeError("negative decision variable")


def solve_minimum_at_delta(
    data,
    delta: float,
    eq_tol: float,
    ineq_tol: float,
    method: str,
):
    model = v3.make_model(data, include_epsilon=True)
    c = np.zeros(model.nvars)
    if not (model.epsilon_index is not None):
        raise RuntimeError('scientific runtime invariant failed: research/income_tax_partial_identification/run_rank_one_sided_bridge_v5.py:327')
    c[model.epsilon_index] = 1.0
    res = solve_lp(model, c, delta=delta, method=method)
    if not res.success:
        raise RuntimeError(
            f"v5 minimum eta failed delta={delta} method={method}: "
            f"{res.status} {res.message}"
        )
    eta = float(res.x[model.epsilon_index])
    if eta < 0.0 and eta > -1e-10:
        eta = 0.0
    diag = diagnostics(model, res.x, delta, eta)
    assert_solution(diag, eq_tol, ineq_tol)
    return model, res, eta, diag


def solve_zero_violation_threshold(
    data,
    eq_tol: float,
    ineq_tol: float,
    method: str,
):
    model = v3.make_model(data, include_epsilon=False)
    c = v3.transport_cost_vector(model)
    res = solve_lp(model, c, delta=None, eta=0.0, method=method)
    if not res.success:
        return model, res, None, None
    delta_star = float(np.dot(c, res.x))
    diag = diagnostics(model, res.x, None, 0.0)
    assert_solution(diag, eq_tol, ineq_tol)
    if abs(diag["transport_cost"] - delta_star) > 1e-9:
        raise RuntimeError("zero-violation cost recomputation mismatch")
    return model, res, delta_star, diag


def fixed_feasibility(
    data,
    delta: float,
    eta: float,
    eq_tol: float,
    ineq_tol: float,
):
    model = v3.make_model(data, include_epsilon=False)
    res = solve_lp(
        model, np.zeros(model.nvars), delta=delta, eta=eta, method="highs-ds"
    )
    if not res.success:
        return model, res, None
    diag = diagnostics(model, res.x, delta, eta)
    assert_solution(diag, eq_tol, ineq_tol)
    return model, res, diag


def endpoint_rows_at(
    data,
    delta: float,
    eta: float,
    eta_reported: float,
    eq_tol: float,
    ineq_tol: float,
) -> list[dict]:
    model, feas, _ = fixed_feasibility(data, delta, eta, eq_tol, ineq_tol)
    if not feas.success:
        return []

    objectives = []
    for di, d in enumerate(data.deciles):
        for metric in DECILE_METRICS:
            objectives.append(("decile", d, di, metric, False))
    for metric in OVERALL_METRICS:
        objectives.append(("overall", "", None, metric, True))

    rows = []
    for scope, d_label, di, metric, overall in objectives:
        c = v3.objective_vector(model, metric, di, overall)
        for bound_name, sign in (("min", 1.0), ("max", -1.0)):
            res = solve_lp(
                model, sign * c, delta=delta, eta=eta, method="highs-ds"
            )
            if not res.success:
                raise RuntimeError(
                    f"v5 endpoint failed delta={delta} eta={eta} "
                    f"{scope} {d_label} {metric} {bound_name}: "
                    f"{res.status} {res.message}"
                )
            diag = diagnostics(model, res.x, delta, eta)
            assert_solution(diag, eq_tol, ineq_tol)
            raw = float(np.dot(c, res.x))
            solver = float(sign * res.fun)
            if abs(raw - solver) > 1e-9:
                raise RuntimeError(
                    f"objective recomputation mismatch: {raw} vs {solver}"
                )
            rows.append({
                "spec_version": SPEC_VERSION,
                "bridge_scheme": BRIDGE_SCHEME,
                "frontier_source": "eta_star_frontier",
                "delta": delta,
                "average_percentile_rank_displacement_pp": 10.0 * delta,
                "eta_star": eta_reported,
                "eta_constraint_used": eta,
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
    return rows


def frontier_rows_and_plans(
    data,
    deltas: list[float],
    cfg: dict[str, str],
):
    eq_tol = float(cfg["equality_residual_tolerance"])
    ineq_tol = float(cfg["inequality_residual_tolerance"])
    cross_tol = float(cfg["v3_outer_set_tolerance"])
    monotone_tol = float(cfg["frontier_monotonicity_tolerance"])
    method_primary = cfg["solver_method"]
    method_cross = cfg["solver_crosscheck_method"]

    v3_by_delta = {
        float(r["delta"]): float(r["epsilon_star"])
        for r in read_csv(V3_FRONTIER)
    }

    frontier = []
    decile_rows = []
    plans = []
    eta_values = []

    for delta in deltas:
        model, res, eta, diag = solve_minimum_at_delta(
            data, delta, eq_tol, ineq_tol, method_primary
        )
        _, res_cross, eta_cross, _ = solve_minimum_at_delta(
            data, delta, eq_tol, ineq_tol, method_cross
        )
        if not res_cross.success:
            raise RuntimeError(f"v5 cross-check failed at delta={delta}")
        if abs(eta - eta_cross) > cross_tol:
            raise RuntimeError(
                f"v5 solver cross-check eta mismatch delta={delta}: "
                f"{eta} vs {eta_cross}"
            )

        if delta not in v3_by_delta:
            raise RuntimeError(f"missing v3 frontier delta={delta}")
        if eta > v3_by_delta[delta] + cross_tol:
            raise RuntimeError(
                f"v3 outer-set regression failed delta={delta}: "
                f"eta={eta} > epsilon_v3={v3_by_delta[delta]}"
            )

        lam, y, t, z = v3.unpack(model, res.x)
        pseudo = np.sum(lam * data.u, axis=1)
        transported = 10.0 * z.sum(axis=1)

        frontier.append({
            "spec_version": SPEC_VERSION,
            "bridge_scheme": BRIDGE_SCHEME,
            "delta": delta,
            "average_percentile_rank_displacement_pp": 10.0 * delta,
            "eta_star": eta,
            "v3_epsilon_star_same_delta": v3_by_delta[delta],
            "eta_minus_v3_epsilon": eta - v3_by_delta[delta],
            "transport_cost_at_one_optimum": diag["transport_cost"],
            "solver_crosscheck_eta_star": eta_cross,
            "solver_crosscheck_absolute_difference": abs(eta - eta_cross),
            "solver_success": bool(res.success),
            "solver_status_code": int(res.status),
            "solver_message": str(res.message),
            **diag,
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "solver_method": method_primary,
            "solver_crosscheck_method": method_cross,
            **flags(),
        })
        eta_values.append(eta)

        for di, d in enumerate(data.deciles):
            directional = float(transported[di] - pseudo[di])
            scenario_support = ";".join(
                data.scenarios[si]
                for si in range(len(data.scenarios))
                if lam[di, si] > 1e-10
            )
            destination_support = ";".join(
                str(data.deciles[qi])
                for qi in range(len(data.deciles))
                if t[di, qi] > 1e-12
            )
            decile_rows.append({
                "spec_version": SPEC_VERSION,
                "delta": delta,
                "eta_star": eta,
                "decile": d,
                "pseudo_positive_modeled_annual_income_tax_share_at_one_optimum":
                    pseudo[di],
                "transported_nta_positive_self_assessed_balance_rate_at_one_optimum":
                    transported[di],
                "directional_violation_transported_minus_pseudo": directional,
                "directional_violation_excess_over_eta":
                    max(0.0, directional - eta),
                "subset_direction_satisfied_without_eta": directional <= 1e-8,
                "binding_upper_violation_within_1e8":
                    abs(directional - eta) <= 1e-8,
                "scenario_support_at_one_optimum": scenario_support,
                "nta_rank_destination_support_at_one_optimum": destination_support,
                "solution_note":
                    "one frontier optimum; scenario, grouped-NTA, and rank-transport allocations need not be unique",
                "numpy_version": np.__version__,
                "scipy_version": scipy.__version__,
                "solver_method": method_primary,
                **flags(),
            })

        for di, d in enumerate(data.deciles):
            for qi, q in enumerate(data.deciles):
                plans.append({
                    "spec_version": SPEC_VERSION,
                    "solution_source": "eta_star_frontier",
                    "delta_budget": delta,
                    "eta": eta,
                    "f_decile": d,
                    "nta_rank_decile": q,
                    "absolute_decile_distance": abs(d - q),
                    "population_transport_mass": t[di, qi],
                    "positive_self_assessed_balance_transport_mass": z[di, qi],
                    "cost_contribution": abs(d - q) * t[di, qi],
                    "population_transport_positive": t[di, qi] > 1e-12,
                    "positive_self_assessed_balance_transport_positive":
                        z[di, qi] > 1e-12,
                    **flags(),
                })

    for prev, curr in zip(eta_values, eta_values[1:]):
        if curr > prev + monotone_tol:
            raise RuntimeError(
                f"v5 eta frontier is not monotone: {prev} -> {curr}"
            )

    return frontier, decile_rows, plans


def zero_row_and_plan(data, cfg: dict[str, str]):
    eq_tol = float(cfg["equality_residual_tolerance"])
    ineq_tol = float(cfg["inequality_residual_tolerance"])
    cross_tol = float(cfg["zero_violation_tolerance"])
    method_primary = cfg["solver_method"]
    method_cross = cfg["solver_crosscheck_method"]

    model, res, delta_star, diag = solve_zero_violation_threshold(
        data, eq_tol, ineq_tol, method_primary
    )
    model_cross, res_cross, delta_cross, diag_cross = solve_zero_violation_threshold(
        data, eq_tol, ineq_tol, method_cross
    )

    if bool(res.success) != bool(res_cross.success):
        raise RuntimeError(
            "v5 zero-violation solver classification mismatch: "
            f"{res.success} vs {res_cross.success}"
        )

    if not res.success:
        row = {
            "spec_version": SPEC_VERSION,
            "bridge_scheme": BRIDGE_SCHEME,
            "zero_violation_feasible": False,
            "delta_zero_star": None,
            "average_percentile_rank_displacement_pp": None,
            "solver_crosscheck_delta_zero_star": None,
            "solver_status_code": int(res.status),
            "solver_message": str(res.message),
            "crosscheck_solver_status_code": int(res_cross.status),
            "crosscheck_solver_message": str(res_cross.message),
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "solver_method": method_primary,
            "solver_crosscheck_method": method_cross,
            **flags(),
        }
        return row, []

    if not (delta_star is not None and diag is not None):
        raise RuntimeError('scientific runtime invariant failed: research/income_tax_partial_identification/run_rank_one_sided_bridge_v5.py:621')
    if not (delta_cross is not None and diag_cross is not None):
        raise RuntimeError('scientific runtime invariant failed: research/income_tax_partial_identification/run_rank_one_sided_bridge_v5.py:622')
    if abs(delta_star - delta_cross) > cross_tol:
        raise RuntimeError(
            f"v5 zero-violation threshold mismatch: {delta_star} vs {delta_cross}"
        )

    lam, y, t, z = v3.unpack(model, res.x)
    row = {
        "spec_version": SPEC_VERSION,
        "bridge_scheme": BRIDGE_SCHEME,
        "zero_violation_feasible": True,
        "delta_zero_star": delta_star,
        "average_percentile_rank_displacement_pp": 10.0 * delta_star,
        "solver_crosscheck_delta_zero_star": delta_cross,
        "solver_crosscheck_absolute_difference": abs(delta_star - delta_cross),
        "solver_status_code": int(res.status),
        "solver_message": str(res.message),
        "crosscheck_solver_status_code": int(res_cross.status),
        "crosscheck_solver_message": str(res_cross.message),
        **diag,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "solver_method": method_primary,
        "solver_crosscheck_method": method_cross,
        **flags(),
    }

    plans = []
    for di, d in enumerate(data.deciles):
        for qi, q in enumerate(data.deciles):
            plans.append({
                "spec_version": SPEC_VERSION,
                "solution_source": "zero_violation_minimum_delta",
                "delta_budget": delta_star,
                "eta": 0.0,
                "f_decile": d,
                "nta_rank_decile": q,
                "absolute_decile_distance": abs(d - q),
                "population_transport_mass": t[di, qi],
                "positive_self_assessed_balance_transport_mass": z[di, qi],
                "cost_contribution": abs(d - q) * t[di, qi],
                "population_transport_positive": t[di, qi] > 1e-12,
                "positive_self_assessed_balance_transport_positive":
                    z[di, qi] > 1e-12,
                **flags(),
            })
    return row, plans


def build_outputs():
    cfg = read_config()
    eq_tol = float(cfg["equality_residual_tolerance"])
    ineq_tol = float(cfg["inequality_residual_tolerance"])
    deltas = delta_grid(cfg)
    data = v3.load_data(cfg)

    frontier, decile_rows, plans = frontier_rows_and_plans(data, deltas, cfg)
    zero_row, zero_plans = zero_row_and_plan(data, cfg)
    plans.extend(zero_plans)

    endpoint_rows = []
    for row in frontier:
        delta = float(row["delta"])
        eta_star = float(row["eta_star"])
        eta_eval = eta_star
        model, res, _ = fixed_feasibility(
            data, delta, eta_eval, eq_tol, ineq_tol
        )
        if not res.success:
            eta_eval = eta_star + min(1e-10, ineq_tol / 10.0)
            model, res, _ = fixed_feasibility(
                data, delta, eta_eval, eq_tol, ineq_tol
            )
            if not res.success:
                raise RuntimeError(
                    f"fixed v5 frontier point infeasible delta={delta}"
                )
        endpoint_rows.extend(
            endpoint_rows_at(
                data, delta, eta_eval, eta_star, eq_tol, ineq_tol
            )
        )

    expected_endpoints = 8 * 84
    if len(endpoint_rows) != expected_endpoints:
        raise RuntimeError(
            f"v5 endpoint count changed: {len(endpoint_rows)} "
            f"!= {expected_endpoints}"
        )

    return [
        (OUT_FRONTIER, frontier),
        (OUT_DECILE, decile_rows),
        (OUT_ZERO, [zero_row]),
        (OUT_PLANS, plans),
        (OUT_END, endpoint_rows),
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
            print(
                "ERROR: stale rank one-sided bridge v5 outputs: "
                + ", ".join(stale)
            )
            sys.exit(1)
        print(
            "rank one-sided bridge LP v5: current "
            "(8 delta budgets; one-sided eta; 672 endpoints)"
        )
        return

    for path, rows in outputs:
        path.write_text(render(rows), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")

    frontier = outputs[0][1]
    zero = outputs[2][1][0]
    print("\nv5 minimum directional-violation frontier:")
    for r in frontier:
        print(
            "delta=", fmt(r["delta"]),
            "eta_star=", fmt(r["eta_star"]),
            "v3_epsilon=", fmt(r["v3_epsilon_star_same_delta"]),
            "cost=", fmt(r["transport_cost_at_one_optimum"]),
        )
    print(
        "zero-violation:",
        "feasible=", fmt(zero["zero_violation_feasible"]),
        "delta_zero_star=", fmt(zero.get("delta_zero_star")),
    )


if __name__ == "__main__":
    main()
