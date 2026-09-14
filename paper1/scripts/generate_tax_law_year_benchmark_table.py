#!/usr/bin/env python3
from pathlib import Path
import argparse, csv, io

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "research/income_tax_partial_identification/tax_law_year_bridge_benchmark.csv"
OUTPUT = ROOT / "paper1/data/tax_law_year_benchmark_table.csv"


def read():
    with SOURCE.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pct(x):
    return f"{100.0 * float(x):.4f}%"


def pp(x):
    return f"{100.0 * float(x):.4f} pp"


def interval(r, lo, hi):
    return f"{100.0 * float(r[lo]):.4f}–{100.0 * float(r[hi]):.4f}%"


def build():
    rows = read()
    combos = {
        (int(r["tax_law_year"]), int(r["nuisance_calibration_tax_law_year"]))
        for r in rows
    }
    expected = {(2024, 2024), (2024, 2026), (2026, 2024), (2026, 2026)}
    if combos != expected:
        raise RuntimeError("tax-law 2x2 benchmark grid changed")
    out = []
    for r in sorted(
        rows,
        key=lambda x: (
            int(x["nuisance_calibration_tax_law_year"]),
            int(x["tax_law_year"]),
        ),
    ):
        out.append({
            "Tax law applied": r["tax_law_year"],
            "Nuisance scale calibrated under": r["nuisance_calibration_tax_law_year"],
            "Central mean pseudo positive-tax share": pct(r["central_equal_decile_mean_positive_share"]),
            "v2 minimum symmetric discrepancy": pp(r["v2_epsilon_star"]),
            "v3 minimum discrepancy at Delta=0.25": pp(r["v3_epsilon_star_delta_0p25"]),
            "v4 feasible fixed-budget points": f"{r['v4_feasible_grid_points_of_104']}/104",
            "v4 minimum feasible grid epsilon at Delta=0.25": pp(r["v4_min_feasible_grid_epsilon_delta_0p25"]),
            "v5 eta* at Delta=0": pp(r["v5_eta_star_delta_0"]),
            "v5 taxable-MTR envelope at Delta=0": interval(
                r, "v5_delta_0_taxable_mtr_min", "v5_delta_0_taxable_mtr_max"
            ),
        })
    return out


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
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            raise SystemExit("ERROR: tax_law_year_benchmark_table.csv is stale")
        print("paper1 tax-law-year 2x2 benchmark table: current")
    else:
        OUTPUT.write_text(expected, encoding="utf-8")
        print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
