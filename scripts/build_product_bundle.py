#!/usr/bin/env python3
"""Build a deterministic product-specific replication archive."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = ROOT / "data/research_products.csv"
FILES = ROOT / "data/research_product_files.csv"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def zip_write(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build(product_id: str, output: Path, root: Path = ROOT) -> str:
    products = {row["product_id"]: row for row in rows(root / PRODUCTS.relative_to(ROOT))}
    if product_id not in products:
        raise ValueError(f"unknown product_id: {product_id}")
    product = products[product_id]
    selected = sorted(
        (row for row in rows(root / FILES.relative_to(ROOT)) if row["product_id"] == product_id),
        key=lambda row: row["path"],
    )
    manifest = io.StringIO(newline="")
    writer = csv.DictWriter(manifest, fieldnames=["path", "role", "sha256", "bytes"], lineterminator="\n")
    writer.writeheader()
    payloads: list[tuple[str, bytes]] = []
    for row in selected:
        data = (root / row["path"]).read_bytes()
        payloads.append((row["path"], data))
        writer.writerow({
            "path": row["path"],
            "role": row["role"],
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        })
    metadata = {
        "product_id": product_id,
        "display_name": product["display_name"],
        "scope": product["scope"],
        "reproduction_command": f"python scripts/reproduce.py {product['reproduction_target']}",
        "claim_registry": product["claim_registry"],
        "component_ids": product["component_ids"].split(";"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in payloads:
            zip_write(archive, name, data)
        zip_write(archive, "PRODUCT_BUNDLE_MANIFEST.csv", manifest.getvalue().encode())
        zip_write(archive, "PRODUCT_BUNDLE.json", (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode())
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = build(args.product_id, args.output)
    print(f"product bundle: {args.product_id} -> {args.output} sha256={digest}")


if __name__ == "__main__":
    main()
