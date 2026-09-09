#!/usr/bin/env python3
"""Audit discontinuation of NTA Public Offices/Others salary person series.

Scope is 1991-2024 because the long-term official note unambiguously states
that person fields from 1991 onward are sample-survey estimates.
"""
from pathlib import Path
import argparse
import csv
import io
import re

from pypdf import PdfReader
from extract_nta_shinkoku_income_class_primary_type import Xlsx, integer_cell

ROOT = Path(__file__).resolve().parents[1]
LONG = ROOT / "data/raw/nta/nta_withholding_long_term_series.xlsx"
PDF2006 = ROOT / "data/raw/nta/nta_2006_withholding_tax_status.pdf"
PDF2007 = ROOT / "data/raw/nta/nta_2007_withholding_tax_status.pdf"
CURRENT = ROOT / "data/derived/nta_salary_source_system_coverage_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"
OUT_SERIES = ROOT / "data/derived/nta_withholding_salary_person_series_1991_2024.csv"
OUT_AUDIT = ROOT / "data/derived/nta_withholding_person_series_discontinuity_audit.csv"


def read_dicts(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def pdf_page_text(path, zero_page=3):
    return PdfReader(path).pages[zero_page].extract_text() or ""


def metric(metric_id, value, unit, source_ids, locator, status, note):
    return {
        "metric_id": metric_id,
        "value": value,
        "unit": unit,
        "source_ids": source_ids,
        "source_locator": locator,
        "identification_status": status,
        "note": note,
    }


def year_rows():
    # Long-term sheet rows: H3..H30 = 1991..2018, Reiwa1..6 = 2019..2024.
    return list(zip(range(1991, 2019), range(51, 79))) + list(zip(range(2019, 2025), range(79, 85)))
def build():
    catalog = {r["source_id"]: r for r in read_dicts(CATALOG)}
    long_src = catalog["NTA-WITHHOLDING-LONG-TERM"]

    x = Xlsx(LONG)
    try:
        rows = x.rows("５　給与所得")
        notes = "".join(str(rows[i].get("A", "")) for i in range(86, 91))
        if "平成３年分以降の「人員」に関する部分は、標本調査" not in notes:
            raise RuntimeError("1991+ sample-estimate note not found in long-term workbook")

        series = []
        for year, rn in year_rows():
            r = rows[rn]
            pub_raw = str(r.get("B", "")).strip()
            other_raw = str(r.get("D", "")).strip()
            available = pub_raw not in ("", "－", "－ ") and other_raw not in ("", "－", "－ ")
            pub_n = integer_cell(pub_raw) if available else ""
            other_n = integer_cell(other_raw) if available else ""
            combined = (pub_n + other_n) if available else ""
            pub_pay = integer_cell(r.get("C"))
            other_pay = integer_cell(r.get("E"))
            day_pay = integer_cell(r.get("F"))
            total_pay = integer_cell(r.get("G"))
            if abs((pub_pay + other_pay + day_pay) - total_pay) > 1:
                raise RuntimeError(f"payment identity residual >1 million yen at {year}")
            series.append({
                "year": year,
                "public_offices_persons_thousand": pub_n,
                "others_persons_thousand": other_n,
                "public_plus_others_persons_thousand": combined,
                "public_offices_salary_payment_million_yen": pub_pay,
                "others_salary_payment_million_yen": other_pay,
                "day_labor_payment_million_yen": day_pay,
                "total_salary_payment_million_yen": total_pay,
                "person_field_status": (
                    "SAMPLE_SURVEY_ESTIMATE_PUBLISHED"
                    if available else "NOT_PUBLISHED"
                ),
                "person_field_nature": (
                    "1991_AND_LATER_PERSON_FIELDS_ARE_SAMPLE_SURVEY_ESTIMATES"
                    if available else "PUBLISHED_PERSON_SERIES_DISCONTINUED"
                ),
                "source_id": "NTA-WITHHOLDING-LONG-TERM",
                "source_row": rn,
                "source_sha256": long_src["sha256"],
            })
    finally:
        x.close()

    available = [r for r in series if r["person_field_status"] == "SAMPLE_SURVEY_ESTIMATE_PUBLISHED"]
    missing = [r for r in series if r["person_field_status"] == "NOT_PUBLISHED"]
    if [r["year"] for r in available] != list(range(1991, 2007)):
        raise RuntimeError("expected published person series 1991-2006")
    if [r["year"] for r in missing] != list(range(2007, 2025)):
        raise RuntimeError("expected missing person series 2007-2024")

    r06 = next(r for r in series if r["year"] == 2006)
    r07 = next(r for r in series if r["year"] == 2007)
    r24 = next(r for r in series if r["year"] == 2024)
    assert (r06["public_offices_persons_thousand"], r06["others_persons_thousand"], r06["public_plus_others_persons_thousand"]) == (9170, 66936, 76106)
    assert r07["public_offices_persons_thousand"] == ""
    assert r24["public_offices_persons_thousand"] == ""
    p06 = re.sub(r"\s+", "", pdf_page_text(PDF2006))
    p07 = re.sub(r"\s+", "", pdf_page_text(PDF2007))
    for needle in ("9,170", "66,936", "76,106", "Numberoftaxpayers"):
        if re.sub(r"\s+", "", needle) not in p06:
            raise RuntimeError(f"2006 PDF anchor missing: {needle}")
    for needle in ("29,368,576", "224,080,537"):
        if re.sub(r"\s+", "", needle) not in p07:
            raise RuntimeError(f"2007 PDF anchor missing: {needle}")
    if "Numberoftaxpayers" in p07:
        raise RuntimeError("2007 PDF unexpectedly contains person header")

    current = {r["metric_id"]: r for r in read_dicts(CURRENT)}
    assert int(current["source_salary_public_offices_payment"]["value"]) == r24["public_offices_salary_payment_million_yen"]
    assert int(current["source_salary_other_payment"]["value"]) == r24["others_salary_payment_million_yen"]

    person_share_2006 = 9170 / 76106
    payment_share_2006 = r06["public_offices_salary_payment_million_yen"] / (
        r06["public_offices_salary_payment_million_yen"] + r06["others_salary_payment_million_yen"]
    )
    payment_share_2024 = r24["public_offices_salary_payment_million_yen"] / (
        r24["public_offices_salary_payment_million_yen"] + r24["others_salary_payment_million_yen"]
    )

    audit = [
        metric(
            "person_series_first_unambiguous_sample_estimate_year",
            1991, "year",
            "NTA-WITHHOLDING-LONG-TERM",
            "Sheet ５ notes and row 51",
            "PERSON_FIELDS_SAMPLE_SURVEY_ESTIMATES_FROM_1991",
            "Audit scope begins where the official note unambiguously classifies all person fields as sample-survey estimates.",
        ),
        metric(
            "person_series_last_published_year",
            2006, "year",
            "NTA-WITHHOLDING-LONG-TERM;NTA-WITHHOLDING-2006-STATUS",
            "Sheet ５ row 66; 2006 Table (7)",
            "LAST_PUBLISHED_PUBLIC_OTHER_PERSON_ESTIMATE",
            "Public Offices and Others person estimates are both published in 2006.",
        ),
        metric(
            "person_series_first_missing_year",
            2007, "year",
            "NTA-WITHHOLDING-LONG-TERM;NTA-WITHHOLDING-2007-STATUS",
            "Sheet ５ row 67; 2007 Table (7)",
            "PUBLISHED_PERSON_SERIES_DISCONTINUED",
            "Payment and withholding amounts continue, but Public Offices/Others person columns disappear.",
        ),
        metric(
            "person_series_missing_years_through_2024",
            18, "years",
            "NTA-WITHHOLDING-LONG-TERM",
            "2007-2024",
            "CURRENT_PERSON_SERIES_GAP",
            "Eighteen consecutive years have no published Public Offices/Others person values in this series.",
        ),
        metric(
            "public_offices_persons_2006",
            9170, "thousand_persons_estimated",
            "NTA-WITHHOLDING-LONG-TERM;NTA-WITHHOLDING-2006-STATUS",
            "Sheet ５ B66; 2006 Table (7)",
            "HISTORICAL_SAMPLE_SURVEY_ESTIMATE",
            "Not an administrative exact count; 1991+ person fields are sample-survey estimates.",
        ),
        metric(
            "others_persons_2006",
            66936, "thousand_persons_estimated",
            "NTA-WITHHOLDING-LONG-TERM;NTA-WITHHOLDING-2006-STATUS",
            "Sheet ５ D66; 2006 Table (7)",
            "HISTORICAL_SAMPLE_SURVEY_ESTIMATE",
            "Not an administrative exact count.",
        ),
        metric(
            "public_plus_others_persons_2006",
            76106, "thousand_persons_estimated",
            "NTA-WITHHOLDING-LONG-TERM;NTA-WITHHOLDING-2006-STATUS",
            "9,170 + 66,936",
            "HISTORICAL_SAMPLE_SURVEY_ESTIMATE",
            "Published payroll-side estimate; not asserted to be annual unique persons.",
        ),
        metric(
            "public_offices_person_share_2006",
            f"{person_share_2006:.12f}".rstrip("0").rstrip("."), "historical_estimated_person_ratio",
            "NTA-WITHHOLDING-LONG-TERM",
            "B66/(B66+D66)",
            "HISTORICAL_RATIO_NOT_CURRENT_PERSON_SHARE",
            "Historical 2006 ratio only; extrapolation to 2024 is not identified.",
        ),
        metric(
            "public_offices_payment_share_2006",
            f"{payment_share_2006:.12f}".rstrip("0").rstrip("."), "amount_ratio",
            "NTA-WITHHOLDING-LONG-TERM",
            "C66/(C66+E66)",
            "HISTORICAL_AMOUNT_SHARE",
            "2006 salary/wages/bonus amount composition.",
        ),
        metric(
            "public_offices_payment_share_2024",
            f"{payment_share_2024:.12f}".rstrip("0").rstrip("."), "amount_ratio",
            "NTA-WITHHOLDING-LONG-TERM;NTA-FY2024-WITHHOLDING-STATUS",
            "C84/(C84+E84)",
            "CURRENT_AMOUNT_SHARE_NOT_PERSON_SHARE",
            "2024 amount share; consistent with current source-system coverage audit.",
        ),
        metric(
            "public_payment_share_change_2006_to_2024_pp",
            f"{100*(payment_share_2024-payment_share_2006):.12f}".rstrip("0").rstrip("."), "percentage_points",
            "NTA-WITHHOLDING-LONG-TERM",
            "2006 versus 2024",
            "STRUCTURAL_COMPOSITION_CHANGE",
            "Large amount-composition change further weakens any 2006 person-share extrapolation.",
        ),
        metric(
            "apply_2006_public_person_share_to_2024",
            "PROHIBITED", "status",
            "NTA-WITHHOLDING-LONG-TERM;NTA-FY2024-WITHHOLDING-STATUS",
            "cross-year extrapolation",
            "DO_NOT_EXTRAPOLATE_DISCONTINUED_SAMPLE_PERSON_SERIES",
            "2006 is a sample-survey person estimate separated from 2024 by 18 missing years and changed payment composition.",
        ),
        metric(
            "nta_public_offices_person_count_2024",
            "NOT_IDENTIFIED", "status",
            "NTA-WITHHOLDING-LONG-TERM;NTA-FY2024-WITHHOLDING-STATUS",
            "2024",
            "NTA_PUBLIC_OFFICES_PERSON_COUNT_NOT_IDENTIFIED",
            "Historical person estimates do not restore the missing current-year person denominator.",
        ),
    ]
    return series, audit
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    series, audit = build()
    outputs = [(OUT_SERIES, render(series)), (OUT_AUDIT, render(audit))]
    if args.check:
        stale = []
        for path, expected in outputs:
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual != expected:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            raise SystemExit("stale generated artifacts: " + ", ".join(stale))
        print(
            "NTA withholding person-series audit: current "
            "(1991-2006 sample person estimates; 2007-2024 missing; "
            "2006 public=9,170k/others=66,936k; 2024 persons not identified)"
        )
        return
    for path, expected in outputs:
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
