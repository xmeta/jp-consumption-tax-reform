#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ROWS = ROOT / "data/derived/nta_salary_processing_status_2024.csv"
AUDIT = ROOT / "data/derived/nta_salary_processing_status_audit_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(ROWS)
by_status = {r["processing_status"]: r for r in rows}
audit = {r["metric_id"]: r for r in read(AUDIT)}
catalog = {r["source_id"]: r for r in read(CATALOG)}

assert len(rows) == 6
assert set(by_status) == {
    "final_return",
    "amended_return",
    "determination_or_correction_increase",
    "correction_for_reduction",
    "request_for_correction",
    "total_actual",
}
anchors = {
    "final_return": (11_293_442, 2_352_779, 7_612_961),
    "amended_return": (81_481, 21_221, 50_210),
    "determination_or_correction_increase": (8_591, 2_275, 4_868),
    "correction_for_reduction": (10_703, 2_103, 7_736),
    "request_for_correction": (29_370, 7_348, 21_243),
    "total_actual": (11_423_587, 2_385_726, 7_697_018),
}
for key, expected in anchors.items():
    r = by_status[key]
    actual = (
        int(r["persons"]),
        int(r["positive_self_assessed_balance_persons"]),
        int(r["refund_persons"]),
    )
    assert actual == expected, (key, actual, expected)

components = [k for k in anchors if k != "total_actual"]
for field in ("persons", "positive_self_assessed_balance_persons", "refund_persons"):
    assert sum(int(by_status[k][field]) for k in components) == int(by_status["total_actual"][field])

assert int(by_status["total_actual"]["persons"]) - int(by_status["final_return"]["persons"]) == 130_145
assert int(by_status["total_actual"]["positive_self_assessed_balance_persons"]) - int(
    by_status["final_return"]["positive_self_assessed_balance_persons"]
) == 32_947
assert int(by_status["total_actual"]["refund_persons"]) - int(
    by_status["final_return"]["refund_persons"]
) == 84_057
metric_anchors = {
    "salary_table22_filed_or_processed_population": "11423587",
    "salary_final_return_row_population": "11293442",
    "salary_post_final_return_processing_population": "130145",
    "salary_post_final_return_processing_share": "0.011392656265",
    "salary_final_return_row_share": "0.988607343735",
    "salary_total_positive_self_assessed_balance": "2385726",
    "salary_final_return_row_positive_self_assessed_balance": "2352779",
    "salary_post_final_return_positive_self_assessed_balance": "32947",
    "salary_total_refund": "7697018",
    "salary_final_return_row_refund": "7612961",
    "salary_post_final_return_refund": "84057",
    "salary_total_neither_positive_nor_refund": "1340843",
    "salary_final_return_row_neither_positive_nor_refund": "1327702",
    "salary_post_final_return_neither_positive_nor_refund": "13141",
    "salary_primary_final_return_population_alias": "11423587",
}
for key, expected in metric_anchors.items():
    assert audit[key]["value"] == expected, (key, audit[key]["value"], expected)

assert audit["salary_table22_filed_or_processed_population"]["identification_status"] == (
    "CANONICAL_TABLE22_FILED_OR_PROCESSED_POPULATION"
)
assert audit["salary_final_return_row_population"]["identification_status"] == (
    "OBSERVED_FINAL_RETURN_ROW"
)
assert audit["salary_primary_final_return_population_alias"]["identification_status"] == (
    "DEPRECATED_ALIAS_NOT_PURE_FINAL_RETURN_ROW"
)

assert abs(
    float(audit["salary_post_final_return_processing_share"]["value"])
    + float(audit["salary_final_return_row_share"]["value"])
    - 1.0
) < 1e-12
# The backward-compatible 11,423,587 label must never be equated with the pure
# Final return row.
assert audit["salary_primary_final_return_population_alias"]["value"] != audit[
    "salary_final_return_row_population"
]["value"]

assert catalog["NTA-2024-PROCESSING-STATUS"]["sha256"] == (
    "e8a10581e2167eb9b39a1d84056d2b561250c914cde0dc509ed2c356cfce8351"
)

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_salary_processing_status.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA salary processing-status tests: OK "
    "(final-return row=11,293,442; later processing=130,145; "
    "filed/processed total=11,423,587)"
)
