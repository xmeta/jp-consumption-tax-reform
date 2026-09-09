#!/usr/bin/env python3
"""Pre-specified rank-transport-budget LP v3.

Implements rank_bridge_lp_v3_spec.adoc.  v3 replaces exact same-rank
correspondence by a population coupling T[d,q] with a pre-specified average
absolute decile-rank displacement budget.  Positive-liability transport z[d,q]
is represented separately so the model remains linear.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import csv
import io
import math
import sys

import numpy as np
import scipy
from scipy.optimize import linprog

import run_rank_bridge_lp_v2 as v2

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

CONFIG = HERE / "rank_bridge_lp_v3_config.csv"
OUT_FRONTIER = HERE / "rank_bridge_lp_v3_minimum_relaxation_frontier.csv"
OUT_DECILE = HERE / "rank_bridge_lp_v3_minimum_decile_diagnostics.csv"
OUT_ZERO = HERE / "rank_bridge_lp_v3_zero_discrepancy_threshold.csv"
OUT_ANALYTIC = HERE / "rank_bridge_lp_v3_analytical_rate_floor.csv"
OUT_PLANS = HERE / "rank_bridge_lp_v3_transport_plans.csv"
OUT_END = HERE / "rank_bridge_lp_v3_endpoints.csv"

SPEC_VERSION = "rank_bridge_lp_v3"
STATUS = "MODEL_CONTINGENT_RANK_TRANSPORT_BUDGET"
HISTORICAL_V6_REPRODUCED = False
P1C13_V1_MODIFIED = False
P1C14_V2_MODIFIED = False

DECILE_METRICS = (
    "taxable_income_weighted_mean_MTR",
    "income_tax_liability_weighted_mean_MTR",
    "pseudo_filer_positive_tax_share",
    "transported_nta_positive_liability_rate",
)
OVERALL_METRICS = (
    "taxable_income_weighted_mean_MTR",
    "income_tax_liability_weighted_mean_MTR",
)


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
    required = {
        "spec_version": SPEC_VERSION,
        "input_pseudofiler_scenarios": "all_13_committed_pseudofiler_scenarios",
        "input_nta_artifact": "nta_income_class_primary_type_filing_status_2024.csv",
        "nta_income_class_count": "25",
        "bridge_scheme": "rank_transport_budget",
        "rank_bin_mass": "0.1",
        "within_class_positive_allocation": "free_within_overlap_capacity",
        "transport_positive_allocation": "free_within_transport_capacity",
        "rank_cost": "absolute_decile_index_distance",
        "delta_unrestricted": "5",
        "zero_discrepancy_threshold": "solve_minimum_delta_at_epsilon_0",
        "frontier_endpoint_rule": "epsilon_star_at_each_delta",
        "overall_weight_scheme": "equal_decile",
        "public_diagnostics_role": "interpretation_only_no_hard_crosswalk",
        "solver": "scipy.optimize.linprog",
        "solver_method": "highs-ds",
        "solver_crosscheck_method": "highs-ipm",
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "historical_v6_restricted_lp_reproduced": "false",
        "p1c13_v1_modified": "false",
        "p1c14_v2_modified": "false",
        "paper1_claim_before_ci": "false",
    }
    for key, expected in required.items():
        if cfg.get(key) != expected:
            raise RuntimeError(
                f"pre-specification mismatch: {key}={cfg.get(key)!r}, expected {expected!r}"
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


def load_data(cfg: dict[str, str]) -> v2.Data:
    deciles, scenarios, u, mt, ml = v2.load_pseudo()
    idx, labels, A, P = v2.load_nta_classes()
    N = float(A.sum())
    a = A / N
    p = P / N
    overlap = v2.build_overlap(a)
    if len(idx) != int(cfg["nta_income_class_count"]):
        raise RuntimeError("NTA income-class count changed")
    if abs(float(cfg["rank_bin_mass"]) - 0.1) > 1e-15:
        raise RuntimeError("rank-bin mass changed")
    return v2.Data(
        deciles=deciles,
        scenarios=scenarios,
        class_index=idx,
        class_label=labels,
        class_population=A,
        class_positive=P,
        total_population=N,
        class_mass=a,
        class_positive_mass=p,
        overlap=overlap,
        u=u,
        m_taxable=mt,
        m_liability=ml,
    )


@dataclass
class Model:
    data: v2.Data
    include_epsilon: bool
    lambda_index: dict[tuple[int, int], int]
    y_index: dict[tuple[int, int], int]
    t_index: dict[tuple[int, int], int]
    z_index: dict[tuple[int, int], int]
    epsilon_index: int | None
    nvars: int
    A_eq: np.ndarray
    b_eq: np.ndarray
    bounds: list[tuple[float | None, float | None]]


def make_model(data: v2.Data, include_epsilon: bool) -> Model:
    D = len(data.deciles)
    S = len(data.scenarios)
    J = len(data.class_index)
    n = 0

    lam_idx = {}
    for di in range(D):
        for si in range(S):
            lam_idx[(di, si)] = n
            n += 1

    y_idx = {}
    for ji in range(J):
        for qi in range(D):
            y_idx[(ji, qi)] = n
            n += 1

    t_idx = {}
    for di in range(D):
        for qi in range(D):
            t_idx[(di, qi)] = n
            n += 1

    z_idx = {}
    for di in range(D):
        for qi in range(D):
            z_idx[(di, qi)] = n
            n += 1

    eps_idx = n if include_epsilon else None
    if include_epsilon:
        n += 1

    eq_rows = []
    eq_rhs = []

    # Pseudo-filer scenario mixture per F decile.
    for di in range(D):
        a = np.zeros(n)
        for si in range(S):
            a[lam_idx[(di, si)]] = 1.0
        eq_rows.append(a)
        eq_rhs.append(1.0)

    # Positive-liability mass within each NTA grouped income class.
    for ji in range(J):
        a = np.zeros(n)
        for qi in range(D):
            a[y_idx[(ji, qi)]] = 1.0
        eq_rows.append(a)
        eq_rhs.append(data.class_positive_mass[ji])

    # Population coupling: F-decile row margins.
    for di in range(D):
        a = np.zeros(n)
        for qi in range(D):
            a[t_idx[(di, qi)]] = 1.0
        eq_rows.append(a)
        eq_rhs.append(0.1)

    # Population coupling: NTA-rank column margins.
    for qi in range(D):
        a = np.zeros(n)
        for di in range(D):
            a[t_idx[(di, qi)]] = 1.0
        eq_rows.append(a)
        eq_rhs.append(0.1)

    # Positive transport preserves each NTA-rank positive margin.
    for qi in range(D):
        a = np.zeros(n)
        for di in range(D):
            a[z_idx[(di, qi)]] = 1.0
        for ji in range(J):
            a[y_idx[(ji, qi)]] -= 1.0
        eq_rows.append(a)
        eq_rhs.append(0.0)

    bounds: list[tuple[float | None, float | None]] = [(0.0, None)] * n

    for ji in range(J):
        for qi in range(D):
            bounds[y_idx[(ji, qi)]] = (0.0, float(data.overlap[ji, qi]))

    for di in range(D):
        for qi in range(D):
            bounds[t_idx[(di, qi)]] = (0.0, 0.1)
            bounds[z_idx[(di, qi)]] = (0.0, 0.1)

    if include_epsilon:
        assert eps_idx is not None
        bounds[eps_idx] = (0.0, 1.0)

    return Model(
        data=data,
        include_epsilon=include_epsilon,
        lambda_index=lam_idx,
        y_index=y_idx,
        t_index=t_idx,
        z_index=z_idx,
        epsilon_index=eps_idx,
        nvars=n,
        A_eq=np.vstack(eq_rows),
        b_eq=np.array(eq_rhs),
        bounds=bounds,
    )


def transport_cost_vector(model: Model) -> np.ndarray:
    c = np.zeros(model.nvars)
    D = len(model.data.deciles)
    for di in range(D):
        for qi in range(D):
            c[model.t_index[(di, qi)]] = abs(di - qi)
    return c


def inequalities(
    model: Model,
    delta: float | None,
    epsilon: float | None,
) -> tuple[np.ndarray, np.ndarray]:
    data = model.data
    D = len(data.deciles)
    S = len(data.scenarios)
    rows = []
    rhs = []

    # Positive-liability transport cannot exceed population transport.
    for di in range(D):
        for qi in range(D):
            a = np.zeros(model.nvars)
            a[model.z_index[(di, qi)]] = 1.0
            a[model.t_index[(di, qi)]] = -1.0
            rows.append(a)
            rhs.append(0.0)

    # Rank-displacement budget. delta=None means unrestricted for the
    # minimum-cost zero-discrepancy problem.
    if delta is not None:
        rows.append(transport_cost_vector(model))
        rhs.append(float(delta))

    # Per-F-decile pseudo-filer versus transported-NTA rate discrepancy.
    for di in range(D):
        a = np.zeros(model.nvars)
        for si in range(S):
            a[model.lambda_index[(di, si)]] = data.u[di, si]
        for qi in range(D):
            a[model.z_index[(di, qi)]] -= 10.0

        if model.include_epsilon:
            assert model.epsilon_index is not None
            a[model.epsilon_index] = -1.0
            b = 0.0
        else:
            assert epsilon is not None
            b = float(epsilon)
        rows.append(a)
        rhs.append(b)

        bvec = -a
        if model.include_epsilon:
            assert model.epsilon_index is not None
            bvec[model.epsilon_index] = -1.0
        rows.append(bvec)
        rhs.append(b)

    return np.vstack(rows), np.array(rhs)


def solve_lp(
    model: Model,
    c: np.ndarray,
    delta: float | None,
    epsilon: float | None = None,
    method: str = "highs-ds",
):
    A_ub, b_ub = inequalities(model, delta, epsilon)
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


def unpack(model: Model, x: np.ndarray):
    data = model.data
    D = len(data.deciles)
    S = len(data.scenarios)
    J = len(data.class_index)
    lam = np.zeros((D, S))
    y = np.zeros((J, D))
    t = np.zeros((D, D))
    z = np.zeros((D, D))
    for di in range(D):
        for si in range(S):
            lam[di, si] = x[model.lambda_index[(di, si)]]
    for ji in range(J):
        for qi in range(D):
            y[ji, qi] = x[model.y_index[(ji, qi)]]
    for di in range(D):
        for qi in range(D):
            t[di, qi] = x[model.t_index[(di, qi)]]
            z[di, qi] = x[model.z_index[(di, qi)]]
    return lam, y, t, z


def diagnostics(
    model: Model,
    x: np.ndarray,
    delta_requested: float | None,
    epsilon_requested: float,
) -> dict[str, float]:
    data = model.data
    lam, y, t, z = unpack(model, x)
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
        0.0 if delta_requested is None
        else max(0.0, transport_cost - delta_requested)
    )
    pseudo = np.sum(lam * data.u, axis=1)
    transported = 10.0 * z.sum(axis=1)
    gaps = np.abs(pseudo - transported)
    max_gap = float(np.max(gaps))
    gap_excess = max(0.0, max_gap - epsilon_requested)
    minimum_var = float(
        min(np.min(lam), np.min(y), np.min(t), np.min(z))
    )
    return {
        "max_scenario_sum_residual": scenario_res,
        "max_class_positive_mass_residual": class_pos_res,
        "max_overlap_capacity_excess": overlap_excess,
        "max_transport_row_margin_residual": t_row_res,
        "max_transport_column_margin_residual": t_col_res,
        "max_positive_transport_capacity_excess": z_capacity_excess,
        "max_nta_rank_positive_margin_residual": z_col_res,
        "transport_cost": transport_cost,
        "rank_displacement_budget_excess": displacement_excess,
        "max_rank_bridge_gap": max_gap,
        "max_rank_bridge_inequality_excess": gap_excess,
        "minimum_decision_variable": minimum_var,
    }


def assert_solution(diag, eq_tol: float, ineq_tol: float) -> None:
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
        "max_positive_transport_capacity_excess",
        "rank_displacement_budget_excess",
        "max_rank_bridge_inequality_excess",
    ):
        if diag[key] > ineq_tol:
            raise RuntimeError(f"{key} exceeds tolerance: {diag[key]}")
    if diag["minimum_decision_variable"] < -eq_tol:
        raise RuntimeError("negative decision variable")


def flags() -> dict:
    return {
        "scientific_status": STATUS,
        "historical_v6_restricted_lp_reproduced": HISTORICAL_V6_REPRODUCED,
        "p1c13_v1_modified": P1C13_V1_MODIFIED,
        "p1c14_v2_modified": P1C14_V2_MODIFIED,
    }


def analytical_rate_floor(data: v2.Data) -> dict:
    """Common-epsilon lower bound with unrestricted rank transport.

    If rank transport is unrestricted, transported NTA row rates are
    nonnegative and their equal-decile average is fixed at the NTA aggregate
    positive-liability rate.  For pseudo lower envelope l_d, feasibility at
    epsilon e requires sum max(0,l_d-e) <= 10*r_NTA.  Solve the scalar
    water-filling condition independently of the full transport LP.
    """
    lower = np.min(data.u, axis=1)
    nta_rate = float(data.class_positive.sum() / data.class_population.sum())
    pseudo_lower_average = float(np.mean(lower))
    simple_floor = max(0.0, pseudo_lower_average - nta_rate)

    lo, hi = 0.0, 1.0
    for _ in range(120):
        mid = (lo + hi) / 2.0
        if float(np.maximum(0.0, lower - mid).sum()) <= 10.0 * nta_rate:
            hi = mid
        else:
            lo = mid
    floor = hi
    binding_zero = ";".join(
        str(data.deciles[di])
        for di, value in enumerate(lower)
        if value <= floor + 1e-12
    )
    return {
        "spec_version": SPEC_VERSION,
        "nta_aggregate_positive_liability_rate": nta_rate,
        "pseudo_filer_lower_envelope_equal_decile_average":
            pseudo_lower_average,
        "simple_average_gap_floor": simple_floor,
        "unrestricted_nonnegative_rate_floor": floor,
        "pseudo_lower_envelope_deciles_below_floor": binding_zero,
        "derivation":
            "min e such that sum_d max(0,min_s(u_ds)-e) <= 10*NTA aggregate positive-liability rate",
        "interpretation":
            "analytical lower bound under unrestricted rank coupling and nonnegative transported row rates; not a confidence bound",
        **flags(),
    }


def solve_minimum_at_delta(
    data: v2.Data,
    delta: float,
    eq_tol: float,
    ineq_tol: float,
    method: str = "highs-ds",
):
    model = make_model(data, include_epsilon=True)
    c = np.zeros(model.nvars)
    assert model.epsilon_index is not None
    c[model.epsilon_index] = 1.0
    res = solve_lp(model, c, delta=delta, method=method)
    if not res.success:
        raise RuntimeError(
            f"v3 minimum epsilon failed delta={delta}: {res.status} {res.message}"
        )
    eps = float(res.x[model.epsilon_index])
    diag = diagnostics(model, res.x, delta, eps)
    assert_solution(diag, eq_tol, ineq_tol)
    return model, res, eps, diag


def solve_zero_discrepancy_threshold(
    data: v2.Data,
    eq_tol: float,
    ineq_tol: float,
    method: str = "highs-ds",
):
    model = make_model(data, include_epsilon=False)
    c = transport_cost_vector(model)
    res = solve_lp(model, c, delta=None, epsilon=0.0, method=method)
    if not res.success:
        return model, res, None, None
    delta_star = float(np.dot(c, res.x))
    diag = diagnostics(model, res.x, None, 0.0)
    assert_solution(diag, eq_tol, ineq_tol)
    if abs(diag["transport_cost"] - delta_star) > 1e-9:
        raise RuntimeError("zero-discrepancy cost recomputation mismatch")
    return model, res, delta_star, diag


def objective_vector(
    model: Model,
    metric: str,
    decile_index: int | None,
    overall: bool,
) -> np.ndarray:
    data = model.data
    c = np.zeros(model.nvars)
    if metric == "taxable_income_weighted_mean_MTR":
        values = data.m_taxable
    elif metric == "income_tax_liability_weighted_mean_MTR":
        values = data.m_liability
    elif metric == "pseudo_filer_positive_tax_share":
        values = data.u
    elif metric == "transported_nta_positive_liability_rate":
        if overall:
            raise ValueError("overall transported NTA rate not pre-specified")
        assert decile_index is not None
        for qi in range(len(data.deciles)):
            c[model.z_index[(decile_index, qi)]] = 10.0
        return c
    else:
        raise ValueError(metric)

    if overall:
        if metric not in OVERALL_METRICS:
            raise ValueError(metric)
        for di in range(len(data.deciles)):
            for si in range(len(data.scenarios)):
                c[model.lambda_index[(di, si)]] = 0.1 * values[di, si]
    else:
        assert decile_index is not None
        for si in range(len(data.scenarios)):
            c[model.lambda_index[(decile_index, si)]] = values[decile_index, si]
    return c


def fixed_feasibility(
    data: v2.Data,
    delta: float,
    epsilon: float,
    eq_tol: float,
    ineq_tol: float,
):
    model = make_model(data, include_epsilon=False)
    res = solve_lp(
        model, np.zeros(model.nvars), delta=delta, epsilon=epsilon
    )
    if not res.success:
        return model, res, None
    diag = diagnostics(model, res.x, delta, epsilon)
    assert_solution(diag, eq_tol, ineq_tol)
    return model, res, diag


def endpoint_rows_at(
    data: v2.Data,
    delta: float,
    epsilon: float,
    frontier_source: str,
    eq_tol: float,
    ineq_tol: float,
) -> list[dict]:
    model, feas, _ = fixed_feasibility(
        data, delta, epsilon, eq_tol, ineq_tol
    )
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
        c = objective_vector(model, metric, di, overall)
        for bound_name, sign in (("min", 1.0), ("max", -1.0)):
            res = solve_lp(
                model, sign * c, delta=delta, epsilon=epsilon
            )
            if not res.success:
                raise RuntimeError(
                    f"v3 endpoint failed delta={delta} eps={epsilon} "
                    f"{scope} {d_label} {metric} {bound_name}: "
                    f"{res.status} {res.message}"
                )
            diag = diagnostics(model, res.x, delta, epsilon)
            assert_solution(diag, eq_tol, ineq_tol)
            raw = float(np.dot(c, res.x))
            solver = float(sign * res.fun)
            if abs(raw - solver) > 1e-9:
                raise RuntimeError(
                    f"objective recomputation mismatch: {raw} vs {solver}"
                )
            rows.append({
                "spec_version": SPEC_VERSION,
                "bridge_scheme": "rank_transport_budget",
                "frontier_source": frontier_source,
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
    return rows


def frontier_rows_and_plans(
    data: v2.Data,
    deltas: list[float],
    eq_tol: float,
    ineq_tol: float,
):
    frontier = []
    decile_rows = []
    plans = []
    solutions = []

    for delta in deltas:
        model, res, eps, diag = solve_minimum_at_delta(
            data, delta, eq_tol, ineq_tol
        )
        lam, y, t, z = unpack(model, res.x)
        pseudo = np.sum(lam * data.u, axis=1)
        transported = 10.0 * z.sum(axis=1)

        frontier.append({
            "spec_version": SPEC_VERSION,
            "bridge_scheme": "rank_transport_budget",
            "delta": delta,
            "average_percentile_rank_displacement_pp": 10.0 * delta,
            "epsilon_star": eps,
            "transport_cost_at_one_optimum": diag["transport_cost"],
            "solver_success": bool(res.success),
            "solver_status_code": int(res.status),
            "solver_message": str(res.message),
            **diag,
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "solver_method": "highs-ds",
            **flags(),
        })

        for di, d in enumerate(data.deciles):
            gap = float(pseudo[di] - transported[di])
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
                "epsilon_star": eps,
                "decile": d,
                "pseudo_positive_tax_share_at_one_optimum": pseudo[di],
                "transported_nta_positive_liability_rate_at_one_optimum":
                    transported[di],
                "signed_gap_pseudo_minus_transported_nta": gap,
                "absolute_gap": abs(gap),
                "binding_within_1e8": abs(abs(gap) - eps) <= 1e-8,
                "scenario_support_at_one_optimum": scenario_support,
                "nta_rank_destination_support_at_one_optimum":
                    destination_support,
                "solution_note":
                    "one frontier optimum; scenario, grouped-NTA, and rank-transport allocations need not be unique",
                "numpy_version": np.__version__,
                "scipy_version": scipy.__version__,
                "solver_method": "highs-ds",
                **flags(),
            })

        for di, d in enumerate(data.deciles):
            for qi, q in enumerate(data.deciles):
                plans.append({
                    "spec_version": SPEC_VERSION,
                    "solution_source": "epsilon_star_frontier",
                    "delta_budget": delta,
                    "epsilon": eps,
                    "f_decile": d,
                    "nta_rank_decile": q,
                    "absolute_decile_distance": abs(d - q),
                    "population_transport_mass": t[di, qi],
                    "positive_liability_transport_mass": z[di, qi],
                    "cost_contribution": abs(d - q) * t[di, qi],
                    "population_transport_positive": t[di, qi] > 1e-12,
                    "positive_transport_positive": z[di, qi] > 1e-12,
                    **flags(),
                })
        solutions.append((delta, eps, model, res, diag))
    return frontier, decile_rows, plans, solutions


def zero_row_and_plan(
    data: v2.Data,
    eq_tol: float,
    ineq_tol: float,
):
    model, res, delta_star, diag = solve_zero_discrepancy_threshold(
        data, eq_tol, ineq_tol
    )
    if not res.success:
        row = {
            "spec_version": SPEC_VERSION,
            "bridge_scheme": "rank_transport_budget",
            "zero_discrepancy_feasible": False,
            "delta_zero_star": None,
            "average_percentile_rank_displacement_pp": None,
            "solver_status_code": int(res.status),
            "solver_message": str(res.message),
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "solver_method": "highs-ds",
            **flags(),
        }
        return row, [], None

    assert delta_star is not None and diag is not None
    lam, y, t, z = unpack(model, res.x)
    row = {
        "spec_version": SPEC_VERSION,
        "bridge_scheme": "rank_transport_budget",
        "zero_discrepancy_feasible": True,
        "delta_zero_star": delta_star,
        "average_percentile_rank_displacement_pp": 10.0 * delta_star,
        "solver_status_code": int(res.status),
        "solver_message": str(res.message),
        **diag,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "solver_method": "highs-ds",
        **flags(),
    }
    plans = []
    for di, d in enumerate(data.deciles):
        for qi, q in enumerate(data.deciles):
            plans.append({
                "spec_version": SPEC_VERSION,
                "solution_source": "zero_discrepancy_minimum_delta",
                "delta_budget": delta_star,
                "epsilon": 0.0,
                "f_decile": d,
                "nta_rank_decile": q,
                "absolute_decile_distance": abs(d - q),
                "population_transport_mass": t[di, qi],
                "positive_liability_transport_mass": z[di, qi],
                "cost_contribution": abs(d - q) * t[di, qi],
                "population_transport_positive": t[di, qi] > 1e-12,
                "positive_transport_positive": z[di, qi] > 1e-12,
                **flags(),
            })
    return row, plans, (model, res, delta_star, diag)


def build_outputs():
    cfg = read_config()
    eq_tol = float(cfg["equality_residual_tolerance"])
    ineq_tol = float(cfg["inequality_residual_tolerance"])
    deltas = delta_grid(cfg)
    data = load_data(cfg)

    analytic_row = analytical_rate_floor(data)
    frontier, decile_rows, plans, _ = frontier_rows_and_plans(
        data, deltas, eq_tol, ineq_tol
    )
    zero_row, zero_plans, zero_solution = zero_row_and_plan(
        data, eq_tol, ineq_tol
    )
    plans.extend(zero_plans)

    endpoint_rows = []
    for row in frontier:
        delta = float(row["delta"])
        eps_star = float(row["epsilon_star"])
        eps_eval = eps_star
        model, res, _ = fixed_feasibility(
            data, delta, eps_eval, eq_tol, ineq_tol
        )
        if not res.success:
            eps_eval = eps_star + min(1e-10, ineq_tol / 10.0)
            model, res, _ = fixed_feasibility(
                data, delta, eps_eval, eq_tol, ineq_tol
            )
            if not res.success:
                raise RuntimeError(
                    f"fixed frontier point infeasible delta={delta}"
                )
        q = endpoint_rows_at(
            data, delta, eps_eval, "epsilon_star_frontier",
            eq_tol, ineq_tol
        )
        for r in q:
            r["epsilon"] = eps_star
        endpoint_rows.extend(q)

    if zero_solution is not None:
        delta_star = float(zero_row["delta_zero_star"])
        if all(abs(delta_star - x) > 1e-10 for x in deltas):
            delta_eval = delta_star
            model, res, _ = fixed_feasibility(
                data, delta_eval, 0.0, eq_tol, ineq_tol
            )
            if not res.success:
                delta_eval = delta_star + min(1e-10, ineq_tol / 10.0)
                model, res, _ = fixed_feasibility(
                    data, delta_eval, 0.0, eq_tol, ineq_tol
                )
                if not res.success:
                    raise RuntimeError(
                        "zero-discrepancy threshold infeasible in fixed form"
                    )
            q = endpoint_rows_at(
                data, delta_eval, 0.0,
                "zero_discrepancy_minimum_delta", eq_tol, ineq_tol
            )
            for r in q:
                r["delta"] = delta_star
                r["average_percentile_rank_displacement_pp"] = 10.0 * delta_star
            endpoint_rows.extend(q)

    return [
        (OUT_FRONTIER, frontier),
        (OUT_DECILE, decile_rows),
        (OUT_ZERO, [zero_row]),
        (OUT_ANALYTIC, [analytic_row]),
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
            print("ERROR: stale rank-bridge LP v3 outputs: " + ", ".join(stale))
            sys.exit(1)
        print(
            "rank-transport budget LP v3: current "
            "(8 delta budgets; v2 nested at delta=0)"
        )
        return

    for path, rows in outputs:
        path.write_text(render(rows), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")

    frontier = outputs[0][1]
    zero = outputs[2][1][0]
    print("\nv3 minimum-discrepancy frontier:")
    for r in frontier:
        print(
            "delta=", fmt(r["delta"]),
            "epsilon_star=", fmt(r["epsilon_star"]),
            "cost=", fmt(r["transport_cost_at_one_optimum"]),
        )
    print(
        "zero-discrepancy:",
        "feasible=", fmt(zero["zero_discrepancy_feasible"]),
        "delta_zero_star=", fmt(zero.get("delta_zero_star")),
    )


if __name__ == "__main__":
    main()
