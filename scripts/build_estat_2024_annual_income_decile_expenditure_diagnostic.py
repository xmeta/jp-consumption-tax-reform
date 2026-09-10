#!/usr/bin/env python3
"""Extract the 2024 NSFCW annual-income-decile household expenditure diagnostic.

This deliberately preserves the source rank concept (household annual income).
It does not map the expenditure rows onto OECD-new equivalized-disposable-income
deciles and does not infer VAT incidence from expenditure categories.
"""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from decimal import Decimal
import argparse
import csv
import io

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data/source_catalog.csv"
OUT = ROOT / "data/derived/estat_2024_annual_income_decile_expenditure_diagnostic.csv"
SOURCE_ID = "ESTAT-NSFCW-2024-T1-21-ANNUAL-INCOME-DECILE-EXPENDITURE"
EXPECTED_SHA = "189e1e777ffa8aed1a37f26709c8918dc35a2adfe42126465b973ac6f6f5acb0"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DECILE_COLS = ["BF","BG","BH","BI","BJ","BK","BL","BM","BN","BO"]

MAJOR = [
    ("food", "210101_食料"),
    ("housing", "210102_住居"),
    ("fuel_light_water", "210103_光熱・水道"),
    ("furniture_household_utensils", "210104_家具・家事用品"),
    ("clothing_footwear", "210105_被服及び履物"),
    ("medical_care", "210106_保健医療"),
    ("transport_communication", "210107_交通・通信"),
    ("education", "210108_教育"),
    ("culture_recreation", "210109_教養娯楽"),
    ("other_consumption", "210110_その他の消費支出"),
]


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()
def clean_decimal(raw):
    if raw in ("", "-"):
        return ""
    d = Decimal(raw)
    # OOXML may contain binary-float renderings for one/two-decimal published cells.
    q = d.quantize(Decimal("0.01"))
    if q == q.to_integral():
        return str(int(q))
    return format(q.normalize(), "f")


def load_cells(path):
    with ZipFile(path) as z:
        strings = []
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{{{NS}}}si"):
            strings.append("".join(t.text or "" for t in si.iter(f"{{{NS}}}t")))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet.findall(f".//{{{NS}}}row"):
            rn = row.attrib["r"]
            values = {}
            for cell in row.findall(f"{{{NS}}}c"):
                ref = cell.attrib["r"]
                value_node = cell.find(f"{{{NS}}}v")
                if value_node is None:
                    value = ""
                else:
                    raw = value_node.text or ""
                    value = strings[int(raw)] if cell.attrib.get("t") == "s" else raw
                values[ref] = value
            rows.append((rn, values))
        return rows


def target_block(rows):
    out = []
    for rn, values in rows:
        if (
            values.get(f"B{rn}") == "00000_全国"
            and values.get(f"D{rn}") == "0_総世帯"
            and values.get(f"F{rn}") == "0_全世帯"
            and values.get(f"H{rn}") == "0_平均"
        ):
            out.append((rn, values))
    if not out:
        raise RuntimeError("target nationwide total-household block not found")
    return out


def unique_row(block, *, item_i=None, item_k=None):
    hits = []
    for rn, values in block:
        if item_i is not None and values.get(f"I{rn}") != item_i:
            continue
        if item_k is not None and values.get(f"K{rn}") != item_k:
            continue
        hits.append((rn, values))
    if len(hits) != 1:
        raise RuntimeError(
            f"expected one row for I={item_i!r} K={item_k!r}; found {len(hits)}"
        )
    return hits[0]
def decile_values(row):
    rn, values = row
    return [clean_decimal(values.get(f"{col}{rn}", "")) for col in DECILE_COLS]


def build():
    catalog = {r["source_id"]: r for r in read_csv(CAT)}
    source = catalog[SOURCE_ID]
    if not (source['sha256'] == EXPECTED_SHA):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_estat_2024_annual_income_decile_expenditure_diagnostic.py:120')
    raw_path = ROOT / source["raw_file"]
    rows = load_cells(raw_path)
    block = target_block(rows)

    sample = decile_values(unique_row(block, item_i="集計世帯数（概数）", item_k="0_総数"))
    population = decile_values(unique_row(block, item_i="世帯数分布", item_k="0_総数"))
    members = decile_values(unique_row(block, item_i="世帯人員", item_k="1_平均"))
    senior = decile_values(unique_row(block, item_i="65歳以上人員", item_k="1_平均"))
    employed = decile_values(unique_row(block, item_i="有業人員", item_k="1_平均"))
    head_age = decile_values(unique_row(block, item_i="世帯主の年齢", item_k="1_平均"))
    upper = decile_values(
        unique_row(block, item_i="各分位の境界値（分位の上限・万円）", item_k="1_平均")
    )
    consumption_row = unique_row(
        block, item_i="1世帯当たり1か月間の収入と支出", item_k="2101_消費支出"
    )
    consumption = decile_values(consumption_row)
    rn, values = consumption_row
    overall_consumption = clean_decimal(values[f"BE{rn}"])
    if not (overall_consumption == '251242'):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_estat_2024_annual_income_decile_expenditure_diagnostic.py:140')

    major_values = {}
    for key, label in MAJOR:
        major_values[key] = decile_values(
            unique_row(
                block,
                item_i="1世帯当たり1か月間の収入と支出",
                item_k=label,
            )
        )

    # Explicit source evidence that the broad food subtotal is not the reduced-rate base.
    unique_row(
        block,
        item_i="1世帯当たり1か月間の収入と支出",
        item_k="21010111_酒類",
    )
    unique_row(
        block,
        item_i="1世帯当たり1か月間の収入と支出",
        item_k="21010112_外食",
    )
    out = []
    for i in range(10):
        c = int(consumption[i])
        major_sum = sum(int(major_values[key][i]) for key, _ in MAJOR)
        gap = major_sum - c
        if abs(gap) > 1:
            raise RuntimeError(f"major-category sum gap too large at decile {i+1}: {gap}")
        food = int(major_values["food"][i])
        row = {
            "annual_income_decile": i + 1,
            "rank_concept": "HOUSEHOLD_ANNUAL_INCOME_DECILE",
            "objective_rank_concept": "OECD_NEW_EQUIVALIZED_DISPOSABLE_INCOME_DECILE",
            "rank_bridge_status": "NOT_LINKED_DO_NOT_TREAT_AS_OBJECTIVE_DECILE",
            "approx_sample_households": sample[i],
            "population_households": population[i],
            "household_members": members[i],
            "members_age65_plus": senior[i],
            "employed_members": employed[i],
            "household_head_age": head_age[i],
            "annual_income_decile_upper_10k_yen": upper[i],
            "annual_income_upper_status": (
                "OPEN_TOP_DECILE_NO_UPPER_BOUND" if i == 9 else "PUBLISHED_UPPER_BOUND"
            ),
            "monthly_consumption_expenditure_yen": str(c),
            "annualized_consumption_expenditure_yen": str(c * 12),
            "consumption_relative_to_all_household_average": (
                f"{Decimal(c) / Decimal(overall_consumption):.12f}".rstrip("0").rstrip(".")
            ),
            "food_yen": major_values["food"][i],
            "housing_yen": major_values["housing"][i],
            "fuel_light_water_yen": major_values["fuel_light_water"][i],
            "furniture_household_utensils_yen": major_values["furniture_household_utensils"][i],
            "clothing_footwear_yen": major_values["clothing_footwear"][i],
            "medical_care_yen": major_values["medical_care"][i],
            "transport_communication_yen": major_values["transport_communication"][i],
            "education_yen": major_values["education"][i],
            "culture_recreation_yen": major_values["culture_recreation"][i],
            "other_consumption_yen": major_values["other_consumption"][i],
            "major_category_sum_yen": str(major_sum),
            "major_category_rounding_gap_yen": str(gap),
            "food_share_of_consumption": (
                f"{Decimal(food) / Decimal(c):.12f}".rstrip("0").rstrip(".")
            ),
            "vat_base_status": "NOT_IDENTIFIED_BROAD_FOOD_INCLUDES_ALCOHOL_AND_EATING_OUT_OTHER_EXEMPTIONS_UNMAPPED",
            "gini_fgt2_use": "PROHIBITED_DIRECT_MAPPING_WITHOUT_RANK_BRIDGE_AND_VAT_INCIDENCE_MODEL",
            "source_id": SOURCE_ID,
            "source_locator": "a01021 nationwide total-households/all-households/head-sex-average block; annual-income deciles BF:BO",
            "scientific_status": "OBSERVED_ANNUAL_INCOME_DECILE_EXPENDITURE_DIAGNOSTIC",
        }
        out.append(row)

    if not ({int(r['population_households']) for r in out} == {5355441}):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_estat_2024_annual_income_decile_expenditure_diagnostic.py:214')
    return out
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = build()
    expected = render(rows)
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != expected:
            raise SystemExit("stale generated artifact: " + str(OUT.relative_to(ROOT)))
        print(
            "NSFCW annual-income-decile expenditure diagnostic: current "
            "(10 deciles; total + 10 major expenditure groups; rank bridge intentionally absent)"
        )
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(expected, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
