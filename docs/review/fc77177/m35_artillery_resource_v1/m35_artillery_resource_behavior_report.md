# M35 artillery resource and behavior binding report

## Version and budget

- New tactical CLI calls: **0**.
- New fixed full-stage simulations: **0**.
- M32 reserve remains **2/2**.
- Production APK: `arknights-hg-2771.apk`, SHA-256
  `0b79b85383e21a6343283bc6bfd7a9d24eb4134abf901115f757da6a5d50f6db`.
- Production resource version: `26-08-16-13-31-15_02805c`.
- Migration evidence resource version: `26-10-14-13-45-10-99469376`
  (`2.7.81`); these are kept separate. The version response was retrieved on
  2026-10-22 00:16:21 Asia/Shanghai; the hot list followed at 00:17:08.
  Version-response and hot-list URLs/hashes are in the JSON evidence.
- GameData zip commit: `0ef7f952dfd018392200157a5c79a6511ba69122`.

The manifest decoder still reports `signature_verification=NOT_PERFORMED`.
Successful FlatBuffer decoding is not signature verification.

## Resources obtained

The 2.7.81 hot list contains five relevant battle/reference bundles; the two
`anon/*.bin` reference candidates are not needed for the recovered chain. One
listed `anon` reference,
`anon/a90f86ed9fd93b2c2af4fd0571371829.bin`, is listed but its CDN URL returned
404. The other, `anon/d18eade0736a6e017095df3593149d3b.bin`, is absent from this
hot list.

These are not treated as proof that either path never existed.

Downloaded and validated:

| Logical path | Inner MD5 | Inner SHA-256 |
|---|---|---|
| `battle/enm_pfb_6.ab` | `9f928e64bae47fa7539837b236adba60` | recorded in JSON evidence |
| `refs/arts/enm_art_5.ab` | `0c96b1b3fe5a3eea7286b9dbaf5b6c25` | recorded in JSON evidence |
| `refs/arts/enm_art_6.ab` | `fbb347a09f0dd39c1c7faea08291a98c` | recorded in JSON evidence |
| `battle/prefabs/[uc]projectiles.ab` | `8ed77a0fb3c6e3cc1aad725dc8524ac6` | recorded in JSON evidence |
| `pkgrps/btl_pfb_fx_enemy_5.ab` | `e137d4ef0d6f364abed29806d2d002d6` | recorded in JSON evidence |

The evidence builder checks wrapper ZIP members and compares inner MD5/size to
the decoded hot list. It writes
`artillery_resource_behavior_evidence.json`.

## Actual binding chain

1. `dyn/battle/prefabs/enemies/enemy_1112_emppnt.prefab`
   (`CAB-0b81ba3070e9ea008a822bead4d3e7fb`, path ID
   `-2534595712224000645`) exists in `battle/enm_pfb_6.ab`.
2. Its root `_modes[0]` points to a combat component; `_combat` and `_attack`
   are the same object (`-3150289406525635205`).
3. That attack object declares `_projectileKey='projectile_enemy_emppnt'`,
   `_projectileDestination=2` (`INPUT_VECTOR3`), `_selectTargetTiming=1`
   (`BEFORE_SPELL_START`), `_cooldown=0`, `_cooldownKey='duration'`, and
   `_waitForAttackEvent=1`.
4. Its selector (`-1308437885939022469`) declares:
   `_targetSide=2`, `_targetMotion=3` (`ALL`), `_targetCategory=1`
   (`DEFAULT`), `_postFilter=4` (`HATRED_DES`), `_secondaryFilter=3`,
   `_sortByTauntAtLast=1`, `_buffKey='mark_neutral[effect]'`, and
   `_limitTargetNum=1`.
5. `dyn/battle/prefabs/[uc]projectiles/projectile_enemy_emppnt.prefab`
   (`CAB-34af01ecb5d2ad63aca01b6e0d71279d`, path ID
   `-619213101382661339`) binds `SimpleProjectile`, `EffectBehaviour`,
   `HitBehaviour`, and `AttachToTarget`.
6. Projectile facts include `_delayToStart=3.0`, `_followTarget=0`,
   `_stopIfTargetDead=0`, `_alwaysReachInTheEnd=1`, `_lifeTime=10.0`, and
   `_maxHitNum=1`.
7. `CircleCollider2D.m_Radius=1.2000000476837158`. `HitBehaviour.Init`
   initializes target options/layer mask; `HitBehaviour.OnProjectileReached`
   calls `Box2dPhysicsUtil.FindTargets_DISPOSE`; `HitBehaviour.DealHitTarget`
   checks camouflage, source, trace target, block mode, then calls
   `Projectile.DealHitTarget`.
8. `RangedAttack.CreateProjectile` calls `BattleController.CreateProjectile`;
   `GetTargetLocatable` converts target `mapPositionV3` into a fixed position
   when the destination mode is `INPUT_VECTOR3`.

This closes the resource-to-ability-to-projectile chain for the **2.7.81
migration candidate**. It does **not** prove the build-2771 body binding.

## Behavior conclusions

| Conclusion | Strength |
|---|---|
| Artillery body and projectile resources now exist together in 2.7.81. | Confirmed from resources |
| The attack points to the exact projectile key and fixed input-vector destination. | Confirmed resource fields + client method call |
| Target/input is selected before spell start. | Confirmed enum/resource field |
| Radius 1.2 participates in the reached-target physics query, not only visuals. | Confirmed call; exact edge semantics remain UNKNOWN |
| Hatred-descending and taunt-last are selector facts. | Confirmed fields; runtime ranking not closed |
| Attack interval starts at a specific frame and resets exactly there. | UNKNOWN / partially traced |
| Damage node and full action-node graph semantics are restored. | UNKNOWN; no action/action-node payload was extracted |
| Build-2771 body binding is recovered. | NOT CLAIMED |

## Reproduction

```bash
PYTHONPATH=/tmp/pylibs python scripts/build_m35_artillery_resource_behavior_evidence_v1.py
UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q \
  tests/test_decode_build2771_resource_manifest_idx_v1.py \
  tests/test_m35_artillery_resource_behavior_evidence_v1.py
```

The `PYTHONPATH` requirement is for the local Capstone 5.0.7 extraction
environment. Tests do not require Capstone.

The expanded resource regression set passed 14/14:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q \
  tests/test_decode_build2771_resource_manifest_idx_v1.py \
  tests/test_m32_resource_index_scanner_v1.py \
  tests/test_m33_artillery_reverse_index_v1.py \
  tests/test_m33_binding_graph_key_rows_v1.py \
  tests/test_m33_bundle_dependency_index_v1.py \
  tests/test_m33_resource_binding_graph_v1.py \
  tests/test_m35_artillery_resource_behavior_evidence_v1.py
```

## Next bounded work

Do not restore tactical iteration on the basis of same-version client behavior.
The single bounded next step is to obtain the 2.7.81 client binary/metadata and
re-run the focused `RangedAttack -> Projectile -> HitBehaviour` disassembly
against that version, then compare the action/action-node payload. Only after
that comparison can a version-unified runtime rule be changed.
