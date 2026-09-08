#!/usr/bin/env python3
from pathlib import Path
import argparse
import csv
import sys

ROOT = Path(__file__).resolve().parents[2]
MINIMUM = (
    ROOT
    / "research/income_tax_partial_identification"
    / "replacement_transport_lp_minimum_relaxation.csv"
)
ENDPOINTS = (
    ROOT
    / "research/income_tax_partial_identification"
    / "replacement_transport_lp_endpoints.csv"
)
OUTPUT = ROOT / "paper1/data/transport_lp_summary_table.csv"

LABELS = {
    "equal_decile": "Equal decile",
    "f71561_leaf_count_normalized": "F71561 leaf-count normalized",
}


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def envelope(rows, scheme, metric):
    q = [
        r for r in rows
        if r["weight_scheme"] == scheme
        and r["epsilon_source"] == "epsilon_star"
        and r["scope"] == "overall"
        and r["metric"] == metric
    ]
    vals = {r["bound"]: float(r["endpoint_value"]) for r in q}
    if set(vals) != {"min", "max"}:
        raise RuntimeError(
            f"missing epsilon-star overall envelope: {scheme} {metric}"
        )
    return vals["min"], vals["max"]


def build():
    minimum = read(MINIMUM)
    endpoints = read(ENDPOINTS)
    by_scheme = {r["weight_scheme"]: r for r in minimum}
    if set(by_scheme) != set(LABELS):
        raise RuntimeError(
            f"unexpected weight schemes: {sorted(by_scheme)}"
        )

    out = []
    for scheme in ["equal_decile", "f71561_leaf_count_normalized"]:
        eps = float(by_scheme[scheme]["epsilon_star"])
        tax_lo, tax_hi = envelope(
            endpoints, scheme, "taxable_income_weighted_mean_MTR"
        )
        liab_lo, liab_hi = envelope(
            endpoints, scheme, "income_tax_liability_weighted_mean_MTR"
        )
        out.append([
            LABELS[scheme],
            f"{eps * 100:.4f} pp",
            f"{tax_lo * 100:.4f}%–{tax_hi * 100:.4f}%",
            f"{liab_lo * 100:.4f}%–{liab_hi * 100:.4f}%",
        ])
    return out


def render(rows):
    lines = [
        "Weight scheme,Minimum common relaxation epsilon*,"
        "Overall taxable-income-weighted MTR envelope at epsilon*,"
        "Overall liability-weighted MTR envelope at epsilon*"
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
            print("ERROR: transport_lp_summary_table.csv is stale")
            sys.exit(1)
        print("paper1 transport-LP table: current")
        return

    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
