# M41 saved-V3 completion

## Scope and budget

- This increment did not regenerate a full plan from scratch. It returned the
  exact saved V3 static conflict to GPT and revised that lineage.
- Historical counters remain unchanged: M39 `4/4 CLI, 2/4 simulations`; M40
  `2/2 CLI, 1/2 simulations`; original M41 `3/3 CLI, 2/3 simulations`.
- This completion used **1/2** new tactical CLI starts. The original M41's
  remaining simulation was used, leaving no M41 simulation. Mechanics version is
  still `m38b-2781-animation-speed-v1`.
- A normal runner defect for static-blocked parents was fixed and covered by the
  existing session tests; it consumed neither CLI nor simulation.

| Plan | Contract | Static | Simulation | Result |
|---|---|---|---|---|
| `R8_7_GPT_M41_V3` | PASS | FAIL | NOT_SIMULATED | Hibiscus cooldown conflict |
| `R8_7_GPT_M41_V4` | PASS | PASS | LOSS | 10 kills / 23 leaks / 9 operator deaths / life -21 |

Prompt SHA-256 values:

- V3: `7d5f45ff7044c0b2719f77b47c78563b57dcf3d92340af8d4c51d844af2e0d48`
- V4: `7c81341c1a46488e16945d797ca8573b9d238dd7ee7abab3290c155389cfda95`

Frozen V4 artifacts: prompt above, plan SHA
`62a9e4aa4533b465858946fbe8fb8340c92104ce8cd028fd8622c0d494a43115`, static SHA
`0f1d84f3cbe620d6ddf88e49998a6a4909b2e71dde5ed4b0080223ad3f620f09`. Compressed
raw artifacts and hashes are in `evidence/manifest_v1.json`.

## Static correction

GameData gives Hibiscus phase-0 level-40 `respawnTime=70`. V3 retreated her at
frame 4650, so the earliest legal return was frame 6750; frame 6600 was 150
frames too early. GPT moved only the return to frame 6750 and moved its skill to
frame 7650. V4 contract and static checks passed with zero conflicts. This fixed
the specific cooldown error but did not by itself prove DP, HP, role coverage, or
survival.

## V4 replay

- The declared opening HEAL occurred: Medic2 healed Fang for 70.00 at frame 516.
- It did not establish survival. Fang, Vanilla, and Medic2 all died at frame 580.
- The first leak was `enemy_1108_uterer#1` at frame 721. Life first reached zero
  at frame 1132. Thus the opening interception/survival duty failed before the
  verified treatment could become a complete defense.
- Hibiscus's original deployment at 2400 could not satisfy its later plan: she
  had already died at 580, so the planned frame-4650 retreat was invalid and
  Lava's same-frame deployment failed for insufficient DP. The corrected frame-6750
  return did execute, cost 17 DP, and self-healed, but produced no artillery
  damage.
- Steward deployed at 2070 and dealt 25 attacks / 9993.89 total, but only 7
  attacks / 1967.89 went to artillery during frames 4825–5113. He received 289.00
  ARTS damage at 5138 and a 910.00 shell at 5143, then died; he received no HEAL.
- The artillery survived and leaked at 5759. Roadblocks #3 and #1 were destroyed;
  #2 and #4 remained. `#3` reached safely at 3554; `#14` died from artillery at
  3945. Final: LOSS, 10 kills, 23 leaks, 9 operator deaths, life -21.

## Interpretation

The cooldown conflict is closed, but V4 does not recover the plan. The first
observable proves treatment occurred, not survival, interception, or full-stage
success. The decisive opening failure was simultaneous death of the first three
operators before frame 721. Steward's output was also displaced to officers and
armored targets before the late artillery window. A later decision must keep
opening survival, artillery targeting/throughput, DP for handoffs, and Hibiscus's
legal return jointly observable.

These are current-model simulator diagnostics only. They do not establish a WIN,
perfect WIN, probabilistic WIN, faithfulness, robustness, or real-device behavior.
