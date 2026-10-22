# R8-7 decisive mechanism coverage

## Evidence discipline

This table deliberately separates the five evidence layers:

1. **GameData** — configuration fact in the fixed JSON files.
2. **Client behavior** — build 2771 resource payload, disassembly, or PRTS
   supplementary evidence. `CONFIRMED_FROM_CODE` is qualified as
   `CLIENT_CODE`; a project function is never promoted to client fact.
3. **Python implementation** — what the current simulator does.
4. **Cross-validation** — whether those two behavior layers have been checked.
5. **Difference and experiment impact** — the known or unresolved mismatch.

Old simulation results remain valid as records of the **current Python model**.
They do not become client-behavior evidence merely because their inputs are
frozen or their hashes are known.

## Fixed inputs and provenance

The GameData working tree matches the contents identified by the comment in
`ArknightsGameData-master.zip`:

| Input | SHA-256 |
|---|---|
| `ArknightsGameData-master.zip` commit | `0ef7f952dfd018392200157a5c79a6511ba69122` |
| `zh_CN/gamedata/levels/obt/main/level_main_08-07.json` | `c9c376e3d5b37e5f764006fce5d1c94f12f233c995545adfe36c2beb8573cdc8` |
| `zh_CN/gamedata/levels/enemydata/enemy_database.json` | `7175461f03c2b29d0dc336d34d7b717dc0e33403b649b745ff852af7aef731bd` |
| `zh_CN/gamedata/excel/character_table.json` | `42708ca01b1938df4e2c3ed9e9efeadbf0e35533411907dadb37b80315e69ae8` |

Client inputs:

| Input | SHA-256 |
|---|---|
| `arknights-hg-2771.apk` | `0b79b85383e21a6343283bc6bfd7a9d24eb4134abf901115f757da6a5d50f6db` |
| `lib/arm64-v8a/libil2cpp.so` | `3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259` |
| `assets/bin/Data/Managed/Metadata/global-metadata.dat` | `bf14421bbafe9c71d944ba4f97b31ecd666232640eac0829db3d84ac716ac8b8` |

M38 correction: the focused M36 artillery methods were generated from the
**2.7.81** candidate binary, not from the build-2771 binary listed above. The
correct candidate binary hash is
`53c12224664f6fd4265905d12f5aaf74e315bc76584a5399d68c68defee14d2b`; its decoded
metadata is
`f4ec4e9b0c87effe9d10f284a90fd7e0cf4f5d21ffa5258f266ce8ce03d27a96`. This does
not change the build-2771 hashes above and does not establish version identity.
The historical M36 report and manifest are left as records.

The reproducible extraction and resource-index scripts are
`scripts/extract_m32_client_evidence_v1.py` and
`scripts/extract_m32_resource_index_v1.py`. Committed artifacts are in
`docs/review/fc77177/m32_external_mechanism_evidence_v1/`; `output/` remains a
local scratch location. Build 2771 and the fixed GameData commit are recorded
together, but their semantic versions are not inferred to be equivalent.

M34 additionally decoded both build-2771 `.idx` resource manifests. The
`main.idx` payload is a signed but unencrypted FlatBuffer with 2,528 bundles and
56,001 asset mappings; no AES key or IV is needed. It contains
`projectile_enemy_emppnt` but not the artillery body prefab. The larger
`resource_manifest_idx.json` in the fixed GameData tree is a separate reference
manifest, not the build-2771 manifest. Details and hashes are in
`docs/review/fc77177/m34_manifest_decoder_v1/m34_manifest_decoder_report.md`.

## R8-7 chain status

| Mechanism | GameData | Client evidence | Python implementation | Cross-validation | Difference / impact | Status |
|---|---|---|---|---|---|---|
| Artillery attributes | `enemy_1112_emppnt` level 0: HP 13000, ATK 1000, DEF 800, RES 50%, radius 2.0, base attack time 5.0, FLY/RANGED. | No `enemy_1112_emppnt` prefab was found in the indexed APK bundles or decoded build-2771 initial manifest. Attributes are GameData-only. | Loads these values from GameData. | Attribute values only; no client runtime attributes checked. | No known difference, but client application of the values is not independently checked. | `CONFIRMED_FROM_GAMEDATA; PROJECT_CODE_ONLY` |
| Artillery delayed projectile | Enemy `skills` is `null`; no ability blackboard identifies the delayed attack. | Build-2771 still lacks the body bundle. The 2.7.81 migration evidence binds `enemy_1112_emppnt.prefab` through `_modes[0] -> combat/attack -> _projectileKey='projectile_enemy_emppnt'`, with `_selectTargetTiming=1` (`BEFORE_SPELL_START`) and `_projectileDestination=2` (`INPUT_VECTOR3`). Its projectile has `_delayToStart=3.0`, `_followTarget=0`, `_stopIfTargetDead=0`, `_alwaysReachInTheEnd=1`, `_lifeTime=10.0`, and `_maxHitNum=1`. | Uses hardcoded `DELAYED_LOCKED_AREA_ATTACK` with a 3.0-second hit delay and 1.2 blast radius. | Projectile and movement fields match in both versions. The ability body binding is only 2.7.81; build-2771 ability/action serialization remains missing. | The Python cooldown, damage conversion, and action sequence remain project rules, not build-2771 client rules. | `PARTIALLY_CONFIRMED_FROM_CLIENT_2_7_81; BUILD2771_BINDING_UNKNOWN` |
| Protected-target acquisition priority | Neutral protected target is in GameData. | The 2.7.81 enemy attack selector has `_targetSide=2`, `_targetMotion=3` (`ALL`), `_targetCategory=1` (`DEFAULT`), `_postFilter=4` (`HATRED_DES`), `_secondaryFilter=3`, `_sortByTauntAtLast=1`, and includes `mark_neutral[effect]`. `SecondaryFilterAdvancedSelector.OnPostFilter` at RVA `0x2972c1c` calls `FilterUtil.Filter`, promotes the buff-filtered candidates to the list front, applies taunt-last sorting, and truncates to `maxTargetNum`. `_Filter_HatredDes` at RVA `0x29618e8` returns negated hatred. | Chooses neutral protected targets first, otherwise deployed operators. Neutral candidates are ordered by spawn index. | The client mark-neutral promotion before hatred sorting is confirmed. Python's protected-target-first outcome matches promotion, but no neutral hatred value or client taunt tie-break is modeled. | When two protected targets have different hatred, Python's spawn-index tie rule is not client-validated. | `SECONDARY_FILTER_ORDER_CONFIRMED_2_7_81; HATRED_AND_TIE_BREAK_UNKNOWN` |
| Locked blast position | None. | Projectile `_followTarget=0`, `_stopIfTargetDead=0`, and `_alwaysReachInTheEnd=1`. In 2.7.81 the attack sets `_projectileDestination=INPUT_VECTOR3` and selects targets `BEFORE_SPELL_START`; `RangedAttack.GetTargetLocatable` at RVA `0x2e541fc` converts target `mapPositionV3` to a fixed position. `CreateProjectile` at RVA `0x2e52bd8` calls `BattleController.CreateProjectile` at RVA `0x25a989c`. The extracted `enemy_1112_emppnt.skel` has an `Attack` animation of `1.166667` seconds with `OnAttack` at `0.333333`; `UpdatePlaybackSpeed` uses `attackTime/rawDuration`, clamps it by `_maxAnimScale=1.0`, and `SpineAnimator.PlayAnimation` divides duration by speed, so the uncapped event is `0.333333` seconds after cast start. | Selects a target at cast start, locks its current route position at projectile creation, then hits the fixed position after another 3.0 seconds. Cooldown remains cast-start + 5.0. | Fixed position, persistence after target death, and the separate 0.333333-second wind-up match the 2.7.81 candidate evidence and M38b regressions. M38's 0.077778-second result used the wrong division direction. | Target death/hidden state immediately before creation is modeled as cancellation; exact client re-target or interruption behavior remains UNKNOWN. The 2.7.81 candidate is not build-2771 proof. | `CONFIRMED_FROM_CLIENT_2_7_81; FIXED_BY_M38B_REGRESSION` |
| Blast geometry | None. | `CircleCollider2D` on `projectile_enemy_emppnt` has `m_Radius=1.2000000476837158`; the same GameObject binds `HitBehaviour`. In 2.7.81, `HitBehaviour.OnProjectileReached` calls `Box2dPhysicsUtil.FindTargets_DISPOSE`, and `HitBehaviour.Init` initializes target options/layer mask from source and projectile. | Uses 1.2-unit circular radius with inclusive boundary epsilon. | Radius is an input to the reached-target physics query, not merely a visual field. Exact inclusive-boundary and wall qualification code remains unclosed. | Do not treat 1.2 as the acquisition range; GameData separately says enemy range radius 2.0. | `REACHED_TARGET_QUERY_INPUT_CONFIRMED_2_7_81; EDGE_SEMANTIC_UNKNOWN` |
| Normal attack versus special artillery | None. | No specific enemy ability prefab or action-node payload found. | Suppresses ordinary projectile output while `DELAYED_LOCKED_AREA_ATTACK` exists. | Not validated. | Cannot infer whether client allows ordinary attacks during/inside the special-ability cycle. | `UNKNOWN_SPECIFIC_BINDING` |
| Ability clock | Base attack time 5.0. | In 2.7.81 the attack has `_cooldown=0` and `_cooldownKey='duration'`, with `_waitForAttackEvent=1`. `AbstractAnimatedAbility.get_cooldown` at RVA `0x2ea6740` resolves this key to `Entity.get_attackTime`; `OnAttackTimeChanged` at RVA `0x2ea69ec` calls `PeriodicTimer.ResetButKeepProgress`. `AbilityStandard.CastToTarget` at RVA `0x25544d4` calls `PeriodicTimer.Reset` immediately before `StartCastingInternal` and `_DoCast`; `DoOnHasNoTarget` at RVA `0x2558ad4` ends with reason 3 without resetting that timer. `RangedAttack.OnAttackTimeChanged` at RVA `0x2e57610` calls the base handler and forwards the event to projectile children. `AbstractAnimatedAbility.UpdatePlaybackSpeed` at RVA `0x2ea7e60` and `SpineAnimator.PlayAnimation` at RVA `0x257e5e0` establish animation timing. | Schedules the next special ability only when a delayed cast starts, at `cast_time + attack_time`; absence of a target does not restart the cycle. The projectile creation event is `cast_time + 0.333333` and hit time is `cast_time + 3.333333`. | 2.7.81 cast-start/no-target, animation-event, and fixed-lock evidence match the runtime regressions. M38b corrected the playback-scale direction and separated raw animation fields from the derived runtime wind-up. | This proves the 2.7.81 candidate-model clock, not build-2771 equality. Ordinary/special mutual exclusion, interruption behavior, and mid-cast attack-time rescheduling remain not fully closed. | `CONFIRMED_FROM_CLIENT_2_7_81; FIXED_BY_M36_AND_M38B_REGRESSIONS` |
| Operator enemy targeting and devices | None. | Not traced in this increment. | Enemies are preferred; devices are fallback targets. | Not validated. | Project-code behavior only. | `PROJECT_CODE_ONLY` |
| Medic target selection | Ansel is MEDIC in GameData. | Ansel prefab attack component references `projectile_ansel`; selector has ally side, category 1, `_limitTargetNum=1`, `_postFilter=3`, and `_sortByTauntAtLast=0`. `_postFilter=3` maps to `HP_RATIO_NOT_FULL_ASC`; `FilterUtil._Filter_HpRatioNotFullAsc` at RVA `0x2960e98` calls `Entity.get_hpRatio` and rejects full-HP candidates. | Covered allies with HP below max are ranked by HP ratio, then operator ID. | The ratio rule and full-HP exclusion match 2.7.81 client code. A synthetic competitor regression covers the Python rule. | Exact client tie-break after equal ratios and skill/heal-free interactions remain UNKNOWN. | `CLIENT_RATIO_FILTER_CONFIRMED_2_7_81; TIE_BREAK_UNKNOWN` |
| Heal amount | Operator ATK comes from GameData. | Generic `BattleFormula.CalculateHeal` is at RVA `0x253f684..0x253f770`; not decoded to a complete formula. | Uses effective ATK with a minimum of 1 and caps at missing HP. | Not validated. | No confirmed mismatch, but modifiers/skill variants are not closed. | `PROJECT_CODE_ONLY; GENERIC_CLIENT_METHOD_UNRESOLVED` |
| Physical/Arts damage | Attack/DEF/RES values come from GameData. | PRTS is supplementary only; client formula not decoded. | Uses 5% floor; DEF and MR do not cross-combine. | Not client validated. | Adequate for current-model diagnosis, not client fidelity. | `PROJECT_CODE_AND_PRTS_ONLY` |
| Civilian protection | Neutral entity and route/life rules come from GameData. | Not specifically traced. | Operator ordinary targeting rejects neutrals; officer has separate protected-target radius. | Not client validated. | Project behavior only. | `PROJECT_CODE_ONLY` |
| Roadblock block/release | Roadblock HP/DEF/RES/taunt come from GameData. | `trap_020_roadblock` LZ4AK fields and route-refresh disassembly are saved. | Uses roadblock as a targetable neutral device and refreshes routes on destruction. | Local saved evidence matches project implementation at a structural level. | Static-edge decode remains partially open. | `CONFIRMED_FROM_CLIENT_AND_GAMEDATA` |
| Route refresh chain | Roadblock route changes come from GameData. | Client `Tile/Rewrite/SPFA` methods are saved. | Refreshes route state on roadblock destruction. | Partial client evidence; exact static-edge decode remains open. | Keep UNKNOWN for undecodable edges. | `PARTIALLY_CONFIRMED_FROM_CLIENT` |
| Redeployment cooldown | `respawnTime` and phase cost are GameData facts. | Not traced in this increment. | Cooldown starts at exit, state resets per deployment generation. | Not client validated. | Cost growth and special redeploy rules remain unknown. | `PROJECT_CODE_ONLY; FIXED_BY_M32_REGRESSION` |
| Conditional static redeployment | None. | Not applicable. | Static compiler distinguishes current/self/other occupancy, future death, cooldown, tile, and DP reservation. | Covered by behavioral regression. | Runtime cost growth and special rules still require verification. | `PROJECT_CODE_ONLY; FIXED_BY_M32_REGRESSION` |
| Dodge/shield/barrier/status defenses | Some statuses appear in data but are not implemented for R8-7. | Not implemented or verified. | Not present for relevant defense calculations. | Not applicable. | Do not infer that physical artillery can be dodged. | `NOT_IMPLEMENTED` |
| Probability branches | None. | Not verified. | No probabilistic-success evaluator. | Not applicable. | A successful run cannot be called probabilistic WIN without a joint lower bound. | `NOT_IMPLEMENTED` |
| Chapter 6–11 broad coverage | Multiple stages not audited. | No broad client audit. | Partial runtime support only. | Not applicable. | R8-7 closure does not imply chapter support. | `NOT_CLOSED` |

## Static redeployment correction

The M32 correction remains a project-code fix and regression-covered behavior,
not a client-behavior proof. A repeated deploy while an operator is still active
is conditional only when the same operator is self-occupying; another occupant
is a conflict. The static ledger reserves base redeploy cost without silently
paying it. Explicit retreat has a known cooldown and starts a new deployment
generation. Actual cost growth and special rules remain
`UNKNOWN_REQUIRES_RUNTIME_VERIFICATION`.

## APK binding gap

M33 expanded the dependency scan to all 2,529 local `.ab` / `.bin` bundles.
The only exact `enemy_1112_emppnt` / `emppnt` container hits are:

- `assets/AB/Android/battle/prefabs/[uc]projectiles.ab`
- `assets/AB/Android/pkgrps/btl_pfb_fx_enemy_5.ab`
- `assets/AB/Android/refs/fx/sharedbattle.ab`
- `assets/AB/Android/refs/fx/texture/star.ab`
- `assets/AB/Android/spritepack/icon_enemies_2.ab`
- `assets/AB/Android/spritepack/ui_recalrune_rune_icon_sprites_0.ab`

The first is the projectile logic/prefab bundle; the others contain FX, texture,
icon, or rune assets. None contains the `enemy_1112_emppnt` body prefab.
There are zero SerializedFile external PPtr dependencies on the projectile
bundle `CAB-34af01ecb5d2ad63aca01b6e0d71279d`. This rules out direct serialized
references among local bundles, but not dynamic loading by a constructed path or
a remote resource.

The missing script CAB is now identified. `CAB-658d74aab777086fc32b93f385be999a`
is a MonoScript dependency, not ability configuration. It is contained by
`assets/AB/Android/anon/25ca9f1e45dc03e951bc38ef8f0a3670.bin` and
`assets/AB/Android/anon/9331724438927fc1266f8a4db7766543.bin`. The projectile's
four MonoBehaviour script bindings resolve to `SimpleProjectile`, `EffectBehaviour`,
`HitBehaviour`, and `AttachToTarget`. This is resource-to-script evidence only;
it does not identify the enemy creation call.

The next bounded extraction task remains obtaining the build-2771 enemy-prefab
bundle or the build-2771 `.idx` resource manifest needed to locate its
ability/action/action-node graph. Until then, the generic trace-target function
must not be claimed as this enemy's configured behavior.

## M38b animation-speed correction

`AbstractAnimatedAbility.UpdatePlaybackSpeed` sets the animation scale as
`max(attack_time / raw_animation_duration, 0.1)`, applies slowdown adjustments,
then clamps with `_maxAnimScale`; `SpineAnimator.PlayAnimation` returns
`raw_animation_duration / animation_speed`. Therefore a raw event maps to real
time as `raw_event_time * animation_scale / animation_speed` under the saved
no-status condition. For this artillery (`attackTime=5.0`, raw duration
`1.166667`, `OnAttack=0.333333`, animation speed `1.0`, `_maxAnimScale=1.0`),
the scale cap is 1.0 and the projectile-creation event is `0.333333` seconds
after cast start. This supersedes M38's `0.077778`-second result and its two
replays as wind-up evidence; the cast, creation/lock, fixed hit, and cooldown
structure remain applicable.

## M35 migration evidence boundary

`2.7.81` / resource `26-10-14-13-45-10-99469376` now provides the previously
missing enemy body bundle and its attack selector. The wrappers, inner-bundle
MD5s, path IDs, fields, and focused method calls are recorded by
`scripts/build_m35_artillery_resource_behavior_evidence_v1.py` and
`docs/review/fc77177/m35_artillery_resource_v1/artillery_resource_behavior_evidence.json`.
This is a migration candidate, not build-2771 proof. It must not be merged into
the production evidence set as same-version fact.

To unify versions, a future migration needs the 2.7.81 client binary/metadata,
this hot list, the relevant dependency closure (including the unresolved
`MonoScript` bundle when a serialized script identity is required), and a
GameData revision known to correspond to that client/resource version. Existing
build-2771 disassembly may guide code reading but must be revalidated against
the 2.7.81 binary before any runtime behavior change.

## M39 tactical result under the candidate model

Two legal M39 simulations used the 2.7.81 candidate timeline and both were
LOSS. V3 kept both civilians safe, cleared all four roadblocks, and reduced
operator deaths to five, but still leaked 14. V4 missed its Steward artillery
output window, destroyed only roadblock #3, lost both civilians, leaked 16, and
lost ten operators. Artillery survived both runs. These results are bounded by
the candidate model and do not establish build-2771 equality, faithfulness, or
real-device behavior. The detailed branch comparison is in
`docs/review/fc77177/m39_tactical_iteration_v1/m39_report.md`.

## M40 capability comparison result

The saved M39 V4 events corrected the Steward interpretation: legal deployment
at frame 1680 did not create an immediate output window. Route-1 waits and
looping delayed first artillery damage to frame 2281, after which Steward did
deliver repeated hits. M40 V2 still lost with 18 leaks and ten operator deaths.
It destroyed all four roadblocks and brought `#14` safely late, but Steward died
at frame 3160, artillery survived, and `#3` was killed by artillery. This is a
candidate-model diagnostic result only.
