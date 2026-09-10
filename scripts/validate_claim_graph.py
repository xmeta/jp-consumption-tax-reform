#!/usr/bin/env python3
"""Validate the repository-wide claim/evidence graph and its product projections."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from generate_claim_registries import GRAPH_FIELDS, expected_outputs

ROOT = Path(__file__).resolve().parents[1]
IDENTIFICATION = {
    "NOT_IDENTIFIED",
    "SENSITIVITY_ONLY",
    "PARTIALLY_IDENTIFIED",
    "READY",
    "RECOVERY_ONLY",
}
IDENTIFICATION_RANK = {
    "NOT_IDENTIFIED": 0,
    "SENSITIVITY_ONLY": 1,
    "PARTIALLY_IDENTIFIED": 2,
    "READY": 3,
}
CAUSAL = {"NOT_CAUSAL", "DESCRIPTIVE_ONLY", "CAUSAL_IDENTIFIED"}
CAUSAL_RANK = {"NOT_CAUSAL": 0, "DESCRIPTIVE_ONLY": 1, "CAUSAL_IDENTIFIED": 2}
POLICY = {"NOT_POLICY_USABLE", "POLICY_USABLE"}
BOOL = {"true", "false"}
RECOVERY_EVIDENCE = {"RECOVERY_ONLY", "RECOVERY_GAP"}
ACTIVE_EVIDENCE_PREFIXES = ("ACTIVE_", "REPRODUCED_")
SENSITIVITY_OVERCLAIM_TERMS = (
    "empirical bound",
    "identified effect",
    "point identified",
    "confidence interval",
    "confidence region",
    "causal bound",
    "causal effect",
    "sharp identified set",
)
CAUSAL_TERMS = ("causal effect", "causal impact", "causal estimate", "causal bound")
POLICY_TERMS = ("optimal policy", "policy optimum", "optimizer input", "welfare optimum")
POINT_ESTIMATE_RE = re.compile(
    r"(?<![A-Za-z0-9_])\d+(?:[.,]\d+)?\s*(?:%|pp\b|jpy\b|yen\b|trillion\b|billion\b|million\b)",
    re.IGNORECASE,
)


def split_ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def normalize(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[-‐‑‒–—_]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def contains_any(text: str, terms: tuple[str, ...]) -> str | None:
    normalized = normalize(text)
    for term in terms:
        if normalize(term) in normalized:
            return term
    return None


def validate(root: Path = ROOT, *, check_outputs: bool = True) -> list[str]:
    graph_path = root / "data/claim_graph.csv"
    evidence_path = root / "data/claim_evidence.csv"
    state_path = root / "data/scientific_state.csv"
    errors: list[str] = []
    if not graph_path.is_file():
        return ["schema: missing data/claim_graph.csv"]
    if not evidence_path.is_file():
        return ["provenance: missing data/claim_evidence.csv"]
    if not state_path.is_file():
        return ["identification: missing data/scientific_state.csv"]

    with graph_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != GRAPH_FIELDS:
            return ["schema: claim_graph.csv fields do not match the authoritative schema"]
        claims = list(reader)

    claim_ids = [row["claim_id"].strip() for row in claims]
    if len(claim_ids) != len(set(claim_ids)):
        errors.append("schema: duplicate repository-wide claim_id")
    if {row["product_id"] for row in claims} != {"paper1", "vat_abolition"}:
        errors.append("schema: product set must be exactly paper1 and vat_abolition")
    paper_ids = {row["claim_id"] for row in claims if row["product_id"] == "paper1"}
    expected_paper_ids = {f"P1-C{i:02d}" for i in range(1, 18)}
    if paper_ids != expected_paper_ids:
        errors.append("schema: Paper 1 projection must contain exactly P1-C01..P1-C17")

    with state_path.open(encoding="utf-8", newline="") as handle:
        state_rows = list(csv.DictReader(handle))
    components = {
        row["component_id"].strip(): row
        for row in state_rows
        if row.get("active", "").strip().lower() == "true"
    }

    with evidence_path.open(encoding="utf-8", newline="") as handle:
        evidence_rows = list(csv.DictReader(handle))
    evidence_by_claim: dict[str, list[dict[str, str]]] = {}
    evidence_edges: set[tuple[str, str, str, str]] = set()
    for row in evidence_rows:
        cid = row["claim_id"].strip()
        edge = (
            cid,
            row["evidence_status"].strip(),
            row["evidence_artifact"].strip(),
            row["locator"].strip(),
        )
        if edge in evidence_edges:
            errors.append(f"provenance: duplicate evidence edge for {cid}")
        evidence_edges.add(edge)
        evidence_by_claim.setdefault(cid, []).append(row)
        if cid not in set(claim_ids):
            errors.append(f"provenance: orphan evidence references unknown claim_id {cid}")
        artifact = row["evidence_artifact"].strip()
        if artifact and not (root / artifact).exists():
            errors.append(f"provenance: {cid}: missing evidence artifact {artifact}")

    for row in claims:
        cid = row["claim_id"].strip() or "<blank>"
        for field in (
            "product_id",
            "claim_id",
            "topic",
            "empirical_status",
            "identification_status",
            "causal_status",
            "policy_status",
            "evidence_scope",
            "allowed_claim",
            "forbidden_claim",
            "source",
            "evidence_ids",
            "active",
        ):
            if not row[field].strip():
                errors.append(f"schema: {cid}: empty {field}")
        identification = row["identification_status"].strip()
        causal = row["causal_status"].strip()
        policy = row["policy_status"].strip()
        active = row["active"].strip().lower()
        if identification not in IDENTIFICATION:
            errors.append(f"schema: {cid}: invalid identification_status {identification!r}")
        if causal not in CAUSAL:
            errors.append(f"schema: {cid}: invalid causal_status {causal!r}")
        if policy not in POLICY:
            errors.append(f"schema: {cid}: invalid policy_status {policy!r}")
        if active not in BOOL:
            errors.append(f"schema: {cid}: active must be true/false")
        source = row["source"].strip()
        if source and not (root / source).exists():
            errors.append(f"provenance: {cid}: missing claim source {source}")

        claim_evidence = evidence_by_claim.get(cid, [])
        if not claim_evidence:
            errors.append(f"provenance: {cid}: claim has no evidence edge")
        declared_artifacts = set(split_ids(row["evidence_ids"]))
        edge_artifacts = {edge["evidence_artifact"].strip() for edge in claim_evidence}
        for artifact in declared_artifacts:
            if not (root / artifact).exists():
                errors.append(f"provenance: {cid}: missing declared evidence {artifact}")
            if artifact not in edge_artifacts:
                errors.append(f"provenance: {cid}: declared evidence lacks graph edge {artifact}")

        statuses = {edge["evidence_status"].strip() for edge in claim_evidence}
        if active == "true":
            if not any(status.startswith(ACTIVE_EVIDENCE_PREFIXES) for status in statuses):
                errors.append(f"provenance: {cid}: active claim lacks active evidence")
            if statuses and statuses <= RECOVERY_EVIDENCE:
                errors.append(f"provenance: {cid}: active claim relies only on recovery evidence")
        if identification == "RECOVERY_ONLY" and not statuses & RECOVERY_EVIDENCE:
            errors.append(f"provenance: {cid}: recovery-only claim lacks recovery evidence")

        component_id = row["component_id"].strip()
        if component_id:
            component = components.get(component_id)
            if component is None:
                errors.append(f"identification: {cid}: unknown/inactive component_id {component_id}")
            elif identification != "RECOVERY_ONLY":
                component_maturity = component["maturity"].strip()
                if (
                    identification in IDENTIFICATION_RANK
                    and component_maturity in IDENTIFICATION_RANK
                    and IDENTIFICATION_RANK[identification] > IDENTIFICATION_RANK[component_maturity]
                ):
                    errors.append(
                        f"identification: {cid}: claim maturity {identification} exceeds component {component_maturity}"
                    )
                component_causal = component["causal_status"].strip()
                if causal in CAUSAL_RANK and component_causal in CAUSAL_RANK:
                    if CAUSAL_RANK[causal] > CAUSAL_RANK[component_causal]:
                        errors.append(
                            f"identification: {cid}: claim causal status {causal} exceeds component {component_causal}"
                        )
                if policy == "POLICY_USABLE" and component["policy_usable"].strip().lower() != "true":
                    errors.append(
                        f"identification: {cid}: POLICY_USABLE contradicts component policy_usable=false"
                    )

        allowed = row["allowed_claim"]
        if identification == "NOT_IDENTIFIED" and POINT_ESTIMATE_RE.search(allowed):
            errors.append(f"claim: {cid}: NOT_IDENTIFIED claim exposes a numeric headline estimate")
        if identification == "SENSITIVITY_ONLY":
            term = contains_any(allowed, SENSITIVITY_OVERCLAIM_TERMS)
            if term:
                errors.append(f"claim: {cid}: SENSITIVITY_ONLY allowed claim uses {term!r}")
        if causal != "CAUSAL_IDENTIFIED":
            term = contains_any(allowed, CAUSAL_TERMS)
            if term:
                errors.append(f"claim: {cid}: noncausal allowed claim uses {term!r}")
        if policy != "POLICY_USABLE":
            term = contains_any(allowed, POLICY_TERMS)
            if term:
                errors.append(f"claim: {cid}: non-policy-usable allowed claim uses {term!r}")

        for field, inverse in (("supersedes", "superseded_by"), ("superseded_by", "supersedes")):
            for target in split_ids(row[field]):
                matches = [candidate for candidate in claims if candidate["claim_id"] == target]
                if not matches:
                    errors.append(f"schema: {cid}: unknown {field} claim_id {target}")
                elif cid not in split_ids(matches[0][inverse]):
                    errors.append(f"schema: {cid}: {field}={target} lacks reciprocal {inverse}")

    active_vat_components = {
        row["component_id"]
        for row in claims
        if row["product_id"] == "vat_abolition" and row["active"].lower() == "true"
    }
    if not {"vat_compliance_productivity", "vat_policy_integration"} <= active_vat_components:
        errors.append("coverage: VAT claim product must cover both active VAT components")

    if check_outputs:
        try:
            outputs = expected_outputs(root)
        except (OSError, ValueError) as exc:
            errors.append(f"projection: cannot render product registries: {exc}")
        else:
            for relative, expected in outputs.items():
                path = root / relative
                if not path.is_file():
                    errors.append(f"projection: missing generated registry {relative}")
                elif path.read_text(encoding="utf-8") != expected:
                    errors.append(f"projection: stale generated registry {relative}")
    return errors


def main() -> None:
    errors = validate(ROOT)
    if errors:
        print("\n".join("ERROR: " + error for error in errors))
        sys.exit(1)
    print("repository claim-graph validation: OK")


if __name__ == "__main__":
    main()
