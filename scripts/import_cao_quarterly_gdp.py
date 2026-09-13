"""Normalize Cabinet Office quarterly GDP raw inputs.

This parser intentionally accepts supplied raw files only.
It does not download external data.
"""

import csv
from pathlib import Path

from scripts.import_macro_gdp import annualize_growth


def normalize_rows(rows):
    for row in rows:
        yield {
            "quarter": row["quarter"],
            "real_gdp_growth_qoq": float(row["real_gdp_growth_qoq"]),
            "annualized_growth": annualize_growth(float(row["real_gdp_growth_qoq"])),
            "status": row.get("status", "observed"),
            "source_id": row["source_id"],
            "revision_date": row["revision_date"],
        }


def convert_csv(source: Path, output: Path):
    with source.open(newline="", encoding="utf-8") as src:
        rows = normalize_rows(csv.DictReader(src))
        with output.open("w", newline="", encoding="utf-8") as dst:
            writer = csv.DictWriter(dst, fieldnames=["quarter", "real_gdp_growth_qoq", "annualized_growth", "status", "source_id", "revision_date"])
            writer.writeheader()
            writer.writerows(rows)
