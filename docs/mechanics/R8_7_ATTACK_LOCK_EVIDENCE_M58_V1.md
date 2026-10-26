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

## Ordinary projectile facts from 3089907

For `projectile_enemy_uoffcr` and `projectile_enemy_uamord`, the client prefabs
contain:

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

For artillery `projectile_enemy_emppnt`, the client prefab contains:

- `_delayToStart = 3`
- `_alwaysReachInTheEnd = 1`
- `_followTarget = 0`
- `_stopIfTargetDead = 0`
- `_stopIfTargetDisappeared = 0`

This supports the existing delayed, location-locked artillery model after the
projectile is born. It still does not establish whether the client can retarget
or cancel between ability cast start and projectile birth.

## Assumption table

| Attack type | Current implementation | Client evidence | Conclusion | Tactic dependency allowed? |
|---|---|---|---|---|
| Ordinary melee/ranged target lock | Target is selected again at `ATTACK_STRIKE`; `ATTACK_WINDUP` does not record a target ID. | `RangedAttack.OnCastStart` starts `_DoCast` and calls `UpdateTargets`; `RangedAttack.OnCastOnTarget` can create a projectile with an explicit target. The exact transition from cast start through target loss to projectile creation is not closed. | Client lock timing: `UNKNOWN`. | No. |
| Ordinary attack after target retreat | If the old target disappears, the next strike reselects a new target; an empty candidate set does not consume the cycle. | Not closed. The ordinary projectile keeps a trace reference after birth, but the client validity/cancel branch is unresolved. | Client H1/H2/H3: `UNKNOWN`; implementation is H1-like. | No. |
| Ordinary attack cooldown | `next_attack_time` advances only after a real strike/damage; it is not reset by retreat or death of the old target. | Attack-finish callback exists, but the precise reset branch and first-vs-stable attack difference are not closed. | Client cooldown start point: `UNKNOWN`. | No. |
| Artillery cast lock | Cast start selects a candidate and locks the position; a later hit occurs after windup plus delay. | `projectile_enemy_emppnt` has `_delayToStart = 3`, `_alwaysReachInTheEnd = 1`, `_followTarget = 0`; target-dead/disappeared stops are disabled. | Post-birth fixed impact: supported. Pre-birth retarget/cancel: `UNKNOWN`. | Location/impact timing may be used; pre-birth bait cancel must not be treated as proven. |
| Artillery cooldown | Starts when the cast starts; does not depend on later target state. | Ability/projectile data support the delayed cast shape, but the exact cooldown-reset branch is not independently closed. | Current model consistency: supported by existing recorded probes. Real-client cooldown branch: `PARTIAL`. | Keep model dependency labeled. |
| Attack recovery / movement pause | Separate `attack_stand_until` and `next_attack_time`. | Client has an attack-finish callback, but the movement pause transition is not closed. | Real-client semantics: `UNKNOWN`. | No. |

## Required next verification

Before treating ordinary-attack baiting as deterministic:

1. Resolve the exact client chain from cast start through `AttackState`,
   `AbilityStandard.CastToTarget`, target invalidation, and projectile creation.
2. Confirm whether a target that is retreated, killed, or leaves range leaves
   the projectile reference valid, cancels the projectile, or causes a miss.
3. Determine whether invalidation consumes the remaining attack cycle and where
   the next cooldown starts.
4. Distinguish first attack from stable continuous attack and the melee, ranged
   projectile, and artillery branches.
5. Run the three minimal client scenarios: normal baseline; target withdrawn
   before projectile birth with another valid target; target withdrawn after
   projectile birth. Add a no-substitute-control case and compare killed versus
   retreated targets.

## Simulator consistency tests

Existing focused tests on the current branch passed:

```text
tests/simulator/test_enemy_runtime_fidelity.py
tests/simulator/test_enemy_ability_runtime.py
tests/simulator/test_stronghold_differential_micro.py
```

They establish implementation behavior only. They do not prove client rules.
