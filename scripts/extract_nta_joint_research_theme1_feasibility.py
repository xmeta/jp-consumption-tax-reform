#!/usr/bin/env python3
"""Extract Theme-1 joint-research schema coverage and route feasibility."""
from __future__ import annotations

import csv
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/income_tax/nta_joint_research_theme1_sample.xlsx"
FIELD_OUT = ROOT / "data/derived/nta_joint_research_theme1_field_presence_2014_2024.csv"
ROUTE_OUT = ROOT / "data/derived/nta_joint_research_theme1_feasibility_2026.csv"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
YEAR_RE = re.compile(r"（(20\d{2})年）")

FIELDS = [
    ("joint_research_identifier", "専用識別番号"),
    ("tax_year", "課税年分"),
    ("filing_date", "申告年月日"),
    ("filing_type", "申告区分"),
    ("salary_receipt_class", "給与収入区分"),
    ("salary_receipts", "給与収入"),
    ("salary_income", "給与所得"),
    ("withholding_tax", "源泉徴収税額"),
    ("self_assessed_balance", "申告納税額"),
    ("prepayment_tax", "予定納税額"),
    ("third_installment_payment", "第３期分の税額（納める税金）"),
    ("third_installment_refund", "第３期分の税額（還付される税金）"),
    ("amended_return_tax_increase", "第３期分の税額の増加額"),
    ("unpaid_withholding_tax", "未納付の源泉所得税額"),
    ("social_insurance_deduction", "社会保険料控除"),
    ("spouse_deduction", "配偶者（特別）控除"),
    ("dependent_deduction", "扶養控除"),
    ("basic_deduction", "基礎控除"),
]


def shared_strings(zf: ZipFile) -> list[str]:
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in si.iter(f"{{{NS['m']}}}t"))
        for si in root.findall("m:si", NS)
    ]


def cell_text(cell: ET.Element, strings: list[str]) -> str:
    value = cell.find("m:v", NS)
    if value is None:
        return ""
    if cell.attrib.get("t") == "s":
        return strings[int(value.text or "0")]
    return value.text or ""


def year_fields() -> dict[int, list[str]]:
    with ZipFile(SOURCE) as zf:
        strings = shared_strings(zf)
        root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows = root.findall(".//m:sheetData/m:row", NS)
        by_number = {int(row.attrib["r"]): row for row in rows}
        result: dict[int, list[str]] = {}
        for row in rows:
            texts = [cell_text(cell, strings) for cell in row.findall("m:c", NS)]
            year = next(
                (int(match.group(1)) for text in texts if (match := YEAR_RE.search(text))),
                None,
            )
            if year is None:
                continue
            header = by_number.get(int(row.attrib["r"]) + 1)
            if header is None:
                raise RuntimeError(f"missing field row after {year}")
            result[year] = [cell_text(cell, strings) for cell in header.findall("m:c", NS)]
    expected = set(range(2014, 2025))
    if set(result) != expected:
        raise RuntimeError(f"unexpected Theme-1 years: {sorted(result)}")
    return result


def present(label: str, fields: list[str]) -> bool:
    return any(value.startswith(label) for value in fields)


def write_field_presence(by_year: dict[int, list[str]]) -> None:
    with FIELD_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow([
            "field_id", "field_label", "years_available", "years_missing",
            "year_count", "availability_status",
        ])
        for field_id, label in FIELDS:
            available = [year for year in sorted(by_year) if present(label, by_year[year])]
            missing = [year for year in sorted(by_year) if year not in available]
            writer.writerow([
                field_id,
                label,
                ";".join(map(str, available)),
                ";".join(map(str, missing)),
                len(available),
                "ALL_2014_2024" if not missing else "PARTIAL_PERIOD",
            ])


def route_rows() -> list[list[str]]:
    return [
        ["theme1_period", "AVAILABLE_2014_2024", "NTA-NTC-JOINT-RESEARCH-CALL6;NTA-NTC-JOINT-RESEARCH-THEME1-SAMPLE", "Return-side microdata are advertised for 2014-2024.", "No payroll-side universe is added."],
        ["return_longitudinal_identifier", "AVAILABLE_WITHIN_THEME1", "NTA-NTC-JOINT-RESEARCH-OVERVIEW;NTA-NTC-JOINT-RESEARCH-THEME1-SAMPLE", "Dedicated joint-research identifier plus repeated tax years supports within-return longitudinal analysis.", "Not an advertised cross-source payroll identifier."],
        ["salary_return_tax_flow", "MATERIAL_PARTIAL_IDENTIFICATION_GAIN", "NTA-NTC-JOINT-RESEARCH-THEME1-SAMPLE", "Salary receipts/income, source withholding, filing status, assessed balance, payment/refund and deductions coexist on return records.", "Does not observe non-filers or private-payroll year-end-adjustment status."],
        ["private_payroll_person_link", "NOT_IDENTIFIED", "NTA-NTC-JOINT-RESEARCH-THEME1-SAMPLE", "No Theme-1 field is documented as a Private Salary Survey person key.", "Do not infer payroll-to-return overlap from salary amounts, ranks or demographics."],
        ["external_statistical_microdata_linkage", "APPLICATION_POSSIBLE_NOT_PREAPPROVED", "NTA-NTC-JOINT-RESEARCH-FAQ", "Official FAQ permits proposals that match eligible statistical microdata for non-identifying statistical research.", "Actual data, linkage key, approval, processing time and any external-data fee remain application-specific."],
        ["applicant_eligibility", "FULL_TIME_ELIGIBLE_INSTITUTION_REQUIRED", "NTA-NTC-JOINT-RESEARCH-GUIDELINE;NTA-NTC-JOINT-RESEARCH-FAQ", "Academic individual-data applicants must be full-time researchers at an eligible public, independent, university or inter-university institution.", "A specific researcher's eligibility must be verified at application time; private-business affiliation alone is insufficient."],
        ["sample_field_universe", "SCHEMA_GATED", "NTA-NTC-JOINT-RESEARCH-FAQ", "Research is generally expected to use fields published in the sample schema.", "Unadvertised fields must not be assumed available."],
        ["secure_access", "WAKO_ONLY_APPROVAL_REQUIRED", "NTA-NTC-JOINT-RESEARCH-GUIDELINE;NTA-NTC-JOINT-RESEARCH-FAQ", "Approved individual-data users work on NTA-provided terminals at NTC Wako and are appointed visiting professors.", "Raw microdata and unreviewed intermediate outputs cannot be exported."],
        ["secure_access_hours", "WEEKDAYS_0930_1700_RESERVATION_REQUIRED", "NTA-NTC-JOINT-RESEARCH-FAQ", "Wako individual-data access is available on non-holiday weekdays from 09:30 to 17:00 with advance reservation.", "Travel and researcher-time costs are not quantified by the reviewed program materials."],
        ["maximum_use_period", "NORMALLY_UP_TO_3_YEARS", "NTA-NTC-JOINT-RESEARCH-GUIDELINE;NTA-NTC-JOINT-RESEARCH-FAQ", "The sixth-call regime normally caps approved use at three years, subject to the guideline's extension rules.", "Requested duration must still be the minimum necessary for the approved plan."],
        ["output_review", "NTA_PREPUBLICATION_REVIEW_REQUIRED", "NTA-NTC-JOINT-RESEARCH-GUIDELINE", "Research outputs must be reported to NTA before publication and pass consistency, confidentiality and disclosure checks.", "Approval of data use is not approval of any later scientific claim."],
        ["external_data_cost", "USER_BORNE_IF_APPLICABLE", "NTA-NTC-JOINT-RESEARCH-FAQ", "If linked statistical microdata incur fees, those costs are borne by the user.", "No project-wide cost estimate is inferred; Theme-1-only institutional/travel costs remain unpriced."],
        ["application_cadence", "ABOUT_ONCE_PER_YEAR", "NTA-NTC-JOINT-RESEARCH-GUIDELINE", "The guideline states that NTA solicits applications about once per year and publishes concrete dates in advance.", "Cadence does not identify the next exact opening date."],
        ["application_window_2026", "CLOSED", "NTA-NTC-JOINT-RESEARCH-CALL6", "Sixth-call applications closed 2026-04-30 12:00; implementation was planned from around August 2026 for up to three years.", "A new application requires a future call unless NTA announces another route."],
        ["next_application_window", "NOT_ANNOUNCED_AS_OF_2026_09_12", "NTA-NTC-INDEX-2026-09-12;NTA-NTC-JOINT-RESEARCH-GUIDELINE", "The current NTC landing page lists the sixth-call decision but no seventh-call application notice.", "Do not project exact future dates from the approximately annual cadence."],
        ["issue25_decision", "DRAFT_FUTURE_CALL_PROPOSAL", "NTA-NTC-JOINT-RESEARCH-CALL6;NTA-NTC-JOINT-RESEARCH-THEME1-SAMPLE;NTA-NTC-JOINT-RESEARCH-FAQ;NTA-NTC-JOINT-RESEARCH-GUIDELINE;NTA-NTC-JOINT-RESEARCH-OVERVIEW", "Expected identification gain is material for return-side longitudinal reconciliation.", "Full salary-payroll-to-return person linkage remains NOT_IDENTIFIED."],
    ]


def write_route() -> None:
    with ROUTE_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["dimension", "status", "source_ids", "identified_use", "limitation"])
        writer.writerows(route_rows())


def main() -> None:
    by_year = year_fields()
    write_field_presence(by_year)
    write_route()
    print(f"Theme-1 feasibility: {len(FIELDS)} fields, {len(route_rows())} route rows")


if __name__ == "__main__":
    main()
