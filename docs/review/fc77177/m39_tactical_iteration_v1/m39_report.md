# M39 R8-7 tactical iteration under the M38b candidate model

## Scope and budget

- Tactical Codex CLI: **4/4** used. No retry, resume or replacement session
  was used. Failed contract output counts as attempt 1.
- Fixed full-stage simulations: **2/4** used. V3 and V4 each ran once.
- Model/provider: `openai` / `gpt-6.1-sol` / `high` with
  `features.apps=false`. Internal request count is `UNKNOWN_CLI_INTERNAL`.
- Mechanics version: `m38b-2781-animation-speed-v1`. This is a 2.7.81
  candidate model; build-2771 equality is not claimed.
- Simulator suite: `PYTHONPATH=.:src:scripts .venv/bin/pytest -q tests/simulator`
  passed **124 tests**.

## Runtime entry fixes

1. `animation_event_real_seconds` now applies `maxAnimScale` directly when no
   slowdown status is active. The 2.5 slowdown cap is applied only in the
   active-slowdown branch. The regression covers `maxAnimScale=4` without slow
   status and the capped slowdown branch.
2. The session builder now injects the active mechanics version, corrected
   artillery/medical/protected-target candidate facts, current UNKNOWN list,
   and an explicit warning that `referenced_experience_ids` must be a subset of
   registered IDs. Without an experience store, the current feedback is
   registered as the only experience record.
3. Contract feedback now preserves the source plan ID recorded by the contract
   validation layer.

## Attempts

| Attempt | Plan | Contract | Static check | Simulation | Key result |
|---:|---|---|---|---|---|
| 1 | `R8_7_GPT_M39_V1` | FAIL | not run | none | Referenced three unavailable experience IDs. |
| 2 | `R8_7_GPT_M39_V2` | PASS | FAIL | none | Steward deploy at frame 1740 needed 18 DP with balance 17. |
| 3 | `R8_7_GPT_M39_V3` | PASS | PASS | LOSS | 19 kills / 14 leaks / 5 operator deaths / life -11. |
| 4 | `R8_7_GPT_M39_V4` | PASS | PASS | LOSS | 17 kills / 16 leaks / 10 operator deaths / life -15. |

Prompt SHA-256:

- Attempt 1: `17e0ed727ec7da6881d1b4508bfde2c4bb8d6a1bc1333b106c99dd7a3a7f9a6e`
- Attempt 2: `adf122a4cf886cc390675e475a078b99cb0c32e865f16b2eae1dfa6f6d2392f8`
- Attempt 3: `a66404cc0703ebb5efe9c4fa53a4fda5ea17ace916fe7add704037813e2004b3`
- Attempt 4: `e86710d9ca4b1b9ae2020892e528a93376542719d1e8ecd4fd2abd841b55124b`

The compressed evidence archive and complete per-file hashes are in
`evidence/manifest_v1.json`.

## V3 result

Direct saved-event observations:

- First leak: `enemy_1107_uoffcr#11` at frame 3065; first objective failure by
  leak at frame 3711.
- Both protected targets reached: `#3` at 3566 and `#14` at 5297; neither died.
- All four roadblocks were destroyed, at 2025, 2850, 3234 and 4965.
- Operator deaths: Vanilla 2023, Steward 3011, Ansel 3311, Fang 3369, Beagle
  5439.
- Artillery received 20 hits totaling 5822.17 damage: 16 from Steward and 4
  from Lava. It remained alive and leaked at 5759.
- Six later skill commands failed because their sources were no longer
  deployed.

Interpretation:

- The V3 prediction (`char_285_medic2` retreat at 1290) was verified, but that
  only verifies the declared observable. It does not prove the full tactical
  hypothesis.
- Compared with M30 V2, V3 improved operator survival and kept both protected
  arrivals plus all four clearances. It reduced artillery damage and did not
  solve the leak problem.

## V4 result

Direct saved-event observations:

- The first prediction, Steward `DAMAGE` to `enemy_1112_emppnt#0` during frames
  1680–1830, was not observed. Steward was deployed at 1680, so deployment was
  not the sole issue; the absent-window cause is UNKNOWN.
- First leak: `enemy_1107_uoffcr#13` at frame 3786; objective failure at 3920.
- No protected target reached. `#14` died at 3966 from officer `#18`; `#3`
  died at 5203 from artillery `#0`.
- Only roadblock `#3` was destroyed at 2025. `#4`, `#1` and `#2` remained.
- Ten operators died. Thirteen later commands failed because their sources
  were no longer deployed.
- Artillery received 27 hits totaling 7609.45 damage, but survived and leaked
  at 5759.

Interpretation:

- V4 failed the key output-window premise before the first leak. The later
  collapse of clearance, protection and replacement duties is a direct event
  chain, while treating the missing attack window as the sole cause would be
  unsupported causation.
- V4 is not the preferred M39 branch. It sacrificed protection and clearance
  while still failing to kill artillery.

## Branch comparison

| Plan | WIN | Kills | Leaks | Protected targets | Roadblocks | Operators dead | Life | Artillery damage |
|---|---|---:|---:|---|---|---:|---:|---:|
| M30 V2 | LOSS | 20 | 13 | both reached | all four | 10 | -10 | 23 / 6626.06 |
| M31 V3 | LOSS | 22 | 11 | `#3` died; `#14` reached | three of four | 10 | -9 | 29 / 7959.67 |
| M39 V3 | LOSS | 19 | 14 | both reached | all four | 5 | -11 | 20 / 5822.17 |
| M39 V4 | LOSS | 17 | 16 | both died | one of four | 10 | -15 | 27 / 7609.45 |

No single branch is declared the unique best. M30 V2 remains the stronger
protection/clearance baseline; M39 V3 shows the best M39 survival branch; M31
V3 and M39 V4 preserve different early-output evidence without becoming
preferred whole-stage candidates.

## Status and next boundary

- Neither M39 run is a simulator WIN, perfect simulator WIN, probabilistic WIN,
  faithful result, robust result, or real-device result.
- M39's tactical lesson is that merely relocating medical/support units and
  naming a Steward artillery window does not establish effective output. The
  next bounded work must first make a single observable artillery-output window
  actually occur and then verify the synchronized leak-defence and clearance
  duties; prediction of an event is not proof that the full plan succeeds.
- Candidate artillery timeline remains: cooldown starts at cast, no target does
  not restart the timer, creation is about cast + 0.333333 s without slowdown,
  position locks at creation, and hit is about creation + 3.0 s.
- Remaining decisive UNKNOWNs: build-2771 equality, interruption, ordinary/special
  attack mutual exclusion, exact tie-breaks, and complete client collision/order
  semantics.
