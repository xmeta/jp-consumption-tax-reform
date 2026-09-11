#!/usr/bin/env python3
"""Validate scientific-review gates independently from computational CI."""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_FIELDS = [
    "product_id", "promotion_target", "review_track", "minimum_independence",
    "status", "review_id",
]
REVIEW_FIELDS = [
    "review_id", "product_id", "review_track", "independence", "status",
    "reviewed_commit", "findings_path", "resolution_path", "evidence_eligible",
]
PRODUCT_FIELDS = [
    "product_id", "display_name", "scope", "reproduction_target",
    "claim_registry", "component_ids",
]
TRACKS = {"ADVERSARIAL_CLAIM", "ECONOMIC_IDENTIFICATION", "MANUSCRIPT_MAJOR_REVISION"}
INDEPENDENCE = {"INTERNAL_ADVERSARIAL": 1, "INDEPENDENT_REVIEWER": 2, "EXTERNAL_PEER": 3}
GATE_STATUSES = {"PENDING", "SATISFIED"}
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

REQUIRED_GATES = {
    "paper1": {
        ("SUBMISSION_QUALITY", "ADVERSARIAL_CLAIM", "INTERNAL_ADVERSARIAL"),
        ("SUBMISSION_QUALITY", "ECONOMIC_IDENTIFICATION", "INDEPENDENT_REVIEWER"),
        ("SUBMISSION_QUALITY", "MANUSCRIPT_MAJOR_REVISION", "INDEPENDENT_REVIEWER"),
    },
    "vat_abolition": {
        ("STANDALONE_PAPER", "ADVERSARIAL_CLAIM", "INTERNAL_ADVERSARIAL"),
        ("STANDALONE_PAPER", "ECONOMIC_IDENTIFICATION", "INDEPENDENT_REVIEWER"),
    },
}


def read_csv(path: Path, fields: list[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != fields:
            raise ValueError(f"{path.name} schema mismatch")
        return list(reader)


def safe_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def split(value: str) -> list[str]:
    return [part for part in value.split(";") if part]

def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        products = read_csv(root / "data/research_products.csv", PRODUCT_FIELDS)
        gates = read_csv(root / "data/scientific_review_gates.csv", GATE_FIELDS)
        reviews = read_csv(root / "data/scientific_reviews.csv", REVIEW_FIELDS)
    except (OSError, ValueError) as exc:
        return [f"schema: {exc}"]

    product_ids = {row["product_id"] for row in products}
    if len(product_ids) != len(products):
        errors.append("schema: duplicate research product_id")
    if product_ids != set(REQUIRED_GATES):
        errors.append("schema: review policy must cover every research product")

    reviews_by_id: dict[str, dict[str, str]] = {}
    for review in reviews:
        review_id = review["review_id"]
        if not review_id or review_id in reviews_by_id:
            errors.append(f"schema: duplicate/empty review_id {review_id!r}")
            continue
        reviews_by_id[review_id] = review
        if review["product_id"] not in product_ids:
            errors.append(f"schema: {review_id}: unknown product_id")
        if review["review_track"] not in TRACKS:
            errors.append(f"schema: {review_id}: unknown review_track")
        if review["independence"] not in INDEPENDENCE:
            errors.append(f"schema: {review_id}: unknown independence class")
        if review["status"] != "COMPLETE":
            errors.append(f"schema: {review_id}: unsupported review status")
        if not COMMIT_RE.fullmatch(review["reviewed_commit"]):
            errors.append(f"schema: {review_id}: reviewed_commit must be a full SHA-1")
        if review["evidence_eligible"] != "false":
            errors.append(f"evidence: {review_id}: review records must be evidence_eligible=false")
        for field in ("findings_path", "resolution_path"):
            value = review[field]
            if not safe_path(value):
                errors.append(f"schema: {review_id}: unsafe {field}")
            elif not value.startswith("reviews/"):
                errors.append(f"schema: {review_id}: {field} must live under reviews/")
            elif not (root / value).is_file():
                errors.append(f"provenance: {review_id}: missing {field} {value}")

    gate_keys: set[tuple[str, str, str]] = set()
    for gate in gates:
        key = (gate["product_id"], gate["promotion_target"], gate["review_track"])
        if key in gate_keys:
            errors.append(f"schema: duplicate review gate {key}")
            continue
        gate_keys.add(key)
        if gate["product_id"] not in product_ids:
            errors.append(f"schema: unknown gate product {gate['product_id']}")
        if gate["review_track"] not in TRACKS:
            errors.append(f"schema: unknown gate track {gate['review_track']}")
        if gate["minimum_independence"] not in INDEPENDENCE:
            errors.append(f"schema: unknown gate independence {gate['minimum_independence']}")
        if gate["status"] not in GATE_STATUSES:
            errors.append(f"schema: invalid gate status {gate['status']}")
        if gate["status"] == "PENDING":
            if gate["review_id"]:
                errors.append(f"schema: pending gate must not name review_id: {key}")
            continue

        review_id = gate["review_id"]
        review = reviews_by_id.get(review_id)
        if review is None:
            errors.append(f"review: satisfied gate missing completed review: {key}")
            continue
        if review["product_id"] != gate["product_id"]:
            errors.append(f"review: {review_id}: product does not satisfy gate {key}")
        if review["review_track"] != gate["review_track"]:
            errors.append(f"review: {review_id}: track does not satisfy gate {key}")
        if review["status"] != "COMPLETE":
            errors.append(f"review: {review_id}: review is not complete")
        if review["independence"] in INDEPENDENCE and gate["minimum_independence"] in INDEPENDENCE:
            if INDEPENDENCE[review["independence"]] < INDEPENDENCE[gate["minimum_independence"]]:
                errors.append(f"review: {review_id}: independence below gate minimum")

    for product_id, required in REQUIRED_GATES.items():
        actual = {
            (row["promotion_target"], row["review_track"], row["minimum_independence"])
            for row in gates if row["product_id"] == product_id
        }
        if actual != required:
            errors.append(f"schema: {product_id}: review-gate set mismatch")

    review_paths = {
        review[field]
        for review in reviews
        for field in ("findings_path", "resolution_path")
        if review[field]
    }
    review_ids = set(reviews_by_id)
    try:
        with (root / "data/source_catalog.csv").open(encoding="utf-8", newline="") as handle:
            source_rows = list(csv.DictReader(handle))
        with (root / "data/claim_graph.csv").open(encoding="utf-8", newline="") as handle:
            claim_rows = list(csv.DictReader(handle))
    except OSError as exc:
        errors.append(f"provenance: {exc}")
        return errors

    raw_files = {row.get("raw_file", "") for row in source_rows}
    for path in review_paths & raw_files:
        errors.append(f"evidence: review artifact registered as raw source: {path}")
    for claim in claim_rows:
        if claim.get("source", "") in review_paths:
            errors.append(f"evidence: {claim.get('claim_id')}: review artifact used as claim source")
        used_review_ids = review_ids.intersection(split(claim.get("evidence_ids", "")))
        if used_review_ids:
            errors.append(
                f"evidence: {claim.get('claim_id')}: review IDs used as evidence: "
                + ";".join(sorted(used_review_ids))
            )

    return errors

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        raise SystemExit("\n".join("ERROR: " + error for error in errors))

    gates = read_csv(args.root / "data/scientific_review_gates.csv", GATE_FIELDS)
    products = read_csv(args.root / "data/research_products.csv", PRODUCT_FIELDS)
    summaries = []
    for product in products:
        rows = [row for row in gates if row["product_id"] == product["product_id"]]
        satisfied = sum(row["status"] == "SATISFIED" for row in rows)
        state = "READY_FOR_PROMOTION" if satisfied == len(rows) else "BLOCKED"
        summaries.append(f"{product['product_id']}={state}({satisfied}/{len(rows)})")
    print("scientific-review validation: OK " + ", ".join(summaries))


if __name__ == "__main__":
    main()
