#!/usr/bin/env python3
from pathlib import Path
import sys

from validate_claim_graph import validate as validate_claim_graph
from validate_scientific_state import validate as validate_scientific_state

ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT / "README.adoc",
    ROOT / "STATUS.adoc",
    ROOT / "PACKAGE_INTEGRITY.adoc",
    ROOT / "data/scientific_state.csv",
    ROOT / "data/claim_graph.csv",
    ROOT / "data/claim_evidence.csv",
    ROOT / "docs/objective_function.adoc",
    ROOT / "docs/identification.adoc",
    ROOT / "docs/reproducibility.adoc",
    ROOT / "docs/scientific_state.adoc",
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

for token in [
    "Income-tax behavioral response |NOT_READY",
    "Pseudo-filer statutory MTR |SENSITIVITY_ONLY",
    "repository_migration |PARTIAL",
]:
    if token not in status:
        errors.append("required status marker missing: " + token)

if errors:
    print("\n".join("ERROR: " + e for e in errors))
    sys.exit(1)

print("repository scientific-state validation: OK")
