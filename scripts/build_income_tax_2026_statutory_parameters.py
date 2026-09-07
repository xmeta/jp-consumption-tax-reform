#!/usr/bin/env python3
from pathlib import Path
import argparse
import csv
import io
import sys

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/source_catalog.csv"
OUT = ROOT / "data/derived/income_tax_2026_statutory_parameters.csv"


def R(group, rule, lo, hi, formula, rate="", quick="", const="",
      source="", locator="", status="VERIFIED_OFFICIAL_RULE", note=""):
    return {
        "parameter_group": group,
        "rule_id": rule,
        "lower_yen_inclusive": lo,
        "upper_yen_exclusive": hi,
        "formula": formula,
        "rate": rate,
        "quick_deduction_yen": quick,
        "constant_yen": const,
        "source_id": source,
        "source_locator": locator,
        "source_sha256": "",
        "status": status,
        "note": note,
    }


ROWS = [
    # Progressive national income-tax quick table.
    R("income_tax_rate","T1",0,1950000,"taxable*rate-quick",0.05,0,source="NTA-INCOME-TAX-RATE-2260",locator="所得税の速算表 / 7 progressive brackets"),
    R("income_tax_rate","T2",1950000,3300000,"taxable*rate-quick",0.10,97500,source="NTA-INCOME-TAX-RATE-2260",locator="所得税の速算表 / 7 progressive brackets"),
    R("income_tax_rate","T3",3300000,6950000,"taxable*rate-quick",0.20,427500,source="NTA-INCOME-TAX-RATE-2260",locator="所得税の速算表 / 7 progressive brackets"),
    R("income_tax_rate","T4",6950000,9000000,"taxable*rate-quick",0.23,636000,source="NTA-INCOME-TAX-RATE-2260",locator="所得税の速算表 / 7 progressive brackets"),
    R("income_tax_rate","T5",9000000,18000000,"taxable*rate-quick",0.33,1536000,source="NTA-INCOME-TAX-RATE-2260",locator="所得税の速算表 / 7 progressive brackets"),
    R("income_tax_rate","T6",18000000,40000000,"taxable*rate-quick",0.40,2796000,source="NTA-INCOME-TAX-RATE-2260",locator="所得税の速算表 / 7 progressive brackets"),
    R("income_tax_rate","T7",40000000,"","taxable*rate-quick",0.45,4796000,source="NTA-INCOME-TAX-RATE-2260",locator="所得税の速算表 / 7 progressive brackets"),

    # 2026 basic deduction. Bounds here are total-income bounds.
    R("basic_deduction","B1",0,4890001,"constant",const=1040000,source="NTA-2026-INCOME-TAX",locator="基礎控除 / 合計所得金額489万円以下"),
    R("basic_deduction","B2",4890001,6550001,"constant",const=670000,source="NTA-2026-INCOME-TAX",locator="基礎控除 / 489万円超655万円以下"),
    R("basic_deduction","B3",6550001,23500001,"constant",const=620000,source="NTA-2026-INCOME-TAX",locator="基礎控除 / 655万円超2350万円以下"),
    R("basic_deduction","B4",23500001,24000001,"constant",const=480000,source="NTA-2026-INCOME-TAX",locator="基礎控除 / 2350万円超2400万円以下"),
    R("basic_deduction","B5",24000001,24500001,"constant",const=320000,source="NTA-2026-INCOME-TAX",locator="基礎控除 / 2400万円超2450万円以下"),
    R("basic_deduction","B6",24500001,25000001,"constant",const=160000,source="NTA-2026-INCOME-TAX",locator="基礎控除 / 2450万円超2500万円以下"),
    R("basic_deduction","B7",25000001,"","constant",const=0,source="NTA-2026-INCOME-TAX",locator="基礎控除 / 2500万円超"),

    # 2026-2029 employment-income amount after the employment-income deduction.
    R("employment_income","E1",0,741000,"zero",const=0,source="NTA-2026-TAX-REFORM",locator="p.1 給与所得控除最低保障額74万円・特例表",status="VERIFIED_TRANSCRIPTION_PDF"),
    R("employment_income","E2",741000,2191000,"gross-740000",source="NTA-2026-TAX-REFORM",locator="p.1 74万1千円以上219万1千円未満",status="VERIFIED_TRANSCRIPTION_PDF"),
    R("employment_income","E3",2191000,2193000,"constant",const=1451000,source="NTA-2026-TAX-REFORM",locator="p.1 219万1千円以上219万3千円未満",status="VERIFIED_TRANSCRIPTION_PDF"),
    R("employment_income","E4",2193000,2196000,"constant",const=1453000,source="NTA-2026-TAX-REFORM",locator="p.1 219万3千円以上219万6千円未満",status="VERIFIED_TRANSCRIPTION_PDF"),
    R("employment_income","E5",2196000,2200000,"constant",const=1456000,source="NTA-2026-TAX-REFORM",locator="p.1 219万6千円以上220万円未満",status="VERIFIED_TRANSCRIPTION_PDF"),
    R("employment_income","E6",2200000,3600000,"floor(gross/4000)*2800-80000",source="NTA-SALARY-DEDUCTION-1410",locator="給与所得控除 / 180万円超360万円以下; 2026 special rule ends below220万円"),
    R("employment_income","E7",3600000,6600000,"floor(gross/4000)*3200-440000",source="NTA-SALARY-DEDUCTION-1410",locator="給与所得控除 / 360万円超660万円以下"),
    R("employment_income","E8",6600000,8500000,"gross*0.90-1100000",source="NTA-SALARY-DEDUCTION-1410",locator="給与所得控除 / 660万円超850万円以下"),
    R("employment_income","E9",8500000,"","gross-1950000",source="NTA-SALARY-DEDUCTION-1410",locator="給与所得控除 / 850万円超"),

    # Public-pension miscellaneous income when non-pension income <=10m.
    R("pension_income_u65","PU1",0,600001,"zero",const=0,source="NTA-2026-PENSION-TAX",locator="65歳未満 / 60万円以下"),
    R("pension_income_u65","PU2",600001,1300000,"gross-600000",source="NTA-2026-PENSION-TAX",locator="65歳未満 / 60万円超130万円未満"),
    R("pension_income_u65","PU3",1300000,4100000,"gross*0.75-275000",source="NTA-2026-PENSION-TAX",locator="65歳未満 / 130万円以上410万円未満"),
    R("pension_income_u65","PU4",4100000,7700000,"gross*0.85-685000",source="NTA-2026-PENSION-TAX",locator="65歳未満 / 410万円以上770万円未満"),
    R("pension_income_u65","PU5",7700000,10000000,"gross*0.95-1455000",source="NTA-2026-PENSION-TAX",locator="65歳未満 / 770万円以上1000万円未満"),
    R("pension_income_u65","PU6",10000000,"","gross-1955000",source="NTA-2026-PENSION-TAX",locator="65歳未満 / 1000万円以上"),

    R("pension_income_65p","P65_1",0,1100001,"zero",const=0,source="NTA-2026-PENSION-TAX",locator="65歳以上 / 110万円以下"),
    R("pension_income_65p","P65_2",1100001,3300000,"gross-1100000",source="NTA-2026-PENSION-TAX",locator="65歳以上 / 110万円超330万円未満"),
    R("pension_income_65p","P65_3",3300000,4100000,"gross*0.75-275000",source="NTA-2026-PENSION-TAX",locator="65歳以上 / 330万円以上410万円未満"),
    R("pension_income_65p","P65_4",4100000,7700000,"gross*0.85-685000",source="NTA-2026-PENSION-TAX",locator="65歳以上 / 410万円以上770万円未満"),
    R("pension_income_65p","P65_5",7700000,10000000,"gross*0.95-1455000",source="NTA-2026-PENSION-TAX",locator="65歳以上 / 770万円以上1000万円未満"),
    R("pension_income_65p","P65_6",10000000,"","gross-1955000",source="NTA-2026-PENSION-TAX",locator="65歳以上 / 1000万円以上"),

    R("pension_other_income_adjustment","PA1",10000001,20000001,"add_to_pension_income",const=100000,source="NTA-2026-PENSION-DETAIL",locator="公的年金等控除表 / 公的年金等以外の所得1000万円超2000万円以下",status="VERIFIED_TRANSCRIPTION_PDF"),
    R("pension_other_income_adjustment","PA2",20000001,"","add_to_pension_income",const=200000,source="NTA-2026-PENSION-DETAIL",locator="公的年金等控除表 / 公的年金等以外の所得2000万円超",status="VERIFIED_TRANSCRIPTION_PDF"),
]


def read_catalog():
    with CATALOG.open(encoding="utf-8", newline="") as f:
        return {r["source_id"]: r for r in csv.DictReader(f)}


def render(rows):
    fields = list(rows[0])
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=fields, lineterminator="\n")
    w.writeheader(); w.writerows(rows)
    return b.getvalue()


def build():
    cat = read_catalog()
    rows = []
    for src in ROWS:
        r = dict(src)
        if r["source_id"] not in cat:
            raise RuntimeError(f"unknown source_id {r['source_id']}")
        r["source_sha256"] = cat[r["source_id"]]["sha256"]
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    expected = render(build())
    if args.check:
        actual = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if actual != expected:
            print("ERROR: statutory parameter table is stale")
            sys.exit(1)
        print(f"2026 statutory parameters: current ({len(ROWS)} rules)")
        return
    OUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(ROWS)} rules")


if __name__ == "__main__":
    main()
