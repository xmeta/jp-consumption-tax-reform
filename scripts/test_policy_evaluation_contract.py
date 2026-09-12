#!/usr/bin/env python3
"""Regression checks for the policy-evaluation contract."""
from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path

if not __debug__:
    raise RuntimeError("policy-evaluation contract tests require non-optimized Python")

ROOT = Path(__file__).resolve().parents[1]
from validate_policy_evaluation_contract import validate


def mutate_csv(path: Path, key: str, key_value: str, field: str, value: str) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    for row in rows:
        if row[key] == key_value:
            row[field] = value
            break
    else:
        raise RuntimeError(f"missing fixture row {key_value}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="policy-contract-"))
    for rel in (
        "data/policy_evaluation_contract.csv",
        "data/scientific_state.csv",
        "research/vat_policy_integration/pareto_objectives.csv",
    ):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    return root


def require_error(errors: list[str], token: str) -> None:
    if not any(token in error for error in errors):
        raise RuntimeError(f"missing expected error {token!r}: {errors}")


base_errors = validate(ROOT)
if base_errors:
    raise RuntimeError("repository policy contract invalid: " + "; ".join(base_errors))

root = fixture()
mutate_csv(
    root / "data/policy_evaluation_contract.csv",
    "item_id", "cumulative_real_growth", "direct_optimizer_input", "true",
)
require_error(validate(root), "direct optimizer input requires maturity=READY")
shutil.rmtree(root)

root = fixture()
mutate_csv(
    root / "data/policy_evaluation_contract.csv",
    "item_id", "fgt2_effect", "allowed_nonready_use", "DIRECT_POINT",
)
require_error(validate(root), "non-ready component use must be robustness/dashboard only")
shutil.rmtree(root)

root = fixture()
mutate_csv(
    root / "data/policy_evaluation_contract.csv",
    "item_id", "annual_real_growth_viability", "formula_or_rule", "g_t>=0 for every t",
)
require_error(validate(root), "strict positive growth")
shutil.rmtree(root)

root = fixture()
contract_path = root / "data/policy_evaluation_contract.csv"
lines = contract_path.read_text(encoding="utf-8").splitlines()
lines[1] += ",EXTRA"
contract_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
require_error(validate(root), "row-width mismatch")
shutil.rmtree(root)

root = fixture()
pareto_path = root / "research/vat_policy_integration/pareto_objectives.csv"
with pareto_path.open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
    fields = list(rows[0])
rows.append({field: "" for field in fields})
rows[-1].update({
    "objective_id": "debt_service_guardrail",
    "objective_label": "Debt-service guardrail",
    "direction": "minimize",
    "required_for_headline": "true",
    "status_column": "dynamic_fiscal_identification_status",
})
with pareto_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
require_error(validate(root), "VAT Pareto implementation must match")
shutil.rmtree(root)

print("policy-evaluation contract tests: OK")
