#!/usr/bin/env python3
"""Generate the Paper 1 v3 rank-transport discrepancy frontier table."""
from pathlib import Path
import argparse
import csv
import io
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "research/income_tax_partial_identification"
FRONTIER = HERE / "rank_bridge_lp_v3_minimum_relaxation_frontier.csv"
ANALYTIC = HERE / "rank_bridge_lp_v3_analytical_rate_floor.csv"
ZERO = HERE / "rank_bridge_lp_v3_zero_discrepancy_threshold.csv"
OUTPUT = ROOT / "paper1/data/rank_bridge_v3_frontier_table.csv"

EXPECTED_DELTAS = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
STATUS = "MODEL_CONTINGENT_RANK_TRANSPORT_BUDGET"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build():
    frontier = read(FRONTIER)
    analytic = read(ANALYTIC)
    zero = read(ZERO)

    if len(frontier) != len(EXPECTED_DELTAS):
        raise RuntimeError("unexpected v3 frontier row count")
    if [float(r["delta"]) for r in frontier] != EXPECTED_DELTAS:
        raise RuntimeError("v3 delta grid changed")
    if len(analytic) != 1 or len(zero) != 1:
        raise RuntimeError("unexpected v3 analytical/zero-discrepancy rows")

    for r in frontier:
        if r["spec_version"] != "rank_bridge_lp_v3":
            raise RuntimeError("unexpected v3 spec version")
        if r["scientific_status"] != STATUS:
            raise RuntimeError("unexpected v3 scientific status")
        for flag in (
            "historical_v6_restricted_lp_reproduced",
            "p1c13_v1_modified",
            "p1c14_v2_modified",
        ):
            if r[flag] != "False":
                raise RuntimeError(f"v3 lineage flag changed: {flag}")

    a = analytic[0]
    if a["scientific_status"] != STATUS:
        raise RuntimeError("unexpected analytical-floor status")
    floor = float(a["unrestricted_nonnegative_rate_floor"])
    simple = float(a["simple_average_gap_floor"])

    z = zero[0]
    if z["zero_discrepancy_feasible"] != "False":
        raise RuntimeError("zero-discrepancy result changed")
    if z["delta_zero_star"]:
        raise RuntimeError("zero-discrepancy delta must be blank when infeasible")

    eps0 = float(frontier[0]["epsilon_star"])
    rows = []
    for r in frontier:
        delta = float(r["delta"])
        eps = float(r["epsilon_star"])
        rows.append({
            "Rank-displacement budget Delta (decile units)": f"{delta:g}",
            "Equivalent average percentile-rank displacement cap": (
                f"{10.0 * delta:.1f} pp"
            ),
            "Minimum common discrepancy epsilon3*(Delta)": f"{100.0 * eps:.4f} pp",
            "Reduction from Delta=0": f"{100.0 * (eps0 - eps):.4f} pp",
            "Minimum discrepancy equals unrestricted nonnegative-rate floor": (
                "Yes" if math.isclose(eps, floor, abs_tol=5e-10) else "No"
            ),
        })

    # Defensive anchors used in prose, but generated from research outputs.
    if not math.isclose(eps0, 0.149015979543, abs_tol=5e-10):
        raise RuntimeError("v3 delta=0 no longer reproduces v2 anchor")
    if not math.isclose(float(frontier[1]["epsilon_star"]), floor, abs_tol=5e-10):
        raise RuntimeError("first positive delta no longer attains analytical floor")
    if not all(
        math.isclose(float(r["epsilon_star"]), floor, abs_tol=5e-10)
        for r in frontier[1:]
    ):
        raise RuntimeError("v3 post-0 frontier is no longer flat at the floor")
    if not math.isclose(floor, 0.0868252768522, abs_tol=5e-10):
        raise RuntimeError("analytical floor changed")
    if not math.isclose(simple, 0.0866905432847, abs_tol=5e-10):
        raise RuntimeError("simple aggregate floor changed")

    return rows


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    expected = render(build())
    if args.check:
        actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if actual != expected:
            print("ERROR: rank_bridge_v3_frontier_table.csv is stale")
            sys.exit(1)
        print("paper1 rank-transport v3 frontier table: current")
        return

    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
