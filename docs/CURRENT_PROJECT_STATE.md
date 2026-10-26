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

## 2026-10-21 M32 deterministic re-check is current

CONFIRMED_FROM_CODE: the static compiler no longer treats a repeated deploy while the same
operator is still deployed as an unconditional redeploy. Another occupant conflicts; self-exit,
cooldown, tile/slot release, generation reset, and actual DP payment remain conditions. Future
death is not assumed. The corrected ledger reserves base redeploy cost without claiming final DP.

CONFIRMED_FROM_SIMULATION: M30 V2 and M31 V3 were replayed once with unchanged action snapshot
hashes. M30 V2 is 23 kills/10 leaks/10 operator deaths/life -7 with both civilians arrived; M31
V3 is 22/11/10/life -9 with #3 killed by artillery and #14 arrived. Both artillery instances
leaked at frame 5759. These losses are still not simulator WINs, perfect objective results,
faithful results, robust results, or real-game results.

R8-7 is suitable for a bounded GPT structural revision, but it must solve artillery damage and
complete route protection as simultaneous constraints. The evidence table is
`docs/mechanics/R8_7_MECHANISM_COVERAGE_V1.md`.
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

## 2026-10-19 m25 R8-1 closes; R8-7 budget is exhausted

CONFIRMED_FROM_SAVED_ARTIFACTS: R8-1 M25 V1 (`R8_1_LOWSTAR_PLAN_C7_M25_GPT_V1`)
is a current-model simulator WIN at 56 kills, 0 leaks, 0 operator deaths, and
life 5. The same frozen 22-action timeline also wins under both saved
roadblock-targeting interpretations. This remains a conditional model result,
not a faithful, broadly robust, or real-game claim.

R8-7 used all eight authorized single-stage CLI starts. Attempts 04, 05, 07 and
08 failed contract validation without simulation; attempt 06 passed static
checks and simulated as a LOSS with 17 kills, 16 leaks, 10 operator deaths, one
protected death, and one protected arrival. Its fatal chain is recorded in
`docs/review/fc77177/m25_attempt04_08_reconciliation_v1.json`: Ansel survived two
artillery hits but died to the third at frame 2280; protected target #14 was
restrained by roadblock #4, received officer attacks and two 950-damage artillery
hits, then died at frame 3966. The scheduler was not running despite a stale
WAITING state; reconcile now marks it STOPPED because the R8-7 stage budget is
exhausted.

## 2026-10-19 M26 deterministic feedback loop and R8-7 status

The M26 loop added a bounded machine-readable experience store, a mandatory
revision hypothesis, deterministic event verification, capped retrieval, and a
two-slot branch manager. It records contract-invalid, operational, static-conflict
and legal battle failures separately.

R8-1 remains a current-model WIN on the frozen timeline under both saved
roadblock-targeting interpretations. R8-2 V15 and R8-4 V4 remain frozen current
model wins. R8-3/5/6 remain mechanism BLOCKED. R8-7 remains LOSS: M26 V3 reached
a legal fixed simulation and lost at 16/17 with 10 operator deaths, remaining
life -16, two protected deaths, and no protected arrivals. The patrol-removal
hypothesis was not verified; the artillery unit leaked at frame 5759. M26 CLI
budget is exhausted, so no further GPT call may be made without new authorization.

## 2026-10-19 M27 closes offline feedback defects and prepares M28

The M27 loop now filters invalid experience, enforces the real event protocol,
compares candidates by compatible stage/mechanics/objective context, records
objective scope separately from simulator WIN, and rejects unauthorized model
configuration before `STARTED`. A minimal MCP stdio server and Skill expose
mechanism facts, experience retrieval, contract checking, frozen-evaluation gate,
and saved-status feedback. The M27 simulation budget remains zero.

R8-1, R8-2 and R8-4 frozen baselines are unchanged. R8-7 remains a legal
battle LOSS and is not a faithful, robust or real-game result. R8-3/5/6 remain
mechanism BLOCKED, and no probabilistic WIN is claimed. The ready but unsent M28
prompt is documented in `docs/review/fc77177/m28_payload_manifest_v1.json`.

## 2026-10-20 M29 phase planning reaches two valid R8-7 losses

The M29 loop added mandatory `battle_phases` and budget reconciliation of
`FAILED_BEFORE_START`, `FAILED_AFTER_START_WITHOUT_SAVED_RESULT`, and completed
legal battles. Four real Codex starts were used: V1 completed but failed static
redeploy-cooldown checking; V2 and V3 passed contract/static checks and each
simulated once; V4 later completed a contract-valid plan but was not statically
checked or simulated. The budget reconciliation is
`docs/review/fc77177/m29_simulation_reconciliation_v1.json`.

R8-7 M29 V2 is a legal LOSS at 19 kills, 14 leaks, 13 operator deaths, life -12,
one protected death and one protected arrival. It moved #14 to a safe arrival but
lost the early medical layer and leaked after frame 4731. R8-7 M29 V3 is a legal
LOSS at 8 kills, 25 leaks, 11 operator deaths, life -23, one protected death and
one protected arrival; its opening survival and upper-corridor coverage failed
earlier. These are conditional current-model simulator results only. R8-1/R8-2/
R8-4 frozen baselines remain unchanged; R8-3/5/6 remain mechanism BLOCKED.

The full parent/child pytest comparison has zero M29-only failures: 31
historical failures remain in both runs, while 16 parent-only failures came from
the isolated parent worktree lacking local untracked output artifacts.

## 2026-10-23 M44 correction confirms closed LOSS state

M44 remains closed at 0/3 recorded separate tactical CLI starts and 3/3 fixed
`main_08-07` simulations under `m38b-2781-animation-speed-v1`. V2 and V3 each
had 31 actions. A matcher correction changes M44 V1's illegal Popukar skill
prediction from `VERIFIED` to `EVENT_NOT_OBSERVED`; V2's legal deployment alone
does not establish the failed handoff, while V3's Popukar handoff is supported
by `BLOCK@1440` and `ENEMY_DEATH@1692`. V3 remains a 19/14/7/life -13 LOSS,
with both protected targets dead and no safe arrival. Evidence and corrected
scope are in `docs/review/fc77177/m44_joint_responsibility_iteration_v1/
m44_prediction_correction_v1.json`. This is not WIN, real-game, faithful, or
robust progress.

## 2026-10-23 M45 closes at CLI limit without WIN

M45 used all three real Codex CLI starts; attempt 2 timed out and produced no
plan. Two frozen plans were simulated once each. V1 lost 12/21/11/life -19 after
Friston died and released the runner at 1453, with no replacement until 3000.
V3 improved the opening duty but still lost 18/15/4/life -13: Melantha actually
blocked and killed `enemy_1108_uterer#5`, while Fang died and released
`enemy_1107_uoffcr#6` at 1449, causing the 1791 leak. V3 protected #3 but #14
died at 6314 to repeated officer hits. M45 has one unused simulation, but no
CLI remains to generate a paired revision. Report:
`docs/review/fc77177/m45_joint_artillery_continuity_v1/m45_tactical_report_v1.md`.

## 2026-10-23 M46 closes without joint protected-target completion

M46 used 3/3 real Codex CLI starts and 2/3 fixed simulations. V1 removed the M45
`enemy_1107_uoffcr#6` opening failure but introduced a route-17 failure after
Midnight died and released `enemy_1107_uoffcr#15`, losing 16/17/12/life -15. V2
greatly improved to 31/2/7/life 1 and #3 safely reached, but artillery leaked at
5759, #14 stayed restrained by roadblock #2 without arrival, and route-29 armor
`enemy_1110_uamord#34` leaked at 6996. V3 timed out without a plan, so the final
simulation could not be used. M46 is not WIN and makes no real-game, faithful,
or robust claim; the report is
`docs/review/fc77177/m46_opening_survival_economy_v1/m46_tactical_report_v1.md`.

## 2026-10-23 M47 closes at CLI limit without WIN

M47 used 3/3 real Codex CLI starts and 1/3 fixed simulations. Attempt 1 was
rejected for the then-undeclared `DEVICE_DAMAGE`; attempt 2 timed out at 3600
seconds without a plan; attempt 3 produced a static-clean 53-action V2. The
fixed run closed roadblock #2 and both protected-target arrivals, but lost
23/10/8/life -7. All eight operator deaths preceded the first leak; only four
runtime deployment/DP failures occurred before it (4410, 4650, 4680, 4710).
`enemy_1107_uoffcr#20` and `enemy_1110_uamord#21` first leaked together at 5046,
artillery #0 leaked at 5759, and armored #34 leaked at 6996 with no damage or
block. Those leak frames are old-action evidence, not universal deadlines. The
result is a
conditional fixed-model LOSS, not real-game, faithful, robust, or probabilistic
progress. Evidence is in
`docs/review/fc77177/m47_remaining_gaps_closure_v1/evidence/`.

## 2026-10-24 M48 freezes at current-model simulator WIN

M48 used one real Codex CLI start and one fixed `main_08-07` simulation from its
own 3/3 budgets. GPT selected `R8_7_GPT_M47_V2` and produced the 53-action,
static-clean `R8_7_GPT_M48_V1`; it retimed Hibiscus toward Ansel and central
blockers, replaced Fang with Beagle, shifted Ansel's first boost, overlapped
Durin before Steward's withdrawal, and gave Lava persistent lower-central
clearance. The run completed with 33 kills, zero leaks, zero operator deaths,
both protected targets reached, and remaining life 3.

Duty evidence is not reduced to command success: Steward killed artillery #0 at
4273; Gallus destroyed roadblock #2 at 4698 and #14/#3 arrived at 5030/5033;
Spot/Beagle/Lava closed the #20/#21/#22 pressure chain; and Spot's block plus
Lava's 7848 kill closed armored #34. This is a conditional current-model
simulator WIN only—real-game verification remains UNKNOWN and faithful, robust,
and probabilistic claims are not issued. The frozen balance is CLI 1/3 and
simulation 1/3; evidence is under
`docs/review/fc77177/m48_joint_survival_interception_v1/evidence/`.

## 2026-10-25 M49 closes at limits without a 10-operator WIN

M49 used all three of its own real Codex CLI starts and all three fixed
`main_08-07` simulations. Post-run reconciliation counted each declared/DEPLOY
operator union as exactly ten; the original runtime check did not activate
because of a now-fixed configuration-chain defect. All plans passed contract and
static checks, but none won: V1 lost 21/12/5/life -10, V2 improved to
23/10/4/life -8, and V3 regressed to 22/11/6/life -9. Each reached one protected
target and lost the other.

V2 is the best loss but still leaves route-16 #18, artillery #0, armored
#21/#22, protected #3, and armored #34 unresolved. The exhausted M49 evidence
does not prove ten operators impossible. This milestone makes no real-game,
faithful, robust, or probabilistic claim. Evidence is under
`docs/review/fc77177/m49_roster_reduction_win_v1/evidence/`.

## 2026-10-25 M50 closes at limits without a 10-operator WIN

M50 used its own 3/3 real Codex CLI starts and 3/3 fixed simulations. All
candidates passed the repaired hard ten-ID gate and full static checks. V1 lost
14/19/8/life -17 after Wyvern died and released #2; V2 improved to
28/5/4/life -3 but left five leaks; and V3 regressed to 19/14/7/life -12 after
early medical reshaping broke survival and DP continuity. V2 is the best
exhausted loss, not a WIN. No historical balance was transferred. Evidence is
under `output/r8_1_r8_7_batch_v1/main_08-07/m50_ten_operator_full_win_v1/`
and `docs/review/fc77177/m50_ten_operator_full_win_v1/`.

## 2026-10-25 M51 freezes the ten-operator current-model simulator WIN

M51 used 2/3 real Codex CLI starts and 2/3 fixed simulations, then froze at the
hard goal. V1 was a 10-ID/29-action LOSS at 28 kills, 5 leaks, 2 operator
deaths, and life -2; its route-11 leak at 3065 preceded artillery #0's 4273
death. V2 is `R8_7_GPT_M51_V2`: it moved Lancet-2 to 1962, delayed Steward to
2132, and replaced the dead-Melantha tail with a live Fang handoff. The fixed
simulation then won with 33 kills, 0 leaks, 0 operator deaths, both protected
targets reached, and life 3. The selected/DEPLOY union is exactly 10. The scope
is current-model fixed simulator WIN only; real-game, faithful, and robust
claims remain unproven. Closeout:
`docs/review/fc77177/m51_ten_operator_full_win_v2/m51_closeout_v1.json`.

## 2026-10-25 M52 reduces the verified win to 9 operators

M52 verified the unpushed M51 V2 parent from local artifacts, then used its own
3/3 CLI starts and 3/3 simulations. V1 removed Lava and passed every hard target
at exactly 9 IDs: 33 kills, 0 leaks, 0 operator deaths, both protected targets
safe, and life 3. V2 removed Beagle but lost at 8 IDs with Steward's 2561 death
preceding the first 4625 leak. V3 removed Lancet-2 with a new medical handoff
but lost at 8 IDs after Friston's 2111 death and #11's 3065 leak. The best
verified result is therefore 9 IDs; no global minimum or 8-ID impossibility is
proved. Closeout:
`docs/review/fc77177/m52_minimum_operator_reduction_v1/m52_closeout_v1.json`.

## 2026-10-25 M53 closes at limits without an 8-operator WIN

M53 verified the unpushed M52 nine-operator WIN locally, then used its own 3/3
CLI starts and 3/3 simulations. V1 removed Beagle and lost 20/13/5/life -11
after Melantha's 2143 death; V2 restored direct Ansel-to-Melantha support but
still lost 21/12/6/life -10 after Hibiscus and Steward died; V3 replaced
Lancet-2 with reciprocal principal-medic coverage and restored Beagle, but lost
19/14/8/life -12 with 11 not-deployed action errors. All three used exactly 8
IDs and passed static checks. The verified best remains M52 V1 at 9 IDs; these
failures do not prove 8 IDs impossible. Closeout:
`docs/review/fc77177/m53_eight_operator_joint_revision_v1/m53_closeout_v1.json`.

## 2026-10-25 M54 closes at limits without an 8-operator WIN

M54 tested two structural directions beyond M53's roster-class deletions. V1
removed Melantha and Beagle but added Vanilla; it lost 15/18/8/life -17 after
artillery killed Ansel and Vanilla early. V2 removed Lancet-2 and separated the
medical/caster geometry; it improved to 23/10/7/life -8 but lost Ansel and
Steward to the first artillery locks. V3 kept that no-Lancet roster and added
reciprocal principal-medic coverage; it regressed to 19/14/8/life -12. All used
8 IDs and passed static checks. The verified best remains M52 V1 at 9 IDs.
Closeout:
`docs/review/fc77177/m54_minimum_operator_continuation_v1/m54_closeout_v1.json`.

## 2026-10-26 M55 closes at its one-call limit without an 8-operator WIN

M55 used its own single CLI start and single fixed simulation. GPT produced the
32-action, static-clean, exactly-8-ID fusion `R8_7_GPT_M55_V1` with Fang,
Vanilla, Midnight, Melantha, Ansel, Steward, Hibiscus, and Durin. The run lost
12/21/6/life -19. Melantha died to officer #9 at 1888, releasing the route;
#9 first leaked at 2121, life reached zero at #11@3065, and 9 dependent
not-deployed errors followed. Artillery #0 and #34 also leaked, while #3 arrived
and #14 died. The verified best remains M52 V1 at 9 IDs; this one failure does
not prove 8 IDs impossible. Closeout:
`docs/review/fc77177/m55_eight_operator_fusion_v1/m55_closeout_v1.json`.

## 2026-10-26 M58 protocol copy is verified once by M59 and loses

M58 remains closed at CLI 1/1 and simulation 0/1. Its normalized A_SPOT_FUSION
copy was later independently audited in M59, passed the original contract and
static checks, then consumed M59's separately authorized single simulation. The
30-action, exactly-8-ID run lost at 15 kills, 18 leaks, 8 operator deaths, one
protected-target death, one protected-target arrival, and life -16. Fang's
2430 retreat succeeded with a 5 DP refund, and Spot deployed at 2431 and healed
Hibiscus at 3038/3155, but the whole-stage duties did not close: artillery #0
leaked at 5759, #34 leaked at 6996, protected #3 died at 3311, and only #14
reached. The best verified current-model simulator WIN remains M52 V1 at 9 IDs.
M59 evidence is under
`docs/review/fc77177/m59_frozen_m58_spot_fusion_v1/evidence/attempt_01/`.

## 2026-10-27 M60 stops before simulation on a contract failure

M60 made its own single GPT tactical call with the M59 event feedback, correct
Spot/Ansel capability fields, and a hard eight-ID gate. The response compared
three structures, but `selected_structure_id` was at the root and only one
strategic hypothesis was supplied. These two errors are not a unique lossless
outer-field rename, so no normalized copy was fabricated. Static compile and the
authorized simulation were not started. The best verified current-model simulator
WIN remains M52 V1 at 9 IDs; this contract failure does not disprove Spot, an
eight-ID plan, or sacrifice tactics. Evidence is under
`docs/review/fc77177/m60_m59_feedback_revision_v1/evidence/attempt_01_cli/`.
