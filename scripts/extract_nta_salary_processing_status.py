#!/usr/bin/env python3
"""Audit 2024 salary-primary filing/processing status semantics.

The NTA 2-1(1) Employment income earners table separates the pure Final return
row from amended returns and subsequent case-processing categories.  Table
2-2(1)'s 11,423,587 salary-primary population corresponds to the processed
total, not the Final return row alone.
"""
from pathlib import Path
import argparse
import csv
import io
import re

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/nta/nta_2024_self_assessment_processing_status.pdf"
CATALOG = ROOT / "data/source_catalog.csv"
TABLE22 = ROOT / "data/derived/nta_income_class_primary_type_filing_status_2024.csv"
OUT_ROWS = ROOT / "data/derived/nta_salary_processing_status_2024.csv"
OUT_AUDIT = ROOT / "data/derived/nta_salary_processing_status_audit_2024.csv"


def read_dicts(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def number(s):
    return int(s.replace(",", ""))


def fmt_ratio(x):
    return f"{x:.12f}".rstrip("0").rstrip(".")


def row_metric(metric_id, value, unit, status, note):
    return {
        "metric_id": metric_id,
        "value": value,
        "unit": unit,
        "source_ids": "NTA-2024-PROCESSING-STATUS;NTA-R06;NTA-2024-ANNUAL-TABLE-NOTES",
        "identification_status": status,
        "note": note,
    }


def parse_numeric_row(text, label):
    normalized = re.sub(r"\s+", " ", text)
    pattern = re.escape(label) + r"\s+" + r"\s+".join([r"([\d,]+)"] * 8)
    m = re.search(pattern, normalized)
    if not m:
        raise RuntimeError(f"could not parse processing row: {label}")
    vals = [number(x) for x in m.groups()]
    return vals


def build():
    catalog = {r["source_id"]: r for r in read_dicts(CATALOG)}
    source = catalog["NTA-2024-PROCESSING-STATUS"]

    reader = PdfReader(SOURCE)
    text = reader.pages[3].extract_text() or ""
    if "Employment income earners" not in text or "給与所得者" not in text:
        raise RuntimeError("salary-earner processing table not found on expected page")

    labels = [
        ("final_return", "Final return"),
        ("amended_return", "Amended return"),
        ("determination_or_correction_increase", "Determination or correction for increase"),
        ("correction_for_reduction", "Correction for reduction"),
        ("request_for_correction", "Request for correction"),
    ]
    parsed = {}
    for key, label in labels:
        parsed[key] = parse_numeric_row(text, label)

    total = parse_numeric_row(text, "2024")

    fields = [
        "persons",
        "positive_self_assessed_balance_persons",
        "refund_persons",
        "total_net_income_million_yen",
        "positive_subset_total_net_income_million_yen",
        "refund_subset_total_net_income_million_yen",
        "self_assessed_income_tax_million_yen",
        "refund_tax_million_yen",
    ]

    rows = []
    for key, _ in labels:
        row = {
            "processing_status": key,
            **dict(zip(fields, parsed[key])),
            "source_id": "NTA-2024-PROCESSING-STATUS",
            "source_locator": "PDF p.4 / (1) Part 4 Employment income earners",
            "source_sha256": source["sha256"],
            "row_nature": "OFFICIAL_CURRENT_YEAR_PROCESSING_COMPONENT",
        }
        rows.append(row)
    rows.append({
        "processing_status": "total_actual",
        **dict(zip(fields, total)),
        "source_id": "NTA-2024-PROCESSING-STATUS",
        "source_locator": "PDF p.4 / 2024 and Total Actual",
        "source_sha256": source["sha256"],
        "row_nature": "OFFICIAL_FILED_OR_PROCESSED_TOTAL",
    })

    # Person-status components reproduce the published 2024 total exactly.
    # Monetary columns are processing-state amounts and are not additive across
    # amended/correction rows, so they are retained as observed values only.
    for i, field in enumerate(fields[:3]):
        if sum(parsed[key][i] for key, _ in labels) != total[i]:
            raise RuntimeError(f"processing person components do not sum to total for {field}")

    table22_salary = [
        r for r in read_dicts(TABLE22) if r["primary_income_type"] == "salary"
    ]
    t22_total = sum(int(r["table22_population_persons"]) for r in table22_salary)
    t22_positive = sum(int(r["positive_self_assessed_balance_persons"]) for r in table22_salary)
    t22_refund = sum(int(r["refund_persons"]) for r in table22_salary)
    t22_residual = sum(int(r["neither_positive_nor_refund_residual"]) for r in table22_salary)

    if not (t22_total == total[0] == 11423587):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:135')
    if not (t22_positive == total[1] == 2385726):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:136')
    if not (t22_refund == total[2] == 7697018):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:137')
    if not (t22_residual == total[0] - total[1] - total[2] == 1340843):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:138')

    final = parsed["final_return"]
    post_persons = total[0] - final[0]
    post_positive = total[1] - final[1]
    post_refund = total[2] - final[2]
    final_residual = final[0] - final[1] - final[2]
    post_residual = t22_residual - final_residual

    if not (final[0] == 11293442):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:147')
    if not (post_persons == 130145):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:148')
    if not (post_positive == 32947):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:149')
    if not (post_refund == 84057):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:150')
    if not (final_residual == 1327702):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:151')
    if not (post_residual == 13141):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:152')
    if not (post_positive + post_refund + post_residual == post_persons):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_processing_status.py:153')
    audit = [
        row_metric(
            "salary_table22_filed_or_processed_population",
            total[0], "persons",
            "CANONICAL_TABLE22_FILED_OR_PROCESSED_POPULATION",
            "Canonical meaning of the 11,423,587 salary-primary Table 2-2(1) population.",
        ),
        row_metric(
            "salary_final_return_row_population",
            final[0], "persons",
            "OBSERVED_FINAL_RETURN_ROW",
            "Pure Final return row within the salary-earner processing table.",
        ),
        row_metric(
            "salary_post_final_return_processing_population",
            post_persons, "persons",
            "OBSERVED_POST_FINAL_RETURN_PROCESSING_COMPONENT",
            "Amended returns plus determinations/corrections and requests for correction.",
        ),
        row_metric(
            "salary_post_final_return_processing_share",
            fmt_ratio(post_persons / total[0]), "ratio",
            "DESCRIPTIVE_PROCESSING_SHARE",
            "Share of the processed total outside the pure Final return row; not a filing-error probability.",
        ),
        row_metric(
            "salary_final_return_row_share",
            fmt_ratio(final[0] / total[0]), "ratio",
            "DESCRIPTIVE_PROCESSING_SHARE",
            "Pure Final return row divided by the filed-or-processed total.",
        ),
        row_metric(
            "salary_total_positive_self_assessed_balance",
            total[1], "persons",
            "OBSERVED_FILED_OR_PROCESSED_STATUS",
            "Positive self-assessed balance within the processed total.",
        ),
        row_metric(
            "salary_final_return_row_positive_self_assessed_balance",
            final[1], "persons",
            "OBSERVED_FINAL_RETURN_ROW_STATUS",
            "Positive self-assessed balance in the pure Final return row.",
        ),
        row_metric(
            "salary_post_final_return_positive_self_assessed_balance",
            post_positive, "persons",
            "OBSERVED_POST_FINAL_RETURN_PROCESSING_COMPONENT",
            "Positive-balance cases attributable to later processing categories.",
        ),
        row_metric(
            "salary_total_refund",
            total[2], "persons",
            "OBSERVED_FILED_OR_PROCESSED_STATUS",
            "Refund cases within the processed total.",
        ),
        row_metric(
            "salary_final_return_row_refund",
            final[2], "persons",
            "OBSERVED_FINAL_RETURN_ROW_STATUS",
            "Refund cases in the pure Final return row.",
        ),
        row_metric(
            "salary_post_final_return_refund",
            post_refund, "persons",
            "OBSERVED_POST_FINAL_RETURN_PROCESSING_COMPONENT",
            "Refund cases attributable to later processing categories.",
        ),
        row_metric(
            "salary_total_neither_positive_nor_refund",
            t22_residual, "persons",
            "OBSERVED_FILED_OR_PROCESSED_RESIDUAL",
            "Processed-total residual after positive-balance and refund cases.",
        ),
        row_metric(
            "salary_final_return_row_neither_positive_nor_refund",
            final_residual, "persons",
            "OBSERVED_FINAL_RETURN_ROW_RESIDUAL",
            "Final-return-row residual after positive-balance and refund cases.",
        ),
        row_metric(
            "salary_post_final_return_neither_positive_nor_refund",
            post_residual, "persons",
            "OBSERVED_POST_FINAL_RETURN_PROCESSING_COMPONENT",
            "Residual-status cases attributable to later processing categories.",
        ),
        row_metric(
            "salary_primary_final_return_population_alias",
            total[0], "persons",
            "DEPRECATED_ALIAS_NOT_PURE_FINAL_RETURN_ROW",
            "Backward-compatible alias only. Use salary_table22_filed_or_processed_population for 11,423,587.",
        ),
    ]
    return rows, audit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows, audit = build()
    outputs = [(OUT_ROWS, render(rows)), (OUT_AUDIT, render(audit))]
    if args.check:
        stale = []
        for path, expected in outputs:
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual != expected:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            raise SystemExit("stale generated artifacts: " + ", ".join(stale))
        print(
            "NTA salary processing-status audit: current "
            "(final-return row=11,293,442; post-final processing=130,145; "
            "filed/processed total=11,423,587)"
        )
        return
    for path, expected in outputs:
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
