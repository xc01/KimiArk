# M43 joint responsibility closure report

## Scope and budget

- Model entry: `openai/gpt-6.1-sol`, `model_reasoning_effort=high`, `features.apps=false`.
- New real tactical CLI starts: **3/3**. New fixed simulations: **1/3**. M42's remaining simulation remains reserved and was not carried into M43.
- V1 was static-blocked, V2 was contract-blocked, and V3 was simulated once. No candidate reached the hard WIN target.
- M42's raw CLI/static/simulation evidence was archived with raw and compressed SHA-256 values in `docs/review/fc77177/m42_retreat_redeploy_artillery_window_v1/evidence/archive_index_v1.json`. M43 evidence is similarly indexed in `docs/review/fc77177/m43_joint_responsibility_closure_v1/evidence/archive_index_v1.json`.

## Candidate comparison

| Candidate | Gate | Simulation | Result |
|---|---|---:|---|
| `R8_7_GPT_M43_V1` | STATIC_BLOCKED | 0 | Gallus redeployment at frame 4710 was still in cooldown. |
| `R8_7_GPT_M43_V2` | CONTRACT_BLOCKED | 0 | Prediction used unsupported `OPERATOR_RETREAT` instead of `RETREAT`. |
| `R8_7_GPT_M43_V3` | PASS | LOSS | 6 kills / 27 leaks / 10 deaths / life -26; first leak frame 1241. |

V3 destroyed roadblocks #3 and #4 at frames 2694 and 3345, but only two successful retreat refunds occurred: Gallus +1 at 2700 and Melantha +7 at 3540 (redeployed at 5760). Steward hit artillery 9 times for 2466.09 (frames 2860–3244) and died at 3250; Lava added one hit for 291. Protected #3 was killed by artillery at 5191 and #14 by an officer at 6314.

The V3 opening regressed badly: Medic2 died at 940, Wyvern at 1090, Friston at 1457, Fang at 1509, and Beagle at 1540. This was materially worse than M42 V3's 19/14 result, so M43 V3 must not be promoted as a parent merely because it destroyed two roadblocks.

## Corrections from M42 raw events

1. **V1 first-leak causality corrected.** `enemy_1108_uterer#2` leaked at frame 961 after Wyvern died at 820 and unblocked it. Medic2 died at 970, nine frames later. Medic2's death worsened support but did not cause the first leak.
2. **Coordinate systems unified.** Plans and static checks use JSON `[row,col]`; event lock/deploy positions use runtime `[x,y]` where `x=col, y=row`. For example, runtime `[3,4]` is JSON `[4,3]`.
3. **M42 V3 retreats were verified narrowly.** Seven successful retreats and refunds occurred, and three had same-frame replacements, but none of the retreated operators was redeployed later. Refund count alone is not success evidence.
4. **M42 V3 artillery window was split.** Steward dealt 3686.68 before protected #3 died, 473.29 between the two civilian deaths, and 2690.28 after protected #14 died. Only the pre-#3-death segment can be treated as a safe-output window.
5. **M42 V3 failure chains separated.** The first leak at 1661 followed Friston's frame-1513 artillery death and release of `enemy_1108_uterer#5`. Civilian #3 died at 3430 after an artillery lock, and #14 died at 3945 after another artillery lock; roadblock #4 restrained #14 at 3251 but did not prevent death.
6. **Roadblock wording corrected.** M42 V3 destroyed only roadblock #2, not two roadblocks.

## Deterministic evaluator correction

The prediction evaluator had accepted a `RETREAT` with `details.legal=false` as VERIFIED. `_event_matches` now rejects illegal `DEPLOY` and `RETREAT` events. Added expectations cover both event types. Pytest is unavailable in this environment (`No module named pytest`), so an equivalent direct-function regression passed for both cases. Recomputing M43 V3 offline changes its prediction from VERIFIED to `EVENT_NOT_OBSERVED`; the corrected result is saved at `attempt_03_cli/revision_hypothesis_evaluation_corrected_v1.json`.

## Boundary and next step

No result is faithful, robust, probabilistic, or real-device evidence. The simulator result is diagnostic only for the current model and mechanics version.

The next bounded tactical round should use M42 V3 as the conditional artillery/interception baseline and explicitly solve the confirmed civilian-exposure and roadblock chains; it should not optimize from M43 V3's degraded opening. This requires new paired CLI and simulation authorization.
