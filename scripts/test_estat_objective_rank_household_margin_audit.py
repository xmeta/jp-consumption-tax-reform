#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data/derived/estat_objective_rank_household_margin_source_matrix_2024.csv"
AUDIT = ROOT / "data/derived/estat_objective_rank_household_margin_identification_audit_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(MATRIX)
audit = {r["metric_id"]: r for r in read(AUDIT)}
catalog = {r["source_id"]: r for r in read(CATALOG)}

assert len(rows) == 7
assert audit["examined_official_source_families"]["value"] == "7"
assert audit["annual_income_household_population_margin_available"]["value"] == "YES_5355441_PER_DECILE"
assert audit["objective_rank_population_person_margin_available"]["value"] == "YES_11390017_PER_DECILE"
assert audit["objective_rank_approx_sample_household_count_available"]["value"] == "YES_SUM_74150"
assert audit["objective_rank_population_household_margin_available"]["value"] == "NO_IN_EXAMINED_OFFICIAL_SOURCE_FAMILIES"
assert audit["same_unit_household_transport_margins_identified"]["value"] == "NO"
assert audit["frechet_household_rank_transport_status"]["value"] == "BLOCKED_NO_OBJECTIVE_RANK_HOUSEHOLD_POPULATION_MARGIN"
assert audit["same_rank_mapping_status"]["value"] == "PROHIBITED_WITHOUT_EVIDENCE"
assert audit["person_decile_as_household_margin_status"]["value"] == "PROHIBITED"
assert audit["independent_rank_coupling_status"]["value"] == "NOT_ADOPTED"
assert audit["vat_gini_fgt2_objective_rank_effect_status"]["value"] == "NOT_IDENTIFIED"
assert "does not claim" in audit["objective_rank_population_household_margin_available"]["note"]

by_table = {r["table_number"]: r for r in rows}
assert by_table["1-21"]["rank_concept"] == "HOUSEHOLD_ANNUAL_INCOME_DECILE"
assert by_table["1-21"]["statistical_unit"] == "HOUSEHOLD"
assert by_table["1-21"]["population_household_margin"] == "YES_5355441_PER_DECILE"
assert by_table["7-141-1"]["rank_is_objective"] == "YES"
assert by_table["7-141-1"]["statistical_unit"] == "HOUSEHOLD_MEMBER"
assert by_table["7-141-1"]["population_person_margin"] == "YES_11390017_PER_DECILE"
assert by_table["7-153-1"]["population_household_margin"] == "NO"
assert by_table["7-153-1"]["approx_sample_household_margin"] == "YES_SUM_74150"
assert by_table["7-156-1"]["approx_sample_household_margin"] == "YES_TOTAL_HOUSEHOLD_TYPE_SUM_74150"
assert by_table["7-142-1-2"]["rank_is_objective"] == "YES"
assert by_table["7-142-1-2"]["population_household_margin"] == "NO"
assert by_table["7-145-1"]["rank_is_objective"] == "YES"
assert by_table["7-145-1"]["population_household_margin"] == "NO"
assert by_table["7-62-1"]["rank_is_objective"] == "NO"
assert by_table["7-62-1"]["population_household_margin"] == "YES_PUBLISHED_HOUSEHOLD_DISTRIBUTION"
assert by_table["7-62-1"]["usable_as_objective_rank_household_margin"] == "NO_WRONG_RANK"

expected_hashes = {
    "ESTAT-7142-1-2-2024-DBVIEW": "5919ba3a9ce4b6d8d11e1b43930ae5af86bbd970225fbfaabc1aa85901d12544",
    "ESTAT-7145-1-2024-DBVIEW": "37dea334e8dee15a8c9364251c10ffcda8f16c521cd38bea27f8e46e3f9683a2",
    "ESTAT-762-1-2024-DBVIEW": "690dbe37398555c1c30e8384069a5f00cbcf31e544c05533634b86eba3aa1cfb",
}
for sid, expected in expected_hashes.items():
    assert catalog[sid]["sha256"] == expected
    assert (ROOT / catalog[sid]["raw_file"]).exists()

# Guard the tempting invalid mappings explicitly.
assert not any(
    r["rank_is_objective"] == "YES"
    and r["population_household_margin"].startswith("YES")
    for r in rows
)
assert not any(
    r["rank_is_objective"] == "YES"
    and r["statistical_unit"] == "HOUSEHOLD"
    for r in rows
)

subprocess.run(
    [sys.executable, str(ROOT / "scripts/build_estat_objective_rank_household_margin_audit.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NSFCW objective-rank household-margin audit tests: OK "
    "(7 source families; household-unit transport remains blocked)"
)
