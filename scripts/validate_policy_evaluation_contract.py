#!/usr/bin/env python3
"""Validate the identification-gated policy-evaluation contract."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "data/policy_evaluation_contract.csv"
STATE = "data/scientific_state.csv"
PARETO = "research/vat_policy_integration/pareto_objectives.csv"

LAYERS = {
    "IDENTIFICATION_GATE", "VIABILITY_CONSTRAINT", "PARETO_OBJECTIVE",
    "EXTENDED_OBJECTIVE", "CONSTRAINT_FAMILY", "DASHBOARD",
    "SECONDARY_DECISION_RULE",
}
DIRECTIONS = {"none", "maximize", "minimize", "gte", "within_range"}
BOOL = {"true", "false"}
CONTRACT_FIELDS = [
    "item_id", "layer", "direction", "component_id", "direct_optimizer_input",
    "allowed_nonready_use", "required_for_headline", "formula_or_rule",
    "normative_status", "notes",
]
CORE_OBJECTIVES = {
    "cumulative_per_capita_real_growth",
    "per_capita_growth_decline_penalty",
    "median_real_equivalized_disposable_income_effect",
    "real_gdp_per_hour_effect",
    "income_gini_effect", "fgt2_effect",
}
EXTENDED_OBJECTIVES = {"wealth_gini_effect", "intergenerational_gap_effect"}
AGGREGATE_DIAGNOSTICS = {
    "overall_real_gdp_level", "cumulative_real_growth",
    "growth_decline_penalty", "aggregate_recession_downside",
}
CONSTRAINT_FAMILIES = {
    "inflation_guardrail", "debt_service_guardrail",
    "jgb_market_function_guardrail", "exchange_rate_guardrail",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    contract_path = root / CONTRACT
    state_path = root / STATE
    pareto_path = root / PARETO
    for path in (contract_path, state_path, pareto_path):
        if not path.exists():
            errors.append(f"missing policy-evaluation input: {path.relative_to(root)}")
    if errors:
        return errors

    with contract_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CONTRACT_FIELDS:
            return ["policy-evaluation contract schema mismatch"]
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        errors.append("policy-evaluation contract row-width mismatch")
    states = {row["component_id"]: row for row in read_csv(state_path)}
    pareto = read_csv(pareto_path)
    ids = [row.get("item_id", "") for row in rows]
    if not ids or len(ids) != len(set(ids)) or any(not value for value in ids):
        errors.append("policy-evaluation item_id values must be non-empty and unique")

    by_id = {row["item_id"]: row for row in rows if row.get("item_id")}
    for row in rows:
        item = row.get("item_id", "<missing>")
        layer = row.get("layer", "")
        direction = row.get("direction", "")
        direct = row.get("direct_optimizer_input", "").lower()
        required = row.get("required_for_headline", "").lower()
        component_id = row.get("component_id", "")
        nonready_use = row.get("allowed_nonready_use", "")
        if layer not in LAYERS:
            errors.append(f"{item}: invalid layer {layer!r}")
        if direction not in DIRECTIONS:
            errors.append(f"{item}: invalid direction {direction!r}")
        if direct not in BOOL or required not in BOOL:
            errors.append(f"{item}: boolean fields must be true/false")
        if component_id:
            state = states.get(component_id)
            if state is None:
                errors.append(f"{item}: unknown component_id {component_id}")
                continue
            if state.get("active", "").lower() != "true":
                errors.append(f"{item}: component {component_id} is not active")
            if direct == "true":
                if state.get("maturity") != "READY" or state.get("policy_usable", "").lower() != "true":
                    errors.append(
                        f"{item}: direct optimizer input requires maturity=READY and policy_usable=true"
                    )
            if state.get("maturity") in {"SENSITIVITY_ONLY", "PARTIALLY_IDENTIFIED"}:
                if nonready_use not in {"ROBUSTNESS_FRONTIER_ONLY", "DASHBOARD_ONLY"}:
                    errors.append(f"{item}: non-ready component use must be robustness/dashboard only")

    gate = by_id.get("identification_gate")
    if gate is None or gate.get("layer") != "IDENTIFICATION_GATE":
        errors.append("identification_gate row is required")
    elif "maturity=READY" not in gate.get("formula_or_rule", "") or "policy_usable=true" not in gate.get("formula_or_rule", ""):
        errors.append("identification_gate must require maturity=READY and policy_usable=true")

    viability = by_id.get("per_capita_real_growth_viability")
    if viability is None or viability.get("layer") != "VIABILITY_CONSTRAINT":
        errors.append("per_capita_real_growth_viability constraint is required")
    elif "g_pc,t>=epsilon_pc" not in viability.get("formula_or_rule", "") or "epsilon_pc>0" not in viability.get("formula_or_rule", ""):
        errors.append("per_capita_real_growth_viability must encode strict positive per-capita growth via pre-specified epsilon_pc>0")

    objective_ids = {row["item_id"] for row in rows if row.get("layer") == "PARETO_OBJECTIVE"}
    if objective_ids != CORE_OBJECTIVES:
        errors.append(
            "Pareto objective contract mismatch: expected " + ",".join(sorted(CORE_OBJECTIVES))
        )
    for objective_id in CORE_OBJECTIVES:
        row = by_id.get(objective_id)
        if row and row.get("required_for_headline", "").lower() != "true":
            errors.append(f"{objective_id}: core Pareto objective must be headline-required")

    median = by_id.get("median_real_equivalized_disposable_income_effect")
    if median is not None:
        rule = median.get("formula_or_rule", "")
        if "person-weighted median" not in rule or "sqrt(household_size)" not in rule:
            errors.append("median real income objective must specify person weighting and sqrt household-size equivalence")
        if "household price deflator" not in rule:
            errors.append("median real income objective must pre-specify a household price deflator")

    productivity = by_id.get("real_gdp_per_hour_effect")
    if productivity is not None and "Y/H" not in productivity.get("formula_or_rule", ""):
        errors.append("real_gdp_per_hour_effect must encode Y/H productivity")

    extended_ids = {row["item_id"] for row in rows if row.get("layer") == "EXTENDED_OBJECTIVE"}
    if extended_ids != EXTENDED_OBJECTIVES:
        errors.append("extended-objective contract mismatch")
    for objective_id in EXTENDED_OBJECTIVES:
        row = by_id.get(objective_id)
        if row and row.get("required_for_headline", "").lower() != "false":
            errors.append(f"{objective_id}: extended objective must not be headline-required")

    dashboard_ids = {row["item_id"] for row in rows if row.get("layer") == "DASHBOARD"}
    if not AGGREGATE_DIAGNOSTICS <= dashboard_ids:
        errors.append("aggregate C_Y/D_g/R_g and GDP level must remain dashboard diagnostics")

    constraint_ids = {row["item_id"] for row in rows if row.get("layer") == "CONSTRAINT_FAMILY"}
    if constraint_ids != CONSTRAINT_FAMILIES:
        errors.append("constraint-family contract mismatch")

    pareto_ids = {row.get("objective_id", "") for row in pareto}
    if pareto_ids != CORE_OBJECTIVES:
        errors.append("VAT Pareto implementation must match the core Pareto objective contract")
    forbidden = CONSTRAINT_FAMILIES & pareto_ids
    if forbidden:
        errors.append("constraint families must not be scalar/Pareto objectives: " + ",".join(sorted(forbidden)))

    regret = by_id.get("minimax_regret")
    if regret is None or regret.get("layer") != "SECONDARY_DECISION_RULE":
        errors.append("minimax_regret secondary rule is required")
    elif regret.get("normative_status") != "EXPLICIT_NORMATIVE_SECONDARY_RULE":
        errors.append("minimax_regret must be explicitly normative")

    if not dashboard_ids:
        errors.append("at least one dashboard metric is required")
    if dashboard_ids & CORE_OBJECTIVES:
        errors.append("dashboard metrics and Pareto objectives must remain distinct")
    return errors


def main() -> None:
    errors = validate(ROOT)
    if errors:
        print("\n".join("ERROR: " + error for error in errors))
        raise SystemExit(1)
    rows = read_csv(ROOT / CONTRACT)
    direct = sum(row["direct_optimizer_input"].lower() == "true" for row in rows)
    print(f"policy-evaluation contract validation: OK items={len(rows)} direct_inputs={direct}")


if __name__ == "__main__":
    main()
