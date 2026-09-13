#!/usr/bin/env python3
from __future__ import annotations

import csv, re
from pathlib import Path

if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests; assertions must remain active")

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "research/vat_compliance_productivity/nta_invoice_registry_pretrend_source_manifest_20260913.csv"
OBS = ROOT / "research/vat_compliance_productivity/nta_invoice_registry_pretrend_observations_20260913.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

manifest = read(MANIFEST)
obs = read(OBS)

assert len(manifest) == 51
full = [r for r in manifest if r["source_scope"] == "full_snapshot"]
delta_files = [r for r in manifest if r["source_scope"] == "delta_window"]
assert len(full) == 11 and len(delta_files) == 40
assert sum(int(r["bytes"]) for r in full) == 126773414
assert sum(int(r["bytes"]) for r in delta_files) == 2590592
assert {r["source_date"] for r in full} == {"2026-08-31"}
assert min(r["source_date"] for r in delta_files) == "2026-07-15"
assert max(r["source_date"] for r in delta_files) == "2026-09-10"
assert all(re.fullmatch(r"[0-9a-f]{64}", r["sha256"]) for r in manifest)

# Privacy guard: the checked-in observations contain no invoice registration numbers.
obs_text = OBS.read_text(encoding="utf-8")
assert not re.search(r"T\d{13}", obs_text)
assert len(obs) == 694
assert all(int(r["count"]) > 0 for r in obs)

history = [r for r in obs if r["component"] == "full_history_monthly"]
stock = [r for r in obs if r["component"] == "full_stock"]
daily = [r for r in obs if r["component"] == "delta_publication_daily"]
assert len(history) == 261 and len(stock) == 13 and len(daily) == 420
assert max(r["period"] for r in history) == "2026-08"
assert all(r["identification_status"] == "SURVIVING_PUBLICATION_HISTORY_EXCLUDES_DELETED_99_NOT_CAUSAL" for r in history)
assert all(r["identification_status"] == "REGISTRY_STOCK_OR_SCHEDULE_DIAGNOSTIC_NOT_CAUSAL" for r in stock)
assert all(r["identification_status"] == "PUBLICATION_CHANGE_FLOW_NOT_EFFECTIVE_EVENT_NOT_CAUSAL" for r in daily)
assert min(r["period"] for r in daily) == "2026-07-15"
assert max(r["period"] for r in daily) == "2026-09-10"
assert sum(int(r["count"]) for r in daily) == 78216
assert any(r["event_type"] == "deletion" for r in daily)

stock_index = {(r["entity_type"], r["event_type"]): int(r["count"]) for r in stock}
assert stock_index[("corporation", "active_as_of_snapshot")] == 2479965
assert stock_index[("individual", "active_as_of_snapshot")] == 2295687
assert stock_index[("unincorporated_association", "active_as_of_snapshot")] == 6820
assert stock_index[("corporation", "future_registration_after_snapshot")] == 3330
assert stock_index[("individual", "future_registration_after_snapshot")] == 6285
assert stock_index[("individual", "future_expiration_after_snapshot")] == 15105

print("NTA invoice-registry pretrend snapshot tests: OK (51 source ZIPs; 694 privacy-safe aggregate rows; no registration identifiers; descriptive only)")
