#!/usr/bin/env python3
from pathlib import Path
import csv
import hashlib
import math

ROOT = Path(__file__).resolve().parents[1]
P141 = ROOT / "data/derived/estat_71411_main_income_by_disposable_decile_2024.csv"
P171 = ROOT / "data/derived/estat_7171_main_income_disposable_quantiles_2024.csv"
R141 = ROOT / "data/raw/estat/000040490407.xlsx"
R171 = ROOT / "data/raw/estat/000040490427.xlsx"
STATUS = "WITHIN_NSFCW_DIAGNOSTIC_NO_NTA_CATEGORY_IDENTITY"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


r141 = read(P141)
r171 = read(P171)
assert len(r141) == 50
assert len(r171) == 30
assert {int(r["decile"]) for r in r141} == set(range(1, 11))
assert {r["semantic_key"] for r in r141} == {
    "total", "wages_salaries", "business_homework",
    "property_income", "current_transfers"
}
sha141 = sha256(R141)
sha171 = sha256(R171)

by_decile = {}
for r in r141:
    assert r["source_id"] == "ESTAT-7141-1-2024"
    assert r["source_sha256"] == sha141
    assert r["rank_concept"] == "equivalized_disposable_income_oecd_new"
    assert r["cross_system_status"] == STATUS
    assert "not asserted to equal NTA" in r["cross_system_warning"]
    assert r["source_cell"]
    by_decile.setdefault(int(r["decile"]), {})[r["semantic_key"]] = r

for d, group in by_decile.items():
    total = int(group["total"]["household_members"])
    assert total == 11_390_017
    subtotal = sum(
        int(group[k]["household_members"])
        for k in ("wages_salaries", "business_homework", "property_income", "current_transfers")
    )
    # Published category components are integer-rounded independently.
    assert abs(total - subtotal) <= 1
    for r in group.values():
        expected = int(r["household_members"]) / total
        assert math.isclose(float(r["share_of_decile_total"]), expected, rel_tol=1e-11)

assert float(by_decile[1]["current_transfers"]["share_of_decile_total"]) > 0.58
assert float(by_decile[9]["wages_salaries"]["share_of_decile_total"]) > 0.85
assert float(by_decile[1]["wages_salaries"]["share_of_decile_total"]) < 0.27
assert float(by_decile[10]["property_income"]["share_of_decile_total"]) > float(
    by_decile[9]["property_income"]["share_of_decile_total"]
)

by_key = {}
for r in r171:
    assert r["source_id"] == "ESTAT-7171-2024"
    assert r["source_sha256"] == sha171
    assert r["cross_system_status"] == STATUS
    assert "not asserted to equal NTA" in r["cross_system_warning"]
    assert r["income_concept"] == "1_等価可処分所得（ＯＥＣＤ新基準準拠）"
    assert r["source_cell"]
    by_key[(r["semantic_key"], r["measure_key"])] = r

categories = {"total", "wages_salaries", "business_homework", "property_income", "current_transfers"}
for category in categories:
    qs = [int(by_key[(category, q)]["value"]) for q in ("p10", "p25", "p50", "p75", "p90")]
    assert qs == sorted(qs), (category, qs)
    assert all(by_key[(category, q)]["unit"] == "千円" for q in ("p10", "p25", "p50", "p75", "p90"))

assert int(by_key[("total", "aggregate_households_approx")]["value"]) == 74_130
assert sum(
    int(by_key[(c, "aggregate_households_approx")]["value"])
    for c in categories - {"total"}
) == 74_130
assert int(by_key[("total", "p10")]["value"]) == 1436
assert int(by_key[("total", "p50")]["value"]) == 3037
assert int(by_key[("total", "p90")]["value"]) == 5479

print(
    "rank-bridge public diagnostic tests: OK "
    "(7-141-1: 10 deciles x 5 source groups; 7-171: 6 measures x 5 source groups; "
    "no NTA category identity imposed)"
)
