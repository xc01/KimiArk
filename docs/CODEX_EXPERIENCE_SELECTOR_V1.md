`scripts/codex_experience_selector_v1.py` is a dry-run, zero-model archive helper. It imports verified
M70/R94–R105 fixed-simulator candidate summaries, preserves complementary branches by observed evidence,
and emits a bounded context package. It does not start Codex, call a model, run a simulation, alter tactics,
or authorize any experiment.

```bash
python scripts/codex_experience_selector_v1.py import
python scripts/codex_experience_selector_v1.py select \
  --goal 'Seven-ID fixed-simulator experiment' --k 7 \
  --tags ARTILLERY_KILL SUPPORT_DELIVERY PROTECTED_ROUTE CENTRAL_INTERCEPT \
  --output output/codex_experience_selector_v1/context.json
python scripts/codex_experience_selector_v1.py rebuild-check --target /tmp/rebuilt.jsonl
python scripts/codex_experience_selector_v1.py audit \
  --pre-context path/pre_context.json --post-context path/post_context.json \
  --store output/codex_experience_selector_v1/experience_records.jsonl \
  --closeout path/closeout_report_v1.json --parent-plan path/parent_plan_snapshot.json \
  --output path/selector_feedback_audit_v1.json
```

The store records identities, hashes, paths, observed summaries, model predictions, unknowns, and evidence
categories. `WIN_REFERENCE`, `ARTILLERY_KILL`, `ARTILLERY_OUTPUT`, `SUPPORT_DELIVERY`,
`PROTECTED_ROUTE`, `CENTRAL_INTERCEPT`, and `ROADBLOCK_CLEARANCE` are retained independently. A WIN does not
erase partial advances, and a LOSS is not a uniform negative label. Unknown fields remain UNKNOWN. Mechanics
other than `m38b-2781-animation-speed-v1` are excluded from current selection.

M70 can be returned as an eight-ID `REFERENCE_TO_EDIT` for a K<=7 task. Its context marks `must_reduce: true`
and never reports it as a seven-ID candidate. Deployment unions count same-ID redeployment once and include
robots. Model validation-card predictions stay separate from observed events. Identity/hash problems are
reference-only. The selector is advisory, may be overridden, and must not be treated as reward learning,
RL, model training, or a global tactical rule.

The `audit` command adds a derived feedback report. It compares pre-run and post-run context membership,
emits advisory parent-action diffs, and records visible adopted/non-applicable experience observations beside
candidate results. The audit never changes the legal role set, adds hard tactical gates, or converts a global
LOSS into a negative label for every local decision. It keeps exact HP, continuous positions, and hidden
reasoning UNKNOWN where evidence is absent.
