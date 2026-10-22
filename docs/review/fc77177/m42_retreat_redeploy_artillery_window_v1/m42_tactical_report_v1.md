# M42 retreat, redeploy and artillery window tactical report

## Scope

- Model entry: `openai/gpt-6.1-sol`, `model_reasoning_effort=high`, `features.apps=false`.
- Stage: `main_08-07` under mechanics `m38b-2781-animation-speed-v1`.
- New real tactical CLI starts: **4/4**; new fixed full-stage simulations: **3/4**. Historical M39–M41 budgets remain unchanged.
- The target was current-model WIN, zero leaks and both protected targets safe. No candidate met that target.

## Candidate comparison

| Candidate | Static | Simulation | Kills / leaks / deaths / life | First leak | Protected targets | Roadblocks destroyed | Key artillery output |
|---|---:|---:|---:|---:|---|---:|---:|
| `R8_7_GPT_M42_V1_ALT` (attempt 1 concurrent branch) | PASS | LOSS | 10 / 23 / 9 / -22 | 1535 | 0 reached; both killed | 0 | Lava hit artillery once for 291 |
| `R8_7_GPT_M42_V1` (attempt 2) | PASS | LOSS | 16 / 17 / 8 / -16 | 961 | 0 reached; both killed | 2 | Jnight 17.2, Gallus 1174.5, Durin 1190 |
| `R8_7_GPT_M42_V2` | STATIC_BLOCKED | NOT_SIMULATED | not evaluated | not evaluated | not evaluated | not evaluated | not evaluated |
| `R8_7_GPT_M42_V3` (attempt 4, best branch) | PASS | LOSS | 19 / 14 / 9 / -13 | 1661 | 0 reached; both killed | 1 | Steward 23 hits / 6850.25 |

## Causal findings

1. **V1's opening hypothesis failed on shell geometry.** Beagle was planned at JSON `[3,4]` (runtime `[4,3]`), Wyvern at JSON `[4,3]` (runtime `[3,4]`), and Medic2 at JSON `[3,2]` (runtime `[2,3]`). The first artillery lock was runtime `[3,4]`; the 670-frame hit reached Wyvern for 760, the 820-frame repeat killed Wyvern and released `enemy_1108_uterer#2`, and the 970-frame hit killed Medic2. The first leak was frame 961, before Medic2 died at 970. Thus Wyvern's death caused the first interception failure; Medic2's death was a separate support loss nine frames later.
2. **V2 improved opening separation but did not close DP.** Its schema was valid and its shell-separated opening was a useful hypothesis, but static compilation found two exact DP conflicts: Ardign needed 6 more DP at frame 2070 and Spot needed 2 more at frame 3000. It was therefore correctly not simulated.
3. **V3 resolved the V2 static conflicts and advanced artillery throughput.** Steward dealt 23 hits / 6850.25 to artillery from frames 2838–4566. Seven successful retreats did execute refunds: Beagle 9, Medic2 1, Gallus 1, Fang 5, Castle-3 1, Confess 1, Falco 5. This is the best local branch, but the artillery was still not cleared, only roadblock #2 was destroyed, 14 enemies leaked, and both protected targets were killed by artillery at frames 3430 and 3945. The first leak at frame 1661 followed Friston's frame-1513 artillery death and release of `enemy_1108_uterer#5`.
4. **Active retreat behavior is valid but cannot rescue a broken predecessor.** V1 had a confirmed Beagle-to-Noir-Corne refund and replacement handoff. Later V1/V3 retreats were invalid when the named operator was already dead or missing. Death grants no refund, while actual successful retreat does.
5. **Artillery handling and line protection remained competing responsibilities.** V3 concentrated effective artillery damage in Steward, but roadblock clearance and both civilian routes degraded. V1 cleared two roadblocks yet had much lower artillery throughput and earlier central collapse.

## Knowledge retained

- Retain the V3 principles of separating splash victims, funding handoffs from observed income, and using Steward before protected-target exposure. Only Steward's pre-#3-death window should be treated as a safe output window.
- Retain the V1 insight that actual retreat refunds and replacement deployments can execute, but only from a living predecessor with enough DP.
- Do not reuse V1-alt; it lost the opening, had no roadblock destruction, and was clearly dominated by V3.
- V2's static conflicts are resolved history, but its structural idea was absorbed by V3 rather than being independently validated in combat.

## Boundary

No candidate is a faithful, robust, probabilistic or real-game WIN. `faithful_certificate` remains `UNKNOWN`; no real device was played. The simulator result is diagnostic evidence for the current model and mechanics version only.

The unique next bounded tactical step is to revise from the combined evidence while fixing the remaining 14-leak / insufficient-roadblock-clearance / civilian-exposure failure chain. This requires a new authorized CLI and simulation budget; no tactical generation was performed by Python.
