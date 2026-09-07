#!/usr/bin/env python3
"""Extract reproducible income-tax research tables from official e-Stat XLSX.

No spreadsheet library is required. The raw XLSX files are treated as ZIP/XML
containers and are never modified.

Inputs
------
data/raw/estat/000040490416.xlsx  e-Stat table 7-153-1
data/raw/estat/000040490419.xlsx  e-Stat table 7-156-1

Outputs
-------
data/derived/estat_71531_deciles_long.csv
data/derived/estat_71561_household_types.csv
data/derived/estat_71561_deciles_long.csv
data/derived/income_tax_household_type_leaf_deciles_2024.csv
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile
import argparse
import csv
import hashlib
import io
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/estat"
DERIVED = ROOT / "data/derived"

F71531 = RAW / "000040490416.xlsx"
F71561 = RAW / "000040490419.xlsx"

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

DECILE_RE = re.compile(r"^R(0[1-9]|10)_十分位([1-9]|10)$")
CELL_RE = re.compile(r"^([A-Z]+)([0-9]+)$")

COMPAT_COMPONENTS = {
    "21": "cash_income_kY",
    "211": "wage_income_kY",
    "21101": "head_wage_kY",
    "21102": "spouse_wage_kY",
    "21103": "other_member_wage_kY",
    "212": "business_kY",
    "213": "interest_dividend_kY",
    "214": "public_pension_kY",
    "21401": "head_public_pension_kY",
    "21402": "spouse_public_pension_kY",
    "21403": "other_member_public_pension_kY",
    "215": "other_social_security_kY",
    "216": "enterprise_private_pension_kY",
    "811": "income_tax_kY",
    "812": "resident_tax_kY",
    "813": "public_pension_contribution_kY",
    "814": "health_insurance_contribution_kY",
    "815": "long_term_care_contribution_kY",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def col_to_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def num_to_col(n: int) -> str:
    chars = []
    while n:
        n, rem = divmod(n - 1, 26)
        chars.append(chr(65 + rem))
    return "".join(reversed(chars))


def split_code_label(text: str) -> tuple[str, str]:
    if "_" not in text:
        return text, ""
    return text.split("_", 1)


def parse_numeric(raw: str) -> tuple[str, str]:
    """Return numeric string and missing marker.

    Numeric is kept as text for exact round-tripping of source values.
    """
    if raw in {"", "-", "X"}:
        return "", raw
    try:
        float(raw)
    except ValueError:
        return "", raw
    return raw, ""


class XlsxStream:
    def __init__(self, path: Path):
        self.path = path
        self.z = ZipFile(path)
        self.shared = self._load_shared_strings()

    def close(self):
        self.z.close()

    def _load_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self.z.namelist():
            return []
        root = ET.fromstring(self.z.read("xl/sharedStrings.xml"))
        out = []
        for si in root.findall(M + "si"):
            out.append("".join(t.text or "" for t in si.iter(M + "t")))
        return out

    def cell_text(self, cell: ET.Element) -> str:
        typ = cell.attrib.get("t")
        if typ == "inlineStr":
            return "".join(t.text or "" for t in cell.iter(M + "t"))
        v = cell.find(M + "v")
        if v is None:
            return ""
        raw = v.text or ""
        if typ == "s":
            return self.shared[int(raw)]
        if typ == "b":
            return "1" if raw == "1" else "0"
        return raw

    def rows(self):
        with self.z.open("xl/worksheets/sheet1.xml") as f:
            for _, row in ET.iterparse(f, events=("end",)):
                if row.tag != M + "row":
                    continue
                row_num = int(row.attrib["r"])
                vals = {}
                for cell in row.findall(M + "c"):
                    ref = cell.attrib["r"]
                    col = CELL_RE.match(ref).group(1)
                    vals[col] = self.cell_text(cell)
                yield row_num, vals
                row.clear()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def render_csv(fieldnames: list[str], rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def decile_from_header(text: str) -> int | None:
    m = DECILE_RE.match(text)
    return int(m.group(2)) if m else None


def extract_71531():
    x = XlsxStream(F71531)
    try:
        headers = {}
        data_rows = []
        for r, vals in x.rows():
            if r == 6:
                for col, value in vals.items():
                    d = decile_from_header(value)
                    if d is not None:
                        headers[col] = (d, value)
            elif r >= 8:
                data_rows.append((r, vals))
    finally:
        x.close()

    if sorted(d for d, _ in headers.values()) != list(range(1, 11)):
        raise RuntimeError("7-153-1 decile headers not found exactly once")

    raw_sha = sha256(F71531)
    rows = []
    for source_row, vals in data_rows:
        reported_item = vals.get("C", "")
        component_text = vals.get("E", "")
        component_code, component_label = split_code_label(component_text)
        unit = vals.get("F", "")
        for col, (decile, decile_label) in sorted(
            headers.items(), key=lambda kv: kv[1][0]
        ):
            raw = vals.get(col, "")
            numeric, marker = parse_numeric(raw)
            rows.append({
                "decile": decile,
                "decile_code": decile_label.split("_", 1)[0],
                "decile_label": decile_label,
                "reported_item": reported_item,
                "income_component_code": component_code,
                "income_component_label": component_label,
                "unit": unit,
                "raw_value": raw,
                "numeric_value": numeric,
                "missing_marker": marker,
                "source_cell": f"{col}{source_row}",
                "source_row": source_row,
                "source_column": col,
                "source_id": "ESTAT-7153-1-2024",
                "source_stat_inf_id": "000040490416",
                "source_file": "data/raw/estat/000040490416.xlsx",
                "source_sha256": raw_sha,
            })
    return rows


def household_type_metadata(header_by_col: dict[str, str]):
    originals = []
    parsed = {}
    for col, text in header_by_col.items():
        code, label = split_code_label(text)
        is_recap = code.startswith("R")
        parsed[code] = (col, text, label, is_recap)
        if not is_recap:
            originals.append(code)

    originals_set = set(originals)
    rows = []
    for code, (col, text, label, is_recap) in parsed.items():
        parent = ""
        is_leaf = False
        if not is_recap:
            parents = [
                p for p in originals_set
                if p != code and code.startswith(p)
            ]
            parent = max(parents, key=len) if parents else ""
            children = [
                c for c in originals_set
                if c != code and c.startswith(code)
            ]
            is_leaf = len(children) == 0 and code != "00"
        rows.append({
            "household_type_code": code,
            "household_type": text,
            "household_type_label": label,
            "source_column": col,
            "source_header_cell": f"{col}6",
            "parent_code": parent,
            "hierarchy_depth": len(code),
            "is_recap": str(is_recap),
            "is_original_leaf": str(is_leaf),
            "source_id": "ESTAT-7156-1-2024",
            "source_stat_inf_id": "000040490419",
        })
    rows.sort(key=lambda r: col_to_num(r["source_column"]))
    return rows


def extract_71561():
    x = XlsxStream(F71561)
    try:
        household_headers = {}
        selected_rows = []
        for r, vals in x.rows():
            if r == 6:
                for cnum in range(col_to_num("K"), col_to_num("BG") + 1):
                    col = num_to_col(cnum)
                    value = vals.get(col, "")
                    if value:
                        household_headers[col] = value
            elif r >= 8:
                decile = decile_from_header(vals.get("D", ""))
                if decile is None:
                    continue
                if vals.get("F", "") != "00_平均":
                    continue
                selected_rows.append((r, decile, vals))
    finally:
        x.close()

    if len(household_headers) != 49:
        raise RuntimeError(
            f"expected 49 household-type columns, got {len(household_headers)}"
        )

    raw_sha = sha256(F71561)
    rows = []
    for source_row, decile, vals in selected_rows:
        decile_text = vals.get("D", "")
        reported_item = vals.get("G", "")
        component_text = vals.get("I", "")
        component_code, component_label = split_code_label(component_text)
        unit = vals.get("J", "")
        for col, household_type in household_headers.items():
            hcode, hlabel = split_code_label(household_type)
            raw = vals.get(col, "")
            numeric, marker = parse_numeric(raw)
            rows.append({
                "decile": decile,
                "decile_code": decile_text.split("_", 1)[0],
                "decile_label": decile_text,
                "asset_class": vals.get("F", ""),
                "reported_item": reported_item,
                "income_component_code": component_code,
                "income_component_label": component_label,
                "unit": unit,
                "household_type_code": hcode,
                "household_type": household_type,
                "household_type_label": hlabel,
                "raw_value": raw,
                "numeric_value": numeric,
                "missing_marker": marker,
                "source_cell": f"{col}{source_row}",
                "source_row": source_row,
                "source_column": col,
                "source_id": "ESTAT-7156-1-2024",
                "source_stat_inf_id": "000040490419",
                "source_file": "data/raw/estat/000040490419.xlsx",
                "source_sha256": raw_sha,
            })

    meta = household_type_metadata(household_headers)
    return rows, meta


def build_leaf_compat(long_rows: list[dict], meta_rows: list[dict]):
    leaf_types = {
        r["household_type"]
        for r in meta_rows
        if r["is_original_leaf"] == "True"
    }
    if len(leaf_types) != 14:
        raise RuntimeError(
            f"expected 14 structurally derived original leaves, got {len(leaf_types)}"
        )

    cells = defaultdict(dict)
    for r in long_rows:
        if r["household_type"] not in leaf_types:
            continue
        key = (int(r["decile"]), r["household_type"])
        if r["reported_item"] == "集計世帯数（概数）":
            cells[key]["household_count_approx"] = (
                r["numeric_value"], r["source_cell"], r["missing_marker"]
            )
        elif r["reported_item"] == "等価年間収入額":
            field = COMPAT_COMPONENTS.get(r["income_component_code"])
            if field:
                cells[key][field] = (
                    r["numeric_value"], r["source_cell"], r["missing_marker"]
                )

    rows = []
    mapped_fields = ["household_count_approx"] + list(COMPAT_COMPONENTS.values())
    for decile in range(1, 11):
        for htype in sorted(leaf_types, key=lambda s: s.split("_", 1)[0]):
            key = (decile, htype)
            hcode, hlabel = split_code_label(htype)
            out = {
                "decile": decile,
                "household_type": htype,
                "household_type_code": hcode,
                "household_type_label": hlabel,
                "source_id": "ESTAT-7156-1-2024",
                "source_stat_inf_id": "000040490419",
                "source_file": "data/raw/estat/000040490419.xlsx",
                "source_sha256": sha256(F71561),
            }
            for field in mapped_fields:
                value, cell, marker = cells[key].get(field, ("", "", ""))
                out[field] = value
                out[field + "_source_cell"] = cell
                out[field + "_missing_marker"] = marker
            rows.append(out)
    return rows


def output_specs():
    long31 = extract_71531()
    long61, meta = extract_71561()
    compat = build_leaf_compat(long61, meta)
    return [
        (
            DERIVED / "estat_71531_deciles_long.csv",
            list(long31[0]),
            long31,
        ),
        (
            DERIVED / "estat_71561_household_types.csv",
            list(meta[0]),
            meta,
        ),
        (
            DERIVED / "estat_71561_deciles_long.csv",
            list(long61[0]),
            long61,
        ),
        (
            DERIVED / "income_tax_household_type_leaf_deciles_2024.csv",
            list(compat[0]),
            compat,
        ),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    specs = output_specs()
    if args.check:
        stale = []
        for path, fields, rows in specs:
            expected = render_csv(fields, rows)
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual != expected:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            print("ERROR: stale e-Stat derived files: " + ", ".join(stale))
            sys.exit(1)
        print(
            "e-Stat income-tax extracts: current "
            f"({sum(len(x[2]) for x in specs):,} output rows)"
        )
        return

    for path, fields, rows in specs:
        write_csv(path, fields, rows)
        print(f"wrote {path.relative_to(ROOT)}: {len(rows):,} rows")


if __name__ == "__main__":
    main()
