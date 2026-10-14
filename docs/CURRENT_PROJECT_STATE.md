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
