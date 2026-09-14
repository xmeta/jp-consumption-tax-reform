#!/usr/bin/env python3
"""Generate the Paper 1 reader-facing claim-status summary table."""
from pathlib import Path
import argparse
import csv
import io
import sys

ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / "data/claim_graph.csv"
REGISTRY = ROOT / "paper1/data/claim_registry.csv"
OUTPUT = ROOT / "paper1/data/claim_status_summary_table.csv"

SELECTED = (
    "P1-C08",  # Stage-1 frontier
    "P1-C13",  # v1
    "P1-C14",  # v2
    "P1-C15",  # v3
    "P1-C16",  # v4
    "P1-C17",  # v5
    "P1-C06",  # historical restricted LP
    "P1-C05",  # external NTA diagnostic
    "P1-C07",  # cross-publication point check
)


def read(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build():
    graph = {r["claim_id"]: r for r in read(GRAPH) if r["product_id"] == "paper1"}
    registry = {r["claim_id"]: r for r in read(REGISTRY)}
    rows = []
    for claim_id in SELECTED:
        if claim_id not in graph or claim_id not in registry:
            raise RuntimeError(f"missing Paper 1 claim: {claim_id}")
        g = graph[claim_id]
        r = registry[claim_id]
        for graph_key, registry_key in (
            ("topic", "topic"),
            ("empirical_status", "status"),
            ("evidence_scope", "evidence_scope"),
            ("forbidden_claim", "forbidden_claim"),
            ("source", "source"),
        ):
            if g[graph_key] != r[registry_key]:
                raise RuntimeError(f"claim graph/registry drift for {claim_id}: {graph_key}")
        rows.append({
            "Claim": claim_id,
            "Empirical object": g["topic"],
            "Empirical status": g["empirical_status"],
            "Identification status": g["identification_status"],
            "Evidence / maintained design": g["evidence_scope"],
            "Explicitly forbidden interpretation": g["forbidden_claim"],
        })
    return rows


def render(rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render(build())
    if args.check:
        actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if actual != expected:
            print("ERROR: claim_status_summary_table.csv is stale")
            sys.exit(1)
        print(f"paper1 claim-status summary: current ({len(SELECTED)} claims)")
        return
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
