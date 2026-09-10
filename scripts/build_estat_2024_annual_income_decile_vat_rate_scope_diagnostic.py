#!/usr/bin/env python3
"""Build an annual-income-decile VAT rate-scope proxy diagnostic.

This maps published NSFCW expenditure categories to the statutory reduced-rate
scope only as a survey-category proxy. It is not a transaction-level VAT base,
tax-incidence estimate, or objective-rank distribution bridge.
"""
from pathlib import Path
import argparse
import csv
import io
from decimal import Decimal

from build_estat_2024_annual_income_decile_expenditure_diagnostic import (
    EXPECTED_SHA as ESTAT_SHA,
    SOURCE_ID as ESTAT_SOURCE_ID,
    decile_values,
    load_cells,
    target_block,
    unique_row,
)

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data/source_catalog.csv"
OUT = ROOT / "data/derived/estat_2024_annual_income_decile_vat_rate_scope_diagnostic.csv"
MOF_SOURCE_ID = "MOF-2019-CONSUMPTION-TAX-HIKE"
MOF_SHA = "8824d30b2fb4ce1be09a9089215a4c0519fb3a70d92790223e763dde2c579a73"


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def values(block, label):
    return decile_values(
        unique_row(
            block,
            item_i="1世帯当たり1か月間の収入と支出",
            item_k=label,
        )
    )


def ratio(numerator, denominator):
    return f"{Decimal(numerator) / Decimal(denominator):.12f}".rstrip("0").rstrip(".")


def build():
    catalog = {row["source_id"]: row for row in read_csv(CAT)}
    estat = catalog[ESTAT_SOURCE_ID]
    mof = catalog[MOF_SOURCE_ID]
    if estat["sha256"] != ESTAT_SHA:
        raise RuntimeError(f"{ESTAT_SOURCE_ID}: unexpected source hash")
    if mof["sha256"] != MOF_SHA:
        raise RuntimeError(f"{MOF_SOURCE_ID}: unexpected source hash")

    mof_text = (ROOT / mof["raw_file"]).read_text(encoding="utf-8")
    for token in (
        "Foods and beverages with the exception of liquors and eating-out",
        "Subscribed newspapers issued twice or more per week",
    ):
        if token not in mof_text:
            raise RuntimeError(f"{MOF_SOURCE_ID}: missing scope token {token!r}")

    block = target_block(load_cells(ROOT / estat["raw_file"]))
    consumption = values(block, "2101_消費支出")
    food = values(block, "210101_食料")
    alcohol = values(block, "21010111_酒類")
    dining = values(block, "21010112_外食")
    newspaper = values(block, "210109030001_新聞")

    rows = []
    for i in range(10):
        c = int(consumption[i])
        f = int(food[i])
        a = int(alcohol[i])
        d = int(dining[i])
        n = int(newspaper[i])
        core = f - a - d
        if core < 0 or core + n > c:
            raise RuntimeError(f"invalid rate-scope proxy arithmetic at decile {i + 1}")
        rows.append({
            "annual_income_decile": i + 1,
            "rank_concept": "HOUSEHOLD_ANNUAL_INCOME_DECILE",
            "objective_rank_concept": "OECD_NEW_EQUIVALIZED_DISPOSABLE_INCOME_DECILE",
            "rank_bridge_status": "NOT_LINKED_DO_NOT_TREAT_AS_OBJECTIVE_DECILE",
            "monthly_consumption_expenditure_yen": c,
            "food_yen_month": f,
            "alcohol_yen_month": a,
            "dining_out_yen_month": d,
            "newspaper_yen_month": n,
            "reduced_rate_scope_proxy_core_yen_month": core,
            "reduced_rate_scope_proxy_core_share_of_consumption": ratio(core, c),
            "reduced_rate_scope_proxy_with_all_newspaper_yen_month": core + n,
            "reduced_rate_scope_proxy_with_all_newspaper_share_of_consumption": ratio(core + n, c),
            "rate_scope_proxy_status": "SURVEY_CATEGORY_PROXY_NOT_TRANSACTION_LEVEL_VAT_BASE",
            "newspaper_scope_status": "ALL_NEWSPAPER_SPENDING_IS_ONLY_A_DIAGNOSTIC_CEILING_QUALIFYING_SUBSCRIPTION_SHARE_NOT_IDENTIFIED",
            "actual_vat_base_status": "NOT_IDENTIFIED_TRANSACTION_LEVEL_TAXABILITY_AND_NEWSPAPER_QUALIFICATION_REQUIRED",
            "source_ids": f"{ESTAT_SOURCE_ID};{MOF_SOURCE_ID}",
            "source_locator": "NSFCW a01021 rows 19-32 and 249, annual-income deciles BF:BO; MOF Reduced Tax Rate System",
            "note": "Food minus alcohol and dining-out is a survey-category proxy for the core reduced-rate scope. Adding all newspaper expenditure is a diagnostic ceiling for category coverage, not a legal or transaction-level VAT-base bound because qualifying newspaper subscriptions and transaction-level taxability are not observed.",
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            raise SystemExit("stale generated artifact: " + str(OUT.relative_to(ROOT)))
        print("VAT rate-scope diagnostic: current (10 annual-income deciles; survey-category proxy only)")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}: 10 rows")


if __name__ == "__main__":
    main()
