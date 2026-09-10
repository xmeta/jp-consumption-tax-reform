#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "frontier", HERE / "47_income_tax_stage1_contamination_frontier.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

v = m.overlap.load_inputs()
summary, rows = m.compute(v)

assert int(summary["births_2020_2024_upper"]) == 3_836_677
assert int(summary["international_inflows_2020_2024_upper"]) == 2_643_204
assert int(summary["quasi_final_death_upper_2024"]) == 1_605_378
assert int(summary["tracked_mismatch_allowance"]) == 8_085_259
assert {r["status"] for r in rows} == {"ROBUSTNESS_FRONTIER_TRACKED_ALLOWANCE"}

# Recovered thresholds are permitted here only as diagnostics carried by
# inputs.csv; scripts 48-49 and Paper 1 main results do not depend on them.
r2 = next(r for r in rows if r["prior"] == "score_power_2.0")
assert int(r2["residual_untracked_mismatch_to_erase_rejection"]) == 8_578_123

print("stage1 tracked-mismatch allowance tests: OK")
