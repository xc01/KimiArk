# M38 artillery cast-to-hit timeline and saved-plan replay

## Scope and budget

- Tactical Codex CLI: **0/0**.
- Fixed full-stage simulations: **2/2**, using the two M37-authorized slots that
  had not been consumed. M30 V2 and M31 V3 were each run once; no plan, action,
  mechanism field, or historical artifact was modified.
- The unrelated pre-existing tracked modification to M26's
  `static_compile_results.json` remains unstaged.

## Evidence correction

The M36 disassembly attribution used a build-2771 `libil2cpp.so` hash while its
methods were actually extracted from the 2.7.81 candidate binary. The correct
candidate inputs are:

| Input | SHA-256 |
|---|---|
| 2.7.81 `libil2cpp.so` | `53c12224664f6fd4265905d12f5aaf74e315bc76584a5399d68c68defee14d2b` |
| decoded 2.7.81 metadata | `f4ec4e9b0c87effe9d10f284a90fd7e0cf4f5d21ffa5258f266ce8ce03d27a96` |

Signature verification remains `NOT_PERFORMED`. The M36 historical report and
manifest were not rewritten. This correction does not prove build-2771 equality.
The focused disassembly, artillery skeleton, animation facts, and file hashes are
committed in `client_evidence_manifest.json`.

## Client timeline

The evidence below is a **2.7.81 candidate model**, identified by the hashes
above.

1. `AbilityStandard.CastToTarget` at RVA `0x25544d4` starts casting and the
   M36-established cooldown clock starts here.
2. `RangedAttack.OnCastOnTarget` at RVA `0x2e4ee9c` runs the attack-event
   path. `GetTargetLocatable` at RVA `0x2e541fc` converts the selected target's
   `mapPositionV3` into `FixedPosition`.
3. The extracted artillery skeleton (`enemy_1112_emppnt.skel`) uses a Spine
   `Attack` animation with duration `1.166667` and an `OnAttack` event at
   `0.333333`. `AbstractAnimatedAbility.UpdatePlaybackSpeed` at RVA
   `0x2ea7e60` and `SpineAnimator.PlayAnimation` at RVA `0x257e5e0` confirm
   playback scaling. With attack time 5.0 and animation speed 1.0, creation
   occurs at `0.333333 × 1.166667 / 5.0 = 0.077778` seconds after cast start.
4. `RangedAttack.CreateProjectile` at RVA `0x2e52bd8` calls
   `BattleController.CreateProjectile` at RVA `0x25a989c`. The projectile then
   uses the separately recorded `_delayToStart=3.0`.
5. The reached-target query therefore occurs at approximately
   `cast_start + 3.077778` seconds. `INPUT_VECTOR3` is read at creation/lock,
   not at cast start; target movement before creation is followed and movement
   after creation cannot move the fixed blast point.

The client's configured body attack is the `RangedAttack` on its combat attack
mode. The current one-delayed-attack abstraction is therefore not contradicted,
but whether a build-2771 or client-state edge can emit a second ordinary attack
remains `UNKNOWN_SPECIFIC_BINDING`.

## Runtime correction

`EnemyAbility` now has `windup_seconds`, and artillery GameData sets it to
`0.07777777777777778`. Runtime now represents:

- cast selection and cooldown start;
- a pending cast ending at creation/lock time;
- a `PROJECTILE_BORN` event with the locked position;
- a pending area hit three seconds later;
- cancellation when the selected target is unavailable before creation.

The cooldown still starts at cast and ends at cast + 5.0; it is not shifted to
the later hit. This changes a real behavior rather than replacing one magic
number with another.

Focused regressions cover the unchanged zero-windup case, exact 3.077778
timing, movement before creation, fixed position after creation, consecutive
cast-start clocks, retained fixed-hit persistence, and target disappearance
before creation. The complete simulator suite passed **120 tests**. The broader
repository suite collected **593 tests** with **31 pre-existing failures** and
one expected skip. A detached parent-worktree comparison was run with the
untracked GameData tree linked in, but it is not an equivalent packaging
environment; it had 54 failures. Therefore the parent comparison is used only as
a non-equivalence boundary, not as proof that all 31 current failures are
unchanged byte-for-byte.

## Replay conditions and budget

The saved M30 V2 and M31 V3 action snapshots retained these hashes:

| Plan | Action SHA-256 |
|---|---|
| `R8_7_GPT_M30_V2` | `2225b9723536bda4eea2a8f72fa9582a296ad9aeeb276d69f1b0afae165cc880` |
| `R8_7_GPT_M31_V3` | `b1475a1796fb2364e03c0ec8e4486b622e371b842654e0349f0c323eef7ec382` |

The replay sources were the static-check `llm_evidence_context.json` and
`llm_structured_output.json` records used for M36. The new budget ledger records
`2/2 started`, `2/2 completed`, `0 failed`, and `0 tactical CLI`. Both replay
plans matched their frozen source plans. Original uncompressed events/summaries
remain in `output/`; committed evidence is gzip-compressed with before/after
SHA-256 records. `m38_replay_manifest_v1.json` binds each source, plan, action,
event, summary, and manifest hash.

Both saved replays contain no `STUN`, `SLOW`, `FEAR`, `FREEZE`, `INTERRUPT`, or
other runtime status event. Thus this constant-windup correction is applicable
to the saved conditions. Whether the enemy ever had multiple protected targets
simultaneously eligible, and whether a medic had multiple in-range candidates at
the same decision instant, remains `UNKNOWN_NOT_IN_EVENT_STREAM`; the event
stream records the selected target but not the complete candidate set.

## Replay comparison

| Plan | Version | Casts | Artillery damage | Kills | Leaks | Operator deaths | Life | First objective failure | Protected #3 | Protected #14 |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| M30 V2 | M36 | 17 | 23 hits / 6626.06 | 21 | 12 | 10 | -9 | frame 5196 / life 0 at 173.2 | reached 3566 | reached 5297 |
| M30 V2 | M38 | 17 | 23 hits / 6626.06 | 20 | 13 | 10 | -10 | first leak 4500; life 0 at 5046 / 168.2 | reached 3566 | reached 5297 |
| M31 V3 | M36 | 24 | 28 hits / 7829.17 | 22 | 11 | 9 | -9 | first leak 5469; life 0 at 5759 / 191.97 | died 5343 | reached 9317 |
| M31 V3 | M38 | 23 | 28 hits / 7829.17 | 22 | 11 | 9 | -9 | first leak 5469; life 0 at 5757 / 191.9 | died 5346 | reached 9317 |

M30 V2 is structurally unchanged in cast count and artillery damage but one
later casualty/leak cascade moves the first leak three seconds earlier and costs
one more life. Both protected targets still reach safely and all four roadblocks
still fall.

M31 V3 loses one cast at frame 4443. The visible aggregate artillery damage and
operator-death count are unchanged, #3's death moves 5343→5346, and the first
leak/objective failure move by only 2–3 frames. Roadblocks #3 and #4 still fall;
#1 remains intact and #14 still reaches.

## Results and boundaries

Both are current-model simulator `LOSS`, not WIN. Neither is a perfect objective
pass because leaks remain. M30 V2 remains the stronger complete-route branch;
M31 V3 remains the stronger early-artillery-output branch. They remain
structurally incomparable and cannot be treated as one best plan by kill count.

No faithful, robust, probabilistic, or real-device win is claimed. The runtime
result is a 2.7.81 candidate mechanism, not a build-2771 proof.
