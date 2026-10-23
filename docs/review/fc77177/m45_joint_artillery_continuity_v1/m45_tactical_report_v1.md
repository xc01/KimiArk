# M45 joint artillery continuity and protected-target report

## Scope and budget

- Model entry: `openai/gpt-6.1-sol`, `model_reasoning_effort=high`, `features.apps=false`.
- Stage and mechanics: `main_08-07` under `m38b-2781-animation-speed-v1`.
- New real tactical CLI starts: **3/3**; new fixed full-stage simulations: **2/3**. Attempt 2 timed out after 3600 seconds and produced no plan. The unused simulation cannot generate a new revision without a new CLI.
- Target: current-model simulator WIN, zero leaks, both protected targets alive and safely arrived. No candidate met that target; no real-game, faithful, robust, or probabilistic WIN is claimed.

## Candidate comparison

| Candidate | CLI | Simulation | Result | First leak | Protected targets |
|---|---:|---:|---:|---:|---|
| `R8_7_GPT_M45_V1` | completed | LOSS | 12 / 21 / 11 deaths / life -19 | `enemy_1108_uterer#5` at 1594 | #3 reached at 4940; #14 killed by artillery at 3945 |
| `R8_7_GPT_M45_V2` | timeout at 3600s | NOT_SIMULATED | no plan | not evaluated | not evaluated |
| `R8_7_GPT_M45_V3` | completed | LOSS | 18 / 15 / 4 deaths / life -13 | `enemy_1107_uoffcr#6` at 1791 | #3 reached at 3776; #14 killed by officer at 6314 |

## Causal feedback

### V1

Friston blocked `enemy_1108_uterer#5` at 1141, received repeated 145-damage hits, died and released it at 1453, and it leaked at 1594. Popukar was not scheduled until 3000, so the handoff premise was already invalid. Hibiscus died at 1903 and Ansel at 2353; later actions failed because operators were absent or DP was insufficient. The declared Ansel-to-Wyvern `HEAL@960-1020` was `EVENT_NOT_OBSERVED`; Ansel healed Fang instead.

### V3

Melantha's early interception was real: `BLOCK@1071` against `enemy_1108_uterer#5`, then kill at 1251. This removed the V1/M44-condition #5 failure. It did not establish a complete interception baseline. Fang blocked `enemy_1107_uoffcr#6` at 1208, died and released it at 1449, and #6 leaked at 1791 without a living replacement. This is the new earliest duty failure.

V3 destroyed roadblocks #4, #3 and #1 at 1881, 1968 and 3444, but left roadblock #2. Protected #14 was restrained by roadblock #2 from 3620, then received repeated 280-damage officer hits from #16, #18, #24, #26 and #32 and died at 6314. Protected #3 arrived safely at 3776. Thus artillery exposure changed but did not disappear; officer damage became the lethal source for #14. The artillery itself leaked at 5759.

## Boundary and next step

M45 is closed at the CLI limit. It is not a WIN or tactical completion claim. The unique bounded next experiment, if separately authorized, must solve V3's frame-1449 Fang death/release and #6 leak while preserving Melantha's verified #5 interception, and must protect #14 from officer attacks or remove the restraint window that exposes it. The one unused M45 simulation is not authorization to rerun V1/V3 or to borrow M42/M43 budgets.
