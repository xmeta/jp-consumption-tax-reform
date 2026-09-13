if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')

"""Focused tests for Issue #121 growth diagnostics."""

from pathlib import Path

from compute_growth_metrics import (
    cumulative_growth,
    growth_decline_penalty,
    per_capita_growth,
    production_decomposition,
    recession_penalty,
)


def test_growth_decline_penalty():
    assert growth_decline_penalty([0.02, 0.01, 0.03]) == 0.0001


def test_per_capita_growth_exact_identity():
    # Aggregate GDP can fall while population-normalized production rises.
    rate = per_capita_growth(-0.003, -0.01)
    assert rate > 0.0
    assert abs((1.0 + rate) - (0.997 / 0.99)) < 1e-15


def test_production_decomposition():
    y_pc, q, u = production_decomposition(100.0, 10.0, 20.0)
    assert y_pc == 10.0
    assert q == 5.0
    assert u == 2.0
    assert y_pc == q * u


def test_recession_penalty():
    assert recession_penalty([0.01, -0.02, -0.01]) == 0.03


def test_cumulative_growth():
    assert cumulative_growth([0.01, 0.01]) > 0


if __name__ == "__main__":
    test_growth_decline_penalty()
    test_per_capita_growth_exact_identity()
    test_production_decomposition()
    test_recession_penalty()
    test_cumulative_growth()
    print("growth metric unit tests: OK")
