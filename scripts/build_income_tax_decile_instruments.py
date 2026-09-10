#!/usr/bin/env python3
from pathlib import Path
import argparse
import csv
import io
import sys

ROOT = Path(__file__).resolve().parents[1]
LONG31 = ROOT / "data/derived/estat_71531_deciles_long.csv"
LEAF = ROOT / "data/derived/income_tax_household_type_leaf_deciles_2024.csv"
OUT_INST = ROOT / "data/derived/income_tax_decile_tax_social_instruments_2024.csv"
OUT_AUDIT = ROOT / "data/derived/estat_71561_leaf_aggregation_audit.csv"
OUT_TARGET_AUDIT = ROOT / "data/derived/estat_71561_income_tax_target_definition_audit_2024.csv"

TARGET_METHOD_SOURCE = "STAT-NSFCW-2024-ANNUAL-NONCONSUMPTION-METHOD"
CALIBRATION_POLICY = "RETAIN_PUBLISHED_IMPUTED_TARGET_AS_NAMED_CROSS_CONCEPT_SENSITIVITY"

TARGET_DEFINITION_AUDIT = [
    ("collection_status", "estimated per household because annual non-consumption expenditure is not surveyed on the annual-income/assets questionnaire", "synthetic pseudo tax units built from published aggregates", "PUBLISHED_IMPUTED_NOT_DIRECT_OBSERVATION", "NOT_APPLICABLE", "PDF p.1 opening paragraph"),
    ("tax_rule_vintage", "2024 Statistics Bureau tax construction", "2026 ordinary national income-tax statutory parameters", "DIFFERENT_RULE_VINTAGE", "NOT_IDENTIFIED_FROM_PUBLISHED_AGGREGATES", "PDF p.1 tax steps 1-5"),
    ("reconstruction_special_income_tax", "added to estimated income tax", "excluded from ordinary_national_income_tax_2026", "TARGET_INCLUDES_MODEL_EXCLUDES", "NOT_IDENTIFIED_FROM_PUBLISHED_AGGREGATES", "PDF p.1 tax step 4"),
    ("fixed_2024_tax_reduction", "deducted from estimated income tax", "not a 2026 model component", "TARGET_INCLUDES_2024_CREDIT_MODEL_DOES_NOT", "NOT_IDENTIFIED_FROM_PUBLISHED_AGGREGATES", "PDF p.1 tax step 4"),
    ("interest_dividend_tax", "tax amount added under a uniform withholding/separate-tax assumption", "interest_dividend_kY is not consumed by the pseudo-tax-unit calculation", "TARGET_INCLUDES_MODEL_EXCLUDES", "NOT_IDENTIFIED_FROM_PUBLISHED_AGGREGATES", "PDF p.1 tax step 5"),
    ("deduction_scope", "medical, disability, donation and other unavailable/low-frequency deductions are omitted from the official imputation", "selected 2026 deductions are modeled under explicit pseudo-filer scenarios/nuisance calibration", "CONSTRUCTION_SCOPES_DIFFER", "NOT_IDENTIFIED_FROM_PUBLISHED_AGGREGATES", "PDF p.1 paragraph after tax step 5"),
    ("calibration_decision", "published imputed F71561 income-tax amount retained unchanged", "continuous 2026 ordinary-tax proxy is moment-matched to that different concept", "NAMED_CROSS_CONCEPT_SENSITIVITY", "NO_NUMERIC_TRANSFORM; CONCEPT_DIFFERENCE_NOT_IDENTIFIED", "repository calibration policy"),
]

COMPONENTS = {
    "811": ("income_tax_kY", "income_tax_yen"),
    "812": ("resident_tax_kY", "resident_tax_yen"),
    "813": ("public_pension_contribution_kY", "public_pension_contribution_yen"),
    "814": ("health_insurance_contribution_kY", "health_insurance_contribution_yen"),
    "815": ("long_term_care_contribution_kY", "long_term_care_contribution_yen"),
}


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(fields, rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def leaf_num(row, field):
    marker = row[field + "_missing_marker"]
    value = row[field]
    if marker == "X":
        raise ValueError(f"suppressed F71561 value must not be coerced: {field}")
    if marker == "-":
        if value != "":
            raise ValueError(f"structural-missing marker has numeric value: {field}")
        return 0.0
    if marker != "":
        raise ValueError(f"unsupported F71561 missing marker {marker!r}: {field}")
    if value == "":
        raise ValueError(f"unmarked blank F71561 value: {field}")
    return float(value)


def target_definition_rows():
    return [
        {
            "audit_item": item,
            "published_imputed_2024_treatment": target,
            "modeled_2026_ordinary_tax_treatment": model,
            "alignment_status": alignment,
            "numeric_reconciliation_status": numeric,
            "source_id": TARGET_METHOD_SOURCE,
            "source_locator": locator,
            "calibration_policy": CALIBRATION_POLICY,
        }
        for item, target, model, alignment, numeric, locator in TARGET_DEFINITION_AUDIT
    ]


def build():
    l31 = read(LONG31)
    leaf = read(LEAF)
    by_decile = {}
    for d in range(1, 11):
        rows = [r for r in l31 if int(r["decile"]) == d]
        count_row = next(
            r for r in rows
            if r["reported_item"] == "集計世帯数（概数）"
        )
        out = {
            "decile": d,
            "household_count_approx": count_row["numeric_value"],
            "household_count_source_cell": count_row["source_cell"],
            "source_id": "ESTAT-7153-1-2024",
            "source_file": count_row["source_file"],
            "source_sha256": count_row["source_sha256"],
        }
        for code, (ky, yen) in COMPONENTS.items():
            r = next(
                x for x in rows
                if x["income_component_code"] == code
                and x["reported_item"] == "等価年間収入額"
            )
            val = r["numeric_value"]
            out[ky] = val
            out[yen] = "" if val == "" else f"{float(val) * 1000:.10g}"
            out[ky + "_source_cell"] = r["source_cell"]
        by_decile[d] = out

    inst_rows = [by_decile[d] for d in range(1, 11)]

    audit_rows = []
    for d in range(1, 11):
        sub = [r for r in leaf if int(r["decile"]) == d]
        suppressed = [
            r for r in sub
            if r["household_count_approx_missing_marker"] == "X"
        ]
        published = [r for r in sub if r not in suppressed]
        leaf_count = sum(leaf_num(r, "household_count_approx") for r in published)
        numeric_counts = [
            leaf_num(r, "household_count_approx")
            for r in published
            if r["household_count_approx_missing_marker"] == ""
        ]
        numeric_count_lower = sum(max(5.0, x - 5.0) for x in numeric_counts)
        suppressed_upper = 5.0 * len(suppressed)
        suppressed_share_upper = (
            suppressed_upper / (numeric_count_lower + suppressed_upper)
            if suppressed_upper else 0.0
        )
        monetary_x_cells = sum(
            1
            for r in suppressed
            for field in r
            if field.endswith("_missing_marker")
            and field != "household_count_approx_missing_marker"
            and r[field] == "X"
        )
        total_count = float(by_decile[d]["household_count_approx"] or 0)
        tax_total = float(by_decile[d]["income_tax_kY"] or 0)
        tax_num = sum(
            leaf_num(r, "household_count_approx") * leaf_num(r, "income_tax_kY")
            for r in published
        )
        tax_leaf = tax_num / leaf_count if leaf_count else 0.0
        audit_rows.append({
            "decile": d,
            "aggregate_household_count_71531": f"{total_count:.10g}",
            "leaf_household_count_sum_71561": f"{leaf_count:.10g}",
            "household_count_difference": f"{leaf_count-total_count:.10g}",
            "suppressed_leaf_count_cells": len(suppressed),
            "suppressed_household_count_upper_exclusive": f"{suppressed_upper:.10g}",
            "suppressed_count_share_upper_bound_exclusive": f"{suppressed_share_upper:.12g}",
            "suppressed_monetary_x_cells": monetary_x_cells,
            "aggregate_income_tax_kY_71531": f"{tax_total:.10g}",
            "leaf_weighted_income_tax_kY_71561": f"{tax_leaf:.12g}",
            "income_tax_difference_kY": f"{tax_leaf-tax_total:.12g}",
            "suppression_assumption":
                "DROP_F71561_ROWS_WITH_SUPPRESSED_HOUSEHOLD_COUNT",
            "suppression_status": (
                "COUNT_SHARE_BOUNDED_MONETARY_IMPACT_NOT_IDENTIFIED"
                if suppressed else "NO_SUPPRESSED_LEAF_COUNT"
            ),
            "interpretation":
                "rounding diagnostic; X rows are explicitly dropped, not zero-imputed",
            "aggregate_count_source_cell": by_decile[d]["household_count_source_cell"],
            "aggregate_income_tax_source_cell":
                by_decile[d]["income_tax_kY_source_cell"],
            "source_ids":
                "ESTAT-7153-1-2024;ESTAT-7156-1-2024;STAT-NSFCW-2024-USAGE-NOTES",
        })

    return inst_rows, audit_rows, target_definition_rows()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    inst, audit, target_audit = build()

    inst_fields = list(inst[0])
    audit_fields = list(audit[0])
    target_audit_fields = list(target_audit[0])
    expected_inst = render(inst_fields, inst)
    expected_audit = render(audit_fields, audit)
    expected_target_audit = render(target_audit_fields, target_audit)

    if args.check:
        stale = []
        for path, expected in [
            (OUT_INST, expected_inst),
            (OUT_AUDIT, expected_audit),
            (OUT_TARGET_AUDIT, expected_target_audit),
        ]:
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual != expected:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            print("ERROR: stale decile instrument/audit outputs: " + ", ".join(stale))
            sys.exit(1)
        print("income-tax decile instrument/audit outputs: current")
        return

    OUT_INST.write_text(expected_inst, encoding="utf-8")
    OUT_AUDIT.write_text(expected_audit, encoding="utf-8")
    OUT_TARGET_AUDIT.write_text(expected_target_audit, encoding="utf-8")
    print(f"wrote {OUT_INST.relative_to(ROOT)}: {len(inst)} rows")
    print(f"wrote {OUT_AUDIT.relative_to(ROOT)}: {len(audit)} rows")
    print(f"wrote {OUT_TARGET_AUDIT.relative_to(ROOT)}: {len(target_audit)} rows")


if __name__ == "__main__":
    main()
