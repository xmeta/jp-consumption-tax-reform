#!/usr/bin/env python3
"""Validate explicit research-product and release boundaries."""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = ROOT / "data/research_products.csv"
FILES = ROOT / "data/research_product_files.csv"
PRODUCT_FIELDS = [
    "product_id", "display_name", "scope", "reproduction_target",
    "claim_registry", "component_ids",
]
FILE_FIELDS = ["product_id", "path", "role"]
ROLES = {"PRODUCT", "SHARED", "RELEASE_METADATA"}
PRIVATE_ROOTS = {
    "paper1": (
        "paper1/",
        "research/income_tax_pseudofiler/",
        "research/income_tax_partial_identification/",
        "research/stage1_filing_bound/",
    ),
    "vat_abolition": (
        "research/vat_compliance_productivity/",
        "research/vat_policy_integration/",
        "research/vat_claim_registry.csv",
    ),
}


def read_csv(path: Path, fields: list[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != fields:
            raise ValueError(f"{path.relative_to(ROOT)} schema mismatch")
        return list(reader)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def split(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        products = read_csv(root / PRODUCTS.relative_to(ROOT), PRODUCT_FIELDS)
        files = read_csv(root / FILES.relative_to(ROOT), FILE_FIELDS)
    except (OSError, ValueError) as exc:
        return [str(exc)]

    reproduce = load_module("product_reproduce", root / "scripts/reproduce.py")
    claims = load_module("product_claims", root / "scripts/generate_claim_registries.py")
    by_product = {row["product_id"]: row for row in products}
    if len(by_product) != len(products):
        errors.append("duplicate product_id")

    with (root / "data/claim_graph.csv").open(encoding="utf-8", newline="") as handle:
        graph = list(csv.DictReader(handle))
    graph_products = {row["product_id"] for row in graph}
    if set(by_product) != graph_products:
        errors.append("product IDs must exactly match claim-graph product IDs")

    with (root / "data/scientific_state.csv").open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle))
    state_by_id = {row["component_id"]: row for row in states}

    file_rows: dict[str, dict[str, str]] = {}
    consumers: dict[str, list[dict[str, str]]] = {}
    for row in files:
        key = f"{row['product_id']}\0{row['path']}"
        if key in file_rows:
            errors.append(f"duplicate product file: {row['product_id']}:{row['path']}")
        file_rows[key] = row
        consumers.setdefault(row["path"], []).append(row)
        if row["product_id"] not in by_product:
            errors.append(f"unknown product in file manifest: {row['product_id']}")
        if row["role"] not in ROLES:
            errors.append(f"invalid product-file role: {row['role']}")
        path = Path(row["path"])
        if path.is_absolute() or ".." in path.parts:
            errors.append(f"unsafe product-file path: {row['path']}")
        elif not (root / path).is_file():
            errors.append(f"missing product file: {row['path']}")

    for path, rows in consumers.items():
        if len(rows) > 1 and any(row["role"] == "PRODUCT" for row in rows):
            errors.append(f"multi-product file must be shared/metadata: {path}")

    for product_id, product in by_product.items():
        target = product["reproduction_target"]
        if target not in reproduce.TARGETS:
            errors.append(f"{product_id}: unknown reproduction target {target}")
            continue
        expected_registry = claims.PRODUCT_OUTPUTS.get(product_id)
        if expected_registry is None or expected_registry.as_posix() != product["claim_registry"]:
            errors.append(f"{product_id}: claim registry does not match claim projection")
        components = split(product["component_ids"])
        if not components or len(components) != len(set(components)):
            errors.append(f"{product_id}: component_ids must be unique and non-empty")
        for component in components:
            state = state_by_id.get(component)
            if state is None or state.get("active", "").lower() != "true":
                errors.append(f"{product_id}: unknown/inactive component {component}")
            elif f"{product_id}\0{state['module_path']}/README.adoc" not in file_rows:
                errors.append(f"{product_id}: component README missing from release boundary: {component}")
        for claim in graph:
            component = claim.get("component_id", "")
            if claim["product_id"] == product_id and component and component not in components:
                errors.append(f"{product_id}: claim component outside product boundary: {component}")

        required = {product["claim_registry"], "scripts/reproduce.py", "scripts/check_clean_tree.py"}
        required.update(command[0] for command in reproduce.TARGETS[target])
        for path in required:
            if f"{product_id}\0{path}" not in file_rows:
                errors.append(f"{product_id}: reproduction file missing from release boundary: {path}")

        other_products = set(PRIVATE_ROOTS) - {product_id}
        for row in files:
            if row["product_id"] != product_id:
                continue
            for other in other_products:
                if any(row["path"].startswith(prefix) for prefix in PRIVATE_ROOTS[other]):
                    errors.append(f"{product_id}: includes {other} private file: {row['path']}")

    return errors


def main() -> None:
    errors = validate()
    if errors:
        raise SystemExit("\n".join("ERROR: " + error for error in errors))
    products = read_csv(PRODUCTS, PRODUCT_FIELDS)
    files = read_csv(FILES, FILE_FIELDS)
    counts = {p["product_id"]: sum(r["product_id"] == p["product_id"] for r in files) for p in products}
    print("research-product validation: OK " + ", ".join(f"{k}={v} files" for k, v in counts.items()))


if __name__ == "__main__":
    main()
