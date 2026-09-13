#!/usr/bin/env python3
"""Build observed population/welfare/productivity diagnostics for Issue #131."""
from __future__ import annotations

import argparse
import csv
import io
import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data/source_catalog.csv"
OUT = ROOT / "data/derived/population_welfare_historical_diagnostics.csv"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def xlsx_cells(path, sheet_name):
    with ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            strings = [
                "".join(t.text or "" for t in si.iter(f"{{{NS}}}t"))
                for si in root.findall(f"{{{NS}}}si")
            ]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        relroot = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in relroot.findall(f"{{{PKG}}}Relationship")}
        sheet = next(s for s in wb.find(f"{{{NS}}}sheets") if s.attrib["name"] == sheet_name)
        xml = ET.fromstring(z.read("xl/" + rels[sheet.attrib[f"{{{REL}}}id"]]))
        cells = {}
        for cell in xml.findall(f".//{{{NS}}}c"):
            node = cell.find(f"{{{NS}}}v")
            raw = "" if node is None else (node.text or "")
            cells[cell.attrib["r"]] = strings[int(raw)] if raw and cell.attrib.get("t") == "s" else raw
        return cells


def population(path):
    text = path.read_text(encoding="utf-8").translate(
        str.maketrans("０１２３４５６７８９", "0123456789")
    )
    m = re.search(r"総人口は(\d+)億(\d+)万(\d+)千人", text)
    if not m:
        raise RuntimeError(f"population not found: {path}")
    oku, man, sen = map(int, m.groups())
    return oku * 100_000_000 + man * 10_000 + sen * 1_000


def metric(metric_id, period, value, unit, stat_unit, source_ids, status, note):
    return {
        "metric_id": metric_id,
        "reference_period": period,
        "value": "" if value is None else f"{value:.12g}",
        "unit": unit,
        "statistical_unit": stat_unit,
        "source_ids": source_ids,
        "identification_status": status,
        "optimizer_usable": "false",
        "note": note,
    }


def build():
    catalog = {r["source_id"]: r for r in read_csv(CAT)}
    ids = {
        "p23": "STAT-POP-EST-2023", "p24": "STAT-POP-EST-2024",
        "real": "ESRI-SNA-2024-REAL-GDP-CY", "nom": "ESRI-SNA-2024-NOMINAL-GDP-CY",
        "defl": "ESRI-SNA-2024-GDP-DEFLATOR-CY", "emp": "ESRI-SNA-2024-EMPLOYMENT-HOURS-CY",
        "hours": "ESRI-HOURS-WORKED-EMPLOYED-2024", "cpi": "ESTAT-CPI-2024-NATIONAL-ALL-ITEMS",
        "median": "ESTAT-7171-2024", "gini": "MHLW-REDISTRIBUTION-2023",
        "poverty": "MHLW-CSLC-2022-POVERTY",
    }
    for sid in ids.values():
        if sid not in catalog:
            raise RuntimeError(f"missing source: {sid}")
    raw = {k: ROOT / catalog[v]["raw_file"] for k, v in ids.items()}
    pop23, pop24 = population(raw["p23"]), population(raw["p24"])
    real = xlsx_cells(raw["real"], "Amount")
    nominal = xlsx_cells(raw["nom"], "Amount")
    deflator = xlsx_cells(raw["defl"], "Amount")
    employed = xlsx_cells(raw["emp"], "C.Y(1)Employed")
    hours = xlsx_cells(raw["hours"], "就業者の労働時間数")
    cpi = xlsx_cells(raw["cpi"], "a0411")

    # Verified official cells from the registered source revisions.
    real23, real24 = float(real["AE48"]), float(real["AF48"])
    nominal24 = float(nominal["AF48"])
    gdp_def24 = float(deflator["AF44"])
    emp23, emp24 = float(employed["AE39"]) * 10_000, float(employed["AF39"]) * 10_000
    h23, h24 = float(hours["T45"]), float(hours["U45"])
    if not (cpi["B25"].strip() == "2024" and float(cpi["C25"]) == 108.5):
        raise RuntimeError("unexpected 2024 CPI anchor")
    cpi24 = float(cpi["C25"])

    med = read_csv(ROOT / "data/derived/estat_7171_main_income_disposable_quantiles_2024.csv")
    median_row = next(r for r in med if r["measure_key"] == "p50" and r["semantic_key"] == "total")
    median_k_yen = float(median_row["value"])

    # Published PDF anchors are fixed by the registered raw files, source
    # locators, source-catalog hashes, and repository manifest. Keep this
    # source-integrity builder standard-library-only so CI needs no PDF package.
    disposable_gini = 0.3233
    poverty_line_k_yen = 1270.0
    poverty_rate = 0.154

    g_y = real24 / real23 - 1.0
    g_n = pop24 / pop23 - 1.0
    g_pc = (1.0 + g_y) / (1.0 + g_n) - 1.0
    total_h24 = emp24 * h24
    y_pc24 = real24 * 1_000_000_000 / pop24
    q24 = real24 * 1_000_000_000 / total_h24
    u24 = total_h24 / pop24
    identity_residual = y_pc24 - q24 * u24
    median_real = median_k_yen / (cpi24 / 100.0)
    observed = "OBSERVED_HISTORICAL_DIAGNOSTIC_NOT_CAUSAL_POLICY_EFFECT"

    rows = [
        metric("population_total", "2023-10-01", pop23, "persons", "resident population", ids["p23"], observed, "Observed demographic state."),
        metric("population_total", "2024-10-01", pop24, "persons", "resident population", ids["p24"], observed, "Observed demographic state."),
        metric("real_gdp", "2024CY", real24, "billion_2020_yen", "national economy", ids["real"], observed, "Chain-linked real GDP."),
        metric("nominal_gdp", "2024CY", nominal24, "billion_yen", "national economy", ids["nom"], observed, "Calendar-year nominal GDP."),
        metric("gdp_deflator", "2024CY", gdp_def24, "index_2020_100", "national economy", ids["defl"], observed, "Not used as household-income deflator."),
        metric("cpi_all_items", "2024CY", cpi24, "index_2020_100", "household prices", ids["cpi"], observed, "Household purchasing-power deflator diagnostic."),
    ]
    rows += [
        metric("real_gdp_growth", "2023CY_to_2024CY", g_y, "ratio", "national economy", ids["real"], observed, "Aggregate growth diagnostic."),
        metric("population_growth", "2023-10-01_to_2024-10-01", g_n, "ratio", "resident population", f"{ids['p23']};{ids['p24']}", observed, "Observed demographic change; not policy-fixed."),
        metric("real_gdp_per_capita_growth", "2023_to_2024", g_pc, "ratio", "resident population", f"{ids['real']};{ids['p23']};{ids['p24']}", observed, "Exact identity (1+gY)/(1+gN)-1."),
        metric("employed_persons", "2024CY", emp24, "persons", "employed persons", ids["emp"], observed, "SNA employed-person total."),
        metric("hours_per_employed_person", "2024CY", h24, "hours_per_year", "employed persons", ids["hours"], observed, "Dedicated employed-person hours reference series."),
        metric("total_hours_worked", "2024CY", total_h24, "hours", "employed persons", f"{ids['emp']};{ids['hours']}", observed, "Employed persons times hours per employed person."),
        metric("real_gdp_per_capita", "2024CY", y_pc24, "2020_yen_per_person", "resident population", f"{ids['real']};{ids['p24']}", observed, "Population-normalized production, not welfare."),
        metric("real_gdp_per_hour", "2024CY", q24, "2020_yen_per_hour", "employed-person hours", f"{ids['real']};{ids['emp']};{ids['hours']}", observed, "Historical productivity diagnostic; no VAT causal attribution."),
        metric("hours_per_resident", "2024CY", u24, "hours_per_person", "resident population", f"{ids['p24']};{ids['emp']};{ids['hours']}", observed, "Labour-utilisation decomposition term."),
        metric("gdp_person_productivity_identity_residual", "2024CY", identity_residual, "2020_yen_per_person", "derived identity", f"{ids['real']};{ids['p24']};{ids['emp']};{ids['hours']}", observed, "Must be zero: GDP/person = GDP/hour * hours/person."),
    ]
    rows += [
        metric("median_equivalized_disposable_income", "2024", median_k_yen, "thousand_yen", "published all-household quantile", ids["median"], "OBSERVED_HOUSEHOLD_QUANTILE_NOT_HEADLINE_PERSON_WEIGHTED_EFFECT", "Published NSFCW household median; not the person-weighted headline policy estimand."),
        metric("median_real_equivalized_disposable_income", "2024", median_real, "thousand_2020_yen", "published all-household quantile", f"{ids['median']};{ids['cpi']}", "DESCRIPTIVE_DEFLATED_HOUSEHOLD_QUANTILE_NOT_CAUSAL", "Uses CPI; no mixed-frequency policy interpolation."),
        metric("equivalized_disposable_income_gini", "2023_survey", disposable_gini, "index_0_1", "household members", ids["gini"], observed, "MHLW person-unit equivalized disposable-income Gini."),
        metric("relative_poverty_line", "2021_income", poverty_line_k_yen, "thousand_yen", "household members", ids["poverty"], observed, "Half the median equivalized disposable income."),
        metric("relative_poverty_rate", "2021_income", poverty_rate, "ratio", "household members", ids["poverty"], observed, "Published incidence; not FGT2."),
        metric("fgt2_relative", "2021_income", None, "index", "household members", ids["poverty"], "NOT_IDENTIFIED_FROM_AGGREGATE_PUBLICATION", "Published aggregate data do not identify the squared poverty-gap distribution."),
    ]
    if not (g_y < 0 < g_pc):
        raise RuntimeError("expected aggregate-negative/per-capita-positive 2023-2024 diagnostic")
    if abs(identity_residual) > 1e-8:
        raise RuntimeError("GDP/person decomposition identity failed")
    return rows


def render(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    return out.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            raise SystemExit(f"stale generated artifact: {OUT.relative_to(ROOT)}")
        print("population/welfare historical diagnostics: current")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
