#!/usr/bin/env python3
from pathlib import Path
import sys

from validate_claim_graph import validate as validate_claim_graph
from validate_scientific_state import validate as validate_scientific_state
from validate_research_priority import validate as validate_research_priority
from validate_repository_migration import validate as validate_repository_migration
from validate_policy_evaluation_contract import validate as validate_policy_evaluation_contract

ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT / "README.adoc",
    ROOT / "STATUS.adoc",
    ROOT / "PACKAGE_INTEGRITY.adoc",
    ROOT / "data/scientific_state.csv",
    ROOT / "data/claim_graph.csv",
    ROOT / "data/claim_evidence.csv",
    ROOT / "data/research_priority_backlog.csv",
    ROOT / "data/policy_evaluation_contract.csv",
    ROOT / "docs/research_prioritization.adoc",
    ROOT / "docs/objective_function.adoc",
    ROOT / "docs/identification.adoc",
    ROOT / "docs/reproducibility.adoc",
    ROOT / "docs/scientific_state.adoc",
    ROOT / "docs/repository_migration.adoc",
    ROOT / "data/recovery/legacy_artifact_capability.csv",
    ROOT / "docs/claim_graph.adoc",
    ROOT / "paper1/data/claim_registry.csv",
    ROOT / "research/vat_claim_registry.csv",
]
missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
status_path = ROOT / "STATUS.adoc"
status = status_path.read_text(encoding="utf-8") if status_path.exists() else ""
errors = []
if missing:
    errors.append("missing required files: " + ", ".join(missing))
else:
    errors.extend(validate_scientific_state(ROOT))
    errors.extend(validate_claim_graph(ROOT))
    errors.extend(validate_research_priority(ROOT))
    errors.extend(validate_repository_migration(ROOT)[0])
    errors.extend(validate_policy_evaluation_contract(ROOT))

for token in [
    "Income-tax behavioral response |NOT_READY",
    "Pseudo-filer statutory MTR |SENSITIVITY_ONLY",
    "repository_migration |COMPLETE",
]:
    if token not in status:
        errors.append("required status marker missing: " + token)

if errors:
    print("\n".join("ERROR: " + e for e in errors))
    sys.exit(1)

print("repository scientific-state validation: OK")
