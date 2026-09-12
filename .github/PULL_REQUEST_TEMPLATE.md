## Scope

- Issue(s):
- Research product/component:
- This PR changes scientific state: yes / no

## Decision-relevant research progress

Use `docs/research_progress_kpis.adoc`. For major research PRs, report the applicable canonical KPI deltas below. Use `N/A` rather than inventing a value.

- `voi_gap_advances`: gap_id(s), before -> after status/admissible set, and why the change is material:
- `identified_set_width_reduction`: parameter/unit, before width -> after width (or `UNBOUNDED -> [L,U]`):
- `assumption_burden_reduction`: named assumptions removed or strictly weakened:
- `policy_relations_resolved`: pair(s) moved from indeterminate to a robust relation:
- `independent_review_gates_satisfied`: before -> after:
- `recovery_only_claims_upgraded_or_retired`: claim_id(s), before -> after:

Snapshot helper:

```bash
python3 scripts/report_research_progress.py --ref <base-sha>
python3 scripts/report_research_progress.py
```

## Integrity / completeness

These are verification metrics, not evidence of scientific progress by themselves.

- Tests / reproduction targets:
- Manifest / source / derived-artifact / row counts, if relevant:
- Generated-output or bundle changes:

## Validation

- [ ] Relevant focused tests pass.
- [ ] Scientific-state/claim boundaries are unchanged or explicitly justified above.
- [ ] No source/file/row count is presented as scientific progress without a decision-relevant KPI change.
