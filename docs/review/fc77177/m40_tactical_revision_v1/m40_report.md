# M40 capability-based R8-7 tactical revision

## Scope and budget

- M39 remains **CLI 4/4, simulations 2/4**. M40 added **2/2** tactical CLI
  starts and used **1/2** of M39's remaining fixed-simulation allowance.
- No third CLI, second simulation, automatic retry, resume, model/provider
  change, or Python action repair was used.
- Model/provider: `openai` / `gpt-6.1-sol` / `high` with
  `features.apps=false`. Internal request count is `UNKNOWN_CLI_INTERNAL`.
- Mechanics version remains `m38b-2781-animation-speed-v1`; this is the 2.7.81
  candidate model, not build-2771 equality.

| Attempt | Plan | Contract | Static | Simulation | Result |
|---:|---|---|---|---|---|
| 1 | `R8_7_GPT_M40_V1` | PASS | FAIL | none | Gallus redeploy at frame 10200 was still in cooldown. |
| 2 | `R8_7_GPT_M40_V2` | PASS | PASS | LOSS | 15 kills / 18 leaks / 10 operator deaths / life -16. |

Prompt SHA-256:

- Attempt 1: `737264c04822b782aa719de599de7c59cd0f8a2f31fcba25663d23d23c82d8d3`
- Attempt 2: `64e7244cd1bf88261404b1d2cefc7292eb36a73fd3eca942c2dee3cc92d9ba10`

The compressed raw requests/responses, checks, snapshots, events, summaries and
per-file hashes are in `evidence/manifest_v1.json`.

## Corrected Steward output window

The M39 V4 saved events establish the actual timing rather than a broad claim
that Steward had no artillery output:

- Steward legally deployed at frame 1680 on JSON tile `[2,7]` (runtime
  `[7,2]`), facing UP, at cost 18.
- Route 1 is 29 units long. The artillery spawns at 3 seconds, has raw speed
  0.5, stage multiplier 0.5, and therefore effective speed 0.25 units/s. It
  waits 3 seconds at distance 2, then 10 seconds each at distances 5 and 8.
- Steward's UP-facing range covers runtime tiles `[6..8] x [2..5]`. The
  artillery first enters that grid at distance 12.5, at 76 seconds/frame 2280.
- The first target selection, attack, projectile creation and damage are all at
  frame 2281. The saved remaining-path distance is 16.491667.
- In M39 V4, Steward hit only artillery 25 times from frames 2281–3433 for
  7348.45 damage, then retreated at 3480 without dying.
- Thus the predicted 1680–1830 window failed because of route waiting/looping
  and geometry, not because Steward could never hit artillery.

M40 V2 confirmed the same late coverage: Steward began at 2281, hit artillery 19
times for 5405.47 before dying at 3160, and Lava added one 291.00 hit at 3850.

## Capability input boundary

The model received phase/level/skill/potential/trust-specific facts for all
eligible operators. `NOT_PLANNER_SAFE` was treated as an implementation-support
boundary, not a strength ranking. Steward's data included ATK 470, interval 1.6,
range `3-1`, cost 18, and the ATK-scaling auto skill; his GameData talent says
“prioritize highest-defense,” but current runtime does not implement that
priority. The current selector is opposing-faction hatred/distance/creation
order. V2 selected no 1-star operator. Its late 2-star caster `char_009_12fce`
was used for delayed roadblock #2 clearance; the plan explicitly denied splash
or dodge credit.

## V1 static feedback

V1's only static conflict was `char_4227_gallus` redeploying at frame 10200 with
cooldown still active. The exact candidate was not simulated and was not
repaired by Python. Attempt 2 changed this dependency.

## V2 saved simulation

Direct observations:

- First leak: `enemy_1107_uoffcr#12` at frame 3847; first objective failure at
  4625.
- The declared first observable—Midnight damaging roadblock #4 during frames
  630–690—was not observed. Roadblock #4 was later destroyed at 2151.
- Roadblocks #3, #4, #1 and #2 were eventually destroyed at 2025, 2151, 9624
  and 9801.
- Artillery received 20 hits totaling 5696.47 (19 Steward + 1 Lava), survived,
  and leaked at 5759.
- `#14` reached at 10133, while `#3` died at 5341 from artillery.
- Ten operators died: Hibiscus 2593, Ansel and Steward 3160, Fang 3520,
  Beagle and Lava 3910, Midnight 4119, Ardign and Durin 4600, Melantha 4753.
- Twenty-two later commands failed because their sources were no longer
  deployed.

Interpretation:

- V2 improved the roadblock-clearance ordering over M39 V4, but the core output
  and survival assumptions still failed. Steward died during the required
  artillery window, artillery survived, leaks increased, and the late civilian
  release did not compensate for the mid-stage losses.
- The absent 630–690 prediction shows that this plan's first key duty was not
  established. It does not alone prove every later failure; the later deaths,
  leaks and deaths are separate direct observations.

## Branch comparison

| Plan | WIN | Kills | Leaks | Protected targets | Roadblocks | Operators dead | Life | Artillery damage |
|---|---|---:|---:|---|---|---:|---:|---:|
| M30 V2 | LOSS | 20 | 13 | both reached | all four | 10 | -10 | 23 / 6626.06 |
| M31 V3 | LOSS | 22 | 11 | `#3` died; `#14` reached | three | 10 | -9 | 29 / 7959.67 |
| M39 V3 | LOSS | 19 | 14 | both reached | all four | 5 | -11 | 20 / 5822.17 |
| M39 V4 | LOSS | 17 | 16 | both died | one | 10 | -15 | 27 / 7609.45 |
| M40 V2 | LOSS | 15 | 18 | `#3` died; `#14` reached | all four | 10 | -16 | 20 / 5696.47 |

M40 V2 is not promoted. It adds a useful negative result: a durable-looking
central replacement plus late four-roadblock clearance does not solve the
artillery/leak bottleneck if the key caster dies before artillery is killed.

## Status

- V2 is a current-model simulator diagnostic LOSS only. It is not a simulator
  WIN, perfect WIN, probabilistic WIN, faithful result, robust result, or
  real-device result.
- No further fixed simulation was run because both CLI starts were exhausted;
  no new candidate could be generated or statically reviewed.
- The next bounded tactical decision should make the artillery-kill duty and the
  caster-survival/handoff duty jointly observable, then verify zero leaks and
  both protected arrivals; a single verified event remains insufficient.
