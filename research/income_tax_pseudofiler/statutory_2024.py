#!/usr/bin/env python3
"""2024 Japanese national-income-tax statutory functions for Issue #133 benchmark."""
from pathlib import Path
import csv
import math

ROOT = Path(__file__).resolve().parents[2]
PARAMS = ROOT / "data/derived/income_tax_2024_statutory_parameters.csv"


def _read():
    with PARAMS.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


_ROWS = _read()
_BY_GROUP = {}
for _r in _ROWS:
    _BY_GROUP.setdefault(_r["parameter_group"], []).append(_r)


def _num(s):
    return None if s in ("", None) else float(s)


def _find(group, x):
    x = float(x)
    for r in _BY_GROUP[group]:
        lo = float(r["lower_yen_inclusive"])
        hi = _num(r["upper_yen_exclusive"])
        if x >= lo and (hi is None or x < hi):
            return r
    raise ValueError(f"no {group} rule for {x}")


def employment_income(gross_salary_yen):
    g = max(float(gross_salary_yen), 0.0)
    r = _find("employment_income", g)
    formula = r["formula"]
    if formula == "zero":
        return 0.0
    if formula == "gross-550000":
        return max(g - 550_000.0, 0.0)
    if formula == "constant":
        return float(r["constant_yen"])
    if formula == "floor(gross/4000)*2400+100000":
        return max(math.floor(g / 4_000.0) * 2_400.0 + 100_000.0, 0.0)
    if formula == "floor(gross/4000)*2800-80000":
        return max(math.floor(g / 4_000.0) * 2_800.0 - 80_000.0, 0.0)
    if formula == "floor(gross/4000)*3200-440000":
        return max(math.floor(g / 4_000.0) * 3_200.0 - 440_000.0, 0.0)
    if formula == "gross*0.90-1100000":
        return max(g * 0.90 - 1_100_000.0, 0.0)
    if formula == "gross-1950000":
        return max(g - 1_950_000.0, 0.0)
    raise ValueError(formula)


def basic_deduction(total_income_yen):
    r = _find("basic_deduction", max(float(total_income_yen), 0.0))
    return float(r["constant_yen"])


def ordinary_income_tax_rate(taxable_income_yen):
    x = max(float(taxable_income_yen), 0.0)
    if x <= 0:
        return 0.0
    return float(_find("income_tax_rate", x)["rate"])


def ordinary_national_income_tax_continuous_proxy(taxable_income_yen):
    x = max(float(taxable_income_yen), 0.0)
    if x <= 0:
        return 0.0
    r = _find("income_tax_rate", x)
    return max(x * float(r["rate"]) - float(r["quick_deduction_yen"]), 0.0)


def ordinary_national_income_tax(taxable_income_yen):
    x = math.floor(max(float(taxable_income_yen), 0.0) / 1_000.0) * 1_000.0
    if x <= 0:
        return 0.0
    r = _find("income_tax_rate", x)
    return max(x * float(r["rate"]) - float(r["quick_deduction_yen"]), 0.0)


def public_pension_misc_income(gross_pension_yen, age65plus, other_income_yen=0.0):
    g = max(float(gross_pension_yen), 0.0)
    group = "pension_income_65p" if age65plus else "pension_income_u65"
    r = _find(group, g)
    formula = r["formula"]
    if formula == "gross-600000":
        out = g - 600_000.0
    elif formula == "gross-1100000":
        out = g - 1_100_000.0
    elif formula == "gross*0.75-275000":
        out = g * 0.75 - 275_000.0
    elif formula == "gross*0.85-685000":
        out = g * 0.85 - 685_000.0
    elif formula == "gross*0.95-1455000":
        out = g * 0.95 - 1_455_000.0
    elif formula == "gross-1955000":
        out = g - 1_955_000.0
    else:
        raise ValueError(formula)
    other = max(float(other_income_yen), 0.0)
    if other > 20_000_000:
        out += 200_000.0
    elif other > 10_000_000:
        out += 100_000.0
    return min(max(out, 0.0), g)


def dependent_deduction_amounts():
    return {
        r["rule_id"]: float(r["constant_yen"])
        for r in _BY_GROUP["dependent_deduction"]
    }
