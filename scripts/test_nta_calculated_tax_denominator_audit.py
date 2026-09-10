#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import math
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/nta_calculated_tax_positive_denominator_audit_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"
STAGE2 = ROOT / "data/derived/nta_primary_type_stage2_2024.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(OUT)
assert len(rows) == 1
r = rows[0]

assert r["tax_year"] == "2024"
assert r["audit_status"] == "CALCULATED_TAX_POSITIVE_PERSON_COUNT_NOT_IDENTIFIED"
assert r["long_term_taxpayer_count_semantics"] == (
    "POSITIVE_SELF_ASSESSED_BALANCE_SURVEY_TARGET_NOT_CALCULATED_TAX_POSITIVE_COUNT"
)
assert r["calculated_tax_positive_persons_public_value"] == ""

# Long-term Sample Survey Table 1 and Table 2 agree exactly on the survey target.
assert int(r["long_term_table1_taxpayer_persons"]) == 5_158_260
assert int(r["long_term_table2_taxpayer_persons"]) == 5_158_260
assert r["long_term_table1_taxpayer_source_cell"] == "B79"
assert r["long_term_table2_taxpayer_source_cell"] == "AE79"

# These monetary anchors are the published grand totals in both long-term tables.
assert int(r["calculated_tax_million_yen"]) == 8_044_571
assert int(r["tax_credits_million_yen"]) == 352_866
assert int(r["source_withholding_persons"]) == 3_302_359
assert int(r["source_withholding_tax_million_yen"]) == 3_446_992
assert int(r["self_assessed_balance_million_yen"]) == 4_406_942

# Independently reproduced annual-statistics population.
assert int(r["annual_positive_self_assessed_balance_persons"]) == 5_158_260
assert int(r["annual_table22_population_persons"]) == 23_362_184
assert int(r["annual_refund_persons"]) == 13_527_496
assert int(r["annual_neither_positive_nor_refund_persons"]) == 4_676_428

# Same-person same-year direction gives only a lower bound.  The full Table 2-2(1)
# population is a conservative upper bound *inside that population only*.
lower = int(r["table22_scope_calculated_tax_positive_lower_bound_persons"])
upper = int(r["table22_scope_calculated_tax_positive_upper_bound_persons"])
assert lower == 5_158_260
assert upper == 23_362_184
assert int(r["table22_scope_bound_width_persons"]) == 18_203_924
assert math.isclose(
    float(r["table22_scope_lower_bound_rate"]),
    5_158_260 / 23_362_184,
    abs_tol=5e-13,
    rel_tol=0.0,
)
assert float(r["table22_scope_upper_bound_rate"]) == 1.0
assert r["same_person_same_year_direction"] == (
    "POSITIVE_SELF_ASSESSED_BALANCE_IMPLIES_POSITIVE_CALCULATED_TAX"
)
assert r["general_population_upper_bound_status"] == (
    "NOT_PROVIDED_BY_THESE_SELF_ASSESSMENT_SOURCES"
)
assert r["cross_system_use"] == (
    "DO_NOT_CALIBRATE_PSEUDO_CALCULATED_TAX_POSITIVE_RATE_FROM_LONG_TERM_TAXPAYER_COUNT"
)
assert "not a general-population or F71561 upper bound" in r["identification_warning"]

# Cross-check the annual total through the existing five primary-type artifact.
stage2 = read(STAGE2)
assert len(stage2) == 5
assert {
    int(x["annual_all_category_positive_self_assessed_balance_persons_exact"])
    for x in stage2
} == {5_158_260}
assert {
    int(x["annual_all_category_table22_population_persons_exact"])
    for x in stage2
} == {23_362_184}

# Both newly retained official workbooks are SHA-pinned in the source catalog.
catalog = {x["source_id"]: x for x in read(CATALOG)}
expected = {
    "NTA-SHINKOKU-JIKEIRETSU-T1-XLSX":
        "4466ab1322052daaae18d3ecea5d12fa1ae794877b188762d3ec9606d844cc88",
    "NTA-SHINKOKU-JIKEIRETSU-T2-XLSX":
        "bddd841d53ad3694ae1cc1a6dc8415d21547245f56b655a02cd156ec49dcfb53",
}
for sid, sha in expected.items():
    assert catalog[sid]["sha256"] == sha
    assert catalog[sid]["status"] == "RAW_OFFICIAL"

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_calculated_tax_denominator_audit.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA calculated-tax-positive denominator audit tests: OK "
    "(long-term taxpayer count=5,158,260 positive-balance target; "
    "calculated-tax-positive count not identified; "
    "Table 2-2(1)-scope bound 5,158,260..23,362,184)"
)
