# M66 Closeout

## Result

M66 did **not** produce an 8-ID WIN. The best verified current-model fixed-simulator result remains the frozen M52 V1 **9-ID WIN**. No real-game, faithful, robust, probabilistic, or globally-minimal claim is made.

Budget was **CLI 3/3** and **simulation 3/3**. One V3 invocation was rejected before STARTED because `features.apps=false` was omitted; it entered no model process and was not counted. The corrected third invocation was then counted. All three simulations were completed with full event settlement.

## Three Closed Loops

1. **V1 — `M66_M52_MEDICAL_REDISTRIBUTION`**: 8 IDs, 26 actions, static PASS. Loss: 17 kills / 16 leaks / 8 deaths / life -14. First leak: `enemy_1107_uoffcr#15@4176`; first objective failure: `4491`; protected #3 died to artillery at `5191`; #14 reached at `15249`. The medical-redistribution survival chain failed.
2. **V2 — `M66_SPOT_OUTER_DELAYED_HEAL`**: 8 IDs, 30 actions, static PASS. Loss: 19 / 14 / 7 / life -13. First leak: `enemy_1107_uoffcr#9@2007`; first objective failure: `4611`; both protected targets died to artillery (`#14@3943`, `#3@5341`). The declared successor BLOCK was absent. Artillery leaked at `5759`; #34 leaked at `6996`.
3. **V3 — `M66_MIRRORED_OUTER_DUTIES`**: 8 IDs, 27 actions, contract/execution/static PASS with 0 conflicts and 0 unknowns. Loss: 19 / 14 / 6 / life -12.

## V3 Causal Accounting

The V3 roster was 芬, Friston-3, 月见夜, 玫兰莎, 安赛尔, 芙蓉, 米格鲁, 史都华德. The model selected four-structure comparison and one referenced strategic hypothesis. Its expected first observable succeeded: Melantha BLOCKed `enemy_1108_uterer#4` at `921`.

The actual first leak was `enemy_1107_uoffcr#11@3065`, after Fang and Midnight had dealt only 886.76 damage and no BLOCK had occurred. The engine's first objective failure began at `4627` when life reached zero. Friston had already died at `2111`; Steward died at `3970`, and later commands targeting dead Hibiscus/Melantha/Steward/Fang states became runtime errors.

Protected #3 passed roadblock #3 but was again blocked by roadblock #1. It took 840 from officer #8 and three artillery hits of 950, then died at `5353`. #14 reached safely at `13749`, but one of two protected targets had died, so the objective was already failed.

Steward dealt 38 hits totaling `11035.13` to artillery #0, but the enemy was never killed or BLOCKed and leaked at `5759`. #34 took two Midnight hits totaling `49.7`, had zero BLOCK, and leaked at `6996`; Steward's planned `9000` retreat was already a dead-state error.

## Candidate-Level Model Gap

The selected plan used no newly added critical `MODEL_GAP`. The separately compared `M66_VANILLA_YATO_PRE_SWING_BRIDGE` was rejected because an aborted pre-strike consuming cooldown is not expressible in the current model. That was not hidden into the selected mechanism.
