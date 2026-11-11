# R100 experience-usage audit

## Scope

This is a zero-model, zero-simulation archive audit. The audited HEAD is
`19703e716799f6614f4cff4dfc43f043168a3a19`; no old ledger was reset. M70 remains
the eight-ID fixed-simulator WIN, and seven-or-fewer feasibility remains UNKNOWN.

Machine-readable evidence is in `selector_feedback_audit_v1.json`. The pre-run
context file hash is
`1a1bef461c1ffe2f59d7faa301228a5c98caacdb74e76085fb09c4e70279fa44`; the
post-run context file hash is
`8d8a9fadd8c182f51c0c4d307e18c18a63f483852abf24ab7a9fcb590bf0f317`. The rebuilt
14-record store hash is
`8ef050a0ab29ebfb3d1d495d4b8cf18eb99cb00a56a679edd38afa169e5c4997`.
The machine-readable audit hash is
`2d84dd7435b9f37f04c8f86fb5bef64df0dd08b1859b76240edb9f402d4d2995`.

## Context and decision trace

The pre-run 12-record context suggested M70 and R98 C1. Both R100 candidates
visibly selected M70 as primary parent and cited the same three observations:
M70's combined artillery/central/support success, R98 C1's 43 artillery hits
without a kill, and R98 C1's evidence that self-heal or some healing does not
prove survival.

All three adopted observations were in the frozen initial context. There is no
visible post-run re-import before C2; C2 used the original context plus C1 raw
feedback. Absence of additional citation is not proof that the readable archive
was not used. Hidden reasoning is UNKNOWN.

The post-run 14-record context added both R100 records, but suggested only M70
and R100 C1. It labeled R100 C2 `NOT_COMPLEMENTARY_AFTER_SELECTED_BRANCHES`
despite C2's better opening/routes and protected-#14 arrival. This is a branch
presentation/retrieval gap, not proof that the selector caused C2's outcome.

## Experience-by-experience audit

| Experience | Delivered | Adopted | Runtime result | Classification |
|---|---|---|---|---|
| Early actual interception | M70 context stated combined success, but did not isolate its `#4` block/kill subevent. | Both cards cited the M70 combined observation, not a specific early-interception observation. | C1 had no `#4` block and it leaked@1132. C2 deployed Melantha@841; she blocked@921 and killed@1111. | Evidence-visible-but-insufficiently-specific; adopted indirectly; C1 regression then C2 repair. |
| Healing delivery and artillery exposure | R98 C1 context supplied 43 hits/no kill and healing-not-survival evidence. | Both cards cited both observations. | C1 exposed new executors and had 6 deaths/7 dependency errors; C2 delayed Hbiscus, moved Ansel, delivered four 362 heals to Steward, but three 910 shells still killed Steward@3193. | Adopted but materially insufficient; no causal claim that moving one heal or one HP point would suffice. |
| Actual artillery output window | R98 C1 context supplied a large hit count without artillery death. | Both cards cited it and promised actual DAMAGE plus death. | C1 had 18 hits/5156.37 and artillery leaked@5759. C2 had 13 hits/3686.68 and artillery leaked@5759. | Adopted but output/closure chain not closed; later roles were truncated by earlier deaths in C1 and protected-#3 death in C2. |

## Parent-action regressions

The action diff shows C1 removed M70's Melantha and Spot and added Cardigan;
C2 removed only Spot and retained Melantha. The diff is advisory and does not
assign failure to one removal. The event evidence shows why the early-interception
dependency mattered: C1 lacked the observed `#4` block/kill, while C2 restored it.
Exact HP and continuous positions are UNKNOWN where not recorded, so cumulative
heal-minus-damage arithmetic is not used as a death predictor.

In C1, seven later action errors were classified as dependency failures after
executor death. That does not make every removed deployment the cause of the
first failure; the first observed failure was protected `#3` death@3161 after
upper shell exposure. In C2, the first observed failure remained protected `#3`
death@5353; artillery and central `#21/#22/#34` remained unresolved.

## Import fix

R100 records previously imported with `parent_plan_id=UNKNOWN` even though both
decision cards selected M70. The importer now reads the validation card's
`experience_selector_decision_record`, stores the visible decision separately
from observations, and derives `parent_plan_id` from `selected_parent.plan_id`.
The rebuilt R100 records now identify M70. The original closeout, plans, actions,
events, and hashes were not modified.

## Minimal feedback capability

`scripts/codex_experience_selector_v1.py audit` now emits:

- pre/post context membership and new-record isolation;
- advisory parent→candidate deployment/action diffs with explicit
  UNKNOWN-without-runtime-events boundaries;
- visible adopted and non-applicable experience rows with candidate results;
- no role whitelist/blacklist, no hard tactical gate, and no causal WIN/LOSS label.

Fake/stub tests cover decision/parent derivation, pre/post isolation, advisory
diffs, and observation/prediction separation. All 11 selector tests pass.

## Next-context suggestion, not an authorization

Next zero-model preparation should make early-interception and branch-repair
evidence explicit: include a compact M70 `#4` block/kill row and list R100 C2's
restored opening/routes separately from its unresolved artillery/central/`#3`
chain. Do not mandate Melantha, Spot, a healer, or M70's stations; do not copy
old frames as deadlines. A next real experiment remains unauthorized here.

If separately authorized, the next prompt should first regenerate and freeze the
context with those explicit rows and hashes, then permit one `gpt-6.1-sol/high`
CLI, 10 checks, 2 candidates, and 2 simulations with the same advisory selector
boundaries. The tactical question is whether explicit early-interception and
route-repair evidence changes role/structure exploration without prescribing any
operator; WIN remains full settlement, zero leaks, both protected arrivals, no
active enemies, legal union <=7, and no claim beyond this fixed simulator.
