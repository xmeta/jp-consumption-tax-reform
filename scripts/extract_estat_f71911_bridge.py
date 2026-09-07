#!/usr/bin/env python3
"""Extract the F71911 decile household-size/age bridge from official e-Stat XLSX.

The source table reports *persons* by household-size category.  Household size
"6_６人以上" is top-coded.  Therefore the exact mean household size is not
identified from this table alone.

For backward-compatible sensitivity work we expose:
  household_size_proxy = mean size obtained by treating every 6+ household as 6.

Because 6 is the smallest possible size in that top-coded category, this is a
lower-side proxy for the mean household size implied by F71911.  It is not an
estimate of the true mean.  Alternative top-code assumptions 7, 8, and 10 are
also reported for sensitivity analysis.

The age columns on the all-household-size row directly identify the published
share of persons aged 65+ within each income decile (up to source rounding).
"""
from __future__ import annotations

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
RAW = ROOT / "data/raw/estat/000040490431.xlsx"
OUT_DETAIL = ROOT / "data/derived/estat_71911_decile_household_size_age_bridge.csv"
OUT_COMPAT = ROOT / "data/derived/income_tax_bridge_deciles_2024.csv"

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
CELL_RE = re.compile(r"^([A-Z]+)([0-9]+)$")
DECILE_RE = re.compile(r"^R(0[1-9]|10)_十分位([1-9]|10)$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class XlsxStream:
    def __init__(self, path: Path):
        self.z = ZipFile(path)
        root = ET.fromstring(self.z.read("xl/sharedStrings.xml"))
        self.shared = [
            "".join(t.text or "" for t in si.iter(M + "t"))
            for si in root.findall(M + "si")
        ]

    def close(self):
        self.z.close()

    def cell_text(self, cell: ET.Element) -> str:
        v = cell.find(M + "v")
        if v is None:
            return ""
        raw = v.text or ""
        if cell.attrib.get("t") == "s":
            return self.shared[int(raw)]
        return raw

    def rows(self):
        with self.z.open("xl/worksheets/sheet1.xml") as f:
            for _, row in ET.iterparse(f, events=("end",)):
                if row.tag != M + "row":
                    continue
                rn = int(row.attrib["r"])
                vals = {}
                for cell in row.findall(M + "c"):
                    ref = cell.attrib["r"]
                    col = CELL_RE.match(ref).group(1)
                    vals[col] = self.cell_text(cell)
                yield rn, vals
                row.clear()


def render(fields, rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def fmt(x: float) -> str:
    return f"{x:.12g}"


def extract():
    x = XlsxStream(RAW)
    selected = {d: {} for d in range(1, 11)}
    try:
        for rn, vals in x.rows():
            if rn < 8:
                continue
            if vals.get("E") != "0_平均":
                continue
            if vals.get("I") != "0_平均":
                continue
            if vals.get("M") != "00_平均":
                continue
            m = DECILE_RE.match(vals.get("K", ""))
            if not m:
                continue
            decile = int(m.group(2))
            g = vals.get("G", "")
            if g == "0_平均":
                selected[decile]["overall"] = {
                    "row": rn,
                    "label": vals["K"],
                    "total": float(vals["O"]),
                    "total_cell": f"O{rn}",
                    "age65_74": float(vals.get("V") or 0),
                    "age65_74_cell": f"V{rn}",
                    "age75_84": float(vals.get("W") or 0),
                    "age75_84_cell": f"W{rn}",
                    "age85p": float(vals.get("X") or 0),
                    "age85p_cell": f"X{rn}",
                }
            else:
                code = g.split("_", 1)[0]
                if code in {"1", "2", "3", "4", "5", "6"}:
                    selected[decile][int(code)] = {
                        "row": rn,
                        "label": g,
                        "persons": float(vals["O"]),
                        "cell": f"O{rn}",
                    }
    finally:
        x.close()

    raw_sha = sha256(RAW)
    detail = []
    compat = []

    for d in range(1, 11):
        rec = selected[d]
        if set(rec) != {"overall", 1, 2, 3, 4, 5, 6}:
            raise RuntimeError(f"F71911 incomplete decile {d}: keys={sorted(rec, key=str)}")

        overall = rec["overall"]
        persons_by_size = {s: rec[s]["persons"] for s in range(1, 7)}
        sum_persons = sum(persons_by_size.values())
        rounding_diff = sum_persons - overall["total"]

        exact_households_1_5 = sum(persons_by_size[s] / s for s in range(1, 6))

        proxy_by_topcode = {}
        household_count_by_topcode = {}
        for assumed_size in (6, 7, 8, 10):
            hh = exact_households_1_5 + persons_by_size[6] / assumed_size
            household_count_by_topcode[assumed_size] = hh
            proxy_by_topcode[assumed_size] = sum_persons / hh

        senior_persons = (
            overall["age65_74"] + overall["age75_84"] + overall["age85p"]
        )
        senior_share = senior_persons / overall["total"]

        row = {
            "decile": d,
            "decile_label": overall["label"],
            "total_persons_reported": fmt(overall["total"]),
            "total_persons_source_cell": overall["total_cell"],
            "sum_household_size_category_persons": fmt(sum_persons),
            "size_category_rounding_difference_persons": fmt(rounding_diff),
            "persons_size1": fmt(persons_by_size[1]),
            "persons_size1_source_cell": rec[1]["cell"],
            "persons_size2": fmt(persons_by_size[2]),
            "persons_size2_source_cell": rec[2]["cell"],
            "persons_size3": fmt(persons_by_size[3]),
            "persons_size3_source_cell": rec[3]["cell"],
            "persons_size4": fmt(persons_by_size[4]),
            "persons_size4_source_cell": rec[4]["cell"],
            "persons_size5": fmt(persons_by_size[5]),
            "persons_size5_source_cell": rec[5]["cell"],
            "persons_size6plus": fmt(persons_by_size[6]),
            "persons_size6plus_source_cell": rec[6]["cell"],
            "persons_size6plus_share": fmt(persons_by_size[6] / sum_persons),
            "implied_households_sizes1_to5": fmt(exact_households_1_5),
            "implied_households_if_6plus_eq6": fmt(household_count_by_topcode[6]),
            "household_size_proxy": fmt(proxy_by_topcode[6]),
            "household_size_proxy_topcode6": fmt(proxy_by_topcode[6]),
            "household_size_proxy_topcode7": fmt(proxy_by_topcode[7]),
            "household_size_proxy_topcode8": fmt(proxy_by_topcode[8]),
            "household_size_proxy_topcode10": fmt(proxy_by_topcode[10]),
            "household_size_proxy_status": "SENSITIVITY_PROXY_TOPCODE_6PLUS_AS_6",
            "household_size_proxy_interpretation":
                "lower-side proxy; exact mean not identified because 6+ is top-coded",
            "age65_74_persons": fmt(overall["age65_74"]),
            "age65_74_source_cell": overall["age65_74_cell"],
            "age75_84_persons": fmt(overall["age75_84"]),
            "age75_84_source_cell": overall["age75_84_cell"],
            "age85plus_persons": fmt(overall["age85p"]),
            "age85plus_source_cell": overall["age85p_cell"],
            "senior_persons_65p": fmt(senior_persons),
            "senior_share_65p": fmt(senior_share),
            "senior_share_status": "PUBLISHED_AGGREGATE_RATIO",
            "source_id": "ESTAT-7191-1-2024",
            "source_stat_inf_id": "000040490431",
            "source_file": "data/raw/estat/000040490431.xlsx",
            "source_sha256": raw_sha,
        }
        detail.append(row)

        compat.append({
            "decile": d,
            "household_size_proxy": fmt(proxy_by_topcode[6]),
            "household_size_proxy_status": "SENSITIVITY_PROXY_TOPCODE_6PLUS_AS_6",
            "household_size_proxy_topcode7": fmt(proxy_by_topcode[7]),
            "household_size_proxy_topcode8": fmt(proxy_by_topcode[8]),
            "household_size_proxy_topcode10": fmt(proxy_by_topcode[10]),
            "senior_share_65p": fmt(senior_share),
            "senior_share_status": "PUBLISHED_AGGREGATE_RATIO",
            "source_id": "ESTAT-7191-1-2024",
            "source_stat_inf_id": "000040490431",
            "source_file": "data/raw/estat/000040490431.xlsx",
            "source_sha256": raw_sha,
            "household_size_source_cells":
                ";".join(rec[s]["cell"] for s in range(1, 7)),
            "senior_share_source_cells":
                ";".join([
                    overall["total_cell"],
                    overall["age65_74_cell"],
                    overall["age75_84_cell"],
                    overall["age85p_cell"],
                ]),
        })

    return detail, compat


def specs():
    detail, compat = extract()
    return [
        (OUT_DETAIL, list(detail[0]), detail),
        (OUT_COMPAT, list(compat[0]), compat),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    out_specs = specs()
    if args.check:
        stale = []
        for path, fields, rows in out_specs:
            expected = render(fields, rows)
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if expected != actual:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            print("ERROR: stale F71911 bridge outputs: " + ", ".join(stale))
            sys.exit(1)
        print("F71911 bridge extracts: current (20 output rows)")
        return

    for path, fields, rows in out_specs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(fields, rows), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
