#!/usr/bin/env python3
"""Validate the repository-wide machine-readable scientific-state authority."""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

FIELDS = [
    "component_id",
    "module_path",
    "display_name",
    "status",
    "phase",
    "maturity",
    "causal_status",
    "policy_usable",
    "evidence_paths",
    "output_paths",
    "blockers",
    "issue_refs",
    "supersedes",
    "superseded_by",
    "active",
]
PHASES = {"PHASE1_COMPLETE", "PHASE2_ACTIVE", "MAINTENANCE"}
MATURITY = {"NOT_IDENTIFIED", "SENSITIVITY_ONLY", "PARTIALLY_IDENTIFIED", "READY"}
CAUSAL = {"NOT_CAUSAL", "DESCRIPTIVE_ONLY", "CAUSAL_IDENTIFIED"}
BOOL = {"true", "false"}

CLAIM_FIELDS = {
    "claim_id",
    "topic",
    "status",
    "evidence_scope",
    "allowed_claim",
    "forbidden_claim",
    "source",
}
CLAIM_EVIDENCE_FIELDS = {"claim_id", "evidence_status"}
RECOVERY_ONLY_EVIDENCE = {"RECOVERY_ONLY", "RECOVERY_GAP"}

SENSITIVITY_OVERCLAIM_TERMS = (
    "empirical bound",
    "empirical lower bound",
    "empirical upper bound",
    "identified effect",
    "point identified",
    "confidence interval",
    "confidence region",
    "causal bound",
    "causal effect",
    "sharp identified set",
    "statistically sharp",
)
CAUSAL_CLAIM_TERMS = (
    "causal effect",
    "causal impact",
    "causal estimate",
    "causal bound",
    "causally increases",
    "causally decreases",
)
POLICY_CLAIM_TERMS = (
    "optimal policy",
    "policy optimum",
    "optimizer input",
    "welfare maximizing",
    "welfare optimum",
)
PER_CLAIM_GUARD_TERMS = tuple(
    dict.fromkeys(
        SENSITIVITY_OVERCLAIM_TERMS
        + CAUSAL_CLAIM_TERMS
        + POLICY_CLAIM_TERMS
        + ("reproduced main result",)
    )
)
POINT_ESTIMATE_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"\d+(?:[.,]\d+)?"
    r"\s*(?:%|pp\b|percentage\s+points?\b|jpy\b|yen\b|"
    r"trillion\b|billion\b|million\b)",
    re.IGNORECASE,
)


def split_paths(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def normalize_claim_text(value: str) -> str:
    normalized = value.casefold()
    normalized = re.sub(r"[-‐‑‒–—_]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def find_term(text: str, terms: tuple[str, ...]) -> str | None:
    normalized = normalize_claim_text(text)
    for term in terms:
        if normalize_claim_text(term) in normalized:
            return term
    return None


def discover_active_modules(root: Path) -> set[str]:
    research = root / "research"
    if not research.is_dir():
        return set()
    modules: set[str] = set()
    for child in research.iterdir():
        if not child.is_dir():
            continue
        if not (child / "README.adoc").is_file():
            continue
        if any(child.glob("*.py")):
            modules.add(child.relative_to(root).as_posix())
    return modules


def claim_component(
    source: str, by_module: dict[str, dict[str, str]]
) -> dict[str, str] | None:
    source = source.strip()
    for module_path in sorted(by_module, key=len, reverse=True):
        if source == module_path or source.startswith(module_path + "/"):
            return by_module[module_path]
    return None


def active_reproduced_claim(status: str) -> bool:
    status = status.strip()
    if status in {"OBSERVED_PUBLIC", "READY_STATIC_ONLY"}:
        return True
    return status.endswith("_REPRODUCED") and "NOT_REPRODUCED" not in status


def validate(root: Path) -> list[str]:
    authority = root / "data/scientific_state.csv"
    status_doc = root / "STATUS.adoc"
    claim_registry = root / "paper1/data/claim_registry.csv"
    claim_evidence = root / "data/claim_evidence.csv"
    errors: list[str] = []

    if not authority.is_file():
        return ["schema: missing data/scientific_state.csv"]
    if not status_doc.is_file():
        return ["sync: missing STATUS.adoc"]

    with authority.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            errors.append(
                "schema: scientific_state.csv fields must be exactly: "
                + ",".join(FIELDS)
            )
            return errors
        rows = list(reader)

    if not rows:
        errors.append("schema: scientific_state.csv must contain at least one row")
        return errors

    component_ids = [row["component_id"].strip() for row in rows]
    if len(component_ids) != len(set(component_ids)):
        errors.append("schema: duplicate component_id")

    active_rows = [row for row in rows if row["active"].strip().lower() == "true"]
    active_paths = [row["module_path"].strip() for row in active_rows]
    if len(active_paths) != len(set(active_paths)):
        errors.append("schema: duplicate active module_path (conflicting module state)")

    status_text = status_doc.read_text(encoding="utf-8")
    for lineno, row in enumerate(rows, 2):
        prefix = f"row {lineno} ({row['component_id'] or '<blank>'})"
        for field in (
            "component_id",
            "module_path",
            "display_name",
            "status",
            "phase",
            "maturity",
            "causal_status",
            "policy_usable",
            "active",
        ):
            if not row[field].strip():
                errors.append(f"schema: {prefix}: empty {field}")
        phase = row["phase"].strip()
        maturity = row["maturity"].strip()
        causal_status = row["causal_status"].strip()
        policy_usable = row["policy_usable"].strip().lower()
        active = row["active"].strip().lower()
        detailed_status = row["status"].strip()

        if phase not in PHASES:
            errors.append(f"schema: {prefix}: invalid phase {row['phase']!r}")
        if maturity not in MATURITY:
            errors.append(f"schema: {prefix}: invalid maturity {row['maturity']!r}")
        if causal_status not in CAUSAL:
            errors.append(
                f"schema: {prefix}: invalid causal_status {row['causal_status']!r}"
            )
        if policy_usable not in BOOL:
            errors.append(f"schema: {prefix}: policy_usable must be true/false")
        if active not in BOOL:
            errors.append(f"schema: {prefix}: active must be true/false")

        module_path = root / row["module_path"].strip()
        if active == "true":
            if not module_path.is_dir():
                errors.append(f"coverage: {prefix}: missing module_path")
            elif not (module_path / "README.adoc").is_file():
                errors.append(f"coverage: {prefix}: missing module README.adoc")
            if detailed_status not in status_text:
                errors.append(
                    f"sync: {prefix}: status token absent from STATUS.adoc: "
                    f"{detailed_status}"
                )

            blockers = row["blockers"].strip()
            if maturity == "READY" and blockers:
                errors.append(
                    f"identification: {prefix}: READY component must not list unresolved blockers"
                )
            elif maturity in MATURITY - {"READY"} and not blockers:
                errors.append(
                    f"identification: {prefix}: non-READY active component must list blockers"
                )

            issue_refs = split_paths(row["issue_refs"])
            if maturity in MATURITY - {"READY"} and not issue_refs:
                errors.append(
                    f"sync: {prefix}: non-READY active component must reference blocker issue"
                )
            if len(issue_refs) != len(set(issue_refs)):
                errors.append(f"schema: {prefix}: duplicate issue_refs")
            for issue_ref in issue_refs:
                if not issue_ref.isdigit() or int(issue_ref) <= 0:
                    errors.append(
                        f"schema: {prefix}: issue_refs must be positive GitHub issue numbers"
                    )

        if policy_usable == "true" and maturity != "READY":
            errors.append(
                f"identification: {prefix}: policy_usable=true requires maturity=READY"
            )
        if causal_status == "CAUSAL_IDENTIFIED" and maturity in {
            "NOT_IDENTIFIED",
            "SENSITIVITY_ONLY",
        }:
            errors.append(
                f"identification: {prefix}: CAUSAL_IDENTIFIED is incompatible with maturity={maturity}"
            )

        status_upper = detailed_status.upper()
        if "SENSITIVITY" in status_upper and maturity != "SENSITIVITY_ONLY":
            errors.append(
                f"identification: {prefix}: sensitivity status requires maturity=SENSITIVITY_ONLY"
            )
        if (
            status_upper.startswith("NOT_READY")
            or status_upper.startswith("NOT_IDENTIFIED")
        ) and maturity != "NOT_IDENTIFIED":
            errors.append(
                f"identification: {prefix}: NOT_READY/NOT_IDENTIFIED status requires maturity=NOT_IDENTIFIED"
            )
        if status_upper == "ROBUSTNESS_FRONTIER" and maturity != "PARTIALLY_IDENTIFIED":
            errors.append(
                f"identification: {prefix}: ROBUSTNESS_FRONTIER requires maturity=PARTIALLY_IDENTIFIED"
            )
        if status_upper.startswith("PARTIAL_") and maturity != "PARTIALLY_IDENTIFIED":
            errors.append(
                f"identification: {prefix}: PARTIAL_* status requires maturity=PARTIALLY_IDENTIFIED"
            )
        if status_upper.startswith("READY") and maturity != "READY":
            errors.append(
                f"identification: {prefix}: READY* status requires maturity=READY"
            )

        for field in ("evidence_paths", "output_paths"):
            paths = split_paths(row[field])
            if not paths:
                errors.append(f"schema: {prefix}: {field} must not be empty")
            for rel in paths:
                if not (root / rel).exists():
                    errors.append(f"provenance: {prefix}: missing {field}: {rel}")

    discovered = discover_active_modules(root)
    declared = set(active_paths)
    if discovered != declared:
        missing = sorted(discovered - declared)
        extra = sorted(declared - discovered)
        detail = []
        if missing:
            detail.append("undeclared=" + ",".join(missing))
        if extra:
            detail.append("not-discovered=" + ",".join(extra))
        errors.append("coverage: active module coverage mismatch: " + "; ".join(detail))

    by_id = {
        row["component_id"].strip(): row
        for row in rows
        if row["component_id"].strip()
    }
    for row in rows:
        cid = row["component_id"].strip()
        for field, inverse in (
            ("supersedes", "superseded_by"),
            ("superseded_by", "supersedes"),
        ):
            for target in split_paths(row[field]):
                if target not in by_id:
                    errors.append(
                        f"schema: {cid}: unknown {field} component_id {target}"
                    )
                elif cid not in split_paths(by_id[target][inverse]):
                    errors.append(
                        f"schema: {cid}: {field}={target} lacks reciprocal {inverse}"
                    )

    # Lightweight fixtures that intentionally model only the state authority may
    # omit Paper 1. A real repository gate requires the claim files in
    # scripts/validate_repo.py; when Paper 1 exists, semantic validation is
    # fail-closed.
    if not (root / "paper1").exists():
        return errors
    if not claim_registry.is_file():
        errors.append("claim: missing paper1/data/claim_registry.csv")
        return errors
    if not claim_evidence.is_file():
        errors.append("provenance: missing data/claim_evidence.csv")
        return errors

    with claim_registry.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not CLAIM_FIELDS.issubset(reader.fieldnames):
            errors.append(
                "claim: claim_registry.csv missing required fields: "
                + ",".join(sorted(CLAIM_FIELDS))
            )
            return errors
        claims = list(reader)

    with claim_evidence.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not CLAIM_EVIDENCE_FIELDS.issubset(reader.fieldnames):
            errors.append(
                "provenance: claim_evidence.csv missing required fields: "
                + ",".join(sorted(CLAIM_EVIDENCE_FIELDS))
            )
            return errors
        evidence_rows = list(reader)

    evidence_by_claim: dict[str, set[str]] = {}
    for evidence in evidence_rows:
        evidence_by_claim.setdefault(evidence["claim_id"].strip(), set()).add(
            evidence["evidence_status"].strip()
        )

    active_by_module = {
        row["module_path"].strip(): row
        for row in active_rows
        if row["module_path"].strip()
    }

    for claim in claims:
        cid = claim["claim_id"].strip() or "<blank>"
        source = claim["source"].strip()
        allowed = claim["allowed_claim"]
        forbidden = claim["forbidden_claim"]
        component = claim_component(source, active_by_module)

        if source.startswith("research/") and component is None:
            errors.append(
                f"claim: {cid}: local research source is not mapped to an active scientific-state component: {source}"
            )

        allowed_norm = normalize_claim_text(allowed)
        forbidden_norm = normalize_claim_text(forbidden)

        for term in PER_CLAIM_GUARD_TERMS:
            normalized_term = normalize_claim_text(term)
            if normalized_term in forbidden_norm and normalized_term in allowed_norm:
                errors.append(
                    f"claim: {cid}: allowed_claim repeats per-claim forbidden term {term!r}"
                )
                break

        if claim["status"].strip() == "NOT_READY" and POINT_ESTIMATE_RE.search(allowed):
            errors.append(
                f"claim: {cid}: NOT_READY claim must not expose a numeric headline point estimate"
            )

        if component is not None:
            maturity = component["maturity"].strip()
            causal_status = component["causal_status"].strip()
            policy_usable = component["policy_usable"].strip().lower()

            if maturity == "NOT_IDENTIFIED" and POINT_ESTIMATE_RE.search(allowed):
                errors.append(
                    f"claim: {cid}: NOT_IDENTIFIED component must not expose a numeric headline point estimate"
                )

            if maturity == "SENSITIVITY_ONLY":
                term = find_term(allowed, SENSITIVITY_OVERCLAIM_TERMS)
                if term is not None:
                    errors.append(
                        f"claim: {cid}: SENSITIVITY_ONLY component cannot label an allowed claim with {term!r}"
                    )

            if causal_status != "CAUSAL_IDENTIFIED":
                term = find_term(allowed, CAUSAL_CLAIM_TERMS)
                if term is not None:
                    errors.append(
                        f"claim: {cid}: {causal_status} component cannot make allowed causal claim {term!r}"
                    )

            if policy_usable == "false":
                term = find_term(allowed, POLICY_CLAIM_TERMS)
                if term is not None:
                    errors.append(
                        f"claim: {cid}: policy_usable=false component cannot make allowed policy-optimization claim {term!r}"
                    )

        if active_reproduced_claim(claim["status"]):
            statuses = evidence_by_claim.get(cid, set())
            if not statuses:
                errors.append(
                    f"provenance: {cid}: active reproduced claim has no claim evidence"
                )
            elif statuses <= RECOVERY_ONLY_EVIDENCE:
                errors.append(
                    f"provenance: {cid}: active reproduced claim relies only on RECOVERY_ONLY/RECOVERY_GAP evidence"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (used by regression fixtures)",
    )
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    if errors:
        print("\n".join("ERROR: " + error for error in errors))
        return 1
    print("machine-readable scientific-state validation: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
