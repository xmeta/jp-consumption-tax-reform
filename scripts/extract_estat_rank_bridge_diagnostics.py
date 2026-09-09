#!/usr/bin/env python3
"""Extract public NSFCW diagnostics relevant to cross-system rank transport.

These outputs are *within-NSFCW diagnostics*.  They do not identify a mapping
from NSFCW main-income categories to NTA primary-income categories, and they do
not identify record-level or decile-level correspondence between the two
systems.
"""
from __future__ import annotations

from pathlib import Path
import csv
import hashlib

from extract_estat_income_tax_tables import XlsxStream

ROOT = Path(__file__).resolve().parents[1]
RAW_71411 = ROOT / "data/raw/estat/000040490407.xlsx"
RAW_7171 = ROOT / "data/raw/estat/000040490427.xlsx"
OUT_71411 = ROOT / "data/derived/estat_71411_main_income_by_disposable_decile_2024.csv"
OUT_7171 = ROOT / "data/derived/estat_7171_main_income_disposable_quantiles_2024.csv"

SOURCE_CATEGORIES = {
    "00_平均": "total",
    "01_勤め先収入": "wages_salaries",
    "02_事業・内職収入": "business_homework",
    "03_財産収入": "property_income",
    "04_経常移転収入": "current_transfers",
}
CROSS_SYSTEM_STATUS = "WITHIN_NSFCW_DIAGNOSTIC_NO_NTA_CATEGORY_IDENTITY"
CROSS_SYSTEM_WARNING = (
    "NSFCW main annual-income categories are not asserted to equal NTA "
    "primary-income categories; no hard cross-system category constraint is identified"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def split_code_label(value: str) -> tuple[str, str]:
    return tuple(value.split("_", 1)) if "_" in value else ("", value)


def main_income_columns(path: Path) -> dict[str, str]:
    x = XlsxStream(path)
    rows = {}
    try:
        for row_no, values in x.rows():
            if row_no in (5, 6):
                rows[row_no] = values
            if row_no > 6:
                break
    finally:
        x.close()
    columns = {}
    for column, group in rows[5].items():
        category = rows[6].get(column, "")
        if group == "主な年間収入の種類" and category in SOURCE_CATEGORIES:
            columns[category] = column
    if set(columns) != set(SOURCE_CATEGORIES):
        raise RuntimeError(f"unexpected main-income columns: {columns}")
    return columns


def extract_71411() -> list[dict[str, object]]:
    columns = main_income_columns(RAW_71411)
    raw_sha = sha256(RAW_71411)
    rows = []
    x = XlsxStream(RAW_71411)
    try:
        for source_row, values in x.rows():
            if source_row < 8:
                continue
            decile_label = values.get("K", "")
            if not decile_label.startswith("R") or "十分位" not in decile_label:
                continue
            if not (
                values.get("A") == "世帯人員数"
                and values.get("C") == "00000_全国"
                and values.get("E") == "0_平均"
                and values.get("G") == "00_平均"
                and values.get("I") == "0_平均"
                and values.get("M") == "00_平均"
            ):
                continue
            decile = int(decile_label[1:3])
            counts = {
                category: int(values[columns[category]])
                for category in SOURCE_CATEGORIES
            }
            total = counts["00_平均"]
            for category, semantic_key in SOURCE_CATEGORIES.items():
                code, label = split_code_label(category)
                rows.append({
                    "decile": decile,
                    "decile_label": decile_label,
                    "rank_concept": "equivalized_disposable_income_oecd_new",
                    "main_income_type_code": code,
                    "main_income_type_label": label,
                    "semantic_key": semantic_key,
                    "household_members": counts[category],
                    "share_of_decile_total": f"{counts[category] / total:.12g}",
                    "source_cell": f"{columns[category]}{source_row}",
                    "source_id": "ESTAT-7141-1-2024",
                    "source_stat_inf_id": "000040490407",
                    "source_file": "data/raw/estat/000040490407.xlsx",
                    "source_sha256": raw_sha,
                    "cross_system_status": CROSS_SYSTEM_STATUS,
                    "cross_system_warning": CROSS_SYSTEM_WARNING,
                })
    finally:
        x.close()
    if len(rows) != 50:
        raise RuntimeError(f"expected 50 table-7-141-1 rows, got {len(rows)}")
    return rows


def extract_7171() -> list[dict[str, object]]:
    columns = main_income_columns(RAW_7171)
    raw_sha = sha256(RAW_7171)
    income_concept = "1_等価可処分所得（ＯＥＣＤ新基準準拠）"
    measures = {
        "集計世帯数（概数）": "aggregate_households_approx",
        "第１・十分位数": "p10",
        "第１・四分位数": "p25",
        "中位数": "p50",
        "第３・四分位数": "p75",
        "第９・十分位数": "p90",
    }
    rows = []
    x = XlsxStream(RAW_7171)
    try:
        for source_row, values in x.rows():
            if source_row < 8:
                continue
            measure = values.get("G", "")
            if not (
                values.get("B") == "00000_全国"
                and values.get("D") == "0_平均"
                and values.get("F") == income_concept
                and measure in measures
            ):
                continue
            for category, semantic_key in SOURCE_CATEGORIES.items():
                code, label = split_code_label(category)
                rows.append({
                    "income_concept": income_concept,
                    "measure": measure,
                    "measure_key": measures[measure],
                    "unit": values.get("H", ""),
                    "main_income_type_code": code,
                    "main_income_type_label": label,
                    "semantic_key": semantic_key,
                    "value": values.get(columns[category], ""),
                    "source_cell": f"{columns[category]}{source_row}",
                    "source_id": "ESTAT-7171-2024",
                    "source_stat_inf_id": "000040490427",
                    "source_file": "data/raw/estat/000040490427.xlsx",
                    "source_sha256": raw_sha,
                    "cross_system_status": CROSS_SYSTEM_STATUS,
                    "cross_system_warning": CROSS_SYSTEM_WARNING,
                })
    finally:
        x.close()
    if len(rows) != 30:
        raise RuntimeError(f"expected 30 table-7-171 rows, got {len(rows)}")
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")


def main() -> None:
    write_csv(OUT_71411, extract_71411())
    write_csv(OUT_7171, extract_7171())


if __name__ == "__main__":
    main()
