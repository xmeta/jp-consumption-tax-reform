#!/usr/bin/env python3
from pathlib import Path
import argparse, csv, io, sys

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/source_catalog.csv"
OUT = ROOT / "data/derived/income_tax_2024_statutory_parameters.csv"


def R(group, rule, lo, hi, formula, rate="", quick="", const="", source="", locator="", note=""):
    return {"parameter_group": group, "rule_id": rule, "lower_yen_inclusive": lo,
            "upper_yen_exclusive": hi, "formula": formula, "rate": rate,
            "quick_deduction_yen": quick, "constant_yen": const, "source_id": source,
            "source_locator": locator, "source_sha256": "",
            "status": "VERIFIED_OFFICIAL_RULE", "note": note}

RATE = "NTA-2024-FILING-GUIDE-RATE"
SALARY = "NTA-2024-FILING-GUIDE-SALARY"
PENSION = "NTA-2024-FILING-GUIDE-PENSION"
BASIC = "NTA-2024-FILING-GUIDE-BASIC"
DEPENDENT = "NTA-2024-FILING-GUIDE-DEPENDENT"

ROWS = [
    R("income_tax_rate","T1",0,1950000,"taxable*rate-quick",.05,0,source=RATE,locator="課税される所得金額に対する税額 / 1,000-1,949,000円"),
    R("income_tax_rate","T2",1950000,3300000,"taxable*rate-quick",.10,97500,source=RATE,locator="1,950,000-3,299,000円"),
    R("income_tax_rate","T3",3300000,6950000,"taxable*rate-quick",.20,427500,source=RATE,locator="3,300,000-6,949,000円"),
    R("income_tax_rate","T4",6950000,9000000,"taxable*rate-quick",.23,636000,source=RATE,locator="6,950,000-8,999,000円"),
    R("income_tax_rate","T5",9000000,18000000,"taxable*rate-quick",.33,1536000,source=RATE,locator="9,000,000-17,999,000円"),
    R("income_tax_rate","T6",18000000,40000000,"taxable*rate-quick",.40,2796000,source=RATE,locator="18,000,000-39,999,000円"),
    R("income_tax_rate","T7",40000000,"","taxable*rate-quick",.45,4796000,source=RATE,locator="40,000,000円以上"),
    R("basic_deduction","B1",0,24000001,"constant",const=480000,source=BASIC,locator="合計所得金額2,400万円以下"),
    R("basic_deduction","B2",24000001,24500001,"constant",const=320000,source=BASIC,locator="2,400万円超2,450万円以下"),
    R("basic_deduction","B3",24500001,25000001,"constant",const=160000,source=BASIC,locator="2,450万円超2,500万円以下"),
    R("basic_deduction","B4",25000001,"","constant",const=0,source=BASIC,locator="2,500万円超"),
    R("employment_income","E1",0,551000,"zero",const=0,source=SALARY,locator="給与収入550,999円以下"),
    R("employment_income","E2",551000,1619000,"gross-550000",source=SALARY,locator="551,000-1,618,999円"),
    R("employment_income","E3",1619000,1620000,"constant",const=1069000,source=SALARY,locator="1,619,000-1,619,999円"),
    R("employment_income","E4",1620000,1622000,"constant",const=1070000,source=SALARY,locator="1,620,000-1,621,999円"),
    R("employment_income","E5",1622000,1624000,"constant",const=1072000,source=SALARY,locator="1,622,000-1,623,999円"),
    R("employment_income","E6",1624000,1628000,"constant",const=1074000,source=SALARY,locator="1,624,000-1,627,999円"),
    R("employment_income","E7",1628000,1800000,"floor(gross/4000)*2400+100000",source=SALARY,locator="1,628,000-1,799,999円"),
    R("employment_income","E8",1800000,3600000,"floor(gross/4000)*2800-80000",source=SALARY,locator="1,800,000-3,599,999円"),
    R("employment_income","E9",3600000,6600000,"floor(gross/4000)*3200-440000",source=SALARY,locator="3,600,000-6,599,999円"),
    R("employment_income","E10",6600000,8500000,"gross*0.90-1100000",source=SALARY,locator="6,600,000-8,499,999円"),
    R("employment_income","E11",8500000,"","gross-1950000",source=SALARY,locator="8,500,000円以上"),
]

for group, prefix, first_hi, first_formula, first_const in [
    ("pension_income_u65","PU",1300000,"gross-600000",0),
    ("pension_income_65p","P65",3300000,"gross-1100000",0),
]:
    ROWS.extend([
        R(group,prefix+"1",0,first_hi,first_formula,source=PENSION,locator="公的年金等の雑所得 / 非年金所得1,000万円以下 / first band"),
        R(group,prefix+"2",first_hi,4100000,"gross*0.75-275000",source=PENSION,locator="公的年金等の雑所得 / 0.75 band"),
        R(group,prefix+"3",4100000,7700000,"gross*0.85-685000",source=PENSION,locator="公的年金等の雑所得 / 0.85 band"),
        R(group,prefix+"4",7700000,10000000,"gross*0.95-1455000",source=PENSION,locator="公的年金等の雑所得 / 0.95 band"),
        R(group,prefix+"5",10000000,"","gross-1955000",source=PENSION,locator="公的年金等の雑所得 / 1,000万円以上"),
    ])
ROWS.extend([
    R("pension_other_income_adjustment","PA1",10000001,20000001,"add_to_pension_income",const=100000,source=PENSION,locator="非年金所得1,000万円超2,000万円以下: calculated income +100,000円"),
    R("pension_other_income_adjustment","PA2",20000001,"","add_to_pension_income",const=200000,source=PENSION,locator="非年金所得2,000万円超: calculated income +200,000円"),
    R("dependent_deduction","D_GENERAL","","","constant",const=380000,source=DEPENDENT,locator="一般の控除対象扶養親族 38万円"),
    R("dependent_deduction","D_SPECIFIED","","","constant",const=630000,source=DEPENDENT,locator="特定扶養親族 63万円"),
    R("dependent_deduction","D_ELDERLY_OTHER","","","constant",const=480000,source=DEPENDENT,locator="同居老親等以外の老人扶養親族 48万円"),
    R("dependent_deduction","D_ELDERLY_CORESIDENT","","","constant",const=580000,source=DEPENDENT,locator="同居老親等 58万円"),
])


def build():
    with CATALOG.open(encoding="utf-8", newline="") as f:
        cat={r["source_id"]:r for r in csv.DictReader(f)}
    out=[]
    for src in ROWS:
        r=dict(src); r["source_sha256"]=cat[r["source_id"]]["sha256"]; out.append(r)
    return out


def render(rows):
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator="\n"); w.writeheader(); w.writerows(rows); return b.getvalue()


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--check",action="store_true"); args=ap.parse_args(); expected=render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text()!=expected: print("ERROR: 2024 statutory parameter table is stale"); sys.exit(1)
        print(f"2024 statutory parameters: current ({len(ROWS)} rules)"); return
    OUT.write_text(expected); print(f"wrote {OUT.relative_to(ROOT)}: {len(ROWS)} rules")

if __name__ == "__main__": main()
