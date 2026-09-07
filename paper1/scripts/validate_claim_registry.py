#!/usr/bin/env python3
from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "paper1/data/claim_registry.csv"

ALLOWED = {
    "OBSERVED_PUBLIC",
    "PARTIAL_IDENTIFIED_REPRODUCED",
    "SENSITIVITY_ONLY_RECOVERABLE",
    "DOCUMENTED_PRIOR_RUN_NOT_REPRODUCED",
    "READY_STATIC_ONLY",
    "NOT_READY",
}

REQUIRED = {f"P1-C{i:02d}" for i in range(1, 13)}
LOCAL_SOURCE_STATUSES = {
    "PARTIAL_IDENTIFIED_REPRODUCED",
    "READY_STATIC_ONLY",
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
    if by_id["P1-C08"]["status"] != "PARTIAL_IDENTIFIED_REPRODUCED":
        errors.append("P1-C08 must remain reproduced partial identification")
    if by_id["P1-C09"]["status"] != "PARTIAL_IDENTIFIED_REPRODUCED":
        errors.append("P1-C09 must remain reproduced partial identification")
    if by_id["P1-C10"]["status"] != "NOT_READY":
        errors.append("P1-C10 non-resident count must remain NOT_READY")
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
    ]
    for phrase in prohibited:
        if phrase.lower() in paper.lower():
            errors.append(f"prohibited manuscript phrase: {phrase}")

    if errors:
        print("\n".join("ERROR: " + e for e in errors))
        sys.exit(1)

    print(f"paper1 claim registry validation: OK ({len(rows)} claims)")

if __name__ == "__main__":
    main()
