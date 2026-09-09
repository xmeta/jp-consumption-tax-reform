#!/usr/bin/env python3
"""Generate the Paper 1 v5 one-sided bridge summary table."""
from pathlib import Path
import argparse
import csv
import io
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "research/income_tax_partial_identification"
FRONTIER = HERE / "rank_one_sided_bridge_v5_minimum_violation_frontier.csv"
ZERO = HERE / "rank_one_sided_bridge_v5_zero_violation_threshold.csv"
ENDPOINTS = HERE / "rank_one_sided_bridge_v5_endpoints.csv"
OUTPUT = ROOT / "paper1/data/rank_one_sided_v5_overall_table.csv"

DELTAS = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
STATUS = "MODEL_CONTINGENT_RANK_ONE_SIDED_SUBSET_COMPATIBILITY"
METRICS = (
    "taxable_income_weighted_mean_MTR",
    "income_tax_liability_weighted_mean_MTR",
)


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def interval(rows, metric):
    q = [r for r in rows if r["scope"] == "overall" and r["metric"] == metric]
    if len(q) != 2:
        raise RuntimeError(f"unexpected overall endpoint count for {metric}")
    vals = {r["bound"]: float(r["endpoint_value"]) for r in q}
    if set(vals) != {"min", "max"}:
        raise RuntimeError(f"missing min/max for {metric}")
    return f"{100.0 * vals['min']:.4f}–{100.0 * vals['max']:.4f}%"


def build():
    frontier = read(FRONTIER)
    zero = read(ZERO)
    endpoints = read(ENDPOINTS)

    if len(frontier) != 8:
        raise RuntimeError("unexpected v5 frontier row count")
    if len(zero) != 1:
        raise RuntimeError("unexpected v5 zero-threshold row count")
    if len(endpoints) != 672:
        raise RuntimeError("unexpected v5 endpoint row count")

    by_delta = {float(r["delta"]): r for r in frontier}
    if sorted(by_delta) != DELTAS:
        raise RuntimeError("v5 Delta grid changed")

    z = zero[0]
    if z["zero_violation_feasible"] != "True":
        raise RuntimeError("v5 zero directional violation is no longer feasible")
    if not math.isclose(float(z["delta_zero_star"]), 0.0, abs_tol=1e-12):
        raise RuntimeError("v5 zero-violation Delta anchor changed")
    if not math.isclose(
        float(z["solver_crosscheck_delta_zero_star"]), 0.0, abs_tol=1e-12
    ):
        raise RuntimeError("v5 zero-violation cross-check anchor changed")

    rows = []
    for delta in DELTAS:
        f = by_delta[delta]
        if f["spec_version"] != "rank_one_sided_bridge_v5":
            raise RuntimeError("unexpected v5 spec version")
        if f["scientific_status"] != STATUS:
            raise RuntimeError("unexpected v5 scientific status")
        eta = float(f["eta_star"])
        eta_cross = float(f["solver_crosscheck_eta_star"])
        if not math.isclose(eta, 0.0, abs_tol=1e-12):
            raise RuntimeError(f"v5 eta anchor changed at Delta={delta}: {eta}")
        if not math.isclose(eta_cross, eta, abs_tol=1e-12):
            raise RuntimeError(f"v5 solver cross-check changed at Delta={delta}")
        for flag in (
            "historical_v6_restricted_lp_reproduced",
            "p1c13_v1_modified",
            "p1c14_v2_modified",
            "p1c15_v3_modified",
            "p1c16_v4_modified",
        ):
            if f[flag] != "False":
                raise RuntimeError(f"v5 lineage flag changed: {flag}")

        q = [r for r in endpoints if math.isclose(float(r["delta"]), delta, abs_tol=1e-12)]
        if len(q) != 84:
            raise RuntimeError(f"unexpected v5 endpoint count at Delta={delta}")

        tax = interval(q, METRICS[0])
        liab = interval(q, METRICS[1])
        if tax != "10.0884–12.8680%":
            raise RuntimeError(f"v5 taxable MTR anchor changed at Delta={delta}: {tax}")
        if liab != "10.8806–13.7776%":
            raise RuntimeError(f"v5 liability MTR anchor changed at Delta={delta}: {liab}")

        rows.append({
            "Delta": f"{delta:g}",
            "minimum directional violation eta*": f"{100.0 * eta:.4f} pp",
            "taxable-income-weighted MTR envelope": tax,
            "income-tax-liability-weighted MTR envelope": liab,
        })

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
            print("ERROR: rank_one_sided_v5_overall_table.csv is stale")
            sys.exit(1)
        print("paper1 rank one-sided v5 overall table: current")
        return
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
