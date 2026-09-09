#!/usr/bin/env python3
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ROWS = ROOT / "data/derived/nta_final_return_submission_processing_reconciliation_2024.csv"
AUDIT = ROOT / "data/derived/nta_final_return_processing_semantics_audit_2024.csv"
CATALOG = ROOT / "data/source_catalog.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(ROWS)
by = {r["income_category"]: r for r in rows}
audit = {r["metric_id"]: r for r in read(AUDIT)}
catalog = {r["source_id"]: r for r in read(CATALOG)}

assert len(rows) == 6
assert set(by) == {"all", "business", "real_estate", "salary", "miscellaneous", "other"}

press = {
    "all": (23389, 5175, 13533, 4681),
    "business": (3789, 1180, 963, 1645),
    "real_estate": (1497, 806, 174, 516),
    "salary": (11442, 2389, 7711, 1343),
    "miscellaneous": (5825, 417, 4292, 1116),
    "other": (837, 382, 394, 61),
}
final = {
    "all": (23090075, 5067037, 13386611, 4636427),
    "business": (3730986, 1145782, 951155, 1634049),
    "real_estate": (1476174, 789809, 172155, 514210),
    "salary": (11293442, 2352779, 7612961, 1327702),
    "miscellaneous": (5765807, 404043, 4261066, 1100698),
    "other": (823666, 374624, 389274, 59768),
}
processed = {
    "all": (23362184, 5158260, 13527496, 4676428),
    "business": (3785184, 1174065, 962359, 1648760),
    "real_estate": (1497102, 804398, 174282, 518422),
    "salary": (11423587, 2385726, 7697018, 1340843),
    "miscellaneous": (5819853, 411376, 4300467, 1108010),
    "other": (836458, 382695, 393370, 60393),
}

for category in by:
    r = by[category]
    assert tuple(int(r[k]) for k in [
        "press_submitted_return_thousand_displayed",
        "press_positive_thousand_displayed",
        "press_refund_thousand_displayed",
        "press_zero_thousand_displayed",
    ]) == press[category]
    assert tuple(int(r[k]) for k in [
        "table21_final_return_row_persons_exact",
        "table21_final_return_row_positive_persons_exact",
        "table21_final_return_row_refund_persons_exact",
        "table21_final_return_row_zero_persons_exact",
    ]) == final[category]
    assert tuple(int(r[k]) for k in [
        "table21_filed_or_processed_persons_exact",
        "table21_filed_or_processed_positive_persons_exact",
        "table21_filed_or_processed_refund_persons_exact",
        "table21_filed_or_processed_zero_persons_exact",
    ]) == processed[category]
    assert r["comparison_status"] == "DISTINCT_PUBLICATION_POPULATION_AND_REFERENCE_DATE"
    assert "descriptive only" in r["interpretation"]
assert by["all"]["press_display_center_minus_final_row_persons"] == "298925"
assert by["all"]["press_display_center_minus_processed_total_persons"] == "26816"
assert by["salary"]["press_display_center_minus_final_row_persons"] == "148558"
assert by["salary"]["press_display_center_minus_processed_total_persons"] == "18413"

assert audit["stage1_table21_final_return_processing_row"]["value"] == "23090075"
assert audit["press_submitted_return_count_displayed"]["value"] == "23389"
assert audit["table21_filed_or_processed_total"]["value"] == "23362184"
assert audit["salary_press_submitted_return_count_displayed"]["value"] == "11442"
assert audit["salary_table21_final_return_processing_row"]["value"] == "11293442"
assert audit["press_and_table21_final_row_same_statistical_object"]["value"] == "NO"
assert audit["press_vs_table21_category_definition_equivalence"]["value"] == "NOT_ESTABLISHED"
assert audit["press_vs_table21_difference_mechanism"]["value"] == "NOT_IDENTIFIED"
assert audit["stage1_23090075_numerical_change_required"]["value"] == "NO"
assert audit["stage1_23090075_wording_change_required"]["value"] == "YES"

assert audit["stage1_table21_final_return_processing_row"]["identification_status"] == (
    "OBSERVED_TABLE21_FINAL_RETURN_PROCESSING_ROW"
)
assert audit["press_and_table21_final_row_same_statistical_object"]["identification_status"] == (
    "DISTINCT_PUBLICATION_POPULATION_AND_REFERENCE_DATE"
)
assert audit["stage1_23090075_numerical_change_required"]["identification_status"] == (
    "RETAIN_AS_PROCESSING_ROW_BENCHMARK"
)

assert catalog["NTA-2024-RETURN-PRESS-T31"]["sha256"] == (
    "54f30a1f26da7e93c42a0d5255ad3825d6df578321dd65fc9099d435698c4978"
)
assert catalog["NTA-2024-PROCESSING-STATUS"]["sha256"] == (
    "e8a10581e2167eb9b39a1d84056d2b561250c914cde0dc509ed2c356cfce8351"
)

# Guard the core semantic mistake: the exact Table 2-1 Final return processing
# row must not be silently substituted for the press-release submitted-return count.
assert int(audit["stage1_table21_final_return_processing_row"]["value"]) != (
    int(audit["press_submitted_return_count_displayed"]["value"]) * 1000
)

subprocess.run(
    [sys.executable, str(ROOT / "scripts/extract_nta_final_return_processing_reconciliation.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "NTA final-return processing reconciliation tests: OK "
    "(press=23,389k displayed; Table 2-1 Final-return row=23,090,075; "
    "filed/processed total=23,362,184; distinct statistical objects)"
)
