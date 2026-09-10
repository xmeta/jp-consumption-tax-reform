#!/usr/bin/env python3
from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

if not __debug__:
    raise RuntimeError("scientific semantic regression tests require non-optimized Python")

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/validate_scientific_state.py"

STATE_FIELDS = [
    "component_id",
    "module_path",
    "display_name",
    "status",
    "phase",
    "maturity",
    "causal_status",
    "policy_usable",
    "evidence_paths",
    "output_paths",
    "blockers",
    "supersedes",
    "superseded_by",
    "active",
]
CLAIM_FIELDS = [
    "claim_id",
    "topic",
    "status",
    "evidence_scope",
    "allowed_claim",
    "forbidden_claim",
    "source",
]
EVIDENCE_FIELDS = [
    "claim_id",
    "evidence_status",
    "evidence_artifact",
    "source_ids",
    "value_ids",
    "locator",
    "note",
]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def base_state() -> dict[str, str]:
    return {
        "component_id": "a",
        "module_path": "research/a",
        "display_name": "A",
        "status": "SENSITIVITY_ONLY_REPRODUCED",
        "phase": "PHASE1_COMPLETE",
        "maturity": "SENSITIVITY_ONLY",
        "causal_status": "NOT_CAUSAL",
        "policy_usable": "false",
        "evidence_paths": "evidence-a.txt",
        "output_paths": "output-a.txt",
        "blockers": "true causal effect not identified",
        "supersedes": "",
        "superseded_by": "",
        "active": "true",
    }


def base_claim() -> dict[str, str]:
    return {
        "claim_id": "C1",
        "topic": "synthetic sensitivity diagnostic",
        "status": "SENSITIVITY_ONLY_REPRODUCED",
        "evidence_scope": "synthetic active evidence",
        "allowed_claim": "The result is a reproducible model-contingent sensitivity diagnostic.",
        "forbidden_claim": (
            "Do not call it a point-identified effect, confidence interval, "
            "causal effect, optimal policy, or reproduced main result."
        ),
        "source": "research/a/README.adoc",
    }


def base_evidence() -> dict[str, str]:
    return {
        "claim_id": "C1",
        "evidence_status": "ACTIVE_REPRODUCED_SENSITIVITY",
        "evidence_artifact": "output-a.txt",
        "source_ids": "",
        "value_ids": "",
        "locator": "fixture",
        "note": "active fixture evidence",
    }


def write_fixture(root: Path) -> None:
    (root / "research/a").mkdir(parents=True, exist_ok=True)
    (root / "research/a/README.adoc").write_text(
        "SENSITIVITY_ONLY_REPRODUCED\n", encoding="utf-8"
    )
    (root / "research/a/run.py").write_text("print('a')\n", encoding="utf-8")
    (root / "evidence-a.txt").write_text("evidence\n", encoding="utf-8")
    (root / "output-a.txt").write_text("output\n", encoding="utf-8")
    (root / "STATUS.adoc").write_text(
        "SENSITIVITY_ONLY_REPRODUCED\n", encoding="utf-8"
    )
    write_csv(root / "data/scientific_state.csv", STATE_FIELDS, [base_state()])
    write_csv(root / "paper1/data/claim_registry.csv", CLAIM_FIELDS, [base_claim()])
    write_csv(root / "data/claim_evidence.csv", EVIDENCE_FIELDS, [base_evidence()])


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def mutate_rows(path: Path, fields: list[str], fn) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fn(rows)
    write_csv(path, fields, rows)


def scenario(tmp: str, name: str) -> Path:
    root = Path(tmp) / name
    write_fixture(root)
    return root


with tempfile.TemporaryDirectory() as tmp:
    root = scenario(tmp, "valid")
    result = run_validator(root)
    check(result.returncode == 0, f"valid semantic fixture failed:\n{result.stdout}{result.stderr}")

    root = scenario(tmp, "policy-state")
    mutate_rows(
        root / "data/scientific_state.csv",
        STATE_FIELDS,
        lambda rows: rows[0].__setitem__("policy_usable", "true"),
    )
    result = run_validator(root)
    check(result.returncode != 0, "non-READY policy_usable=true unexpectedly passed")
    check(
        "identification:" in result.stdout and "policy_usable=true" in result.stdout,
        "policy-state identification diagnostic missing",
    )

    root = scenario(tmp, "causal-state")
    mutate_rows(
        root / "data/scientific_state.csv",
        STATE_FIELDS,
        lambda rows: rows[0].__setitem__("causal_status", "CAUSAL_IDENTIFIED"),
    )
    result = run_validator(root)
    check(result.returncode != 0, "sensitivity-only CAUSAL_IDENTIFIED unexpectedly passed")
    check(
        "identification:" in result.stdout and "CAUSAL_IDENTIFIED" in result.stdout,
        "causal-state identification diagnostic missing",
    )

    root = scenario(tmp, "ready-blocker")

    def make_ready(rows):
        rows[0]["status"] = "READY"
        rows[0]["maturity"] = "READY"

    mutate_rows(root / "data/scientific_state.csv", STATE_FIELDS, make_ready)
    (root / "STATUS.adoc").write_text("READY\n", encoding="utf-8")
    result = run_validator(root)
    check(result.returncode != 0, "READY state with unresolved blocker unexpectedly passed")
    check(
        "identification:" in result.stdout and "READY component must not list" in result.stdout,
        "READY-blocker diagnostic missing",
    )

    root = scenario(tmp, "sensitivity-overclaim")
    mutate_rows(
        root / "paper1/data/claim_registry.csv",
        CLAIM_FIELDS,
        lambda rows: rows[0].__setitem__(
            "allowed_claim", "This is an empirical bound on the policy effect."
        ),
    )
    result = run_validator(root)
    check(result.returncode != 0, "SENSITIVITY_ONLY empirical-bound overclaim unexpectedly passed")
    check(
        "claim:" in result.stdout and "SENSITIVITY_ONLY" in result.stdout,
        "sensitivity claim diagnostic missing",
    )

    root = scenario(tmp, "causal-overclaim")
    mutate_rows(
        root / "paper1/data/claim_registry.csv",
        CLAIM_FIELDS,
        lambda rows: rows[0].__setitem__(
            "allowed_claim", "The intervention has a causal effect on the outcome."
        ),
    )
    result = run_validator(root)
    check(result.returncode != 0, "noncausal causal-effect claim unexpectedly passed")
    check(
        "claim:" in result.stdout and "causal" in result.stdout.lower(),
        "causal claim diagnostic missing",
    )

    root = scenario(tmp, "policy-overclaim")
    mutate_rows(
        root / "paper1/data/claim_registry.csv",
        CLAIM_FIELDS,
        lambda rows: rows[0].__setitem__("allowed_claim", "This is the optimal policy."),
    )
    result = run_validator(root)
    check(result.returncode != 0, "policy_usable=false optimal-policy claim unexpectedly passed")
    check(
        "claim:" in result.stdout and "policy_usable=false" in result.stdout,
        "policy claim diagnostic missing",
    )

    root = scenario(tmp, "not-ready-point")

    def make_not_ready_point(rows):
        rows[0]["status"] = "NOT_READY"
        rows[0]["allowed_claim"] = "The unresolved quantity is 2.5%."

    mutate_rows(root / "paper1/data/claim_registry.csv", CLAIM_FIELDS, make_not_ready_point)
    result = run_validator(root)
    check(result.returncode != 0, "NOT_READY numeric point estimate unexpectedly passed")
    check(
        "claim:" in result.stdout and "headline point estimate" in result.stdout,
        "NOT_READY point-estimate diagnostic missing",
    )

    root = scenario(tmp, "per-claim-guard")
    mutate_rows(
        root / "paper1/data/claim_registry.csv",
        CLAIM_FIELDS,
        lambda rows: rows[0].__setitem__(
            "allowed_claim", "This is a reproduced main result."
        ),
    )
    result = run_validator(root)
    check(result.returncode != 0, "per-claim forbidden vocabulary overlap unexpectedly passed")
    check(
        "claim:" in result.stdout and "per-claim forbidden term" in result.stdout,
        "per-claim guard diagnostic missing",
    )

    root = scenario(tmp, "recovery-only")
    mutate_rows(
        root / "data/claim_evidence.csv",
        EVIDENCE_FIELDS,
        lambda rows: rows[0].__setitem__("evidence_status", "RECOVERY_ONLY"),
    )
    result = run_validator(root)
    check(result.returncode != 0, "active reproduced recovery-only claim unexpectedly passed")
    check(
        "provenance:" in result.stdout and "RECOVERY_ONLY" in result.stdout,
        "recovery-only provenance diagnostic missing",
    )

print(
    "scientific semantic invariant tests: OK "
    "(identification, claim, policy, causal, recovery-only)"
)
