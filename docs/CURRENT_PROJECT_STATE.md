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
`seven_stage_status_v11.json`.
