#!/usr/bin/env python3
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "stage1", HERE / "46_income_tax_stage1_population_overlap.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

v = m.load_inputs()
d, rows = m.compute(v)

assert int(d["f71561_mother_person_benchmark"]) == 122_494_621
assert int(d["nominal_outside_person_benchmark"]) == 3_651_478
assert int(d["nominal_return_filer_overlap_benchmark"]) == 19_438_597
assert int(d["candidate_person_upper"]) == 126_146_099
assert abs(d["c0_pretracked_participation_benchmark"] - 0.15409590271990892) < 1e-14
assert {r["status"] for r in rows} == {"NOMINAL_BRIDGE_BENCHMARK"}

print("stage1 nominal-overlap benchmark tests: OK")
