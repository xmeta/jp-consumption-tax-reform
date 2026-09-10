#!/usr/bin/env python3
"""Generate product-specific claim registries from the repository claim graph."""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_FIELDS = [
    "product_id",
    "claim_id",
    "topic",
    "empirical_status",
    "identification_status",
    "causal_status",
    "policy_status",
    "component_id",
    "evidence_scope",
    "allowed_claim",
    "forbidden_claim",
    "source",
    "evidence_ids",
    "supersedes",
    "superseded_by",
    "active",
]
LEGACY_FIELDS = [
    "claim_id",
    "topic",
    "status",
    "evidence_scope",
    "allowed_claim",
    "forbidden_claim",
    "source",
]
PRODUCT_OUTPUTS = {
    "paper1": Path("paper1/data/claim_registry.csv"),
    "vat_abolition": Path("research/vat_claim_registry.csv"),
}


def read_graph(root: Path = ROOT) -> list[dict[str, str]]:
    path = root / "data/claim_graph.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != GRAPH_FIELDS:
            raise ValueError("claim_graph.csv schema mismatch")
        return list(reader)


def render_product(rows: list[dict[str, str]], product_id: str) -> str:
    selected = sorted(
        (row for row in rows if row["product_id"] == product_id),
        key=lambda row: row["claim_id"],
    )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=LEGACY_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in selected:
        writer.writerow(
            {
                "claim_id": row["claim_id"],
                "topic": row["topic"],
                "status": row["empirical_status"],
                "evidence_scope": row["evidence_scope"],
                "allowed_claim": row["allowed_claim"],
                "forbidden_claim": row["forbidden_claim"],
                "source": row["source"],
            }
        )
    return buffer.getvalue()


def expected_outputs(root: Path = ROOT) -> dict[Path, str]:
    rows = read_graph(root)
    return {
        relative: render_product(rows, product_id)
        for product_id, relative in PRODUCT_OUTPUTS.items()
    }


def generate(root: Path = ROOT, *, check: bool = False) -> list[str]:
    errors: list[str] = []
    for relative, expected in expected_outputs(root).items():
        path = root / relative
        if check:
            if not path.is_file():
                errors.append(f"missing generated claim registry: {relative}")
            elif path.read_text(encoding="utf-8") != expected:
                errors.append(f"generated claim registry is stale: {relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    errors = generate(ROOT, check=args.check)
    if errors:
        raise SystemExit("\n".join("ERROR: " + error for error in errors))
    action = "validation" if args.check else "generation"
    counts = {
        product: sum(row["product_id"] == product for row in read_graph(ROOT))
        for product in PRODUCT_OUTPUTS
    }
    print(
        "claim-registry " + action + ": OK "
        + ", ".join(f"{product}={count}" for product, count in counts.items())
    )


if __name__ == "__main__":
    main()
