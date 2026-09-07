#!/usr/bin/env python3
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "stage1",
    HERE / "46_income_tax_stage1_population_overlap.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

v = m.load_inputs()
d, rows = m.compute(v)

assert int(d["f71561_mother_person_lower_bound"]) == 122_494_621
assert int(d["out_of_mother_domestic_person_upper_bound"]) == 3_651_478
assert int(d["conditional_return_filer_overlap_lower"]) == 19_710_522
assert abs(d["conditional_stage1_filing_rate_lower"] - 0.15625153814704965) < 1e-14

by_prior = {r["prior"]: r for r in rows}
assert by_prior["score_power_2.0"][
    "conditional_rejected_without_untracked_contamination"
] is True
assert by_prior["score_power_1.0"][
    "conditional_rejected_without_untracked_contamination"
] is False
assert by_prior["score_power_0.5"][
    "conditional_rejected_without_untracked_contamination"
] is False
assert int(by_prior["score_power_2.0"][
    "additional_untracked_filers_needed_to_erase_rejection"
]) == 16_935_307

print("stage1 population-overlap tests: OK")
