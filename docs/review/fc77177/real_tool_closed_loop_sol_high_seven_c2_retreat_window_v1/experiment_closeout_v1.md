# R103 C2 retreat-window closeout

## Budget and control

- Model: configured `gpt-6.1-sol/high`, `features.apps=false`; cryptographic model identity was not proven.
- Real usage: 1/1 CLI, 3/5 checks, 1/1 candidate, 1/1 complete fixed simulation.
- Control: `R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002`, plan `044eb9eb90254934cc4767dbd1070ee91ccbdf349380ec258bbdd488098b146b`, action `d5a07b4dca4f05cee428875165d3c59ee0c388e9b950623cd62fc8c60d83fc8f`.
- Candidate: `R103_SOL_HIGH_SEVEN_C2_RETREAT_WINDOW_001`, SHA-256 `921fa462cd69d0cc0a6d254ed991e37ea8db2a1141be0a54eadae26bd67a6593`.
- Normalized diff: action index 14 only, Steward `RETREAT 4200 -> 4201`; 34/34 actions otherwise unchanged.
- Control validity: all 19,405 events before the first 4200-window difference were identical.

## Fact-pack correction

The frozen fact pack incorrectly treated Steward's 70 as frames. The production check used 70 seconds × 30 = 2,100 frames, so retreat at 4280 made redeploy available at 6380 and failed the unchanged 6301 action. `4201` was the latest legal single-action change. The frozen fact pack remains unchanged; this correction is recorded as derived evidence.

## Result

The candidate remained a complete diagnostic LOSS: 20 kills, 13 leaks, life −11. Artillery output stayed 43 hits / 12,504.82 damage, with the last hit at 4177 and the artillery leaking at 5759. Protected `#3` died at 3311; `#14` reached at 12448. Roadblocks `#4/#3/#2` were destroyed at 2443/11917/12116; central `#21/#22/#33/#34` leaked. Operator deaths were Friston 2111, Hibiscus 4511, Fang 4702, and Steward 6569.

The one-frame delay did not close the immediate cutoff question into a WIN and did not add output. It also did **not** test the 4225/4273 reference window: that would require 4280 retreat, which is illegal under the unchanged redeploy. Therefore the material later window remains untested. Exact HP and continuous positions are UNKNOWN where not recorded.

## Scope

This is only a fixed-simulator, single-variable result for R101 C2. It does not prove real-game behavior, faithfulness, robustness, probabilistic WIN, Steward necessity, seven-ID impossibility, or a global minimum. M70 `R8_7_GPT_M70_V1` remains the verified eight-operator WIN.
