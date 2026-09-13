if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')

from scripts.import_macro_gdp import annualize_growth


def test_annualize_growth():
    assert annualize_growth(0.01) == (1.01**4) - 1
