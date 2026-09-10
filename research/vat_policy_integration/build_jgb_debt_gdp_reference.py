#!/usr/bin/env python3
"""Build a static JGB-financing-to-nominal-GDP reference from official ESRI SNA."""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from decimal import Decimal
import argparse
import csv
import io

ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "data/source_catalog.csv"
FISCAL = ROOT / "data/derived/vat_policy_fiscal_replacement_reference.csv"
OUT = ROOT / "data/derived/vat_jgb_debt_gdp_reference.csv"
SOURCE_ID = "ESRI-SNA-2024-NOMINAL-GDP-FISCAL-YEAR"
EXPECTED_SHA = "a0cd9e5e973360e704c2a4abbe3208239884559310d4df045c345cc3b9f17ae5"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def fmt_decimal(x):
    return format(x.normalize(), "f")
def xlsx_cells(path):
    with ZipFile(path) as z:
        strings = []
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{{{NS}}}si"):
            strings.append(
                "".join(t.text or "" for t in si.iter(f"{{{NS}}}t"))
            )
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        cells = {}
        for cell in sheet.iter(f"{{{NS}}}c"):
            ref = cell.attrib["r"]
            value_node = cell.find(f"{{{NS}}}v")
            if value_node is None:
                cells[ref] = ""
                continue
            raw = value_node.text or ""
            cells[ref] = strings[int(raw)] if cell.attrib.get("t") == "s" else raw
        return cells


def build():
    catalog = {r["source_id"]: r for r in read_csv(CAT)}
    source = catalog[SOURCE_ID]
    assert source["sha256"] == EXPECTED_SHA
    cells = xlsx_cells(ROOT / source["raw_file"])

    assert cells["A1"] == "1. Gross Domestic Product (Expenditure approach: at current prices)"
    assert cells["A3"] == "Fiscal Year"
    assert cells["A4"] == "(Billion Yen)"
    assert cells["AF6"] == "2024"
    assert cells["A48"] == "5.  Gross domestic product (expenditure approach) (1+2+3+4)"
    nominal_gdp_billion_yen = Decimal(cells["AF48"])
    assert nominal_gdp_billion_yen == Decimal("642414.69999999995")
    nominal_gdp_yen = Decimal("642414.7") * Decimal("1000000000")

    fiscal = {r["scenario_id"]: r for r in read_csv(FISCAL)}
    jgb_yen = Decimal(fiscal["full_abolition_jgb"]["full_jgb_financing_reference_yen"])
    assert jgb_yen == Decimal("25021206715000")
    ratio = jgb_yen / nominal_gdp_yen
    pct = ratio * Decimal("100")
    rows = []
    for scenario_id, fr in fiscal.items():
        if scenario_id == "full_abolition_jgb":
            amount = str(int(jgb_yen))
            ratio_value = fmt_decimal(ratio.quantize(Decimal("0.000000000001")))
            pct_value = fmt_decimal(pct.quantize(Decimal("0.000000001")))
            status = "STATIC_INCREMENTAL_JGB_FINANCING_SHARE_OF_FY2024_NOMINAL_GDP"
        else:
            amount = ""
            ratio_value = ""
            pct_value = ""
            status = "NOT_APPLICABLE_OR_JGB_SHARE_NOT_DEFINED_FOR_THIS_SCENARIO"
        rows.append({
            "scenario_id": scenario_id,
            "fy2024_nominal_gdp_yen": str(int(nominal_gdp_yen)),
            "full_jgb_financing_reference_yen": amount,
            "static_incremental_jgb_financing_share_of_fy2024_nominal_gdp": ratio_value,
            "static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp": pct_value,
            "debt_gdp_reference_status": status,
            "source_id": SOURCE_ID,
            "source_locator": "Amount!AF48; FY2024 nominal GDP, billion yen",
            "note": (
                "Static gross financing amount divided by FY2024 nominal GDP. "
                "This is not the change in observed debt/GDP: it excludes baseline debt stock, "
                "redemptions, other borrowing, financial assets, GDP feedback, interest and time dynamics."
            ),
        })
    assert len(rows) == 8
    return rows


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
            "JGB debt/GDP reference: current "
            "(FY2024 nominal GDP parsed from ESRI XLSX; full-JGB static financing share only)"
        )
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(expected, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
