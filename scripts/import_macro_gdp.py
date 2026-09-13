"""Normalize quarterly real GDP inputs for Issue #123.

This module intentionally works on supplied raw files. It does not download
external data. Raw source acquisition remains a provenance step.
"""

from pathlib import Path


REQUIRED_COLUMNS = [
    "quarter",
    "real_gdp_growth_qoq",
    "status",
    "source_id",
    "revision_date",
]

OUTPUT_COLUMNS = [
    "quarter",
    "real_gdp_growth_qoq",
    "annualized_growth",
    "status",
    "source_id",
    "revision_date",
]


def annualize_growth(qoq: float) -> float:
    return (1.0 + qoq) ** 4 - 1.0


def validate_schema(path: Path) -> None:
    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise ValueError(f"missing columns: {missing}")


if __name__ == "__main__":
    validate_schema(Path("data/macro/real_gdp_quarterly.csv"))
    print("macro GDP schema OK")
