#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "grid49", HERE / "49_income_tax_stage1_frontier_grid.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

v = m.m.frontier47.overlap.load_inputs()
rows = m.compute_grid(v)

assert len(rows) == 9
rates = [r["robustness_rate"] for r in rows]
assert all(a >= b for a, b in zip(rates, rates[1:]))
by = {r["scenario"]: r for r in rows}
assert abs(by["C_U=0"]["robustness_rate_pct"] - 9.000149897619902) < 1e-12
assert by["C_U=12m"]["robustness_rate"] == 0.0
assert int(by["C_U=11m"]["remaining_overlap_benchmark"]) == 353_338

print("stage1 frontier-grid tests: OK")
