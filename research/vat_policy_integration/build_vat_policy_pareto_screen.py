#!/usr/bin/env python3
"""Screen VAT policy scenarios for robust Pareto dominance.

This is an identification-aware screen, not a welfare optimizer. A scenario can
robustly dominate another only when every required objective is numerically
bounded for both scenarios and the interval ordering establishes no-worse on
all objectives with at least one strict improvement.
"""
from pathlib import Path
import argparse
import csv
import io

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OBJECTIVES = HERE / "pareto_objectives.csv"
SUMMARY = ROOT / "data/derived/vat_policy_scenario_summary.csv"
SCREEN = ROOT / "data/derived/vat_policy_pareto_screen.csv"
PAIRWISE = ROOT / "data/derived/vat_policy_pareto_pairwise.csv"

EXPECTED_SCENARIOS = {
    "current_8_10", "reduced_5", "zero_rate_admin_retained", "full_abolition",
    "full_abolition_jgb", "full_abolition_income_tax",
    "full_abolition_asset_tax", "full_abolition_mixed",
}

def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def bounded(row, objective):
    lo_col = objective["value_min_column"]
    hi_col = objective["value_max_column"]
    status_col = objective["status_column"]
    if not status_col or status_col not in row:
        raise RuntimeError(f"missing objective status column: {status_col}")
    if not lo_col or not hi_col:
        return None
    lo = row.get(lo_col, "")
    hi = row.get(hi_col, "")
    if lo == "" or hi == "":
        return None
    if row[status_col].startswith("NOT_"):
        raise RuntimeError(f"numeric interval conflicts with status {row[status_col]}")
    return float(lo), float(hi)


def no_worse(a, b, direction):
    if direction == "minimize":
        return a[1] <= b[0]
    if direction == "maximize":
        return a[0] >= b[1]
    raise RuntimeError(f"unknown objective direction: {direction}")


def strictly_better(a, b, direction):
    if direction == "minimize":
        return a[1] < b[0]
    if direction == "maximize":
        return a[0] > b[1]
    raise RuntimeError(f"unknown objective direction: {direction}")


def compare(a_row, b_row, objectives):
    missing = []
    intervals = []
    for objective in objectives:
        if objective["required_for_headline"].lower() != "true":
            continue
        a = bounded(a_row, objective)
        b = bounded(b_row, objective)
        if a is None or b is None:
            missing.append(objective["objective_id"])
            continue
        intervals.append((objective, a, b))

    if missing:
        return "INDETERMINATE_MISSING_REQUIRED_OBJECTIVES", missing, intervals

    a_dominates = all(no_worse(a, b, obj["direction"]) for obj, a, b in intervals)
    b_dominates = all(no_worse(b, a, obj["direction"]) for obj, a, b in intervals)
    a_strict = any(strictly_better(a, b, obj["direction"]) for obj, a, b in intervals)
    b_strict = any(strictly_better(b, a, obj["direction"]) for obj, a, b in intervals)
    if a_dominates and a_strict:
        return "A_ROBUSTLY_DOMINATES_B", [], intervals
    if b_dominates and b_strict:
        return "B_ROBUSTLY_DOMINATES_A", [], intervals
    return "NO_ROBUST_DOMINANCE", [], intervals


def build():
    objectives = read(OBJECTIVES)
    summary_rows = read(SUMMARY)
    summary = {row["scenario_id"]: row for row in summary_rows}
    if set(summary) != EXPECTED_SCENARIOS:
        raise RuntimeError("unexpected VAT scenario set")
    if len(objectives) != 8:
        raise RuntimeError("unexpected Pareto objective count")
    if not all(o["required_for_headline"].lower() == "true" for o in objectives):
        raise RuntimeError("all committed Pareto objectives must remain headline-required")

    pairwise = []
    pair_results = {sid: [] for sid in EXPECTED_SCENARIOS}
    ordered = sorted(EXPECTED_SCENARIOS)
    for i, a_id in enumerate(ordered):
        for b_id in ordered[i + 1:]:
            status, missing, intervals = compare(summary[a_id], summary[b_id], objectives)
            common = [obj["objective_id"] for obj, _, _ in intervals]
            pairwise.append({
                "scenario_a": a_id,
                "scenario_b": b_id,
                "dominance_status": status,
                "common_bounded_required_objectives": ";".join(common),
                "missing_required_objectives": ";".join(missing),
                "normative_weights_used": "false",
                "interpretation": (
                    "No Pareto conclusion: at least one required objective lacks a numerical bound."
                    if missing else
                    "Robust interval dominance evaluated without scalar welfare weights."
                ),
            })
            pair_results[a_id].append((b_id, status, "A"))
            pair_results[b_id].append((a_id, status, "B"))

    screen = []
    for sid in ordered:
        row = summary[sid]
        available = []
        missing = []
        for objective in objectives:
            interval = bounded(row, objective)
            (available if interval is not None else missing).append(objective["objective_id"])

        dominated_by = []
        unresolved = False
        for other, status, side in pair_results[sid]:
            if status == "INDETERMINATE_MISSING_REQUIRED_OBJECTIVES":
                unresolved = True
            elif status == "A_ROBUSTLY_DOMINATES_B" and side == "B":
                dominated_by.append(other)
            elif status == "B_ROBUSTLY_DOMINATES_A" and side == "A":
                dominated_by.append(other)

        if dominated_by:
            classification = "ROBUSTLY_DOMINATED"
        elif unresolved:
            classification = "UNRESOLVED_NOT_ENOUGH_IDENTIFIED_OBJECTIVES"
        else:
            classification = "ROBUSTLY_NON_DOMINATED"

        screen.append({
            "scenario_id": sid,
            "scenario_label": row["scenario_label"],
            "required_objective_count": len(objectives),
            "bounded_required_objective_count": len(available),
            "bounded_required_objectives": ";".join(available),
            "missing_required_objectives": ";".join(missing),
            "pareto_classification": classification,
            "robustly_dominated_by": ";".join(sorted(dominated_by)),
            "normative_weights_used": "false",
            "headline_optimum_claim_allowed": "false",
        })

    if len(pairwise) != 28 or len(screen) != 8:
        raise RuntimeError("unexpected Pareto output dimensions")
    return screen, pairwise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    screen, pairwise = build()
    outputs = [(SCREEN, render(screen)), (PAIRWISE, render(pairwise))]
    if args.check:
        stale = [
            str(path.relative_to(ROOT))
            for path, expected in outputs
            if not path.exists() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            raise SystemExit("stale generated artifacts: " + ", ".join(stale))
        print(
            "VAT Pareto screen: current "
            "(8 scenarios; 28 pairwise comparisons; no scalar welfare weights)"
        )
        return
    for path, expected in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
