#!/usr/bin/env python3
"""Validate publication-facing citation, licensing, and reproduction metadata."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = Path("data/research_products.csv")
FILES = Path("data/research_product_files.csv")
REQUIRED_RELEASE_METADATA = {
    "CITATION.cff",
    "REPRODUCE.adoc",
    "docs/data_availability.adoc",
    "docs/licensing.adoc",
    "docs/research_products.adoc",
    "scripts/build_product_bundle.py",
}


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def require_tokens(text: str, tokens: tuple[str, ...], label: str, errors: list[str]) -> None:
    for token in tokens:
        if token not in text:
            errors.append(f"{label}: missing required token {token!r}")


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    licensing = (root / "docs/licensing.adoc").read_text(encoding="utf-8")
    availability = (root / "docs/data_availability.adoc").read_text(encoding="utf-8")
    reproduce = (root / "REPRODUCE.adoc").read_text(encoding="utf-8")

    require_tokens(citation, (
        "cff-version: 1.2.0",
        'alias: "xmeta"',
        'repository-code: "https://github.com/xmeta/jp-consumption-tax-reform"',
    ), "CITATION.cff", errors)
    require_tokens(licensing, (
        "NO_BLANKET_PUBLIC_LICENSE_GRANTED",
        "raw_source_redistribution_audit.csv",
        "CITATION.cff",
    ), "licensing", errors)
    require_tokens(availability, (
        "Public and archived sources",
        "Restricted and recovery-only material",
        "RAW_SOURCE_ACQUISITION.csv",
    ), "data availability", errors)
    require_tokens(reproduce, (
        "python scripts/reproduce.py paper1",
        "python scripts/reproduce.py vat",
        "python scripts/reproduce.py clean-room",
        "--public-release",
    ), "REPRODUCE", errors)

    products = {row["product_id"]: row for row in rows(root / PRODUCTS)}
    boundaries: dict[str, set[str]] = {product_id: set() for product_id in products}
    for row in rows(root / FILES):
        if row["product_id"] in boundaries:
            boundaries[row["product_id"]].add(row["path"])

    for product_id, product in products.items():
        missing = sorted(REQUIRED_RELEASE_METADATA - boundaries.get(product_id, set()))
        if missing:
            errors.append(f"{product_id}: release metadata missing {missing}")
        command = f"python scripts/reproduce.py {product['reproduction_target']}"
        if command not in reproduce:
            errors.append(f"{product_id}: reproduction command missing from REPRODUCE.adoc")
        if not product["publication_status"]:
            errors.append(f"{product_id}: publication_status missing")

    return errors


def main() -> None:
    errors = validate()
    if errors:
        raise SystemExit("\n".join(f"ERROR: {error}" for error in errors))
    print(f"publication metadata validation: OK products={len(rows(ROOT / PRODUCTS))}")


if __name__ == "__main__":
    main()
