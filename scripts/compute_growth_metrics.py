"""Compute macro growth diagnostics for Issue #121.

Observed GDP data handling is intentionally separated from policy simulation.
This computes descriptive diagnostics only; it does not create optimizer inputs.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path


def annualize_qoq(rate: float) -> float:
    """Convert quarterly growth rate to annualized growth rate."""
    return (1.0 + rate) ** 4 - 1.0


def growth_decline_penalty(growth_rates: list[float]) -> float:
    """Compute D_g without applying normative weights."""
    return sum(
        max(0.0, previous - current) ** 2
        for previous, current in zip(growth_rates, growth_rates[1:])
    )


def recession_penalty(growth_rates: list[float]) -> float:
    """Compute R_g downside diagnostic."""
    return sum(abs(rate) for rate in growth_rates if rate < 0.0)


def cumulative_growth(growth_rates: list[float]) -> float:
    """Compute C_Y as cumulative log growth diagnostic."""
    return sum(math.log1p(rate) for rate in growth_rates if rate > -1.0)


def load_growth_rates(path: Path) -> list[float]:
    """Load observed quarterly real GDP growth rates only."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = csv.DictReader(f)
        return [
            float(row["real_gdp_growth_qoq"])
            for row in rows
            if row.get("status") == "observed"
        ]


def compute_metrics(path: Path) -> dict[str, float]:
    rates = load_growth_rates(path)
    return {
        "C_Y": cumulative_growth(rates),
        "D_g": growth_decline_penalty(rates),
        "R_g": recession_penalty(rates),
    }


def main() -> None:
    path = Path("data/macro/real_gdp_quarterly.csv")
    print(compute_metrics(path))


if __name__ == "__main__":
    main()
