if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')

"""Focused schema checks for Issue #121 GDP import preparation."""

import csv
from io import StringIO


REQUIRED_COLUMNS = {
    "quarter",
    "real_gdp_growth_qoq",
    "annualized_growth",
    "status",
    "source_id",
    "revision_date",
}


def validate_columns(content: str) -> bool:
    reader = csv.DictReader(StringIO(content))
    return set(reader.fieldnames or ()) == REQUIRED_COLUMNS


def test_real_gdp_schema():
    assert validate_columns(
        "quarter,real_gdp_growth_qoq,annualized_growth,status,source_id,revision_date\n"
    )


def test_invalid_schema():
    assert not validate_columns("quarter,growth\n")
