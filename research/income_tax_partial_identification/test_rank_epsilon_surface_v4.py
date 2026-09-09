#!/usr/bin/env python3
"""Regression and invariant tests for pre-specified v4 sensitivity surface."""
from pathlib import Path
import csv
import math
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

RUN = HERE / "run_rank_epsilon_surface_v4.py"
FEAS = HERE / "rank_epsilon_surface_v4_feasibility.csv"
END = HERE / "rank_epsilon_surface_v4_endpoints.csv"
SUMMARY = HERE / "rank_epsilon_surface_v4_summary.csv"
V2_FEAS = HERE / "rank_bridge_lp_v2_feasibility.csv"
V2_END = HERE / "rank_bridge_lp_v2_endpoints.csv"
V3_FRONTIER = HERE / "rank_bridge_lp_v3_minimum_relaxation_frontier.csv"

DELTAS = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
EPSILONS = [
    0.0, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15,
    0.175, 0.20, 0.225, 0.25, 0.275, 0.30,
]
STATUS = "MODEL_CONTINGENT_RANK_EPSILON_SURFACE"
TOL = 1e-8


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def as_bool(x):
    assert x in {"True", "False"}, x
    return x == "True"


feas = read(FEAS)
end = read(END)
summary = read(SUMMARY)
v2_feas = read(V2_FEAS)
v2_end = read(V2_END)
v3_frontier = read(V3_FRONTIER)

# Complete pre-specified surface.
assert len(feas) == 104
assert len(summary) == 104
expected_points = [(d, e) for d in DELTAS for e in EPSILONS]
assert [(float(r["delta"]), float(r["epsilon"])) for r in feas] == expected_points
assert [(float(r["delta"]), float(r["epsilon"])) for r in summary] == expected_points

# Scientific-state flags and independent solver classification agreement.
for collection in [feas, end, summary]:
    for r in collection:
        assert r["scientific_status"] == STATUS
        assert r["historical_v6_restricted_lp_reproduced"] == "False"
        assert r["p1c13_v1_modified"] == "False"
        assert r["p1c14_v2_modified"] == "False"
        assert r["p1c15_v3_modified"] == "False"

for r in feas:
    assert r["classification_agrees"] == "True"
    assert as_bool(r["feasible"]) == as_bool(r["crosscheck_feasible"])
    if as_bool(r["feasible"]):
        assert int(r["solver_status_code"]) == 0
        assert int(r["crosscheck_status_code"]) == 0
        for key in (
            "max_scenario_sum_residual",
            "max_class_positive_mass_residual",
            "max_transport_row_margin_residual",
            "max_transport_column_margin_residual",
            "max_nta_rank_positive_margin_residual",
        ):
            assert float(r[key]) <= TOL, (r["delta"], r["epsilon"], key, r[key])
        for key in (
            "max_overlap_capacity_excess",
            "max_positive_transport_capacity_excess",
            "rank_displacement_budget_excess",
            "max_rank_bridge_inequality_excess",
        ):
            assert float(r[key]) <= TOL, (r["delta"], r["epsilon"], key, r[key])
        assert float(r["minimum_decision_variable"]) >= -TOL
        assert (
            float(r["transport_cost_at_one_feasible_solution"])
            <= float(r["delta"]) + TOL
        )
        assert (
            float(r["max_rank_bridge_gap_at_one_feasible_solution"])
            <= float(r["epsilon"]) + TOL
        )
    else:
        assert int(r["solver_status_code"]) == 2
        assert int(r["crosscheck_status_code"]) == 2

# V3 minimum frontier determines the fixed-grid feasibility boundary away from
# exact numerical equality. This derives the expected feasible count rather
# than hard-coding a post-result choice.
stars = {float(r["delta"]): float(r["epsilon_star"]) for r in v3_frontier}
assert set(stars) == set(DELTAS)
expected_feasible = 0
for r in feas:
    delta = float(r["delta"])
    epsilon = float(r["epsilon"])
    f = as_bool(r["feasible"])
    star = stars[delta]
    if epsilon < star - TOL:
        assert not f, (delta, epsilon, star)
    elif epsilon > star + TOL:
        assert f, (delta, epsilon, star)
    if f:
        expected_feasible += 1

assert len(end) == expected_feasible * 84
assert expected_feasible == sum(as_bool(r["feasible"]) for r in feas)

# Exactly 84 endpoint rows for each feasible point; none for infeasible.
by_point = {}
for r in end:
    key = (float(r["delta"]), float(r["epsilon"]))
    by_point.setdefault(key, []).append(r)
for r in feas:
    key = (float(r["delta"]), float(r["epsilon"]))
    rows = by_point.get(key, [])
    assert len(rows) == (84 if as_bool(r["feasible"]) else 0), (key, len(rows))

# Endpoint structure, residuals and value ranges.
endpoint_map = {}
for r in end:
    key = (
        float(r["delta"]), float(r["epsilon"]), r["scope"], r["decile"],
        r["metric"], r["bound"],
    )
    assert key not in endpoint_map
    endpoint_map[key] = float(r["endpoint_value"])
    assert int(r["solver_status_code"]) == 0

    for residual in (
        "max_scenario_sum_residual",
        "max_class_positive_mass_residual",
        "max_transport_row_margin_residual",
        "max_transport_column_margin_residual",
        "max_nta_rank_positive_margin_residual",
    ):
        assert float(r[residual]) <= TOL
    for residual in (
        "max_overlap_capacity_excess",
        "max_positive_transport_capacity_excess",
        "rank_displacement_budget_excess",
        "max_rank_bridge_inequality_excess",
    ):
        assert float(r[residual]) <= TOL

    value = float(r["endpoint_value"])
    if "MTR" in r["metric"]:
        assert -TOL <= value <= 0.45 + TOL
    else:
        assert -TOL <= value <= 1.0 + TOL

for key, rows in by_point.items():
    objects = {}
    for r in rows:
        obj = (r["scope"], r["decile"], r["metric"])
        objects.setdefault(obj, {})[r["bound"]] = float(r["endpoint_value"])
    assert len(objects) == 42
    for obj, pair in objects.items():
        assert set(pair) == {"min", "max"}
        assert pair["min"] <= pair["max"] + TOL, (key, obj, pair)

# Delta=0 must reproduce the committed v2 fixed-epsilon feasibility grid.
v2_grid_feas = {
    float(r["epsilon"]): as_bool(r["feasible"])
    for r in v2_feas if r["epsilon_source"] == "pre_specified_grid"
}
assert set(v2_grid_feas) == set(EPSILONS)
v4_delta0 = {
    float(r["epsilon"]): as_bool(r["feasible"])
    for r in feas if float(r["delta"]) == 0.0
}
assert v4_delta0 == v2_grid_feas

# Delta=0 endpoint values must reproduce all committed v2 fixed-grid
# endpoints, mapping only the v2 NTA metric label to the v3/v4 transport label.
def normalized_metric(metric):
    if metric == "nta_rank_positive_liability_rate":
        return "transported_nta_positive_liability_rate"
    return metric

v2_grid_end = {}
for r in v2_end:
    if r["epsilon_source"] != "pre_specified_grid":
        continue
    key = (
        float(r["epsilon"]), r["scope"], r["decile"],
        normalized_metric(r["metric"]), r["bound"],
    )
    v2_grid_end[key] = float(r["endpoint_value"])

v4_delta0_end = {}
for r in end:
    if float(r["delta"]) != 0.0:
        continue
    key = (
        float(r["epsilon"]), r["scope"], r["decile"],
        r["metric"], r["bound"],
    )
    v4_delta0_end[key] = float(r["endpoint_value"])

assert set(v4_delta0_end) == set(v2_grid_end)
for key, expected in v2_grid_end.items():
    got = v4_delta0_end[key]
    assert math.isclose(got, expected, abs_tol=TOL), (key, got, expected)

# Feasibility must be monotone when either budget is relaxed.
feasible_map = {
    (float(r["delta"]), float(r["epsilon"])): as_bool(r["feasible"])
    for r in feas
}
for d in DELTAS:
    seen = False
    for e in EPSILONS:
        f = feasible_map[(d, e)]
        if seen:
            assert f, ("epsilon feasibility nesting", d, e)
        if f:
            seen = True

for e in EPSILONS:
    seen = False
    for d in DELTAS:
        f = feasible_map[(d, e)]
        if seen:
            assert f, ("delta feasibility nesting", d, e)
        if f:
            seen = True

# Endpoint sets must expand monotonically under either relaxation.  Check all
# 42 objective identities, not just overall MTR summaries.
def point_objects(delta, epsilon):
    rows = by_point.get((delta, epsilon), [])
    out = {}
    for r in rows:
        obj = (r["scope"], r["decile"], r["metric"])
        out.setdefault(obj, {})[r["bound"]] = float(r["endpoint_value"])
    return out

def assert_nested(smaller, larger, label):
    assert set(smaller) == set(larger)
    for obj in smaller:
        a = smaller[obj]
        b = larger[obj]
        assert b["min"] <= a["min"] + TOL, (label, obj, a, b)
        assert b["max"] >= a["max"] - TOL, (label, obj, a, b)
        aw = a["max"] - a["min"]
        bw = b["max"] - b["min"]
        assert bw >= aw - TOL, (label, obj, aw, bw)

for d in DELTAS:
    feasible_eps = [e for e in EPSILONS if feasible_map[(d, e)]]
    for e1, e2 in zip(feasible_eps, feasible_eps[1:]):
        assert_nested(
            point_objects(d, e1),
            point_objects(d, e2),
            ("epsilon nesting", d, e1, e2),
        )

for e in EPSILONS:
    feasible_d = [d for d in DELTAS if feasible_map[(d, e)]]
    for d1, d2 in zip(feasible_d, feasible_d[1:]):
        assert_nested(
            point_objects(d1, e),
            point_objects(d2, e),
            ("delta nesting", e, d1, d2),
        )

# Summary must contain all 104 points and exactly reproduce overall endpoint
# pairs and widths when feasible, while leaving endpoint fields blank otherwise.
summary_map = {
    (float(r["delta"]), float(r["epsilon"])): r for r in summary
}
for point in expected_points:
    r = summary_map[point]
    f = feasible_map[point]
    assert as_bool(r["feasible"]) == f
    assert int(r["endpoint_row_count"]) == (84 if f else 0)
    fields = (
        "overall_taxable_mtr_min",
        "overall_taxable_mtr_max",
        "overall_taxable_mtr_width",
        "overall_liability_mtr_min",
        "overall_liability_mtr_max",
        "overall_liability_mtr_width",
    )
    if not f:
        assert all(r[k] == "" for k in fields)
        continue

    objs = point_objects(*point)
    for metric, prefix in (
        ("taxable_income_weighted_mean_MTR", "overall_taxable_mtr"),
        ("income_tax_liability_weighted_mean_MTR", "overall_liability_mtr"),
    ):
        pair = objs[("overall", "", metric)]
        lo = float(r[f"{prefix}_min"])
        hi = float(r[f"{prefix}_max"])
        width = float(r[f"{prefix}_width"])
        assert math.isclose(lo, pair["min"], abs_tol=1e-10)
        assert math.isclose(hi, pair["max"], abs_tol=1e-10)
        assert math.isclose(width, hi - lo, abs_tol=1e-10)

# Deterministic regeneration. This also repeats every primary LP and every
# HiGHS-IPM feasibility classification from a clean output comparison path.
subprocess.run(
    [sys.executable, str(RUN), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "rank-epsilon surface v4 tests: OK "
    f"(104 fixed points; {expected_feasible} feasible; "
    f"{len(end)} endpoints; v2 Delta=0 regression; v3 boundary; "
    "2D set nesting; HiGHS classification cross-check)"
)
