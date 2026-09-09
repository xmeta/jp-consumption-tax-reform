#!/usr/bin/env python3
"""Extract FY2024 NTA exact income-class x primary-type filing-status counts.

Source
------
National Tax Agency Annual Statistics Report FY2024, Table 2-2(1),
printed pp.61-62 (PDF pages 71-72).

The two pages report, for 25 total-net-income classes:
* all final-return income earners;
* persons with positive self-assessed income tax;
* refund return filers;
and the same three counts for each of five primary income-earner categories.

Unlike the NTA sample-survey income-class cells, these are administrative
annual-statistics counts.  The mapping from NTA total net income to F71561
equivalized household-income deciles remains unobserved.
"""
from pathlib import Path
import argparse
import csv
import io
import re
import sys

import cryptography
import pypdf
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data/raw/nta/nta_fy2024_annual_statistics.pdf"
CATALOG = ROOT / "data/source_catalog.csv"
SAMPLE = (
    ROOT
    / "data/derived"
    / "nta_positive_self_assessed_balance_income_class_primary_type_2024.csv"
)
OUT = (
    ROOT
    / "data/derived"
    / "nta_income_class_primary_type_filing_status_2024.csv"
)

# Zero-indexed PDF pages corresponding to printed pp.61-62.
PAGE_PART1 = 70
PAGE_PART2 = 71

CATEGORIES = [
    ("business", "事業所得者"),
    ("real_estate", "不動産所得者"),
    ("salary", "給与所得者"),
    ("miscellaneous", "雑所得者"),
    ("other", "他の区分に該当しない所得者"),
]

LABELS = [
    "70万円以下", "100万円", "150万円", "200万円", "250万円",
    "300万円", "400万円", "500万円", "600万円", "700万円",
    "800万円", "1,000万円", "1,200万円", "1,500万円", "2,000万円",
    "3,000万円", "5,000万円", "1億円", "2億円", "5億円",
    "10億円", "20億円", "50億円", "100億円", "100億円超",
]

UPPER_YEN = [
    700_000, 1_000_000, 1_500_000, 2_000_000, 2_500_000,
    3_000_000, 4_000_000, 5_000_000, 6_000_000, 7_000_000,
    8_000_000, 10_000_000, 12_000_000, 15_000_000, 20_000_000,
    30_000_000, 50_000_000, 100_000_000, 200_000_000, 500_000_000,
    1_000_000_000, 2_000_000_000, 5_000_000_000, 10_000_000_000,
    None,
]

# Match integers with optional thousands separators or a dash.  Decimal
# threshold translations such as 0.7 are intentionally split; taking the
# final nine tokens on a data row isolates the nine table counts.
TOKEN_RE = re.compile(r"(?<![\d.])(?:\d{1,3}(?:,\d{3})+|\d+|-)(?![\d.])")


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_token(s):
    if s == "-":
        return 0
    return int(s.replace(",", ""))


def candidate_rows(text):
    out = []
    for line in text.splitlines():
        if not ("万円" in line or "億円" in line):
            continue
        toks = TOKEN_RE.findall(line)
        if len(toks) < 9:
            continue
        values = [parse_token(x) for x in toks[-9:]]
        out.append((line, values))
    return out


def extract_pages():
    reader = PdfReader(PDF)
    t1 = reader.pages[PAGE_PART1].extract_text()
    t2 = reader.pages[PAGE_PART2].extract_text()
    p1 = candidate_rows(t1)
    p2 = candidate_rows(t2)

    # The table has exactly 25 data rows on each part.
    if len(p1) != 25:
        raise RuntimeError(f"part1 expected 25 rows, got {len(p1)}")
    if len(p2) != 25:
        raise RuntimeError(f"part2 expected 25 rows, got {len(p2)}")

    return p1, p2


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def build():
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    src = catalog["NTA-R06"]
    p1, p2 = extract_pages()

    sample = {
        (int(r["income_class_index"]), r["primary_income_type"]):
            int(r["positive_self_assessed_balance_persons_estimated"])
        for r in read_csv(SAMPLE)
    }

    out = []
    prev_upper = None

    for i in range(25):
        # Part 1:
        # total all/positive/refund,
        # business all/positive/refund,
        # real-estate all/positive/refund.
        _, a = p1[i]
        # Part 2:
        # salary all/positive/refund,
        # miscellaneous all/positive/refund,
        # other all/positive/refund.
        _, b = p2[i]

        overall = {
            "all": a[0],
            "positive": a[1],
            "refund": a[2],
        }
        per_cat = {
            "business": (a[3], a[4], a[5]),
            "real_estate": (a[6], a[7], a[8]),
            "salary": (b[0], b[1], b[2]),
            "miscellaneous": (b[3], b[4], b[5]),
            "other": (b[6], b[7], b[8]),
        }

        # Category partitions must exactly reconcile for each status.
        if sum(v[0] for v in per_cat.values()) != overall["all"]:
            raise RuntimeError(f"class {i+1}: all-person category mismatch")
        if sum(v[1] for v in per_cat.values()) != overall["positive"]:
            raise RuntimeError(f"class {i+1}: positive category mismatch")
        if sum(v[2] for v in per_cat.values()) != overall["refund"]:
            raise RuntimeError(f"class {i+1}: refund category mismatch")

        upper = UPPER_YEN[i]
        for category, ja in CATEGORIES:
            all_persons, positive, refund = per_cat[category]
            residual = all_persons - positive - refund
            if residual < 0:
                raise RuntimeError(
                    f"class {i+1} {category}: negative residual {residual}"
                )

            # Independent cross-publication validation against the sample
            # survey Table 2 positive-self-assessed-balance population estimate.
            sample_positive = sample[(i + 1, category)]
            if positive != sample_positive:
                raise RuntimeError(
                    f"class {i+1} {category}: annual positive={positive} "
                    f"!= sample Table2={sample_positive}"
                )

            out.append({
                "income_class_index": i + 1,
                "income_class_label": LABELS[i],
                "lower_bound_yen_exclusive":
                    "" if prev_upper is None else prev_upper,
                "upper_bound_yen_inclusive": "" if upper is None else upper,
                "is_topcoded": "True" if upper is None else "False",
                "primary_income_type": category,
                "primary_income_type_ja": ja,
                "table22_population_persons": all_persons,
                "positive_self_assessed_balance_persons": positive,
                "refund_persons": refund,
                "neither_positive_nor_refund_residual": residual,
                "positive_self_assessed_balance_rate":
                    f"{positive / all_persons:.12g}" if all_persons else "",
                "refund_rate":
                    f"{refund / all_persons:.12g}" if all_persons else "",
                "residual_rate":
                    f"{residual / all_persons:.12g}" if all_persons else "",
                "income_class_all_categories_table22_population_persons":
                    overall["all"],
                "income_class_all_categories_positive_self_assessed_balance_persons":
                    overall["positive"],
                "income_class_all_categories_refund_persons":
                    overall["refund"],
                "sample_survey_positive_self_assessed_balance_cell":
                    sample_positive,
                "sample_crosscheck_difference":
                    positive - sample_positive,
                "source_id": "NTA-R06",
                "source_file": src["raw_file"],
                "source_sha256": src["sha256"],
                "source_locator":
                    "Table 2-2(1), printed pp.61-62 / PDF pages 71-72",
                "source_printed_page":
                    61 if category in {"business", "real_estate"} else 62,
                "source_pdf_page_1based":
                    71 if category in {"business", "real_estate"} else 72,
                "pypdf_version": pypdf.__version__,
                "cryptography_version": cryptography.__version__,
                "population_definition":
                    "Table 2-2(1): persons who filed for 2024 or whose income-tax cases were processed (correction/determination etc.) by 2025-03-31, classified as of 2025-06-30",
                "denominator_note":
                    "table22_population_persons is not the stage-1 NTA Table 2-1 Final-return processing-row numerator and is not restricted to voluntary final-return filings alone",
                "cell_nature": "ADMINISTRATIVE_ANNUAL_STATISTICS_COUNT",
                "evidence_status":
                    "REPRODUCED_OFFICIAL_ADMINISTRATIVE_CROSSTAB",
                "identification_warning":
                    "NTA total net income is not F71561 equivalized disposable income; decile linkage still requires an explicit bridge assumption",
            })

        prev_upper = upper

    if len(out) != 125:
        raise RuntimeError(f"expected 125 rows, got {len(out)}")

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
            print("ERROR: stale NTA annual income-class filing-status cross-tab")
            sys.exit(1)
        print(
            "NTA annual income-class x primary-type filing-status cross-tab: "
            "current (25 classes x 5 types = 125 rows)"
        )
        return

    OUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
