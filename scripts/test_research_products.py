#!/usr/bin/env python3
"""Regression tests for research-product boundaries and release bundles."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import tempfile
import zipfile
from pathlib import Path

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load("research_products_validator", ROOT / "scripts/validate_research_products.py")
builder = load("research_products_builder", ROOT / "scripts/build_product_bundle.py")
assert validator.validate(ROOT) == []

with (ROOT / "data/research_product_files.csv").open(encoding="utf-8", newline="") as handle:
    file_rows = list(csv.DictReader(handle))

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    for product_id in ("paper1", "vat_abolition"):
        first = tmp / f"{product_id}-1.zip"
        second = tmp / f"{product_id}-2.zip"
        first_hash = builder.build(product_id, first, ROOT)
        second_hash = builder.build(product_id, second, ROOT)
        assert first_hash == second_hash
        assert first.read_bytes() == second.read_bytes()

        with zipfile.ZipFile(first) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names))
            metadata = json.loads(archive.read("PRODUCT_BUNDLE.json"))
            assert metadata["product_id"] == product_id
            with (ROOT / "data/research_products.csv").open(encoding="utf-8", newline="") as handle:
                products = {row["product_id"]: row for row in csv.DictReader(handle)}
            assert metadata["publication_status"] == products[product_id]["publication_status"]
            manifest = list(csv.DictReader(io.StringIO(archive.read("PRODUCT_BUNDLE_MANIFEST.csv").decode())))
            expected = [row for row in file_rows if row["product_id"] == product_id]
            assert len(manifest) == len(expected)
            for row in manifest:
                data = archive.read(row["path"])
                assert hashlib.sha256(data).hexdigest() == row["sha256"]
                assert len(data) == int(row["bytes"])

            other_products = set(validator.PRIVATE_ROOTS) - {product_id}
            for other in other_products:
                assert not any(
                    name.startswith(prefix)
                    for name in names
                    for prefix in validator.PRIVATE_ROOTS[other]
                )

        public = tmp / f"{product_id}-public.zip"
        builder.build(product_id, public, ROOT, public_release=True)
        with zipfile.ZipFile(public) as archive:
            names = archive.namelist()
            assert not any(name.startswith("data/raw/") for name in names)
            metadata = json.loads(archive.read("PRODUCT_BUNDLE.json"))
            assert metadata["bundle_mode"] == "public_release"
            acquisition = list(csv.DictReader(io.StringIO(archive.read("RAW_SOURCE_ACQUISITION.csv").decode())))
            expected_raw = [row for row in file_rows if row["product_id"] == product_id and row["path"].startswith("data/raw/")]
            assert len(acquisition) == len(expected_raw)
            for row in acquisition:
                assert row["public_release_action"] == "EXCLUDE_RAW_ACQUIRE_EXTERNALLY"
                assert row["source_url"] in row["acquisition_instruction"]
                assert row["sha256"] in row["acquisition_instruction"]

print("research-product bundle tests: OK (determinism, hashes, isolation, public raw-source exclusion)")
