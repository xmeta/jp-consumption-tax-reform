#!/usr/bin/env python3
"""Regression checks for the NTA Theme-1 restricted-data feasibility audit."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

if not __debug__:
    raise RuntimeError("Theme-1 feasibility tests require non-optimized Python")

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/income_tax/nta_joint_research_theme1_sample.xlsx"
FIELDS = ROOT / "data/derived/nta_joint_research_theme1_field_presence_2014_2024.csv"
ROUTE = ROOT / "data/derived/nta_joint_research_theme1_feasibility_2026.csv"
EXPECTED_SHA = "1f38ba548a916b08048f79f30ff1ae5e7067513bf55106fbb7e3b2eb528a967b"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)

require(hashlib.sha256(RAW.read_bytes()).hexdigest() == EXPECTED_SHA, "Theme-1 raw SHA changed")
field_rows = {row["field_id"]: row for row in read(FIELDS)}
route_rows = {row["dimension"]: row for row in read(ROUTE)}
all_year_fields = [
    "joint_research_identifier", "tax_year", "filing_date", "filing_type",
    "salary_receipts", "salary_income", "withholding_tax", "self_assessed_balance",
    "third_installment_payment", "third_installment_refund", "social_insurance_deduction",
]
for field_id in all_year_fields:
    require(field_rows[field_id]["availability_status"] == "ALL_2014_2024", f"{field_id} lost coverage")

require(field_rows["salary_receipt_class"]["years_available"] == "2020;2021;2022;2023;2024", "salary class period changed")
require(field_rows["amended_return_tax_increase"]["years_available"] == "2022;2023;2024", "amended-return period changed")
require(route_rows["salary_return_tax_flow"]["status"] == "MATERIAL_PARTIAL_IDENTIFICATION_GAIN", "gain status changed")
require(route_rows["private_payroll_person_link"]["status"] == "NOT_IDENTIFIED", "payroll link was promoted")
require(route_rows["external_statistical_microdata_linkage"]["status"] == "APPLICATION_POSSIBLE_NOT_PREAPPROVED", "external linkage overclaimed")
require(route_rows["applicant_eligibility"]["status"] == "FULL_TIME_ELIGIBLE_INSTITUTION_REQUIRED", "eligibility gate changed")
require(route_rows["secure_access_hours"]["status"] == "WEEKDAYS_0930_1700_RESERVATION_REQUIRED", "access hours changed")
require(route_rows["maximum_use_period"]["status"] == "NORMALLY_UP_TO_3_YEARS", "maximum use period changed")
require(route_rows["output_review"]["status"] == "NTA_PREPUBLICATION_REVIEW_REQUIRED", "output review gate changed")
require(route_rows["external_data_cost"]["status"] == "USER_BORNE_IF_APPLICABLE", "external-data cost rule changed")
require(route_rows["application_cadence"]["status"] == "ABOUT_ONCE_PER_YEAR", "application cadence changed")
require(route_rows["application_window_2026"]["status"] == "CLOSED", "closed sixth call was treated as open")
require(route_rows["next_application_window"]["status"] == "NOT_ANNOUNCED_AS_OF_2026_09_12", "unannounced next call was projected")
require(route_rows["issue25_decision"]["status"] == "DRAFT_FUTURE_CALL_PROPOSAL", "proposal decision changed")
require("Full salary-payroll-to-return person linkage remains NOT_IDENTIFIED" in route_rows["issue25_decision"]["limitation"], "full-link boundary missing")

print("NTA Theme-1 feasibility tests: OK")
