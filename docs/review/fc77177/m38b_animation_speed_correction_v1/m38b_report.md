# M38b animation-speed correction and saved-plan reverification

## Scope and budget

- Tactical Codex CLI: **0/0**.
- Newly authorized fixed full-stage simulations: **2/2** used; M30 V2 and
  M31 V3 ran once each. A ledger-finalization bug occurred after the first
  simulation had completed; `--resume` validated the existing artifacts and did
  not repeat any run. The second run then consumed the second slot normally.
- Historical M38 artifacts are unchanged and remain valid only for their
  artifact hashes and broad timeline structure, not for the old wind-up number.

## Corrected formula

The disassembly is a **2.7.81 candidate model** and remains
`signature_verification=NOT_PERFORMED`. `libil2cpp.so` and decoded metadata
hashes are recorded in the M38 evidence manifest.

1. `AbstractAnimatedAbility.UpdatePlaybackSpeed` at RVA `0x2ea7e60` obtains the
   raw animation time/speed, computes
   `animScale = max(attackTime / rawAnimationDuration, 0.1)`, and stores the
   float scale at ability offset `+0x1b8`. `_maxAnimScale` at `+0x1a0` is the
   upper clamp. A nonzero `slowDown` when `_affectedBySlowDown` is set uses
   `animSlowDown`: raw duration and the cap are divided by `animSlowDown`; the
   ordinary absolute cap uses `maxAnimScale`, while the slowdown cap uses
   `min(maxAnimScale / animSlowDown, 2.5)`.
2. The final out value written at `0x2ea81ec..0x2ea81f4` is
   `animationDataSpeed * animSlowDown / animScale`. Thus `animationData.speed`
   is animation seconds advanced per real second; the scale converts cast time
   into animation time.
3. `SpineAnimator.PlayAnimation` at `0x257e914` also confirms its return value
   is `rawDuration / animationDataSpeed`.
4. For a raw event, actual time from cast start is
   `rawEventTime * animScale / (animationDataSpeed * animSlowDown)`. Units are
   seconds on both sides of this conversion.

For artillery: raw duration `1.166667 s`, raw `OnAttack` `0.333333 s`,
`attackTime=5.0 s`, animation speed `1.0`, `_maxAnimScale=1.0`, and
`_affectedBySlowDown=true`. With no slowdown status,
`animScale=min(5/1.166667, 1)=1`, so creation occurs at
`0.333333 s`, not M38's `0.077778 s`. The hit remains creation `+3.0 s`.

Runtime now stores these raw inputs separately on `EnemyAbility`
(`animation_event_time_seconds`, `animation_duration_seconds`,
`animation_speed`, `attack_time_seconds`, `max_anim_scale`, and
`affected_by_slow_down`) and derives `windup_seconds`; it does not encode the
corrected result in a GameData adapter constant.

## Test boundary

Focused simulator additions cover speed `1/2/0.5`, the max-scale clamp,
slowdown scaling, full artillery derivation, projectile creation, post-creation
position lock, and cancellation before creation. The simulator suite passed
**123 tests**. The broader repository suite collected **596 tests** with **31
known failures** and one expected skip; every failing ID matches the M37
recorded common-failure set, so this correction introduced no new full-suite
failure. Independent expectations come from the disassembly and resource facts,
not from the current implementation.

## Replays

| Plan | Simulator result | Kills | Leaks | Operators dead | Life | Protected #3 | Protected #14 | Casts | Artillery damage | Artillery damage to operators |
|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|
| M30 V2 | LOSS | 20 | 13 | 10 | -10 | reached 3566 | reached 5297 | 17 | 23 / 6626.06 | 24 / 19960 |
| M31 V3 | LOSS | 22 | 11 | 10 | -9 | died 5353 | reached 9317 | 23 | 29 / 7959.67 | 26 / 21872 |

M30 V2 differs from M38 only by later hits moving through the same damage/leak
chain: first operator damage/death shifts `1326 -> 1333` and first leak
`4500 -> 4507`. Cast count, aggregate artillery damage, and both protected-target
arrivals remain unchanged.

M31 V3 keeps 23 casts but changes the casualty chain. Gallus dies
`1083 -> 1090`, Steward `3036 -> 3043`, Ansel `3936 -> 3793`, and Lava now dies
at 3943. Artillery damage rises `7829.17 -> 7959.67` with one extra hit, while
artillery damage to operators rises `21263 -> 21872` with one extra hit. #3 dies
`5346 -> 5353`; the artillery leak moves `5757 -> 5759`, the next ordinary leak
moves `5757 -> 5791`, and the final life failure remains 5759. The branch is
still LOSS and is not a tactical WIN.

## Status and unknowns

- Both are current-model simulator diagnostic LOSS values. Neither is a
  simulator WIN, probabilistic WIN, faithful result, robust result, or real-device
  result.
- The correction is limited to the saved no-slowdown replay conditions. The
  slowdown branch is implemented from the candidate client formula, but no
  R8-7 replay exercises it as an end-to-end combat condition.
- Ordinary/special mutual exclusion, interruption, build-2771 equality, exact
  protected-target hatred/tie-break, and exact medical tie-breaks remain outside
  this correction.
