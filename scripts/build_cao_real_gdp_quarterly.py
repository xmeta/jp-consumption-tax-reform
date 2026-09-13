#!/usr/bin/env python3
"""Build normalized quarterly real GDP growth data from the latest archived CAO QE CSV."""

from __future__ import annotations

import csv
from pathlib import Path

SOURCE_ID = "ESRI-QE-2026Q2-2-REAL-QOQ"
REVISION_DATE = "2026-09-08"
SOURCE = Path("data/raw/esri/cao_real_gdp_qoq_2026_q2_second_prelim.csv")
OUTPUT = Path("data/macro/real_gdp_quarterly.csv")


def parse_quarter(label: str) -> str:
    year, month = label.strip(".").split("/")
    quarter = {"1- 3": 1, "4- 6": 2, "7- 9": 3, "10-12": 4}[month.strip()]
    return f"{int(year)}-Q{quarter}"


def build_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    current_year: int | None = None
    with SOURCE.open(encoding="cp932", newline="") as f:
        for raw in csv.reader(f):
            if not raw or not raw[0].strip():
                continue
            first = raw[0].strip()
            if "/" in first:
                year_text = first.split("/", 1)[0]
                if not year_text.isdigit():
                    continue
                current_year = int(year_text)
                label = first
            elif current_year is not None and first.rstrip(".") in {"4- 6", "7- 9", "10-12"}:
                label = f"{current_year}/{first}"
            else:
                continue

            quarter = parse_quarter(label)
            value = raw[1].strip() if len(raw) > 1 else ""
            if not value or value == "***":
                rows.append({
                    "quarter": quarter,
                    "real_gdp_growth_qoq": "",
                    "annualized_growth": "",
                    "status": "source_baseline_no_qoq",
                    "source_id": SOURCE_ID,
                    "revision_date": REVISION_DATE,
                })
                continue

            qoq = float(value) / 100.0
            rows.append({
                "quarter": quarter,
                "real_gdp_growth_qoq": qoq,
                "annualized_growth": (1.0 + qoq) ** 4 - 1.0,
                "status": "observed",
                "source_id": SOURCE_ID,
                "revision_date": REVISION_DATE,
            })
    return rows


def validate_rows(rows: list[dict[str, object]]) -> None:
    if len(rows) != 130 or rows[0]["quarter"] != "1994-Q1" or rows[-1]["quarter"] != "2026-Q2":
        raise RuntimeError("unexpected CAO quarterly coverage")
    if rows[0]["status"] != "source_baseline_no_qoq" or rows[0]["real_gdp_growth_qoq"] != "":
        raise RuntimeError("1994-Q1 must preserve the publisher's missing QoQ baseline")
    if sum(row["status"] == "observed" for row in rows) != 129:
        raise RuntimeError("expected 129 observed QoQ rates after the 1994-Q1 baseline row")
    if any(row["source_id"] != SOURCE_ID or row["revision_date"] != REVISION_DATE for row in rows):
        raise RuntimeError("GDP provenance fields are incomplete")


def main() -> None:
    rows = build_rows()
    validate_rows(rows)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUTPUT}: {len(rows)} rows ({sum(r['status'] == 'observed' for r in rows)} observed)")


if __name__ == "__main__":
    main()
