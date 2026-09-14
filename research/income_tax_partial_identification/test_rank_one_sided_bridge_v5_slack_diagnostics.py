#!/usr/bin/env python3
"""Regression and independent exact-rank checks for v5 slack diagnostics."""
if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests")

from pathlib import Path
import csv
import math
import subprocess
import sys

import numpy as np
from scipy.optimize import linprog

import run_rank_bridge_lp_v3 as v3
import run_rank_one_sided_bridge_v5 as v5
import run_rank_one_sided_bridge_v5_slack_diagnostics as slack

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BOUNDS = HERE / "rank_one_sided_bridge_v5_slack_bounds.csv"
SUMMARY = HERE / "rank_one_sided_bridge_v5_slack_summary.csv"
EXPECTED_DELTAS = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
TOL = 1e-8


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


bounds = read(BOUNDS)
summary = read(SUMMARY)
assert len(bounds) == 80
assert len(summary) == 8
assert [float(r["delta"]) for r in summary] == EXPECTED_DELTAS

for r in bounds:
    lo = float(r["slack_minimum_over_fixed_frontier_set"])
    hi = float(r["slack_maximum_over_fixed_frontier_set"])
    assert lo >= -TOL
    assert hi + TOL >= lo
    assert r["can_bind"] == str(lo <= TOL)
    assert r["must_bind"] == str(hi <= TOL)
    assert r["can_near_bind"] == str(lo <= slack.NEAR_BINDING_THRESHOLD)
    assert r["must_near_bind"] == str(hi <= slack.NEAR_BINDING_THRESHOLD)

for r in summary:
    assert abs(float(r["eta_star"])) <= 1e-10
    assert 0 <= int(r["witness_binding_count"]) <= 10
    assert 0 <= int(r["feasible_set_can_bind_decile_count"]) <= 10
    assert 0 <= int(r["feasible_set_must_bind_decile_count"]) <= 10
    assert int(r["feasible_set_must_bind_decile_count"]) <= int(r["feasible_set_can_bind_decile_count"])

# Independent reduced LP for Delta=0 / eta=0. Delta=0 fixes population
# transport to the identity. We optimize each decile slack using only grouped
# positive-balance allocations y_jq plus one scalar pseudo rate p_q. Other
# deciles need only satisfy their existence condition m_q <= 0.1*max_s u_qs.
cfg = v5.read_config()
data = v3.load_data(cfg)
J = len(data.class_index)
D = len(data.deciles)
N_Y = J * D


def yidx(j, q):
    return j * D + q


def reduced_bound(target_q, maximize=False):
    pidx = N_Y
    n = N_Y + 1
    c = np.zeros(n)
    for j in range(J):
        c[yidx(j, target_q)] = -10.0
    c[pidx] = 1.0
    if maximize:
        c = -c

    A_eq = []
    b_eq = []
    for j in range(J):
        a = np.zeros(n)
        for q in range(D):
            a[yidx(j, q)] = 1.0
        A_eq.append(a)
        b_eq.append(data.class_positive_mass[j])

    A_ub = []
    b_ub = []
    pseudo_max = np.max(data.u, axis=1)
    for q in range(D):
        a = np.zeros(n)
        for j in range(J):
            a[yidx(j, q)] = 10.0
        if q == target_q:
            a[pidx] = -1.0
            rhs = 0.0
        else:
            rhs = float(pseudo_max[q])
        A_ub.append(a)
        b_ub.append(rhs)

    bounds_lp = [
        (0.0, float(data.overlap[j, q]))
        for j in range(J)
        for q in range(D)
    ]
    bounds_lp.append((float(np.min(data.u[target_q])), float(np.max(data.u[target_q]))))

    res = linprog(
        c,
        A_ub=np.vstack(A_ub),
        b_ub=np.array(b_ub),
        A_eq=np.vstack(A_eq),
        b_eq=np.array(b_eq),
        bounds=bounds_lp,
        method="highs-ds",
        options={
            "presolve": True,
            "primal_feasibility_tolerance": 1e-9,
            "dual_feasibility_tolerance": 1e-9,
        },
    )
    assert res.success, res.message
    return float((-1.0 if maximize else 1.0) * res.fun)


same_rank = {
    int(r["decile"]): r for r in bounds if math.isclose(float(r["delta"]), 0.0, abs_tol=1e-12)
}
assert len(same_rank) == 10
for qi, decile in enumerate(data.deciles):
    lo = reduced_bound(qi, maximize=False)
    hi = reduced_bound(qi, maximize=True)
    row = same_rank[int(decile)]
    assert math.isclose(lo, float(row["slack_minimum_over_fixed_frontier_set"]), abs_tol=2e-9, rel_tol=0.0), (decile, lo, row)
    assert math.isclose(hi, float(row["slack_maximum_over_fixed_frontier_set"]), abs_tol=2e-9, rel_tol=0.0), (decile, hi, row)

subprocess.run(
    [sys.executable, str(HERE / "run_rank_one_sided_bridge_v5_slack_diagnostics.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print("rank one-sided bridge v5 slack diagnostics tests: OK (80 bounds; reduced exact-rank LP agrees)")
