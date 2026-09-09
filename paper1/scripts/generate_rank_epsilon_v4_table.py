#!/usr/bin/env python3
"""Generate the Paper 1 v4 fixed-budget overall-MTR surface table."""
from pathlib import Path
import argparse
import csv
import io
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "research/income_tax_partial_identification"
SUMMARY = HERE / "rank_epsilon_surface_v4_summary.csv"
ENDPOINTS = HERE / "rank_epsilon_surface_v4_endpoints.csv"
OUTPUT = ROOT / "paper1/data/rank_epsilon_v4_overall_table.csv"

EPSILONS = [
    0.0, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15,
    0.175, 0.20, 0.225, 0.25, 0.275, 0.30,
]
POSITIVE_DELTAS = [0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
STATUS = "MODEL_CONTINGENT_RANK_EPSILON_SURFACE"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def as_bool(x):
    if x not in {"True", "False"}:
        raise RuntimeError(f"unexpected boolean {x!r}")
    return x == "True"


def interval(row, prefix):
    lo = float(row[f"{prefix}_min"])
    hi = float(row[f"{prefix}_max"])
    return f"{100.0 * lo:.4f}–{100.0 * hi:.4f}%"


def same_bounds(rows, prefix, tol=5e-10):
    vals = [
        (
            float(r[f"{prefix}_min"]),
            float(r[f"{prefix}_max"]),
        )
        for r in rows
    ]
    a = vals[0]
    return all(
        math.isclose(x[0], a[0], abs_tol=tol)
        and math.isclose(x[1], a[1], abs_tol=tol)
        for x in vals
    )


def build():
    summary = read(SUMMARY)
    endpoints = read(ENDPOINTS)
    if len(summary) != 104:
        raise RuntimeError("unexpected v4 summary row count")
    if len(endpoints) != 5880:
        raise RuntimeError("unexpected v4 endpoint row count")
    if sum(as_bool(r["feasible"]) for r in summary) != 70:
        raise RuntimeError("unexpected v4 feasible-point count")

    for r in summary:
        if r["spec_version"] != "rank_epsilon_surface_v4":
            raise RuntimeError("unexpected v4 spec version")
        if r["scientific_status"] != STATUS:
            raise RuntimeError("unexpected v4 scientific status")
        for flag in (
            "historical_v6_restricted_lp_reproduced",
            "p1c13_v1_modified",
            "p1c14_v2_modified",
            "p1c15_v3_modified",
        ):
            if r[flag] != "False":
                raise RuntimeError(f"v4 lineage flag changed: {flag}")

    by = {
        (float(r["delta"]), float(r["epsilon"])): r
        for r in summary
    }
    rows = []
    for epsilon in EPSILONS:
        d0 = by[(0.0, epsilon)]
        pos = [by[(d, epsilon)] for d in POSITIVE_DELTAS]

        pos_feasible = [as_bool(r["feasible"]) for r in pos]
        if len(set(pos_feasible)) != 1:
            raise RuntimeError(
                f"positive-Delta feasibility differs at epsilon={epsilon}"
            )

        if pos_feasible[0]:
            if not same_bounds(pos, "overall_taxable_mtr"):
                raise RuntimeError(
                    f"positive-Delta taxable MTR bounds differ at epsilon={epsilon}"
                )
            if not same_bounds(pos, "overall_liability_mtr"):
                raise RuntimeError(
                    f"positive-Delta liability MTR bounds differ at epsilon={epsilon}"
                )
            pos_status = "feasible; identical across Delta=0.25,...,5"
            pos_tax = interval(pos[0], "overall_taxable_mtr")
            pos_liab = interval(pos[0], "overall_liability_mtr")
        else:
            pos_status = "infeasible at all Delta=0.25,...,5"
            pos_tax = ""
            pos_liab = ""

        if as_bool(d0["feasible"]):
            d0_status = "feasible"
            d0_tax = interval(d0, "overall_taxable_mtr")
            d0_liab = interval(d0, "overall_liability_mtr")
        else:
            d0_status = "infeasible"
            d0_tax = ""
            d0_liab = ""

        rows.append({
            "epsilon": f"{epsilon:g}",
            "Delta=0 status": d0_status,
            "Delta=0 taxable-weighted MTR envelope": d0_tax,
            "Delta=0 liability-weighted MTR envelope": d0_liab,
            "Delta=0.25,...,5 status": pos_status,
            "Delta=0.25,...,5 taxable-weighted MTR envelope": pos_tax,
            "Delta=0.25,...,5 liability-weighted MTR envelope": pos_liab,
        })

    # Defensive anchors for prose.
    r010 = by[(0.25, 0.10)]
    if interval(r010, "overall_taxable_mtr") != "10.5552–11.7415%":
        raise RuntimeError("v4 epsilon=0.10 taxable anchor changed")
    if interval(r010, "overall_liability_mtr") != "11.4432–12.6219%":
        raise RuntimeError("v4 epsilon=0.10 liability anchor changed")
    r030 = by[(0.25, 0.30)]
    if interval(r030, "overall_taxable_mtr") != "10.0884–12.8680%":
        raise RuntimeError("v4 epsilon=0.30 taxable anchor changed")
    if interval(r030, "overall_liability_mtr") != "10.8806–13.7776%":
        raise RuntimeError("v4 epsilon=0.30 liability anchor changed")

    # Every feasible surface point must retain nonzero overall MTR width.
    for r in summary:
        if not as_bool(r["feasible"]):
            continue
        if float(r["overall_taxable_mtr_width"]) <= 0:
            raise RuntimeError("zero taxable MTR width at feasible v4 point")
        if float(r["overall_liability_mtr_width"]) <= 0:
            raise RuntimeError("zero liability MTR width at feasible v4 point")

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
            print("ERROR: rank_epsilon_v4_overall_table.csv is stale")
            sys.exit(1)
        print("paper1 rank-epsilon v4 overall table: current")
        return

    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
