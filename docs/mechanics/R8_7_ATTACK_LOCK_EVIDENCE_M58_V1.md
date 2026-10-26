# R8-7 attack lock, cancel, and cooldown gate (M58 v1)

## Gate decision

`GATE_STOPPED_BEFORE_TACTICAL_CLI`. No M58 tactical CLI, full-stage simulation,
or budget STARTED was performed. The client evidence is sufficient to reject
the current simulator's ordinary-attack model as a proven real-client model for
lock/cancel behavior, but not sufficient to establish the real-client rule.
Using either H1, H2, or H3 as a tactical dependency would therefore turn an
UNKNOWN into a false deterministic fact.

## Client evidence basis

The sampled client tree is `/tmp/kimiark-m58-client-3089907`:

| Item | SHA256 |
|---|---|
| `native/libil2cpp.so` | `3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259` |
| `metadata/global-metadata.dat` | `bf14421bbafe9c71d944ba4f97b31ecd666232640eac0829db3d84ac716ac8b8` |
| `manifest/AndroidManifest.xml` | `92856638465aff947a54e24633134a43a4de45cd81221381896e8be1c1d46404` |

The current client is distinct from the 2.7.81 APK used by earlier checks:

| Item | SHA256 |
|---|---|
| 2.7.81 `libil2cpp.so` | `53c12224664f6fd4265905d12f5aaf74e315bc76584a5399d68c68defee14d2b` |
| 2.7.81 `global-metadata.dat` | `48b712f1664a0a686fd26dfe981da52cc9741899c98e63548f3d76133f10b3fa` |

The 3089907 metadata is encrypted in the same XOR/AES family as 2.7.81. A
temporary decrypted copy was used only for symbol lookup and was not committed.
Automatic Il2CppDumper did not finish because the protected ELF did not expose a
usable `MetadataRegistration`; exact method ranges below therefore combine the
decrypted-metadata lookup with direct ARM64 disassembly.

The M58 control-chain check then resolved the current-client method table
directly. The `Assembly-CSharp.dll` native module has 217,813 method pointers;
relevant tokens map to exact RVAs in
`m58_attack_control_chain_v1/evidence/2771_method_map_excerpt.txt`. This mapping
is cross-checked by plaintext calls from `RangedAttack.UpdateTargets`,
`RangedAttack.OnCastStart`, and `RangedAttack.CreateProjectile`. However, the
actual bodies of `Enemy.AttackState.OnEnter`, `OnTick`, `OnExit`, and
`_AttackFinishCallback` are not readable ARM64 in this static client; the first
instructions are obfuscated/encrypted. `RangedAttack.OnCastOnTarget` and
`RangedAttack.DoCastOnTargets` are also encrypted. Consequently, the pre-birth
ordinary target-loss transition cannot be closed without runtime or unpacked
evidence.

## Ordinary projectile facts from 3089907

The current material contains
`projectile_enemy_uoffcr.prefab` and `projectile_enemy_uamord.prefab`. Their
serialized fields contain:

- `_alwaysHitTraceTargetInTheEnd = 1`
- `_alwaysHitTraceTargetWhenReached = 0`
- `_alwaysReachInTheEnd = 0`
- `_delayToStart = 0`
- `_lifeTime = 5`
- `_maxHitNum = 1`
- `_stopWhenSourceInvalid = 0`

`Projectile.SetTraceTarget` writes the traced target reference into
`m_traceTarget` and its map position into `m_traceTargetMapPos`. This proves
that the projectile has a retained target reference after creation. It does not
prove that a withdrawn or dead target remains a valid hit target.
`Projectile._DealHitTraceTarget` can later call `DealHitTarget` for the retained
trace target after an already-hit/validity guard passes. The guard helper itself
does not reveal whether a retreated or dead unit still passes. Therefore this is
post-birth retained-reference evidence, not proof of a miss or of damage.

No current 2771 enemy body prefab binding for `enemy_1107_uoffcr` or
`enemy_1110_uamord` was available in the extracted materials. The projectile
resource names alone do not prove which ability object those enemies invoke; the
current-client body-to-ability binding remains `UNKNOWN`.

For artillery `projectile_enemy_emppnt`, the client prefab contains:

- `_delayToStart = 3`
- `_alwaysReachInTheEnd = 1`
- `_followTarget = 0`
- `_stopIfTargetDead = 0`
- `_stopIfTargetDisappeared = 0`

This supports the existing delayed, location-locked artillery model after the
projectile is born. It still does not establish whether the client can retarget
or cancel between ability cast start and projectile birth.

Current simulator terms must be separated. `_enemy_ability_outputs` selects a
target ID and starts cooldown at cast start. `_process_area_cast` runs at
projectile birth (`windup_seconds` later), reads the still-selected candidate's
current position, emits `PROJECTILE_BORN`, and only then locks the blast
position. If the source or target is unavailable at that instant, the simulator
cancels that pending cast but does not undo the already-started cooldown.

## Assumption table

| Attack type | Current implementation | Client evidence | Conclusion | Tactic dependency allowed? |
|---|---|---|---|---|
| Enemy/ordinary pre-birth lock | Target is selected again at `ATTACK_STRIKE`; `ATTACK_WINDUP` does not record a target ID. | Exact state scheduler and ranged cast-on-target bodies are encrypted in 2771. | Client lock timing: `UNKNOWN`. | No. |
| Ordinary attack after target retreat | If the old target disappears, the next strike reselects a new target; an empty candidate set does not consume the cycle. | Retained projectile reference and `_DealHitTraceTarget` are visible, but validity, retarget, cancel, and cooldown branches are not. | Client H1/H2/H3: `UNKNOWN`; implementation is H1-like. | No. |
| Ordinary attack cooldown | `next_attack_time` advances only after a real strike/damage; it is not reset by retreat or death of the old target. | `_AttackFinishCallback` body is encrypted. | Client cooldown start point: `UNKNOWN`. | No. |
| Artillery target/position split | `_enemy_ability_outputs` selects target and starts cooldown at cast start; `_process_area_cast` locks position at projectile birth. | 2771 projectile data support post-birth fixed impact. The exact client pre-birth selection/cancel path remains unknown. | Current implementation: split is code fact. Real client: post-birth fixed impact supported, pre-birth `UNKNOWN`. | Location/impact timing may be used; pre-birth bait cancel must not be treated as proven. |
| Artillery cooldown | Starts when cast starts; does not depend on later target state. | Ability/projectile data support the delayed cast shape, but exact 2771 cooldown reset is not closed. | Current model consistency: supported by existing recorded probes. Real-client cooldown branch: `PARTIAL`. | Keep model dependency labeled. |
| Attack recovery / movement pause | Separate `attack_stand_until` and `next_attack_time`. | Client has an attack-finish callback, but the movement pause transition is not closed. | Real-client semantics: `UNKNOWN`. | No. |

## Required next verification

Before treating ordinary-attack baiting as deterministic:

The next concrete action is to obtain an authorized current-client runtime trace
or memory-dump of the mapped methods at `0x292d0ac`, `0x292d628`, `0x292d7b0`,
`0x292d8f8`, `0x2d7fb64`, and `0x2d80404`. The required scenarios remain: normal
baseline; target withdrawn before projectile birth with another valid target;
target withdrawn after birth; no-substitute control; and death versus retreat.
Until then, do not convert either H1, H2, H3, or artillery pre-birth cancellation
into a deterministic client fact.

## Simulator consistency tests

Existing focused tests on the current branch passed:

```text
tests/simulator/test_enemy_runtime_fidelity.py
tests/simulator/test_enemy_ability_runtime.py
tests/simulator/test_stronghold_differential_micro.py
```

They establish implementation behavior only. They do not prove client rules.

## Budget and boundary

This increment started no tactical CLI and no fixed full-stage simulation. M58's
remaining authorized budget remains one tactical CLI and one full-stage
simulation. The result is version-limited static evidence for client 3089907; it
is not a claim about later builds, faithful Arknights behavior, robustness, or a
probability WIN.
