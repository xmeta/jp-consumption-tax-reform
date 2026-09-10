#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    with (ROOT / rel).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha256(rel):
    h = hashlib.sha256()
    with (ROOT / rel).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


long31 = read("data/derived/estat_71531_deciles_long.csv")
meta61 = read("data/derived/estat_71561_household_types.csv")
long61 = read("data/derived/estat_71561_deciles_long.csv")
leaf = read("data/derived/income_tax_household_type_leaf_deciles_2024.csv")
suppression = read("data/derived/estat_71561_leaf_suppressed_cells.csv")

assert len(long31) == 430, len(long31)
assert len(meta61) == 49, len(meta61)
assert len(long61) == 21_070, len(long61)
assert len(leaf) == 140, len(leaf)
assert len(suppression) == 137, len(suppression)

assert {int(r["decile"]) for r in long31} == set(range(1, 11))
assert {int(r["decile"]) for r in long61} == set(range(1, 11))
assert {int(r["decile"]) for r in leaf} == set(range(1, 11))

expected_leaves = {
    "0111_無業",
    "0112_有業",
    "0121_無業",
    "0122_有業",
    "0131_有業者なし",
    "0132_有業者１人",
    "0133_有業者２人以上",
    "0141_有業者なし",
    "0142_有業者１人",
    "0143_有業者２人以上",
    "0211_無業",
    "0212_有業",
    "0221_有業者なし",
    "0222_有業者１人以上",
}
structural_leaves = {
    r["household_type"]
    for r in meta61
    if r["is_original_leaf"] == "True"
}
assert structural_leaves == expected_leaves
assert {r["household_type"] for r in leaf} == expected_leaves

# The total-household column of table 7-156-1 must reproduce the independent
# table 7-153-1 for every decile/component row, byte-for-byte at value level.
key31 = {
    (
        int(r["decile"]),
        r["reported_item"],
        r["income_component_code"],
        r["unit"],
    ): r
    for r in long31
}
total61 = [
    r for r in long61
    if r["household_type_code"] == "00"
]
assert len(total61) == 430
for r in total61:
    key = (
        int(r["decile"]),
        r["reported_item"],
        r["income_component_code"],
        r["unit"],
    )
    a = key31[key]
    assert r["raw_value"] == a["raw_value"], (
        key, a["raw_value"], r["raw_value"],
        a["source_cell"], r["source_cell"],
    )
    assert r["missing_marker"] == a["missing_marker"], key

raw31_sha = sha256("data/raw/estat/000040490416.xlsx")
raw61_sha = sha256("data/raw/estat/000040490419.xlsx")
assert {r["source_sha256"] for r in long31} == {raw31_sha}
assert {r["source_sha256"] for r in long61} == {raw61_sha}
assert {r["source_sha256"] for r in leaf} == {raw61_sha}

required_fields = [
    "household_count_approx",
    "head_wage_kY",
    "spouse_wage_kY",
    "other_member_wage_kY",
    "business_kY",
    "public_pension_kY",
    "head_public_pension_kY",
    "spouse_public_pension_kY",
    "other_member_public_pension_kY",
    "income_tax_kY",
    "public_pension_contribution_kY",
    "health_insurance_contribution_kY",
    "long_term_care_contribution_kY",
]
for r in leaf:
    for field in required_fields:
        assert r[field + "_source_cell"], (r["decile"], r["household_type"], field)

count_x = [r for r in suppression if r["field"] == "household_count_approx"]
assert len(count_x) == 11
assert {r["value_kind"] for r in count_x} == {"HOUSEHOLD_COUNT"}
assert {r["count_lower_bound"] for r in count_x} == {"0"}
assert {r["count_lower_bound_inclusive"] for r in count_x} == {"False"}
assert {r["count_upper_bound"] for r in count_x} == {"5"}
assert {r["count_upper_bound_inclusive"] for r in count_x} == {"False"}
assert {r["rule_source_id"] for r in suppression} == {"STAT-NSFCW-2024-USAGE-NOTES"}
count_x_keys = {(r["decile"], r["household_type"]) for r in count_x}
assert all((r["decile"], r["household_type"]) in count_x_keys for r in suppression)
assert sum(r["value_kind"] == "MONETARY_AMOUNT" for r in suppression) == 126

# Approximate household counts are published rounded. Their leaf partition
# should stay close to the total-household count, but exact equality is not
# required because the source labels them approximate.
for decile in range(1, 11):
    sub = [r for r in leaf if int(r["decile"]) == decile]
    markers = {r["household_count_approx_missing_marker"] for r in sub}
    assert markers <= {"", "-", "X"}
    leaf_count = sum(
        float(r["household_count_approx"])
        for r in sub
        if r["household_count_approx_missing_marker"] == ""
    )
    total_count = float(
        next(
            r["numeric_value"]
            for r in long31
            if int(r["decile"]) == decile
            and r["reported_item"] == "集計世帯数（概数）"
        )
    )
    assert abs(leaf_count - total_count) <= 20, (
        decile, leaf_count, total_count
    )

print(
    "e-Stat income-tax extract tests: OK "
    "(430 cross-table cells exact; 14 leaves; 140 leaf-decile rows; 137 X cells audited)"
)
