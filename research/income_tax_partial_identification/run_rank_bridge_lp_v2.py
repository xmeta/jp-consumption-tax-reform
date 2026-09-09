#!/usr/bin/env python3
"""Pre-specified rank-bridge transport-relaxation LP v2.

This implementation follows the specification committed before any v2
endpoint computation:
  rank_bridge_lp_v2_spec.adoc
  rank_bridge_lp_v2_config.csv

Scientific status:
  MODEL_CONTINGENT_RANK_BRIDGE_RELAXATION

This is not a restoration of the historical V6 restricted LP and does not
modify the committed v1 result.
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

CONFIG = HERE / "rank_bridge_lp_v2_config.csv"
PSEUDO = ROOT / "research/income_tax_pseudofiler/pseudofiler_mtr_scenarios.csv"
NTA = ROOT / "data/derived/nta_income_class_primary_type_filing_status_2024.csv"

OUT_INPUTS = HERE / "rank_bridge_lp_v2_class_inputs.csv"
OUT_OVERLAP = HERE / "rank_bridge_lp_v2_class_rank_overlap.csv"
OUT_MIN = HERE / "rank_bridge_lp_v2_minimum_relaxation.csv"
OUT_MIN_DECILE = HERE / "rank_bridge_lp_v2_minimum_decile_diagnostics.csv"
OUT_FEAS = HERE / "rank_bridge_lp_v2_feasibility.csv"
OUT_END = HERE / "rank_bridge_lp_v2_endpoints.csv"

SPEC_VERSION = "rank_bridge_lp_v2"
STATUS = "MODEL_CONTINGENT_RANK_BRIDGE_RELAXATION"
HISTORICAL_V6_REPRODUCED = False
P1C13_V1_MODIFIED = False

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

DECILE_METRICS = (
    "taxable_income_weighted_mean_MTR",
    "income_tax_liability_weighted_mean_MTR",
    "pseudo_positive_modeled_annual_income_tax_share",
    "nta_rank_positive_self_assessed_balance_rate",
)
OVERALL_METRICS = (
    "taxable_income_weighted_mean_MTR",
    "income_tax_liability_weighted_mean_MTR",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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


def read_config() -> dict[str, str]:
    rows = read_csv(CONFIG)
    cfg = {r["key"]: r["value"] for r in rows}
    required = {
        "spec_version": SPEC_VERSION,
        "input_pseudofiler_scenarios": "all_13_committed_pseudofiler_scenarios",
        "input_nta_artifact": "nta_income_class_primary_type_filing_status_2024.csv",
        "nta_income_class_count": "25",
        "bridge_scheme": "same_rank_decile",
        "rank_bin_mass": "0.1",
        "within_class_positive_allocation": "free_within_overlap_capacity",
        "overall_weight_scheme": "equal_decile",
        "solver": "scipy.optimize.linprog",
        "solver_method": "highs-ds",
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "historical_v6_restricted_lp_reproduced": "false",
        "paper1_claim_before_ci": "false",
    }
    for key, expected in required.items():
        if cfg.get(key) != expected:
            raise RuntimeError(
                f"pre-specification mismatch: {key}={cfg.get(key)!r}, "
                f"expected {expected!r}"
            )
    return cfg


@dataclass(frozen=True)
class Data:
    deciles: tuple[int, ...]
    scenarios: tuple[str, ...]
    class_index: tuple[int, ...]
    class_label: tuple[str, ...]
    class_population: np.ndarray
    class_positive: np.ndarray
    total_population: float
    class_mass: np.ndarray
    class_positive_mass: np.ndarray
    overlap: np.ndarray       # J x D population mass, normalized to total N
    u: np.ndarray             # D x S pseudo positive-tax share
    m_taxable: np.ndarray
    m_liability: np.ndarray


@dataclass
class Model:
    data: Data
    include_epsilon: bool
    lambda_index: dict[tuple[int, int], int]
    y_index: dict[tuple[int, int], int]
    epsilon_index: int | None
    nvars: int
    A_eq: np.ndarray
    b_eq: np.ndarray
    bounds: list[tuple[float | None, float | None]]


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


def load_pseudo() -> tuple[
    tuple[int, ...], tuple[str, ...], np.ndarray, np.ndarray, np.ndarray
]:
    rows = read_csv(PSEUDO)
    by: dict[int, dict[str, dict[str, str]]] = {}
    for r in rows:
        by.setdefault(int(r["decile"]), {})[r["scenario"]] = r

    deciles = tuple(sorted(by))
    if deciles != tuple(range(1, 11)):
        raise RuntimeError(f"decile set changed: {deciles}")

    got_scenarios = {r["scenario"] for r in rows}
    if got_scenarios != set(EXPECTED_SCENARIOS):
        raise RuntimeError(
            f"scenario set changed: got={sorted(got_scenarios)}"
        )

    D = len(deciles)
    S = len(EXPECTED_SCENARIOS)
    u = np.empty((D, S))
    mt = np.empty((D, S))
    ml = np.empty((D, S))

    for di, d in enumerate(deciles):
        if set(by[d]) != set(EXPECTED_SCENARIOS):
            raise RuntimeError(f"decile {d}: incomplete scenario set")
        for si, s in enumerate(EXPECTED_SCENARIOS):
            r = by[d][s]
            u[di, si] = f(r["pseudo_positive_modeled_annual_income_tax_share"])
            mt[di, si] = f(r["taxable_income_weighted_mean_MTR"])
            ml[di, si] = f(r["income_tax_liability_weighted_mean_MTR"])

    return deciles, EXPECTED_SCENARIOS, u, mt, ml


def load_nta_classes() -> tuple[
    tuple[int, ...], tuple[str, ...], np.ndarray, np.ndarray
]:
    rows = read_csv(NTA)
    by_class: dict[int, list[dict[str, str]]] = {}
    for r in rows:
        by_class.setdefault(int(r["income_class_index"]), []).append(r)

    indices = tuple(sorted(by_class))
    if indices != tuple(range(1, 26)):
        raise RuntimeError(f"NTA income-class set changed: {indices}")

    labels = []
    populations = []
    positives = []

    for j in indices:
        q = by_class[j]
        if len(q) != 5:
            raise RuntimeError(f"class {j}: expected 5 primary types")

        labels_set = {r["income_class_label"] for r in q}
        if len(labels_set) != 1:
            raise RuntimeError(f"class {j}: inconsistent labels")
        labels.append(next(iter(labels_set)))

        pop = sum(int(r["table22_population_persons"]) for r in q)
        pos = sum(int(r["positive_self_assessed_balance_persons"]) for r in q)

        repeated_pop = {
            int(r["income_class_all_categories_table22_population_persons"])
            for r in q
        }
        repeated_pos = {
            int(r["income_class_all_categories_positive_self_assessed_balance_persons"])
            for r in q
        }
        if repeated_pop != {pop}:
            raise RuntimeError(
                f"class {j}: population repeated total mismatch"
            )
        if repeated_pos != {pos}:
            raise RuntimeError(
                f"class {j}: positive repeated total mismatch"
            )
        if not (0 <= pos <= pop):
            raise RuntimeError(f"class {j}: invalid positive/pop counts")

        populations.append(pop)
        positives.append(pos)

    A = np.array(populations, dtype=float)
    P = np.array(positives, dtype=float)
    if int(A.sum()) != 23_362_184:
        raise RuntimeError(f"unexpected Table2-2 population total {A.sum()}")
    if int(P.sum()) != 5_158_260:
        raise RuntimeError(f"unexpected positive total {P.sum()}")

    return indices, tuple(labels), A, P


def build_overlap(class_mass: np.ndarray) -> np.ndarray:
    """Ordered grouped-data overlap with ten equal rank bins."""
    J = len(class_mass)
    D = 10
    overlap = np.zeros((J, D), dtype=float)

    cum_hi = np.cumsum(class_mass)
    cum_lo = np.concatenate(([0.0], cum_hi[:-1]))

    for j in range(J):
        for di in range(D):
            d_lo = di / 10.0
            d_hi = (di + 1) / 10.0
            overlap[j, di] = max(
                0.0,
                min(float(cum_hi[j]), d_hi)
                - max(float(cum_lo[j]), d_lo),
            )

    # Grouped rank decomposition must preserve both margins.
    if np.max(np.abs(overlap.sum(axis=1) - class_mass)) > 1e-12:
        raise RuntimeError("class-rank overlap fails class-mass reconciliation")
    if np.max(np.abs(overlap.sum(axis=0) - 0.1)) > 1e-12:
        raise RuntimeError("class-rank overlap fails 0.1 rank-bin mass")

    return overlap


def load_data(cfg: dict[str, str]) -> Data:
    deciles, scenarios, u, mt, ml = load_pseudo()
    idx, labels, A, P = load_nta_classes()

    N = float(A.sum())
    a = A / N
    p = P / N
    overlap = build_overlap(a)

    if len(idx) != int(cfg["nta_income_class_count"]):
        raise RuntimeError("NTA income-class count changed")
    if abs(float(cfg["rank_bin_mass"]) - 0.1) > 1e-15:
        raise RuntimeError("rank bin mass changed")

    return Data(
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


def make_model(data: Data, include_epsilon: bool) -> Model:
    D = len(data.deciles)
    S = len(data.scenarios)
    J = len(data.class_index)

    lam_idx = {}
    n = 0
    for di in range(D):
        for si in range(S):
            lam_idx[(di, si)] = n
            n += 1

    y_idx = {}
    for ji in range(J):
        for di in range(D):
            y_idx[(ji, di)] = n
            n += 1

    eps_idx = n if include_epsilon else None
    if include_epsilon:
        n += 1

    eq_rows = []
    eq_rhs = []

    # Pseudo-filer convex scenario mixture per F71561 decile.
    for di in range(D):
        a = np.zeros(n)
        for si in range(S):
            a[lam_idx[(di, si)]] = 1.0
        eq_rows.append(a)
        eq_rhs.append(1.0)

    # Positive self-assessed balance mass conservation within each NTA income class.
    for ji in range(J):
        a = np.zeros(n)
        for di in range(D):
            a[y_idx[(ji, di)]] = 1.0
        eq_rows.append(a)
        eq_rhs.append(data.class_positive_mass[ji])

    bounds: list[tuple[float | None, float | None]] = [(0.0, None)] * n

    # Positive mass can only live in the class x rank-decile population overlap.
    for ji in range(J):
        for di in range(D):
            bounds[y_idx[(ji, di)]] = (
                0.0,
                float(data.overlap[ji, di]),
            )

    if include_epsilon:
        assert eps_idx is not None
        bounds[eps_idx] = (0.0, 1.0)

    return Model(
        data=data,
        include_epsilon=include_epsilon,
        lambda_index=lam_idx,
        y_index=y_idx,
        epsilon_index=eps_idx,
        nvars=n,
        A_eq=np.vstack(eq_rows),
        b_eq=np.array(eq_rhs),
        bounds=bounds,
    )


def bridge_inequalities(
    model: Model,
    epsilon: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    data = model.data
    D = len(data.deciles)
    S = len(data.scenarios)
    J = len(data.class_index)

    rows = []
    rhs = []

    for di in range(D):
        # pseudo - NTA <= epsilon
        a = np.zeros(model.nvars)
        for si in range(S):
            a[model.lambda_index[(di, si)]] = data.u[di, si]
        for ji in range(J):
            a[model.y_index[(ji, di)]] = -10.0

        if model.include_epsilon:
            assert model.epsilon_index is not None
            a[model.epsilon_index] = -1.0
            b = 0.0
        else:
            assert epsilon is not None
            b = epsilon

        rows.append(a)
        rhs.append(b)

        # NTA - pseudo <= epsilon
        bvec = -a
        if model.include_epsilon:
            assert model.epsilon_index is not None
            bvec[model.epsilon_index] = -1.0
        rows.append(bvec)
        rhs.append(b)

    return np.vstack(rows), np.array(rhs)


def solve_lp(model: Model, c: np.ndarray, epsilon: float | None = None):
    A_ub, b_ub = bridge_inequalities(model, epsilon)
    return linprog(
        c,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=model.A_eq,
        b_eq=model.b_eq,
        bounds=model.bounds,
        method="highs-ds",
        options={
            "presolve": True,
            "dual_feasibility_tolerance": 1e-9,
            "primal_feasibility_tolerance": 1e-9,
        },
    )


def unpack(model: Model, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    data = model.data
    D = len(data.deciles)
    S = len(data.scenarios)
    J = len(data.class_index)

    lam = np.zeros((D, S))
    y = np.zeros((J, D))

    for di in range(D):
        for si in range(S):
            lam[di, si] = z[model.lambda_index[(di, si)]]
    for ji in range(J):
        for di in range(D):
            y[ji, di] = z[model.y_index[(ji, di)]]

    return lam, y


def diagnostics(
    model: Model,
    z: np.ndarray,
    epsilon_requested: float,
) -> dict[str, float]:
    data = model.data
    lam, y = unpack(model, z)

    scenario_res = float(np.max(np.abs(lam.sum(axis=1) - 1.0)))
    class_positive_res = float(
        np.max(np.abs(y.sum(axis=1) - data.class_positive_mass))
    )
    capacity_excess = float(np.max(np.maximum(0.0, y - data.overlap)))
    min_variable = float(min(np.min(lam), np.min(y)))

    pseudo = np.sum(lam * data.u, axis=1)
    nta = 10.0 * y.sum(axis=0)
    gaps = np.abs(pseudo - nta)
    max_gap = float(np.max(gaps))
    inequality_excess = max(0.0, max_gap - epsilon_requested)

    return {
        "max_scenario_sum_residual": scenario_res,
        "max_class_positive_mass_residual": class_positive_res,
        "max_overlap_capacity_excess": capacity_excess,
        "max_rank_bridge_gap": max_gap,
        "max_rank_bridge_inequality_excess": inequality_excess,
        "minimum_decision_variable": min_variable,
    }


def assert_solution(
    diag: dict[str, float],
    eq_tol: float,
    ineq_tol: float,
) -> None:
    if diag["max_scenario_sum_residual"] > eq_tol:
        raise RuntimeError("scenario mixture residual exceeds tolerance")
    if diag["max_class_positive_mass_residual"] > eq_tol:
        raise RuntimeError("class positive-mass residual exceeds tolerance")
    if diag["max_overlap_capacity_excess"] > ineq_tol:
        raise RuntimeError("class-rank overlap capacity exceeded")
    if diag["max_rank_bridge_inequality_excess"] > ineq_tol:
        raise RuntimeError("rank-bridge inequality exceeded")
    if diag["minimum_decision_variable"] < -eq_tol:
        raise RuntimeError("negative decision variable")


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
    elif metric == "pseudo_positive_modeled_annual_income_tax_share":
        values = data.u
    elif metric == "nta_rank_positive_self_assessed_balance_rate":
        if overall:
            raise ValueError("overall NTA-rank rate endpoint not pre-specified")
        assert decile_index is not None
        for ji in range(len(data.class_index)):
            c[model.y_index[(ji, decile_index)]] = 10.0
        return c
    else:
        raise ValueError(metric)

    if overall:
        if metric not in OVERALL_METRICS:
            raise ValueError(metric)
        for di in range(len(data.deciles)):
            for si in range(len(data.scenarios)):
                c[model.lambda_index[(di, si)]] = (
                    0.1 * values[di, si]
                )
    else:
        assert decile_index is not None
        for si in range(len(data.scenarios)):
            c[model.lambda_index[(decile_index, si)]] = (
                values[decile_index, si]
            )

    return c


def solve_minimum(data: Data, eq_tol: float, ineq_tol: float):
    model = make_model(data, include_epsilon=True)
    c = np.zeros(model.nvars)
    assert model.epsilon_index is not None
    c[model.epsilon_index] = 1.0
    res = solve_lp(model, c)
    if not res.success:
        raise RuntimeError(
            f"v2 minimum epsilon failed: {res.status} {res.message}"
        )

    eps = float(res.x[model.epsilon_index])
    diag = diagnostics(model, res.x, eps)
    assert_solution(diag, eq_tol, ineq_tol)
    lam, y = unpack(model, res.x)

    pseudo = np.sum(lam * data.u, axis=1)
    nta = 10.0 * y.sum(axis=0)

    row = {
        "spec_version": SPEC_VERSION,
        "bridge_scheme": "same_rank_decile",
        "epsilon_star": eps,
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
        "p1c13_v1_modified": P1C13_V1_MODIFIED,
    }

    decile_rows = []
    for di, d in enumerate(data.deciles):
        gap = float(pseudo[di] - nta[di])
        scenario_support = ";".join(
            data.scenarios[si]
            for si in range(len(data.scenarios))
            if lam[di, si] > 1e-10
        )
        positive_class_support = ";".join(
            str(data.class_index[ji])
            for ji in range(len(data.class_index))
            if y[ji, di] > 1e-12
        )
        decile_rows.append({
            "spec_version": SPEC_VERSION,
            "decile": d,
            "epsilon_star": eps,
            "pseudo_positive_modeled_annual_income_tax_share_at_one_optimum": pseudo[di],
            "nta_rank_positive_self_assessed_balance_rate_at_one_optimum": nta[di],
            "signed_gap_pseudo_minus_nta": gap,
            "absolute_gap": abs(gap),
            "binding_within_1e8": abs(abs(gap) - eps) <= 1e-8,
            "scenario_support_at_one_optimum": scenario_support,
            "nta_positive_class_support_at_one_optimum":
                positive_class_support,
            "solution_note":
                "one optimal minimum-epsilon solution; within-class positive allocation and scenario mixture need not be unique",
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "solver_method": "highs-ds",
            "scientific_status": STATUS,
            "historical_v6_restricted_lp_reproduced":
                HISTORICAL_V6_REPRODUCED,
            "p1c13_v1_modified": P1C13_V1_MODIFIED,
        })

    return row, decile_rows


def fixed_feasibility(
    data: Data,
    epsilon: float,
    eq_tol: float,
    ineq_tol: float,
):
    model = make_model(data, include_epsilon=False)
    c = np.zeros(model.nvars)
    res = solve_lp(model, c, epsilon)
    if not res.success:
        return model, res, None
    diag = diagnostics(model, res.x, epsilon)
    assert_solution(diag, eq_tol, ineq_tol)
    return model, res, diag


def endpoint_rows_at(
    data: Data,
    epsilon: float,
    epsilon_source: str,
    eq_tol: float,
    ineq_tol: float,
) -> list[dict]:
    model, feas, _ = fixed_feasibility(data, epsilon, eq_tol, ineq_tol)
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
            res = solve_lp(model, sign * c, epsilon)
            if not res.success:
                raise RuntimeError(
                    f"v2 endpoint failed eps={epsilon} "
                    f"{scope} {d_label} {metric} {bound_name}: "
                    f"{res.status} {res.message}"
                )

            diag = diagnostics(model, res.x, epsilon)
            assert_solution(diag, eq_tol, ineq_tol)

            raw_value = float(np.dot(c, res.x))
            solver_value = float(sign * res.fun)
            if abs(raw_value - solver_value) > 1e-9:
                raise RuntimeError(
                    f"objective recomputation mismatch: "
                    f"{raw_value} vs {solver_value}"
                )

            rows.append({
                "spec_version": SPEC_VERSION,
                "bridge_scheme": "same_rank_decile",
                "epsilon_source": epsilon_source,
                "epsilon": epsilon,
                "scope": scope,
                "decile": d_label,
                "metric": metric,
                "bound": bound_name,
                "endpoint_value": raw_value,
                "solver_status_code": int(res.status),
                "solver_message": str(res.message),
                **diag,
                "numpy_version": np.__version__,
                "scipy_version": scipy.__version__,
                "solver_method": "highs-ds",
                "scientific_status": STATUS,
                "historical_v6_restricted_lp_reproduced":
                    HISTORICAL_V6_REPRODUCED,
                "p1c13_v1_modified": P1C13_V1_MODIFIED,
            })

    return rows


def build_static_rows(data: Data):
    inputs = []
    for ji, j in enumerate(data.class_index):
        inputs.append({
            "spec_version": SPEC_VERSION,
            "income_class_index": j,
            "income_class_label": data.class_label[ji],
            "table22_population_persons": int(data.class_population[ji]),
            "positive_self_assessed_balance_persons": int(data.class_positive[ji]),
            "population_mass": data.class_mass[ji],
            "positive_self_assessed_balance_mass": data.class_positive_mass[ji],
            "within_class_positive_self_assessed_balance_rate":
                data.class_positive[ji] / data.class_population[ji],
            "source_artifact":
                "data/derived/nta_income_class_primary_type_filing_status_2024.csv",
            "scientific_status": STATUS,
        })

    overlap = []
    cum = np.cumsum(data.class_mass)
    lows = np.concatenate(([0.0], cum[:-1]))
    for ji, j in enumerate(data.class_index):
        for di, d in enumerate(data.deciles):
            h = data.overlap[ji, di]
            overlap.append({
                "spec_version": SPEC_VERSION,
                "income_class_index": j,
                "income_class_label": data.class_label[ji],
                "class_rank_lower": lows[ji],
                "class_rank_upper": cum[ji],
                "nta_rank_decile": d,
                "rank_decile_lower": (d - 1) / 10.0,
                "rank_decile_upper": d / 10.0,
                "population_overlap_mass": h,
                "positive_mass_upper_capacity": h,
                "overlap_positive": h > 0,
                "scientific_status": STATUS,
            })

    return inputs, overlap


def build_outputs():
    cfg = read_config()
    eq_tol = float(cfg["equality_residual_tolerance"])
    ineq_tol = float(cfg["inequality_residual_tolerance"])
    data = load_data(cfg)

    input_rows, overlap_rows = build_static_rows(data)
    min_row, min_decile_rows = solve_minimum(data, eq_tol, ineq_tol)
    eps_star = float(min_row["epsilon_star"])

    feasibility_rows = []
    endpoint_rows = []

    for eps in epsilon_grid(cfg):
        model, res, diag = fixed_feasibility(data, eps, eq_tol, ineq_tol)
        feasibility_rows.append({
            "spec_version": SPEC_VERSION,
            "bridge_scheme": "same_rank_decile",
            "epsilon_source": "pre_specified_grid",
            "epsilon": eps,
            "feasible": bool(res.success),
            "solver_status_code": int(res.status),
            "solver_message": str(res.message),
            "max_scenario_sum_residual":
                None if diag is None else diag["max_scenario_sum_residual"],
            "max_class_positive_mass_residual":
                None if diag is None else diag[
                    "max_class_positive_mass_residual"
                ],
            "max_overlap_capacity_excess":
                None if diag is None else diag["max_overlap_capacity_excess"],
            "max_rank_bridge_gap":
                None if diag is None else diag["max_rank_bridge_gap"],
            "max_rank_bridge_inequality_excess":
                None if diag is None else diag[
                    "max_rank_bridge_inequality_excess"
                ],
            "minimum_decision_variable":
                None if diag is None else diag["minimum_decision_variable"],
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "solver_method": "highs-ds",
            "scientific_status": STATUS,
            "historical_v6_restricted_lp_reproduced":
                HISTORICAL_V6_REPRODUCED,
            "p1c13_v1_modified": P1C13_V1_MODIFIED,
        })
        if res.success:
            endpoint_rows.extend(
                endpoint_rows_at(
                    data, eps, "pre_specified_grid", eq_tol, ineq_tol
                )
            )

    # Endpoints at exact epsilon-star.  Allow only a sub-tolerance numerical
    # nudge if HiGHS rejects exact optimum in the fixed-epsilon form.
    model, res, diag = fixed_feasibility(data, eps_star, eq_tol, ineq_tol)
    eps_for_endpoint = eps_star
    if not res.success:
        eps_for_endpoint = eps_star + min(1e-10, ineq_tol / 10)
        model, res, diag = fixed_feasibility(
            data, eps_for_endpoint, eq_tol, ineq_tol
        )
        if not res.success:
            raise RuntimeError(
                "v2 fixed epsilon-star infeasible even after sub-tolerance nudge"
            )

    assert diag is not None
    feasibility_rows.append({
        "spec_version": SPEC_VERSION,
        "bridge_scheme": "same_rank_decile",
        "epsilon_source": "epsilon_star",
        "epsilon": eps_star,
        "feasible": True,
        "solver_status_code": int(res.status),
        "solver_message": str(res.message),
        "max_scenario_sum_residual": diag["max_scenario_sum_residual"],
        "max_class_positive_mass_residual":
            diag["max_class_positive_mass_residual"],
        "max_overlap_capacity_excess": diag["max_overlap_capacity_excess"],
        "max_rank_bridge_gap": diag["max_rank_bridge_gap"],
        "max_rank_bridge_inequality_excess":
            max(0.0, diag["max_rank_bridge_gap"] - eps_star),
        "minimum_decision_variable": diag["minimum_decision_variable"],
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "solver_method": "highs-ds",
        "scientific_status": STATUS,
        "historical_v6_restricted_lp_reproduced":
            HISTORICAL_V6_REPRODUCED,
        "p1c13_v1_modified": P1C13_V1_MODIFIED,
    })

    star_rows = endpoint_rows_at(
        data, eps_for_endpoint, "epsilon_star", eq_tol, ineq_tol
    )
    for row in star_rows:
        row["epsilon"] = eps_star
    endpoint_rows.extend(star_rows)

    return [
        (OUT_INPUTS, input_rows),
        (OUT_OVERLAP, overlap_rows),
        (OUT_MIN, [min_row]),
        (OUT_MIN_DECILE, min_decile_rows),
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
                "ERROR: stale rank-bridge LP v2 outputs: "
                + ", ".join(stale)
            )
            sys.exit(1)
        print(
            "rank-bridge transport-relaxation LP v2: current "
            "(25 grouped income classes; same-rank bridge)"
        )
        return

    for path, rows in outputs:
        path.write_text(render(rows), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")

    min_row = dict(outputs[2][1][0])
    print(
        "\nv2 minimum relaxation:",
        "epsilon_star=",
        fmt(min_row["epsilon_star"]),
    )


if __name__ == "__main__":
    main()
