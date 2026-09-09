#!/usr/bin/env python3
"""Regression and independent checks for the pre-specified v5 implementation."""
from pathlib import Path
import csv
import math
import subprocess
import sys

import numpy as np
from scipy.optimize import linprog

import run_rank_one_sided_bridge_v5 as v5
import run_rank_bridge_lp_v3 as v3

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

FRONTIER = HERE / "rank_one_sided_bridge_v5_minimum_violation_frontier.csv"
DECILE = HERE / "rank_one_sided_bridge_v5_minimum_decile_diagnostics.csv"
ZERO = HERE / "rank_one_sided_bridge_v5_zero_violation_threshold.csv"
PLANS = HERE / "rank_one_sided_bridge_v5_transport_plans.csv"
ENDPOINTS = HERE / "rank_one_sided_bridge_v5_endpoints.csv"
V3_ENDPOINTS = HERE / "rank_bridge_lp_v3_endpoints.csv"

EXPECTED_DELTAS = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
TOL = 1e-8


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def f(r, k):
    return float(r[k])


frontier = read(FRONTIER)
assert len(frontier) == 8
assert [f(r, "delta") for r in frontier] == EXPECTED_DELTAS

# First post-pre-specification result: the directional subset restriction is
# feasible with eta=0 even at Delta=0.  These are reproducibility anchors, not
# pre-specified hypotheses.
for r in frontier:
    assert abs(f(r, "eta_star")) <= 1e-10
    assert abs(f(r, "solver_crosscheck_eta_star")) <= 1e-10
    assert f(r, "solver_crosscheck_absolute_difference") <= 1e-10
    assert f(r, "eta_star") <= f(r, "v3_epsilon_star_same_delta") + TOL
    assert f(r, "maximum_directional_violation_excess") <= TOL
    assert r["scientific_status"] == (
        "MODEL_CONTINGENT_RANK_ONE_SIDED_SUBSET_COMPATIBILITY"
    )
    for flag in (
        "historical_v6_restricted_lp_reproduced",
        "p1c13_v1_modified",
        "p1c14_v2_modified",
        "p1c15_v3_modified",
        "p1c16_v4_modified",
    ):
        assert r[flag] == "False"

# Zero directional violation is feasible without rank displacement.
zero = read(ZERO)
assert len(zero) == 1
z = zero[0]
assert z["zero_violation_feasible"] == "True"
assert abs(f(z, "delta_zero_star")) <= 1e-10
assert abs(f(z, "solver_crosscheck_delta_zero_star")) <= 1e-10
assert f(z, "solver_crosscheck_absolute_difference") <= 1e-10
assert f(z, "maximum_directional_violation_excess") <= TOL

# All reported decile solutions respect the one-sided restriction.
dec = read(DECILE)
assert len(dec) == 80
for r in dec:
    assert float(r["directional_violation_transported_minus_pseudo"]) <= (
        float(r["eta_star"]) + TOL
    )
    assert float(r["directional_violation_excess_over_eta"]) <= TOL
    assert r["subset_direction_satisfied_without_eta"] == "True"

# Transport-plan structure: eight 10x10 frontier plans plus one 10x10
# zero-violation minimum-delta plan.
plans = read(PLANS)
assert len(plans) == 900
sources = {}
for r in plans:
    sources[r["solution_source"]] = sources.get(r["solution_source"], 0) + 1
assert sources == {
    "eta_star_frontier": 800,
    "zero_violation_minimum_delta": 100,
}
zero_plan = [r for r in plans if r["solution_source"] == "zero_violation_minimum_delta"]
offdiag = sum(
    float(r["population_transport_mass"])
    for r in zero_plan
    if r["f_decile"] != r["nta_rank_decile"]
)
assert abs(offdiag) <= 1e-10

# Independent reduced-LP check for Delta=0 / eta=0.
# With exact same-rank transport, v5 feasibility reduces to allocating each
# grouped NTA positive-balance mass y_jq within its rank-overlap capacity while
# requiring rank-q positive mass <= 0.1 * max_s pseudo_positive(q,s).
# This formulation does not use the v5 inequality builder.
cfg = v5.read_config()
data = v3.load_data(cfg)
J = len(data.class_index)
D = len(data.deciles)
n = J * D

def idx(j, q):
    return j * D + q

A_eq = []
b_eq = []
for j in range(J):
    a = np.zeros(n)
    for q in range(D):
        a[idx(j, q)] = 1.0
    A_eq.append(a)
    b_eq.append(data.class_positive_mass[j])

A_ub = []
b_ub = []
pseudo_max = np.max(data.u, axis=1)
for q in range(D):
    a = np.zeros(n)
    for j in range(J):
        a[idx(j, q)] = 1.0
    A_ub.append(a)
    b_ub.append(0.1 * pseudo_max[q])

bounds = [
    (0.0, float(data.overlap[j, q]))
    for j in range(J)
    for q in range(D)
]
reduced = linprog(
    np.zeros(n),
    A_ub=np.vstack(A_ub),
    b_ub=np.array(b_ub),
    A_eq=np.vstack(A_eq),
    b_eq=np.array(b_eq),
    bounds=bounds,
    method="highs-ds",
    options={
        "presolve": True,
        "primal_feasibility_tolerance": 1e-9,
        "dual_feasibility_tolerance": 1e-9,
    },
)
assert reduced.success, reduced.message
y = reduced.x.reshape(J, D)
rank_positive = y.sum(axis=0)
assert np.max(rank_positive - 0.1 * pseudo_max) <= TOL
assert np.max(np.abs(y.sum(axis=1) - data.class_positive_mass)) <= TOL
assert np.max(np.maximum(0.0, y - data.overlap)) <= TOL

# Exactly the pre-specified 84 endpoint objectives are evaluated at each of
# eight frontier points.
end = read(ENDPOINTS)
assert len(end) == 672
for delta in EXPECTED_DELTAS:
    q = [r for r in end if abs(float(r["delta"]) - delta) <= 1e-12]
    assert len(q) == 84
    assert all(abs(float(r["eta_star"])) <= 1e-10 for r in q)
    assert all(float(r["maximum_directional_violation_excess"]) <= TOL for r in q)

# The pre-specified v3 outer-set regression applies to the *minimum budget*:
# eta_star_v5 <= epsilon_star_v3.  Endpoint sets here are evaluated at different
# frontier budgets (eta_star=0 versus positive epsilon_star), so no endpoint-set
# nesting is implied or tested.
# Post-result deterministic anchors for the overall MTR envelope.  They are
# intentionally labeled here as regression anchors rather than pre-spec values.
expected_overall = {
    ("taxable_income_weighted_mean_MTR", "min"): 0.100883929779,
    ("taxable_income_weighted_mean_MTR", "max"): 0.128679704602,
    ("income_tax_liability_weighted_mean_MTR", "min"): 0.108806323885,
    ("income_tax_liability_weighted_mean_MTR", "max"): 0.137775579803,
}
for delta in EXPECTED_DELTAS:
    q = [
        r for r in end
        if abs(float(r["delta"]) - delta) <= 1e-12 and r["scope"] == "overall"
    ]
    assert len(q) == 4
    for r in q:
        expected = expected_overall[(r["metric"], r["bound"])]
        assert math.isclose(
            float(r["endpoint_value"]), expected, abs_tol=2e-12, rel_tol=0.0
        ), (delta, r["metric"], r["bound"], r["endpoint_value"], expected)

# Implementation must leave Paper 1 unpromoted.
claims = read(ROOT / "paper1/data/claim_registry.csv")
assert len(claims) == 16
assert all(r["claim_id"] != "P1-C17" for r in claims)

subprocess.run(
    [sys.executable, str(HERE / "run_rank_one_sided_bridge_v5.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "rank one-sided bridge v5 tests: OK "
    "(eta*=0 at all 8 deltas; zero violation at Delta=0; independent reduced-LP "
    "check; 672 endpoints; v3 outer-set regression)"
)
