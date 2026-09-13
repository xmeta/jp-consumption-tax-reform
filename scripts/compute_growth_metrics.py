"""Compute macro growth diagnostics for Issue #121.

This module intentionally keeps observed data handling separate from policy
simulation. It will compute reproducible diagnostics once the GDP dataset is
populated.
"""

from __future__ import annotations

import csv
from pathlib import Path


def annualize_qoq(rate: float) -> float:
    """Convert quarterly growth rate to annualized growth rate."""
    return (1.0 + rate) ** 4 - 1.0


def main() -> None:
    path = Path("data/macro/real_gdp_quarterly.csv")
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open(newline="", encoding="utf-8") as f:
        list(csv.DictReader(f))


if __name__ == "__main__":
    main()
