#!/usr/bin/env python3
"""Report and validate decision-relevant research-progress KPI governance."""
from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILES = {
    "backlog": "data/research_priority_backlog.csv",
    "pairs": "data/derived/vat_policy_pareto_pairwise.csv",
    "gates": "data/scientific_review_gates.csv",
    "claims": "data/claim_graph.csv",
}
CANONICAL_KPIS = (
    "voi_gap_advances",
    "identified_set_width_reduction",
    "assumption_burden_reduction",
    "policy_relations_resolved",
    "independent_review_gates_satisfied",
    "recovery_only_claims_upgraded_or_retired",
)
TEMPLATES = (
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/RELEASE_TEMPLATE.md",
)


def parse_csv(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def worktree_reader(root: Path):
    def read(rel: str) -> list[dict[str, str]]:
        return parse_csv((root / rel).read_text(encoding="utf-8"))

    return read


def ref_reader(root: Path, ref: str):
    def read(rel: str) -> list[dict[str, str]]:
        try:
            data = subprocess.check_output(
                ["git", "-C", str(root), "show", f"{ref}:{rel}"],
                text=True,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"cannot read {rel} at {ref}: {exc.output.strip()}") from exc
        return parse_csv(data)

    return read


def snapshot(read) -> dict[str, tuple[int, int | None]]:
    backlog = read(DATA_FILES["backlog"])
    pairs = read(DATA_FILES["pairs"])
    gates = read(DATA_FILES["gates"])
    claims = read(DATA_FILES["claims"])

    high_voi = [row for row in backlog if row.get("expected_voi") == "HIGH"]
    indeterminate = [
        row for row in pairs if row.get("dominance_status", "").startswith("INDETERMINATE")
    ]
    independent = [
        row for row in gates if row.get("minimum_independence") == "INDEPENDENT_REVIEWER"
    ]
    active_claims = [row for row in claims if row.get("active", "").lower() == "true"]
    active_recovery = [
        row for row in active_claims if row.get("identification_status") == "RECOVERY_ONLY"
    ]

    return {
        "high_voi_unresolved_gaps": (len(high_voi), None),
        "indeterminate_policy_pairs": (len(indeterminate), len(pairs)),
        "independent_review_gates_satisfied": (
            sum(row.get("status") == "SATISFIED" for row in independent),
            len(independent),
        ),
        "active_recovery_only_claims": (len(active_recovery), len(active_claims)),
    }


def render(values: dict[str, tuple[int, int | None]]) -> str:
    lines = []
    for key, (value, denominator) in values.items():
        rendered = str(value) if denominator is None else f"{value}/{denominator}"
        lines.append(f"{key}={rendered}")
    return "\n".join(lines)


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    doc_path = root / "docs/research_progress_kpis.adoc"
    priority_path = root / "docs/research_prioritization.adoc"
    required = [doc_path, priority_path, *(root / path for path in TEMPLATES)]
    required.extend(root / path for path in DATA_FILES.values())
    for path in required:
        if not path.is_file():
            errors.append(f"research-progress: missing {path.relative_to(root)}")
    if errors:
        return errors

    doc = doc_path.read_text(encoding="utf-8")
    for kpi in CANONICAL_KPIS:
        if f"`{kpi}`" not in doc:
            errors.append(f"research-progress: KPI missing from documentation: {kpi}")

    for rel in TEMPLATES:
        text = (root / rel).read_text(encoding="utf-8")
        for kpi in CANONICAL_KPIS:
            if f"`{kpi}`" not in text:
                errors.append(f"research-progress: {rel} missing KPI: {kpi}")
        lowered = text.casefold()
        if "integrity" not in lowered or "scientific progress" not in lowered:
            errors.append(f"research-progress: {rel} must separate integrity from scientific progress")

    priority = priority_path.read_text(encoding="utf-8")
    if "research_progress_kpis.adoc" not in priority:
        errors.append("research-progress: prioritization doc must link KPI governance")

    try:
        snapshot(worktree_reader(root))
    except (OSError, ValueError, csv.Error) as exc:
        errors.append(f"research-progress: cannot compute snapshot: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", help="read KPI source files from a Git ref")
    parser.add_argument("--validate", action="store_true", help="validate KPI governance")
    args = parser.parse_args()

    if args.validate:
        errors = validate(ROOT)
        if errors:
            print("\n".join("ERROR: " + error for error in errors))
            return 1
        print("research-progress KPI validation: OK")
        return 0

    try:
        reader = ref_reader(ROOT, args.ref) if args.ref else worktree_reader(ROOT)
        values = snapshot(reader)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(render(values))
    return 0


if __name__ == "__main__":
    sys.exit(main())
