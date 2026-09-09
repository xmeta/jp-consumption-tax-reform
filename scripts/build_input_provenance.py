#!/usr/bin/env python3
from pathlib import Path
import argparse
import csv
import sys
from io import StringIO

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "data/derived/stage1_official_inputs.csv"
RECOVERY = ROOT / "data/recovery/v6_recovered_values.csv"
CATALOG = ROOT / "data/source_catalog.csv"
OUTPUT = ROOT / "data/input_provenance.csv"

RECOVERY_STAGE1_IDS = {
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
            "value_id": r["value_id"],
            "value": r["value"],
            "unit": r["unit"],
            "evidence_status": "RAW_OFFICIAL",
            "source_id": r["source_id"],
            "source_file": src["raw_file"],
            "source_sha256": src["sha256"],
            "source_url": src["source_url"],
            "source_locator": r["source_locator"],
            "extraction_method": r["extraction_method"],
            "derived_artifact": "research/stage1_filing_bound/inputs.csv",
            "claim_ids": r["claim_ids"],
            "note": r["note"],
        })

    for r in read_csv(RECOVERY):
        if r["value_id"] not in RECOVERY_STAGE1_IDS:
            continue
        rows.append({
            "value_id": r["value_id"],
            "value": r["value"],
            "unit": r["unit"],
            "evidence_status": "RECOVERY_ONLY",
            "source_id": "RECOVERY-V6-2026-09-08",
            "source_file": "data/recovery/v6_recovered_values.csv",
            "source_sha256": r["source_artifact_sha256"],
            "source_url": "",
            "source_locator":
                "recovered V6 artifact; generating source chain not restored",
            "extraction_method": "recovered_value_transcription",
            "derived_artifact": "research/stage1_filing_bound/inputs.csv",
            "claim_ids": "P1-C09",
            "note": r["note"],
        })
    return rows


def render(rows):
    fields = [
        "value_id", "value", "unit", "evidence_status", "source_id",
        "source_file", "source_sha256", "source_url", "source_locator",
        "extraction_method", "derived_artifact", "claim_ids", "note",
    ]
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
            print("ERROR: data/input_provenance.csv is stale")
            sys.exit(1)
        print("input provenance: current")
        return

    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
