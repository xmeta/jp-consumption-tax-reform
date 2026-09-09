#!/usr/bin/env python3
"""Reconcile NTA submitted-return press counts with Table 2-1 processing rows.

The press release Table 3-1 reports rounded thousand-person filing counts based
on returns submitted by the following March 31.  Annual Table 2-1 reports
taxation status as of June 30 for persons who filed or whose cases were
processed by March 31.  Its row labelled Final return is therefore retained as
an exact processing-row benchmark, not equated to the press-release submitted-
return count.
"""
from pathlib import Path
import argparse
import csv
import io
import re

from pypdf import PdfReader
from extract_nta_stage2_holdout import PRESS, PRESS_GRAND, LABELS

ROOT = Path(__file__).resolve().parents[1]
PRESS_PDF = ROOT / "data/raw/nta/nta_2024_final_return_press_table31.pdf"
PROCESSING_PDF = ROOT / "data/raw/nta/nta_2024_self_assessment_processing_status.pdf"
CATALOG = ROOT / "data/source_catalog.csv"
OUT = ROOT / "data/derived/nta_final_return_submission_processing_reconciliation_2024.csv"
AUDIT = ROOT / "data/derived/nta_final_return_processing_semantics_audit_2024.csv"

PAGE_BY_CATEGORY = {
    "all": 0,
    "business": 1,
    "real_estate": 2,
    "salary": 3,
    "miscellaneous": 4,
    "other": 5,
}
LABELS_ALL = {"all": "合計", **LABELS}


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def parse_triplet(text, label):
    norm = re.sub(r"\s+", " ", text)
    if label == "2024":
        pat = r"2024\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)"
    else:
        pat = re.escape(label) + r"\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)"
    m = re.search(pat, norm)
    if not m:
        raise RuntimeError(f"row not found: {label}")
    return tuple(int(x.replace(",", "")) for x in m.groups())


def processing_rows():
    reader = PdfReader(PROCESSING_PDF)
    scope = re.sub(r"\s+", " ", reader.pages[0].extract_text() or "")
    required_scope = [
        "as of June 30, 2025",
        "filed final returns or whose cases processed",
        "by March 31",
    ]
    for phrase in required_scope:
        if phrase not in scope:
            raise RuntimeError(f"Table 2-1 scope phrase missing: {phrase}")
    out = {}
    for category, page_index in PAGE_BY_CATEGORY.items():
        text = reader.pages[page_index].extract_text() or ""
        total = parse_triplet(text, "2024")
        final = parse_triplet(text, "Final return")
        out[category] = {
            "processed_total_persons": total[0],
            "processed_positive_persons": total[1],
            "processed_refund_persons": total[2],
            "processed_zero_persons": total[0] - total[1] - total[2],
            "final_row_persons": final[0],
            "final_row_positive_persons": final[1],
            "final_row_refund_persons": final[2],
            "final_row_zero_persons": final[0] - final[1] - final[2],
        }
    return out


def verify_press_pdf():
    text = PdfReader(PRESS_PDF).pages[14].extract_text() or ""
    norm = re.sub(r"\s+", "", text)
    for token in ("23,389", "5,175", "13,533", "4,681", "11,442", "2,389", "7,711", "1,343"):
        if token.replace(" ", "") not in norm:
            raise RuntimeError(f"press Table 3-1 anchor missing: {token}")
    if "翌年３月末日までに提出された申告書の計数である" not in norm:
        raise RuntimeError("press Table 3-1 submission-cutoff note missing")


def build():
    cat = {r["source_id"]: r for r in read_csv(CATALOG)}
    press_src = cat["NTA-2024-RETURN-PRESS-T31"]
    processing_src = cat["NTA-2024-PROCESSING-STATUS"]
    verify_press_pdf()
    proc = processing_rows()

    press_by = {
        "all": (
            PRESS_GRAND["final_return_thousand"],
            PRESS_GRAND["positive_self_assessed_balance_thousand"],
            PRESS_GRAND["refund_thousand"],
            PRESS_GRAND["zero_thousand"],
        )
    }
    for category, total, positive, refund, zero in PRESS:
        press_by[category] = (total, positive, refund, zero)

    expected_processed = {
        "all": (23_362_184, 5_158_260, 13_527_496),
        "business": (3_785_184, 1_174_065, 962_359),
        "real_estate": (1_497_102, 804_398, 174_282),
        "salary": (11_423_587, 2_385_726, 7_697_018),
        "miscellaneous": (5_819_853, 411_376, 4_300_467),
        "other": (836_458, 382_695, 393_370),
    }
    expected_final = {
        "all": (23_090_075, 5_067_037, 13_386_611),
        "business": (3_730_986, 1_145_782, 951_155),
        "real_estate": (1_476_174, 789_809, 172_155),
        "salary": (11_293_442, 2_352_779, 7_612_961),
        "miscellaneous": (5_765_807, 404_043, 4_261_066),
        "other": (823_666, 374_624, 389_274),
    }
    for category in PAGE_BY_CATEGORY:
        p = proc[category]
        assert (p["processed_total_persons"], p["processed_positive_persons"], p["processed_refund_persons"]) == expected_processed[category]
        assert (p["final_row_persons"], p["final_row_positive_persons"], p["final_row_refund_persons"]) == expected_final[category]

    rows = []
    for category in PAGE_BY_CATEGORY:
        press_total, press_pos, press_refund, press_zero = press_by[category]
        p = proc[category]
        press_center = press_total * 1000
        rows.append({
            "income_category": category,
            "income_category_ja": LABELS_ALL[category],
            "press_submitted_return_thousand_displayed": press_total,
            "press_positive_thousand_displayed": press_pos,
            "press_refund_thousand_displayed": press_refund,
            "press_zero_thousand_displayed": press_zero,
            "table21_final_return_row_persons_exact": p["final_row_persons"],
            "table21_final_return_row_positive_persons_exact": p["final_row_positive_persons"],
            "table21_final_return_row_refund_persons_exact": p["final_row_refund_persons"],
            "table21_final_return_row_zero_persons_exact": p["final_row_zero_persons"],
            "table21_filed_or_processed_persons_exact": p["processed_total_persons"],
            "table21_filed_or_processed_positive_persons_exact": p["processed_positive_persons"],
            "table21_filed_or_processed_refund_persons_exact": p["processed_refund_persons"],
            "table21_filed_or_processed_zero_persons_exact": p["processed_zero_persons"],
            "press_display_center_minus_final_row_persons": press_center - p["final_row_persons"],
            "press_display_center_minus_processed_total_persons": press_center - p["processed_total_persons"],
            "press_source_id": "NTA-2024-RETURN-PRESS-T31",
            "press_source_sha256": press_src["sha256"],
            "processing_source_id": "NTA-2024-PROCESSING-STATUS",
            "processing_source_sha256": processing_src["sha256"],
            "comparison_status": "DISTINCT_PUBLICATION_POPULATION_AND_REFERENCE_DATE",
            "interpretation": (
                "Press count is a displayed thousand-person filing count based on returns submitted by March 31; "
                "Table 2-1 is taxation status as of June 30 for filed-or-processed cases. "
                "Displayed-center differences are descriptive only because press counts are rounded."
            ),
        })
    allrow = next(r for r in rows if r["income_category"] == "all")
    salary = next(r for r in rows if r["income_category"] == "salary")
    audit = [
        {
            "metric_id": "stage1_table21_final_return_processing_row",
            "value": allrow["table21_final_return_row_persons_exact"],
            "unit": "persons_exact",
            "identification_status": "OBSERVED_TABLE21_FINAL_RETURN_PROCESSING_ROW",
            "source_ids": "NTA-2024-PROCESSING-STATUS;NTA-R06",
            "note": "Retain 23,090,075 as the stage-1 public benchmark only under this processing-row semantics.",
        },
        {
            "metric_id": "press_submitted_return_count_displayed",
            "value": allrow["press_submitted_return_thousand_displayed"],
            "unit": "thousand_persons_displayed",
            "identification_status": "OBSERVED_PRESS_SUBMITTED_RETURN_COUNT_ROUNDED",
            "source_ids": "NTA-2024-RETURN-PRESS-T31",
            "note": "Table 3-1 count based on returns submitted by the following March 31.",
        },
        {
            "metric_id": "table21_filed_or_processed_total",
            "value": allrow["table21_filed_or_processed_persons_exact"],
            "unit": "persons_exact",
            "identification_status": "OBSERVED_TABLE21_FILED_OR_PROCESSED_TOTAL",
            "source_ids": "NTA-2024-PROCESSING-STATUS",
            "note": "Taxation status as of June 30 for persons who filed or whose cases were processed by March 31.",
        },
        {
            "metric_id": "salary_press_submitted_return_count_displayed",
            "value": salary["press_submitted_return_thousand_displayed"],
            "unit": "thousand_persons_displayed",
            "identification_status": "OBSERVED_PRESS_SUBMITTED_RETURN_COUNT_ROUNDED",
            "source_ids": "NTA-2024-RETURN-PRESS-T31",
            "note": "Salary-income row of press Table 3-1.",
        },
        {
            "metric_id": "salary_table21_final_return_processing_row",
            "value": salary["table21_final_return_row_persons_exact"],
            "unit": "persons_exact",
            "identification_status": "OBSERVED_TABLE21_FINAL_RETURN_PROCESSING_ROW",
            "source_ids": "NTA-2024-PROCESSING-STATUS",
            "note": "Salary-income Final return processing row.",
        },
        {
            "metric_id": "press_and_table21_final_row_same_statistical_object",
            "value": "NO",
            "unit": "status",
            "identification_status": "DISTINCT_PUBLICATION_POPULATION_AND_REFERENCE_DATE",
            "source_ids": "NTA-2024-RETURN-PRESS-T31;NTA-2024-PROCESSING-STATUS",
            "note": "Do not equate the press submitted-return count with the Table 2-1 Final return processing row.",
        },
        {
            "metric_id": "press_vs_table21_category_definition_equivalence",
            "value": "NOT_ESTABLISHED",
            "unit": "status",
            "identification_status": "DO_NOT_ASSUME_CATEGORY_DEFINITION_IDENTITY",
            "source_ids": "NTA-2024-RETURN-PRESS-T31;NTA-2024-PROCESSING-STATUS",
            "note": "Category-specific comparisons are diagnostics; the publications do not establish an exact category-definition crosswalk.",
        },
        {
            "metric_id": "press_vs_table21_difference_mechanism",
            "value": "NOT_IDENTIFIED",
            "unit": "status",
            "identification_status": "PUBLICATIONS_ESTABLISH_SCOPE_DIFFERENCE_NOT_CAUSAL_MECHANISM",
            "source_ids": "NTA-2024-RETURN-PRESS-T31;NTA-2024-PROCESSING-STATUS",
            "note": "Later processing may contribute, but the published tables do not decompose the observed cross-publication count difference by mechanism.",
        },
        {
            "metric_id": "stage1_23090075_numerical_change_required",
            "value": "NO",
            "unit": "status",
            "identification_status": "RETAIN_AS_PROCESSING_ROW_BENCHMARK",
            "source_ids": "NTA-2024-PROCESSING-STATUS;NTA-R06;NTA-2024-RETURN-PRESS-T31",
            "note": "The existing robustness benchmark can retain the exact public row; its label must not imply all submitted-return persons.",
        },
        {
            "metric_id": "stage1_23090075_wording_change_required",
            "value": "YES",
            "unit": "status",
            "identification_status": "CANONICAL_LABEL_TABLE21_FINAL_RETURN_PROCESSING_ROW",
            "source_ids": "NTA-2024-PROCESSING-STATUS;NTA-2024-RETURN-PRESS-T31",
            "note": "Canonical wording is NTA Table 2-1 Final-return processing-row persons.",
        },
    ]
    return rows, audit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows, audit = build()
    outputs = [(OUT, render(rows)), (AUDIT, render(audit))]
    if args.check:
        stale = []
        for path, expected in outputs:
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual != expected:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            raise SystemExit("stale generated artifacts: " + ", ".join(stale))
        print(
            "NTA final-return processing reconciliation: current "
            "(press submitted returns=23,389k displayed; Table 2-1 final row=23,090,075; "
            "filed/processed total=23,362,184; stage-1 numeric retained with semantic relabel)"
        )
        return
    for path, expected in outputs:
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
