#!/usr/bin/env python3
"""Build Japan VAT pass-through/base/quantity evidence without policy extrapolation."""
from pathlib import Path
import argparse, csv, io
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data/source_catalog.csv"
OUT = ROOT / "data/derived/vat_pass_through_evidence.csv"
EXPECTED = {
    "JSTAGE-SHIRAISHI-2016-VAT-PASS-THROUGH-POS": "23b7fb786fa7b563a142a31af82c952314154661ca21411c44428612570e8b77",
    "BOJ-OUTLOOK-2019-07-CONSUMPTION-TAX": "5aceffc5a8d4c459a2cd2952aeb017bb71c6bd7a3b01b6e2a0d533b1e2488b32",
    "CAO-2014-CONSUMPTION-TAX-DEMAND": "4707c274068e22b7d351ed968e92f1c9cbdfb29a4a28f22ff93a40b468b19a22",
    "MOF-2019-CONSUMPTION-TAX-HIKE": "8824d30b2fb4ce1be09a9089215a4c0519fb3a70d92790223e763dde2c579a73",
}

def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def render(rows):
    b = io.StringIO(); w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader(); w.writerows(rows); return b.getvalue()

def require(text, tokens, label):
    for token in tokens:
        if token not in text:
            raise RuntimeError(f"{label}: missing token {token!r}")

def build():
    cat = {r["source_id"]: r for r in read_csv(CAT)}
    for sid, sha in EXPECTED.items():
        if sid not in cat or cat[sid]["sha256"] != sha:
            raise RuntimeError(f"{sid}: missing or unexpected source hash")

    pdf = PdfReader(ROOT / cat["JSTAGE-SHIRAISHI-2016-VAT-PASS-THROUGH-POS"]["raw_file"])
    if len(pdf.pages) != 29:
        raise RuntimeError("Shiraishi 2016: unexpected page count")
    summary = pdf.pages[-1].extract_text() or ""
    require(summary, ["Pass Through in Value Added Tax", "over-and under-shifting", "extent of pass through", "market structure"], "Shiraishi 2016 summary")

    boj = (ROOT / cat["BOJ-OUTLOOK-2019-07-CONSUMPTION-TAX"]["raw_file"]).read_text(encoding="utf-8")
    require(boj, ["fully passed on to prices of taxable items", "front-loaded increase and subsequent decline in demand", "decline in real income"], "BOJ July 2019")
    cao = (ROOT / cat["CAO-2014-CONSUMPTION-TAX-DEMAND"]["raw_file"]).read_text(encoding="utf-8")
    require(cao, ["2.5～3.3兆円程度", "実質GDPの0.5～0.6％程度", "異時点間で発生する支出の代替効果"], "CAO 2014")
    mof = (ROOT / cat["MOF-2019-CONSUMPTION-TAX-HIKE"]["raw_file"]).read_text(encoding="utf-8")
    require(mof, ["The Standard Rate of Consumption Tax: 10%", "Reduced Tax Rate System", "Foods and beverages with the exception of liquors and eating-out", "Subscribed newspapers issued twice or more per week"], "MOF 2019")

    common_transfer = "HISTORICAL_RATE_INCREASE_EVIDENCE_NOT_RATE_CUT_OR_ABOLITION_PARAMETER"
    rows = [
        {"evidence_id":"PT-2014-POS-HETEROGENEITY","evidence_dimension":"PRICE_PASS_THROUGH","event_period":"2014-04","policy_change":"VAT 5% to 8%","market_scope":"supermarket consumer goods / POS regular and sale prices","method":"item-level POS analysis and regressions","pass_through_point":"","pass_through_unit":"","quantity_effect_low":"","quantity_effect_high":"","quantity_effect_unit":"","identification_status":"OBSERVED_HISTORICAL_MICRO_HETEROGENEITY","policy_transfer_status":common_transfer,"vat_base_status":"2014_TAXABLE_RETAIL_GOODS_STUDY_SCOPE_NOT_HOUSEHOLD_BASE_SHARE","quantity_response_status":"NOT_ESTIMATED_IN_THIS_EVIDENCE_ROW","source_ids":"JSTAGE-SHIRAISHI-2016-VAT-PASS-THROUGH-POS","source_locator":"article pp.119-146; English summary p.29","note":"Many items passed through the 2014 increase, but pass-through differed across goods and both under- and over-shifting occurred. No uniform household pass-through coefficient is promoted."},
        {"evidence_id":"PT-2019-BOJ-FULL-PASS-THROUGH-ASSUMPTION","evidence_dimension":"PRICE_PASS_THROUGH","event_period":"2019-10","policy_change":"VAT standard rate 8% to 10%","market_scope":"taxable CPI items excluding reduced-rate items","method":"BOJ mechanical forecast assumption","pass_through_point":"1","pass_through_unit":"assumed_fraction_of_tax_change_passed_to_taxable_item_prices","quantity_effect_low":"","quantity_effect_high":"","quantity_effect_unit":"","identification_status":"MECHANICAL_ASSUMPTION_NOT_EMPIRICAL_ESTIMATE","policy_transfer_status":"DO_NOT_TREAT_FULL_PASS_THROUGH_ASSUMPTION_AS_OBSERVED_OR_ABOLITION_PARAMETER","vat_base_status":"STANDARD_RATE_TAXABLE_ITEMS_EXCLUDING_REDUCED_RATE","quantity_response_status":"NOT_ESTIMATED_IN_THIS_EVIDENCE_ROW","source_ids":"BOJ-OUTLOOK-2019-07-CONSUMPTION-TAX","source_locator":"July 2019 Outlook footnote 6","note":"BOJ assumed full pass-through for taxable items when mechanically estimating the direct CPI effect; this is an assumption, not an empirical pass-through estimate."},
        {"evidence_id":"QR-2019-BOJ-DEMAND-CHANNELS","evidence_dimension":"QUANTITY_RESPONSE","event_period":"2019-10","policy_change":"VAT standard rate 8% to 10% with reduced rate","market_scope":"aggregate Japanese demand","method":"BOJ outlook channel decomposition","pass_through_point":"","pass_through_unit":"","quantity_effect_low":"","quantity_effect_high":"","quantity_effect_unit":"","identification_status":"OFFICIAL_OUTLOOK_CHANNEL_DECOMPOSITION","policy_transfer_status":common_transfer,"vat_base_status":"REDUCED_RATE_PRESENT","quantity_response_status":"FRONTLOAD_THEN_DECLINE_PLUS_REAL_INCOME_CHANNEL_NOT_STRUCTURAL_ELASTICITY","source_ids":"BOJ-OUTLOOK-2019-07-CONSUMPTION-TAX","source_locator":"July 2019 Outlook footnotes 2-3","note":"BOJ separated front-loaded demand/subsequent decline from the real-income channel. This does not identify a steady-state quantity elasticity for a VAT cut or abolition."},
        {"evidence_id":"QR-2014-CAO-FRONTLOAD-REBOUND","evidence_dimension":"QUANTITY_RESPONSE","event_period":"2013-2014","policy_change":"VAT 5% to 8%","market_scope":"aggregate private consumption","method":"Cabinet Office ex-post intertemporal-substitution estimate","pass_through_point":"","pass_through_unit":"","quantity_effect_low":"2500000000000","quantity_effect_high":"3300000000000","quantity_effect_unit":"yen_intertemporal_consumption_shift","identification_status":"OFFICIAL_EX_POST_INTERTEMPORAL_SHIFT_ESTIMATE","policy_transfer_status":common_transfer,"vat_base_status":"AGGREGATE_CONSUMPTION_NOT_VAT_BASE_DECOMPOSITION","quantity_response_status":"TEMPORARY_FRONTLOAD_AND_REBOUND_NOT_STEADY_STATE_ELASTICITY","source_ids":"CAO-2014-CONSUMPTION-TAX-DEMAND","source_locator":"2014 Japanese Economy, ch.1 sec.1, Table 1-1-4 discussion","note":"Cabinet Office estimated 2014 front-loading and rebound at 2.5-3.3 trillion yen, about 0.5-0.6% of real GDP; this is timing substitution around a tax increase, not a persistent demand multiplier."},
        {"evidence_id":"BASE-2019-MOF-RATE-SCOPE","evidence_dimension":"VAT_BASE_RULE","event_period":"2019-10 onward","policy_change":"standard 10%, reduced 8%","market_scope":"statutory consumption-tax rate scope","method":"official statutory-policy description","pass_through_point":"","pass_through_unit":"","quantity_effect_low":"","quantity_effect_high":"","quantity_effect_unit":"","identification_status":"OBSERVED_STATUTORY_SCOPE","policy_transfer_status":"NOT_A_BEHAVIORAL_PARAMETER","vat_base_status":"STANDARD_AND_REDUCED_RATE_SCOPE_RULE_IDENTIFIED_HOUSEHOLD_EXPENDITURE_SHARES_NOT_IDENTIFIED","quantity_response_status":"NOT_APPLICABLE","source_ids":"MOF-2019-CONSUMPTION-TAX-HIKE","source_locator":"Reduced Tax Rate System section","note":"Reduced 8% applies to specified food/beverages excluding liquor and dining out, and qualifying subscribed newspapers; category rules do not identify decile-specific taxable expenditure shares."},
    ]
    return rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); args = ap.parse_args()
    text = render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            raise SystemExit("stale generated artifact: " + str(OUT.relative_to(ROOT)))
        print("VAT pass-through evidence: current (5 evidence rows; empirical, mechanical, base and quantity channels separated)")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}: 5 rows")

if __name__ == "__main__": main()
