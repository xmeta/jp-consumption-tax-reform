#!/usr/bin/env python3
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "frontier",
    HERE / "47_income_tax_stage1_contamination_frontier.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

v = m.overlap.load_inputs()
summary, rows = m.compute(v)

assert int(summary["births_2020_2024_upper"]) == 3_836_677
assert int(summary["international_inflows_2020_2024_upper"]) == 2_643_204
assert int(summary["quasi_final_death_upper_2024"]) == 1_605_378
assert int(summary["tracked_contamination_upper"]) == 8_085_259

by_prior = {r["prior"]: r for r in rows}
r2 = by_prior["score_power_2.0"]
assert int(r2["total_break_even_contamination"]) == 16_935_307
assert int(r2["residual_unresolved_contamination_to_erase_rejection"]) == 8_850_048
assert abs(
    r2["residual_share_of_candidate_upper"] - 0.07015713440333973
) < 1e-14

assert by_prior["score_power_1.0"][
    "residual_unresolved_contamination_to_erase_rejection"
] == 0.0
assert by_prior["score_power_0.5"][
    "residual_unresolved_contamination_to_erase_rejection"
] == 0.0

print("stage1 contamination-frontier tests: OK")
