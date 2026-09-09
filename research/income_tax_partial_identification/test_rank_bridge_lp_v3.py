#!/usr/bin/env python3
"""Regression and invariant tests for pre-specified rank-transport LP v3."""
from pathlib import Path
import csv
import importlib.util
import math
import subprocess
import sys

import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "run_rank_bridge_lp_v3.py"
FRONTIER = HERE / "rank_bridge_lp_v3_minimum_relaxation_frontier.csv"
DECILE = HERE / "rank_bridge_lp_v3_minimum_decile_diagnostics.csv"
ZERO = HERE / "rank_bridge_lp_v3_zero_discrepancy_threshold.csv"
ANALYTIC = HERE / "rank_bridge_lp_v3_analytical_rate_floor.csv"
PLANS = HERE / "rank_bridge_lp_v3_transport_plans.csv"
END = HERE / "rank_bridge_lp_v3_endpoints.csv"
V2_MIN = HERE / "rank_bridge_lp_v2_minimum_relaxation.csv"
V2_END = HERE / "rank_bridge_lp_v2_endpoints.csv"
PSEUDO = ROOT / "research/income_tax_pseudofiler/pseudofiler_mtr_scenarios.csv"
NTA = ROOT / "data/derived/nta_income_class_primary_type_filing_status_2024.csv"

STATUS = "MODEL_CONTINGENT_RANK_TRANSPORT_BUDGET"
DELTAS = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
V2_EPS = 0.149015979543
UNRESTRICTED_FLOOR = 0.0868252768522
EQ_TOL = 1e-8
INEQ_TOL = 1e-8


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def as_bool(x):
    assert x in {"True", "False"}
    return x == "True"


def load_module():
    sp = importlib.util.spec_from_file_location("rankv3_test_module", RUN)
    mod = importlib.util.module_from_spec(sp)
    sys.path.insert(0, str(HERE))
    sys.modules[sp.name] = mod
    sp.loader.exec_module(mod)
    return mod


frontier = read(FRONTIER)
decile = read(DECILE)
zero = read(ZERO)
analytic = read(ANALYTIC)
plans = read(PLANS)
endpoints = read(END)
v2_min = read(V2_MIN)
v2_end = read(V2_END)

assert len(frontier) == 8
assert len(decile) == 80
assert len(zero) == 1
assert len(analytic) == 1
assert len(plans) == 800
assert len(endpoints) == 672
assert len(v2_min) == 1

for collection in [frontier, decile, zero, analytic, plans, endpoints]:
    for r in collection:
        assert r["scientific_status"] == STATUS
        assert r["historical_v6_restricted_lp_reproduced"] == "False"
        assert r["p1c13_v1_modified"] == "False"
        assert r["p1c14_v2_modified"] == "False"

# The pre-specified frontier grid is exact and monotone.
assert [float(r["delta"]) for r in frontier] == DELTAS
eps = [float(r["epsilon_star"]) for r in frontier]
for a, b in zip(eps, eps[1:]):
    assert b <= a + 1e-10, eps

assert math.isclose(eps[0], V2_EPS, abs_tol=5e-10)
for e in eps[1:]:
    assert math.isclose(e, UNRESTRICTED_FLOOR, abs_tol=5e-10)

for r in frontier:
    assert as_bool(r["solver_success"])
    assert int(r["solver_status_code"]) == 0
    assert float(r["transport_cost"]) <= float(r["delta"]) + INEQ_TOL
    assert math.isclose(
        float(r["transport_cost"]),
        float(r["transport_cost_at_one_optimum"]),
        abs_tol=1e-10,
    )
    for key in (
        "max_scenario_sum_residual",
        "max_class_positive_mass_residual",
        "max_transport_row_margin_residual",
        "max_transport_column_margin_residual",
        "max_nta_rank_positive_margin_residual",
    ):
        assert float(r[key]) <= EQ_TOL, (r["delta"], key, r[key])
    for key in (
        "max_overlap_capacity_excess",
        "max_positive_transport_capacity_excess",
        "rank_displacement_budget_excess",
        "max_rank_bridge_inequality_excess",
    ):
        assert float(r[key]) <= INEQ_TOL, (r["delta"], key, r[key])
    assert float(r["minimum_decision_variable"]) >= -EQ_TOL

# Delta=0 is exactly the committed v2 minimum.
assert math.isclose(
    float(v2_min[0]["epsilon_star"]),
    eps[0],
    abs_tol=5e-10,
)

# One minimum-epsilon diagnostic per decile and delta.
by_delta_decile = {}
for r in decile:
    by_delta_decile.setdefault(float(r["delta"]), []).append(r)
assert set(by_delta_decile) == set(DELTAS)
for delta, rows in by_delta_decile.items():
    assert len(rows) == 10
    assert {int(r["decile"]) for r in rows} == set(range(1, 11))
    e = next(float(x["epsilon_star"]) for x in frontier if float(x["delta"]) == delta)
    assert any(as_bool(r["binding_within_1e8"]) for r in rows)
    for r in rows:
        p = float(r["pseudo_positive_tax_share_at_one_optimum"])
        n = float(r["transported_nta_positive_liability_rate_at_one_optimum"])
        gap = float(r["signed_gap_pseudo_minus_transported_nta"])
        assert 0 <= p <= 1
        assert 0 <= n <= 1
        assert math.isclose(gap, p - n, abs_tol=1e-10)
        assert abs(gap) <= e + INEQ_TOL
        assert "need not be unique" in r["solution_note"]

# Transport plan margins and cost at each frontier optimum.
by_plan = {}
for r in plans:
    assert r["solution_source"] == "epsilon_star_frontier"
    by_plan.setdefault(float(r["delta_budget"]), []).append(r)
assert set(by_plan) == set(DELTAS)
for delta, rows in by_plan.items():
    assert len(rows) == 100
    for d in range(1, 11):
        q = [r for r in rows if int(r["f_decile"]) == d]
        assert math.isclose(
            sum(float(r["population_transport_mass"]) for r in q),
            0.1,
            abs_tol=5e-10,
        )
    for qrank in range(1, 11):
        q = [r for r in rows if int(r["nta_rank_decile"]) == qrank]
        assert math.isclose(
            sum(float(r["population_transport_mass"]) for r in q),
            0.1,
            abs_tol=5e-10,
        )
    cost = sum(float(r["cost_contribution"]) for r in rows)
    frow = next(r for r in frontier if float(r["delta"]) == delta)
    assert math.isclose(cost, float(frow["transport_cost"]), abs_tol=5e-9)
    for r in rows:
        t = float(r["population_transport_mass"])
        z = float(r["positive_liability_transport_mass"])
        assert -1e-12 <= z <= t + 1e-10

# At delta=0 only the diagonal population coupling can be positive.
for r in by_plan[0.0]:
    d = int(r["f_decile"])
    q = int(r["nta_rank_decile"])
    t = float(r["population_transport_mass"])
    if d == q:
        assert math.isclose(t, 0.1, abs_tol=5e-10)
    else:
        assert abs(t) <= 5e-10

# Zero discrepancy is pre-specified and must be recorded as infeasible rather
# than silently changing the criterion.
z0 = zero[0]
assert not as_bool(z0["zero_discrepancy_feasible"])
assert z0["delta_zero_star"] == ""
assert int(z0["solver_status_code"]) == 2
assert "infeasible" in z0["solver_message"].lower()

# Analytical unrestricted common-epsilon floor.
# Let l_d be the minimum pseudo-positive rate in each decile. With unrestricted
# transport, the transported NTA row rates remain nonnegative and have fixed
# mean equal to the NTA aggregate positive-liability rate. Feasibility at
# common epsilon e requires sum_d max(0,l_d-e) <= 10*r_NTA. The smallest e is
# therefore a one-dimensional water-filling lower bound.
pseudo = read(PSEUDO)
by_d = {}
for r in pseudo:
    by_d.setdefault(int(r["decile"]), []).append(
        float(r["pseudo_filer_positive_tax_share"])
    )
lower = np.array([min(by_d[d]) for d in range(1, 11)])

nta = read(NTA)
N = sum(int(r["table22_population_persons"]) for r in nta)
P = sum(int(r["positive_liability_persons"]) for r in nta)
nta_rate = P / N

lo, hi = 0.0, 1.0
for _ in range(100):
    mid = (lo + hi) / 2
    if np.maximum(0.0, lower - mid).sum() <= 10.0 * nta_rate:
        hi = mid
    else:
        lo = mid
analytic_floor = hi
assert math.isclose(analytic_floor, UNRESTRICTED_FLOOR, abs_tol=5e-12)
assert math.isclose(eps[-1], analytic_floor, abs_tol=5e-10)

simple_average_floor = max(0.0, float(lower.mean() - nta_rate))
assert math.isclose(simple_average_floor, 0.0866905432846686, abs_tol=5e-12)
assert analytic_floor > simple_average_floor
assert lower[0] < analytic_floor  # explains the non-negativity correction

arow = analytic[0]
assert math.isclose(
    float(arow["nta_aggregate_positive_liability_rate"]),
    nta_rate,
    abs_tol=5e-12,
)
assert math.isclose(
    float(arow["pseudo_filer_lower_envelope_equal_decile_average"]),
    float(lower.mean()),
    abs_tol=5e-12,
)
assert math.isclose(
    float(arow["simple_average_gap_floor"]),
    simple_average_floor,
    abs_tol=5e-12,
)
assert math.isclose(
    float(arow["unrestricted_nonnegative_rate_floor"]),
    analytic_floor,
    abs_tol=5e-12,
)
assert arow["pseudo_lower_envelope_deciles_below_floor"] == "1"
assert "not a confidence bound" in arow["interpretation"]

# The equal-margin transport polytope has maximum average absolute decile
# distance exactly five (reverse-rank permutation).
D = 10
cost = np.array([abs(d-q) for d in range(D) for q in range(D)], dtype=float)
Aeq = []
beq = []
for d in range(D):
    row = np.zeros(D*D)
    for q in range(D):
        row[d*D+q] = 1
    Aeq.append(row)
    beq.append(0.1)
for q in range(D):
    row = np.zeros(D*D)
    for d in range(D):
        row[d*D+q] = 1
    Aeq.append(row)
    beq.append(0.1)
max_cost = linprog(
    -cost,
    A_eq=np.array(Aeq),
    b_eq=np.array(beq),
    bounds=[(0, None)]*(D*D),
    method="highs-ds",
)
assert max_cost.success
assert math.isclose(-float(max_cost.fun), 5.0, abs_tol=1e-10)

# Endpoint structure: 84 endpoints per each of 8 frontier points.
groups = {}
for r in endpoints:
    assert r["frontier_source"] == "epsilon_star_frontier"
    groups.setdefault(float(r["delta"]), []).append(r)
assert set(groups) == set(DELTAS)
assert all(len(rows) == 84 for rows in groups.values())

for delta, rows in groups.items():
    pairs = {}
    for r in rows:
        obj = (r["scope"], r["decile"], r["metric"])
        pairs.setdefault(obj, {})[r["bound"]] = float(r["endpoint_value"])
        assert int(r["solver_status_code"]) == 0
        for key in (
            "max_scenario_sum_residual",
            "max_class_positive_mass_residual",
            "max_transport_row_margin_residual",
            "max_transport_column_margin_residual",
            "max_nta_rank_positive_margin_residual",
        ):
            assert float(r[key]) <= EQ_TOL
        for key in (
            "max_overlap_capacity_excess",
            "max_positive_transport_capacity_excess",
            "rank_displacement_budget_excess",
            "max_rank_bridge_inequality_excess",
        ):
            assert float(r[key]) <= INEQ_TOL
        value = float(r["endpoint_value"])
        if "MTR" in r["metric"]:
            assert -1e-12 <= value <= 0.45 + 1e-12
        else:
            assert 0 <= value <= 1
    assert len(pairs) == 42
    for obj, vals in pairs.items():
        assert set(vals) == {"min", "max"}
        assert vals["min"] <= vals["max"] + 1e-10, (delta, obj, vals)

# Delta=0 frontier endpoints must reproduce v2 epsilon-star endpoints exactly.
v2_star = [r for r in v2_end if r["epsilon_source"] == "epsilon_star"]
assert len(v2_star) == 84
v2_map = {}
for r in v2_star:
    metric = r["metric"]
    if metric == "nta_rank_positive_liability_rate":
        metric = "transported_nta_positive_liability_rate"
    v2_map[(r["scope"], r["decile"], metric, r["bound"])] = float(r["endpoint_value"])

v3_zero = groups[0.0]
assert len(v3_zero) == 84
for r in v3_zero:
    key = (r["scope"], r["decile"], r["metric"], r["bound"])
    assert key in v2_map
    assert math.isclose(
        float(r["endpoint_value"]), v2_map[key], abs_tol=5e-9
    ), key

# Once the unrestricted analytical floor is attained, the minimum-epsilon
# frontier forces pseudo-filer positive shares to their lower envelope.  The
# resulting MTR point at that *frontier* must not be interpreted as identified.
expected_overall_floor = {
    "taxable_income_weighted_mean_MTR": 0.108892198911,
    "income_tax_liability_weighted_mean_MTR": 0.117712893177,
}
for delta in DELTAS[1:]:
    rows = groups[delta]
    for metric, expected in expected_overall_floor.items():
        q = [
            r for r in rows
            if r["scope"] == "overall" and r["metric"] == metric
        ]
        got = {r["bound"]: float(r["endpoint_value"]) for r in q}
        assert math.isclose(got["min"], expected, abs_tol=5e-10)
        assert math.isclose(got["max"], expected, abs_tol=5e-10)

# Direct HiGHS-IPM cross-check of every minimum-discrepancy frontier point.
m = load_module()
cfg = m.read_config()
data = m.load_data(cfg)
for delta, expected in zip(DELTAS, eps):
    model, res, got, diag = m.solve_minimum_at_delta(
        data, delta, EQ_TOL, INEQ_TOL, method="highs-ipm"
    )
    assert res.success
    assert math.isclose(got, expected, abs_tol=5e-9)

# The zero-discrepancy LP must also be infeasible under the independent HiGHS
# IPM path.
model, res, delta_star, diag = m.solve_zero_discrepancy_threshold(
    data, EQ_TOL, INEQ_TOL, method="highs-ipm"
)
assert not res.success
assert res.status == 2
assert delta_star is None and diag is None

# Deterministic regeneration.
subprocess.run(
    [sys.executable, str(RUN), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "rank-transport LP v3 tests: OK "
    "(8-delta frontier; delta=0 nests v2; unrestricted analytical floor; "
    "zero-discrepancy infeasible; 672 endpoints; HiGHS cross-check)"
)
