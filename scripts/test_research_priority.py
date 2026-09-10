#!/usr/bin/env python3
if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests; assertions must remain active")

from pathlib import Path
import csv
import shutil
import tempfile

from validate_research_priority import validate

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "data/research_priority_backlog.csv"
DOC = ROOT / "docs/research_prioritization.adoc"


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


assert validate(ROOT) == []
fields, baseline = read_rows(BACKLOG)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "data").mkdir()
    (root / "docs").mkdir()
    shutil.copy2(DOC, root / "docs/research_prioritization.adoc")

    rows = [dict(r) for r in baseline]
    rows[0]["priority_rank"] = "2"
    write_rows(root / "data/research_priority_backlog.csv", fields, rows)
    assert any("consecutive priority_rank" in e for e in validate(root))

    rows = [dict(r) for r in baseline]
    next(r for r in rows if r["gap_id"] == "INCOME-TAX-RETURN-MICRO-LINK")["issue_refs"] = "26"
    write_rows(root / "data/research_priority_backlog.csv", fields, rows)
    assert any("Issue #25" in e for e in validate(root))

    rows = [dict(r) for r in baseline]
    rows[0]["evidence_accumulation_only"] = "true"
    rows[0]["identification_gain_type"] = "EVIDENCE_ACCUMULATION_ONLY"
    write_rows(root / "data/research_priority_backlog.csv", fields, rows)
    assert any("evidence-only work cannot be HIGH" in e for e in validate(root))

    rows = [dict(r) for r in baseline]
    row = next(r for r in rows if r["public_data_search_status"] == "STOP_PUBLIC_SEARCH_ESCALATE_RESTRICTED")
    row["escalation_if_stopped"] = ""
    write_rows(root / "data/research_priority_backlog.csv", fields, rows)
    assert any("stopped public search requires escalation" in e for e in validate(root))

print("research-priority validator tests: OK (rank, issue coverage, evidence-only guard, stop/escalation guard)")
