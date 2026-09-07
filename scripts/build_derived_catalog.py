#!/usr/bin/env python3
from pathlib import Path
import csv
import hashlib

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived"
OUT = ROOT / "data/derived_catalog.csv"

SPECS = [
    (
        "STAGE1-OFFICIAL-INPUTS",
        "stage1_official_inputs.csv",
        "manual_transcription_verified",
        "NTA-R06;STAT-CENSUS-2020-SUMMARY;STAT-CENSUS-2020-BASIC;"
        "STAT-F71561-DESIGN;ISHIKAWA-CENSUS-2020;STAT-MIGRATION-2024;"
        "MHLW-VITAL-2020-T1;MHLW-VITAL-2022-T1;MHLW-VITAL-2024-T1",
        "DERIVED_VERIFIED_TRANSCRIPTION",
        "Normalized official values used by the stage-1 robustness analysis",
    ),
    (
        "ESTAT-71531-DECILES-LONG",
        "estat_71531_deciles_long.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7153-1-2024",
        "DERIVED_REPRODUCED",
        "Table 7-153-1 decile-by-income-component long extract with source cells",
    ),
    (
        "ESTAT-71561-HOUSEHOLD-TYPES",
        "estat_71561_household_types.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "49 household-type headers and hierarchy; original leaves derived structurally",
    ),
    (
        "ESTAT-71561-DECILES-LONG",
        "estat_71561_deciles_long.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "Table 7-156-1 decile x household-type x component long extract with source cells",
    ),
    (
        "ESTAT-71561-LEAF-COMPAT",
        "income_tax_household_type_leaf_deciles_2024.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "14 structural leaf household types x 10 deciles; compatibility layer for income-tax research",
    ),
    (
        "ESTAT-71531-TAX-SOCIAL-INSTRUMENTS",
        "income_tax_decile_tax_social_instruments_2024.csv",
        "scripts/build_income_tax_decile_instruments.py",
        "ESTAT-7153-1-2024",
        "DERIVED_REPRODUCED",
        "Decile income tax, resident tax and social-insurance contribution moments",
    ),
    (
        "ESTAT-71561-LEAF-AUDIT",
        "estat_71561_leaf_aggregation_audit.csv",
        "scripts/build_income_tax_decile_instruments.py",
        "ESTAT-7153-1-2024;ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "Leaf aggregation versus total-table rounding diagnostic",
    ),
    (
        "ESTAT-71911-SIZE-AGE-BRIDGE",
        "estat_71911_decile_household_size_age_bridge.csv",
        "scripts/extract_estat_f71911_bridge.py",
        "ESTAT-7191-1-2024",
        "DERIVED_REPRODUCED",
        "F71911 decile household-size top-code sensitivity and age-65+ bridge with source cells",
    ),
    (
        "ESTAT-71911-INCOME-TAX-BRIDGE",
        "income_tax_bridge_deciles_2024.csv",
        "scripts/extract_estat_f71911_bridge.py",
        "ESTAT-7191-1-2024",
        "DERIVED_REPRODUCED_SENSITIVITY_INPUT",
        "Backward-compatible pseudo-filer sensitivity bridge; exact mean household size is not identified because 6+ is top-coded",
    ),
    (
        "NTA-2026-STATUTORY-PARAMETERS",
        "income_tax_2026_statutory_parameters.csv",
        "scripts/build_income_tax_2026_statutory_parameters.py",
        "NTA-2026-TAX-REFORM;NTA-2026-INCOME-TAX;NTA-SALARY-DEDUCTION-1410;NTA-INCOME-TAX-RATE-2260;NTA-2026-PENSION-TAX;NTA-2026-PENSION-DETAIL",
        "DERIVED_REPRODUCED_VERIFIED_RULES",
        "Versioned 2026 statutory tax parameters with official source locators and raw SHA-256 values",
    ),
]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def row_count(path):
    with path.open(encoding="utf-8", newline="") as f:
        return max(0, sum(1 for _ in f) - 1)


def main():
    rows = []
    registered = set()
    for aid, rel, generator, source_ids, status, description in SPECS:
        path = DERIVED / rel
        if not path.exists():
            raise SystemExit(f"missing derived artifact: {path}")
        if rel in registered:
            raise SystemExit(f"duplicate derived path: {rel}")
        registered.add(rel)
        rows.append({
            "artifact_id": aid,
            "derived_file": str(path.relative_to(ROOT)),
            "generator": generator,
            "source_ids": source_ids,
            "row_count": row_count(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "status": status,
            "description": description,
        })

    actual = {
        p.name for p in DERIVED.iterdir()
        if p.is_file()
    }
    if actual != registered:
        raise SystemExit(
            "derived catalog mismatch: "
            f"unregistered={sorted(actual-registered)} "
            f"missing={sorted(registered-actual)}"
        )

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=list(rows[0]), lineterminator="\n"
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} artifacts")


if __name__ == "__main__":
    main()
