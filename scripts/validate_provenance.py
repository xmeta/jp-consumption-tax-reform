#!/usr/bin/env python3
from pathlib import Path
import csv
import hashlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def read_csv(rel):
    path = ROOT / rel
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def split_ids(text):
    return [x.strip() for x in text.split(";") if x.strip()]

errors = []

catalog_rows = read_csv("data/source_catalog.csv")
catalog = {}
catalog_paths = set()
for r in catalog_rows:
    sid = r["source_id"]
    if sid in catalog:
        errors.append(f"duplicate source_id: {sid}")
        continue
    catalog[sid] = r
    path = ROOT / r["raw_file"]
    catalog_paths.add(str(path.relative_to(ROOT / "data/raw")))
    if not path.exists():
        errors.append(f"{sid}: raw file missing: {r['raw_file']}")
        continue
    actual_sha = sha256(path)
    if actual_sha != r["sha256"]:
        errors.append(f"{sid}: SHA mismatch")
    if path.stat().st_size != int(r["bytes"]):
        errors.append(f"{sid}: byte-size mismatch")
    if not r["source_url"].startswith("https://"):
        errors.append(f"{sid}: source_url is not https")

actual_raw = {
    str(p.relative_to(ROOT / "data/raw"))
    for p in (ROOT / "data/raw").rglob("*")
    if p.is_file()
}
if actual_raw != catalog_paths:
    errors.append(
        "raw catalog coverage mismatch: "
        f"unregistered={sorted(actual_raw-catalog_paths)} "
        f"missing={sorted(catalog_paths-actual_raw)}"
    )

derived_rows = read_csv("data/derived_catalog.csv")
derived_paths = set()
for r in derived_rows:
    rel = r["derived_file"]
    if rel in derived_paths:
        errors.append(f"duplicate derived_file: {rel}")
        continue
    derived_paths.add(rel)
    path = ROOT / rel
    if not path.exists():
        errors.append(f"derived file missing: {rel}")
        continue
    if sha256(path) != r["sha256"]:
        errors.append(f"derived SHA mismatch: {rel}")
    if path.stat().st_size != int(r["bytes"]):
        errors.append(f"derived byte-size mismatch: {rel}")
    with path.open(encoding="utf-8", newline="") as f:
        actual_rows = max(0, sum(1 for _ in f) - 1)
    if actual_rows != int(r["row_count"]):
        errors.append(f"derived row-count mismatch: {rel}")
    for sid in split_ids(r["source_ids"]):
        if sid not in catalog:
            errors.append(f"{rel}: unknown derived source_id {sid}")
    generator = r["generator"]
    if generator != "manual_transcription_verified":
        gp = ROOT / generator
        if not gp.exists():
            errors.append(f"{rel}: generator missing: {generator}")

actual_derived = {
    str(p.relative_to(ROOT))
    for p in (ROOT / "data/derived").glob("*")
    if p.is_file()
}
if actual_derived != derived_paths:
    errors.append(
        "derived catalog coverage mismatch: "
        f"unregistered={sorted(actual_derived-derived_paths)} "
        f"missing={sorted(derived_paths-actual_derived)}"
    )

official_rows = read_csv("data/derived/stage1_official_inputs.csv")
official = {}
for r in official_rows:
    vid = r["value_id"]
    if vid in official:
        errors.append(f"duplicate official value_id: {vid}")
    official[vid] = r
    if r["source_id"] not in catalog:
        errors.append(f"{vid}: unknown official source_id {r['source_id']}")
    elif catalog[r["source_id"]]["status"] != "RAW_OFFICIAL":
        errors.append(f"{vid}: source is not RAW_OFFICIAL")
    if not r["source_locator"].strip():
        errors.append(f"{vid}: missing source locator")
    if r["extraction_method"] not in {
        "manual_transcription_verified",
        "machine_extracted_verified",
    }:
        errors.append(f"{vid}: invalid extraction method")

recovery_rows = read_csv("data/recovery/v6_recovered_values.csv")
# Primary key: value_id. Reject duplicates before dictionary construction.
recovery = {}
for r in recovery_rows:
    vid = r["value_id"]
    if vid in recovery:
        errors.append(f"duplicate recovery value_id: {vid}")
        continue
    recovery[vid] = r
release_sha_file = ROOT / "releases/V6_RECOVERED_2026-09-08.sha256"
release_sha_text = release_sha_file.read_text(encoding="utf-8")
for r in recovery_rows:
    if r["status"] != "RECOVERY_ONLY":
        errors.append(f"{r['value_id']}: recovery row not RECOVERY_ONLY")
    if r["source_artifact_sha256"] not in release_sha_text:
        errors.append(
            f"{r['value_id']}: recovery artifact SHA not recorded in release"
        )

inputs_rows = read_csv("research/stage1_filing_bound/inputs.csv")
inputs = {}
for r in inputs_rows:
    name = r["name"]
    if name in inputs:
        errors.append(f"duplicate stage1 input: {name}")
    inputs[name] = r

expected_ids = set(official) | {
    "threshold_score_power_0p5",
    "threshold_score_power_1p0",
    "threshold_score_power_2p0",
}
if set(inputs) != expected_ids:
    errors.append(
        f"stage1 input-id mismatch: got={sorted(inputs)}"
    )

for vid, r in official.items():
    if vid not in inputs:
        continue
    inp = inputs[vid]
    if inp["value"] != r["value"] or inp["unit"] != r["unit"]:
        errors.append(f"{vid}: stage1 input differs from official normalized value")
    if inp["source_id"] != r["source_id"]:
        errors.append(f"{vid}: source_id differs")
    if inp["evidence_status"] != "RAW_OFFICIAL":
        errors.append(f"{vid}: official input lacks RAW_OFFICIAL status")

for vid in expected_ids - set(official):
    if vid not in inputs or vid not in recovery:
        continue
    inp, rec = inputs[vid], recovery[vid]
    if inp["value"] != rec["value"] or inp["unit"] != rec["unit"]:
        errors.append(f"{vid}: stage1 input differs from recovery record")
    if inp["evidence_status"] != "RECOVERY_ONLY":
        errors.append(f"{vid}: recovered input lacks RECOVERY_ONLY status")

prov_rows = read_csv("data/input_provenance.csv")
prov = {}
for r in prov_rows:
    vid = r["value_id"]
    if vid in prov:
        errors.append(f"duplicate provenance value_id: {vid}")
    prov[vid] = r
if set(prov) != expected_ids:
    errors.append("input provenance does not cover stage1 inputs exactly")

for vid, inp in inputs.items():
    p = prov.get(vid)
    if not p:
        continue
    if p["value"] != inp["value"] or p["unit"] != inp["unit"]:
        errors.append(f"{vid}: provenance value/unit differs from input")
    if p["evidence_status"] != inp["evidence_status"]:
        errors.append(f"{vid}: provenance evidence status differs from input")
    if p["evidence_status"] == "RAW_OFFICIAL":
        sid = p["source_id"]
        if sid not in catalog:
            errors.append(f"{vid}: provenance source_id missing from catalog")
        else:
            if p["source_sha256"] != catalog[sid]["sha256"]:
                errors.append(f"{vid}: provenance source SHA differs from catalog")
            if p["source_file"] != catalog[sid]["raw_file"]:
                errors.append(f"{vid}: provenance source file differs from catalog")
    elif p["evidence_status"] == "RECOVERY_ONLY":
        if p["source_sha256"] not in release_sha_text:
            errors.append(f"{vid}: recovery provenance SHA not in release record")

claims_rows = read_csv("paper1/data/claim_registry.csv")
# Primary key: claim_id. Keep provenance validation fail-closed even though
# the Paper 1 claim validator independently checks this key as well.
claims = {}
for r in claims_rows:
    cid = r["claim_id"]
    if cid in claims:
        errors.append(f"duplicate claim_id: {cid}")
        continue
    claims[cid] = r
evidence_rows = read_csv("data/claim_evidence.csv")
by_claim = {}
known_values = set(prov) | set(recovery)
for r in evidence_rows:
    cid = r["claim_id"]
    by_claim.setdefault(cid, []).append(r)
    artifact = ROOT / r["evidence_artifact"]
    if not artifact.exists():
        errors.append(f"{cid}: evidence artifact missing: {r['evidence_artifact']}")
    for sid in split_ids(r["source_ids"]):
        if sid not in catalog:
            errors.append(f"{cid}: unknown evidence source_id: {sid}")
    for vid in split_ids(r["value_ids"]):
        if vid not in known_values:
            errors.append(f"{cid}: unknown evidence value_id: {vid}")

if set(by_claim) != set(claims):
    errors.append(
        "claim evidence coverage mismatch: "
        f"without_evidence={sorted(set(claims)-set(by_claim))} "
        f"orphan={sorted(set(by_claim)-set(claims))}"
    )

active_required = {
    "OBSERVED_PUBLIC",
    "ROBUSTNESS_FRONTIER_REPRODUCED",
    "READY_STATIC_ONLY",
    "SENSITIVITY_ONLY_REPRODUCED",
    "EXTERNAL_STAGE2_DIAGNOSTIC_REPRODUCED",
    "CROSS_PUBLICATION_POINT_CHECK_REPRODUCED",
    "MODEL_CONTINGENT_TRANSPORT_RELAXATION_REPRODUCED",
    "MODEL_CONTINGENT_RANK_BRIDGE_RELAXATION_REPRODUCED",
    "MODEL_CONTINGENT_RANK_TRANSPORT_BUDGET_REPRODUCED",
    "MODEL_CONTINGENT_RANK_EPSILON_SURFACE_REPRODUCED",
    "MODEL_CONTINGENT_RANK_ONE_SIDED_BRIDGE_REPRODUCED",
}
for cid, claim in claims.items():
    ev_statuses = {r["evidence_status"] for r in by_claim.get(cid, [])}
    if claim["status"] in active_required:
        if not ev_statuses & {
            "ACTIVE_OFFICIAL",
            "ACTIVE_REPRODUCED",
            "ACTIVE_REPRODUCED_SENSITIVITY",
            "ACTIVE_REPRODUCED_EXTERNAL_DIAGNOSTIC",
            "ACTIVE_REPRODUCED_POINT_CHECK",
            "ACTIVE_REPRODUCED_MODEL_CONTINGENT",
            "ACTIVE_REPRODUCED_MODEL_CONTINGENT_RANK_BRIDGE",
            "ACTIVE_REPRODUCED_MODEL_CONTINGENT_RANK_TRANSPORT",
            "ACTIVE_REPRODUCED_MODEL_CONTINGENT_RANK_EPSILON_SURFACE",
            "ACTIVE_REPRODUCED_MODEL_CONTINGENT_RANK_ONE_SIDED",
            "ACTIVE_STATE",
        }:
            errors.append(f"{cid}: active claim lacks active evidence")
        if ev_statuses <= {"RECOVERY_ONLY", "RECOVERY_GAP"}:
            errors.append(f"{cid}: active claim relies only on recovery evidence")
    if claim["status"] in {
        "DOCUMENTED_PRIOR_RUN_NOT_REPRODUCED",
        "SENSITIVITY_ONLY_RECOVERABLE",
    }:
        if not ev_statuses & {"RECOVERY_ONLY", "RECOVERY_GAP"}:
            errors.append(f"{cid}: recovery claim lacks recovery evidence")

tracked = set(
    subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files"], text=True
    ).splitlines()
)
required_data = {
    str(p.relative_to(ROOT))
    for p in DATA.rglob("*")
    if p.is_file()
}
untracked_data = sorted(required_data - tracked)
if untracked_data:
    errors.append(f"data files not tracked by git: {untracked_data}")

if errors:
    print("\n".join("ERROR: " + e for e in errors))
    sys.exit(1)

print(
    "provenance validation: OK "
    f"({len(catalog)} raw sources, {len(prov)} inputs, {len(claims)} claims)"
)
