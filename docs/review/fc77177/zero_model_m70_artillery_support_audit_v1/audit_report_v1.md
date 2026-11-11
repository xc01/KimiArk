# M70 artillery/support zero-model audit v1

## Boundary

This is a read-only audit of existing fixed-simulator archives. It used no model CLI, no simulation, no `run_simulation`, and created no new `STARTED`. It does not claim real-game, faithful, robust, probabilistic, seven-ID-impossible, or global-minimum results. `OBSERVED` means an archive event/static identity was verified; `HYPOTHESIS` remains untested.

## Identity

HEAD/remote at audit start: `8909545f503ae9ca5325027587d51eaa568df2b3`. Identities were checked by raw plan/action/event-gzip SHA-256 and gzip restored-event SHA-256.

| Case | Plan ID | Plan | Action | Events.gzip |
|---|---|---|---|---|
| M70 8-ID | `R8_7_GPT_M70_V1` | `fe265c2837d9…` | `c6248dd2da3e…` | `d8ea88ad9499…` |
| R94 C1 | `R94_SOL_HIGH_SEVEN_RETRY2_001` | `efd06045343e…` | `39a8131fd71e…` | `70607b8e73ef…` |
| R95 C1 | `R95_SOL_HIGH_SEVEN_RETRY3_001` | `61354112963e…` | `1e4869141340…` | `b0a06beeb0a9…` |
| R95 C2 | `R95_SOL_HIGH_SEVEN_RETRY3_002` | `146cbdee4f56…` | `d2713ef9e11b…` | `61b5e262a7e8…` |
| R96 C1 | `R96_SOL_HIGH_SEVEN_SUPPORT_COVERAGE_001` | `983b254a31a3…` | `ec088af35095…` | `26b151328b44…` |
| R96 C2 | `R96_SOL_HIGH_SEVEN_SUPPORT_COVERAGE_002` | `48fd440f6575…` | `ddb04d428658…` | `506405bc0301…` |

## Core finding

M70's artillery success was not merely “Steward attacked.” Its first output tile was runtime `(7,5)`, and both Ansel runtime `(6,5) DOWN` and Hibiscus runtime `(6,2) UP` covered it. Steward hit the artillery 45 times for `13227.21`; the artillery died at `4273`; no operator died. This is `OBSERVED`.

Whether dual support coverage is necessary or sufficient for a seven-ID plan is `HYPOTHESIS`. The observed seven-ID losses show that changing timing or roster without establishing actual coverage can leave the failure unchanged:

- R94: Steward runtime `(7,2)`; only Ansel covered. Steward hit 23 times for `6626.06`, then died at `3343`.
- R95 C1/C2: Steward runtime `(7,2)`; Hibiscus did not cover despite changed deployment/skill timing. Ansel was the only relevant healer, with one heal at `2959`; Steward hit 16 times for `4658.17`, then died at `3043` in both versions.
- R96 C1: Steward runtime `(6,5)`; Hibiscus geometrically covered it but died at `1571`, before Steward deployed at `2071`. Steward hit 8 times for `2216.99`, then died at `2443`.
- R96 C2: Steward runtime `(6,5)`; both medics geometrically covered it. Hibiscus actually healed Steward `372.6` at `2476`, but Ansel died at `2261` after shells locked `(5,5)` then `(5,6)`. Steward still died at `2561` after 11 hits for `3188.48`.

Exact HP at arbitrary frames is `UNKNOWN`. No total-heal or “one more heal must survive” claim is made.

## Requested checks

1. **R95 non-propagation:** Hbiscus timing changed, but its runtime `(3,5) RIGHT` coverage never reached Steward's `(7,2)`. The only Steward heal remained Ansel `506.8@2959`. Because Steward's deployment and shell locks stayed at `(7,2)`, the relevant hit/heal sequence did not change.
2. **R96 C2 Ansel death chain:** Ansel moved to runtime `(5,5)`. Shells locked `(5,5)` and `(5,6)` hit Ansel at `1961` and `2261`; no heal to Ansel was observed in the checked window. It died before the Steward shells at `2411` and `2561`. This proves a changed exposure and death chain, not that Ansel was deliberately sacrificed to heal Steward.
3. **Action errors:** R96 C1 had 9 and C2 had 6 recorded `legal:false` actions. Every one occurred after the executor's recorded death; no independent illegal deployment/coordinate error was found. They are dependency failures, not separate independent design failures.
4. **M70 grounding:** M70 was not merely indexed. The R96 model trajectory read the M70 plan/status, decompressed M70 events, and inspected shells, deaths, devices, and healer aggregates (`codex_exec.jsonl` items 9-13). It did not preserve M70's observed dual-support condition as a mandatory constraint; that was a tactical-parent choice, not evidence absence.

## Falsifiable next questions

1. **Q1_DUAL_SUPPORT_GEOMETRY** — Can a seven-ID plan establish real support coverage for the artillery-output tile while avoiding R96 C2's shared splash exposure, with opening/protected-route duties retained? Observe actual support coverage, shells/heals, operator deaths, artillery damage/death, protected outcomes, and leaks.
2. **Q2_ALTERNATIVE_ARTILLERY_CLOSURE** — Can artillery be closed by a materially different output placement/executor before sustained Steward survival is solved, without dropping opening, roadblock, central, or protected-route duties? Observe each operator's actual artillery damage, artillery death, and the independent endgame conditions.

These are hypotheses, not approved actions. No roster or old frame is mandatory.

## Artifacts

- Machine-readable index: `comparison_index_v1.json`
- Fact-pack draft: `next_fact_pack_draft_v1.json`
- Unauthorized next prompt: `next_prompt_suggestion_v1.md`

Actual model calls: **0**. Actual simulations: **0**. New `STARTED`: **0**.
