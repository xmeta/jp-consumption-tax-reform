#!/usr/bin/env python3
from pathlib import Path
import csv
import hashlib
import importlib.util
import math

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "data/derived/income_tax_2026_statutory_parameters.csv"
CATALOG = ROOT / "data/source_catalog.csv"

spec = importlib.util.spec_from_file_location(
    "statutory_2026",
    ROOT / "research/income_tax_pseudofiler/statutory_2026.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(PARAMS)
cat = {r["source_id"]: r for r in read(CATALOG)}
assert len(rows) == 37

for r in rows:
    assert r["source_id"] in cat
    assert r["source_locator"]
    assert r["source_sha256"] == cat[r["source_id"]]["sha256"]
    assert r["status"] in {"VERIFIED_OFFICIAL_RULE", "VERIFIED_TRANSCRIPTION_PDF"}

# Snapshot anchors for machine-readable official HTML.
income_html = (
    ROOT / "data/raw/nta/nta_2026_income_tax_mechanism.html"
).read_bytes().decode("shift_jis")
for anchor in [
    "104万円", "67万円", "62万円", "48万円", "32万円", "16万円",
]:
    assert anchor in income_html, anchor

rate_html = (
    ROOT / "data/raw/nta/nta_income_tax_answer_2260_rates.html"
).read_bytes().decode("utf-8")
for anchor in [
    "1,950,000", "3,300,000", "6,950,000", "9,000,000",
    "18,000,000", "40,000,000",
    "97,500", "427,500", "636,000", "1,536,000", "2,796,000", "4,796,000",
]:
    assert anchor in rate_html, anchor

pension_html = (
    ROOT / "data/raw/nta/nta_2026_pension_tax.html"
).read_bytes().decode("shift_jis")
for anchor in [
    "60万円以下", "60万円超130万円未満",
    "110万円以下", "110万円超330万円未満",
    "0.75", "0.85", "0.95", "195万5千円",
]:
    assert anchor in pension_html, anchor

salary_html = (
    ROOT / "data/raw/nta/nta_income_tax_answer_1410_salary_deduction.html"
).read_bytes().decode("utf-8", errors="ignore")
if "8,500,001" not in salary_html:
    salary_html = (
        ROOT / "data/raw/nta/nta_income_tax_answer_1410_salary_deduction.html"
    ).read_bytes().decode("shift_jis")
for anchor in ["3,600,000", "6,600,000", "8,500,000", "1,950,000"]:
    assert anchor in salary_html, anchor

# Exact 2026-2029 special salary boundaries.
salary_cases = {
    0: 0,
    740_999: 0,
    741_000: 1_000,
    2_190_999: 1_450_999,
    2_191_000: 1_451_000,
    2_192_999: 1_451_000,
    2_193_000: 1_453_000,
    2_195_999: 1_453_000,
    2_196_000: 1_456_000,
    2_199_999: 1_456_000,
    2_200_000: 1_460_000,
    3_600_000: 2_440_000,
    6_600_000: 4_840_000,
    8_500_000: 6_550_000,
}
for gross, expected in salary_cases.items():
    got = mod.employment_income_2026(gross)
    assert math.isclose(got, expected, abs_tol=1e-9), (gross, got, expected)

# The historical recovered continuous formula differs in the narrow statutory
# fixed-value interval; preserve this as an explicit correction test.
old_at_2_192_999 = 2_192_999 - 740_000
new_at_2_192_999 = mod.employment_income_2026(2_192_999)
assert old_at_2_192_999 != new_at_2_192_999
assert old_at_2_192_999 - new_at_2_192_999 == 1_999

basic_cases = {
    4_890_000: 1_040_000,
    4_890_001: 670_000,
    6_550_000: 670_000,
    6_550_001: 620_000,
    23_500_000: 620_000,
    23_500_001: 480_000,
    24_000_001: 320_000,
    24_500_001: 160_000,
    25_000_001: 0,
}
for income, expected in basic_cases.items():
    assert mod.basic_deduction_2026(income) == expected

tax_cases = {
    1_949_999: 1_949_000 * 0.05,
    1_950_000: 1_950_000 * 0.10 - 97_500,
    3_300_000: 3_300_000 * 0.20 - 427_500,
    7_000_000: 7_000_000 * 0.23 - 636_000,
}
for taxable, expected in tax_cases.items():
    got = mod.ordinary_national_income_tax_2026(taxable)
    assert math.isclose(got, expected, abs_tol=1e-9), (taxable, got, expected)

# Taxable income is rounded down to 1,000 yen for the quick table.
assert mod.ordinary_national_income_tax_2026(1_234_999) == 1_234_000 * 0.05

assert mod.public_pension_misc_income_2026(600_000, False) == 0
assert mod.public_pension_misc_income_2026(1_100_000, True) == 0
assert mod.public_pension_misc_income_2026(2_000_000, False) == 1_225_000
assert mod.public_pension_misc_income_2026(2_000_000, True) == 900_000
assert mod.public_pension_misc_income_2026(
    2_000_000, True, 10_000_001
) == 1_000_000
assert mod.public_pension_misc_income_2026(
    2_000_000, True, 20_000_001
) == 1_100_000

print(
    "2026 statutory parameter tests: OK "
    "(37 rules; official snapshot anchors; salary boundary correction)"
)
