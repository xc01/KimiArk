# M37 R8-7 clock, selector, and medical evidence

## Scope and budget

- Tactical Codex CLI: **0/0**.
- New full-stage simulations: **0/2**. No behavior-changing Python correction was
  justified by the newly decoded evidence, so the two authorized M37 slots remain
  unused and historical M36 replay artifacts were not rerun.
- Evidence remains a **2.7.81 candidate model**; build-2771 identity is not
  claimed. Signature verification remains `NOT_PERFORMED`.

## Inputs

The disassembly fragments below come from the M36 2.7.81
`libil2cpp.so` and decoded `global-metadata.dat`. The binary SHA-256 is
`3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259`; decoded
metadata SHA-256 is
`f4ec4e9b0c87effe9d10f284a90fd7e0cf4f5d21ffa5258f266ce8ce03d27a96`. Files are
named by their SHA-256 under `disassembly/`.

| Method | Start RVA | Purpose |
|---|---:|---|
| `AbilityStandard.CastToTarget` | `0x25544d4` | Cast start and cooldown reset |
| `AbilityStandard.DoOnHasNoTarget` | `0x2558ad4` | No-target branch |
| `AbilityStandard.OnTick` | `0x2559ac4` | Ability tick entry |
| `RangedAttack.OnAttackTimeChanged` | `0x2e57610` | Attack-time propagation |
| `AbstractAnimatedAbility.get_cooldown` | `0x2ea6740` | `_cooldownKey='duration'` resolution |
| `AbstractAnimatedAbility.OnAttackTimeChanged` | `0x2ea69ec` | Reset with retained progress |
| `SecondaryFilterAdvancedSelector.OnPostFilter` | `0x2972c1c` | Buff promotion and sorting |
| `SecondaryFilterAdvancedSelector._CheckSecondFilter` | `0x2973410` | Buff membership filter |
| `FilterUtil._Filter_HpRatioNotFullAsc` | `0x2960e98` | Medic `_postFilter=3` |
| `FilterUtil._Filter_HatredDes` | `0x29618e8` | Artillery `_postFilter=4` |

## Attack clock

The closed 2.7.81 candidate-model edge sequence is:

1. `AbilityStandard.OnTick` reaches `Ability.OnTick` at RVA `0x255213c`, which
   owns the periodic timer at ability offset `0x70`.
2. With no valid target, `DoOnHasNoTarget` may finish with reason `3`; its
   decoded path contains no `PeriodicTimer.Reset` or `ResetButKeepProgress`.
   This supports not restarting the cycle while waiting for a target.
3. When a target exists, `CastToTarget` calls `PeriodicTimer.Reset` at
   `0x2554840`, then calls `StartCastingInternal` and `_DoCast`. Thus the
   candidate-model cooldown starts at cast start, not cast end.
4. Attack-time changes are handled by
   `AbstractAnimatedAbility.OnAttackTimeChanged` through
   `PeriodicTimer.ResetButKeepProgress`; `RangedAttack.OnAttackTimeChanged`
   calls the base handler and forwards the event to projectile children.
   `get_cooldown` resolves `_cooldownKey='duration'` to owner attack time.
5. The separately configured projectile `_delayToStart=3.0` is not evidence that
   the attack cycle starts at projectile creation. The decoded cast-start reset
   precedes `_DoCast`; exact projectile-creation and animation-event timing
   remain UNKNOWN.

Python already resets `ability_next_fire_time` when a delayed locked-area cast
starts and does not reset it on an empty-target scan. The M37 regressions cover
waiting before a target appears, a locked hit after the selected operator
retreats, and two consecutive casts. They do not make animation timing or
build-2771 identity proven.

## Selector and medical behavior

`SecondaryFilterAdvancedSelector.OnPostFilter` performs `FilterUtil.Filter`,
then promotes candidates accepted by `_CheckSecondFilter` to the list front. For
the artillery selector, `_secondaryFilter=3` is buff membership against
`mark_neutral[effect]`. `_sortByTauntAtLast=1` then applies taunt-last sorting
before `maxTargetNum=1` truncation. `_Filter_HatredDes` returns negated hatred.

This confirms why `mark_neutral` can outrank a higher-hatred operator. It does
not fully close the artillery tie: Python has no client hatred value and uses
spawn index for neutral candidates. The mark-neutral promotion outcome is
regression-covered; exact hatred ordering and taunt tie-breaking remain UNKNOWN.

`FilterUtil._Filter_HpRatioNotFullAsc` calls `Entity.get_hpRatio` and rejects
full-HP candidates. This confirms the Python medic rule of selecting the lowest
HP-ratio ally below max HP. It does not prove the final equal-ratio tie-break or
all skill/heal-free interactions; Python's operator-ID tie-break remains a
project rule.

## Validation and M36 record correction

Historical M36 replay artifacts remain unchanged. They were produced before the
active mechanics version was relabeled, so their `mechanics_version` field
alone must not be treated as a runtime-source hash or as proof of parent-code
equivalence. The derived interpretation is in this report; no old artifact was
rewritten.

The prior claim that 31 broader failures were unchanged by only restoring the
version label is now explicitly downgraded to a non-equivalent environment
comparison. A parent-worktree comparison result is recorded in
`parent_test_comparison.json`. With fixed GameData, PRTS inputs, `uv.lock`, and
`dev`/`client-evidence` dependencies equalized, the parent had 585 tests /
47 failures, while current had 590 tests / 31 failures. All 31 current failures
are common with the parent; there were no current-only failures. Sixteen
parent-only failures remain attributable to historical code/artifact
differences and untracked local outputs that were not copied into the parent.
This is a bounded comparison, not a claim that every dependency of every test
was cloned.

## Remaining decisive UNKNOWN

- Build-2771 equivalence for the clock and selector.
- Exact animation event, projectile creation frame, and cast-end semantics.
- Ordinary attack versus special artillery mutual exclusion.
- Client interruption semantics on stun/freeze/levitate.
- Mid-cast attack-time-change behavior when the runtime actually applies such a
  change to R8-7.
- Neutral hatred values, hatred ranking, and taunt/equal-rank tie-breaks.
- Medic equal-ratio tie-break and skill interactions beyond the decoded filter.

These do not block interpreting the existing R8-7 runs, but they do prevent
calling the model faithful, robust, or client-identical.
