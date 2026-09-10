#!/usr/bin/env python3
"""Freeze the v5 pre-specification across implementation and Paper promotion.

The original fef4776 version required that no implementation or v5 result
existed.  The implementation commit 006e259 still kept Paper 1 at 16 claims.
Git history preserves both gates.  The current promoted state keeps the exact
pre-specification bytes frozen while requiring the later, separately promoted
P1-C17 claim to retain its model-contingent status.
"""

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import hashlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CONFIG = HERE / "rank_one_sided_bridge_v5_config.csv"
SPEC = HERE / "rank_one_sided_bridge_v5_spec.adoc"
CLAIMS = ROOT / "data/claim_graph.csv"

PRESPEC_COMMIT = "fef477667816e1f95b6c532add770ac85675204b"
SPEC_SHA256 = "8c9459cafcc0c18c68666da0492c13fa4b70e68868fd8585a703709f798254f0"
CONFIG_SHA256 = "923eade3ebe1fdfd7974e23186d6bfdabb0385db61a7c9da81979b0d9b268be8"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


assert sha256(SPEC) == SPEC_SHA256
assert sha256(CONFIG) == CONFIG_SHA256

text = SPEC.read_text(encoding="utf-8")
assert "PRESPECIFIED_NO_V5_RESULT" in text
assert "no v5 solver has been implemented" in text
assert "no v5 frontier has been computed" in text
assert "no zero-violation threshold has been computed" in text
assert "no v5 MTR endpoint has been computed" in text

cfg = {r["key"]: r["value"] for r in read_csv(CONFIG)}
assert cfg["delta_grid"] == "0;0.25;0.5;1;2;3;4;5"
assert cfg["directional_constraint"] == (
    "transported_nta_positive_balance_minus_pseudo_calculated_tax_positive_le_eta"
)
assert cfg["solver_method"] == "highs-ds"
assert cfg["solver_crosscheck_method"] == "highs-ipm"
assert cfg["paper1_claim_before_ci"] == "false"
assert cfg["paper1_claim_before_separate_promotion"] == "false"

claims = [r for r in read_csv(CLAIMS) if r["product_id"] == "paper1"]
assert len(claims) == 17
by_id = {r["claim_id"]: r for r in claims}
assert by_id["P1-C17"]["empirical_status"] == (
    "MODEL_CONTINGENT_RANK_ONE_SIDED_BRIDGE_REPRODUCED"
)
assert by_id["P1-C17"]["source"] == (
    "research/income_tax_partial_identification/rank_one_sided_bridge_v5_spec.adoc"
)
assert "eta=0 proves" in by_id["P1-C17"]["forbidden_claim"].lower()
assert "v3/v4 symmetric discrepancy results are invalid" in (
    by_id["P1-C17"]["forbidden_claim"].lower()
)

print(
    "rank one-sided bridge v5 pre-specification freeze: OK "
    f"(commit={PRESPEC_COMMIT[:7]}; exact spec/config SHA-256; "
    "separate P1-C17 promotion retained)"
)
