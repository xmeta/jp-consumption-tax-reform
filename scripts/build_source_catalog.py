#!/usr/bin/env python3
from pathlib import Path
import csv
import hashlib

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
OUT = ROOT / "data/source_catalog.csv"

# Every file under data/raw must appear exactly once here.
SOURCES = [
    ("ESTAT-7153-1-2024","Statistics Bureau of Japan","2024 NSFCW table 7-153-1: equivalized annual income by decile and income component","https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040490416&fileKind=0","estat/000040490416.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","e-Stat statInfId=000040490416; table 7-153-1","RAW_OFFICIAL"),
    ("ESTAT-7156-1-2024","Statistics Bureau of Japan","2024 NSFCW table 7-156-1: household type x equivalized-income class/decile x income component","https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040490419&fileKind=0","estat/000040490419.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","e-Stat statInfId=000040490419; table 7-156-1","RAW_OFFICIAL"),
    ("ESTAT-7191-1-2024","Statistics Bureau of Japan","2024 NSFCW table 7-191-1: household members by sex, age, household size, head employment, income and asset classes","https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040490431&fileKind=0","estat/000040490431.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","e-Stat statInfId=000040490431; table 7-191-1; F71911","RAW_OFFICIAL"),
    ("STAT-F71561-DESIGN","Statistics Bureau of Japan","2024 National Survey of Family Income, Consumption and Wealth sample design","https://www.stat.go.jp/data/zenkokukakei/2024/pdf/hyohon2024.pdf","statistics_bureau/2024_nsfcw_sample_design.pdf","application/pdf","Section II; Table 4; 2020 Census results rearranged to municipalities as of 2024-01-01","RAW_OFFICIAL"),
    ("STAT-CENSUS-2020-SUMMARY","Statistics Bureau of Japan","Population and Households of Japan 2020 - overview","https://www.stat.go.jp/english/data/kokusei/2020/summary/pdf/all.pdf","statistics_bureau/2020_population_census_summary_en.pdf","application/pdf","Summary p.2 / PDF p.5; total population 126,146,099","RAW_OFFICIAL"),
    ("STAT-CENSUS-2020-BASIC","Statistics Bureau of Japan","2020 Population Census basic complete tabulation - results overview","https://www.stat.go.jp/data/kokusei/2020/kekka/pdf/outline_01.pdf","statistics_bureau/2020_population_census_basic_complete_summary.pdf","application/pdf","General-household persons and one-person general households; cross-check against Census Report Table 7-2","RAW_OFFICIAL"),
    ("STAT-MIGRATION-2024","Statistics Bureau of Japan","Report on Internal Migration in Japan 2024 - summary","https://www.stat.go.jp/data/idou/2024np/jissu/pdf/gaiyou.pdf","statistics_bureau/2024_basic_resident_register_migration_summary.pdf","application/pdf","Table 1; gross international inflow, 2020-2024","RAW_OFFICIAL"),
    ("ISHIKAWA-CENSUS-2020","Ishikawa Prefecture","2020 Population Census basic tabulation summary - Ishikawa","https://toukei.pref.ishikawa.lg.jp/dl/4461/R2census_jinkou.pdf","ishikawa/2020_population_census_summary.pdf","application/pdf","Municipal population and general-household-person tables for Wajima, Suzu, Anamizu and Noto","RAW_OFFICIAL"),
    ("NTA-R06","National Tax Agency","FY2024 National Tax Agency Annual Statistics Report","https://www.nta.go.jp/publication/statistics/kokuzeicho/r06/R06.pdf","nta/nta_fy2024_annual_statistics.pdf","application/pdf","PDF p.55 / printed p.46; Table 2-1(1), final-return row","RAW_OFFICIAL"),
    ("NTA-INFO-EXCHANGE-2024","National Tax Agency","FY2024 status of information exchange under tax treaties","https://www.nta.go.jp/information/release/pdf/0026001-016.pdf","nta/nta_fy2024_tax_treaty_information_exchange.pdf","application/pdf","Non-resident statutory-report information exchange count; scale diagnostic only","RAW_OFFICIAL"),
    ("NTA-NONRESIDENT-GUIDANCE","National Tax Agency","Tax Answer No.1926 - non-residents with Japanese domestic-source income","https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1926.htm","nta/nonresident_domestic_source_guidance.html","text/html","Legal/source-coverage audit; no person count extracted","RAW_OFFICIAL"),
    ("MHLW-VITAL-2020-PAGE","Ministry of Health, Labour and Welfare","2020 Vital Statistics final landing page","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei20/index.html","mhlw/2020_vital_statistics_final_page.html","text/html","Landing-page snapshot linking final tables","RAW_OFFICIAL_METADATA"),
    ("MHLW-VITAL-2020-T1","Ministry of Health, Labour and Welfare","2020 Vital Statistics final - Table 1","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei20/dl/03_h1.pdf","mhlw/2020_vital_table1.pdf","application/pdf","Table 1; births 2020","RAW_OFFICIAL"),
    ("MHLW-VITAL-2020-T2","Ministry of Health, Labour and Welfare","2020 Vital Statistics final - Table 2-1 annual trend","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei20/dl/04_h2-1.pdf","mhlw/2020_vital_trend_table2_1.pdf","application/pdf","Table 2-1 annual trend","RAW_OFFICIAL"),
    ("MHLW-VITAL-2022-PAGE","Ministry of Health, Labour and Welfare","2022 Vital Statistics final landing page","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei22/","mhlw/2022_vital_statistics_final_page.html","text/html","Landing-page snapshot linking final tables","RAW_OFFICIAL_METADATA"),
    ("MHLW-VITAL-2022-T1","Ministry of Health, Labour and Welfare","2022 Vital Statistics final - Table 1","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei22/dl/03_h1.pdf","mhlw/2022_vital_table1.pdf","application/pdf","Table 1; births 2022 and prior-year 2021","RAW_OFFICIAL"),
    ("MHLW-VITAL-2022-T2","Ministry of Health, Labour and Welfare","2022 Vital Statistics final - Table 2-1 annual trend","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei22/dl/04_h2-1.pdf","mhlw/2022_vital_trend_table2_1.pdf","application/pdf","Table 2-1; 2020-2022 annual trend","RAW_OFFICIAL"),
    ("MHLW-VITAL-2024-PAGE","Ministry of Health, Labour and Welfare","2024 Vital Statistics final landing page","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei24/","mhlw/2024_vital_statistics_final_page.html","text/html","Landing-page snapshot linking final tables","RAW_OFFICIAL_METADATA"),
    ("MHLW-VITAL-2024-T1","Ministry of Health, Labour and Welfare","2024 Vital Statistics final - Table 1","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei24/dl/03_h1.pdf","mhlw/2024_vital_table1.pdf","application/pdf","Table 1; births/deaths 2024 and prior-year 2023","RAW_OFFICIAL"),
    ("MHLW-VITAL-2024-T2","Ministry of Health, Labour and Welfare","2024 Vital Statistics final - Table 2 annual trend","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei24/dl/04_h2.pdf","mhlw/2024_vital_trend_table2.pdf","application/pdf","Table 2 annual trend","RAW_OFFICIAL"),
    ("MHLW-VITAL-2024-ANNUAL-PAGE","Ministry of Health, Labour and Welfare","2024 Vital Statistics annual-summary landing page","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/geppo/nengai24/","mhlw/2024_vital_statistics_annual_summary_page.html","text/html","Landing-page snapshot; comparison only when final data are unavailable","RAW_OFFICIAL_METADATA"),
    ("MHLW-VITAL-2024-ANNUAL-T1","Ministry of Health, Labour and Welfare","2024 Vital Statistics annual-summary Table 1","https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/geppo/nengai24/dl/h1.pdf","mhlw/2024_annual_vital_table1.pdf","application/pdf","Annual-summary Table 1; retained for provenance comparison","RAW_OFFICIAL"),
]

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def main():
    rows = []
    catalog_paths = set()
    for sid, publisher, title, url, rel, media_type, locator, status in SOURCES:
        path = RAW / rel
        if not path.exists():
            raise SystemExit(f"missing raw source: {path}")
        if rel in catalog_paths:
            raise SystemExit(f"duplicate raw path in catalog: {rel}")
        catalog_paths.add(rel)
        rows.append({
            "source_id": sid,
            "publisher": publisher,
            "title": title,
            "source_url": url,
            "raw_file": str(path.relative_to(ROOT)),
            "media_type": media_type,
            "locator": locator,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "status": status,
        })

    actual_paths = {
        str(p.relative_to(RAW))
        for p in RAW.rglob("*")
        if p.is_file()
    }
    if actual_paths != catalog_paths:
        missing = sorted(actual_paths - catalog_paths)
        phantom = sorted(catalog_paths - actual_paths)
        raise SystemExit(
            f"raw/catalog mismatch; unregistered={missing}; missing={phantom}"
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} sources")

if __name__ == "__main__":
    main()
