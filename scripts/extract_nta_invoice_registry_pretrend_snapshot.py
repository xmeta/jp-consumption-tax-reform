#!/usr/bin/env python3
"""Create a privacy-safe frozen snapshot from NTA invoice-registry ZIP downloads.

The source ZIPs contain public registration numbers and are intentionally NOT copied
into this public repository. This extractor reads them locally and writes only file
hash metadata plus non-identifying aggregate counts.
"""
from __future__ import annotations

import argparse, collections, csv, hashlib, re, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_MANIFEST = ROOT / "research/vat_compliance_productivity/nta_invoice_registry_pretrend_source_manifest_20260913.csv"
OUT_OBS = ROOT / "research/vat_compliance_productivity/nta_invoice_registry_pretrend_observations_20260913.csv"
SNAPSHOT_DATE = "2026-08-31"
FULL_IDS = {
    "h_all_20260831_csv_001.zip": ("5075", "corporation"),
    "h_all_20260831_csv_002.zip": ("5071", "corporation"),
    "h_all_20260831_csv_003.zip": ("5080", "corporation"),
    "h_all_20260831_csv_004.zip": ("5073", "corporation"),
    "h_all_20260831_csv_005.zip": ("5072", "corporation"),
    "j_all_20260831_csv.zip": ("5074", "unincorporated_association"),
    "k_all_20260831_csv_001.zip": ("5081", "individual"),
    "k_all_20260831_csv_002.zip": ("5077", "individual"),
    "k_all_20260831_csv_003.zip": ("5078", "individual"),
    "k_all_20260831_csv_004.zip": ("5079", "individual"),
    "k_all_20260831_csv_005.zip": ("5076", "individual"),
}
PROCESS = {"01":"registration_publication", "02":"public_info_change", "03":"expiration_publication", "04":"cancellation_publication", "99":"deletion"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def csv_rows(path: Path):
    with zipfile.ZipFile(path) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".csv"))
        yield from csv.reader((line.decode("utf-8") for line in zf.open(name)))


def extract(source_dir: Path):
    manifest = []
    monthly = collections.Counter()
    stock = collections.Counter()
    delta = collections.Counter()
    last_id = {}
    seen_for_id = {}

    for filename, (file_id, entity_type) in FULL_IDS.items():
        path = source_dir / filename
        if not path.exists():
            raise RuntimeError(f"missing full snapshot ZIP: {path}")
        manifest.append({
            "source_scope":"full_snapshot", "source_date":SNAPSHOT_DATE, "file_id":file_id,
            "entity_type":entity_type, "filename":filename, "bytes":path.stat().st_size,
            "sha256":sha256(path),
            "download_url":f"https://www.invoice-kohyo.nta.go.jp/download/zenken/dlfile?dlFilKanriNo={file_id}&jinkakukbn={'1' if entity_type=='individual' else '2' if entity_type=='corporation' else '3'}&type=01",
        })
        for row in csv_rows(path):
            if len(row) < 11:
                continue
            regnum, latest, reg, disposal, expire = row[1], row[6], row[7], row[9], row[10]
            if last_id.get(entity_type) != regnum:
                last_id[entity_type] = regnum
                seen_for_id[entity_type] = set()
            for event_type, effective_date in (("registration", reg), ("cancellation", disposal), ("expiration", expire)):
                key = (event_type, effective_date)
                if effective_date and effective_date <= SNAPSHOT_DATE and key not in seen_for_id[entity_type]:
                    monthly[(effective_date[:7], entity_type, event_type)] += 1
                    seen_for_id[entity_type].add(key)
            if latest == "1" and reg:
                if reg > SNAPSHOT_DATE:
                    stock[(entity_type, "future_registration_after_snapshot")] += 1
                else:
                    ended = (disposal and disposal <= SNAPSHOT_DATE) or (expire and expire <= SNAPSHOT_DATE)
                    stock[(entity_type, "inactive_as_of_snapshot" if ended else "active_as_of_snapshot")] += 1
                    if disposal and disposal > SNAPSHOT_DATE:
                        stock[(entity_type, "future_cancellation_after_snapshot")] += 1
                    if expire and expire > SNAPSHOT_DATE:
                        stock[(entity_type, "future_expiration_after_snapshot")] += 1

    delta_manifest = source_dir / "manifest_delta.csv"
    if not delta_manifest.exists():
        raise RuntimeError(f"missing delta manifest: {delta_manifest}")
    with delta_manifest.open(encoding="utf-8", newline="") as f:
        delta_sources = list(csv.DictReader(f))
    if len(delta_sources) != 40:
        raise RuntimeError(f"expected 40 delta files, found {len(delta_sources)}")
    for src in delta_sources:
        path = source_dir / src["filename"]
        if not path.exists():
            raise RuntimeError(f"missing delta ZIP: {path}")
        actual_sha = sha256(path)
        if actual_sha != src["sha256"] or path.stat().st_size != int(src["bytes"]):
            raise RuntimeError(f"delta manifest mismatch: {path.name}")
        manifest.append({
            "source_scope":"delta_window", "source_date":src["file_date"], "file_id":src["file_id"],
            "entity_type":"mixed", "filename":src["filename"], "bytes":src["bytes"], "sha256":actual_sha,
            "download_url":f"https://www.invoice-kohyo.nta.go.jp/download/sabun/dlfile?dlFilKanriNo={src['file_id']}&type=01",
        })
        for row in csv_rows(path):
            if len(row) < 7:
                continue
            process, kind, latest = row[2], row[4], row[6]
            entity_type = {"1":"individual", "2":"corporation_or_unincorporated_association", "":"unknown"}.get(kind, "other")
            delta[(src["file_date"], entity_type, PROCESS.get(process, f"other_{process}"), latest or "blank")] += 1

    obs = []
    for (month, entity, event), count in sorted(monthly.items()):
        obs.append({"component":"full_history_monthly", "period":month, "entity_type":entity, "event_type":event,
                    "latest_flag":"", "count":count, "source_scope":"2026-08-31 full snapshot surviving publication history",
                    "identification_status":"SURVIVING_PUBLICATION_HISTORY_EXCLUDES_DELETED_99_NOT_CAUSAL"})
    for (entity, metric), count in sorted(stock.items()):
        obs.append({"component":"full_stock", "period":SNAPSHOT_DATE, "entity_type":entity, "event_type":metric,
                    "latest_flag":"1", "count":count, "source_scope":"2026-08-31 full snapshot latest rows",
                    "identification_status":"REGISTRY_STOCK_OR_SCHEDULE_DIAGNOSTIC_NOT_CAUSAL"})
    for (day, entity, event, latest), count in sorted(delta.items()):
        obs.append({"component":"delta_publication_daily", "period":day, "entity_type":entity, "event_type":event,
                    "latest_flag":latest, "count":count, "source_scope":"40-business-day official delta download window",
                    "identification_status":"PUBLICATION_CHANGE_FLOW_NOT_EFFECTIVE_EVENT_NOT_CAUSAL"})
    return manifest, obs


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source_dir", type=Path)
    args = ap.parse_args()
    manifest, obs = extract(args.source_dir)
    write_csv(OUT_MANIFEST, manifest); write_csv(OUT_OBS, obs)
    print(f"wrote {OUT_MANIFEST.relative_to(ROOT)}: {len(manifest)} source files")
    print(f"wrote {OUT_OBS.relative_to(ROOT)}: {len(obs)} privacy-safe aggregate rows")

if __name__ == "__main__":
    main()
