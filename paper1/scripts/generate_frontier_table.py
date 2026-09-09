#!/usr/bin/env python3
from pathlib import Path
import argparse
import csv
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "research/stage1_filing_bound/untracked_frontier_grid.csv"
OUTPUT = ROOT / "paper1/data/stage1_frontier_table.csv"


def build():
    with SOURCE.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    out = []
    for row in rows:
        c = float(row["C_U"])
        remaining = float(row["remaining_overlap_benchmark"])
        rate = float(row["robustness_rate_pct"])
        out.append([
            row["scenario"],
            f"{c:,.0f}",
            f"{remaining:,.0f}",
            f"{rate:.4f}%",
        ])
    return out


def render(rows):
    lines = [
        "Scenario,C_U persons,Remaining nominal overlap benchmark,"
        "Robustness rate"
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
            print("ERROR: stage1_frontier_table.csv is stale")
            sys.exit(1)
        print("paper1 frontier table: current")
        return
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
