#!/usr/bin/env python3
from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "paper1/data/claim_registry.csv"

ALLOWED = {
    "OBSERVED_PUBLIC",
    "ROBUSTNESS_FRONTIER_REPRODUCED",
    "SENSITIVITY_ONLY_RECOVERABLE",
    "SENSITIVITY_ONLY_REPRODUCED",
    "EXTERNAL_STAGE2_DIAGNOSTIC_REPRODUCED",
    "CROSS_PUBLICATION_POINT_CHECK_REPRODUCED",
    "MODEL_CONTINGENT_TRANSPORT_RELAXATION_REPRODUCED",
    "MODEL_CONTINGENT_RANK_BRIDGE_RELAXATION_REPRODUCED",
    "MODEL_CONTINGENT_RANK_TRANSPORT_BUDGET_REPRODUCED",
    "MODEL_CONTINGENT_RANK_EPSILON_SURFACE_REPRODUCED",
    "DOCUMENTED_PRIOR_RUN_NOT_REPRODUCED",
    "READY_STATIC_ONLY",
    "NOT_READY",
}

REQUIRED = {f"P1-C{i:02d}" for i in range(1, 17)}
LOCAL_SOURCE_STATUSES = {
    "ROBUSTNESS_FRONTIER_REPRODUCED",
    "READY_STATIC_ONLY",
    "SENSITIVITY_ONLY_REPRODUCED",
    "EXTERNAL_STAGE2_DIAGNOSTIC_REPRODUCED",
    "CROSS_PUBLICATION_POINT_CHECK_REPRODUCED",
    "MODEL_CONTINGENT_TRANSPORT_RELAXATION_REPRODUCED",
    "MODEL_CONTINGENT_RANK_BRIDGE_RELAXATION_REPRODUCED",
    "MODEL_CONTINGENT_RANK_TRANSPORT_BUDGET_REPRODUCED",
    "MODEL_CONTINGENT_RANK_EPSILON_SURFACE_REPRODUCED",
    "NOT_READY",
}

def fail(msg):
    print(f"ERROR: {msg}")
    return 1

def main():
    with REGISTRY.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    errors = []
    ids = [r["claim_id"] for r in rows]
    if len(ids) != len(set(ids)):
        errors.append("duplicate claim_id")
    if set(ids) != REQUIRED:
        errors.append(
            f"claim-id set mismatch: got={sorted(ids)}"
        )

    for row in rows:
        cid = row["claim_id"]
        status = row["status"]
        if status not in ALLOWED:
            errors.append(f"{cid}: unknown status {status}")
        if not row["allowed_claim"].strip():
            errors.append(f"{cid}: allowed_claim is empty")
        if not row["forbidden_claim"].strip():
            errors.append(f"{cid}: forbidden_claim is empty")
        if not row["source"].strip():
            errors.append(f"{cid}: source is empty")

        src = row["source"].strip()
        if status in LOCAL_SOURCE_STATUSES and (
            src.startswith("research/") or src == "STATUS.adoc"
        ):
            if not (ROOT / src).exists():
                errors.append(f"{cid}: local source missing: {src}")

    by_id = {r["claim_id"]: r for r in rows}
    if by_id["P1-C03"]["status"] != "SENSITIVITY_ONLY_REPRODUCED":
        errors.append("P1-C03 pseudo-filer must remain reproduced sensitivity-only")
    if by_id["P1-C05"]["status"] != "EXTERNAL_STAGE2_DIAGNOSTIC_REPRODUCED":
        errors.append("P1-C05 must remain an external reproduced diagnostic")
    if by_id["P1-C06"]["status"] != "DOCUMENTED_PRIOR_RUN_NOT_REPRODUCED":
        errors.append("P1-C06 restricted LP must remain unreproduced")
    if by_id["P1-C07"]["status"] != "CROSS_PUBLICATION_POINT_CHECK_REPRODUCED":
        errors.append("P1-C07 must remain a non-inferential reproduced point check")
    if by_id["P1-C08"]["status"] != "ROBUSTNESS_FRONTIER_REPRODUCED":
        errors.append("P1-C08 must remain a reproduced robustness frontier")
    if by_id["P1-C09"]["status"] != "DOCUMENTED_PRIOR_RUN_NOT_REPRODUCED":
        errors.append("P1-C09 recovered threshold must remain unreproduced")
    if by_id["P1-C10"]["status"] != "NOT_READY":
        errors.append("P1-C10 untracked frame mismatch must remain NOT_READY")
    if by_id["P1-C13"]["status"] != "MODEL_CONTINGENT_TRANSPORT_RELAXATION_REPRODUCED":
        errors.append("P1-C13 must remain model-contingent transport-relaxation")
    if by_id["P1-C14"]["status"] != "MODEL_CONTINGENT_RANK_BRIDGE_RELAXATION_REPRODUCED":
        errors.append("P1-C14 must remain model-contingent same-rank bridge")
    if by_id["P1-C15"]["status"] != "MODEL_CONTINGENT_RANK_TRANSPORT_BUDGET_REPRODUCED":
        errors.append("P1-C15 must remain model-contingent rank-transport-budget frontier")
    if by_id["P1-C16"]["status"] != "MODEL_CONTINGENT_RANK_EPSILON_SURFACE_REPRODUCED":
        errors.append("P1-C16 must remain model-contingent fixed-budget rank-epsilon surface")
    for cid in ("P1-C11", "P1-C12"):
        if by_id[cid]["status"] != "NOT_READY":
            errors.append(f"{cid} must remain NOT_READY")

    paper = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "paper1").rglob("*.adoc"))
    )
    prohibited = [
        "income_tax = READY",
        "filing rate is point identified",
        "fully sharp identified set",
        "score_power=2.0 prior is rejected whenever",
        "replacement transport-relaxation lp identifies the filer mtr",
        "transport-relaxation envelope is a confidence interval",
        "replacement transport-relaxation lp reproduces the historical v6 restricted lp",
        "rank-bridge envelope is a confidence interval",
        "same-rank bridge is observed linkage",
        "rank-bridge v2 reproduces the historical v6 restricted lp",
        "rank-transport v3 is observed linkage",
        "rank-transport budget is estimated rank error",
        "v3 frontier mtr is point identified",
        "rank-transport v3 reproduces the historical v6 restricted lp",
        "rank-epsilon surface is a confidence region",
        "epsilon is estimated discrepancy",
        "v4 mtr is point identified",
        "rank-epsilon v4 reproduces the historical v6 restricted lp",
    ]
    for phrase in prohibited:
        if phrase.lower() in paper.lower():
            errors.append(f"prohibited manuscript phrase: {phrase}")
    if "\x0b" in paper:
        errors.append("manuscript contains vertical-tab control character; check LaTeX backslash escaping")

    if errors:
        print("\n".join("ERROR: " + e for e in errors))
        sys.exit(1)

    print(f"paper1 claim registry validation: OK ({len(rows)} claims)")

if __name__ == "__main__":
    main()
