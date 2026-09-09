#!/usr/bin/env python3
"""Regression and invariant tests for pre-specified rank-bridge LP v2."""
from pathlib import Path
import csv
import hashlib
import importlib.util
import math
import subprocess
import sys

import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

RUN = HERE / "run_rank_bridge_lp_v2.py"
INPUTS = HERE / "rank_bridge_lp_v2_class_inputs.csv"
OVERLAP = HERE / "rank_bridge_lp_v2_class_rank_overlap.csv"
MINIMUM = HERE / "rank_bridge_lp_v2_minimum_relaxation.csv"
MIN_DECILE = HERE / "rank_bridge_lp_v2_minimum_decile_diagnostics.csv"
FEAS = HERE / "rank_bridge_lp_v2_feasibility.csv"
END = HERE / "rank_bridge_lp_v2_endpoints.csv"
PSEUDO = ROOT / "research/income_tax_pseudofiler/pseudofiler_mtr_scenarios.csv"

V1_MIN = HERE / "replacement_transport_lp_minimum_relaxation.csv"
V1_END = HERE / "replacement_transport_lp_endpoints.csv"

STATUS = "MODEL_CONTINGENT_RANK_BRIDGE_RELAXATION"
EPS_STAR = 0.149015979543
ANALYTIC_MARGINAL_LB = 0.13137080564529152
EQ_TOL = 1e-8
INEQ_TOL = 1e-8
GRID = [
    0.000, 0.025, 0.050, 0.075, 0.100, 0.125, 0.150,
    0.175, 0.200, 0.225, 0.250, 0.275, 0.300,
]
V1_MIN_SHA256 = "5158f4ccf0e82d2f8968b9d68003069f8e69fe5370887a103fddeaadc6271e4e"
V1_END_SHA256 = "497804702dc66474df7db41d5587f2d2fde36f4c663db4f4bafa1f37b32271a8"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def as_bool(x):
    assert x in {"True", "False"}
    return x == "True"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module():
    sp = importlib.util.spec_from_file_location("rankv2_test_module", RUN)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = mod
    sp.loader.exec_module(mod)
    return mod


inputs = read(INPUTS)
overlap = read(OVERLAP)
minimum = read(MINIMUM)
min_decile = read(MIN_DECILE)
feas = read(FEAS)
endpoints = read(END)

assert len(inputs) == 25
assert len(overlap) == 250
assert len(minimum) == 1
assert len(min_decile) == 10
assert len(feas) == 14
assert len(endpoints) == 672

# v2 must never mutate the committed post-semantic-migration v1 evidence.
# Numeric equality to the pre-migration evidence is checked separately by
# test_self_assessed_balance_schema_migration.py.
assert sha(V1_MIN) == V1_MIN_SHA256
assert sha(V1_END) == V1_END_SHA256

for collection in [inputs, overlap, minimum, min_decile, feas, endpoints]:
    for r in collection:
        assert r["scientific_status"] == STATUS

for collection in [minimum, min_decile, feas, endpoints]:
    for r in collection:
        assert r["historical_v6_restricted_lp_reproduced"] == "False"
        assert r["p1c13_v1_modified"] == "False"

# Input totals.
assert {int(r["income_class_index"]) for r in inputs} == set(range(1, 26))
N = sum(int(r["table22_population_persons"]) for r in inputs)
P = sum(int(r["positive_self_assessed_balance_persons"]) for r in inputs)
assert N == 23_362_184
assert P == 5_158_260
assert math.isclose(
    sum(float(r["population_mass"]) for r in inputs),
    1.0,
    abs_tol=5e-10,
)
assert math.isclose(
    sum(float(r["positive_self_assessed_balance_mass"]) for r in inputs),
    P / N,
    abs_tol=5e-10,
)

# Ordered grouped-rank overlap: preserve each class mass and each rank-decile
# mass exactly (within numerical output precision).
by_class = {}
by_decile = {}
for r in overlap:
    by_class.setdefault(int(r["income_class_index"]), []).append(r)
    by_decile.setdefault(int(r["nta_rank_decile"]), []).append(r)

input_by_class = {int(r["income_class_index"]): r for r in inputs}
for j, q in by_class.items():
    assert len(q) == 10
    assert math.isclose(
        sum(float(r["population_overlap_mass"]) for r in q),
        float(input_by_class[j]["population_mass"]),
        abs_tol=5e-10,
    )
    for r in q:
        h = float(r["population_overlap_mass"])
        assert 0 <= h <= float(input_by_class[j]["population_mass"]) + 1e-12
        assert float(r["positive_mass_upper_capacity"]) == h

for d, q in by_decile.items():
    assert len(q) == 25
    assert math.isclose(
        sum(float(r["population_overlap_mass"]) for r in q),
        0.1,
        abs_tol=5e-10,
    )

# Minimum relaxation.
rmin = minimum[0]
eps = float(rmin["epsilon_star"])
assert math.isclose(eps, EPS_STAR, abs_tol=5e-10)
assert as_bool(rmin["solver_success"])
assert int(rmin["solver_status_code"]) == 0
assert float(rmin["max_scenario_sum_residual"]) <= EQ_TOL
assert float(rmin["max_class_positive_mass_residual"]) <= EQ_TOL
assert float(rmin["max_overlap_capacity_excess"]) <= INEQ_TOL
assert float(rmin["max_rank_bridge_inequality_excess"]) <= INEQ_TOL
assert float(rmin["minimum_decision_variable"]) >= -EQ_TOL
assert math.isclose(
    float(rmin["max_rank_bridge_gap"]),
    eps,
    abs_tol=5e-10,
)

# One reported optimum is feasible; its allocation need not be unique.
assert {int(r["decile"]) for r in min_decile} == set(range(1, 11))
assert any(as_bool(r["binding_within_1e8"]) for r in min_decile)
for r in min_decile:
    p = float(r["pseudo_positive_modeled_annual_income_tax_share_at_one_optimum"])
    n = float(r["nta_rank_positive_self_assessed_balance_rate_at_one_optimum"])
    gap = float(r["signed_gap_pseudo_minus_nta"])
    assert 0 <= p <= 1
    assert 0 <= n <= 1
    assert math.isclose(gap, p - n, abs_tol=1e-10)
    assert abs(gap) <= eps + INEQ_TOL
    assert "need not be unique" in r["solution_note"]

# Pre-specified grid feasibility switches between 0.125 and 0.150.
grid_rows = [r for r in feas if r["epsilon_source"] == "pre_specified_grid"]
assert len(grid_rows) == len(GRID)
assert [float(r["epsilon"]) for r in grid_rows] == GRID
for r in grid_rows:
    e = float(r["epsilon"])
    feasible = as_bool(r["feasible"])
    assert feasible == (e >= 0.150 - 1e-12)
    if feasible:
        assert int(r["solver_status_code"]) == 0
        assert float(r["max_scenario_sum_residual"]) <= EQ_TOL
        assert float(r["max_class_positive_mass_residual"]) <= EQ_TOL
        assert float(r["max_overlap_capacity_excess"]) <= INEQ_TOL
        assert float(r["max_rank_bridge_inequality_excess"]) <= INEQ_TOL
    else:
        assert int(r["solver_status_code"]) == 2
        assert "infeasible" in r["solver_message"].lower()

star = [r for r in feas if r["epsilon_source"] == "epsilon_star"]
assert len(star) == 1 and as_bool(star[0]["feasible"])
assert math.isclose(float(star[0]["epsilon"]), EPS_STAR, abs_tol=5e-10)

# 8 feasible epsilon points: 7 fixed-grid points plus epsilon-star.
# Each point has 10 deciles x 4 metrics x 2 bounds + 2 overall metrics x 2.
groups = {}
for r in endpoints:
    key = (r["epsilon_source"], float(r["epsilon"]))
    groups.setdefault(key, []).append(r)
assert len(groups) == 8
assert all(len(q) == 84 for q in groups.values())

for key, rows in groups.items():
    pairs = {}
    for r in rows:
        obj = (r["scope"], r["decile"], r["metric"])
        pairs.setdefault(obj, {})[r["bound"]] = float(r["endpoint_value"])

        assert int(r["solver_status_code"]) == 0
        assert float(r["max_scenario_sum_residual"]) <= EQ_TOL
        assert float(r["max_class_positive_mass_residual"]) <= EQ_TOL
        assert float(r["max_overlap_capacity_excess"]) <= INEQ_TOL
        assert float(r["max_rank_bridge_inequality_excess"]) <= INEQ_TOL
        assert float(r["minimum_decision_variable"]) >= -EQ_TOL

        value = float(r["endpoint_value"])
        if "MTR" in r["metric"]:
            assert -1e-12 <= value <= 0.45 + 1e-12
        else:
            assert 0 <= value <= 1

    assert len(pairs) == 42
    for obj, vals in pairs.items():
        assert set(vals) == {"min", "max"}
        assert vals["min"] <= vals["max"] + 1e-10, (key, obj, vals)

# Feasible-set expansion with epsilon.
fixed = [r for r in endpoints if r["epsilon_source"] == "pre_specified_grid"]
objects = {(r["scope"], r["decile"], r["metric"]) for r in fixed}
for obj in objects:
    for bound in ("min", "max"):
        z = sorted(
            (float(r["epsilon"]), float(r["endpoint_value"]))
            for r in fixed
            if (r["scope"], r["decile"], r["metric"]) == obj
            and r["bound"] == bound
        )
        for (_, a), (_, b) in zip(z, z[1:]):
            if bound == "min":
                assert b <= a + 1e-9, (obj, z)
            else:
                assert b + 1e-9 >= a, (obj, z)

# Regression anchors for epsilon-star overall MTR envelopes.
expected_overall = {
    "taxable_income_weighted_mean_MTR":
        (0.103389290194, 0.119819722727),
    "income_tax_liability_weighted_mean_MTR":
        (0.111969128307, 0.129585234991),
}
star_end = [r for r in endpoints if r["epsilon_source"] == "epsilon_star"]
for metric, (lo, hi) in expected_overall.items():
    q = [
        r for r in star_end
        if r["scope"] == "overall" and r["metric"] == metric
    ]
    got = {r["bound"]: float(r["endpoint_value"]) for r in q}
    assert math.isclose(got["min"], lo, abs_tol=5e-10)
    assert math.isclose(got["max"], hi, abs_tol=5e-10)

# Analytical decile-by-decile grouped-data lower bound.  This deliberately
# ignores cross-decile coupling, so the joint LP optimum must weakly exceed it.
pseudo = read(PSEUDO)
p_by_d = {}
for r in pseudo:
    p_by_d.setdefault(int(r["decile"]), []).append(
        float(r["pseudo_positive_modeled_annual_income_tax_share"])
    )

analytic_lbs = []
for d in range(1, 11):
    nta_lo = 0.0
    nta_hi = 0.0
    for j in range(1, 26):
        inp = input_by_class[j]
        a = float(inp["population_mass"])
        p = float(inp["positive_self_assessed_balance_mass"])
        hrow = next(
            r for r in by_class[j] if int(r["nta_rank_decile"]) == d
        )
        h = float(hrow["population_overlap_mass"])
        nta_lo += max(0.0, p - (a - h))
        nta_hi += min(h, p)
    nta_lo *= 10.0
    nta_hi *= 10.0

    pf_lo = min(p_by_d[d])
    pf_hi = max(p_by_d[d])
    analytic_lbs.append(max(0.0, pf_lo - nta_hi, nta_lo - pf_hi))

assert math.isclose(
    max(analytic_lbs),
    ANALYTIC_MARGINAL_LB,
    abs_tol=5e-10,
)
assert EPS_STAR > ANALYTIC_MARGINAL_LB + 0.01

# Direct perturbation check around epsilon-star and a second HiGHS algorithm
# cross-check the optimum without changing the official output solver.
m = load_module()
cfg = m.read_config()
data = m.load_data(cfg)

model_low = m.make_model(data, include_epsilon=False)
res_low = m.solve_lp(
    model_low,
    np.zeros(model_low.nvars),
    EPS_STAR - 1e-8,
)
assert not res_low.success and res_low.status == 2

model_hi = m.make_model(data, include_epsilon=False)
res_hi = m.solve_lp(
    model_hi,
    np.zeros(model_hi.nvars),
    EPS_STAR + 1e-8,
)
assert res_hi.success

model = m.make_model(data, include_epsilon=True)
c = np.zeros(model.nvars)
c[model.epsilon_index] = 1.0
A_ub, b_ub = m.bridge_inequalities(model)
res_ipm = linprog(
    c,
    A_ub=A_ub,
    b_ub=b_ub,
    A_eq=model.A_eq,
    b_eq=model.b_eq,
    bounds=model.bounds,
    method="highs-ipm",
)
assert res_ipm.success
assert math.isclose(
    float(res_ipm.x[model.epsilon_index]),
    EPS_STAR,
    abs_tol=5e-9,
)

# Deterministic regeneration under the pinned official solver.
subprocess.run(
    [sys.executable, str(RUN), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "rank-bridge LP v2 tests: OK "
    "(epsilon*=0.149016; grouped-rank overlap; 14 feasibility rows; "
    "672 endpoints; analytical lower bound; solver cross-check)"
)
