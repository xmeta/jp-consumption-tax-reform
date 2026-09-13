from scripts.import_macro_gdp import annualize_growth


def test_annualize_growth():
    assert annualize_growth(0.01) == (1.01**4) - 1
