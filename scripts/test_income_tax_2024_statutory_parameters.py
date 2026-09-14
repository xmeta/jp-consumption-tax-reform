#!/usr/bin/env python3
if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests")
from pathlib import Path
import csv, importlib.util, math

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "data/derived/income_tax_2024_statutory_parameters.csv"
CATALOG = ROOT / "data/source_catalog.csv"
spec = importlib.util.spec_from_file_location(
    "statutory_2024", ROOT / "research/income_tax_pseudofiler/statutory_2024.py"
)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def text(name):
    raw=(ROOT / "data/raw/nta" / name).read_bytes()
    for enc in ("utf-8", "shift_jis", "cp932"):
        try: return raw.decode(enc)
        except UnicodeDecodeError: pass
    raise AssertionError(name)

rows=read(PARAMS); cat={r["source_id"]:r for r in read(CATALOG)}
assert len(rows) == 38
for r in rows:
    assert r["source_id"] in cat
    assert r["source_locator"]
    assert r["source_sha256"] == cat[r["source_id"]]["sha256"]
    assert r["status"] == "VERIFIED_OFFICIAL_RULE"

salary=text("nta_2024_filing_guide_salary_income.html")
for a in ["550,999", "551,000", "1,628,000", "3,600,000", "6,600,000", "8,500,000"]: assert a in salary
basic=text("nta_2024_filing_guide_basic_deduction.html")
for a in ["2,400万円以下", "48万円", "32万円", "16万円"]: assert a in basic
rate=text("nta_2024_filing_guide_tax_rate.html")
for a in ["1,950,000", "3,300,000", "6,950,000", "9,000,000", "18,000,000", "40,000,000"]: assert a in rate
pension=text("nta_2024_filing_guide_misc_income.html")
for a in ["600,000", "1,100,000", "0.75", "0.85", "0.95"]: assert a in pension

salary_cases={0:0,550_999:0,551_000:1_000,1_619_000:1_069_000,1_628_000:1_076_800,1_800_000:1_180_000,3_600_000:2_440_000,6_600_000:4_840_000,8_500_000:6_550_000}
for gross, expected in salary_cases.items():
    assert math.isclose(mod.employment_income(gross), expected, abs_tol=1e-9), (gross,mod.employment_income(gross),expected)
for income, expected in {24_000_000:480_000,24_000_001:320_000,24_500_001:160_000,25_000_001:0}.items():
    assert mod.basic_deduction(income) == expected
assert mod.ordinary_national_income_tax(1_234_999) == 1_234_000 * .05
assert mod.public_pension_misc_income(600_000, False) == 0
assert mod.public_pension_misc_income(1_100_000, True) == 0
assert mod.public_pension_misc_income(2_000_000, False) == 1_225_000
assert mod.public_pension_misc_income(2_000_000, True) == 900_000
print("2024 statutory parameter tests: OK (38 rules; official snapshot anchors; boundary functions)")
