"""Focused tests for Issue #121 growth diagnostics."""

from pathlib import Path

from compute_growth_metrics import (
    cumulative_growth,
    growth_decline_penalty,
    recession_penalty,
)


def test_growth_decline_penalty():
    assert growth_decline_penalty([0.02, 0.01, 0.03]) == 0.0001


def test_recession_penalty():
    assert recession_penalty([0.01, -0.02, -0.01]) == 0.03


def test_cumulative_growth():
    assert cumulative_growth([0.01, 0.01]) > 0
