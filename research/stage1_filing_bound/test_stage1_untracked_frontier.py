#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "frontier48", HERE / "48_income_tax_stage1_untracked_frontier.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

v = m.frontier47.overlap.load_inputs()
s = m.compute(v)

assert int(s["nominal_overlap_benchmark"]) == 19_438_597
assert int(s["tracked_mismatch_allowance"]) == 8_085_259
assert int(s["residual_benchmark_after_tracked_allowance"]) == 11_353_338
assert int(s["candidate_person_upper"]) == 126_146_099
assert abs(s["robustness_rate_at_C_U_0"] - 0.09000149897619902) < 1e-14

p = s["candidate_person_upper"]
br = s["residual_benchmark_after_tracked_allowance"]
assert m.critical_budget(0.0, br, p) == br
assert abs(m.critical_budget(0.022, br, p) - 8_578_123.822) < 1e-9
assert m.critical_budget(1.0, br, p) == 0.0
assert abs(m.robustness_rate(0, br, p) - s["robustness_rate_at_C_U_0"]) < 1e-14
assert m.robustness_rate(br + 1, br, p) == 0.0

print("stage1 untracked-mismatch frontier tests: OK")
