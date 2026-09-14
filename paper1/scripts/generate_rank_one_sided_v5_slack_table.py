#!/usr/bin/env python3
"""Generate Paper 1 tables for the post-result v5 slack diagnostic."""
from pathlib import Path
import argparse
import csv
import io
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "research/income_tax_partial_identification"
SUMMARY = HERE / "rank_one_sided_bridge_v5_slack_summary.csv"
BOUNDS = HERE / "rank_one_sided_bridge_v5_slack_bounds.csv"
WITNESS = HERE / "rank_one_sided_bridge_v5_minimum_decile_diagnostics.csv"
OUT_SUMMARY = ROOT / "paper1/data/rank_one_sided_v5_slack_summary_table.csv"
OUT_SAME_RANK = ROOT / "paper1/data/rank_one_sided_v5_slack_same_rank_table.csv"
DELTAS = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pp(value):
    return f"{100.0 * float(value):.4f} pp"


def render(rows):
    b = io.StringIO()
    writer = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return b.getvalue()


def build():
    summary = read(SUMMARY)
    bounds = read(BOUNDS)
    witness = read(WITNESS)
    if len(summary) != 8 or len(bounds) != 80 or len(witness) != 80:
        raise RuntimeError("unexpected v5 slack diagnostic row count")
    if [float(r["delta"]) for r in summary] != DELTAS:
        raise RuntimeError("v5 slack Delta grid changed")

    summary_rows = []
    for r in summary:
        if not math.isclose(float(r["eta_star"]), 0.0, abs_tol=1e-12):
            raise RuntimeError("v5 eta*=0 anchor changed")
        summary_rows.append({
            "Delta": f"{float(r['delta']):g}",
            "witness slack min / median / max": (
                f"{pp(r['witness_slack_minimum'])} / "
                f"{pp(r['witness_slack_median'])} / "
                f"{pp(r['witness_slack_maximum'])}"
            ),
            "witness binding / near-binding deciles": (
                f"{r['witness_binding_count']} / {r['witness_near_binding_count']}"
            ),
            "deciles that can bind": r["feasible_set_can_bind_decile_count"],
            "deciles that must bind": r["feasible_set_must_bind_decile_count"],
        })

    same_bounds = {
        int(r["decile"]): r
        for r in bounds
        if math.isclose(float(r["delta"]), 0.0, abs_tol=1e-12)
    }
    same_witness = {
        int(r["decile"]): r
        for r in witness
        if math.isclose(float(r["delta"]), 0.0, abs_tol=1e-12)
    }
    if len(same_bounds) != 10 or len(same_witness) != 10:
        raise RuntimeError("exact-rank slack rows missing")

    same_rank_rows = []
    for d in range(1, 11):
        b = same_bounds[d]
        w = same_witness[d]
        witness_slack = -float(w["directional_violation_transported_minus_pseudo"])
        same_rank_rows.append({
            "Decile": d,
            "one-witness slack": pp(witness_slack),
            "feasible-set slack range": (
                f"{pp(b['slack_minimum_over_fixed_frontier_set'])}–"
                f"{pp(b['slack_maximum_over_fixed_frontier_set'])}"
            ),
            "can bind": b["can_bind"],
            "must bind": b["must_bind"],
        })

    return summary_rows, same_rank_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    summary_rows, same_rank_rows = build()
    outputs = (
        (OUT_SUMMARY, render(summary_rows)),
        (OUT_SAME_RANK, render(same_rank_rows)),
    )
    if args.check:
        stale = [
            str(path.relative_to(ROOT))
            for path, expected in outputs
            if (path.read_text(encoding="utf-8") if path.exists() else "") != expected
        ]
        if stale:
            print("ERROR: stale Paper 1 v5 slack tables: " + ", ".join(stale))
            sys.exit(1)
        print("paper1 rank one-sided v5 slack tables: current")
        return
    for path, expected in outputs:
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
