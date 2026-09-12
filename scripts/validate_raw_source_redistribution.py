#!/usr/bin/env python3
"""Validate source-by-source redistribution metadata and conservative public-release policy."""
from __future__ import annotations

import csv
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path("data/source_catalog.csv")
RULES = Path("data/raw_source_redistribution_rules.csv")
AUDIT = Path("data/raw_source_redistribution_audit.csv")
ALLOWED_ACTIONS = {"EXCLUDE_RAW_ACQUIRE_EXTERNALLY", "INCLUDE_RAW"}
ALLOW_RIGHTS = {"SITE_TERMS_ALLOW_REUSE_WITH_ATTRIBUTION"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    catalog_rows = read_rows(root / CATALOG)
    audit_rows = read_rows(root / AUDIT)
    rule_rows = read_rows(root / RULES)
    catalog = {r["source_id"]: r for r in catalog_rows}
    audit = {r["source_id"]: r for r in audit_rows}
    rules = {r["domain"]: r for r in rule_rows}
    if len(catalog) != len(catalog_rows):
        errors.append("source catalog contains duplicate source_id")
    if len(audit) != len(audit_rows):
        errors.append("redistribution audit contains duplicate source_id")
    if set(catalog) != set(audit):
        missing = sorted(set(catalog) - set(audit))
        extra = sorted(set(audit) - set(catalog))
        errors.append(f"audit/source catalog coverage mismatch missing={missing} extra={extra}")
    domains = {urllib.parse.urlparse(r["source_url"]).netloc for r in catalog_rows}
    if domains != set(rules):
        errors.append(f"domain rule coverage mismatch missing={sorted(domains-set(rules))} extra={sorted(set(rules)-domains)}")
    for source_id, source in catalog.items():
        row = audit.get(source_id)
        if row is None:
            continue
        domain = urllib.parse.urlparse(source["source_url"]).netloc
        for field, expected in (("publisher", source["publisher"]), ("title", source["title"]),
                                ("source_url", source["source_url"]), ("raw_file", source["raw_file"]),
                                ("sha256", source["sha256"]), ("bytes", source["bytes"]),
                                ("source_status", source["status"]), ("domain", domain)):
            if row[field] != expected:
                errors.append(f"{source_id}: {field} does not match source catalog")
        rule = rules.get(domain)
        if rule and row["rights_status"] != rule["rights_status"]:
            errors.append(f"{source_id}: rights_status does not match domain rule")
        if row["public_release_action"] not in ALLOWED_ACTIONS:
            errors.append(f"{source_id}: invalid public_release_action")
        if row["public_release_action"] == "INCLUDE_RAW" and row["rights_status"] not in ALLOW_RIGHTS:
            errors.append(f"{source_id}: raw inclusion lacks explicit reusable-rights status")
        if source["source_url"] not in row["acquisition_instruction"] or source["sha256"] not in row["acquisition_instruction"]:
            errors.append(f"{source_id}: acquisition instruction must contain source URL and expected SHA-256")
        if not row["attribution_requirement"]:
            errors.append(f"{source_id}: attribution requirement missing")
    return errors


def main() -> None:
    errors = validate()
    if errors:
        raise SystemExit("\n".join(f"ERROR: {e}" for e in errors))
    print(f"raw-source redistribution validation: OK sources={len(read_rows(ROOT / AUDIT))}")


if __name__ == "__main__":
    main()
