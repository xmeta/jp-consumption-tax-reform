#!/usr/bin/env python3
from pathlib import Path
import argparse
import csv
import sys

ROOT = Path(__file__).resolve().parents[2]
MINIMUM = (
    ROOT
    / "research/income_tax_partial_identification"
    / "rank_bridge_lp_v2_minimum_relaxation.csv"
)
ENDPOINTS = (
    ROOT
    / "research/income_tax_partial_identification"
    / "rank_bridge_lp_v2_endpoints.csv"
)
OUTPUT = ROOT / "paper1/data/rank_bridge_v2_summary_table.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def envelope(rows, metric):
    q = [
        r for r in rows
        if r["epsilon_source"] == "epsilon_star"
        and r["scope"] == "overall"
        and r["metric"] == metric
    ]
    vals = {r["bound"]: float(r["endpoint_value"]) for r in q}
    if set(vals) != {"min", "max"}:
        raise RuntimeError(f"missing v2 epsilon-star envelope for {metric}")
    return vals["min"], vals["max"]


def build():
    m = read(MINIMUM)
    if len(m) != 1:
        raise RuntimeError("v2 minimum relaxation must have one row")
    r = m[0]
    if r["spec_version"] != "rank_bridge_lp_v2":
        raise RuntimeError("unexpected v2 spec version")
    if r["scientific_status"] != "MODEL_CONTINGENT_RANK_BRIDGE_RELAXATION":
        raise RuntimeError("unexpected v2 scientific status")
    if r["historical_v6_restricted_lp_reproduced"] != "False":
        raise RuntimeError("historical V6 must remain unreproduced")
    if r["p1c13_v1_modified"] != "False":
        raise RuntimeError("v1 must remain unchanged")

    endpoints = read(ENDPOINTS)
    tax_lo, tax_hi = envelope(
        endpoints, "taxable_income_weighted_mean_MTR"
    )
    liab_lo, liab_hi = envelope(
        endpoints, "income_tax_liability_weighted_mean_MTR"
    )
    eps = float(r["epsilon_star"])

    return [[
        "Same-rank decile",
        f"{eps * 100:.4f} pp",
        f"{tax_lo * 100:.4f}%–{tax_hi * 100:.4f}%",
        f"{liab_lo * 100:.4f}%–{liab_hi * 100:.4f}%",
    ]]


def render(rows):
    lines = [
        "Bridge scheme,Minimum common relaxation epsilon2*,"
        "Overall taxable-income-weighted MTR envelope at epsilon2*,"
        "Overall liability-weighted MTR envelope at epsilon2*"
    ]
    for row in rows:
        escaped = []
        for cell in row:
            if "," in cell or '"' in cell:
                cell = '"' + cell.replace('"', '""') + '"'
            escaped.append(cell)
        lines.append(",".join(escaped))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    expected = render(build())
    if args.check:
        actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if actual != expected:
            print("ERROR: rank_bridge_v2_summary_table.csv is stale")
            sys.exit(1)
        print("paper1 rank-bridge v2 table: current")
        return

    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
