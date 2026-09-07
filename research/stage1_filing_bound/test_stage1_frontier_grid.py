#!/usr/bin/env python3
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "grid49",
    HERE / "49_income_tax_stage1_frontier_grid.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

v = m.m.frontier47.overlap.load_inputs()
rows = m.compute_grid(v)

assert len(rows) == 8
lbs = [r["lower_bound"] for r in rows]
assert all(a >= b for a, b in zip(lbs, lbs[1:]))

by = {r["scenario"]: r for r in rows}
assert by["C_NR=0"]["reject_score_power_2_0"] is True
assert by["C_NR=8m"]["reject_score_power_2_0"] is True
assert by["score2_break_even"]["reject_score_power_2_0"] is False
assert by["C_NR=9m"]["reject_score_power_2_0"] is False

for row in rows:
    assert row["reject_score_power_0_5"] is False
    assert row["reject_score_power_1_0"] is False

assert abs(by["score2_break_even"]["lower_bound_pct"] - 2.2) < 1e-12
assert abs(by["C_NR=0"]["lower_bound_pct"] - 9.000149897619902) < 1e-12

print("stage1 frontier-grid tests: OK")
