#!/usr/bin/env python3
"""Pre-specified replacement transport-relaxation LP v1.

This is a NEW model-contingent sensitivity analysis.  It is deliberately not
named or represented as a restoration of the historical V6 restricted LP.

The model specification was committed before endpoint computation in:
  replacement_transport_lp_spec.adoc
  replacement_transport_lp_config.csv

Scientific status of every numerical output:
  MODEL_CONTINGENT_TRANSPORT_RELAXATION
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

CONFIG = HERE / "replacement_transport_lp_config.csv"
SCENARIOS_FILE = (
    ROOT / "research/income_tax_pseudofiler/pseudofiler_mtr_scenarios.csv"
)
LEAF_FILE = (
    ROOT / "data/derived/income_tax_household_type_leaf_deciles_2024.csv"
)
STAGE2_FILE = ROOT / "data/derived/nta_primary_type_stage2_2024.csv"

OUT_MIN = HERE / "replacement_transport_lp_minimum_relaxation.csv"
OUT_MIN_DECILE = HERE / "replacement_transport_lp_minimum_decile_diagnostics.csv"
OUT_FEAS = HERE / "replacement_transport_lp_feasibility.csv"
OUT_END = HERE / "replacement_transport_lp_endpoints.csv"
OUT_WEIGHTS = HERE / "replacement_transport_lp_decile_weights.csv"

STATUS = "MODEL_CONTINGENT_TRANSPORT_RELAXATION"
SPEC_VERSION = "transport_lp_v1"
HISTORICAL_V6_REPRODUCED = False

EXPECTED_SCENARIOS = (
    "central",
    "f71911_topcode10",
    "size_lower",
    "size_upper",
    "business_proportional",
    "other_wage_split2",
    "no_social_deduction_proxy",
    "nta_salary_social",
    "nta_salary_dependents",
    "pension_head_merge",
    "pension_age_split_separate",
    "pension_member_split",
    "pension_member_split_f71551",
)
EXPECTED_CATEGORIES = (
    "business",
    "real_estate",
    "salary",
    "miscellaneous",
    "other",
)
METRICS = (
    "taxable_income_weighted_mean_MTR",
    "income_tax_liability_weighted_mean_MTR",
    "pseudo_positive_modeled_annual_income_tax_share",
)
OVERALL_METRICS = (
    "taxable_income_weighted_mean_MTR",
    "income_tax_liability_weighted_mean_MTR",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_config() -> dict[str, str]:
    rows = read_csv(CONFIG)
    cfg = {r["key"]: r["value"] for r in rows}
    if cfg.get("spec_version") != SPEC_VERSION:
        raise RuntimeError(
            f"spec version mismatch: {cfg.get('spec_version')} != {SPEC_VERSION}"
        )
    if cfg.get("scenario_set") != "all_13_committed_pseudofiler_scenarios":
        raise RuntimeError("scenario_set changed after pre-specification")
    if cfg.get("solver") != "scipy.optimize.linprog":
        raise RuntimeError("solver changed after pre-specification")
    if cfg.get("solver_method") != "highs-ds":
        raise RuntimeError("solver method changed after pre-specification")
    if cfg.get("numpy_version") != np.__version__:
        raise RuntimeError(
            f"NumPy version mismatch: required={cfg.get('numpy_version')} "
            f"actual={np.__version__}"
        )
    if cfg.get("scipy_version") != scipy.__version__:
        raise RuntimeError(
            f"SciPy version mismatch: required={cfg.get('scipy_version')} "
            f"actual={scipy.__version__}"
        )
    return cfg


def f(x: str | float | int) -> float:
    return float(x)


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


@dataclass(frozen=True)
class ModelData:
    deciles: tuple[int, ...]
    scenarios: tuple[str, ...]
    categories: tuple[str, ...]
    p: np.ndarray       # D x S
    m_taxable: np.ndarray
    m_liability: np.ndarray
    q: np.ndarray       # K
    r: np.ndarray       # K
    weight_schemes: dict[str, np.ndarray]


@dataclass
class MatrixModel:
    data: ModelData
    weights: np.ndarray
    weight_scheme: str
    include_epsilon: bool
    lambda_index: dict[tuple[int, int], int]
    x_index: dict[tuple[int, int], int]
    epsilon_index: int | None
    nvars: int
    A_eq: np.ndarray
    b_eq: np.ndarray


def load_model_data(cfg: dict[str, str]) -> ModelData:
    scenario_rows = read_csv(SCENARIOS_FILE)
    by_decile: dict[int, dict[str, dict[str, str]]] = {}
    for row in scenario_rows:
        d = int(row["decile"])
        s = row["scenario"]
        by_decile.setdefault(d, {})[s] = row

    deciles = tuple(sorted(by_decile))
    if deciles != tuple(range(1, 11)):
        raise RuntimeError(f"decile set changed: {deciles}")

    seen_scenarios = tuple(sorted({r["scenario"] for r in scenario_rows}))
    if set(seen_scenarios) != set(EXPECTED_SCENARIOS):
        raise RuntimeError(
            f"scenario set changed: got={seen_scenarios} "
            f"expected={EXPECTED_SCENARIOS}"
        )
    scenarios = EXPECTED_SCENARIOS
    for d in deciles:
        if set(by_decile[d]) != set(scenarios):
            raise RuntimeError(f"decile {d} does not contain all 13 scenarios")

    p = np.empty((len(deciles), len(scenarios)))
    mt = np.empty_like(p)
    ml = np.empty_like(p)
    for di, d in enumerate(deciles):
        for si, s in enumerate(scenarios):
            row = by_decile[d][s]
            p[di, si] = f(row["pseudo_positive_modeled_annual_income_tax_share"])
            mt[di, si] = f(row["taxable_income_weighted_mean_MTR"])
            ml[di, si] = f(row["income_tax_liability_weighted_mean_MTR"])

    stage2 = read_csv(STAGE2_FILE)
    by_cat = {row["primary_income_type"]: row for row in stage2}
    if set(by_cat) != set(EXPECTED_CATEGORIES):
        raise RuntimeError(
            f"NTA category set changed: got={sorted(by_cat)} "
            f"expected={EXPECTED_CATEGORIES}"
        )
    categories = EXPECTED_CATEGORIES
    table22_counts = np.array(
        [f(by_cat[k]["table22_population_persons_exact"]) for k in categories],
        dtype=float,
    )
    positive_counts = np.array(
        [f(by_cat[k]["positive_self_assessed_balance_persons_exact"]) for k in categories],
        dtype=float,
    )
    q = table22_counts / table22_counts.sum()
    r = positive_counts / table22_counts
    if not math.isclose(float(q.sum()), 1.0, abs_tol=1e-12):
        raise RuntimeError("NTA category shares do not sum to one")

    leaf_rows = read_csv(LEAF_FILE)
    counts = np.zeros(len(deciles), dtype=float)
    for row in leaf_rows:
        d = int(row["decile"])
        counts[d - 1] += f(row["household_count_approx"] or 0)
    if np.any(counts <= 0):
        raise RuntimeError("non-positive F71561 decile leaf count")

    schemes = tuple(cfg["weight_schemes"].split(";"))
    if schemes != ("equal_decile", "f71561_leaf_count_normalized"):
        raise RuntimeError(f"weight schemes changed: {schemes}")
    weight_schemes = {
        "equal_decile": np.full(len(deciles), 1.0 / len(deciles)),
        "f71561_leaf_count_normalized": counts / counts.sum(),
    }

    return ModelData(
        deciles=deciles,
        scenarios=scenarios,
        categories=categories,
        p=p,
        m_taxable=mt,
        m_liability=ml,
        q=q,
        r=r,
        weight_schemes=weight_schemes,
    )


def make_model(
    data: ModelData,
    weight_scheme: str,
    include_epsilon: bool,
) -> MatrixModel:
    w = data.weight_schemes[weight_scheme]
    D = len(data.deciles)
    S = len(data.scenarios)
    K = len(data.categories)

    lam_idx = {}
    n = 0
    for di in range(D):
        for si in range(S):
            lam_idx[(di, si)] = n
            n += 1

    x_idx = {}
    for di in range(D):
        for ki in range(K):
            x_idx[(di, ki)] = n
            n += 1

    eps_idx = n if include_epsilon else None
    if include_epsilon:
        n += 1

    rows = []
    rhs = []

    # Scenario convex mixtures.
    for di in range(D):
        a = np.zeros(n)
        for si in range(S):
            a[lam_idx[(di, si)]] = 1.0
        rows.append(a)
        rhs.append(1.0)

    # Decile transported mass.
    for di in range(D):
        a = np.zeros(n)
        for ki in range(K):
            a[x_idx[(di, ki)]] = 1.0
        rows.append(a)
        rhs.append(w[di])

    # First four category sums. Fifth is redundant given the row sums.
    for ki in range(K - 1):
        a = np.zeros(n)
        for di in range(D):
            a[x_idx[(di, ki)]] = 1.0
        rows.append(a)
        rhs.append(data.q[ki])

    return MatrixModel(
        data=data,
        weights=w,
        weight_scheme=weight_scheme,
        include_epsilon=include_epsilon,
        lambda_index=lam_idx,
        x_index=x_idx,
        epsilon_index=eps_idx,
        nvars=n,
        A_eq=np.vstack(rows),
        b_eq=np.array(rhs),
    )


def link_inequalities(
    model: MatrixModel,
    epsilon: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    data = model.data
    D, S = data.p.shape
    K = len(data.categories)
    rows = []
    rhs = []

    for di in range(D):
        # + (p - r) <= epsilon
        a = np.zeros(model.nvars)
        for si in range(S):
            a[model.lambda_index[(di, si)]] = (
                model.weights[di] * data.p[di, si]
            )
        for ki in range(K):
            a[model.x_index[(di, ki)]] = -data.r[ki]
        if model.include_epsilon:
            assert model.epsilon_index is not None
            a[model.epsilon_index] = -model.weights[di]
            b = 0.0
        else:
            assert epsilon is not None
            b = epsilon * model.weights[di]
        rows.append(a)
        rhs.append(b)

        # - (p - r) <= epsilon
        a = -a
        if model.include_epsilon:
            # Negating the previous row would make epsilon coefficient positive.
            # Restore the required -epsilon*w term explicitly.
            assert model.epsilon_index is not None
            a[model.epsilon_index] = -model.weights[di]
        rows.append(a)
        rhs.append(b)

    return np.vstack(rows), np.array(rhs)


def bounds_for(model: MatrixModel):
    bounds = [(0.0, None)] * model.nvars
    if model.include_epsilon:
        assert model.epsilon_index is not None
        bounds[model.epsilon_index] = (0.0, 1.0)
    return bounds


def solve_lp(
    model: MatrixModel,
    c: np.ndarray,
    epsilon: float | None = None,
):
    A_ub, b_ub = link_inequalities(model, epsilon)
    res = linprog(
        c,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=model.A_eq,
        b_eq=model.b_eq,
        bounds=bounds_for(model),
        method="highs-ds",
        options={
            "presolve": True,
            "dual_feasibility_tolerance": 1e-9,
            "primal_feasibility_tolerance": 1e-9,
        },
    )
    return res


def unpack_solution(model: MatrixModel, z: np.ndarray):
    data = model.data
    D = len(data.deciles)
    S = len(data.scenarios)
    K = len(data.categories)
    lam = np.zeros((D, S))
    x = np.zeros((D, K))
    for di in range(D):
        for si in range(S):
            lam[di, si] = z[model.lambda_index[(di, si)]]
        for ki in range(K):
            x[di, ki] = z[model.x_index[(di, ki)]]
    return lam, x


def diagnostics(
    model: MatrixModel,
    z: np.ndarray,
    epsilon_requested: float,
) -> dict[str, float]:
    data = model.data
    lam, x = unpack_solution(model, z)
    scenario_res = float(np.max(np.abs(lam.sum(axis=1) - 1.0)))
    decile_mass_res = float(
        np.max(np.abs(x.sum(axis=1) - model.weights))
    )
    category_mass_res = float(
        np.max(np.abs(x.sum(axis=0) - data.q))
    )
    pseudo = np.sum(lam * data.p, axis=1)
    transported = (x @ data.r) / model.weights
    gaps = np.abs(pseudo - transported)
    max_gap = float(np.max(gaps))
    inequality_excess = max(0.0, max_gap - epsilon_requested)
    min_variable = float(min(np.min(lam), np.min(x)))
    return {
        "max_scenario_sum_residual": scenario_res,
        "max_decile_mass_residual": decile_mass_res,
        "max_category_mass_residual": category_mass_res,
        "max_transport_gap": max_gap,
        "max_transport_inequality_excess": inequality_excess,
        "minimum_decision_variable": min_variable,
    }


def assert_solution(
    diag: dict[str, float],
    eq_tol: float,
    ineq_tol: float,
) -> None:
    for key in (
        "max_scenario_sum_residual",
        "max_decile_mass_residual",
        "max_category_mass_residual",
    ):
        if diag[key] > eq_tol:
            raise RuntimeError(f"{key}={diag[key]} > {eq_tol}")
    if diag["max_transport_inequality_excess"] > ineq_tol:
        raise RuntimeError(
            "transport inequality violation "
            f"{diag['max_transport_inequality_excess']} > {ineq_tol}"
        )
    if diag["minimum_decision_variable"] < -eq_tol:
        raise RuntimeError(
            "negative decision variable "
            f"{diag['minimum_decision_variable']}"
        )


def objective_vector(
    model: MatrixModel,
    metric: str,
    decile_index: int | None,
    overall: bool,
) -> np.ndarray:
    c = np.zeros(model.nvars)
    data = model.data
    if metric == "taxable_income_weighted_mean_MTR":
        values = data.m_taxable
    elif metric == "income_tax_liability_weighted_mean_MTR":
        values = data.m_liability
    elif metric == "pseudo_positive_modeled_annual_income_tax_share":
        values = data.p
    else:
        raise ValueError(metric)

    if overall:
        if metric == "pseudo_positive_modeled_annual_income_tax_share":
            raise ValueError("overall positive-share endpoint not pre-specified")
        for di in range(len(data.deciles)):
            for si in range(len(data.scenarios)):
                c[model.lambda_index[(di, si)]] = (
                    model.weights[di] * values[di, si]
                )
    else:
        assert decile_index is not None
        di = decile_index
        for si in range(len(data.scenarios)):
            c[model.lambda_index[(di, si)]] = values[di, si]
    return c


def raw_objective_value(
    model: MatrixModel,
    z: np.ndarray,
    metric: str,
    decile_index: int | None,
    overall: bool,
) -> float:
    c = objective_vector(model, metric, decile_index, overall)
    return float(np.dot(c, z))


def epsilon_grid(cfg: dict[str, str]) -> list[float]:
    vals = [float(x) for x in cfg["epsilon_grid"].split(";")]
    expected = [
        0.000, 0.025, 0.050, 0.075, 0.100, 0.125, 0.150,
        0.175, 0.200, 0.225, 0.250, 0.275, 0.300,
    ]
    if len(vals) != len(expected) or any(
        abs(a - b) > 1e-15 for a, b in zip(vals, expected)
    ):
        raise RuntimeError(f"epsilon grid changed: {vals}")
    return vals


def minimum_relaxation(
    data: ModelData,
    scheme: str,
    eq_tol: float,
    ineq_tol: float,
):
    model = make_model(data, scheme, include_epsilon=True)
    c = np.zeros(model.nvars)
    assert model.epsilon_index is not None
    c[model.epsilon_index] = 1.0
    res = solve_lp(model, c)
    if not res.success:
        raise RuntimeError(
            f"minimum epsilon LP failed for {scheme}: {res.status} {res.message}"
        )
    eps = float(res.x[model.epsilon_index])
    diag = diagnostics(model, res.x, eps)
    assert_solution(diag, eq_tol, ineq_tol)

    nta_overall = float(np.dot(data.q, data.r))
    weighted_min_p = float(
        np.dot(model.weights, np.min(data.p, axis=1))
    )
    weighted_max_p = float(
        np.dot(model.weights, np.max(data.p, axis=1))
    )
    aggregate_lower_bound = max(0.0, weighted_min_p - nta_overall)

    row = {
        "spec_version": SPEC_VERSION,
        "weight_scheme": scheme,
        "epsilon_star": eps,
        "aggregate_discrepancy_lower_bound": aggregate_lower_bound,
        "weighted_raw_min_pseudo_positive_modeled_annual_income_tax_share": weighted_min_p,
        "weighted_raw_max_pseudo_positive_modeled_annual_income_tax_share": weighted_max_p,
        "nta_overall_positive_self_assessed_balance_rate": nta_overall,
        "solver_success": bool(res.success),
        "solver_status_code": int(res.status),
        "solver_message": str(res.message),
        **diag,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "solver_method": "highs-ds",
        "scientific_status": STATUS,
        "historical_v6_restricted_lp_reproduced":
            HISTORICAL_V6_REPRODUCED,
    }

    lam, x = unpack_solution(model, res.x)
    pseudo = np.sum(lam * data.p, axis=1)
    transported = (x @ data.r) / model.weights
    decile_rows = []
    for di, d in enumerate(data.deciles):
        gap = float(pseudo[di] - transported[di])
        scenario_support = ";".join(
            data.scenarios[si]
            for si in range(len(data.scenarios))
            if lam[di, si] > 1e-10
        )
        category_support = ";".join(
            data.categories[ki]
            for ki in range(len(data.categories))
            if x[di, ki] > 1e-10
        )
        decile_rows.append({
            "spec_version": SPEC_VERSION,
            "weight_scheme": scheme,
            "decile": d,
            "decile_weight": model.weights[di],
            "epsilon_star": eps,
            "pseudo_positive_modeled_annual_income_tax_share_at_one_optimum": pseudo[di],
            "transported_nta_stage2_rate_at_one_optimum": transported[di],
            "signed_gap_pseudo_minus_transport": gap,
            "absolute_gap": abs(gap),
            "binding_within_1e8": abs(abs(gap) - eps) <= 1e-8,
            "scenario_support_at_one_optimum": scenario_support,
            "nta_category_support_at_one_optimum": category_support,
            "solution_note":
                "one optimal minimum-epsilon solution; allocation need not be unique",
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "solver_method": "highs-ds",
            "scientific_status": STATUS,
            "historical_v6_restricted_lp_reproduced":
                HISTORICAL_V6_REPRODUCED,
        })
    return row, decile_rows


def solve_fixed_feasibility(
    data: ModelData,
    scheme: str,
    epsilon: float,
    eq_tol: float,
    ineq_tol: float,
):
    model = make_model(data, scheme, include_epsilon=False)
    c = np.zeros(model.nvars)
    res = solve_lp(model, c, epsilon=epsilon)
    if not res.success:
        return model, res, None
    diag = diagnostics(model, res.x, epsilon)
    assert_solution(diag, eq_tol, ineq_tol)
    return model, res, diag


def endpoint_rows_at(
    data: ModelData,
    scheme: str,
    epsilon: float,
    epsilon_source: str,
    eq_tol: float,
    ineq_tol: float,
) -> list[dict]:
    model, feas, _ = solve_fixed_feasibility(
        data, scheme, epsilon, eq_tol, ineq_tol
    )
    if not feas.success:
        return []

    rows = []
    objectives = []
    for di, d in enumerate(data.deciles):
        for metric in METRICS:
            objectives.append(("decile", d, di, metric, False))
    for metric in OVERALL_METRICS:
        objectives.append(("overall", "", None, metric, True))

    for scope, d_label, di, metric, overall in objectives:
        c = objective_vector(model, metric, di, overall)
        for bound, sign in (("min", 1.0), ("max", -1.0)):
            res = solve_lp(model, sign * c, epsilon=epsilon)
            if not res.success:
                raise RuntimeError(
                    f"endpoint solve failed: {scheme} eps={epsilon} "
                    f"{scope} {d_label} {metric} {bound}: "
                    f"{res.status} {res.message}"
                )
            diag = diagnostics(model, res.x, epsilon)
            assert_solution(diag, eq_tol, ineq_tol)
            value = raw_objective_value(
                model, res.x, metric, di, overall
            )
            solver_obj = float(sign * res.fun)
            if abs(value - solver_obj) > 1e-9:
                raise RuntimeError(
                    f"objective recomputation mismatch: {value} vs {solver_obj}"
                )
            rows.append({
                "spec_version": SPEC_VERSION,
                "weight_scheme": scheme,
                "epsilon_source": epsilon_source,
                "epsilon": epsilon,
                "scope": scope,
                "decile": d_label,
                "metric": metric,
                "bound": bound,
                "endpoint_value": value,
                "solver_status_code": int(res.status),
                "solver_message": str(res.message),
                **diag,
                "numpy_version": np.__version__,
                "scipy_version": scipy.__version__,
                "solver_method": "highs-ds",
                "scientific_status": STATUS,
                "historical_v6_restricted_lp_reproduced":
                    HISTORICAL_V6_REPRODUCED,
            })
    return rows


def build_outputs():
    cfg = read_config()
    eq_tol = float(cfg["equality_residual_tolerance"])
    ineq_tol = float(cfg["inequality_residual_tolerance"])
    data = load_model_data(cfg)

    weight_rows = []
    for scheme, weights in data.weight_schemes.items():
        for di, d in enumerate(data.deciles):
            weight_rows.append({
                "spec_version": SPEC_VERSION,
                "weight_scheme": scheme,
                "decile": d,
                "decile_weight": weights[di],
                "source_definition": (
                    "fixed 0.1 per decile"
                    if scheme == "equal_decile"
                    else "normalized sum of F71561 14-leaf approximate household counts"
                ),
                "scientific_status": STATUS,
            })

    minimum_rows = []
    minimum_decile_rows = []
    eps_star = {}
    for scheme in data.weight_schemes:
        row, decile_rows = minimum_relaxation(
            data, scheme, eq_tol, ineq_tol
        )
        minimum_rows.append(row)
        minimum_decile_rows.extend(decile_rows)
        eps_star[scheme] = float(row["epsilon_star"])

    feasibility_rows = []
    endpoint_rows = []
    grid = epsilon_grid(cfg)

    for scheme in data.weight_schemes:
        # Pre-specified fixed grid.
        for eps in grid:
            model, res, diag = solve_fixed_feasibility(
                data, scheme, eps, eq_tol, ineq_tol
            )
            row = {
                "spec_version": SPEC_VERSION,
                "weight_scheme": scheme,
                "epsilon_source": "pre_specified_grid",
                "epsilon": eps,
                "feasible": bool(res.success),
                "solver_status_code": int(res.status),
                "solver_message": str(res.message),
                "max_scenario_sum_residual":
                    None if diag is None else diag["max_scenario_sum_residual"],
                "max_decile_mass_residual":
                    None if diag is None else diag["max_decile_mass_residual"],
                "max_category_mass_residual":
                    None if diag is None else diag["max_category_mass_residual"],
                "max_transport_gap":
                    None if diag is None else diag["max_transport_gap"],
                "max_transport_inequality_excess":
                    None if diag is None else diag[
                        "max_transport_inequality_excess"
                    ],
                "minimum_decision_variable":
                    None if diag is None else diag["minimum_decision_variable"],
                "numpy_version": np.__version__,
                "scipy_version": scipy.__version__,
                "solver_method": "highs-ds",
                "scientific_status": STATUS,
                "historical_v6_restricted_lp_reproduced":
                    HISTORICAL_V6_REPRODUCED,
            }
            feasibility_rows.append(row)
            if res.success:
                endpoint_rows.extend(
                    endpoint_rows_at(
                        data, scheme, eps, "pre_specified_grid",
                        eq_tol, ineq_tol
                    )
                )

        # Exact minimum-relaxation endpoint (separate from grid).
        eps = eps_star[scheme]
        model, res, diag = solve_fixed_feasibility(
            data, scheme, eps, eq_tol, ineq_tol
        )
        if not res.success:
            # HiGHS may need a numerical nudge exactly at the optimum. The
            # requested epsilon remains eps_star; only a sub-tolerance nudge is
            # allowed, and post-solve diagnostics still enforce 1e-8.
            eps_nudged = eps + min(1e-10, ineq_tol / 10)
            model, res, diag = solve_fixed_feasibility(
                data, scheme, eps_nudged, eq_tol, ineq_tol
            )
            if not res.success:
                raise RuntimeError(
                    f"fixed epsilon_star infeasible for {scheme}: "
                    f"{eps} / nudged={eps_nudged}"
                )
            eps_for_endpoint = eps_nudged
        else:
            eps_for_endpoint = eps

        feasibility_rows.append({
            "spec_version": SPEC_VERSION,
            "weight_scheme": scheme,
            "epsilon_source": "epsilon_star",
            "epsilon": eps,
            "feasible": True,
            "solver_status_code": int(res.status),
            "solver_message": str(res.message),
            "max_scenario_sum_residual": diag["max_scenario_sum_residual"],
            "max_decile_mass_residual": diag["max_decile_mass_residual"],
            "max_category_mass_residual": diag["max_category_mass_residual"],
            "max_transport_gap": diag["max_transport_gap"],
            "max_transport_inequality_excess":
                max(0.0, diag["max_transport_gap"] - eps),
            "minimum_decision_variable": diag["minimum_decision_variable"],
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "solver_method": "highs-ds",
            "scientific_status": STATUS,
            "historical_v6_restricted_lp_reproduced":
                HISTORICAL_V6_REPRODUCED,
        })
        endpoint_rows.extend(
            endpoint_rows_at(
                data, scheme, eps_for_endpoint, "epsilon_star",
                eq_tol, ineq_tol
            )
        )
        # Rewrite the recorded epsilon to the exact pre-specified optimum if a
        # sub-tolerance numerical nudge was needed.
        for row in endpoint_rows:
            if (
                row["weight_scheme"] == scheme
                and row["epsilon_source"] == "epsilon_star"
            ):
                row["epsilon"] = eps

    return [
        (OUT_WEIGHTS, weight_rows),
        (OUT_MIN, minimum_rows),
        (OUT_MIN_DECILE, minimum_decile_rows),
        (OUT_FEAS, feasibility_rows),
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
                "ERROR: stale replacement transport-LP outputs: "
                + ", ".join(stale)
            )
            sys.exit(1)
        print(
            "replacement transport-relaxation LP: current "
            "(2 weight schemes; pre-specified epsilon frontier)"
        )
        return

    for path, rows in outputs:
        path.write_text(render(rows), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")

    for path, rows in outputs:
        if path == OUT_MIN:
            print("\nMinimum relaxation:")
            for row in rows:
                print(
                    row["weight_scheme"],
                    "epsilon_star=",
                    fmt(row["epsilon_star"]),
                    "aggregate_lower_bound=",
                    fmt(row["aggregate_discrepancy_lower_bound"]),
                )


if __name__ == "__main__":
    main()
