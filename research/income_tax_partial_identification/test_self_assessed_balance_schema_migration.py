#!/usr/bin/env python3
"""Verify semantic schema migration preserves all pre-migration numeric payloads."""
from __future__ import annotations

from pathlib import Path
import csv
import hashlib
from decimal import Decimal, InvalidOperation

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANCHORS = HERE / "self_assessed_balance_numeric_anchors.csv"

EXPECTED_TABLE22_POPULATION = 23_362_184
EXPECTED_POSITIVE_SELF_ASSESSED_BALANCE = 5_158_260
EXPECTED_REFUND = 13_527_496
EXPECTED_V2_EPSILON_STAR = 0.149015979543
EXPECTED_V3_FLOOR = 0.0868252768522
EXPECTED_V4_POINTS = 104
EXPECTED_V4_FEASIBLE = 70
EXPECTED_V4_ENDPOINTS = 5_880


def read(path: Path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def numeric_payload_fingerprint(path: Path):
    h = hashlib.sha256()
    n = 0
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for ri, row in enumerate(reader, start=1):
            for ci, cell in enumerate(row):
                s = cell.strip()
                if not s:
                    continue
                try:
                    Decimal(s)
                except InvalidOperation:
                    continue
                n += 1
                h.update(f"{ri}\t{ci}\t{s}\n".encode())
    return h.hexdigest(), n


anchors = read(ANCHORS)
assert len(anchors) == 16

for row in anchors:
    path = ROOT / row["canonical_path_after_migration"]
    assert path.exists(), path
    got_sha, got_count = numeric_payload_fingerprint(path)
    assert got_sha == row["numeric_payload_sha256_before_migration"], (
        path,
        got_sha,
        row["numeric_payload_sha256_before_migration"],
    )
    assert got_count == int(row["numeric_cell_count"]), (
        path,
        got_count,
        row["numeric_cell_count"],
    )

# Canonical schema names on the two sides of the bridge.
pseudo = read(
    ROOT / "research/income_tax_pseudofiler/pseudofiler_mtr_scenarios.csv"
)
assert "pseudo_positive_modeled_annual_income_tax_share" in pseudo[0]
assert "pseudo_filer_positive_tax_share" not in pseudo[0]

nta = read(
    ROOT
    / "data/derived/"
    "nta_income_class_primary_type_filing_status_2024.csv"
)
assert "positive_self_assessed_balance_persons" in nta[0]
assert "positive_self_assessed_balance_rate" in nta[0]
assert "positive_liability_persons" not in nta[0]
assert "positive_liability_rate" not in nta[0]

sample = read(
    ROOT
    / "data/derived/"
    "nta_positive_self_assessed_balance_income_class_primary_type_2024.csv"
)
assert "positive_self_assessed_balance_persons_estimated" in sample[0]
assert "positive_liability_persons_estimated" not in sample[0]

# Numerical anchors explicitly named in the audit.
assert sum(int(r["table22_population_persons"]) for r in nta) == EXPECTED_TABLE22_POPULATION
assert (
    sum(int(r["positive_self_assessed_balance_persons"]) for r in nta)
    == EXPECTED_POSITIVE_SELF_ASSESSED_BALANCE
)
assert sum(int(r["refund_persons"]) for r in nta) == EXPECTED_REFUND

v2 = read(HERE / "rank_bridge_lp_v2_minimum_relaxation.csv")
assert len(v2) == 1
assert abs(float(v2[0]["epsilon_star"]) - EXPECTED_V2_EPSILON_STAR) <= 1e-12

v3 = read(HERE / "rank_bridge_lp_v3_analytical_rate_floor.csv")
assert len(v3) == 1
assert (
    abs(
        float(v3[0]["unrestricted_nonnegative_rate_floor"])
        - EXPECTED_V3_FLOOR
    )
    <= 1e-12
)

v4_summary = read(HERE / "rank_epsilon_surface_v4_summary.csv")
v4_endpoints = read(HERE / "rank_epsilon_surface_v4_endpoints.csv")
assert len(v4_summary) == EXPECTED_V4_POINTS
assert sum(r["feasible"] == "True" for r in v4_summary) == EXPECTED_V4_FEASIBLE
assert len(v4_endpoints) == EXPECTED_V4_ENDPOINTS

# Active model code/specs must use the new canonical identifiers.  The audit
# and numeric-anchor files intentionally preserve the old vocabulary as
# historical migration evidence.
scan_roots = [
    ROOT / "scripts",
    ROOT / "research/income_tax_pseudofiler",
    ROOT / "research/income_tax_partial_identification",
    ROOT / "paper1",
    ROOT / "data",
    ROOT / "STATUS.adoc",
]
excluded = {
    ANCHORS.resolve(),
    (HERE / "self_assessed_balance_semantics_audit.adoc").resolve(),
    Path(__file__).resolve(),
}
legacy_tokens = (
    "positive_liability",
    "positive-liability",
    "positive liability",
    "pseudo_filer_positive_tax_share",
    "pseudo_positive_tax_share",
)
violations = []
for root in scan_roots:
    paths = [root] if root.is_file() else root.rglob("*")
    for path in paths:
        if not path.is_file() or path.resolve() in excluded:
            continue
        # Raw official evidence must remain byte-faithful to the publisher.
        # Some official CSVs are CP932 rather than UTF-8, and raw-source
        # vocabulary is not part of the repository schema migration.
        if (ROOT / "data/raw") in path.parents:
            continue
        if path.name == "MANIFEST.sha256":
            continue
        if path.suffix.lower() not in {".py", ".adoc", ".csv", ".yml", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        # One README sentence intentionally states the former field spelling.
        if path == HERE / "README.adoc":
            text = text.replace(
                "The NTA count previously labelled `positive_liability`",
                "The NTA count previously labelled LEGACY_FIELD",
            )
        for token in legacy_tokens:
            if token in text:
                violations.append((str(path.relative_to(ROOT)), token))
assert not violations, violations[:20]

print(
    "self-assessed-balance schema migration: numeric invariance OK "
    "(16 artifacts; Table 2-2(1) 23,362,184; "
    "positive self-assessed balance 5,158,260; "
    "v2/v3/v4 anchors unchanged)"
)
