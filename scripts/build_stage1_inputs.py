#!/usr/bin/env python3
from pathlib import Path
import argparse
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "data/derived/stage1_official_inputs.csv"
RECOVERY = ROOT / "data/recovery/v6_recovered_values.csv"
CATALOG = ROOT / "data/source_catalog.csv"
OUTPUT = ROOT / "research/stage1_filing_bound/inputs.csv"

RECOVERY_IDS = {
    "threshold_score_power_0p5",
    "threshold_score_power_1p0",
    "threshold_score_power_2p0",
}


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_rows():
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    rows = []

    for r in read_csv(OFFICIAL):
        src = catalog[r["source_id"]]
        rows.append({
            "name": r["value_id"],
            "value": r["value"],
            "unit": r["unit"],
            "role": r["role"],
            "source": src["title"],
            "source_url": src["source_url"],
            "source_id": r["source_id"],
            "source_locator": r["source_locator"],
            "evidence_status": "RAW_OFFICIAL",
            "source_note": r["note"],
        })

    recovery = {r["value_id"]: r for r in read_csv(RECOVERY)}
    for value_id in sorted(RECOVERY_IDS):
        r = recovery[value_id]
        rows.append({
            "name": value_id,
            "value": r["value"],
            "unit": r["unit"],
            "role": "prior_threshold",
            "source": "Recovered V6 stage-1 threshold diagnostic",
            "source_url": "",
            "source_id": "RECOVERY-V6-2026-09-08",
            "source_locator": "data/recovery/v6_recovered_values.csv",
            "evidence_status": "RECOVERY_ONLY",
            "source_note": r["note"],
        })
    return rows


def render(rows):
    fields = [
        "name", "value", "unit", "role", "source", "source_url",
        "source_id", "source_locator", "evidence_status", "source_note",
    ]
    from io import StringIO
    buf = StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    expected = render(build_rows())
    if args.check:
        actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if actual != expected:
            print("ERROR: research/stage1_filing_bound/inputs.csv is stale")
            sys.exit(1)
        print("stage1 inputs: current")
        return

    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
