#!/usr/bin/env python3
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "data/derived/nta_withholding_salary_person_series_1991_2024.csv"
AUDIT = ROOT / "data/derived/nta_withholding_person_series_discontinuity_audit.csv"
CATALOG = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


series = read(SERIES)
audit = {r["metric_id"]: r for r in read(AUDIT)}
catalog = {r["source_id"]: r for r in read(CATALOG)}

assert len(series) == 34
assert [int(r["year"]) for r in series] == list(range(1991, 2025))

published = [r for r in series if r["person_field_status"] == "SAMPLE_SURVEY_ESTIMATE_PUBLISHED"]
missing = [r for r in series if r["person_field_status"] == "NOT_PUBLISHED"]
assert [int(r["year"]) for r in published] == list(range(1991, 2007))
assert [int(r["year"]) for r in missing] == list(range(2007, 2025))
assert len(published) == 16
assert len(missing) == 18
r2006 = next(r for r in series if r["year"] == "2006")
r2007 = next(r for r in series if r["year"] == "2007")
r2024 = next(r for r in series if r["year"] == "2024")

assert r2006["public_offices_persons_thousand"] == "9170"
assert r2006["others_persons_thousand"] == "66936"
assert r2006["public_plus_others_persons_thousand"] == "76106"
assert r2006["public_offices_salary_payment_million_yen"] == "31894770"
assert r2006["others_salary_payment_million_yen"] == "210904546"

assert r2007["public_offices_persons_thousand"] == ""
assert r2007["others_persons_thousand"] == ""
assert r2007["person_field_nature"] == "PUBLISHED_PERSON_SERIES_DISCONTINUED"

assert r2024["public_offices_persons_thousand"] == ""
assert r2024["public_offices_salary_payment_million_yen"] == "28282710"
assert r2024["others_salary_payment_million_yen"] == "325610351"

for r in published:
    assert r["person_field_nature"] == "1991_AND_LATER_PERSON_FIELDS_ARE_SAMPLE_SURVEY_ESTIMATES"
for r in missing:
    assert r["person_field_nature"] == "PUBLISHED_PERSON_SERIES_DISCONTINUED"
anchors = {
    "person_series_first_unambiguous_sample_estimate_year": "1991",
    "person_series_last_published_year": "2006",
    "person_series_first_missing_year": "2007",
    "person_series_missing_years_through_2024": "18",
    "public_offices_persons_2006": "9170",
    "others_persons_2006": "66936",
    "public_plus_others_persons_2006": "76106",
    "public_offices_person_share_2006": "0.120489843114",
    "public_offices_payment_share_2006": "0.131362684728",
    "public_offices_payment_share_2024": "0.079918803494",
    "public_payment_share_change_2006_to_2024_pp": "-5.144388123434",
    "apply_2006_public_person_share_to_2024": "PROHIBITED",
    "nta_public_offices_person_count_2024": "NOT_IDENTIFIED",
}
for key, expected in anchors.items():
    assert audit[key]["value"] == expected, (key, audit[key]["value"], expected)

assert audit["apply_2006_public_person_share_to_2024"]["identification_status"] == (
    "DO_NOT_EXTRAPOLATE_DISCONTINUED_SAMPLE_PERSON_SERIES"
)
assert audit["nta_public_offices_person_count_2024"]["identification_status"] == (
    "NTA_PUBLIC_OFFICES_PERSON_COUNT_NOT_IDENTIFIED"
)
assert audit["person_series_first_missing_year"]["identification_status"] == (
    "PUBLISHED_PERSON_SERIES_DISCONTINUED"
)
# The historical public-person share is not a current person-share estimator.
historical_share = 9170 / 76106
assert 0 < historical_share < 1
assert not any(
    r["metric_id"] == "public_offices_person_share_2024"
    for r in audit.values()
)

# The amount composition changed materially between 2006 and 2024.
share06 = 31_894_770 / (31_894_770 + 210_904_546)
share24 = 28_282_710 / (28_282_710 + 325_610_351)
assert share24 < share06
assert abs(100 * (share24 - share06) - float(
    audit["public_payment_share_change_2006_to_2024_pp"]["value"]
)) < 1e-12

hashes = {
    "NTA-WITHHOLDING-LONG-TERM":
        "21dd517e4508eb0db2d379c9ac31998f7a599161187ab27ab27b0d5b700cdef4",
    "NTA-WITHHOLDING-2006-STATUS":
        "cf6991d25fc92aee3682f8871afe005a4ff2f88bfd28e3db26c112741e7a1ff8",
    "NTA-WITHHOLDING-2007-STATUS":
        "40e96b1a88358fb31a7227c958b18f71998c3ab826e6ae27b003039cb6ef95ba",
}
for source_id, expected in hashes.items():
    assert catalog[source_id]["sha256"] == expected
subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_withholding_person_series.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA withholding person-series tests: OK "
    "(1991-2006 sample person estimates; 2007-2024 missing; "
    "2006 public=9,170k/others=66,936k; 2024 person share not identified)"
)
