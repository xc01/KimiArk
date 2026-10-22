# M36 2.7.81 artillery behavior and saved-plan re-verification

## Scope and budget

- Tactical Codex CLI: **0/0**.
- Full-stage simulations: **2/4 total M36 ledger slots**, using exactly the two simulations left from M32. No historical ledger was reset.
- Model/provider/account: unchanged; no new tactical model output was requested.
- Historical M29/M30/M31/M32 artifacts were not overwritten.
- The unrelated pre-existing modification to
  `output/r8_1_r8_7_batch_v1/main_08-07/m26_tactical_revision_v1/attempt_04_cli/static_compile_results.json`
  remains unstaged and is not part of this milestone.

## Version evidence

The client evidence remains a **2.7.81 migration candidate**, not a build-2771
identity claim. Signature verification was not performed.

| Item | Value |
|---|---|
| Client version | `2.7.81` |
| Resource version | `26-10-14-13-45-10-99469376` |
| APK SHA-256 | `1a505eb9bc722ac24f05666e1e3536bd8fb4ed931dc70678a5699ea3a1cf368a` |
| `libil2cpp.so` SHA-256 | `3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259` |
| Decoded metadata SHA-256 | `f4ec4e9b0c87effe9d10f284a90fd7e0cf4f5d21ffa5258f266ce8ce03d27a96` |
| Signature verification | `NOT_PERFORMED` |

The resource-to-attack binding established in M35 remains unchanged:
`enemy_1112_emppnt -> RangedAttack -> projectile_enemy_emppnt`, with fixed
`INPUT_VECTOR3`, `_delayToStart=3.0`, and a 1.2 collision radius. The focused
disassembly snapshots are in `disassembly/` and listed by SHA-256 in
`m36_reverification_manifest_v1.json`.

## New client behavior

`AbstractAnimatedAbility.get_cooldown` at RVA `0x2ea6740` handles the configured
`_cooldownKey='duration'` by returning `Entity.get_attackTime` from the ability
owner. Since the resource also sets `_cooldown=0`, this means the effective
cooldown is the owner's attack time, not a separately configured zero.

`AbstractAnimatedAbility.OnAttackTimeChanged` at RVA `0x2ea69ec` calls
`PeriodicTimer.ResetButKeepProgress` on the periodic cooldown timer.
`RangedAttack.OnAttackTimeChanged` at RVA `0x2e57610` calls that base handler
and forwards the attack-time change to projectile children. Therefore the
periodic clock is tied to attack-time changes, not to the presence of an
immediate target and not to each failed candidate scan.

## Runtime correction

The old Python path reset `enemy.ability_next_fire_time` after every attempted
enemy-ability pass, including `DELAYED_LOCKED_AREA_ATTACK` passes that found no
target. This repeatedly restarted the 5-second artillery window.

The corrected `Simulator` sets `ability_next_fire_time` only when an actual
delayed locked-area cast begins. Other enemy ability families retain the old
post-cycle reset behavior. The behavioral regression proves an artillery unit
spawned at time 0 with a protected target appearing at time 2 casts at time 2
and hits at time 5.

The active runtime version is now `m36-2781-artillery-clock-v1`. The two replay
artifacts were generated before that version label was applied, so their
`mechanics_version` fields still say `m23-behavioral-mechanics-v1`; their results
are interpreted with the M36 corrected behavior documented here. The historical
replay artifacts were not rewritten.

Changed files:

- `src/arknights_planner/simulator/simulator.py`
- `tests/simulator/test_deep_mechanism_regressions.py`
- `scripts/build_m36_key_chain_summary_v1.py`

## Regression result

Both focused clock tests passed. The complete simulator regression passed with
113 tests.

```bash
PYTHONPATH=.:src:scripts UV_CACHE_DIR=/tmp/kimiark_uv_cache uv run pytest -q tests/simulator
```

A broader regression found 31 pre-existing failures. The same 31 test IDs were
rerun in this working tree with only `ACTIVE_MECHANICS_VERSION` temporarily
restored to `m23-behavioral-mechanics-v1`; they failed identically. The parent
commit could not be used as an equivalent environment because the required
GameData files are untracked. Thus these 31 failures are environmental/pre-existing
comparisons, not failures introduced by M36.

## Frozen-input re-verification

Both original action snapshots retained the hashes established in M32:

| Plan | Action SHA-256 |
|---|---|
| `R8_7_GPT_M30_V2` | `2225b9723536bda4eea2a8f72fa9582a296ad9aeeb276d69f1b0afae165cc880` |
| `R8_7_GPT_M31_V3` | `b1475a1796fb2364e03c0ec8e4486b622e371b842654e0349f0c323eef7ec382` |

The full original events and diagnostic summaries are preserved outside the
repository in the authorized M36 output directories and are committed here only
as lossless gzip files. `m36_reverification_manifest_v1.json` records both the
pre-compression and post-compression hashes.

## Result comparison

The old numbers below are the M32 baseline. The new numbers are the M36 replay
after the 2.7.81-backed clock correction.

| Plan | Version | Kills | Leaks | Operator deaths | Life | First objective failure |
|---|---|---:|---:|---:|---:|---|
| M30 V2 | M32 | 23 | 10 | 10 | -7 | frame 5759 |
| M30 V2 | M36 | 21 | 12 | 10 | -9 | frame 5196 |
| M31 V3 | M32 | 22 | 11 | 10 | -9 | frame 5759 |
| M31 V3 | M36 | 22 | 11 | 9 | -9 | frame 5759 |

### M30 V2

- The first 14 ability starts move earlier: M32 starts `1290, 1890, 2040, ...`;
  M36 starts `1233, 1773, 1923, ...`.
- Steward is the only source of artillery damage in both runs. Damage changes
  from 25 hits / `7348.45` to 23 hits / `6626.06`.
- Hits from the artillery on operators change from 21 to 24, while later-plan
  dynamics produce more ordinary leaks.
- Both protected targets still arrive (#3 frame 3566, #14 frame 5297); neither
  dies.
- All four roadblocks are still destroyed (#3/2025, #4/2820, #1/3234,
  #2/4965).
- Result: `MECHANICS_CORRECTED_DIAGNOSTIC_LOSS`; not WIN and not a perfect
  objective pass because enemies leak.

### M31 V3

- M32's clock stayed idle after frame 990 until frame 2040; M36 casts again at
  frame 1893 and continues earlier. This produces 24 starts versus 22.
- Artillery damage changes from 30 hits / `8285.47` to 28 hits / `7829.17`.
  In M36: Steward `4658.17`, Lava `2910.0`, Gallus `261.0`.
- Artillery hits on operators change from 21 to 26.
- The first leak remains frame 5469, but protected target #3 dies earlier:
  frame 5430 in M32, frame 5343 in M36.
- Roadblocks destroyed remain #3/1725, #4/2421, #2/8985; #1 remains intact.
- Result: `MECHANICS_CORRECTED_DIAGNOSTIC_LOSS`; #14 still arrives at frame
  9317, but #3 dies and enemies leak.

## Interpretation

The correction is behaviorally meaningful but does not make either saved plan a
WIN. M30 V2 keeps the stronger complete-route branch: both protected targets
arrive and all four roadblocks are destroyed. M31 V3 keeps the stronger early
artillery-output branch but loses #3 and leaves roadblock #1 intact. Neither
branch should be reduced to a single best by kill count; their structural
advantages remain incomparable.

The old “4714.53 remaining HP” was a conditional M31 V3/M32 diagnostic value,
not a universal damage shortfall requirement. The corrected M31 V3 value is
`5170.83` under the no-enemy-recovery assumption used by the compact summary.

## Remaining UNKNOWN

- Build-2771 is not proven identical to the 2.7.81 clock.
- The exact neutral-versus-operator runtime ranking and taunt tie-break ordering
  remain unknown.
- The complete damage formula, modifier order, and wall/camouflage edge cases
  remain unknown.
- Medic `_postFilter=3` runtime semantics remain unknown.
- Ordinary/special attack mutual exclusion and exact animation-event/projectile
  creation timing remain unknown.
- No faithful, robust, probabilistic, or real-device WIN is claimed.
