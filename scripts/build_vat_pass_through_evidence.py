#!/usr/bin/env python3
"""Build Japan VAT pass-through/base/quantity evidence without policy extrapolation."""
from pathlib import Path
import argparse, csv, html, io, re
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data/source_catalog.csv"
OUT = ROOT / "data/derived/vat_pass_through_evidence.csv"
OUT_CUT_AUDIT = ROOT / "data/derived/vat_rate_cut_transport_audit.csv"
EXPECTED = {
    "JSTAGE-SHIRAISHI-2016-VAT-PASS-THROUGH-POS": "23b7fb786fa7b563a142a31af82c952314154661ca21411c44428612570e8b77",
    "BOJ-OUTLOOK-2019-07-CONSUMPTION-TAX": "5aceffc5a8d4c459a2cd2952aeb017bb71c6bd7a3b01b6e2a0d533b1e2488b32",
    "CAO-2014-CONSUMPTION-TAX-DEMAND": "4707c274068e22b7d351ed968e92f1c9cbdfb29a4a28f22ff93a40b468b19a22",
    "MOF-2019-CONSUMPTION-TAX-HIKE": "8824d30b2fb4ce1be09a9089215a4c0519fb3a70d92790223e763dde2c579a73",
    "MOF-CONSUMPTION-TAX-RATE-HISTORY": "739217b9e11f414fed31e51eece41ddc9a6fdb23e2bab13d91d48f3bf49900a3",
    "REPEC-CESIFO-2021-GERMANY-TEMP-VAT-CUT": "86f58edff474966c6f53a86c5d8ec20855fa53e7f78b1ce6fbd6f931d523aa56",
    "OXFORD-2014-UK-TEMP-VAT-CUT": "a6abc4f6473dea307c77ea940ac7a01d6d4d5ca32762154fbb7632a14f7b9176",
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

def html_text(path):
    text = path.read_text(encoding="utf-8-sig", errors="strict")
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text)

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

    history = html_text(ROOT / cat["MOF-CONSUMPTION-TAX-RATE-HISTORY"]["raw_file"])
    require(history, ["税率３％の消費税が平成元年４月から導入", "3％ → 5％", "5％から8％に引き上げ", "8％から10％に引き上げ"], "MOF consumption-tax history")
    germany = html_text(ROOT / cat["REPEC-CESIFO-2021-GERMANY-TEMP-VAT-CUT"]["raw_file"])
    require(germany, ["temporary value added tax (VAT) rate reduction", "asymmetric price response", "roughly 1.3%", "about 70%", "about half that size"], "Germany 2020 VAT cut")
    uk = html_text(ROOT / cat["OXFORD-2014-UK-TEMP-VAT-CUT"]["raw_file"])
    require(uk, ["2.5 percentage points for 13 months", "initially passed through the VAT cut", "reversed after only a few months", "around 1%", "0.4% increase in total expenditure", "significant fall in sales after the VAT cut ended"], "UK 2008 VAT cut")

    common_transfer = "HISTORICAL_RATE_INCREASE_EVIDENCE_NOT_RATE_CUT_OR_ABOLITION_PARAMETER"
    rows = [
        {"evidence_id":"PT-2014-POS-HETEROGENEITY","evidence_dimension":"PRICE_PASS_THROUGH","event_period":"2014-04","policy_change":"VAT 5% to 8%","market_scope":"supermarket consumer goods / POS regular and sale prices","method":"item-level POS analysis and regressions","pass_through_point":"","pass_through_unit":"","quantity_effect_low":"","quantity_effect_high":"","quantity_effect_unit":"","identification_status":"OBSERVED_HISTORICAL_MICRO_HETEROGENEITY","policy_transfer_status":common_transfer,"vat_base_status":"2014_TAXABLE_RETAIL_GOODS_STUDY_SCOPE_NOT_HOUSEHOLD_BASE_SHARE","quantity_response_status":"NOT_ESTIMATED_IN_THIS_EVIDENCE_ROW","source_ids":"JSTAGE-SHIRAISHI-2016-VAT-PASS-THROUGH-POS","source_locator":"article pp.119-146; English summary p.29","note":"Many items passed through the 2014 increase, but pass-through differed across goods and both under- and over-shifting occurred. No uniform household pass-through coefficient is promoted."},
        {"evidence_id":"PT-2019-BOJ-FULL-PASS-THROUGH-ASSUMPTION","evidence_dimension":"PRICE_PASS_THROUGH","event_period":"2019-10","policy_change":"VAT standard rate 8% to 10%","market_scope":"taxable CPI items excluding reduced-rate items","method":"BOJ mechanical forecast assumption","pass_through_point":"1","pass_through_unit":"assumed_fraction_of_tax_change_passed_to_taxable_item_prices","quantity_effect_low":"","quantity_effect_high":"","quantity_effect_unit":"","identification_status":"MECHANICAL_ASSUMPTION_NOT_EMPIRICAL_ESTIMATE","policy_transfer_status":"DO_NOT_TREAT_FULL_PASS_THROUGH_ASSUMPTION_AS_OBSERVED_OR_ABOLITION_PARAMETER","vat_base_status":"STANDARD_RATE_TAXABLE_ITEMS_EXCLUDING_REDUCED_RATE","quantity_response_status":"NOT_ESTIMATED_IN_THIS_EVIDENCE_ROW","source_ids":"BOJ-OUTLOOK-2019-07-CONSUMPTION-TAX","source_locator":"July 2019 Outlook footnote 6","note":"BOJ assumed full pass-through for taxable items when mechanically estimating the direct CPI effect; this is an assumption, not an empirical pass-through estimate."},
        {"evidence_id":"QR-2019-BOJ-DEMAND-CHANNELS","evidence_dimension":"QUANTITY_RESPONSE","event_period":"2019-10","policy_change":"VAT standard rate 8% to 10% with reduced rate","market_scope":"aggregate Japanese demand","method":"BOJ outlook channel decomposition","pass_through_point":"","pass_through_unit":"","quantity_effect_low":"","quantity_effect_high":"","quantity_effect_unit":"","identification_status":"OFFICIAL_OUTLOOK_CHANNEL_DECOMPOSITION","policy_transfer_status":common_transfer,"vat_base_status":"REDUCED_RATE_PRESENT","quantity_response_status":"FRONTLOAD_THEN_DECLINE_PLUS_REAL_INCOME_CHANNEL_NOT_STRUCTURAL_ELASTICITY","source_ids":"BOJ-OUTLOOK-2019-07-CONSUMPTION-TAX","source_locator":"July 2019 Outlook footnotes 2-3","note":"BOJ separated front-loaded demand/subsequent decline from the real-income channel. This does not identify a steady-state quantity elasticity for a VAT cut or abolition."},
        {"evidence_id":"QR-2014-CAO-FRONTLOAD-REBOUND","evidence_dimension":"QUANTITY_RESPONSE","event_period":"2013-2014","policy_change":"VAT 5% to 8%","market_scope":"aggregate private consumption","method":"Cabinet Office ex-post intertemporal-substitution estimate","pass_through_point":"","pass_through_unit":"","quantity_effect_low":"2500000000000","quantity_effect_high":"3300000000000","quantity_effect_unit":"yen_intertemporal_consumption_shift","identification_status":"OFFICIAL_EX_POST_INTERTEMPORAL_SHIFT_ESTIMATE","policy_transfer_status":common_transfer,"vat_base_status":"AGGREGATE_CONSUMPTION_NOT_VAT_BASE_DECOMPOSITION","quantity_response_status":"TEMPORARY_FRONTLOAD_AND_REBOUND_NOT_STEADY_STATE_ELASTICITY","source_ids":"CAO-2014-CONSUMPTION-TAX-DEMAND","source_locator":"2014 Japanese Economy, ch.1 sec.1, Table 1-1-4 discussion","note":"Cabinet Office estimated 2014 front-loading and rebound at 2.5-3.3 trillion yen, about 0.5-0.6% of real GDP; this is timing substitution around a tax increase, not a persistent demand multiplier."},
        {"evidence_id":"PT-2020-GERMANY-TEMP-CUT","evidence_dimension":"PRICE_PASS_THROUGH","event_period":"2020-07 to 2020-12","policy_change":"temporary broad VAT rate cut, then restoration","market_scope":"German supermarket products; Austria counterfactual","method":"web-scraped daily prices; Germany-vs-Austria causal comparison","pass_through_point":"0.70","pass_through_unit":"fraction_of_tax_cut_passed_to_consumer_prices","quantity_effect_low":"","quantity_effect_high":"","quantity_effect_unit":"","identification_status":"EXTERNAL_CAUSAL_TEMPORARY_RATE_CUT_SUPERMARKET","policy_transfer_status":"EXTERNAL_SENSITIVITY_ONLY_NO_JAPAN_PARAMETER_OR_BOUND","vat_base_status":"GERMAN_SUPERMARKET_SCOPE_NOT_JAPAN_HOUSEHOLD_VAT_BASE","quantity_response_status":"NOT_ESTIMATED_IN_THIS_EVIDENCE_ROW","source_ids":"REPEC-CESIFO-2021-GERMANY-TEMP-VAT-CUT","source_locator":"CESifo Working Paper 9149 abstract","note":"Temporary German VAT cut lowered supermarket prices by roughly 1.3%, implying about 70% cut pass-through. The subsequent VAT increase price effect was only about half as large, so simple cut/increase symmetry is not supported in this study scope."},
        {"evidence_id":"QR-2008-UK-TEMP-CUT","evidence_dimension":"QUANTITY_RESPONSE","event_period":"2008-12 for 13 months","policy_change":"temporary standard VAT cut by 2.5 percentage points","market_scope":"UK retail sales and prices","method":"alternative counterfactual identification strategies","pass_through_point":"","pass_through_unit":"","quantity_effect_low":"0.01","quantity_effect_high":"0.01","quantity_effect_unit":"approx_retail_sales_volume_fraction","identification_status":"EXTERNAL_TEMPORARY_RATE_CUT_EMPIRICAL","policy_transfer_status":"EXTERNAL_SENSITIVITY_ONLY_NO_JAPAN_PARAMETER_OR_STEADY_STATE_ELASTICITY","vat_base_status":"UK_STANDARD_RATE_SCOPE_NOT_JAPAN_HOUSEHOLD_VAT_BASE","quantity_response_status":"TEMPORARY_INTERTEMPORAL_SUBSTITUTION_NOT_STEADY_STATE_RESPONSE","source_ids":"OXFORD-2014-UK-TEMP-VAT-CUT","source_locator":"Oxford working-paper abstract","note":"Firms initially lowered prices, but part of pass-through reversed within months. Retail sales volume rose around 1% (about 0.4% total-expenditure effect by itself) and fell significantly after the cut ended, indicating intertemporal substitution."},
        {"evidence_id":"BASE-2019-MOF-RATE-SCOPE","evidence_dimension":"VAT_BASE_RULE","event_period":"2019-10 onward","policy_change":"standard 10%, reduced 8%","market_scope":"statutory consumption-tax rate scope","method":"official statutory-policy description","pass_through_point":"","pass_through_unit":"","quantity_effect_low":"","quantity_effect_high":"","quantity_effect_unit":"","identification_status":"OBSERVED_STATUTORY_SCOPE","policy_transfer_status":"NOT_A_BEHAVIORAL_PARAMETER","vat_base_status":"STANDARD_AND_REDUCED_RATE_SCOPE_RULE_IDENTIFIED_HOUSEHOLD_EXPENDITURE_SHARES_NOT_IDENTIFIED","quantity_response_status":"NOT_APPLICABLE","source_ids":"MOF-2019-CONSUMPTION-TAX-HIKE","source_locator":"Reduced Tax Rate System section","note":"Reduced 8% applies to specified food/beverages excluding liquor and dining out, and qualifying subscribed newspapers; category rules do not identify decile-specific taxable expenditure shares."},
    ]
    return rows

def build_cut_audit():
    return [
        {"metric_id":"japan_nationwide_standard_rate_cut_episode","value":"NONE_IN_ENUMERATED_1989_2019_STANDARD_RATE_HISTORY","identification_status":"BOUNDED_OFFICIAL_HISTORY_AUDIT","japan_policy_parameter_effect":"NO_DIRECT_JAPAN_RATE_CUT_IDENTIFICATION","source_ids":"MOF-CONSUMPTION-TAX-RATE-HISTORY","note":"MOF history enumerates introduction at 3% and nationwide standard-rate increases to 5%, 8%, and 10%; this bounded history provides no implemented nationwide standard-rate decrease episode for direct identification."},
        {"metric_id":"germany_2020_temporary_cut_pass_through","value":"0.70","identification_status":"EXTERNAL_CAUSAL_TEMPORARY_RATE_CUT_SUPERMARKET","japan_policy_parameter_effect":"SENSITIVITY_ONLY_NOT_JAPAN_BOUND","source_ids":"REPEC-CESIFO-2021-GERMANY-TEMP-VAT-CUT","note":"Germany-vs-Austria design: roughly 1.3% price decrease, about 70% of the temporary tax cut passed to consumers."},
        {"metric_id":"germany_cut_restoration_asymmetry","value":"CUT_PRICE_EFFECT_1.3PCT;RESTORATION_PRICE_EFFECT_ABOUT_HALF","identification_status":"EXTERNAL_WITHIN_STUDY_ASYMMETRY_EVIDENCE","japan_policy_parameter_effect":"DO_NOT_ASSUME_INCREASE_DECREASE_SYMMETRY","source_ids":"REPEC-CESIFO-2021-GERMANY-TEMP-VAT-CUT","note":"The same study reports the subsequent VAT-increase price effect at about half the cut effect; this is evidence against imposing symmetry as a generic transfer rule."},
        {"metric_id":"uk_2008_temporary_cut_price_profile","value":"INITIAL_PASS_THROUGH_PARTLY_REVERSED_WITHIN_MONTHS","identification_status":"EXTERNAL_TEMPORARY_RATE_CUT_EMPIRICAL","japan_policy_parameter_effect":"SENSITIVITY_ONLY_NOT_PERSISTENT_PASS_THROUGH","source_ids":"OXFORD-2014-UK-TEMP-VAT-CUT","note":"UK standard VAT was cut 2.5 percentage points for 13 months; initial price pass-through was partially reversed before the policy ended."},
        {"metric_id":"uk_2008_temporary_cut_quantity_profile","value":"RETAIL_VOLUME_ABOUT_1PCT;TOTAL_EXPENDITURE_ABOUT_0.4PCT;POST_CUT_SALES_FALL","identification_status":"EXTERNAL_INTERTEMPORAL_QUANTITY_RESPONSE","japan_policy_parameter_effect":"DO_NOT_TREAT_AS_STEADY_STATE_JAPAN_DEMAND_ELASTICITY","source_ids":"OXFORD-2014-UK-TEMP-VAT-CUT","note":"The study attributes part of the sales response to purchases brought forward, followed by a significant fall after the cut ended."},
        {"metric_id":"increase_to_decrease_symmetry_status","value":"NOT_ADOPTED","identification_status":"UNSUPPORTED_TRANSFER_RESTRICTION","japan_policy_parameter_effect":"HISTORICAL_JAPAN_RATE_INCREASES_NOT_INVERTED_INTO_CUT_COEFFICIENT","source_ids":"JSTAGE-SHIRAISHI-2016-VAT-PASS-THROUGH-POS;REPEC-CESIFO-2021-GERMANY-TEMP-VAT-CUT;OXFORD-2014-UK-TEMP-VAT-CUT","note":"Observed heterogeneity and external cut/restoration dynamics do not justify a common symmetric Japan cut/abolition pass-through coefficient."},
        {"metric_id":"japan_5_0_abolition_pass_through_parameter","value":"NOT_IDENTIFIED","identification_status":"NO_FORMAL_JAPAN_BOUND_FROM_CURRENT_EVIDENCE","japan_policy_parameter_effect":"KEEP_POLICY_MATRIX_PARAMETER_BLANK","source_ids":"MOF-CONSUMPTION-TAX-RATE-HISTORY;REPEC-CESIFO-2021-GERMANY-TEMP-VAT-CUT;OXFORD-2014-UK-TEMP-VAT-CUT","note":"External temporary-cut estimates are not transported into a Japan bound without a validated transport model; full institutional abolition is additionally distinct from a temporary rate cut."},
        {"metric_id":"rate_cut_public_search_stop","value":"STOP_GENERAL_RATE_CUT_EVIDENCE_ACCUMULATION","identification_status":"BOUNDED_TARGETED_SEARCH_COMPLETED","japan_policy_parameter_effect":"ADVANCE_NEXT_EXECUTABLE_HIGH_VOI_GAP","source_ids":"MOF-CONSUMPTION-TAX-RATE-HISTORY;REPEC-CESIFO-2021-GERMANY-TEMP-VAT-CUT;OXFORD-2014-UK-TEMP-VAT-CUT","note":"Reopen public searching only for evidence that identifies Japan directly or supplies observable transport restrictions capable of shrinking a formal Japan admissible set."},
    ]

def write_or_check(path, rows, check):
    text = render(rows)
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            raise SystemExit("stale generated artifact: " + str(path.relative_to(ROOT)))
    else:
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); args = ap.parse_args()
    rows = build(); audit = build_cut_audit()
    write_or_check(OUT, rows, args.check)
    write_or_check(OUT_CUT_AUDIT, audit, args.check)
    if args.check:
        print("VAT pass-through evidence: current (7 evidence rows; Japan cut parameter remains unidentified)")

if __name__ == "__main__": main()
