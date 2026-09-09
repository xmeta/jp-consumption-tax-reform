#!/usr/bin/env python3
"""Extract 2024 Private Salary Survey Table 16 taxpayer-status diagnostics.

This is an external wage-side diagnostic.  It is NOT joined additively to the
self-assessed-return population.

Official terminology:
- survey target: private-sector salary earners regardless of income-tax status;
- "taxpayer": salary earner with positive source-withheld income tax;
- secondary-payroll (乙欄) records can represent an additional payroll record
  for a person receiving salary from multiple payers.

For year-end-adjusted taxpayers, positive post-adjustment withholding is used
only as an external annual-tax-positive subset diagnostic.  Counts are never
added to the NTA positive-self-assessed-balance population because overlap is
not identified.
"""
from pathlib import Path
import argparse
import csv
import io
import math
import re

from extract_nta_shinkoku_income_class_primary_type import Xlsx, integer_cell

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "data/raw/nta/nta_minkan2024_table16_taxpayer_nontaxpayer.xlsx"
METH = ROOT / "data/raw/nta/nta_private_salary_survey_methodology.html"
CATALOG = ROOT / "data/source_catalog.csv"

OUT_CLASS = ROOT / "data/derived/nta_private_salary_taxpayer_status_by_salary_class_2024.csv"
OUT_SUMMARY = ROOT / "data/derived/nta_private_salary_taxpayer_status_summary_2024.csv"

PANELS = [
    ("その１", "full_year", False),
    ("その２", "less_than_year", False),
    ("その３", "full_year", True),
    ("その４", "less_than_year", True),
]
PERSON_ROWS = list(range(7, 21))
PERSON_TOTAL_ROW = 21
TAX_ROWS = list(range(39, 53))
TAX_TOTAL_ROW = 53

SALARY_UPPER_YEN = [
    1_000_000,
    2_000_000,
    3_000_000,
    4_000_000,
    5_000_000,
    6_000_000,
    7_000_000,
    8_000_000,
    9_000_000,
    10_000_000,
    15_000_000,
    20_000_000,
    25_000_000,
    None,
]


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def clean_label(s):
    return re.sub(r"\s+", " ", str(s).replace("\u3000", " ")).strip()


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def parse_triplet(vals, cols):
    a, b, c = (integer_cell(vals.get(k)) for k in cols)
    residual = a + b - c
    if abs(residual) > 1:
        raise RuntimeError(
            f"count triplet rounding residual too large {cols}: "
            f"{a}+{b}-{c}={residual}"
        )
    return a, b, c


def methodology_checks():
    # The page declares Shift_JIS but contains Windows extension bytes; CP932
    # is the deterministic decoder matching the official page payload.
    text = METH.read_bytes().decode("cp932", errors="strict")
    required = [
        "所得税の納税の有無を問わない",
        "給与所得者のうち、源泉徴収された所得税額がある者をいう。",
        "1人の給与所得者が2か所以上の支払先から給与の支払を受けている場合",
        "主たる給与以外の給与分に関し独立した給与所得者とみなして乙欄適用者",
        "年末調整の有無",
        "年税額",
    ]
    for phrase in required:
        if phrase not in text:
            raise RuntimeError(f"methodology phrase not found: {phrase}")
    return text


def build():
    methodology_checks()
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    xsrc = catalog["NTA-MINKAN-2024-T16"]
    msrc = catalog["NTA-MINKAN-METHODOLOGY"]

    x = Xlsx(XLSX)
    class_rows = []
    summaries = []
    try:
        by_panel = {}
        for sheet, duration, otsuran_excluded in PANELS:
            rows = x.rows(sheet)
            if len(PERSON_ROWS) != len(TAX_ROWS) or len(PERSON_ROWS) != len(SALARY_UPPER_YEN):
                raise RuntimeError("salary-class definition mismatch")

            panel_class = []
            prev_upper = None
            for i, (pr, tr, upper) in enumerate(
                zip(PERSON_ROWS, TAX_ROWS, SALARY_UPPER_YEN), start=1
            ):
                pv = rows[pr]
                tv = rows[tr]
                plabel = clean_label(pv.get("C", ""))
                tlabel = clean_label(tv.get("C", ""))
                if plabel != tlabel:
                    raise RuntimeError(
                        f"{sheet} class label mismatch row {pr}/{tr}: {plabel!r} != {tlabel!r}"
                    )

                adj_taxpayer, adj_nontax, adj_total = parse_triplet(pv, ("D", "E", "F"))
                noadj_taxpayer, noadj_nontax, noadj_total = parse_triplet(pv, ("G", "H", "I"))
                all_taxpayer, all_nontax, all_total = parse_triplet(pv, ("J", "K", "L"))

                if abs(adj_taxpayer + noadj_taxpayer - all_taxpayer) > 1:
                    raise RuntimeError(f"{sheet} class {i}: taxpayer additivity rounding residual")
                if abs(adj_nontax + noadj_nontax - all_nontax) > 1:
                    raise RuntimeError(f"{sheet} class {i}: nontaxpayer additivity rounding residual")
                if abs(adj_total + noadj_total - all_total) > 1:
                    raise RuntimeError(f"{sheet} class {i}: total additivity rounding residual")

                adj_tax_m = integer_cell(tv.get("D"))
                noadj_tax_m = integer_cell(tv.get("G"))
                all_tax_m = integer_cell(tv.get("J"))
                if abs(adj_tax_m + noadj_tax_m - all_tax_m) > 1:
                    raise RuntimeError(
                        f"{sheet} class {i}: tax amount additivity rounding residual"
                    )

                row = {
                    "tax_year": 2024,
                    "sheet": sheet,
                    "employment_duration_group": duration,
                    "secondary_payroll_otsuran_excluded": otsuran_excluded,
                    "salary_class_index": i,
                    "salary_class_label": plabel,
                    "salary_lower_bound_yen_exclusive": "" if prev_upper is None else prev_upper,
                    "salary_upper_bound_yen_inclusive": "" if upper is None else upper,
                    "salary_class_topcoded": upper is None,
                    "year_end_adjusted_taxpayer_persons": adj_taxpayer,
                    "year_end_adjusted_nontaxpayer_persons": adj_nontax,
                    "year_end_adjusted_total_persons": adj_total,
                    "not_year_end_adjusted_taxpayer_persons": noadj_taxpayer,
                    "not_year_end_adjusted_nontaxpayer_persons": noadj_nontax,
                    "not_year_end_adjusted_total_persons": noadj_total,
                    "all_taxpayer_persons": all_taxpayer,
                    "all_nontaxpayer_persons": all_nontax,
                    "all_total_persons": all_total,
                    "year_end_adjusted_taxpayer_rate":
                        f"{adj_taxpayer / adj_total:.12g}" if adj_total else "",
                    "all_taxpayer_rate":
                        f"{all_taxpayer / all_total:.12g}" if all_total else "",
                    "year_end_adjusted_tax_million_yen": adj_tax_m,
                    "not_year_end_adjusted_tax_million_yen": noadj_tax_m,
                    "all_tax_million_yen": all_tax_m,
                    "person_source_cells":
                        f"D{pr}:L{pr}",
                    "tax_source_cells":
                        f"D{tr};G{tr};J{tr}",
                    "taxpayer_definition":
                        "Private Salary Survey: salary earner with positive source-withheld income tax",
                    "survey_population":
                        "Private-sector salary earners employed at sampled source-withholding obligors at year-end; tax status not required for inclusion",
                    "cross_system_status":
                        "EXTERNAL_WAGE_SIDE_DIAGNOSTIC_NO_ADDITIVE_JOIN_TO_SELF_ASSESSED_RETURNS",
                    "year_end_adjusted_direction_note":
                        "Positive post-year-end-adjustment withholding is an annual payroll-tax-positive diagnostic under payroll information. Later final-return deductions, credits or loss offsets can change final calculated/self-assessed tax, so this is not a strict final calculated-tax-positive subset.",
                    "source_id_xlsx": "NTA-MINKAN-2024-T16",
                    "source_file_xlsx": xsrc["raw_file"],
                    "source_sha256_xlsx": xsrc["sha256"],
                    "source_id_methodology": "NTA-MINKAN-METHODOLOGY",
                    "source_file_methodology": msrc["raw_file"],
                    "source_sha256_methodology": msrc["sha256"],
                    "evidence_status":
                        "REPRODUCED_OFFICIAL_PRIVATE_SALARY_TAXPAYER_STATUS_DIAGNOSTIC",
                    "identification_warning":
                        "Do not add these taxpayer counts to positive-self-assessed-balance counts; cross-source person overlap is not identified. Non-year-end-adjusted positive withholding can later be refunded and is not treated as a strict annual calculated-tax-positive subset.",
                }
                class_rows.append(row)
                panel_class.append(row)
                prev_upper = upper

            # Check against published panel totals.
            pv = rows[PERSON_TOTAL_ROW]
            tv = rows[TAX_TOTAL_ROW]
            adj_taxpayer, adj_nontax, adj_total = parse_triplet(pv, ("D", "E", "F"))
            noadj_taxpayer, noadj_nontax, noadj_total = parse_triplet(pv, ("G", "H", "I"))
            all_taxpayer, all_nontax, all_total = parse_triplet(pv, ("J", "K", "L"))
            if abs(sum(r["year_end_adjusted_taxpayer_persons"] for r in panel_class) - adj_taxpayer) > 2:
                raise RuntimeError(f"{sheet}: class sum rounding residual adjusted taxpayers")
            if abs(sum(r["year_end_adjusted_nontaxpayer_persons"] for r in panel_class) - adj_nontax) > 2:
                raise RuntimeError(f"{sheet}: class sum rounding residual adjusted nontaxpayers")
            if abs(sum(r["not_year_end_adjusted_taxpayer_persons"] for r in panel_class) - noadj_taxpayer) > 2:
                raise RuntimeError(f"{sheet}: class sum rounding residual nonadjusted taxpayers")
            if abs(sum(r["all_total_persons"] for r in panel_class) - all_total) > 2:
                raise RuntimeError(f"{sheet}: class sum rounding residual total persons")

            adj_tax_m = integer_cell(tv.get("D"))
            noadj_tax_m = integer_cell(tv.get("G"))
            all_tax_m = integer_cell(tv.get("J"))
            if abs(adj_tax_m + noadj_tax_m - all_tax_m) > 1:
                raise RuntimeError(f"{sheet}: total tax amount rounding residual")
            if abs(sum(r["year_end_adjusted_tax_million_yen"] for r in panel_class) - adj_tax_m) > 2:
                raise RuntimeError(f"{sheet}: class sum rounding residual adjusted tax")
            if abs(sum(r["all_tax_million_yen"] for r in panel_class) - all_tax_m) > 2:
                raise RuntimeError(f"{sheet}: class sum rounding residual all tax")

            summary = {
                "tax_year": 2024,
                "summary_scope": f"{duration}_{'otsuran_excluded' if otsuran_excluded else 'all_payroll_records'}",
                "employment_duration_group": duration,
                "secondary_payroll_otsuran_excluded": otsuran_excluded,
                "year_end_adjusted_taxpayer_persons": adj_taxpayer,
                "year_end_adjusted_nontaxpayer_persons": adj_nontax,
                "year_end_adjusted_total_persons": adj_total,
                "not_year_end_adjusted_taxpayer_persons": noadj_taxpayer,
                "not_year_end_adjusted_nontaxpayer_persons": noadj_nontax,
                "not_year_end_adjusted_total_persons": noadj_total,
                "all_taxpayer_persons": all_taxpayer,
                "all_nontaxpayer_persons": all_nontax,
                "all_total_persons": all_total,
                "year_end_adjusted_tax_million_yen": adj_tax_m,
                "not_year_end_adjusted_tax_million_yen": noadj_tax_m,
                "all_tax_million_yen": all_tax_m,
                "year_end_adjusted_taxpayer_rate": f"{adj_taxpayer/adj_total:.12g}",
                "all_taxpayer_rate": f"{all_taxpayer/all_total:.12g}",
                "person_total_source_cells": f"D{PERSON_TOTAL_ROW}:L{PERSON_TOTAL_ROW}",
                "tax_total_source_cells": f"D{TAX_TOTAL_ROW};G{TAX_TOTAL_ROW};J{TAX_TOTAL_ROW}",
                "final_calculated_tax_positive_subset_status":
                    "NOT_STRICT_SUBSET_FINAL_RETURN_CAN_CHANGE_TAX",
                "cross_source_union_status":
                    "OVERLAP_WITH_SELF_ASSESSED_RETURNS_UNKNOWN_DO_NOT_SUM",
                "source_ids": "NTA-MINKAN-2024-T16;NTA-MINKAN-METHODOLOGY",
                "evidence_status":
                    "REPRODUCED_OFFICIAL_PRIVATE_SALARY_TAXPAYER_STATUS_DIAGNOSTIC",
            }
            summaries.append(summary)
            by_panel[(duration, otsuran_excluded)] = summary

        # Year-end-adjusted records are unchanged by excluding secondary-payroll
        # records, which is consistent with secondary wages generally not being
        # year-end-adjusted.
        for duration in ("full_year", "less_than_year"):
            a = by_panel[(duration, False)]
            b = by_panel[(duration, True)]
            for key in (
                "year_end_adjusted_taxpayer_persons",
                "year_end_adjusted_nontaxpayer_persons",
                "year_end_adjusted_total_persons",
                "year_end_adjusted_tax_million_yen",
            ):
                if a[key] != b[key]:
                    raise RuntimeError(
                        f"{duration}: adjusted value changes under otsuran exclusion: {key}"
                    )

        fy = by_panel[("full_year", True)]
        ly = by_panel[("less_than_year", True)]
        combined = {
            "tax_year": 2024,
            "summary_scope": "combined_year_end_adjusted_private_salary_otsuran_excluded",
            "employment_duration_group": "full_year_plus_less_than_year",
            "secondary_payroll_otsuran_excluded": True,
            "year_end_adjusted_taxpayer_persons":
                fy["year_end_adjusted_taxpayer_persons"]
                + ly["year_end_adjusted_taxpayer_persons"],
            "year_end_adjusted_nontaxpayer_persons":
                fy["year_end_adjusted_nontaxpayer_persons"]
                + ly["year_end_adjusted_nontaxpayer_persons"],
            "year_end_adjusted_total_persons":
                fy["year_end_adjusted_total_persons"]
                + ly["year_end_adjusted_total_persons"],
            "not_year_end_adjusted_taxpayer_persons":
                fy["not_year_end_adjusted_taxpayer_persons"]
                + ly["not_year_end_adjusted_taxpayer_persons"],
            "not_year_end_adjusted_nontaxpayer_persons":
                fy["not_year_end_adjusted_nontaxpayer_persons"]
                + ly["not_year_end_adjusted_nontaxpayer_persons"],
            "not_year_end_adjusted_total_persons":
                fy["not_year_end_adjusted_total_persons"]
                + ly["not_year_end_adjusted_total_persons"],
            "all_taxpayer_persons":
                fy["all_taxpayer_persons"] + ly["all_taxpayer_persons"],
            "all_nontaxpayer_persons":
                fy["all_nontaxpayer_persons"] + ly["all_nontaxpayer_persons"],
            "all_total_persons":
                fy["all_total_persons"] + ly["all_total_persons"],
            "year_end_adjusted_tax_million_yen":
                fy["year_end_adjusted_tax_million_yen"]
                + ly["year_end_adjusted_tax_million_yen"],
            "not_year_end_adjusted_tax_million_yen":
                fy["not_year_end_adjusted_tax_million_yen"]
                + ly["not_year_end_adjusted_tax_million_yen"],
            "all_tax_million_yen":
                fy["all_tax_million_yen"] + ly["all_tax_million_yen"],
            "year_end_adjusted_taxpayer_rate": "",
            "all_taxpayer_rate": "",
            "person_total_source_cells":
                "その3!D21:L21;その4!D21:L21",
            "tax_total_source_cells":
                "その3!D53;G53;J53;その4!D53;G53;J53",
            "final_calculated_tax_positive_subset_status":
                "NOT_STRICT_SUBSET_EXTERNAL_PAYROLL_SCALE_DIAGNOSTIC_ONLY",
            "cross_source_union_status":
                "OVERLAP_WITH_SELF_ASSESSED_RETURNS_UNKNOWN_DO_NOT_SUM",
            "source_ids": "NTA-MINKAN-2024-T16;NTA-MINKAN-METHODOLOGY",
            "evidence_status":
                "REPRODUCED_OFFICIAL_PRIVATE_SALARY_TAXPAYER_STATUS_DIAGNOSTIC",
        }
        combined["year_end_adjusted_taxpayer_rate"] = (
            f"{combined['year_end_adjusted_taxpayer_persons']/combined['year_end_adjusted_total_persons']:.12g}"
        )
        combined["all_taxpayer_rate"] = (
            f"{combined['all_taxpayer_persons']/combined['all_total_persons']:.12g}"
        )
        summaries.append(combined)
    finally:
        x.close()

    return class_rows, summaries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    class_rows, summaries = build()
    outputs = [
        (OUT_CLASS, render(class_rows)),
        (OUT_SUMMARY, render(summaries)),
    ]
    if args.check:
        stale = []
        for path, expected in outputs:
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual != expected:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            raise SystemExit("stale generated artifacts: " + ", ".join(stale))
        print(
            "NTA private-salary taxpayer-status diagnostic: current "
            "(56 salary-class rows; 5 summaries; no additive join to self-assessed returns)"
        )
        return

    for path, expected in outputs:
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
