# 2026-10-14 Civilian mechanics correction and current seven-stage state

CONFIRMED_FROM_CODE_AND_EVIDENCE: the runtime now requires positive remaining
life for WIN, rejects ordinary operator attack/block selection of neutral Ursus
Civilians, records safe arrival and civilian death scoring, implements the
1.2 protected-target attack pool for the Infected Patrol Officer, and separates
roadblock civilian blocking from ordinary operator blocking. The source-backed
mechanics version is `m19.0-neutral-protected-target-v1`.

CONFIRMED_FROM_SIMULATION: the five saved candidates were re-evaluated once
under this corrected model. The old R8-2 V1 `PARTIAL_MECHANICS_DIAGNOSTIC_WIN`
is contradicted: it is now 8 kills/28 leaks/0 deaths/life -26, with first
objective failure at frame 1889. R8-2 V3 is 11/25/0/life -23; R8-4 V1/V2 are
20/34/life -31 with 0/1 deaths; R8-7 V1 is 4/29/5/life -26. R8-7 V2 then
improved to 13/20/2/life -17, first objective failure frame 1532, but remains
LOSS.

CONFIRMED_FROM_STATIC_CHECKS: R8-2 V4 and R8-4 V3 passed schema/contract but
were not simulated. R8-2 V4 has deployment-limit, DP, SP and redeploy-declaration
conflicts; R8-4 V3 has three Melantha SP conflicts. R8-7 V2 needed only the
recorded `parent_hypothesis_id` mapping and then passed static checks.

CONFIRMED_FROM_CODE: `seven_stage_status_v3.json` is the active table. R8-1 is
roadblock-targeting robust simulator WIN; R8-2/R8-4/R8-7 are corrected-model
LOSS; R8-3/R8-5/R8-6 are mechanism-blocked. No new optimization cycle has
started. Cumulative CLI starts are 16; internal requests remain
UNKNOWN_CLI_INTERNAL. Simulator results are not real-game claims.

## 2026-10-14 Death-unblock revalidation is current

CONFIRMED_FROM_CODE: `seven_stage_status_v4.json` supersedes v3 for tactical
interpretation. The death/unblock path now releases dead targets in ordinary,
projectile, and multi-block tests. R8-1 C7 remains robust across both saved
roadblock-targeting interpretations. R8-2 V1/V3 reach zero leaks and life 2 but
leave civilian #11 active at roadblock #2. R8-4 V2 is 50/4/1/life -1; R8-7 V2 is
29/4/2/life -1. The six older corrected-model windows are potentially polluted
and no longer reliable tactical feedback.

## 2026-10-14 R8-2 is waiting on the tactical transport

R8-2 V1/V3 are zero-leak, zero-operator-death, life-positive candidates but not
WIN because civilian #11 remains active at roadblock #2. Fixed GameData gives
roadblock #2 HP 8000/DEF 200/RES 20. V1/V3 never selected or damaged it. A
compact clearance evidence package and explicit user observation are prepared.
Two R8-2 GPT-C5 CLI starts failed at `workspace routing discovery failed`
without a retry; no plan or simulation was produced.

## 2026-10-14 R8-2 V5 is the current best fixed candidate

`seven_stage_status_v5.json` supersedes v4. R8-2 V5 passed schema/contract and
static checks, then its first fixed simulation produced a simulator WIN with 36
kills, 0 leaks, 0 operator deaths, and life 2. Roadblock #2 was destroyed at
frame 6633 and #11 arrived safely at frame 6956. Civilian #6 died at frame 4604,
so perfect completion is still false. The V6 prompt was generated and frozen,
but its only CLI attempt failed at `workspace routing discovery timed out`.

## 2026-10-14 V6/V8 restore the entry but miss perfect completion

`seven_stage_status_v6.json` supersedes v5. The optional `features.apps=false`
Codex override restored transport without changing the model or global config.
CLI starts are now 24 (V6=22, V7=23, V8=24); internal requests remain
`UNKNOWN_CLI_INTERNAL`. V5 remains the immutable zero-leak simulator WIN with
protected-target loss. V6/V8 both simulated LOSS; V7 was blocked by an exact DP
static conflict. The next step is a structural GPT revision, not another
same-shape timing retry.

## 2026-10-14 V14/V15 are zero-leak WINs but not perfect

`seven_stage_status_v8.json` supersedes v7. CLI starts are now 32. V14 and V15
are both simulator WINs with 36 kills / 0 leaks / 0 operator deaths / life 2.
V14 is the better perfect-completion candidate because #6 died at 5294 rather
than 4994 and #11 arrived without damage. Neither is perfect: #6 remains the only
blocked protected target. V16 had no final message and was manually stopped with
evidence. R8-4/R8-7 have not advanced in this round.
## 2026-10-14 Local device targeting and R8-2 V15 perfect simulator result

CONFIRMED_FROM_CODE: the prior device fallback contained an unsupported global
gate—any active non-neutral enemy anywhere prevented a device target, even when
the operator had no optional local enemy. PRTS and fixed GameData support taunt
`-1` and filtered candidate priority, not a map-wide gate. Mechanics version
`m19.1-local-device-target-v1` now considers ordinary devices only after the
same operator has no local enemy candidate and only within its range. Exact
multi-device ordering remains UNKNOWN.

CONFIRMED_FROM_SIMULATION: unchanged V14 and V15 actions were replayed once at
`output/r8_1_r8_7_batch_v1/main_08-02/local_device_target_revalidation_v1/`.
V14 remains a WIN but #6 dies at 5294; V15 is now a perfect current-model
simulator result with 36 kills, 0 leaks, 0 deaths, life 3, 0 protected-target
deaths, all four protected arrivals, and roadblock #2 destroyed at 2715. This
is not robust and not real-game. The seven-stage table is
`seven_stage_status_v9.json`.

CONFIRMED_FROM_SIMULATION: R8-1 C7 was replayed once on the same timeline under
both historical roadblock-targeting variants and remains WIN in both.
## 2026-10-15 R8-4 V4 is a perfect simulator result

CONFIRMED_FROM_SIMULATION: after one failed V3 revision, GPT's V4 fixed plan
reached simulator WIN for `main_08-04`: 54 kills, 0 leaks, 0 operator deaths,
remaining life 3, and all three civilians safely arrived at frame 5336 with no
civilian damage. Roadblock #2 and #1 were destroyed at 4062 and 4644. This is
`PERFECT_SIMULATOR_WIN_IN_CURRENT_MODEL`, not robust and not real-game. Evidence
is `output/r8_1_r8_7_batch_v1/main_08-04/local_device_diagnostic_v4/`; active
status is `seven_stage_status_v10.json`.
## 2026-10-15 R8-7 tactical iterations are current

CONFIRMED_FROM_CODE: the diagnostic runner incorrectly rejected valid
`RETREAT -> DEPLOY` transitions. It now validates each repeat against a
source-backed prior retreat and passes both new regressions. R8-7 V5 was
re-evaluated once on the same frozen plan after this correction.

CONFIRMED_FROM_SIMULATION: R8-7 V5 achieved all four roadblock clears and both
civilian arrivals, but lost with 21/12/7/life -9. V9 improved to 24/9/4/life -6
with both arrivals. V10 nearly restored V2 throughput at 28/5/3/life -2 and
arrived #3, but #14 stayed blocked by roadblock #4. V10 is the best current
R8-7 result; V2 remains the minimum-leak loss baseline. V11 failed schema/contract
lineage validation and has no simulation. The seven-stage table is
`seven_stage_status_v12.json`.

## 2026-10-15 m21 seven-stage status

| Stage | Current result | Evidence |
|---|---|---|
| R8-1 | C7 LOSS under m21 targeting A/B; historical wins are m19-history only | `output/r8_1_gpt_tactical_batch_v1/r8_1_c7_roadblock_targeting_replay_roadblock_radius_m21_v1/roadblock_targeting_replay_summary.json` |
| R8-2 | V15 m21 simulator WIN; perfect completion retained | `output/r8_1_r8_7_batch_v1/main_08-02/roadblock_radius_replay_v15_m21_v1/` |
| R8-3 | Mechanism BLOCKED | `docs/review/fc77177/deep_mechanism_fix_matrix_v1.json` |
| R8-4 | V4 m21 simulator WIN; perfect completion retained | `output/r8_1_r8_7_batch_v1/main_08-04/roadblock_radius_replay_v4_m21_v1/` |
| R8-5 | Mechanism BLOCKED | `docs/review/fc77177/deep_mechanism_fix_matrix_v1.json` |
| R8-6 | Mechanism BLOCKED | `docs/review/fc77177/deep_mechanism_fix_matrix_v1.json` |
| R8-7 | V13 m21 LOSS | `output/r8_1_r8_7_batch_v1/main_08-07/roadblock_radius_replay_v13_m21_v1/` |

Codex start count is 46; the latest start used a writable runtime `CODEX_HOME`
but stopped after service-side `workspace routing discovery failed`. The fix
matrix is `docs/review/fc77177/deep_mechanism_fix_matrix_v1.json`.
## 2026-10-15 m22 mechanism repair is partial, not full closure

CONFIRMED_FROM_CODE: mechanics `m22-deep-mechanics-partial-v1` fixes static DP
generation leakage, 99 maxCost, half-cost refunds, one-star occupancy, and
zero-duration AUTO tick loss. It also implements the six named low-rarity
behaviors tested in `test_normal_low_star_mechanics.py`, bounded delayed locked-area
artillery, and source-backed ice/altar device effects. These repairs do not restore
any historical stage WIN as a full-mechanism conclusion: R8-2 V15 and R8-4 V4 must
be replayed before current-mechanism use, and R8-1 C7/R8-7 candidates likewise
remain historical-only.

The full test suite is 496 passed, 31 failed, 2 skipped (529 collected). The same-venv focused
parent comparison confirms the two architecture device tests are newly fixed; the
31 full-run failures match the previously observed parent count, but a fair full
parent run requires copying gitignored runtime artifacts. See
`docs/review/fc77177/m22_full_test_comparison_v1.json`.

## 2026-10-15 m23 behavioral repair

CONFIRMED_FROM_CODE: `m23-behavioral-mechanics-v1` makes Ansel/Midnight/Spot/
Beagle effects observable in runtime, fixes route-blocking endpoint false
positives, makes delayed artillery a launch/impact cycle with faction and defense
rules, applies COLD to enemy attack interval, uses source range `x-1` for friendly
ice/altar effects, caps static refunds, counts one-star slots correctly, and fixes
the compiler CLI entry. Work's 13 behavioral regressions plus the CLI regression
pass. Full tests are 497 passed, 31 failed, 2 skipped (530 collected).

Seven stages remain historical-only until replayed unchanged under m23. R8-3,
R8-5 and R8-6 still have incomplete decisive semantics. Exact client artillery
prefab lifecycle, friendly-device lifecycle, redeploy cost growth, full 34-operator
ability closure, Talulah, checkpoints and probability bounds remain UNKNOWN.

## 2026-10-15 m24 deployment-slot correction and frozen replay

CONFIRMED_FROM_CODE: the complete compiler evaluated the deployment-limit gate
before reading the current operator. It now reads rarity first, applies the gate
only to a known rarity-2/3 normal deployment, records `MISSING_OR_INVALID_RARITY`
instead of silently treating missing rarity as a robot, and leaves one-star
occupancy and retreat release unchanged. Five focused compiler regressions pass.

CONFIRMED_FROM_SIMULATION: five unchanged m23 replays are complete at commit
`4073c511f214ae291ea4508af84db521254cf689`: R8-1 C7 A/B are LOSS (54/2/0/life 3
both), R8-2 V15 is simulator WIN (36/0/0/life 3, four protected arrivals, no
protected death), R8-4 V4 is simulator WIN (54/0/0/life 3, three protected
arrivals, no protected death, but Ansel dies at frame 5304), and R8-7 V13 is
LOSS (17/16/11 operator deaths/life -15, two protected deaths). These are
current-model diagnostics only, not faithful, robust or real-game claims.

| Stage | Current m23/m24 diagnostic | Evidence |
|---|---|---|
| R8-1 | C7 A/B LOSS: 54 kills, 2 leaks, 0 deaths, life 3 | `output/r8_1_r8_7_batch_v1/main_08-01/m23_deployment_slot_revalidation_v1/c7_targeting/` |
| R8-2 | V15 WIN: 36/0/0, life 3, all 4 protected targets arrive | `output/r8_1_r8_7_batch_v1/main_08-02/m23_deployment_slot_revalidation_v1/v15/` |
| R8-3 | Mechanism BLOCKED | `docs/review/fc77177/deep_mechanism_fix_matrix_v1.json` |
| R8-4 | V4 WIN: 54/0/0, life 3, all 3 protected targets arrive; 1 operator death | `output/r8_1_r8_7_batch_v1/main_08-04/m23_deployment_slot_revalidation_v1/v4/` |
| R8-5 | Mechanism BLOCKED | `docs/review/fc77177/deep_mechanism_fix_matrix_v1.json` |
| R8-6 | Mechanism BLOCKED | `docs/review/fc77177/deep_mechanism_fix_matrix_v1.json` |
| R8-7 | V13 LOSS: 17/16, life -15, 11 operator deaths, 2 protected deaths | `output/r8_1_r8_7_batch_v1/main_08-07/m23_deployment_slot_revalidation_v1/v13/` |

New tactical CLI calls remain 0. New full-stage simulation starts are 5. The
m23 parent/current and m24 full-test comparisons have exact failure IDs;
the latest 530-test run is 497 passed / 31 failed / 2 skipped with no new failure.
The local m24 commits have not yet reached GitHub; SSH through both the direct
route and process-level mihomo CONNECT proxy failed before key exchange. See
`docs/review/fc77177/m24_push_status_v1.json`.

## 2026-10-16 m24 evidence package is ready, not sent

CONFIRMED_FROM_SAVED_ARTIFACTS: `m24_review_evidence_v1.json` indexes five
runs, verifies compressed events, and matches every action snapshot to its
saved source. `m24_causal_feedback_v1.json` separates R8-1 route-throughput,
R8-4 operator death from target loss, and R8-7 artillery/opening chain. Two
complete R8-1/R8-7 tactical payloads are stored with hashes and explicit
`sent=false`; no model call has occurred.

## 2026-10-16 m25 entry is blocked before tactics

The first authorized R8-1 Codex start used `gpt-6.1-sol`, `high`,
`features.apps=false`, and the prepared m24 payload. It counted as CLI start 47
and failed before producing a plan with `workspace routing discovery failed`.
Network preflight showed the configured mihomo port was absent; starting the
existing local binary was denied by the sandbox before it could bind 7890/9090,
and direct DNS also failed. No auth, provider, model, or node switch was made.
R8-7 has a runner-compatible prepared prompt under the 140 KiB limit, but was
not sent. Both R8-1 and R8-7 therefore have zero new plans and zero new full
simulations; their m23/m24 baselines remain the newest tactical evidence.

The resulting m25 commit was also not pushable: SSH closed before key exchange.
A verified incremental bundle based on `21f2914...` is saved in
`output/r8_1_r8_7_batch_v1/KimiArk_m25_unpushed_21f2914_9f6992a_20261016004824.bundle`.
