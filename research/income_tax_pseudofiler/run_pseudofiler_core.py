#!/usr/bin/env python3
"""Reproducible pseudo-filer statutory-MTR sensitivity core.

This is a new reproduction, not a claim of byte-identical execution of the
historical V6 script.  It uses only repository-tracked official/derived inputs.

Identification status:
    SENSITIVITY_ONLY_NOT_IDENTIFIED

The model constructs pseudo tax units from aggregate household-type cells,
calibrates one nuisance income scale per decile/scenario to the published/imputed
F71561 income-tax construction moment under a named cross-concept sensitivity,
and reports statutory-bracket diagnostics.
It does not identify the true filer MTR distribution.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import io
import math
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from statutory_2026 import (  # noqa: E402
    employment_income_2026,
    basic_deduction_2026,
    ordinary_income_tax_rate_2026,
    ordinary_national_income_tax_continuous_proxy_2026,
    ordinary_national_income_tax_2026,
    public_pension_misc_income_2026,
)

LEAF = ROOT / "data/derived/income_tax_household_type_leaf_deciles_2024.csv"
BRIDGE = ROOT / "data/derived/income_tax_bridge_deciles_2024.csv"
INST = ROOT / "data/derived/income_tax_decile_tax_social_instruments_2024.csv"
NTA_SOCIAL = ROOT / "data/derived/nta_salary_class_social_deduction_schedule_2024.csv"
NTA_FAMILY = ROOT / "data/derived/nta_salary_class_family_deduction_validation_2024.csv"
F71551_AGE = ROOT / "data/derived/income_tax_age_income_source_shares_2024.csv"

OUT_CAL = HERE / "pseudofiler_calibration.csv"
OUT_SCEN = HERE / "pseudofiler_mtr_scenarios.csv"
OUT_SUM = HERE / "pseudofiler_mtr_summary.csv"
OUT_GROUP = HERE / "household_worker_groups.csv"

STATUS = "SENSITIVITY_ONLY_NOT_IDENTIFIED"
INPUT_SOURCE_IDS = (
    "ESTAT-7156-1-2024;ESTAT-7191-1-2024;ESTAT-7153-1-2024;"
    "NTA-2026-TAX-REFORM;NTA-2026-INCOME-TAX;"
    "NTA-SALARY-DEDUCTION-1410;NTA-INCOME-TAX-RATE-2260;"
    "NTA-2026-PENSION-TAX;NTA-2026-PENSION-DETAIL;"
    "NTA-MINKAN-2024-T17;NTA-2026-DEPENDENT-DEDUCTION;"
    "ESTAT-7155-1-2024;STAT-NSFCW-2024-ANNUAL-NONCONSUMPTION-METHOD"
)
STATUTORY_ARTIFACT = "data/derived/income_tax_2026_statutory_parameters.csv"
CALIBRATION_TARGET_CONCEPT = "STATISTICS_BUREAU_PUBLISHED_IMPUTED_2024_INCOME_TAX"
CALIBRATION_TARGET_SOURCE_ID = "STAT-NSFCW-2024-ANNUAL-NONCONSUMPTION-METHOD"
MODELED_TAX_CONCEPT = "2026_ORDINARY_NATIONAL_INCOME_TAX_EXCLUDING_RECONSTRUCTION_SPECIAL_INCOME_TAX"
TARGET_MODEL_ALIGNMENT = "NAMED_CROSS_CONCEPT_SENSITIVITY"
TARGET_NUMERIC_RECONCILIATION = "NO_NUMERIC_TRANSFORM; CONCEPT_DIFFERENCE_NOT_IDENTIFIED"

SIZE_BOUNDS = {
    "011": (1.0, 1.0),
    "012": (2.0, 5.0),
    "013": (2.0, 4.0),
    "014": (3.0, 6.0),
    "021": (1.0, 1.0),
    "022": (2.0, 4.0),
}

SCENARIOS = {
    # size mode, bridge target col, business, other split, social, pension
    "central": (
        "calibrated", "household_size_proxy", "head", 1,
        "proportional", "absorbed_in_nuisance",
    ),
    "f71911_topcode10": (
        "calibrated", "household_size_proxy_topcode10", "head", 1,
        "proportional", "absorbed_in_nuisance",
    ),
    "size_lower": (
        "lower", "household_size_proxy", "head", 1,
        "proportional", "absorbed_in_nuisance",
    ),
    "size_upper": (
        "upper", "household_size_proxy", "head", 1,
        "proportional", "absorbed_in_nuisance",
    ),
    "business_proportional": (
        "calibrated", "household_size_proxy", "proportional", 1,
        "proportional", "absorbed_in_nuisance",
    ),
    "other_wage_split2": (
        "calibrated", "household_size_proxy", "head", 2,
        "proportional", "absorbed_in_nuisance",
    ),
    "no_social_deduction_proxy": (
        "calibrated", "household_size_proxy", "head", 1,
        "none", "absorbed_in_nuisance",
    ),
    "nta_salary_social": (
        "calibrated", "household_size_proxy", "head", 1,
        "nta_salary_class", "absorbed_in_nuisance",
    ),
    "nta_salary_dependents": (
        "calibrated", "household_size_proxy", "head", 1,
        "proportional", "absorbed_in_nuisance",
    ),
    "pension_head_merge": (
        "calibrated", "household_size_proxy", "head", 1,
        "proportional", "merge_to_head_by_household_head_age",
    ),
    "pension_age_split_separate": (
        "calibrated", "household_size_proxy", "head", 1,
        "proportional", "separate_by_F71551_age_share",
    ),
    "pension_member_split": (
        "calibrated", "household_size_proxy", "head", 1,
        "proportional", "member_split_by_F71911_age_share",
    ),
    "pension_member_split_f71551": (
        "calibrated", "household_size_proxy", "head", 1,
        "proportional", "member_split_by_F71551_age_share",
    ),
}

MTR_GRID = [0.0, 0.05, 0.10, 0.20, 0.23, 0.33, 0.40, 0.45]


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


_NTA_SOCIAL_ROWS = None
_NTA_FAMILY_ROWS = None


def salary_class_lookup(gross_wage_yen, path, value_col):
    global _NTA_SOCIAL_ROWS, _NTA_FAMILY_ROWS
    if path == NTA_SOCIAL:
        if _NTA_SOCIAL_ROWS is None:
            _NTA_SOCIAL_ROWS = read_csv(path)
        rows = _NTA_SOCIAL_ROWS
    elif path == NTA_FAMILY:
        if _NTA_FAMILY_ROWS is None:
            _NTA_FAMILY_ROWS = read_csv(path)
        rows = _NTA_FAMILY_ROWS
    else:
        raise ValueError(path)

    g = max(float(gross_wage_yen), 0.0)
    if g <= 0:
        return 0.0
    rows = sorted(rows, key=lambda r: float(r["upper_salary_yen_inclusive"]))
    chosen = rows[-1]
    for r in rows:
        if g <= float(r["upper_salary_yen_inclusive"]):
            chosen = r
            break
    return num(chosen[value_col])


def nta_salary_social_proxy(gross_wage_yen):
    return salary_class_lookup(
        gross_wage_yen,
        NTA_SOCIAL,
        "average_social_insurance_deduction_per_employee_yen",
    )


def nta_salary_dependent_proxy(gross_wage_yen):
    return salary_class_lookup(
        gross_wage_yen,
        NTA_FAMILY,
        "dependent_deduction_2026_amounts_on_2024_composition_per_employee_yen",
    )


def num(x):
    if x in ("", None, "-"):
        return 0.0
    if x == "X":
        raise ValueError("suppressed value X must not be coerced to zero")
    return float(x)


def leaf_num(row, field):
    marker = row[field + "_missing_marker"]
    value = row[field]
    if marker == "X":
        raise ValueError(
            f"suppressed F71561 value must not enter pseudo-filer: {field}"
        )
    if marker == "-":
        if value != "":
            raise ValueError(f"structural-missing marker has numeric value: {field}")
        return 0.0
    if marker != "":
        raise ValueError(f"unsupported F71561 missing marker {marker!r}: {field}")
    if value == "":
        raise ValueError(f"unmarked blank F71561 value: {field}")
    return float(value)


def modeled_leaf_rows(rows):
    modeled = []
    suppressed = []
    for row in rows:
        marker = row["household_count_approx_missing_marker"]
        if marker == "X":
            suppressed.append(row)
            continue
        for field, value in row.items():
            if field.endswith("_missing_marker") and value == "X":
                raise ValueError(
                    "monetary X with non-suppressed household count must not be imputed: "
                    + field
                )
        modeled.append(row)
    return modeled, suppressed


def suppression_metadata(modeled, suppressed):
    numeric_counts = [
        leaf_num(row, "household_count_approx")
        for row in modeled
        if row["household_count_approx_missing_marker"] == ""
    ]
    numeric_count_lower = sum(max(5.0, x - 5.0) for x in numeric_counts)
    suppressed_upper = 5.0 * len(suppressed)
    share_upper = (
        suppressed_upper / (numeric_count_lower + suppressed_upper)
        if suppressed_upper else 0.0
    )
    monetary_x = sum(
        1
        for row in suppressed
        for field, value in row.items()
        if field.endswith("_missing_marker")
        and field != "household_count_approx_missing_marker"
        and value == "X"
    )
    return {
        "suppression_assumption":
            "DROP_F71561_ROWS_WITH_SUPPRESSED_HOUSEHOLD_COUNT",
        "suppressed_leaf_rows_omitted": len(suppressed),
        "suppressed_household_count_upper_exclusive": suppressed_upper,
        "suppressed_count_share_upper_bound_exclusive": share_upper,
        "suppressed_monetary_x_cells_without_numeric_bound": monetary_x,
        "suppression_residual_status": (
            "MONETARY_X_IMPACT_NOT_IDENTIFIED"
            if monetary_x else
            "COUNT_ONLY_X_BOUNDED_BY_OFFICIAL_DISCLOSURE_RULE"
            if suppressed else
            "NO_SUPPRESSED_LEAF_COUNT"
        ),
    }


def fmt(x):
    if isinstance(x, bool):
        return "True" if x else "False"
    if isinstance(x, (int, str)):
        return str(x)
    return f"{float(x):.12g}"


def size_bounds(household_type):
    for prefix, bounds in SIZE_BOUNDS.items():
        if household_type.startswith(prefix):
            return bounds
    raise ValueError(f"unmapped household type: {household_type}")


def weighted_mean(pairs):
    total_w = sum(w for _, w in pairs)
    if total_w <= 0:
        return 0.0
    return sum(x * w for x, w in pairs) / total_w


def calibrated_size_map(rows, bridge_row, target_col):
    weights = [leaf_num(r, "household_count_approx") for r in rows]
    lo = weighted_mean([
        (size_bounds(r["household_type"])[0], w)
        for r, w in zip(rows, weights)
    ])
    hi = weighted_mean([
        (size_bounds(r["household_type"])[1], w)
        for r, w in zip(rows, weights)
    ])
    target = num(bridge_row[target_col])
    q = 0.0 if hi <= lo else min(max((target - lo) / (hi - lo), 0.0), 1.0)
    out = {}
    for r in rows:
        a, b = size_bounds(r["household_type"])
        out[r["household_type"]] = a + q * (b - a)
    calibrated = weighted_mean([
        (out[r["household_type"]], w)
        for r, w in zip(rows, weights)
    ])
    return out, {
        "target_household_size_proxy": target,
        "target_bridge_column": target_col,
        "logical_lower_weighted_size": lo,
        "logical_upper_weighted_size": hi,
        "interpolation_q": q,
        "calibrated_weighted_size": calibrated,
        "target_inside_logical_bounds": lo <= target <= hi,
    }


def scenario_size_map(rows, bridge_row, scenario):
    size_mode, target_col, *_ = SCENARIOS[scenario]
    central, meta = calibrated_size_map(rows, bridge_row, target_col)
    if size_mode == "calibrated":
        return central, meta
    out = {}
    for r in rows:
        lo, hi = size_bounds(r["household_type"])
        out[r["household_type"]] = lo if size_mode == "lower" else hi
    meta = dict(meta)
    meta["calibrated_weighted_size"] = weighted_mean([
        (out[r["household_type"]], leaf_num(r, "household_count_approx"))
        for r in rows
    ])
    return out, meta


def new_unit(label, gross_wage=0.0, pre_basic=0.0):
    return {
        "label": label,
        "gross_wage": float(gross_wage),
        "pre_basic": float(pre_basic),
        "social": 0.0,
    }


def build_units(row, size, scenario, contrib_eq_yen, senior_share):
    _, _, business_mode, other_split, social_mode, pension_mode = SCENARIOS[scenario]
    scale = math.sqrt(size)

    head_w = leaf_num(row, "head_wage_kY") * 1000.0 * scale
    spouse_w = leaf_num(row, "spouse_wage_kY") * 1000.0 * scale
    other_total = leaf_num(row, "other_member_wage_kY") * 1000.0 * scale

    units = [
        new_unit("head", head_w, employment_income_2026(head_w)),
        new_unit("spouse", spouse_w, employment_income_2026(spouse_w)),
    ]
    if other_total > 0:
        n = max(1, int(other_split))
        for i in range(n):
            w = other_total / n
            units.append(new_unit(
                f"other_{i+1}", w, employment_income_2026(w)
            ))

    business = leaf_num(row, "business_kY") * 1000.0 * scale
    if business > 0:
        if business_mode == "head":
            units[0]["pre_basic"] += business
        elif business_mode == "proportional":
            denom = sum(u["gross_wage"] for u in units)
            if denom > 0:
                for u in units:
                    u["pre_basic"] += business * u["gross_wage"] / denom
            else:
                units[0]["pre_basic"] += business
        else:
            raise ValueError(business_mode)

    pension_total = leaf_num(row, "public_pension_kY") * 1000.0 * scale
    if pension_mode == "absorbed_in_nuisance":
        pass
    elif pension_mode == "merge_to_head_by_household_head_age":
        if pension_total > 0:
            head65 = row["household_type"].startswith("02")
            units[0]["pre_basic"] += public_pension_misc_income_2026(
                pension_total, head65, units[0]["pre_basic"]
            )
    elif pension_mode == "separate_by_F71551_age_share":
        if pension_total > 0:
            p65 = pension_total * senior_share
            pu65 = pension_total - p65
            if pu65 > 0:
                units.append(new_unit(
                    "pension_separate_u65",
                    0.0,
                    public_pension_misc_income_2026(pu65, False, 0.0),
                ))
            if p65 > 0:
                units.append(new_unit(
                    "pension_separate_65p",
                    0.0,
                    public_pension_misc_income_2026(p65, True, 0.0),
                ))
    elif pension_mode in {
        "member_split_by_F71911_age_share",
        "member_split_by_F71551_age_share",
    }:
        if pension_total > 0:
            head_p = leaf_num(row, "head_public_pension_kY") * 1000.0 * scale
            spouse_p = leaf_num(row, "spouse_public_pension_kY") * 1000.0 * scale
            other_p = leaf_num(row, "other_member_public_pension_kY") * 1000.0 * scale
            residual = max(pension_total - head_p - spouse_p - other_p, 0.0)

            if head_p > 0:
                head65 = row["household_type"].startswith("02")
                units[0]["pre_basic"] += public_pension_misc_income_2026(
                    head_p, head65, units[0]["pre_basic"]
                )

            for label, amount in [
                ("spouse_pension", spouse_p),
                ("other_pension", other_p),
                ("pension_residual", residual),
            ]:
                if amount <= 0:
                    continue
                p65 = amount * senior_share
                pu65 = amount - p65
                if pu65 > 0:
                    units.append(new_unit(
                        label + "_u65",
                        0.0,
                        public_pension_misc_income_2026(pu65, False, 0.0),
                    ))
                if p65 > 0:
                    units.append(new_unit(
                        label + "_65p",
                        0.0,
                        public_pension_misc_income_2026(p65, True, 0.0),
                    ))
    else:
        raise ValueError(pension_mode)

    if social_mode == "proportional":
        household_social = contrib_eq_yen * scale
        denom = sum(u["gross_wage"] for u in units)
        if denom > 0:
            for u in units:
                u["social"] = household_social * u["gross_wage"] / denom
        else:
            denom = sum(u["pre_basic"] for u in units)
            if denom > 0:
                for u in units:
                    u["social"] = household_social * u["pre_basic"] / denom
    elif social_mode == "nta_salary_class":
        for u in units:
            u["social"] = nta_salary_social_proxy(u["gross_wage"])
    elif social_mode != "none":
        raise ValueError(social_mode)

    return units, scale


def household_tax(row, size, nuisance_scale, scenario, contrib_eq_yen,
                  senior_share, return_units=False):
    units, eq_scale = build_units(
        row, size, scenario, contrib_eq_yen, senior_share
    )
    out_units = []
    total_calibration_tax = 0.0
    for u in units:
        calibrated_income = u["pre_basic"] * nuisance_scale
        basic = basic_deduction_2026(calibrated_income)
        family = (
            nta_salary_dependent_proxy(u["gross_wage"])
            if scenario == "nta_salary_dependents"
            else 0.0
        )
        taxable = max(calibrated_income - basic - u["social"] - family, 0.0)
        calibration_tax = ordinary_national_income_tax_continuous_proxy_2026(taxable)
        tax = ordinary_national_income_tax_2026(taxable)
        rounded_taxable = math.floor(taxable / 1000.0) * 1000.0
        mtr = ordinary_income_tax_rate_2026(rounded_taxable)
        total_calibration_tax += calibration_tax
        if return_units:
            v = dict(u)
            v.update({
                "calibrated_income": calibrated_income,
                "basic_deduction": basic,
                "dependent_deduction_external_proxy": family,
                "taxable_income": taxable,
                "rounded_taxable_income": rounded_taxable,
                "calibration_income_tax": calibration_tax,
                "income_tax": tax,
                "mtr": mtr,
            })
            out_units.append(v)
    eq_tax_kY = total_calibration_tax / eq_scale / 1000.0
    if return_units:
        return eq_tax_kY, out_units
    return eq_tax_kY


def published_imputed_decile_tax(rows):
    return weighted_mean([
        (leaf_num(r, "income_tax_kY"), leaf_num(r, "household_count_approx"))
        for r in rows
    ])


def predicted_decile_tax(rows, size_map, nuisance, scenario, contrib, senior):
    return weighted_mean([
        (
            household_tax(
                r, size_map[r["household_type"]], nuisance,
                scenario, contrib, senior
            ),
            leaf_num(r, "household_count_approx"),
        )
        for r in rows if leaf_num(r, "household_count_approx") > 0
    ])


def predicted_decile_exact_tax(rows, size_map, nuisance, scenario, contrib, senior):
    pairs = []
    for r in rows:
        weight = leaf_num(r, "household_count_approx")
        if weight <= 0:
            continue
        size = size_map[r["household_type"]]
        _, units = household_tax(
            r, size, nuisance, scenario, contrib, senior, return_units=True
        )
        exact_eq_kY = (
            sum(u["income_tax"] for u in units)
            / math.sqrt(size)
            / 1000.0
        )
        pairs.append((exact_eq_kY, weight))
    return weighted_mean(pairs)


def calibrate(rows, size_map, scenario, contrib, senior, target):
    lo, hi = 0.0, 8.0
    plo = predicted_decile_tax(rows, size_map, lo, scenario, contrib, senior)
    phi = predicted_decile_tax(rows, size_map, hi, scenario, contrib, senior)
    while phi < target and hi < 64:
        hi *= 2
        phi = predicted_decile_tax(rows, size_map, hi, scenario, contrib, senior)
    if target < plo - 1e-9 or target > phi + 1e-9:
        raise RuntimeError(
            f"target {target} outside calibration range [{plo},{phi}]"
        )

    best = (abs(plo - target), lo, plo)
    cand = (abs(phi - target), hi, phi)
    if cand < best:
        best = cand

    for _ in range(90):
        mid = (lo + hi) / 2.0
        pmid = predicted_decile_tax(
            rows, size_map, mid, scenario, contrib, senior
        )
        cand = (abs(pmid - target), mid, pmid)
        if cand < best:
            best = cand
        if pmid < target:
            lo = mid
        else:
            hi = mid

    # Also evaluate both sides of the final discontinuity.
    for x in [lo, hi, (lo + hi) / 2.0]:
        px = predicted_decile_tax(
            rows, size_map, x, scenario, contrib, senior
        )
        cand = (abs(px - target), x, px)
        if cand < best:
            best = cand
    return best[1], best[2]


def worker_group(htype):
    if htype in {
        "0111_無業", "0121_無業", "0131_有業者なし",
        "0141_有業者なし", "0211_無業", "0221_有業者なし",
    }:
        return "zero_worker_label"
    if htype in {
        "0112_有業", "0122_有業", "0132_有業者１人",
        "0142_有業者１人", "0212_有業",
    }:
        return "one_worker_label"
    if htype in {"0133_有業者２人以上", "0143_有業者２人以上"}:
        return "two_plus_worker_label"
    if htype == "0222_有業者１人以上":
        return "one_plus_unspecified_label"
    return "unmapped"


def build_outputs():
    leaf = read_csv(LEAF)
    bridge = {int(r["decile"]): r for r in read_csv(BRIDGE)}
    inst = {int(r["decile"]): r for r in read_csv(INST)}
    f71551_age = {int(r["decile"]): r for r in read_csv(F71551_AGE)}

    calibration = []
    scenarios_out = []
    groups = []
    suppression_by_decile = {}

    for d in range(1, 11):
        all_rows = [r for r in leaf if int(r["decile"]) == d]
        rows, suppressed_rows = modeled_leaf_rows(all_rows)
        suppression = suppression_metadata(rows, suppressed_rows)
        suppression_by_decile[d] = suppression
        target_tax = published_imputed_decile_tax(rows)
        total_count = sum(leaf_num(r, "household_count_approx") for r in rows)

        for group in [
            "zero_worker_label",
            "one_worker_label",
            "two_plus_worker_label",
            "one_plus_unspecified_label",
        ]:
            sub = [r for r in rows if worker_group(r["household_type"]) == group]
            count = sum(leaf_num(r, "household_count_approx") for r in sub)
            tax_num = sum(
                leaf_num(r, "household_count_approx") * leaf_num(r, "income_tax_kY")
                for r in sub
            )
            all_tax_num = sum(
                leaf_num(r, "household_count_approx") * leaf_num(r, "income_tax_kY")
                for r in rows
            )
            groups.append({
                "decile": d,
                "worker_group": group,
                "household_count_approx": count,
                "household_share_within_leaf_partition":
                    count / total_count if total_count else 0.0,
                "published_imputed_income_tax_share":
                    tax_num / all_tax_num if all_tax_num else 0.0,
                "source_id": "ESTAT-7156-1-2024",
                "model_status": STATUS,
            })

        contrib = (
            num(inst[d]["public_pension_contribution_yen"])
            + num(inst[d]["health_insurance_contribution_yen"])
            + num(inst[d]["long_term_care_contribution_yen"])
        )
        senior_f71911 = num(bridge[d]["senior_share_65p"])
        senior_f71551 = num(
            f71551_age[d]["age65p_share_of_public_pension_amount_proxy"]
        )

        for scenario in SCENARIOS:
            size_mode, _, business_mode, other_split, social_mode, pension_mode = (
                SCENARIOS[scenario]
            )
            senior = (
                senior_f71551
                if "F71551" in pension_mode
                else senior_f71911
            )
            senior_source = (
                "F71551 public-pension amount proxy"
                if "F71551" in pension_mode
                else "F71911 aggregate age65+ person share"
            )
            size_map, size_meta = scenario_size_map(
                rows, bridge[d], scenario
            )
            nuisance, fit = calibrate(
                rows, size_map, scenario, contrib, senior, target_tax
            )
            exact_fit = predicted_decile_exact_tax(
                rows, size_map, nuisance, scenario, contrib, senior
            )
            calibration.append({
                "decile": d,
                "scenario": scenario,
                "nuisance_income_scale": nuisance,
                "published_imputed_leaf_weighted_income_tax_kY": target_tax,
                "reconstructed_continuous_proxy_income_tax_kY": fit,
                "continuous_proxy_fit_error_kY": abs(fit - target_tax),
                "reconstructed_exact_statutory_income_tax_kY": exact_fit,
                "exact_statutory_rounding_gap_kY": exact_fit - target_tax,
                "calibration_tax_basis":
                    "continuous quick-table proxy before 1000-yen taxable-income rounding",
                **size_meta,
                "size_mode": size_mode,
                "business_allocation": business_mode,
                "other_member_wage_split": other_split,
                "social_deduction_proxy": social_mode,
                "family_deduction_proxy": (
                    "NTA2024 dependent composition x 2026 statutory amounts"
                    if scenario == "nta_salary_dependents"
                    else "none/absorbed in nuisance"
                ),
                "pension_mode": pension_mode,
                "senior_share_65p": senior,
                "senior_share_source": senior_source,
                "nuisance_parameter_interpretation":
                    "moment-matching scale; not behavioral or causal",
                "model_status": STATUS,
                "input_source_ids": INPUT_SOURCE_IDS,
                "statutory_parameter_artifact": STATUTORY_ARTIFACT,
                "calibration_target_concept": CALIBRATION_TARGET_CONCEPT,
                "calibration_target_source_id": CALIBRATION_TARGET_SOURCE_ID,
                "modeled_tax_concept": MODELED_TAX_CONCEPT,
                "target_model_alignment_status": TARGET_MODEL_ALIGNMENT,
                "target_numeric_reconciliation_status": TARGET_NUMERIC_RECONCILIATION,
            })

            tax_units = []
            for r in rows:
                count = leaf_num(r, "household_count_approx")
                if count <= 0:
                    continue
                _, units = household_tax(
                    r, size_map[r["household_type"]], nuisance,
                    scenario, contrib, senior, return_units=True
                )
                for u in units:
                    if u["pre_basic"] <= 0 and u["income_tax"] <= 0:
                        continue
                    tax_units.append((count, u))

            total_weight = sum(w for w, _ in tax_units)
            taxable_weight = sum(
                w * max(u["taxable_income"], 0.0) for w, u in tax_units
            )
            liability_weight = sum(
                w * max(u["income_tax"], 0.0) for w, u in tax_units
            )
            filer_mtr = (
                sum(w * u["mtr"] for w, u in tax_units) / total_weight
                if total_weight else 0.0
            )
            taxable_mtr = (
                sum(
                    w * max(u["taxable_income"], 0.0) * u["mtr"]
                    for w, u in tax_units
                ) / taxable_weight if taxable_weight else 0.0
            )
            liability_mtr = (
                sum(
                    w * max(u["income_tax"], 0.0) * u["mtr"]
                    for w, u in tax_units
                ) / liability_weight if liability_weight else 0.0
            )
            positive_share = (
                sum(w for w, u in tax_units if u["income_tax"] > 0)
                / total_weight if total_weight else 0.0
            )

            out = {
                "decile": d,
                "scenario": scenario,
                "nuisance_income_scale": nuisance,
                "pseudo_filer_weighted_mean_MTR": filer_mtr,
                "taxable_income_weighted_mean_MTR": taxable_mtr,
                "income_tax_liability_weighted_mean_MTR": liability_mtr,
                "pseudo_positive_modeled_annual_income_tax_share": positive_share,
                "continuous_proxy_fit_error_kY": abs(fit - target_tax),
                "exact_statutory_rounding_gap_kY": exact_fit - target_tax,
                "MTR_status":
                    "continuous-moment-calibrated statutory-bracket diagnostic; not observed filer MTR",
                "model_status": STATUS,
                "input_source_ids": INPUT_SOURCE_IDS,
            }
            for rate in MTR_GRID:
                key = str(rate).replace(".", "p")
                out[f"pseudo_filer_share_MTR_{key}"] = (
                    sum(w for w, u in tax_units if abs(u["mtr"] - rate) < 1e-12)
                    / total_weight if total_weight else 0.0
                )
            scenarios_out.append(out)

    summary = []
    for d in range(1, 11):
        rows = [r for r in scenarios_out if int(r["decile"]) == d]
        central = next(r for r in rows if r["scenario"] == "central")
        suppression = suppression_by_decile[d]
        summary.append({
            "decile": d,
            "central_taxable_income_weighted_MTR":
                central["taxable_income_weighted_mean_MTR"],
            "min_taxable_income_weighted_MTR_across_scenarios":
                min(r["taxable_income_weighted_mean_MTR"] for r in rows),
            "max_taxable_income_weighted_MTR_across_scenarios":
                max(r["taxable_income_weighted_mean_MTR"] for r in rows),
            "central_liability_weighted_MTR":
                central["income_tax_liability_weighted_mean_MTR"],
            "min_liability_weighted_MTR_across_scenarios":
                min(r["income_tax_liability_weighted_mean_MTR"] for r in rows),
            "max_liability_weighted_MTR_across_scenarios":
                max(r["income_tax_liability_weighted_mean_MTR"] for r in rows),
            "central_pseudo_positive_modeled_annual_income_tax_share":
                central["pseudo_positive_modeled_annual_income_tax_share"],
            "central_nuisance_income_scale": central["nuisance_income_scale"],
            "max_continuous_proxy_fit_error_kY":
                max(r["continuous_proxy_fit_error_kY"] for r in rows),
            "max_absolute_exact_statutory_rounding_gap_kY":
                max(abs(r["exact_statutory_rounding_gap_kY"]) for r in rows),
            "suppression_assumption": suppression["suppression_assumption"],
            "suppressed_leaf_rows_omitted": suppression["suppressed_leaf_rows_omitted"],
            "suppressed_household_count_upper_exclusive":
                suppression["suppressed_household_count_upper_exclusive"],
            "suppressed_count_share_upper_bound_exclusive":
                suppression["suppressed_count_share_upper_bound_exclusive"],
            "suppressed_monetary_x_cells_without_numeric_bound":
                suppression["suppressed_monetary_x_cells_without_numeric_bound"],
            "suppression_residual_status": suppression["suppression_residual_status"],
            "structural_MTR_identified": False,
            "recommended_use":
                "sensitivity/ETI input only; not point input for optimal policy",
            "model_status": STATUS,
            "scenario_count": len(rows),
            "input_source_ids": INPUT_SOURCE_IDS,
            "statutory_parameter_artifact": STATUTORY_ARTIFACT,
            "calibration_target_concept": CALIBRATION_TARGET_CONCEPT,
            "calibration_target_source_id": CALIBRATION_TARGET_SOURCE_ID,
            "modeled_tax_concept": MODELED_TAX_CONCEPT,
            "target_model_alignment_status": TARGET_MODEL_ALIGNMENT,
            "target_numeric_reconciliation_status": TARGET_NUMERIC_RECONCILIATION,
        })
    return calibration, scenarios_out, summary, groups


def render(rows):
    fields = list(rows[0])
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: fmt(v) for k, v in r.items()})
    return b.getvalue()


def specs():
    cal, scen, summ, groups = build_outputs()
    return [
        (OUT_CAL, cal),
        (OUT_SCEN, scen),
        (OUT_SUM, summ),
        (OUT_GROUP, groups),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    outputs = specs()
    if args.check:
        stale = []
        for path, rows in outputs:
            expected = render(rows)
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if expected != actual:
                stale.append(path.name)
        if stale:
            print("ERROR: stale pseudo-filer outputs: " + ", ".join(stale))
            raise SystemExit(1)
        print("pseudo-filer core: current (13 scenarios x 10 deciles)")
        return
    for path, rows in outputs:
        path.write_text(render(rows), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
