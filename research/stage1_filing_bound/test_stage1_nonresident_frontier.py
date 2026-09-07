#!/usr/bin/env python3
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "frontier48",
    HERE / "48_income_tax_stage1_nonresident_frontier.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

v = m.frontier47.overlap.load_inputs()
summary, rows = m.compute(v)

assert int(summary[
    "conditional_overlap_before_tracked_contamination"
]) == 19_438_597
assert int(summary["tracked_contamination_upper"]) == 8_085_259
assert int(summary["residual_numerator_at_C_NR_0"]) == 11_353_338
assert abs(summary["lower_bound_at_C_NR_0"] - 0.09000149897619902) < 1e-14

by_prior = {r["prior"]: r for r in rows}
r2 = by_prior["score_power_2.0"]
assert int(r2["critical_C_NR_strict"]) == 8_578_123
assert abs(
    r2["critical_C_NR_share_of_candidate_upper"]
    - 0.06800149897619902
) < 1e-14
assert r2["rejection_rule"] == "reject_if_C_NR_below_critical"

for prior in ("score_power_0.5", "score_power_1.0"):
    assert by_prior[prior]["critical_C_NR_strict"] == 0.0
    assert by_prior[prior]["rejection_rule"] == (
        "not_rejected_even_at_C_NR_0"
    )

p = summary["candidate_person_upper"]
n0 = summary["residual_numerator_at_C_NR_0"]
assert m.lower_bound(0, n0, p) > 0.022
assert abs(m.lower_bound(r2["critical_C_NR_strict"], n0, p) - 0.022) < 1e-14
assert m.lower_bound(r2["critical_C_NR_strict"] + 1, n0, p) < 0.022

print("stage1 nonresident-frontier tests: OK")
