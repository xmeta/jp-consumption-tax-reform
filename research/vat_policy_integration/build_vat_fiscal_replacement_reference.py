#!/usr/bin/env python3
"""Build a static VAT fiscal replacement reference from official MOF receipts."""
from pathlib import Path
from html.parser import HTMLParser
import argparse
import csv
import io

ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "data/source_catalog.csv"
SCENARIOS = ROOT / "research/vat_policy_integration/scenarios.csv"
OUT_METRICS = ROOT / "data/derived/vat_fiscal_receipt_reference.csv"
OUT_SCENARIOS = ROOT / "data/derived/vat_policy_fiscal_replacement_reference.csv"
SOURCE_ID = "MOF-FY2024-TREASURY-REVENUE-2025-07"
EXPECTED_SHA = "20670bb317eeef1e69a8a910cb43efc50b7df7ae58c6324a23909c7433f1c243"


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_cell = False
        self.cell = []
        self.row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag in ("td", "th"):
            self.in_cell = True
            self.cell = []
    def handle_data(self, data):
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell:
            self.row.append(" ".join("".join(self.cell).split()))
            self.in_cell = False
        if tag == "tr" and self.row:
            self.rows.append(self.row)


def parse_int(text):
    return int(text.replace(",", "").replace("△", "").strip())


def build():
    catalog = {r["source_id"]: r for r in read_csv(CAT)}
    source = catalog[SOURCE_ID]
    assert source["sha256"] == EXPECTED_SHA
    raw = (ROOT / source["raw_file"]).read_text(encoding="utf-8")

    for token in ("令和6年度", "令和7年7月末", "単位", "千円"):
        assert token in raw

    parser = TableParser()
    parser.feed(raw)
    tax_row = next(r for r in parser.rows if "租税" in r and "消費税" not in r)
    vat_row = next(r for r in parser.rows if "消費税" in r)

    assert tax_row[1] == "租税"
    assert vat_row[0] == "消費税"
    total_tax_k_yen = parse_int(tax_row[5])
    vat_k_yen = parse_int(vat_row[4])
    vat_budget_k_yen = parse_int(vat_row[1])
    vat_budget_gap_k_yen = parse_int(vat_row[5])
    assert vat_row[6] == "102.7"
    total_tax_yen = total_tax_k_yen * 1000
    vat_yen = vat_k_yen * 1000
    metrics = [
        {
            "metric_id": "fy2024_total_tax_receipts_yen",
            "value": str(total_tax_yen),
            "unit": "yen",
            "source_id": SOURCE_ID,
            "source_locator": "general-account revenue table; tax row; receipts total",
            "identification_status": "OBSERVED_CENTRAL_GOVERNMENT_CASH_RECEIPTS",
            "model_use": "FISCAL_SCALE_REFERENCE_ONLY",
            "note": "FY2024 treasury receipts recorded through end-July 2025; not general-government revenue and not a behavioral counterfactual.",
        },
        {
            "metric_id": "fy2024_consumption_tax_receipts_yen",
            "value": str(vat_yen),
            "unit": "yen",
            "source_id": SOURCE_ID,
            "source_locator": "general-account revenue table; consumption-tax row; receipts total",
            "identification_status": "OBSERVED_CENTRAL_GOVERNMENT_CASH_RECEIPTS",
            "model_use": "STATIC_VAT_REPLACEMENT_SCALE_REFERENCE",
            "note": "Observed cash receipts, not the causal revenue loss from a reform after behavioral, timing, price, import or macro responses.",
        },
        {
            "metric_id": "fy2024_consumption_tax_budget_yen",
            "value": str(vat_budget_k_yen * 1000),
            "unit": "yen",
            "source_id": SOURCE_ID,
            "source_locator": "general-account revenue table; consumption-tax row; revenue budget",
            "identification_status": "OBSERVED_BUDGET_REFERENCE",
            "model_use": "FISCAL_CONTEXT_ONLY",
            "note": "Budget amount, distinct from realized receipts.",
        },
        {
            "metric_id": "fy2024_consumption_tax_receipts_minus_budget_yen",
            "value": str(vat_budget_gap_k_yen * 1000),
            "unit": "yen",
            "source_id": SOURCE_ID,
            "source_locator": "general-account revenue table; consumption-tax row; receipts minus budget",
            "identification_status": "OBSERVED_BUDGET_EXECUTION_DIFFERENCE",
            "model_use": "FISCAL_CONTEXT_ONLY",
            "note": "Observed receipts exceed the recorded budget by this amount.",
        },
        {
            "metric_id": "fy2024_consumption_tax_share_of_total_tax_receipts",
            "value": f"{vat_yen / total_tax_yen:.12f}".rstrip("0").rstrip("."),
            "unit": "ratio",
            "source_id": SOURCE_ID,
            "source_locator": "derived from consumption-tax and total-tax receipt rows",
            "identification_status": "DERIVED_OBSERVED_RECEIPT_SHARE",
            "model_use": "FISCAL_SCALE_REFERENCE_ONLY",
            "note": "Central-government cash-receipt composition; not tax incidence or welfare burden.",
        },
    ]

    scenarios = read_csv(SCENARIOS)
    scenario_rows = []
    full_gap = {"zero_rate_admin_retained", "full_abolition",
                "full_abolition_jgb", "full_abolition_income_tax",
                "full_abolition_asset_tax", "full_abolition_mixed"}
    for s in scenarios:
        sid = s["scenario_id"]
        if sid == "current_8_10":
            receipt_effect = "0"
            replacement = "0"
            status = "BASELINE_ZERO_STATIC_RECEIPT_CHANGE"
        elif sid == "reduced_5":
            receipt_effect = ""
            replacement = ""
            status = "NOT_IDENTIFIED_RATE_BASE_MIX_AND_BEHAVIOR_REQUIRED"
        elif sid in full_gap:
            receipt_effect = str(-vat_yen)
            replacement = str(vat_yen)
            status = "STATIC_FULL_VAT_RECEIPT_REMOVAL_REFERENCE_NOT_BEHAVIORAL_FORECAST"
        else:
            raise AssertionError(sid)

        jgb = str(vat_yen) if sid == "full_abolition_jgb" else ""
        replacement_tax = str(vat_yen) if sid in {
            "full_abolition_income_tax", "full_abolition_asset_tax", "full_abolition_mixed"
        } else ""
        scenario_rows.append({
            "scenario_id": sid,
            "fy2024_consumption_tax_receipts_reference_yen": str(vat_yen),
            "static_consumption_tax_receipt_effect_yen": receipt_effect,
            "gross_replacement_requirement_reference_yen": replacement,
            "full_jgb_financing_reference_yen": jgb,
            "replacement_tax_target_reference_yen": replacement_tax,
            "fiscal_reference_status": status,
            "source_id": SOURCE_ID,
            "note": "Static central-government cash-receipt reference. It does not include behavioral/base changes, local consumption tax, expenditure changes, interest, macro feedback or general-government consolidation.",
        })
    return metrics, scenario_rows
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    metrics, scenarios = build()
    outputs = [(OUT_METRICS, render(metrics)), (OUT_SCENARIOS, render(scenarios))]
    if args.check:
        stale = [
            str(path.relative_to(ROOT))
            for path, expected in outputs
            if not path.exists() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            raise SystemExit("stale generated artifacts: " + ", ".join(stale))
        print(
            "VAT fiscal replacement reference: current "
            "(FY2024 consumption-tax cash receipts + 8-scenario static replacement mapping)"
        )
    else:
        for path, expected in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
            print(
                f"wrote {path.relative_to(ROOT)}: "
                f"{len(metrics) if path == OUT_METRICS else len(scenarios)} rows"
            )


if __name__ == "__main__":
    main()
