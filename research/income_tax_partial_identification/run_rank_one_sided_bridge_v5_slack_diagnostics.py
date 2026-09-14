#!/usr/bin/env python3
"""Post-result slack diagnostics for the frozen rank one-sided bridge v5.

The v5 pre-specification is intentionally left unchanged. This diagnostic
examines how informative eta*=0 is by bounding each decile constraint slack
across the full fixed-(Delta, eta*) feasible set, rather than interpreting the
binding pattern of one non-unique solver witness as structural.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import io
import math
import statistics
import sys

import numpy as np

import run_rank_bridge_lp_v3 as v3
import run_rank_one_sided_bridge_v5 as v5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FRONTIER = HERE / "rank_one_sided_bridge_v5_minimum_violation_frontier.csv"
WITNESS = HERE / "rank_one_sided_bridge_v5_minimum_decile_diagnostics.csv"
OUT_BOUNDS = HERE / "rank_one_sided_bridge_v5_slack_bounds.csv"
OUT_SUMMARY = HERE / "rank_one_sided_bridge_v5_slack_summary.csv"

NEAR_BINDING_THRESHOLD = 1e-4  # rate units = 0.01 percentage point


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def fmt(value) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    value = float(value)
    if math.isnan(value):
        return ""
    return f"{value:.12g}"


def render(rows: list[dict]) -> str:
    if not rows:
        raise RuntimeError("cannot render empty slack diagnostics")
    b = io.StringIO()
    writer = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: fmt(v) for k, v in row.items()})
    return b.getvalue()


def slack_objective(model: v3.Model, decile_index: int) -> np.ndarray:
    """Return c with c'x = r_PF - r_B for one decile."""
    data = model.data
    c = np.zeros(model.nvars)
    for si in range(len(data.scenarios)):
        c[model.lambda_index[(decile_index, si)]] = data.u[decile_index, si]
    for qi in range(len(data.deciles)):
        c[model.z_index[(decile_index, qi)]] = -10.0
    return c


def build_outputs() -> tuple[list[dict], list[dict]]:
    cfg = v5.read_config()
    eq_tol = float(cfg["equality_residual_tolerance"])
    ineq_tol = float(cfg["inequality_residual_tolerance"])
    binding_tol = ineq_tol
    deltas = v5.delta_grid(cfg)
    data = v3.load_data(cfg)

    frontier = read_csv(FRONTIER)
    witness = read_csv(WITNESS)
    if len(frontier) != len(deltas):
        raise RuntimeError("unexpected v5 frontier row count")
    if len(witness) != len(deltas) * len(data.deciles):
        raise RuntimeError("unexpected v5 witness row count")

    frontier_by_delta = {float(r["delta"]): r for r in frontier}
    witness_by_delta = {
        delta: [r for r in witness if math.isclose(float(r["delta"]), delta, abs_tol=1e-12)]
        for delta in deltas
    }

    bounds_rows: list[dict] = []
    summary_rows: list[dict] = []

    for delta in deltas:
        frow = frontier_by_delta[delta]
        eta_star = float(frow["eta_star"])
        model = v3.make_model(data, include_epsilon=False)

        delta_bounds = []
        for di, decile in enumerate(data.deciles):
            c = slack_objective(model, di)
            solved = {}
            for bound, sign in (("min", 1.0), ("max", -1.0)):
                res = v5.solve_lp(
                    model,
                    sign * c,
                    delta=delta,
                    eta=eta_star,
                    method=cfg["solver_method"],
                )
                if not res.success:
                    raise RuntimeError(
                        f"slack {bound} solve failed delta={delta} decile={decile}: "
                        f"{res.status} {res.message}"
                    )
                diag = v5.diagnostics(model, res.x, delta, eta_star)
                v5.assert_solution(diag, eq_tol, ineq_tol)
                value = eta_star + float(np.dot(c, res.x))
                if value < -binding_tol:
                    raise RuntimeError(
                        f"negative slack beyond tolerance delta={delta} decile={decile}: {value}"
                    )
                solved[bound] = max(0.0, value)

            slack_min = solved["min"]
            slack_max = solved["max"]
            if slack_min > slack_max + binding_tol:
                raise RuntimeError(
                    f"slack bounds inverted delta={delta} decile={decile}: "
                    f"{slack_min} > {slack_max}"
                )
            can_bind = slack_min <= binding_tol
            must_bind = slack_max <= binding_tol
            can_near_bind = slack_min <= NEAR_BINDING_THRESHOLD
            must_near_bind = slack_max <= NEAR_BINDING_THRESHOLD
            row = {
                "spec_version": v5.SPEC_VERSION,
                "diagnostic_version": "rank_one_sided_bridge_v5_slack_v1",
                "delta": delta,
                "eta_star": eta_star,
                "decile": decile,
                "slack_definition": "eta_star_plus_pseudo_rate_minus_transported_positive_balance_rate",
                "slack_minimum_over_fixed_frontier_set": slack_min,
                "slack_maximum_over_fixed_frontier_set": slack_max,
                "binding_tolerance_rate": binding_tol,
                "near_binding_threshold_rate": NEAR_BINDING_THRESHOLD,
                "can_bind": can_bind,
                "must_bind": must_bind,
                "can_near_bind": can_near_bind,
                "must_near_bind": must_near_bind,
                "interpretation": (
                    "bounds are over the full fixed-(Delta,eta*) feasible set; "
                    "binding at one solver witness is not structural when the optimum is non-unique"
                ),
                "scientific_status": v5.STATUS,
            }
            bounds_rows.append(row)
            delta_bounds.append(row)

        witness_rows = witness_by_delta[delta]
        if len(witness_rows) != len(data.deciles):
            raise RuntimeError(f"missing witness deciles at delta={delta}")
        witness_slack = []
        for r in witness_rows:
            directional = float(r["directional_violation_transported_minus_pseudo"])
            slack = eta_star - directional
            if slack < -binding_tol:
                raise RuntimeError(f"witness slack negative at delta={delta}: {slack}")
            witness_slack.append(max(0.0, slack))

        summary_rows.append({
            "spec_version": v5.SPEC_VERSION,
            "diagnostic_version": "rank_one_sided_bridge_v5_slack_v1",
            "delta": delta,
            "eta_star": eta_star,
            "witness_slack_minimum": min(witness_slack),
            "witness_slack_median": statistics.median(witness_slack),
            "witness_slack_maximum": max(witness_slack),
            "witness_binding_count": sum(x <= binding_tol for x in witness_slack),
            "witness_near_binding_count": sum(x <= NEAR_BINDING_THRESHOLD for x in witness_slack),
            "feasible_set_can_bind_decile_count": sum(r["can_bind"] for r in delta_bounds),
            "feasible_set_must_bind_decile_count": sum(r["must_bind"] for r in delta_bounds),
            "feasible_set_can_near_bind_decile_count": sum(r["can_near_bind"] for r in delta_bounds),
            "feasible_set_must_near_bind_decile_count": sum(r["must_near_bind"] for r in delta_bounds),
            "minimum_decile_slack_lower_bound": min(
                float(r["slack_minimum_over_fixed_frontier_set"]) for r in delta_bounds
            ),
            "maximum_decile_slack_upper_bound": max(
                float(r["slack_maximum_over_fixed_frontier_set"]) for r in delta_bounds
            ),
            "binding_tolerance_rate": binding_tol,
            "near_binding_threshold_rate": NEAR_BINDING_THRESHOLD,
            "witness_note": (
                "witness statistics describe the committed one-frontier-optimum diagnostic only; "
                "use feasible-set can_bind/must_bind counts for solution-invariant interpretation"
            ),
            "scientific_status": v5.STATUS,
        })

    return bounds_rows, summary_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    bounds_rows, summary_rows = build_outputs()
    outputs = ((OUT_BOUNDS, bounds_rows), (OUT_SUMMARY, summary_rows))

    if args.check:
        stale = []
        for path, rows in outputs:
            expected = render(rows)
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if expected != actual:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            print("ERROR: stale v5 slack diagnostics: " + ", ".join(stale))
            sys.exit(1)
        print("rank one-sided bridge v5 slack diagnostics: current")
        return

    for path, rows in outputs:
        path.write_text(render(rows), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
