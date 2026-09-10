#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import hashlib
import math

ROOT = Path(__file__).resolve().parents[1]
DETAIL = ROOT / "data/derived/estat_71911_decile_household_size_age_bridge.csv"
COMPAT = ROOT / "data/derived/income_tax_bridge_deciles_2024.csv"
RAW = ROOT / "data/raw/estat/000040490431.xlsx"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


detail = read(DETAIL)
compat = read(COMPAT)
assert len(detail) == 10, len(detail)
assert len(compat) == 10, len(compat)
assert {int(r["decile"]) for r in detail} == set(range(1, 11))
assert {int(r["decile"]) for r in compat} == set(range(1, 11))

raw_sha = sha256(RAW)
by_decile = {int(r["decile"]): r for r in detail}

for d, r in by_decile.items():
    assert r["source_id"] == "ESTAT-7191-1-2024"
    assert r["source_stat_inf_id"] == "000040490431"
    assert r["source_sha256"] == raw_sha
    assert abs(float(r["size_category_rounding_difference_persons"])) <= 1.0

    persons = [
        float(r[f"persons_size{s}"])
        for s in range(1, 6)
    ]
    p6 = float(r["persons_size6plus"])
    total_categories = sum(persons) + p6
    assert math.isclose(
        total_categories,
        float(r["sum_household_size_category_persons"]),
        abs_tol=1e-6,
    )

    hh_1_5 = sum(persons[s - 1] / s for s in range(1, 6))
    proxy6 = total_categories / (hh_1_5 + p6 / 6.0)
    proxy7 = total_categories / (hh_1_5 + p6 / 7.0)
    proxy8 = total_categories / (hh_1_5 + p6 / 8.0)
    proxy10 = total_categories / (hh_1_5 + p6 / 10.0)

    assert math.isclose(float(r["household_size_proxy"]), proxy6, rel_tol=1e-10)
    assert math.isclose(float(r["household_size_proxy_topcode6"]), proxy6, rel_tol=1e-10)
    assert math.isclose(float(r["household_size_proxy_topcode7"]), proxy7, rel_tol=1e-10)
    assert math.isclose(float(r["household_size_proxy_topcode8"]), proxy8, rel_tol=1e-10)
    assert math.isclose(float(r["household_size_proxy_topcode10"]), proxy10, rel_tol=1e-10)

    # Larger assumed size in the 6+ top-code lowers the imputed household
    # count and therefore raises the implied average household size.
    assert 1.0 < proxy6 <= proxy7 <= proxy8 <= proxy10
    assert p6 > 0

    senior = (
        float(r["age65_74_persons"])
        + float(r["age75_84_persons"])
        + float(r["age85plus_persons"])
    )
    senior_share = senior / float(r["total_persons_reported"])
    assert 0.0 <= senior_share <= 1.0
    assert math.isclose(float(r["senior_share_65p"]), senior_share, rel_tol=1e-10)

    for field in [
        "total_persons_source_cell",
        "persons_size1_source_cell",
        "persons_size2_source_cell",
        "persons_size3_source_cell",
        "persons_size4_source_cell",
        "persons_size5_source_cell",
        "persons_size6plus_source_cell",
        "age65_74_source_cell",
        "age75_84_source_cell",
        "age85plus_source_cell",
    ]:
        assert r[field], (d, field)

    assert r["household_size_proxy_status"] == "SENSITIVITY_PROXY_TOPCODE_6PLUS_AS_6"
    assert r["senior_share_status"] == "PUBLISHED_AGGREGATE_RATIO"

for c in compat:
    d = int(c["decile"])
    r = by_decile[d]
    assert c["source_sha256"] == raw_sha
    assert c["source_id"] == "ESTAT-7191-1-2024"
    for field in [
        "household_size_proxy",
        "household_size_proxy_topcode7",
        "household_size_proxy_topcode8",
        "household_size_proxy_topcode10",
        "senior_share_65p",
        "household_size_proxy_status",
        "senior_share_status",
    ]:
        assert c[field] == r[field], (d, field, c[field], r[field])
    assert c["household_size_source_cells"]
    assert c["senior_share_source_cells"]

print(
    "F71911 bridge tests: OK "
    "(10 deciles; top-code sensitivity monotone; senior shares reproduced)"
)
