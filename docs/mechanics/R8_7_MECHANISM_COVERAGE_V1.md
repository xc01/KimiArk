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
| Artillery delayed projectile | Enemy `skills` is `null`; no ability blackboard identifies the delayed attack. | Exact `projectile_enemy_emppnt.prefab` exists in `[uc]projectiles.ab`: path ID `-619213101382661339`. Movement component has `_delayToStart=3.0`, `_followTarget=0`, `_stopIfTargetDead=0`, and `_alwaysReachInTheEnd=1`; collision component has `_onlyCheckHitWhenReachTarget=1` and `_goThroughWall=1`; main component has `_lifeTime=10.0` and `_maxHitNum=1`. Trail effect has `_delayTime=2.75`. | Uses hardcoded `DELAYED_LOCKED_AREA_ATTACK` with a 3.0-second hit delay and 1.2 blast radius. | 3.0-second delayed, fixed-point, one-hit projectile matches. Blast radius 1.2 and damage/action-node details are not in the extracted projectile fields. | Specific artillery ability prefab is still missing, so the Python cooldown, radius, damage conversion, and action sequence cannot be promoted to client rules. | `PARTIALLY_CONFIRMED_FROM_CLIENT` |
| Protected-target acquisition priority | Neutral protected target is in GameData. | Generic `EnemyTraceTargetByPriorityAbility` exists at metadata RVA `0x2e2bfc4..0x2e2c290`; its priority path calls `TargetSelector$$FindTargets_DISPOSE`. Generic existence is not a binding. | Chooses neutral protected targets first, otherwise deployed operators. | No specific artillery ability binding was found. | Python priority may or may not match this enemy's configured selector. | `UNKNOWN_SPECIFIC_BINDING` |
| Locked blast position | None. | Projectile `_followTarget=0`, `_stopIfTargetDead=0`, and `_alwaysReachInTheEnd=1`. | Locks target position when ability starts and hits that position after 3.0 seconds. | Fixed position and persistence after target death match. | Client may have an extra interval between ability decision and projectile creation; exact lock-frame origin remains unknown. | `PARTIALLY_CONFIRMED_FROM_CLIENT` |
| Blast geometry | None. | `CircleCollider2D` on `projectile_enemy_emppnt` has `m_Radius=1.2000000476837158`; the same GameObject also binds `HitBehaviour`. This is a collision-radius field fact. | Uses 1.2-unit circular radius with inclusive boundary epsilon. | Radius value matches; damage qualification is not yet decoded. | Do not treat 1.2 as the acquisition range; GameData separately says enemy range radius 2.0. | `RESOURCE_FIELD_FACT; DAMAGE_SEMANTIC_UNKNOWN` |
| Normal attack versus special artillery | None. | No specific enemy ability prefab or action-node payload found. | Suppresses ordinary projectile output while `DELAYED_LOCKED_AREA_ATTACK` exists. | Not validated. | Cannot infer whether client allows ordinary attacks during/inside the special-ability cycle. | `UNKNOWN_SPECIFIC_BINDING` |
| Ability clock | Base attack time 5.0. | Generic `get_cooldown` is at RVA `0x2e2a6cc..0x2e2a76c`; no specific ability config bound. | Schedules next special ability at `state.time + 5.0` when it starts. | Not validated. | Start/finish-frame framing and interaction with projectile delay remain unknown. | `UNKNOWN_SPECIFIC_BINDING` |
| Operator enemy targeting and devices | None. | Not traced in this increment. | Enemies are preferred; devices are fallback targets. | Not validated. | Project-code behavior only. | `PROJECT_CODE_ONLY` |
| Medic target selection | Ansel is MEDIC in GameData. | Ansel prefab attack component references `projectile_ansel`; selector has ally side, category 1, `_limitTargetNum=1`, `_postFilter=3`, and `_sortByTauntAtLast=0`. Generic `AdvancedSelector.OnPostFilter` is at RVA `0x288a898..0x288ae08` and calls `FilterUtil$$Filter`. | Covered allies with HP below max are ranked by HP ratio, then operator ID. | Client selector fields conflict in interpretation without decoding the exact `_postFilter=3` filter implementation. | `lowest-HP-ratio` is not proven to be the client's universal medic rule. | `UNKNOWN_CLIENT_FILTER_DECODING` |
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
