#!/usr/bin/env python3
"""Build the source-by-source public redistribution audit from catalog + domain rules."""
from __future__ import annotations

import argparse
import csv
import io
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path("data/source_catalog.csv")
RULES = Path("data/raw_source_redistribution_rules.csv")
OUTPUT = Path("data/raw_source_redistribution_audit.csv")
FIELDS = [
    "source_id", "publisher", "title", "source_url", "raw_file", "sha256", "bytes",
    "source_status", "domain", "rights_status", "terms_url", "terms_checked_date",
    "public_release_action", "acquisition_instruction", "archive_reliance",
    "attribution_requirement", "third_party_caveat", "note",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def render(root: Path = ROOT) -> str:
    catalog = read_rows(root / CATALOG)
    rules = {row["domain"]: row for row in read_rows(root / RULES)}
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in sorted(catalog, key=lambda r: r["source_id"]):
        domain = urllib.parse.urlparse(row["source_url"]).netloc
        if domain not in rules:
            raise RuntimeError(f"missing redistribution rule for domain: {domain}")
        rule = rules[domain]
        writer.writerow({
            "source_id": row["source_id"],
            "publisher": row["publisher"],
            "title": row["title"],
            "source_url": row["source_url"],
            "raw_file": row["raw_file"],
            "sha256": row["sha256"],
            "bytes": row["bytes"],
            "source_status": row["status"],
            "domain": domain,
            "rights_status": rule["rights_status"],
            "terms_url": rule["terms_url"],
            "terms_checked_date": rule["terms_checked_date"],
            "public_release_action": "EXCLUDE_RAW_ACQUIRE_EXTERNALLY",
            "acquisition_instruction": (
                f"Retrieve from {row['source_url']} and verify SHA-256 {row['sha256']}; "
                "if bytes differ, treat the upstream source as changed and do not silently substitute."
            ),
            "archive_reliance": "NONE_DECLARED_IN_SOURCE_CATALOG",
            "attribution_requirement": rule["attribution_requirement"],
            "third_party_caveat": rule["third_party_caveat"],
            "note": rule["rule_note"],
        })
    return out.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render()
    path = ROOT / OUTPUT
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"{OUTPUT} is stale; regenerate it")
        print(f"raw-source redistribution audit: current ({len(read_rows(path))} sources)")
        return
    path.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT}: {len(read_rows(path))} sources")


if __name__ == "__main__":
    main()
