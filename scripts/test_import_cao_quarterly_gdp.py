from scripts.import_cao_quarterly_gdp import normalize_rows


def test_normalize_rows_adds_annualized_growth():
    row = {
        "quarter": "2024-Q1",
        "real_gdp_growth_qoq": "0.01",
        "source_id": "NIAES_QNA",
        "revision_date": "2026-09-13",
    }
    result = list(normalize_rows([row]))[0]
    assert result["annualized_growth"] == (1.01**4) - 1
