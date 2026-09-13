#!/usr/bin/env python3
"""Validate Issue #121 policy-event timing metadata and provenance."""

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "data/policy/tax_events.csv"
CATALOG = ROOT / "data/source_catalog.csv"

with EVENTS.open(encoding="utf-8", newline="") as f:
    events = list(csv.DictReader(f))
with CATALOG.open(encoding="utf-8", newline="") as f:
    sources = {row["source_id"]: row for row in csv.DictReader(f)}

expected = [
    ("1989-04-01", "vat_introduction", "NTA-CONSUMPTION-TAX-1989-START"),
    ("1997-04-01", "vat_rate_increase", "NTA-70YEAR-CONSUMPTION-TAX-HISTORY"),
    ("2014-04-01", "vat_rate_increase", "NTA-70YEAR-CONSUMPTION-TAX-HISTORY"),
    ("2019-10-01", "vat_rate_increase", "NTA-70YEAR-CONSUMPTION-TAX-HISTORY"),
    ("2023-10-01", "invoice_system_introduction", "NTA-70YEAR-CONSUMPTION-TAX-HISTORY"),
]
assert [(r["event_date"], r["event_type"], r["source_id"]) for r in events] == expected
assert all(r["source_id"] in sources for r in events)
assert all(sources[r["source_id"]]["status"].startswith("RAW_OFFICIAL") for r in events)
print("macro policy-event metadata: OK (5 official event markers; timing only, no causal promotion)")
