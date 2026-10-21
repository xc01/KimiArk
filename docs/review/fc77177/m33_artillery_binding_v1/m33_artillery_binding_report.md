# M33 artillery binding report

## Scope and budget

- Build 2771 APK: `arknights-hg-2771.apk`, SHA-256
  `0b79b85383e21a6343283bc6bfd7a9d24eb4134abf901115f757da6a5d50f6db`.
- Tactical CLI calls: 0. Fixed full-stage simulations: 0. M32 simulation
  budget remains 2/4.
- The 2.7.81 reference graph was not merged into build-2771 conclusions.

## Implementation and tests

Added and exercised:

- `scripts/build_m33_bundle_dependency_index_v1.py` — all-bundle dependency
  scan with resume, error recovery, and match reporting.
- `scripts/extract_m33_resource_binding_graph_v1.py` — object identities use
  `SerializedFile:pathID`; internal and external PPtr references are retained
  separately from GameObject/component ownership and string clues.
- `scripts/build_m33_artillery_reverse_index_v1.py` — normalizes graph records
  into serialized PPtr, GameObject/component, string, container, and
  MonoScript-binding records.
- `scripts/build_m33_artillery_binding_evidence_v1.py` — extracts the projectile
  component fields, exact references, and selected client method addresses.
- `scripts/build_m33_binding_graph_key_rows_v1.py` — extracts the committed
  projectile-root graph evidence and resolves its four root-component script
  bindings against the large reverse index.

Regression files:

- `tests/test_m33_bundle_dependency_index_v1.py`
- `tests/test_m33_resource_binding_graph_v1.py`
- `tests/test_m33_artillery_reverse_index_v1.py`
- `tests/test_m32_resource_index_scanner_v1.py`
- `tests/test_m33_binding_graph_key_rows_v1.py`

Focused command:

```bash
.venv/bin/pytest -q \
  tests/test_m32_resource_index_scanner_v1.py \
  tests/test_m33_resource_binding_graph_v1.py \
  tests/test_m33_bundle_dependency_index_v1.py \
  tests/test_m33_artillery_reverse_index_v1.py
```

Result: 8 passed. No tactical CLI call or full-stage simulation was used.

## Confirmed resource chain

The projectile root is:

```text
SerializedFile/pathID =
  CAB-34af01ecb5d2ad63aca01b6e0d71279d:-619213101382661339
APK member =
  assets/AB/Android/battle/prefabs/[uc]projectiles.ab
APK member SHA-256 =
  77b786fe25fb1a0020393399d4ce2d02815d7290dd5718b828a1e609323f65bf
```

Its four MonoBehaviour `m_Script` references resolve to:

| Component pathID | Script name | Script CAB/pathID |
|---|---|---|
| `5265639341831392037` | `SimpleProjectile` | `CAB-658d74aab777086fc32b93f385be999a:-8797129986015012478` |
| `-7735524921054295259` | `EffectBehaviour` | `CAB-658d74aab777086fc32b93f385be999a:6834194400804168919` |
| `-6634548127984547035` | `HitBehaviour` | `CAB-658d74aab777086fc32b93f385be999a:-3494225671239136090` |
| `-2731905538226156763` | `AttachToTarget` | `CAB-658d74aab777086fc32b93f385be999a:740622368551806873` |

The previously unknown `CAB-658d74aab777086fc32b93f385be999a` is therefore a
MonoScript dependency. It is not the artillery ability configuration.

New resource-field facts include `SimpleProjectile` `_lifeTime=10.0`,
`_maxHitNum=1`, `HitBehaviour` `_onlyCheckHitWhenReachTarget=1`,
`_goThroughWall=1`, and `AttachToTarget` `_delayToStart=3.0`,
`_followTarget=0`, `_stopIfTargetDead=0`, `_alwaysReachInTheEnd=1`.
The 1.2 value is `CircleCollider2D.m_Radius=1.2000000476837158`; it is a
collision-radius field fact, not yet a decoded damage-qualification proof.
The 1.2 collision radius must not be confused with the GameData enemy range
radius of 2.0.

`dump.cs` supplies the relevant method identities:

- `SimpleProjectile` is type definition `10667`.
- `HitBehaviour.Init` is at RVA `0x2BFB724`; `DealHitTarget` is at
  `0x2BFBDB8`; `OnTriggerEnter2D` is at `0x2C0C37C`.
- `AdvancedMovement.Init` is at RVA `0x2C2BF5C`; `OnTick` is at `0x2C2C360`;
  `CheckStartTick` is at `0x2C2CDA8`.
- `Enemy.CheckTargetInAttackRange` is at RVA `0x2928618`.

These prove the generic projectile/hit/movement and enemy range-check code
paths exist, but not that the specific artillery ability/action graph uses any
particular alternative path.

## Full dependency result

The local dependency index scanned 2,529 APK bundles with 0 errors:

```text
output/m33_bundle_dependency_index_v1/bundle_dependencies.jsonl
SHA-256 17df3974ecb74ccdb6f5cc33079185c682708346fd7caed03125513c830446e4
```

The six exact container matches are listed in
`bundle_dependency_summary.json`. Only the projectile bundle is logic
configuration; the others are FX, texture, icon, or rune assets. No local
bundle contains the `enemy_1112_emppnt` body prefab. There are zero external
SerializedFile PPtr dependencies on the projectile CAB. This excludes direct
serialized references among local bundles only; it does not prove dynamic-load
absence.

The focused graph covered 64,264 objects, 316,310 PPtr references, 82,695
ownership references, 19 relevant string clues, and 0 typetree errors. Local
scratch artifacts:

| Artifact | SHA-256 |
|---|---|
| `output/m33_artillery_reverse_source_graph_v1/bundle_graph.jsonl` | `21c1095d8fdf4582ac008df889b443cf013bf61d30a1972530a331b8c4ec9e14` |
| `output/m33_artillery_reverse_index_v1/reverse_index.jsonl` | `0e31f08aa6f8da447862916628bfe42ff31f04ca7a401ae38cbc4de2e290e7cc` |
| `output/m33_anon_binding_graph_v1/bundle_graph.jsonl` | `05e9fad26f3be457e4cf27810c03e13651381fbb81bdd4c91ddd0de1a946003a` |
| `output/m33_projectile_binding_graph_v1/bundle_graph.jsonl` | `6ef918c73063d14b8d860a53e368f011ca03ff8088f99f22e9e8a0d228176633` |

The committed `binding_graph_key_rows.json` preserves the projectile root
identity, its container path, all six root-component PPtr references, the four
resolved MonoScript bindings, and every external PPtr row whose target is the
projectile CAB. The latter count is zero. Its inputs include the SHA-256 of the
259 MB source graph and 188 MB normalized reverse index, so the small evidence
file can be checked without committing the full indexes. The compressed copy of
the 2,529-record dependency index is also committed. Both the compressed and
uncompressed forms of that index use the SHA-256 recorded in
`large_index_hashes.json`.

## Open chain

Still `UNKNOWN`, not disproven:

1. The enemy body prefab and its ability/action/action-node graph.
2. The client-side transition from enemy attack decision to projectile creation.
3. The exact frame/event at which the 3-second delay starts.
4. The exact attack-cycle clock framing relative to projectile start and hit.
5. Configured target priority and tie-breaking.
6. Whether the 1.2 collision radius exactly defines damage qualification.

The build-2771 `.idx` remains blocked without the exact RSA/signature framing,
AES-CBC key, and IV. The evidence is recorded in `missing_materials.json`;
no key candidates were guessed.

Committed evidence hashes:

| Artifact | SHA-256 |
|---|---|
| `artillery_binding_evidence.json` | `940e8da4b6fbee8433a9086e4ea541b05a66b76caf6e69f703ef0e69289785ba` |
| `bundle_dependency_summary.json` | `ed1f53262680abb636ccc44419376434236d745970bcf323617f8e8afcf706bf` |
| `binding_graph_key_rows.json` | `accf4e6ab5e8fc10c6c34db607c5fc8b63b4b1e6ee3b44ad8a27d34800c03552` |
| `bundle_dependencies.jsonl.gz` | `4606d32d3477e381fdc109af9e34f6466adc9fd2c0e219f4656f2ba435b3010e` |
| `large_index_hashes.json` | `361d761910b389b4de93995ed49bf3899fdfc2b59617700e90d037837ae34000` |
| `missing_materials.json` | `b5884ae4236be74852b2f0f607ddade5f64c25cb452893e753666d2b1466fa9b` |
| `docs/mechanics/R8_7_MECHANISM_COVERAGE_V1.md` | `c4e25845083ffcc2fdc51e72c7884cb7bc277775269e937ff87a202bb96f8f6c` |

## Unique next node

Decode the build-2771 `main.idx` `ResourceManifest` only after recovering the
exact `FlatBufferSignedConverter` key/IV and framing from client evidence. This
is the next bounded extraction task. Do not use 2.7.81 as a substitute fact.
