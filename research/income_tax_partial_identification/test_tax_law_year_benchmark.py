#!/usr/bin/env python3
if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests; assertions must remain active")
from pathlib import Path
import csv, math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

pseudo = read(ROOT / "research/income_tax_pseudofiler/tax_law_year_pseudofiler_benchmark.csv")
bridge = read(HERE / "tax_law_year_bridge_benchmark.csv")
assert len(pseudo) == 10
assert len(bridge) == 2
assert {int(r["decile"]) for r in pseudo} == set(range(1, 11))
assert {int(r["tax_law_year"]) for r in bridge} == {2024, 2026}
for r in pseudo:
    assert r["scenario"] == "central"
    assert r["status"] == "SENSITIVITY_ONLY_NOT_IDENTIFIED_TAX_LAW_YEAR_BENCHMARK"

by = {int(r["tax_law_year"]): r for r in bridge}
r24, r26 = by[2024], by[2026]
assert int(r24["aggregate_year"]) == int(r26["aggregate_year"]) == 2024

# The benchmark must reproduce the existing 2026-law headline diagnostics.
v2 = read(HERE / "rank_bridge_lp_v2_minimum_relaxation.csv")[0]
assert math.isclose(float(r26["v2_epsilon_star"]), float(v2["epsilon_star"]), abs_tol=5e-10)
v3 = {float(r["delta"]): r for r in read(HERE / "rank_bridge_lp_v3_minimum_relaxation_frontier.csv")}
for delta, field in [(0.0,"v3_epsilon_star_delta_0"),(0.25,"v3_epsilon_star_delta_0p25"),(5.0,"v3_epsilon_star_delta_5")]:
    assert math.isclose(float(r26[field]), float(v3[delta]["epsilon_star"]), abs_tol=5e-10)
v4 = read(HERE / "rank_epsilon_surface_v4_summary.csv")
assert int(r26["v4_feasible_grid_points_of_104"]) == sum(r["feasible"] == "True" for r in v4) == 70
v5 = {float(r["delta"]): r for r in read(HERE / "rank_one_sided_bridge_v5_minimum_violation_frontier.csv")}
for delta, field in [(0.0,"v5_eta_star_delta_0"),(0.25,"v5_eta_star_delta_0p25"),(5.0,"v5_eta_star_delta_5")]:
    assert math.isclose(float(r26[field]), float(v5[delta]["eta_star"]), abs_tol=1e-12)

# Same-year law materially changes the symmetric bridge diagnostics but not the
# one-sided subset-compatibility conclusion.  These are sensitivity deltas, not
# an identified decomposition of the discrepancy.
assert float(r24["v2_epsilon_star"]) > float(r26["v2_epsilon_star"]) + 0.05
assert float(r24["v3_epsilon_star_delta_0p25"]) > float(r26["v3_epsilon_star_delta_0p25"]) + 0.05
assert int(r24["v4_feasible_grid_points_of_104"]) < int(r26["v4_feasible_grid_points_of_104"])
assert float(r24["v5_eta_star_delta_0"]) == float(r26["v5_eta_star_delta_0"]) == 0.0
assert abs(float(r24["central_equal_decile_mean_positive_share"]) - float(r26["central_equal_decile_mean_positive_share"])) > 0.05
assert all("not identified decomposition" in r["interpretation"] for r in bridge)
print("tax-law-year benchmark tests: OK (2024-law same-year benchmark; 2026 regression; v2-v5 comparison)")
