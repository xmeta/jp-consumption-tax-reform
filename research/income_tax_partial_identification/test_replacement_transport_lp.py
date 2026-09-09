#!/usr/bin/env python3
"""Regression and invariant tests for replacement transport-relaxation LP v1."""
from pathlib import Path
import csv
import math
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

WEIGHTS = HERE / "replacement_transport_lp_decile_weights.csv"
MINIMUM = HERE / "replacement_transport_lp_minimum_relaxation.csv"
MIN_DECILE = HERE / "replacement_transport_lp_minimum_decile_diagnostics.csv"
FEAS = HERE / "replacement_transport_lp_feasibility.csv"
END = HERE / "replacement_transport_lp_endpoints.csv"
RUN = HERE / "run_replacement_transport_lp.py"

SCHEMES = {"equal_decile", "f71561_leaf_count_normalized"}
STATUS = "MODEL_CONTINGENT_TRANSPORT_RELAXATION"
EXPECTED_EPS = {
    "equal_decile": 0.24186895007431228,
    "f71561_leaf_count_normalized": 0.22195251225156468,
}
GRID = [
    0.000, 0.025, 0.050, 0.075, 0.100, 0.125, 0.150,
    0.175, 0.200, 0.225, 0.250, 0.275, 0.300,
]
EQ_TOL = 1e-8
INEQ_TOL = 1e-8


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def as_bool(s):
    assert s in {"True", "False"}
    return s == "True"


weights = read(WEIGHTS)
minimum = read(MINIMUM)
min_decile = read(MIN_DECILE)
feas = read(FEAS)
endpoints = read(END)

assert len(weights) == 20
assert len(minimum) == 2
assert len(min_decile) == 20
assert len(feas) == 28
assert len(endpoints) == 576

assert {r["weight_scheme"] for r in weights} == SCHEMES
assert {r["weight_scheme"] for r in minimum} == SCHEMES
assert {r["weight_scheme"] for r in min_decile} == SCHEMES
assert {r["weight_scheme"] for r in feas} == SCHEMES
assert {r["weight_scheme"] for r in endpoints} == SCHEMES

for collection in [minimum, min_decile, feas, endpoints]:
    for r in collection:
        assert r["scientific_status"] == STATUS
        assert r["historical_v6_restricted_lp_reproduced"] == "False"

# Weight schemes are fixed ex ante and each is a probability vector.
for scheme in SCHEMES:
    q = [r for r in weights if r["weight_scheme"] == scheme]
    assert {int(r["decile"]) for r in q} == set(range(1, 11))
    vals = [float(r["decile_weight"]) for r in q]
    assert math.isclose(sum(vals), 1.0, abs_tol=1e-10)
    assert all(v > 0 for v in vals)
    if scheme == "equal_decile":
        assert all(math.isclose(v, 0.1, abs_tol=1e-12) for v in vals)

min_by_scheme = {r["weight_scheme"]: r for r in minimum}
for scheme, expected in EXPECTED_EPS.items():
    r = min_by_scheme[scheme]
    eps = float(r["epsilon_star"])
    assert math.isclose(eps, expected, rel_tol=0, abs_tol=5e-10), (
        scheme, eps, expected
    )
    assert float(r["aggregate_discrepancy_lower_bound"]) <= eps + 1e-12
    assert float(r["weighted_raw_min_pseudo_positive_modeled_annual_income_tax_share"]) <= (
        float(r["weighted_raw_max_pseudo_positive_modeled_annual_income_tax_share"])
    )
    assert 0 < float(r["nta_overall_positive_self_assessed_balance_rate"]) < 1
    assert as_bool(r["solver_success"])
    assert int(r["solver_status_code"]) == 0
    assert float(r["max_scenario_sum_residual"]) <= EQ_TOL
    assert float(r["max_decile_mass_residual"]) <= EQ_TOL
    assert float(r["max_category_mass_residual"]) <= EQ_TOL
    assert float(r["max_transport_inequality_excess"]) <= INEQ_TOL
    assert float(r["minimum_decision_variable"]) >= -EQ_TOL
    assert math.isclose(
        float(r["max_transport_gap"]), eps, abs_tol=5e-10
    )

# One reported optimum must itself satisfy epsilon*; allocation/support is not
# asserted unique.
for scheme in SCHEMES:
    q = [r for r in min_decile if r["weight_scheme"] == scheme]
    assert len(q) == 10
    eps = EXPECTED_EPS[scheme]
    assert max(float(r["absolute_gap"]) for r in q) <= eps + INEQ_TOL
    assert any(as_bool(r["binding_within_1e8"]) for r in q)
    for r in q:
        p = float(r["pseudo_positive_modeled_annual_income_tax_share_at_one_optimum"])
        t = float(r["transported_nta_stage2_rate_at_one_optimum"])
        gap = float(r["signed_gap_pseudo_minus_transport"])
        assert 0 <= p <= 1
        assert 0 <= t <= 1
        assert math.isclose(gap, p - t, abs_tol=1e-10)
        assert "need not be unique" in r["solution_note"]

# Fixed-grid feasibility must switch only after epsilon reaches epsilon*.
for scheme in SCHEMES:
    q = [
        r for r in feas
        if r["weight_scheme"] == scheme
        and r["epsilon_source"] == "pre_specified_grid"
    ]
    assert len(q) == len(GRID)
    got_grid = [float(r["epsilon"]) for r in q]
    assert all(
        math.isclose(a, b, abs_tol=1e-12)
        for a, b in zip(got_grid, GRID)
    )
    eps_star = EXPECTED_EPS[scheme]
    for r in q:
        eps = float(r["epsilon"])
        feasible = as_bool(r["feasible"])
        assert feasible == (eps >= eps_star - 1e-10), (scheme, eps, eps_star)
        if feasible:
            assert int(r["solver_status_code"]) == 0
            assert float(r["max_scenario_sum_residual"]) <= EQ_TOL
            assert float(r["max_decile_mass_residual"]) <= EQ_TOL
            assert float(r["max_category_mass_residual"]) <= EQ_TOL
            assert float(r["max_transport_inequality_excess"]) <= INEQ_TOL
            assert float(r["minimum_decision_variable"]) >= -EQ_TOL
        else:
            assert int(r["solver_status_code"]) == 2
            assert "infeasible" in r["solver_message"].lower()

    star = [
        r for r in feas
        if r["weight_scheme"] == scheme
        and r["epsilon_source"] == "epsilon_star"
    ]
    assert len(star) == 1
    assert as_bool(star[0]["feasible"])
    assert math.isclose(
        float(star[0]["epsilon"]), eps_star, abs_tol=5e-10
    )

# Every feasible epsilon point yields exactly 64 endpoint rows:
# 10 deciles x 3 metrics x 2 bounds + 2 overall MTR metrics x 2 bounds.
grouped = {}
for r in endpoints:
    key = (
        r["weight_scheme"],
        r["epsilon_source"],
        float(r["epsilon"]),
    )
    grouped.setdefault(key, []).append(r)
assert len(grouped) == 9
assert all(len(v) == 64 for v in grouped.values())

for r in endpoints:
    val = float(r["endpoint_value"])
    metric = r["metric"]
    assert r["bound"] in {"min", "max"}
    assert r["scope"] in {"decile", "overall"}
    if "MTR" in metric:
        assert -1e-12 <= val <= 0.45 + 1e-12
    elif metric == "pseudo_positive_modeled_annual_income_tax_share":
        assert 0 <= val <= 1
    else:
        raise AssertionError(metric)
    assert int(r["solver_status_code"]) == 0
    assert float(r["max_scenario_sum_residual"]) <= EQ_TOL
    assert float(r["max_decile_mass_residual"]) <= EQ_TOL
    assert float(r["max_category_mass_residual"]) <= EQ_TOL
    assert float(r["max_transport_inequality_excess"]) <= INEQ_TOL
    assert float(r["minimum_decision_variable"]) >= -EQ_TOL

# At each point, min <= max for every requested functional.
for key, rows in grouped.items():
    pairs = {}
    for r in rows:
        obj = (r["scope"], r["decile"], r["metric"])
        pairs.setdefault(obj, {})[r["bound"]] = float(r["endpoint_value"])
    assert len(pairs) == 32
    for obj, vals in pairs.items():
        assert set(vals) == {"min", "max"}
        assert vals["min"] <= vals["max"] + 1e-10, (key, obj, vals)

# The feasible set expands monotonically with epsilon on the pre-specified grid:
# minima cannot increase and maxima cannot decrease.
for scheme in SCHEMES:
    q = [
        r for r in endpoints
        if r["weight_scheme"] == scheme
        and r["epsilon_source"] == "pre_specified_grid"
    ]
    objects = {
        (r["scope"], r["decile"], r["metric"]) for r in q
    }
    for obj in objects:
        for bound in ["min", "max"]:
            z = sorted(
                (
                    float(r["epsilon"]),
                    float(r["endpoint_value"]),
                )
                for r in q
                if (r["scope"], r["decile"], r["metric"]) == obj
                and r["bound"] == bound
            )
            for (_, a), (_, b) in zip(z, z[1:]):
                if bound == "min":
                    assert b <= a + 1e-9, (scheme, obj, z)
                else:
                    assert b + 1e-9 >= a, (scheme, obj, z)

# Regression anchors for epsilon-star overall MTR envelopes.
expected_overall = {
    ("equal_decile", "taxable_income_weighted_mean_MTR"):
        (0.102542256962, 0.120705685962),
    ("equal_decile", "income_tax_liability_weighted_mean_MTR"):
        (0.111142262186, 0.130258116694),
    ("f71561_leaf_count_normalized", "taxable_income_weighted_mean_MTR"):
        (0.0954990298023, 0.113078393108),
    ("f71561_leaf_count_normalized", "income_tax_liability_weighted_mean_MTR"):
        (0.103047467719, 0.121585807029),
}
for (scheme, metric), (lo, hi) in expected_overall.items():
    q = [
        r for r in endpoints
        if r["weight_scheme"] == scheme
        and r["epsilon_source"] == "epsilon_star"
        and r["scope"] == "overall"
        and r["metric"] == metric
    ]
    got = {r["bound"]: float(r["endpoint_value"]) for r in q}
    assert math.isclose(got["min"], lo, abs_tol=5e-10)
    assert math.isclose(got["max"], hi, abs_tol=5e-10)

# Deterministic regeneration with the pinned solver versions.
subprocess.run(
    [sys.executable, str(RUN), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "replacement transport-LP tests: OK "
    "(epsilon*; 28 feasibility rows; 576 endpoints; residuals; monotonicity)"
)
