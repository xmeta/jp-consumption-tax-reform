#!/usr/bin/env python3
"""Audit public 2024 NSFCW margins for an annual-income -> objective-rank bridge.

The audit is deliberately bounded to the official source families enumerated
below.  A negative result means that those examined public tables do not expose
a same-unit household population margin for the OECD-new equivalized-disposable-
income deciles.  It does not claim that unpublished microdata or administrative
linkage do not exist.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import html
import io
import re

from extract_estat_income_tax_tables import XlsxStream

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/source_catalog.csv"
ANNUAL = ROOT / "data/derived/estat_2024_annual_income_decile_expenditure_diagnostic.csv"
OBJECTIVE_PERSON = ROOT / "data/derived/estat_71411_main_income_by_disposable_decile_2024.csv"
F71531 = ROOT / "data/derived/estat_71531_deciles_long.csv"
F71561 = ROOT / "data/derived/estat_71561_deciles_long.csv"
OUT_MATRIX = ROOT / "data/derived/estat_objective_rank_household_margin_source_matrix_2024.csv"
OUT_AUDIT = ROOT / "data/derived/estat_objective_rank_household_margin_identification_audit_2024.csv"

NEW_HTML_SOURCES = {
    "ESTAT-7142-1-2-2024-DBVIEW": {
        "table_number": "7-142-1-2",
        "rank": "OECD_NEW_EQUIVALIZED_DISPOSABLE_INCOME_DECILE",
        "objective": "YES",
        "expected_title_tokens": ["世帯員数", "等価可処分所得十分位階級", "OECD新基準"],
        "forbidden_title_tokens": ["世帯数・世帯員数", "年間可処分所得十分位階級"],
        "body_household_distribution": "NO",
        "unit": "HOUSEHOLD_MEMBER",
        "note": "Official DB view exposes household-member counts by OECD-new equivalized-disposable-income class/decile, not household population counts.",
    },
    "ESTAT-7145-1-2024-DBVIEW": {
        "table_number": "7-145-1",
        "rank": "OECD_NEW_EQUIVALIZED_DISPOSABLE_INCOME_DECILE",
        "objective": "YES",
        "expected_title_tokens": ["世帯員数", "等価可処分所得十分位階級", "世帯類型", "OECD新基準"],
        "forbidden_title_tokens": ["世帯数・世帯員数", "年間可処分所得十分位階級"],
        "body_household_distribution": "NO",
        "unit": "HOUSEHOLD_MEMBER",
        "note": "Official household-type table remains person-unit (household members); household-type detail does not create household population decile margins.",
    },
    "ESTAT-762-1-2024-DBVIEW": {
        "table_number": "7-62-1",
        "rank": "HOUSEHOLD_ANNUAL_DISPOSABLE_INCOME_DECILE_OECD_NEW",
        "objective": "NO",
        "expected_title_tokens": ["世帯数・世帯員数", "年間可処分所得十分位階級", "OECD新基準"],
        "forbidden_title_tokens": ["等価可処分所得十分位階級"],
        "body_household_distribution": "YES",
        "unit": "HOUSEHOLD_AND_MEMBER",
        "note": "A public household-count distribution exists for annual disposable-income deciles, but that rank is not equivalized disposable income and cannot close the objective-rank bridge.",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows: list[dict[str, object]]) -> str:
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def og_title(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    m = re.search(r'<meta property="og:title" content="([^"]+)"', text)
    if not m:
        raise RuntimeError(f"og:title missing: {path}")
    return html.unescape(m.group(1)), text


def workbook_row2_title(path: Path) -> str:
    x = XlsxStream(path)
    try:
        for row_no, values in x.rows():
            if row_no == 2:
                return values.get("A", "")
            if row_no > 2:
                break
    finally:
        x.close()
    raise RuntimeError(f"row-2 title missing: {path}")


def sample_counts(rows: list[dict[str, str]], *, household_type: str | None = None) -> list[int]:
    hits = []
    for r in rows:
        if r.get("reported_item") != "集計世帯数（概数）":
            continue
        if r.get("income_component_code") != "0":
            continue
        if household_type is not None and r.get("household_type_code") != household_type:
            continue
        hits.append((int(r["decile"]), int(r["numeric_value"])))
    hits.sort()
    if len(hits) != 10:
        raise RuntimeError(f"expected 10 sample-count deciles, got {len(hits)}")
    return [v for _, v in hits]


def build() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    annual = read_csv(ANNUAL)
    objective = read_csv(OBJECTIVE_PERSON)
    rows31 = read_csv(F71531)
    rows61 = read_csv(F71561)

    annual_population = [int(r["population_households"]) for r in annual]
    annual_sample = [int(r["approx_sample_households"]) for r in annual]
    if not (len(annual_population) == 10):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_estat_objective_rank_household_margin_audit.py:123')
    if not (set(annual_population) == {5355441}):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_estat_objective_rank_household_margin_audit.py:124')

    objective_totals = [
        int(r["household_members"])
        for r in objective
        if r["semantic_key"] == "total"
    ]
    if not (len(objective_totals) == 10):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_estat_objective_rank_household_margin_audit.py:131')
    if not (set(objective_totals) == {11390017}):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_estat_objective_rank_household_margin_audit.py:132')

    sample31 = sample_counts(rows31)
    sample61 = sample_counts(rows61, household_type="00")
    if not (sample31 == sample61):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_estat_objective_rank_household_margin_audit.py:136')
    if not (sum(sample31) == 74150):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_estat_objective_rank_household_margin_audit.py:137')

    for sid in ("ESTAT-7153-1-2024", "ESTAT-7156-1-2024"):
        source = catalog[sid]
        title = workbook_row2_title(ROOT / source["raw_file"])
        if "等価可処分所得十分位階級" not in title or "OECD新基準" not in title:
            raise RuntimeError(f"{sid}: objective-rank title semantics not verified")

    matrix: list[dict[str, object]] = [
        {
            "source_family_id": "annual_income_expenditure_table_1_21",
            "source_id": "ESTAT-NSFCW-2024-T1-21-ANNUAL-INCOME-DECILE-EXPENDITURE",
            "table_number": "1-21",
            "rank_concept": "HOUSEHOLD_ANNUAL_INCOME_DECILE",
            "rank_is_objective": "NO",
            "statistical_unit": "HOUSEHOLD",
            "population_household_margin": "YES_5355441_PER_DECILE",
            "population_person_margin": "NO",
            "approx_sample_household_margin": "YES_SUM_" + str(sum(annual_sample)),
            "usable_as_objective_rank_household_margin": "NO_WRONG_RANK",
            "note": "Observed expenditure source supplies household population margins for annual household-income deciles only.",
        },
        {
            "source_family_id": "objective_rank_main_income_table_7_141_1",
            "source_id": "ESTAT-7141-1-2024",
            "table_number": "7-141-1",
            "rank_concept": "OECD_NEW_EQUIVALIZED_DISPOSABLE_INCOME_DECILE",
            "rank_is_objective": "YES",
            "statistical_unit": "HOUSEHOLD_MEMBER",
            "population_household_margin": "NO",
            "population_person_margin": "YES_11390017_PER_DECILE",
            "approx_sample_household_margin": "NO",
            "usable_as_objective_rank_household_margin": "NO_UNIT_MISMATCH",
            "note": "Published decile totals are household members (persons), not households.",
        },
        {
            "source_family_id": "objective_rank_income_component_table_7_153_1",
            "source_id": "ESTAT-7153-1-2024",
            "table_number": "7-153-1",
            "rank_concept": "OECD_NEW_EQUIVALIZED_DISPOSABLE_INCOME_DECILE",
            "rank_is_objective": "YES",
            "statistical_unit": "APPROX_SAMPLE_HOUSEHOLD_COUNT_FOR_AGGREGATION",
            "population_household_margin": "NO",
            "population_person_margin": "NO_DIRECT_MARGIN_IN_DERIVED_EXTRACT",
            "approx_sample_household_margin": "YES_SUM_74150",
            "usable_as_objective_rank_household_margin": "NO_SAMPLE_NOT_POPULATION_WEIGHT",
            "note": "The published 'aggregate households (approx.)' values sum to 74,150 and are retained as survey aggregation counts, not population household weights.",
        },
        {
            "source_family_id": "objective_rank_household_type_table_7_156_1",
            "source_id": "ESTAT-7156-1-2024",
            "table_number": "7-156-1",
            "rank_concept": "OECD_NEW_EQUIVALIZED_DISPOSABLE_INCOME_DECILE",
            "rank_is_objective": "YES",
            "statistical_unit": "APPROX_SAMPLE_HOUSEHOLD_COUNT_FOR_AGGREGATION",
            "population_household_margin": "NO",
            "population_person_margin": "NO_DIRECT_MARGIN_IN_DERIVED_EXTRACT",
            "approx_sample_household_margin": "YES_TOTAL_HOUSEHOLD_TYPE_SUM_74150",
            "usable_as_objective_rank_household_margin": "NO_SAMPLE_NOT_POPULATION_WEIGHT",
            "note": "Household-type detail reproduces the same approximate aggregation counts for total households; it does not publish population household decile margins.",
        },
    ]

    for sid, spec in NEW_HTML_SOURCES.items():
        source = catalog.get(sid)
        if source is None:
            raise RuntimeError(f"source catalog missing {sid}")
        title, body = og_title(ROOT / source["raw_file"])
        for token in spec["expected_title_tokens"]:
            if token not in title:
                raise RuntimeError(f"{sid}: expected title token missing: {token}")
        for token in spec["forbidden_title_tokens"]:
            if token in title:
                raise RuntimeError(f"{sid}: forbidden title token found: {token}")
        has_household_distribution = "YES" if "世帯数分布" in body else "NO"
        if has_household_distribution != spec["body_household_distribution"]:
            raise RuntimeError(
                f"{sid}: unexpected household-distribution availability: {has_household_distribution}"
            )
        matrix.append({
            "source_family_id": sid.lower().replace("-", "_"),
            "source_id": sid,
            "table_number": spec["table_number"],
            "rank_concept": spec["rank"],
            "rank_is_objective": spec["objective"],
            "statistical_unit": spec["unit"],
            "population_household_margin": (
                "YES_PUBLISHED_HOUSEHOLD_DISTRIBUTION"
                if has_household_distribution == "YES" else "NO"
            ),
            "population_person_margin": (
                "YES_PUBLISHED_HOUSEHOLD_MEMBER_COUNT"
                if "世帯員数" in title else "NO"
            ),
            "approx_sample_household_margin": "NO",
            "usable_as_objective_rank_household_margin": (
                "NO_WRONG_RANK"
                if spec["objective"] == "NO"
                else "NO_UNIT_MISMATCH"
            ),
            "note": spec["note"],
        })

    objective_rows = [r for r in matrix if r["rank_is_objective"] == "YES"]
    usable = [
        r for r in objective_rows
        if str(r["population_household_margin"]).startswith("YES")
    ]
    direct_joint = []  # No examined table contains both annual-income and objective-rank deciles.

    audit = [
        {
            "metric_id": "examined_official_source_families",
            "value": str(len(matrix)),
            "identification_status": "BOUNDED_OFFICIAL_SOURCE_AUDIT",
            "note": "Enumerated source families only; not a claim about unpublished microdata.",
        },
        {
            "metric_id": "annual_income_household_population_margin_available",
            "value": "YES_5355441_PER_DECILE",
            "identification_status": "OBSERVED_PUBLIC",
            "note": "Table 1-21 household annual-income deciles provide equal population-household margins.",
        },
        {
            "metric_id": "objective_rank_population_person_margin_available",
            "value": "YES_11390017_PER_DECILE",
            "identification_status": "OBSERVED_PUBLIC",
            "note": "Table 7-141-1 publishes equal household-member/person totals across objective-rank deciles.",
        },
        {
            "metric_id": "objective_rank_approx_sample_household_count_available",
            "value": "YES_SUM_74150",
            "identification_status": "OBSERVED_PUBLIC_SAMPLE_AGGREGATION_COUNT",
            "note": "Tables 7-153-1 and 7-156-1 expose approximate aggregation-household counts; these are not population weights.",
        },
        {
            "metric_id": "objective_rank_population_household_margin_available",
            "value": "NO_IN_EXAMINED_OFFICIAL_SOURCE_FAMILIES",
            "identification_status": "PUBLIC_AGGREGATE_HOUSEHOLD_MARGIN_NOT_IDENTIFIED",
            "note": "No examined objective-rank table publishes a population household margin. This bounded negative audit does not claim absence from unpublished microdata.",
        },
        {
            "metric_id": "same_unit_household_transport_margins_identified",
            "value": "NO",
            "identification_status": "NOT_IDENTIFIED",
            "note": "Annual-income rank has household population margins; objective rank has person population margins and sample-household counts, not household population margins.",
        },
        {
            "metric_id": "direct_annual_income_x_objective_rank_joint_table_available",
            "value": "NO_IN_EXAMINED_OFFICIAL_SOURCE_FAMILIES" if not direct_joint else "YES",
            "identification_status": "PUBLIC_AGGREGATE_JOINT_RANK_LINK_NOT_IDENTIFIED",
            "note": "No examined source jointly cross-tabulates household annual-income decile and OECD-new equivalized-disposable-income decile.",
        },
        {
            "metric_id": "frechet_household_rank_transport_status",
            "value": "BLOCKED_NO_OBJECTIVE_RANK_HOUSEHOLD_POPULATION_MARGIN",
            "identification_status": "DO_NOT_BUILD_TRANSPORT_LP",
            "note": "A household-unit Fréchet transport requires household margins on both ranks; substituting person deciles or sample counts would change the estimand/unit.",
        },
        {
            "metric_id": "same_rank_mapping_status",
            "value": "PROHIBITED_WITHOUT_EVIDENCE",
            "identification_status": "ASSUMPTION_NOT_ADOPTED",
            "note": "Annual household income and equivalized disposable income are distinct rank concepts.",
        },
        {
            "metric_id": "person_decile_as_household_margin_status",
            "value": "PROHIBITED",
            "identification_status": "UNIT_MISMATCH",
            "note": "The 11,390,017 objective-decile totals are household members, not households.",
        },
        {
            "metric_id": "independent_rank_coupling_status",
            "value": "NOT_ADOPTED",
            "identification_status": "UNSUPPORTED_IDENTIFYING_ASSUMPTION",
            "note": "Independence is not introduced merely to manufacture a bridge.",
        },
        {
            "metric_id": "vat_gini_fgt2_objective_rank_effect_status",
            "value": "NOT_IDENTIFIED",
            "identification_status": "PENDING_VALID_RANK_BRIDGE_AND_VAT_INCIDENCE_MODEL",
            "note": "The household tax-content envelope remains an annual-income-rank accounting diagnostic and is not propagated to objective-rank Gini/FGT2.",
        },
    ]

    if usable:
        raise RuntimeError(f"unexpected usable objective-rank household margin: {usable}")
    return matrix, audit


def write_or_check(path: Path, rows: list[dict[str, object]], check: bool) -> None:
    expected = render(rows)
    if check:
        actual = path.read_text(encoding="utf-8") if path.exists() else ""
        if actual != expected:
            raise SystemExit(f"stale generated artifact: {path.relative_to(ROOT)}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    matrix, audit = build()
    write_or_check(OUT_MATRIX, matrix, args.check)
    write_or_check(OUT_AUDIT, audit, args.check)
    if args.check:
        print(
            "NSFCW objective-rank household-margin audit: current "
            "(7 source families; no objective-rank population household margin)"
        )


if __name__ == "__main__":
    main()
