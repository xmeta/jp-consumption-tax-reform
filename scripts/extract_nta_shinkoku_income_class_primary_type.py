#!/usr/bin/env python3
"""Extract the 2024 NTA positive-self-assessed-balance income-class x primary-type cross-tab.

Source of record
----------------
NTA 2024 Sample Survey for Self-Assessment Income Tax, Table 2,
"Income Type Table", official XLSX R06_02.xlsx.

The survey target population is persons with positive self-assessed income tax.
The income-class cells are survey-based population estimates.  They are not
filer microdata and they are not an observed mapping to F71561 equivalized
household-income deciles.

A companion official PDF is retained only as a visual cross-check source.
"""
from pathlib import Path
from zipfile import ZipFile
import argparse
import csv
import io
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "data/raw/nta/nta_2024_shinkoku_sample_table2.xlsx"
CATALOG = ROOT / "data/source_catalog.csv"
STAGE2 = ROOT / "data/derived/nta_primary_type_stage2_2024.csv"
OUT = (
    ROOT
    / "data/derived"
    / "nta_positive_self_assessed_balance_income_class_primary_type_2024.csv"
)

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
CELL_RE = re.compile(r"^([A-Z]+)([0-9]+)$")

CATEGORIES = [
    ("business", "事業所得者", 37, 62),
    ("real_estate", "不動産所得者", 72, 97),
    ("salary", "給与所得者", 100, 125),
    ("miscellaneous", "雑所得者", 135, 160),
    ("other", "他の区分に該当しない所得者", 163, 188),
]

# The 25 classes in Table 2.  Bounds are stated only to support transparent
# mapping/sensitivity work later; the first class has no asserted lower bound.
UPPER_YEN = [
    700_000,
    1_000_000,
    1_500_000,
    2_000_000,
    2_500_000,
    3_000_000,
    4_000_000,
    5_000_000,
    6_000_000,
    7_000_000,
    8_000_000,
    10_000_000,
    12_000_000,
    15_000_000,
    20_000_000,
    30_000_000,
    50_000_000,
    100_000_000,
    200_000_000,
    500_000_000,
    1_000_000_000,
    2_000_000_000,
    5_000_000_000,
    10_000_000_000,
    None,
]


class Xlsx:
    def __init__(self, path):
        self.z = ZipFile(path)
        if "xl/sharedStrings.xml" in self.z.namelist():
            root = ET.fromstring(self.z.read("xl/sharedStrings.xml"))
            self.shared = [
                "".join(t.text or "" for t in si.iter(M + "t"))
                for si in root.findall(M + "si")
            ]
        else:
            self.shared = []

        wb = ET.fromstring(self.z.read("xl/workbook.xml"))
        rels = ET.fromstring(self.z.read("xl/_rels/workbook.xml.rels"))
        by_rid = {
            r.attrib["Id"]: r.attrib["Target"]
            for r in rels.findall(REL + "Relationship")
        }
        self.targets = {}
        for s in wb.find(M + "sheets"):
            target = by_rid[s.attrib[RID]]
            if target.startswith("/"):
                target = target.lstrip("/")
            else:
                target = "xl/" + target
            self.targets[s.attrib["name"]] = target

    def cell_value(self, c):
        typ = c.attrib.get("t")
        if typ == "inlineStr":
            return "".join(t.text or "" for t in c.iter(M + "t"))
        v = c.find(M + "v")
        if v is None:
            return ""
        raw = v.text or ""
        return self.shared[int(raw)] if typ == "s" else raw

    def rows(self, sheet_name):
        root = ET.fromstring(self.z.read(self.targets[sheet_name]))
        out = {}
        for row in root.iter(M + "row"):
            rn = int(row.attrib["r"])
            vals = {}
            for c in row.findall(M + "c"):
                col = CELL_RE.match(c.attrib["r"]).group(1)
                vals[col] = self.cell_value(c)
            out[rn] = vals
        return out

    def close(self):
        self.z.close()


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def normalize_label(s):
    return (
        s.replace("\u3000", " ")
        .replace("〃", "")
        .strip()
    )


def integer_cell(v):
    if v in ("", "-", None):
        return 0
    return int(float(v))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def build():
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    xsrc = catalog["NTA-2024-SHINKOKU-T2-XLSX"]
    psrc = catalog["NTA-2024-SHINKOKU-T2-PDF"]

    x = Xlsx(XLSX)
    try:
        rows = x.rows("第２表")
    finally:
        x.close()

    stage2 = {
        r["primary_income_type"]: int(r["positive_self_assessed_balance_persons_exact"])
        for r in read_csv(STAGE2)
    }

    total_rows = list(range(9, 34))
    if len(total_rows) != 25 or len(UPPER_YEN) != 25:
        raise RuntimeError("income class definition count mismatch")

    category_totals = {}
    for category, _, _, total_row in CATEGORIES:
        category_totals[category] = integer_cell(rows[total_row].get("D"))
        if category_totals[category] != stage2[category]:
            raise RuntimeError(
                f"{category}: Table2 total {category_totals[category]} "
                f"!= annual exact positive-self-assessed-balance count {stage2[category]}"
            )

    out = []
    previous_upper = None
    for i, total_row in enumerate(total_rows):
        raw_label = rows[total_row].get("B", "")
        income_total = integer_cell(rows[total_row].get("D"))
        if income_total <= 0:
            raise RuntimeError(f"class {i+1}: non-positive total")

        category_values = []
        for category, ja, start_row, total_cat_row in CATEGORIES:
            source_row = start_row + i
            label = rows[source_row].get("C", "")
            persons = integer_cell(rows[source_row].get("D"))
            category_values.append(persons)

            upper = UPPER_YEN[i]
            out.append({
                "income_class_index": i + 1,
                "income_class_label": normalize_label(raw_label),
                "lower_bound_yen_exclusive":
                    "" if previous_upper is None else previous_upper,
                "upper_bound_yen_inclusive": "" if upper is None else upper,
                "is_topcoded": "True" if upper is None else "False",
                "primary_income_type": category,
                "primary_income_type_ja": ja,
                "positive_self_assessed_balance_persons_estimated": persons,
                "source_cell": f"D{source_row}",
                "source_income_class_label_cell": f"C{source_row}",
                "source_income_class_label": normalize_label(label),
                "income_class_positive_self_assessed_balance_total_estimated": income_total,
                "income_class_total_source_cell": f"D{total_row}",
                "category_positive_self_assessed_balance_total": category_totals[category],
                "category_total_source_cell": f"D{total_cat_row}",
                "share_within_income_class":
                    f"{persons / income_total:.12g}",
                "share_within_primary_type":
                    f"{persons / category_totals[category]:.12g}",
                "target_population":
                    "NTA Sample Survey population: persons with positive self-assessed income tax",
                "cell_nature":
                    "SURVEY_ESTIMATED_POPULATION_CELL",
                "source_id_xlsx": "NTA-2024-SHINKOKU-T2-XLSX",
                "source_file_xlsx": xsrc["raw_file"],
                "source_sha256_xlsx": xsrc["sha256"],
                "visual_source_id_pdf": "NTA-2024-SHINKOKU-T2-PDF",
                "visual_source_file_pdf": psrc["raw_file"],
                "visual_source_sha256_pdf": psrc["sha256"],
                "evidence_status":
                    "REPRODUCED_OFFICIAL_SURVEY_ESTIMATE_CROSSTAB",
                "identification_warning":
                    "NTA total-income class is not F71561 equivalized disposable-income decile; any bridge requires an explicit transport assumption",
            })

        if sum(category_values) != income_total:
            raise RuntimeError(
                f"class {i+1}: category sum {sum(category_values)} "
                f"!= total {income_total}"
            )
        previous_upper = UPPER_YEN[i]

    if len(out) != 125:
        raise RuntimeError(f"expected 125 rows, got {len(out)}")

    # Grand total is the exact sum of the five benchmarked category totals.
    if sum(category_totals.values()) != 5_158_260:
        raise RuntimeError(
            f"unexpected grand total {sum(category_totals.values())}"
        )

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    rows = build()
    expected = render(rows)
    if args.check:
        actual = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if actual != expected:
            print(
                "ERROR: stale NTA positive-self-assessed-balance income-class cross-tab"
            )
            sys.exit(1)
        print(
            "NTA positive-self-assessed-balance income-class x primary-type cross-tab: "
            "current (25 classes x 5 types = 125 rows)"
        )
        return

    OUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
