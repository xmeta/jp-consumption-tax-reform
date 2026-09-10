#!/usr/bin/env python3
from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = Path("data/research_priority_backlog.csv")
DOC = Path("docs/research_prioritization.adoc")

REQUIRED = {
    "priority_rank", "gap_id", "issue_refs", "research_domain",
    "uncertain_object", "current_scientific_status", "decision_or_claim_at_risk",
    "current_admissible_set", "candidate_evidence_or_method",
    "identification_gain_type", "expected_identification_gain", "decision_impact",
    "expected_effort", "access_delay", "expected_voi",
    "could_change_policy_ranking", "could_change_manuscript_claim",
    "public_data_search_status", "stop_rule", "escalation_if_stopped",
    "evidence_accumulation_only", "next_action",
}
LEVEL = {"HIGH", "MEDIUM", "LOW"}
EFFORT = {"HIGH", "MEDIUM", "LOW"}
DELAY = {"HIGH", "MEDIUM", "LOW", "NONE"}
GAIN = {"DIRECT_OR_BOUND_SHRINKAGE", "BOUND_SHRINKAGE", "MODEL_COMPLETION", "EVIDENCE_ACCUMULATION_ONLY"}
SEARCH = {"ACTIVE_TARGETED", "STOP_PUBLIC_SEARCH_ESCALATE_RESTRICTED", "STOP_UNLINKED_EVIDENCE_ACCUMULATION", "MODEL_BUILD_FIRST"}
BOOL = {"true", "false"}


def validate(root=ROOT):
    errors = []
    path = root / BACKLOG
    doc = root / DOC
    if not path.exists():
        return [f"research-priority: missing {BACKLOG}"]
    if not doc.exists():
        errors.append(f"research-priority: missing {DOC}")
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = set(reader.fieldnames or [])
    if fields != REQUIRED:
        errors.append(f"research-priority: schema mismatch: {sorted(fields ^ REQUIRED)}")
        return errors
    if not rows:
        return errors + ["research-priority: backlog is empty"]
    if len({r["gap_id"] for r in rows}) != len(rows):
        errors.append("research-priority: gap_id values must be unique")
    try:
        ranks = [int(r["priority_rank"]) for r in rows]
    except ValueError:
        errors.append("research-priority: priority_rank must be integer")
        ranks = []
    if ranks and ranks != list(range(1, len(rows) + 1)):
        errors.append("research-priority: rows must be ordered by consecutive priority_rank")
    voi_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    seen_voi = []
    issues = set()
    stopped = 0
    for r in rows:
        for key in ("uncertain_object", "current_scientific_status", "decision_or_claim_at_risk", "current_admissible_set", "candidate_evidence_or_method", "stop_rule", "next_action"):
            if not r[key].strip():
                errors.append(f"research-priority: {r['gap_id']}: blank {key}")
        if r["expected_identification_gain"] not in LEVEL:
            errors.append(f"research-priority: {r['gap_id']}: invalid expected_identification_gain")
        if r["decision_impact"] not in LEVEL:
            errors.append(f"research-priority: {r['gap_id']}: invalid decision_impact")
        if r["expected_effort"] not in EFFORT:
            errors.append(f"research-priority: {r['gap_id']}: invalid expected_effort")
        if r["access_delay"] not in DELAY:
            errors.append(f"research-priority: {r['gap_id']}: invalid access_delay")
        if r["expected_voi"] not in LEVEL:
            errors.append(f"research-priority: {r['gap_id']}: invalid expected_voi")
        else:
            seen_voi.append(voi_order[r["expected_voi"]])
        if r["identification_gain_type"] not in GAIN:
            errors.append(f"research-priority: {r['gap_id']}: invalid identification_gain_type")
        if r["public_data_search_status"] not in SEARCH:
            errors.append(f"research-priority: {r['gap_id']}: invalid public_data_search_status")
        for key in ("could_change_policy_ranking", "could_change_manuscript_claim", "evidence_accumulation_only"):
            if r[key] not in BOOL:
                errors.append(f"research-priority: {r['gap_id']}: {key} must be true/false")
        refs = {x for x in r["issue_refs"].split(";") if x}
        if not refs or any(not x.isdigit() for x in refs):
            errors.append(f"research-priority: {r['gap_id']}: issue_refs must be semicolon-separated issue numbers")
        issues.update(refs)
        if r["public_data_search_status"].startswith("STOP_"):
            stopped += 1
            if not r["escalation_if_stopped"].strip():
                errors.append(f"research-priority: {r['gap_id']}: stopped public search requires escalation")
        if r["evidence_accumulation_only"] == "true":
            if r["expected_identification_gain"] == "HIGH" or r["expected_voi"] == "HIGH":
                errors.append(f"research-priority: {r['gap_id']}: evidence-only work cannot be HIGH identification gain/VoI")
            if r["identification_gain_type"] != "EVIDENCE_ACCUMULATION_ONLY":
                errors.append(f"research-priority: {r['gap_id']}: evidence-only flag/type disagree")
        elif r["identification_gain_type"] == "EVIDENCE_ACCUMULATION_ONLY":
            errors.append(f"research-priority: {r['gap_id']}: evidence-only type requires evidence_accumulation_only=true")
    if seen_voi != sorted(seen_voi):
        errors.append("research-priority: HIGH VoI rows must precede MEDIUM, then LOW")
    for required_issue in {"25", "26"}:
        if required_issue not in issues:
            errors.append(f"research-priority: Issue #{required_issue} must be represented")
    if stopped == 0:
        errors.append("research-priority: at least one public-data dead end must have an explicit stop/escalation rule")
    forbidden_progress_fields = {"source_count", "file_count", "artifact_count", "stress_point_count"}
    if fields & forbidden_progress_fields:
        errors.append("research-priority: source/file/artifact counts must not drive priority")
    return errors


def main():
    errors = validate()
    if errors:
        print("\n".join("ERROR: " + e for e in errors))
        sys.exit(1)
    with (ROOT / BACKLOG).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    stopped = sum(r["public_data_search_status"].startswith("STOP_") for r in rows)
    print(f"research-priority validation: OK ({len(rows)} gaps; {stopped} explicit public-search stop rules; Issues #25/#26 represented)")


if __name__ == "__main__":
    main()
