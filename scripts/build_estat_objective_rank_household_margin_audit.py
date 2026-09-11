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
OUT_RESTRICTED_ROUTES = ROOT / "data/derived/estat_objective_rank_restricted_route_audit_2024.csv"
OUT_RESTRICTED_VARIABLES = ROOT / "data/derived/estat_objective_rank_restricted_variable_map_2024.csv"

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



def _meta_rows(catalog: dict[str, dict[str, str]], source_id: str, expected_aggregate: str) -> tuple[dict[str, dict[str, str]], str]:
    source = catalog[source_id]
    x = XlsxStream(ROOT / source["raw_file"])
    rows: list[tuple[int, dict[str, str]]] = []
    try:
        rows = list(x.rows())
    finally:
        x.close()
    if rows[0][1].get("B") != "00200564" or expected_aggregate not in rows[1][1].get("F", ""):
        raise RuntimeError(f"{source_id}: unexpected 2024 NSFCW metadata header")
    by_var = {v.get("N", ""): v for rn, v in rows if rn >= 9 and v.get("N")}
    return by_var, rows[1][1].get("B", "")


def build_restricted_route() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    ds51, ds51_name = _meta_rows(catalog, "EMICRO-NSFCW-2024-DS51-META", "所得資産集計体系")
    ds52, ds52_name = _meta_rows(catalog, "EMICRO-NSFCW-2024-DS52-META", "細分類")

    expected = {
        "DS51": ["SetaiFugo", "Ichiren", "SetaiID", "Setaijinnin", "I_Bdy001", "I_Bdy031", "M_Weight_Ippan_ZenkokuKen"],
        "DS52": ["SetaiFugo", "Ichiren", "SetaiID", "Setaijinnin", "M_Nenshu", "Bdy003", "Bdy004", "Bdy015", "Bdy016", "Bdy233", "M_Weight_Ippan_ZenkokuKen"],
    }
    for code, names in expected.items():
        table = ds51 if code == "DS51" else ds52
        missing = [name for name in names if name not in table]
        if missing:
            raise RuntimeError(f"{code}: required metadata variables missing: {missing}")
    if "2024年集計" not in ds51["SetaiID"].get("I", "") or "2024年集計" not in ds52["SetaiID"].get("I", ""):
        raise RuntimeError("SetaiID 2024 non-use guard missing from official metadata")

    def variable_row(dataset_code: str, source_id: str, table: dict[str, dict[str, str]], name: str, role: str, bridge_use: str, guard: str) -> dict[str, object]:
        v = table[name]
        return {
            "dataset_code": dataset_code,
            "source_id": source_id,
            "variable_name": name,
            "variable_label": v.get("D", ""),
            "position": v.get("E", ""),
            "role": role,
            "unit_or_definition": v.get("I", ""),
            "statistical_unit": "HOUSEHOLD",
            "objective_rank_concept": "OECD_NEW_EQUIVALIZED_DISPOSABLE_INCOME_DECILE",
            "availability_status": "OBSERVED_OFFICIAL_METADATA",
            "bridge_use": bridge_use,
            "guard": guard,
        }

    variables = [
        variable_row("M4AR8-DS51", "EMICRO-NSFCW-2024-DS51-META", ds51, "SetaiFugo", "candidate_cross_system_household_key", "candidate join component; provider confirmation required", "Metadata does not itself authorize or prove DS51-DS52 joining."),
        variable_row("M4AR8-DS51", "EMICRO-NSFCW-2024-DS51-META", ds51, "Ichiren", "candidate_cross_system_household_key", "candidate join component; provider confirmation required", "Must not be treated as a stable cross-system key without provider confirmation."),
        variable_row("M4AR8-DS51", "EMICRO-NSFCW-2024-DS51-META", ds51, "SetaiID", "nonusable_2024_household_id", "none", "Official metadata says empty / not used for 2024 aggregation."),
        variable_row("M4AR8-DS51", "EMICRO-NSFCW-2024-DS51-META", ds51, "Setaijinnin", "equivalization_input", "household-size input needed for the official equivalized-disposable-income rank construction", "Use the official NSFCW equivalization rule; do not invent a rank mapping."),
        variable_row("M4AR8-DS51", "EMICRO-NSFCW-2024-DS51-META", ds51, "I_Bdy001", "annual_household_income", "annual-income side of the joint bridge", "Annual household income is not the objective rank."),
        variable_row("M4AR8-DS51", "EMICRO-NSFCW-2024-DS51-META", ds51, "I_Bdy031", "oecd_new_annual_disposable_income", "income numerator for the objective-rank construction", "Do not relabel annual-income deciles as this rank."),
        variable_row("M4AR8-DS51", "EMICRO-NSFCW-2024-DS51-META", ds51, "M_Weight_Ippan_ZenkokuKen", "population_weight", "weighted household objective-rank distribution", "Use only under the provider-approved population/weight definition."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "SetaiFugo", "candidate_cross_system_household_key", "candidate join component; provider confirmation required", "Metadata does not itself authorize or prove DS51-DS52 joining."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "Ichiren", "candidate_cross_system_household_key", "candidate join component; provider confirmation required", "Must not be treated as a stable cross-system key without provider confirmation."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "SetaiID", "nonusable_2024_household_id", "none", "Official metadata says empty / not used for 2024 aggregation."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "Setaijinnin", "household_size", "same-household consistency check if cross-system join is approved", "Not a substitute for DS51 OECD-new annual disposable income."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "M_Nenshu", "annual_household_income", "annual-income rank / consistency variable on expenditure records", "Annual income remains a distinct rank concept from objective rank."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "Bdy003", "consumption_expenditure", "household consumption denominator / expenditure diagnostic", "Two-month-average accounting measure; not itself a legal VAT base."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "Bdy004", "food_expenditure", "VAT rate-scope input", "Broad food is not identical to the reduced-rate legal base."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "Bdy015", "alcohol_expenditure", "VAT rate-scope exclusion input", "Category-level mapping remains an accounting proxy."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "Bdy016", "dining_out_expenditure", "VAT rate-scope exclusion input", "Category-level mapping remains an accounting proxy."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "Bdy233", "newspaper_expenditure", "VAT rate-scope sensitivity input", "Qualifying subscription status is not identified by the category alone."),
        variable_row("M4AR8-DS52", "EMICRO-NSFCW-2024-DS52-META", ds52, "M_Weight_Ippan_ZenkokuKen", "population_weight", "weighted expenditure distribution", "Use only under the provider-approved population/weight definition."),
    ]

    query_source = catalog["EMICRO-2026-ONSITE-NSFCW-QUERY"]
    query = (ROOT / query_source["raw_file"]).read_text(encoding="utf-8", errors="ignore")
    if "2024年" not in query or 'data-list-id="658126"' not in query:
        raise RuntimeError("2024 NSFCW onsite listing not verified")
    guidance = (ROOT / catalog["EMICRO-ONSITE-USE-GUIDANCE"]["raw_file"]).read_text(encoding="utf-8", errors="ignore")
    if "オンサイト施設" not in guidance or "所定の審査" not in guidance:
        raise RuntimeError("onsite access/output-review guidance not verified")
    custom = (ROOT / catalog["NSTAC-CUSTOM-TABULATION-GUIDANCE"]["raw_file"]).read_text(encoding="utf-8", errors="ignore")
    custom_text = re.sub(r"<[^>]+>", " ", html.unescape(custom))
    custom_text = re.sub(r"\s+", " ", custom_text)
    m = re.search(r"全国家計構造調査\s*（全国消費実態調査）(.*?)労働力調査", custom_text)
    if not m or "2019年" not in m.group(1):
        raise RuntimeError("current NSFCW custom-tabulation year listing not verified")
    custom_2024 = "2024年" in m.group(1)

    routes = [
        {
            "route_id": "NSFCW_2024_ONSITE_DS51_X_DS52",
            "provider": "Statistics Bureau of Japan / National Statistics Center via e-Micro",
            "year": "2024",
            "access_mode": "ON_SITE_QUESTIONNAIRE_INFORMATION",
            "datasets": f"M4AR8-DS51:{ds51_name};M4AR8-DS52:{ds52_name}",
            "household_unit": "HOUSEHOLD",
            "objective_rank_definition": "OECD_NEW_EQUIVALIZED_DISPOSABLE_INCOME_DECILE_FROM_DS51_I_Bdy031_PLUS_OFFICIAL_EQUIVALIZATION_INPUTS",
            "expenditure_definition": "DS52_DETAILED_TWO_MONTH_AVERAGE_HOUSEHOLD_EXPENDITURE_WITH_RATE_SCOPE_PROXY_INPUTS",
            "household_join_status": "SHARED_SETAIFUGO_AND_ICHIREN_OBSERVED;EXACT_CROSS_SYSTEM_JOIN_KEY_PROVIDER_CONFIRMATION_REQUIRED;SETAIID_NOT_USED_2024",
            "access_status": "LISTED_AVAILABLE_ONSITE_2024",
            "expected_identification_gain": "DIRECT_HOUSEHOLD_JOINT_RANK_BRIDGE_IF_CROSS_SYSTEM_JOIN_CONFIRMED",
            "current_identification_status": "NOT_IDENTIFIED_PENDING_ACCESS_AND_JOIN_CONFIRMATION",
            "access_disclosure_reproducibility": "Secure onsite application required; raw questionnaire microdata cannot be checked into this repository; disclosure-reviewed outputs plus code/specification are the reproducible boundary.",
            "stop_rule": "STOP_PUBLIC_AGGREGATE_SEARCH;NEXT_ACTION_PROVIDER_JOIN_CONFIRMATION_AND_ONSITE_APPLICATION",
            "source_ids": "EMICRO-2026-ONSITE-NSFCW-QUERY;EMICRO-NSFCW-2024-DS51-META;EMICRO-NSFCW-2024-DS52-META;EMICRO-ONSITE-USE-GUIDANCE",
        },
        {
            "route_id": "NSFCW_2024_ONSITE_DS51_ONLY",
            "provider": "Statistics Bureau of Japan / e-Micro",
            "year": "2024",
            "access_mode": "ON_SITE_QUESTIONNAIRE_INFORMATION",
            "datasets": f"M4AR8-DS51:{ds51_name}",
            "household_unit": "HOUSEHOLD",
            "objective_rank_definition": "HAS_OECD_NEW_ANNUAL_DISPOSABLE_INCOME_INPUT",
            "expenditure_definition": "NO_DETAILED_CONSUMPTION_FILE_IN_THIS_DATASET",
            "household_join_status": "NOT_APPLICABLE_SINGLE_DATASET",
            "access_status": "LISTED_AVAILABLE_ONSITE_2024",
            "expected_identification_gain": "NO_DIRECT_VAT_EXPENDITURE_BRIDGE_ALONE",
            "current_identification_status": "INSUFFICIENT_ALONE",
            "access_disclosure_reproducibility": "Same onsite/disclosure constraints as the primary route.",
            "stop_rule": "DO_NOT_SUBSTITUTE_OBJECTIVE_RANK_MARGIN_FOR_JOINT_HOUSEHOLD_BRIDGE",
            "source_ids": "EMICRO-NSFCW-2024-DS51-META;EMICRO-ONSITE-USE-GUIDANCE",
        },
        {
            "route_id": "NSFCW_2024_ONSITE_DS52_ONLY",
            "provider": "Statistics Bureau of Japan / e-Micro",
            "year": "2024",
            "access_mode": "ON_SITE_QUESTIONNAIRE_INFORMATION",
            "datasets": f"M4AR8-DS52:{ds52_name}",
            "household_unit": "HOUSEHOLD",
            "objective_rank_definition": "NO_DS51_I_Bdy031_OECD_NEW_ANNUAL_DISPOSABLE_INCOME_VARIABLE",
            "expenditure_definition": "HAS_DETAILED_TWO_MONTH_AVERAGE_EXPENDITURE_AND_WEIGHTS",
            "household_join_status": "NOT_APPLICABLE_SINGLE_DATASET",
            "access_status": "LISTED_AVAILABLE_ONSITE_2024",
            "expected_identification_gain": "NO_EXACT_OBJECTIVE_RANK_BRIDGE_ALONE",
            "current_identification_status": "INSUFFICIENT_ALONE",
            "access_disclosure_reproducibility": "Same onsite/disclosure constraints as the primary route.",
            "stop_rule": "DO_NOT_RELABEL_ANNUAL_INCOME_OR_DS52_DISPOSABLE_INCOME_AS_OBJECTIVE_RANK",
            "source_ids": "EMICRO-NSFCW-2024-DS52-META;EMICRO-ONSITE-USE-GUIDANCE",
        },
        {
            "route_id": "NSFCW_2024_CUSTOM_TABULATION",
            "provider": "National Statistics Center",
            "year": "2024",
            "access_mode": "CUSTOM_TABULATION",
            "datasets": "REQUESTED_2024_NSFCW_CUSTOM_TABLE",
            "household_unit": "HOUSEHOLD",
            "objective_rank_definition": "REQUEST_OBJECTIVE_RANK_X_EXPENDITURE_TABLE_IF_PROVIDER_SUPPORTS_2024",
            "expenditure_definition": "REQUEST_HOUSEHOLD_EXPENDITURE_OR_VAT_RATE_SCOPE_CROSSTAB",
            "household_join_status": "PROVIDER_PERFORMS_TABULATION_NO_USER_MICRODATA_JOIN",
            "access_status": "NOT_CURRENTLY_LISTED_FOR_2024" if not custom_2024 else "LISTED_FOR_2024",
            "expected_identification_gain": "DIRECT_AGGREGATE_JOINT_BRIDGE_IF_2024_CUSTOM_SPEC_ACCEPTED;OTHERWISE_NO_GAIN",
            "current_identification_status": "NOT_AVAILABLE_FROM_CURRENT_LISTING" if not custom_2024 else "PENDING_SPECIFICATION",
            "access_disclosure_reproducibility": "Fee-based specification and provider disclosure rules; resulting table can be provenance-registered if supplied.",
            "stop_rule": "DO_NOT_ASSUME_2024_SERVICE_FROM_2019_LISTING;REOPEN_ONLY_ON_PROVIDER_CONFIRMATION",
            "source_ids": "NSTAC-CUSTOM-TABULATION-GUIDANCE",
        },
        {
            "route_id": "PUBLIC_AGGREGATE_TABLE_SEARCH",
            "provider": "e-Stat public tables",
            "year": "2024",
            "access_mode": "PUBLIC_AGGREGATE",
            "datasets": "SEVEN_ALREADY_AUDITED_SOURCE_FAMILIES",
            "household_unit": "MIXED_HOUSEHOLD_PERSON_SAMPLE_COUNT",
            "objective_rank_definition": "PUBLIC_OBJECTIVE_RANK_PERSON_MARGIN_ONLY",
            "expenditure_definition": "ANNUAL_INCOME_RANK_HOUSEHOLD_EXPENDITURE_ONLY",
            "household_join_status": "NO_DIRECT_JOINT_TABLE_IN_AUDITED_FAMILIES",
            "access_status": "PUBLIC",
            "expected_identification_gain": "NO_FURTHER_GAIN_UNDER_EXISTING_AUDIT",
            "current_identification_status": "PUBLIC_AGGREGATE_HOUSEHOLD_MARGIN_NOT_IDENTIFIED",
            "access_disclosure_reproducibility": "Fully reproducible public route already captured in repository.",
            "stop_rule": "STOP_PUBLIC_SEARCH_UNLESS_NEW_SOURCE_SUPPLIES_HOUSEHOLD_JOINT_BRIDGE_OR_OBJECTIVE_RANK_POPULATION_HOUSEHOLD_MARGIN",
            "source_ids": "ESTAT-OBJECTIVE-RANK-HOUSEHOLD-MARGIN-SOURCE-MATRIX-2024",
        },
    ]
    return routes, variables

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
    routes, variables = build_restricted_route()
    write_or_check(OUT_MATRIX, matrix, args.check)
    write_or_check(OUT_AUDIT, audit, args.check)
    write_or_check(OUT_RESTRICTED_ROUTES, routes, args.check)
    write_or_check(OUT_RESTRICTED_VARIABLES, variables, args.check)
    if args.check:
        print(
            "NSFCW objective-rank household-margin audit: current "
            "(7 public source families; 2024 onsite route mapped; join confirmation pending)"
        )


if __name__ == "__main__":
    main()
