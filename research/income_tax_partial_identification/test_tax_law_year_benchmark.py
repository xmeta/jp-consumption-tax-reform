#!/usr/bin/env python3
if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests; assertions must remain active")
from pathlib import Path
import csv, math, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research/income_tax_pseudofiler"))
import run_pseudofiler_core as pf  # noqa: E402


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


pseudo = read(ROOT / "research/income_tax_pseudofiler/tax_law_year_pseudofiler_benchmark.csv")
bridge = read(HERE / "tax_law_year_bridge_benchmark.csv")
assert len(pseudo) == 40
assert len(bridge) == 4
combos = {(2024, 2024), (2024, 2026), (2026, 2024), (2026, 2026)}
assert {(int(r["tax_law_year"]), int(r["nuisance_calibration_tax_law_year"])) for r in bridge} == combos
assert {(int(r["tax_law_year"]), int(r["nuisance_calibration_tax_law_year"])) for r in pseudo} == combos
assert {int(r["decile"]) for r in pseudo} == set(range(1, 11))
assert all(r["scenario"] == "central" for r in pseudo)
assert all(r["status"] == "SENSITIVITY_ONLY_NOT_IDENTIFIED_TAX_LAW_YEAR_2X2_BENCHMARK" for r in pseudo)

# The dependent-composition sensitivity must obtain statutory amounts from the
# selected law module rather than silently reusing the 2026-derived amount column.
base = pf.nta_salary_dependent_proxy(5_000_000, pf.statutory_2024)
class DoubledDependentLaw:
    @staticmethod
    def dependent_deduction_amounts():
        return {k: 2.0 * v for k, v in pf.statutory_2024.dependent_deduction_amounts().items()}
shifted = pf.nta_salary_dependent_proxy(5_000_000, DoubledDependentLaw)
assert base > 0.0
assert math.isclose(shifted, 2.0 * base, rel_tol=0.0, abs_tol=1e-9)

by = {
    (int(r["tax_law_year"]), int(r["nuisance_calibration_tax_law_year"])): r
    for r in bridge
}
r24_24 = by[(2024, 2024)]
r24_26 = by[(2024, 2026)]
r26_24 = by[(2026, 2024)]
r26_26 = by[(2026, 2026)]
assert all(int(r["aggregate_year"]) == 2024 for r in bridge)
assert all("not an identified causal decomposition" in r["interpretation"] for r in bridge)

# Fixed-calibration cross-law rows must use exactly the same nuisance scale for
# a given calibration year and decile.
for calibration_year in (2024, 2026):
    for d in range(1, 11):
        rows = [
            r for r in pseudo
            if int(r["nuisance_calibration_tax_law_year"]) == calibration_year
            and int(r["decile"]) == d
        ]
        assert len(rows) == 2
        assert math.isclose(
            float(rows[0]["nuisance_income_scale"]),
            float(rows[1]["nuisance_income_scale"]),
            abs_tol=1e-12,
        )

# The diagonal 2026/2026 cell remains an exact regression control for the
# committed headline diagnostics.
v2 = read(HERE / "rank_bridge_lp_v2_minimum_relaxation.csv")[0]
assert math.isclose(float(r26_26["v2_epsilon_star"]), float(v2["epsilon_star"]), abs_tol=5e-10)
v3 = {float(r["delta"]): r for r in read(HERE / "rank_bridge_lp_v3_minimum_relaxation_frontier.csv")}
for delta, field in [(0.0, "v3_epsilon_star_delta_0"), (0.25, "v3_epsilon_star_delta_0p25"), (5.0, "v3_epsilon_star_delta_5")]:
    assert math.isclose(float(r26_26[field]), float(v3[delta]["epsilon_star"]), abs_tol=5e-10)
v4 = read(HERE / "rank_epsilon_surface_v4_summary.csv")
assert int(r26_26["v4_feasible_grid_points_of_104"]) == sum(r["feasible"] == "True" for r in v4) == 70
v5 = {float(r["delta"]): r for r in read(HERE / "rank_one_sided_bridge_v5_minimum_violation_frontier.csv")}
for delta, field in [(0.0, "v5_eta_star_delta_0"), (0.25, "v5_eta_star_delta_0p25"), (5.0, "v5_eta_star_delta_5")]:
    assert math.isclose(float(r26_26[field]), float(v5[delta]["eta_star"]), abs_tol=1e-12)

# Both fixed-calibration law substitutions are material.  The diagonal change
# can now be written as law substitution plus recalibration along either path;
# this is an algebraic within-model decomposition, not causal identification.
for field in ("v2_epsilon_star", "v3_epsilon_star_delta_0p25"):
    a = float(r24_24[field]); b = float(r26_24[field])
    c = float(r24_26[field]); d = float(r26_26[field])
    assert abs(b - a) > 1e-3
    assert abs(d - c) > 1e-3
    assert math.isclose(d - a, (b - a) + (d - b), abs_tol=1e-10)
    assert math.isclose(d - a, (c - a) + (d - c), abs_tol=1e-10)

assert float(r24_24["v5_eta_star_delta_0"]) == 0.0
assert float(r24_26["v5_eta_star_delta_0"]) == 0.0
assert float(r26_24["v5_eta_star_delta_0"]) == 0.0
assert float(r26_26["v5_eta_star_delta_0"]) == 0.0
print("tax-law-year benchmark tests: OK (2x2 law substitution x nuisance calibration; 2026 regression; v2-v5)")
