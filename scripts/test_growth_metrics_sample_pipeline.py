if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')

"""Integration test for the Issue #121 sample GDP pipeline."""

from pathlib import Path

from compute_growth_metrics import compute_metrics, load_growth_rates


ROOT = Path(__file__).resolve().parents[1]


def test_sample_csv_pipeline():
    values = load_growth_rates(ROOT / "data/macro/real_gdp_quarterly_sample.csv")
    result = compute_metrics(values)

    assert len(values) == 3
    assert result["R_g"] == 0.005
    assert result["D_g"] > 0
    assert result["C_Y"] < 0
