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
RAW_AUDIT = ROOT / "data/raw_source_redistribution_audit.csv"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
ACQUISITION_FIELDS = [
    "source_id", "publisher", "title", "source_url", "raw_file", "sha256", "bytes",
    "rights_status", "terms_url", "public_release_action", "acquisition_instruction",
    "attribution_requirement",
]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def zip_write(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build(product_id: str, output: Path, root: Path = ROOT, *, public_release: bool = False) -> str:
    products = {row["product_id"]: row for row in rows(root / PRODUCTS.relative_to(ROOT))}
    if product_id not in products:
        raise ValueError(f"unknown product_id: {product_id}")
    product = products[product_id]
    selected = sorted(
        (row for row in rows(root / FILES.relative_to(ROOT)) if row["product_id"] == product_id),
        key=lambda row: row["path"],
    )
    raw_selected = [row for row in selected if row["path"].startswith("data/raw/")]
    audit_by_path: dict[str, dict[str, str]] = {}
    if public_release and raw_selected:
        audit_by_path = {row["raw_file"]: row for row in rows(root / RAW_AUDIT.relative_to(ROOT))}

    manifest = io.StringIO(newline="")
    writer = csv.DictWriter(manifest, fieldnames=["path", "role", "sha256", "bytes"], lineterminator="\n")
    writer.writeheader()
    acquisition = io.StringIO(newline="")
    acquisition_writer = csv.DictWriter(acquisition, fieldnames=ACQUISITION_FIELDS, lineterminator="\n")
    acquisition_writer.writeheader()
    payloads: list[tuple[str, bytes]] = []
    for row in selected:
        if public_release and row["path"].startswith("data/raw/"):
            audit = audit_by_path.get(row["path"])
            if audit is None:
                raise ValueError(f"raw source missing redistribution audit: {row['path']}")
            if audit["public_release_action"] != "INCLUDE_RAW":
                acquisition_writer.writerow({field: audit[field] for field in ACQUISITION_FIELDS})
                continue
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
        "publication_status": product["publication_status"],
        "bundle_mode": "public_release" if public_release else "internal_replication",
        "raw_source_policy": "external_acquisition_manifest" if public_release else "declared_product_files",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in payloads:
            zip_write(archive, name, data)
        zip_write(archive, "PRODUCT_BUNDLE_MANIFEST.csv", manifest.getvalue().encode())
        if public_release:
            zip_write(archive, "RAW_SOURCE_ACQUISITION.csv", acquisition.getvalue().encode())
        zip_write(archive, "PRODUCT_BUNDLE.json", (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode())
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public-release", action="store_true", help="exclude raw source bytes unless explicitly cleared")
    args = parser.parse_args()
    digest = build(args.product_id, args.output, public_release=args.public_release)
    print(f"product bundle: {args.product_id} -> {args.output} sha256={digest}")


if __name__ == "__main__":
    main()
