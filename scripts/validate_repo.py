#!/usr/bin/env python3
import csv
from pathlib import Path
import sys

from validate_claim_graph import validate as validate_claim_graph
from validate_scientific_state import validate as validate_scientific_state
from validate_research_priority import validate as validate_research_priority
from validate_repository_migration import validate as validate_repository_migration
from validate_policy_evaluation_contract import validate as validate_policy_evaluation_contract
from validate_publication_metadata import validate as validate_publication_metadata
from validate_raw_source_redistribution import validate as validate_raw_source_redistribution

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_readme_dashboard() -> list[str]:
    errors: list[str] = []
    readme_path = ROOT / "README.adoc"
    if not readme_path.is_file():
        return ["README dashboard missing: README.adoc"]
    if (ROOT / "README.md").exists():
        errors.append("README dashboard must have a single root entry point; remove README.md")

    readme = readme_path.read_text(encoding="utf-8")
    state_path = ROOT / "data/scientific_state.csv"
    products_path = ROOT / "data/research_products.csv"
    if not state_path.is_file() or not products_path.is_file():
        return errors

    for row in read_rows(state_path):
        if row.get("active", "").strip().lower() != "true":
            continue
        expected = (
            f"|{row['component_id']} |{row['status']} "
            f"|{row['maturity']} |{row['policy_usable']}"
        )
        if expected not in readme:
            errors.append(
                "README dashboard scientific-state row is missing/stale: "
                + row["component_id"]
            )

    for row in read_rows(products_path):
        expected = (
            f"|{row['product_id']} |{row['publication_status']} "
            f"|{row['reproduction_target']}"
        )
        if expected not in readme:
            errors.append(
                "README dashboard research-product row is missing/stale: "
                + row["product_id"]
            )

    for token in (
        "`data/scientific_state.csv`",
        "`data/claim_graph.csv`",
        "`STATUS.adoc`",
        "`scripts/reproduce.py`",
        "issues/94",
    ):
        if token not in readme:
            errors.append("README dashboard required navigation missing: " + token)
    return errors


required = [
    ROOT / "README.adoc",
    ROOT / "CITATION.cff",
    ROOT / "REPRODUCE.adoc",
    ROOT / "STATUS.adoc",
    ROOT / "PACKAGE_INTEGRITY.adoc",
    ROOT / "data/scientific_state.csv",
    ROOT / "data/research_products.csv",
    ROOT / "data/claim_graph.csv",
    ROOT / "data/claim_evidence.csv",
    ROOT / "data/research_priority_backlog.csv",
    ROOT / "data/policy_evaluation_contract.csv",
    ROOT / "data/raw_source_redistribution_rules.csv",
    ROOT / "data/raw_source_redistribution_audit.csv",
    ROOT / "docs/research_prioritization.adoc",
    ROOT / "docs/objective_function.adoc",
    ROOT / "docs/identification.adoc",
    ROOT / "docs/reproducibility.adoc",
    ROOT / "docs/data_availability.adoc",
    ROOT / "docs/licensing.adoc",
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
    errors.extend(validate_publication_metadata(ROOT))
    errors.extend(validate_raw_source_redistribution(ROOT))
    errors.extend(validate_readme_dashboard())

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
