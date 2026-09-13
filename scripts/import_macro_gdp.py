"""Prepare quarterly GDP import pipeline for Issue #121.

The importer intentionally does not download or transform external sources yet.
Source-specific parsers should be added only after the authoritative source
format is fixed.
"""

from pathlib import Path


REQUIRED_COLUMNS = [
    "quarter",
    "real_gdp_growth_qoq",
    "annualized_growth",
    "status",
    "source_id",
    "revision_date",
]


def validate_schema(path: Path) -> None:
    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise ValueError(f"missing columns: {missing}")


if __name__ == "__main__":
    validate_schema(Path("data/macro/real_gdp_quarterly.csv"))
    print("macro GDP schema OK")
