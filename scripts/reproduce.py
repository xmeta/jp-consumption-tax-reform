#!/usr/bin/env python3
"""Stable reproduction entrypoint for the research repository.

Every target is an ordered, fail-fast sequence.  CI calls this file directly so
the local and CI reproduction paths cannot drift apart.
"""
from __future__ import annotations

import argparse
import fnmatch
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCE_INTEGRITY = (
    ("scripts/build_source_catalog.py",),
    ("scripts/test_reproduce.py",),
)

VAT = (
    ("scripts/extract_meti_vat_internal_hours.py",),
    ("scripts/test_meti_vat_internal_hours.py",),
    ("scripts/build_meti_vat_hours_source_lineage.py",),
    ("scripts/test_meti_vat_hours_source_lineage.py",),
    ("scripts/build_vat_transition_system_subsidy_bounds.py",),
    ("scripts/test_vat_transition_system_subsidy_bounds.py",),
    ("scripts/build_rieti_vat_threshold_structural_bridge.py",),
    ("scripts/test_rieti_vat_threshold_structural_bridge.py",),
    ("scripts/build_ichikawa_2019_vat_10m_threshold_bridge.py",),
    ("scripts/test_ichikawa_2019_vat_10m_threshold_bridge.py",),
    ("scripts/build_jcci_invoice_network_distortion_bridge.py",),
    ("scripts/test_jcci_invoice_network_distortion_bridge.py",),
    ("scripts/build_smea_fy2025_invoice_transaction_bridge.py",),
    ("scripts/test_smea_fy2025_invoice_transaction_bridge.py",),
    ("scripts/build_bsws_2019_industry_hourly_wage_bridge.py",),
    ("scripts/build_meti_vat_internal_labor_cost_bridge.py",),
    ("scripts/test_bsws_vat_wage_bridge.py",),
    ("scripts/extract_vat_compliance_evidence.py",),
    ("scripts/test_vat_compliance_evidence.py",),
    ("research/vat_compliance_productivity/run_vat_compliance_productivity.py",),
    ("research/vat_compliance_productivity/test_vat_compliance_productivity.py",),
    ("research/vat_policy_integration/build_vat_fiscal_replacement_reference.py",),
    ("research/vat_policy_integration/test_vat_fiscal_replacement_reference.py",),
    ("research/vat_policy_integration/build_jgb_debt_gdp_reference.py",),
    ("research/vat_policy_integration/test_jgb_debt_gdp_reference.py",),
    ("scripts/build_estat_2024_annual_income_decile_expenditure_diagnostic.py",),
    ("scripts/test_estat_2024_annual_income_decile_expenditure_diagnostic.py",),
    ("scripts/build_estat_objective_rank_household_margin_audit.py",),
    ("scripts/test_estat_objective_rank_household_margin_audit.py",),
    ("scripts/build_vat_household_tax_content_envelope.py",),
    ("scripts/test_vat_household_tax_content_envelope.py",),
    ("research/vat_policy_integration/run_vat_policy_scenario_matrix.py",),
    ("research/vat_policy_integration/test_vat_policy_scenario_matrix.py",),
)

INCOME_TAX = (
    ("scripts/extract_estat_income_tax_tables.py",),
    ("scripts/test_estat_income_tax_extracts.py",),
    ("scripts/build_income_tax_decile_instruments.py",),
    ("scripts/extract_estat_f71911_bridge.py",),
    ("scripts/test_estat_f71911_bridge.py",),
    ("scripts/extract_estat_rank_bridge_diagnostics.py",),
    ("scripts/test_estat_rank_bridge_diagnostics.py",),
    ("scripts/build_income_tax_2026_statutory_parameters.py",),
    ("scripts/test_income_tax_2026_statutory_parameters.py",),
    ("scripts/extract_nta_table17_and_f71551.py",),
    ("scripts/test_nta_table17_and_f71551.py",),
    ("scripts/extract_nta_stage2_holdout.py",),
    ("scripts/test_nta_stage2_holdout.py",),
    ("scripts/extract_nta_final_return_processing_reconciliation.py",),
    ("scripts/test_nta_final_return_processing_reconciliation.py",),
    ("scripts/extract_nta_shinkoku_income_class_primary_type.py",),
    ("scripts/test_nta_shinkoku_income_class_primary_type.py",),
    ("scripts/extract_nta_positive_balance_tax_flow.py",),
    ("scripts/test_nta_positive_balance_tax_flow.py",),
    ("scripts/extract_nta_calculated_tax_denominator_audit.py",),
    ("scripts/test_nta_calculated_tax_denominator_audit.py",),
    ("scripts/extract_nta_private_salary_taxpayer_status.py",),
    ("scripts/test_nta_private_salary_taxpayer_status.py",),
    ("scripts/extract_nta_annual_income_class_filing_status.py",),
    ("scripts/test_nta_annual_income_class_filing_status.py",),
    ("scripts/extract_nta_salary_processing_status.py",),
    ("scripts/test_nta_salary_processing_status.py",),
    ("scripts/extract_nta_salary_return_overlap.py",),
    ("scripts/test_nta_salary_return_overlap.py",),
    ("scripts/extract_nta_salary_receipt_return_bridge.py",),
    ("scripts/test_nta_salary_receipt_return_bridge.py",),
    ("scripts/build_nta_salary_filing_bridge_source_matrix.py",),
    ("scripts/test_nta_salary_filing_bridge_source_matrix.py",),
    ("scripts/extract_nta_salary_source_system_coverage.py",),
    ("scripts/test_nta_salary_source_system_coverage.py",),
    ("scripts/test_filed_processed_terminology.py",),
    ("scripts/extract_public_sector_person_coverage.py",),
    ("scripts/test_public_sector_person_coverage.py",),
    ("scripts/extract_nta_withholding_person_series.py",),
    ("scripts/test_nta_withholding_person_series.py",),
    ("research/income_tax_pseudofiler/run_pseudofiler_core.py",),
    ("research/income_tax_pseudofiler/test_pseudofiler_core.py",),
    ("research/income_tax_partial_identification/run_replacement_transport_lp.py",),
    ("research/income_tax_partial_identification/test_replacement_transport_lp.py",),
    ("research/income_tax_partial_identification/run_rank_bridge_lp_v2.py",),
    ("research/income_tax_partial_identification/test_rank_bridge_lp_v2.py",),
    ("research/income_tax_partial_identification/run_rank_bridge_lp_v3.py",),
    ("research/income_tax_partial_identification/test_rank_bridge_lp_v3.py",),
    ("research/income_tax_partial_identification/run_rank_epsilon_surface_v4.py",),
    ("research/income_tax_partial_identification/test_rank_epsilon_surface_v4.py",),
    ("research/income_tax_partial_identification/test_self_assessed_balance_schema_migration.py",),
    ("research/income_tax_partial_identification/test_rank_one_sided_bridge_v5_prespec.py",),
    ("research/income_tax_partial_identification/run_rank_one_sided_bridge_v5.py",),
    ("research/income_tax_partial_identification/test_rank_one_sided_bridge_v5.py",),
)

PROVENANCE = (
    ("scripts/build_derived_catalog.py",),
    ("scripts/build_input_provenance.py",),
    ("scripts/build_stage1_inputs.py",),
    ("scripts/validate_provenance.py",),
)

STAGE1 = (
    ("research/stage1_filing_bound/46_income_tax_stage1_population_overlap.py",),
    ("research/stage1_filing_bound/47_income_tax_stage1_contamination_frontier.py",),
    ("research/stage1_filing_bound/48_income_tax_stage1_untracked_frontier.py",),
    ("research/stage1_filing_bound/49_income_tax_stage1_frontier_grid.py",),
    ("research/stage1_filing_bound/test_stage1_population_overlap.py",),
    ("research/stage1_filing_bound/test_stage1_contamination_frontier.py",),
    ("research/stage1_filing_bound/test_stage1_untracked_frontier.py",),
    ("research/stage1_filing_bound/test_stage1_frontier_grid.py",),
)

PAPER1_GENERATORS = (
    ("paper1/scripts/generate_stage1_attributes.py",),
    ("paper1/scripts/generate_frontier_table.py",),
    ("paper1/scripts/generate_transport_lp_table.py",),
    ("paper1/scripts/generate_rank_bridge_v2_table.py",),
    ("paper1/scripts/generate_rank_bridge_v3_table.py",),
    ("paper1/scripts/generate_rank_epsilon_v4_table.py",),
    ("paper1/scripts/generate_rank_one_sided_v5_table.py",),
)

PAPER1 = (
    *STAGE1,
    *PAPER1_GENERATORS,
    *((path, "--check") for (path,) in PAPER1_GENERATORS),
    ("paper1/scripts/validate_claim_registry.py",),
)

INTEGRITY = (
    ("scripts/validate_repo.py",),
    ("scripts/check_manifest.py",),
    ("scripts/test_check_clean_tree.py",),
    ("scripts/check_clean_tree.py",),
)

TARGETS = {
    "source-integrity": SOURCE_INTEGRITY,
    "vat": VAT,
    "income-tax": INCOME_TAX,
    "provenance": PROVENANCE,
    "paper1": PAPER1,
    "integrity": INTEGRITY,
}
ALL_ORDER = (
    "source-integrity",
    "vat",
    "income-tax",
    "provenance",
    "paper1",
    "docs",
    "integrity",
)

# Only files that are outputs of the commands above belong here. Clean-room
# deliberately keeps raw/recovery/config/spec inputs intact.
CLEAN_ROOM_GLOBS = (
    "data/source_catalog.csv",
    "data/derived/*.csv",
    "data/derived_catalog.csv",
    "data/input_provenance.csv",
    "research/income_tax_pseudofiler/pseudofiler_*.csv",
    "research/income_tax_partial_identification/replacement_transport_lp_endpoints.csv",
    "research/income_tax_partial_identification/replacement_transport_lp_feasibility.csv",
    "research/income_tax_partial_identification/replacement_transport_lp_minimum_*.csv",
    "research/income_tax_partial_identification/rank_bridge_lp_v2_class_inputs.csv",
    "research/income_tax_partial_identification/rank_bridge_lp_v2_class_rank_overlap.csv",
    "research/income_tax_partial_identification/rank_bridge_lp_v2_endpoints.csv",
    "research/income_tax_partial_identification/rank_bridge_lp_v2_feasibility.csv",
    "research/income_tax_partial_identification/rank_bridge_lp_v2_minimum_*.csv",
    "research/income_tax_partial_identification/rank_bridge_lp_v3_analytical_rate_floor.csv",
    "research/income_tax_partial_identification/rank_bridge_lp_v3_endpoints.csv",
    "research/income_tax_partial_identification/rank_bridge_lp_v3_minimum_*.csv",
    "research/income_tax_partial_identification/rank_bridge_lp_v3_transport_plans.csv",
    "research/income_tax_partial_identification/rank_bridge_lp_v3_zero_discrepancy_threshold.csv",
    "research/income_tax_partial_identification/rank_epsilon_surface_v4_endpoints.csv",
    "research/income_tax_partial_identification/rank_epsilon_surface_v4_feasibility.csv",
    "research/income_tax_partial_identification/rank_epsilon_surface_v4_summary.csv",
    "research/income_tax_partial_identification/rank_one_sided_bridge_v5_endpoints.csv",
    "research/income_tax_partial_identification/rank_one_sided_bridge_v5_minimum_*.csv",
    "research/income_tax_partial_identification/rank_one_sided_bridge_v5_transport_plans.csv",
    "research/income_tax_partial_identification/rank_one_sided_bridge_v5_zero_violation_threshold.csv",
    "research/stage1_filing_bound/inputs.csv",
    "research/stage1_filing_bound/results.csv",
    "research/stage1_filing_bound/contamination_frontier.csv",
    "research/stage1_filing_bound/untracked_frontier*.csv",
    "paper1/data/stage1_attributes.adoc",
    "paper1/data/stage1_frontier_table.csv",
    "paper1/data/transport_lp_summary_table.csv",
    "paper1/data/rank_bridge_v2_summary_table.csv",
    "paper1/data/rank_bridge_v3_frontier_table.csv",
    "paper1/data/rank_epsilon_v4_overall_table.csv",
    "paper1/data/rank_one_sided_v5_overall_table.csv",
)


def _display(argv: list[str]) -> str:
    return shlex.join(argv)


def _run(argv: list[str], root: Path, dry_run: bool) -> None:
    print(f"+ {_display(argv)}", flush=True)
    if not dry_run:
        subprocess.run(argv, cwd=root, check=True)


def _run_python(command: tuple[str, ...], root: Path, dry_run: bool) -> None:
    _run([sys.executable, *command], root, dry_run)


def _check_clean(root: Path, dry_run: bool) -> None:
    _run_python(("scripts/check_clean_tree.py",), root, dry_run)


def _run_docs(root: Path, dry_run: bool) -> None:
    asciidoctor = shutil.which("asciidoctor")
    if asciidoctor is None:
        if dry_run:
            asciidoctor = "asciidoctor"
        else:
            raise SystemExit(
                "asciidoctor is required for the docs target; "
                "install Ruby 3.3 and `gem install asciidoctor --no-document`"
            )
    output = Path(tempfile.gettempdir()) / "jp-consumption-tax-reform-paper1.html"
    _run([asciidoctor, "-o", str(output), "paper1/index.adoc"], root, dry_run)


def run_target(
    target: str,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
    verify_clean: bool = True,
) -> None:
    print(f"== reproduce: {target} ==", flush=True)
    if target == "docs":
        _run_docs(root, dry_run)
    elif target in TARGETS:
        for command in TARGETS[target]:
            _run_python(command, root, dry_run)
    else:
        raise ValueError(f"unknown concrete target: {target}")
    if verify_clean and target != "integrity":
        _check_clean(root, dry_run)


def run_all(*, root: Path = ROOT, dry_run: bool = False) -> None:
    for target in ALL_ORDER:
        run_target(target, root=root, dry_run=dry_run, verify_clean=False)


def _tracked_paths(root: Path) -> list[str]:
    raw = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"])
    return [item.decode("utf-8") for item in raw.split(b"\0") if item]


def _clean_room_outputs(root: Path, dry_run: bool) -> list[str]:
    selected = sorted(
        rel
        for rel in _tracked_paths(root)
        if any(fnmatch.fnmatchcase(rel, pattern) for pattern in CLEAN_ROOM_GLOBS)
    )
    if not selected:
        raise SystemExit("clean-room output set is empty")
    print(f"clean-room: deleting {len(selected)} tracked generated outputs", flush=True)
    for rel in selected:
        print(f"- {rel}", flush=True)
        if not dry_run:
            (root / rel).unlink()
    return selected


def run_clean_room(*, dry_run: bool = False) -> None:
    _check_clean(ROOT, dry_run)
    if dry_run:
        print("+ git worktree add --detach <temporary-worktree> HEAD")
        print("clean-room: delete tracked generated outputs")
        print(f"+ {sys.executable} scripts/reproduce.py all")
        print("+ git diff --exit-code && git status --porcelain")
        return

    parent = Path(tempfile.mkdtemp(prefix="jp-tax-reproduce-"))
    worktree = parent / "worktree"
    try:
        subprocess.run(
            ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(worktree), "HEAD"],
            check=True,
        )
        _clean_room_outputs(worktree, False)
        subprocess.run(
            [sys.executable, "scripts/reproduce.py", "all"],
            cwd=worktree,
            check=True,
        )
        subprocess.run(["git", "-C", str(worktree), "diff", "--exit-code"], check=True)
        _check_clean(worktree, False)
        print("clean-room reproduction: OK", flush=True)
    finally:
        if worktree.exists():
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(worktree)],
                check=False,
            )
        shutil.rmtree(parent, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce research products with the same entrypoints used by CI."
    )
    parser.add_argument(
        "target",
        nargs="?",
        choices=(*TARGETS, "docs", "all", "clean-room"),
        help="research product or gate to reproduce",
    )
    parser.add_argument("--list", action="store_true", help="list available targets and exit")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the deterministic command sequence without executing it",
    )
    args = parser.parse_args()

    if args.list:
        for target in (*TARGETS, "docs", "all", "clean-room"):
            print(target)
        return
    if args.target is None:
        parser.error("target is required unless --list is used")

    if args.target == "all":
        run_all(dry_run=args.dry_run)
    elif args.target == "clean-room":
        run_clean_room(dry_run=args.dry_run)
    else:
        run_target(args.target, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
