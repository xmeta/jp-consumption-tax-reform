#!/usr/bin/env python3
from pathlib import Path
from tempfile import TemporaryDirectory

from report_research_progress import CANONICAL_KPIS, snapshot, validate, worktree_reader


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


with TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root,
        "data/research_priority_backlog.csv",
        "gap_id,expected_voi\nA,HIGH\nB,LOW\nC,HIGH\n",
    )
    write(
        root,
        "data/derived/vat_policy_pareto_pairwise.csv",
        "dominance_status\nINDETERMINATE_MISSING_REQUIRED_OBJECTIVES\nDOMINATES\n",
    )
    write(
        root,
        "data/scientific_review_gates.csv",
        "minimum_independence,status\nINDEPENDENT_REVIEWER,SATISFIED\n"
        "INDEPENDENT_REVIEWER,PENDING\nINTERNAL_ADVERSARIAL,SATISFIED\n",
    )
    write(
        root,
        "data/claim_graph.csv",
        "claim_id,identification_status,active\n"
        "C1,RECOVERY_ONLY,true\nC2,READY,true\nC3,RECOVERY_ONLY,false\n",
    )
    values = snapshot(worktree_reader(root))
    assert values == {
        "high_voi_unresolved_gaps": (2, None),
        "indeterminate_policy_pairs": (1, 2),
        "independent_review_gates_satisfied": (1, 2),
        "active_recovery_only_claims": (1, 2),
    }, values

assert len(CANONICAL_KPIS) == 6
assert "policy_relations_resolved" in CANONICAL_KPIS

errors = validate()
assert not errors, errors

print("research-progress KPI tests: OK")
