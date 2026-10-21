# M34 build-2771 manifest decode report

## Scope and budget

This pass was offline only: no tactical CLI start and no full-stage simulation.
M32's remaining simulation reserve remains 2/4. Build 2771 is the only manifest
version decoded here; 2.7.81 remains reference-only and is not merged into these
conclusions.

## Converter data flow

`FlatBufferSignedConverter` extends `CrypticConverter_WithSign`, which extends
`CrypticConverter_A`. The relevant identities are:

| Method | RVA | Evidence |
|---|---:|---|
| `FlatBufferSignedConverter.EnableCodeOpts` | `0x578c590` | ARM64 bytes `40008052 c0035fd6` return `CodeOpt.SIGN` (`2`). |
| `CrypticConverter_WithSign.DecodeInternal` | `0x578b9b8` | Calls signature checking and then the base decode path. |
| `CrypticConverter_WithSign._CheckIfSignMatchOrThrow` | `0x578baf8` | At `0x578bb90..0x578bba8` reads `0x80` signature bytes and verifies them with `m_signPubKey`. |
| `CrypticConverter_WithSign._BaseDecodeInternalToDecrypt` | `0x578bd4c` | Passes `CodeOpt.CRYPTO` to `_CheckIfEnabled`; for this converter the test fails. |
| `CrypticConverter_A.DecodeInternal` | `0x578aad4` | Generic AES path exists, but it is not selected for the `.idx` payload. |

Therefore the build-2771 `.idx` files have this evidenced pipeline:

```text
input bytes
  -> 128-byte RSA signature header (verified in client; not regenerated here)
  -> remaining bytes are the FlatBuffer payload directly
  -> FlatLookupConverter unpacks ResourceManifest
  -> no AES-CBC, padding, decompression, or additional framing
```

`EnableCodeOpts` returning `2` is the decisive client fact: signature checking
is enabled, while `CodeOpt.CRYPTO` (`1`) is disabled. Consequently there is no
AES key/IV requirement for decoding these two `.idx` files. The generic AES
class does keep a 16-byte token and a 16-byte IV in `CrypticConverter_A`; its
constructor stores the token in object field `0x20`. The RSA public key is in
`CrypticConverter_WithSign.m_signPubKey` at object field `0x28`. Their exact
metadata-backed literal values were not recovered because they are not needed
for this payload. `PlayerData.chatMask` is not part of this chain.

## FlatBuffer layout

The payload begins with a 16-byte root offset. The root table is therefore at
file offset `128 + 16 = 144`. `FlatLookupConverter` uses even field IDs:

| Method | RVA | Field mapping |
|---|---:|---|
| `Unpack_ResourceManifest` | `0x576153c` | `4=rawCount`, `6=bundles`, `8=assetToBundleList` |
| `Unpack_ResourceManifest_BundleMeta` | `0x5761668` | `4=name`, `6=props`, `8=sccIndex`, `10=allDependencies` |
| `Unpack_ResourceManifest_AssetToBundleMeta` | `0x576178c` | `4=assetName`, `6=bundleIndex`, `8=name`, `10=path` |

The compact vtable slot is `(field_id - 4) / 2`. This is why the root vtable can
have only three entries while the client methods refer to IDs `4`, `6`, and `8`.
The implementation is `scripts/decode_build2771_resource_manifest_idx_v1.py`.

## Decode verification

The committed 78,996-byte small `.idx` fixture is the APK member
`assets/AB/Android/613696e0b7f401be75f635e43560cf93.idx`. The decoder reads:

| Input | SHA-256 | Size | rawCount | Bundles | Assets |
|---|---|---:|---:|---:|---:|
| `main.idx` | `11898eef33eecef9f4ac015863944df305531f8fcd6f0fa1d2274d5b0b23fad9` | 9,875,736 | 0 | 2,528 | 56,001 |
| small fixture | `67c47a74e01cf6418b08dbc4cf1443bb5c0cba8fa3b3f35b6bdc41580559f43c` | 78,996 | 0 | 35 | 365 |

M33 had recorded 9,961,472 and 79,872 bytes for the same SHA-256 values. Those
numbers are `stat -c %b*512` allocated-block sizes, not `stat -c %s` logical
file sizes. The incorrect M33 `size_bytes` fields are retained as historical
records and superseded by the logical sizes above. Successful FlatBuffer parsing
does not imply RSA signature verification; its status is `NOT_PERFORMED`.

Known strings and mappings survive the parse, including the first small fixture
asset `config/config -> dyn/config/config.json` and the main fixture asset
`premain/abfontconfig -> Assets/Torappu/Arts/UI/Common/Fonts/AbFontConfig.asset`.
Machine-readable summaries and artillery resource rows are in this directory.

## Relationship to the existing manifest JSON

`data/ArknightsGameData/zh_CN/resource_manifest_idx.json` is **not** the decoded
build-2771 `main.idx`:

| Manifest | Bundles | Assets |
|---|---:|---:|
| decoded build-2771 `main.idx` | 2,528 | 56,001 |
| existing repo manifest reference | 15,166 | 194,002 |

It is useful as a larger manifest reference but cannot be promoted to build-2771
evidence. Its bundle names and dependency graph are labeled separately in
`resource_location_evidence.json`.

## Artillery resource result

The decoded APK initial manifest contains the projectile:

```text
battle/prefabs/[uc]projectiles/projectile_enemy_emppnt
  -> bundle 1597 = battle/prefabs/[uc]projectiles.ab
```

That agrees with the already extracted projectile payload. It does **not**
contain `battle/prefabs/enemies/enemy_1112_emppnt`; the artillery body prefab is
therefore absent from the indexed APK bundle set and from the APK initial
manifest. The larger repo manifest reference points it to
`battle/enm_pfb_6.ab`, with four members not present in the APK:

```text
battle/enm_pfb_6.ab
refs/arts/enm_art_5.ab
refs/arts/enm_art_6.ab
anon/a90f86ed9fd93b2c2af4fd0571371829.bin
anon/d18eade0736a6e017095df3593149d3b.bin
```

These five names are a concrete retrieval target from the reference manifest,
not a proof that this exact remote set belongs to build 2771. A build-2771
remote manifest or bundle download record is still required before asserting
version equivalence.

## Artifacts and tests

| Artifact | Purpose |
|---|---|
| `build2771_main_idx_summary.json` | Decoded main index counts and input hash. |
| `build2771_small_idx_summary.json` | Decoded committed fixture counts and input hash. |
| `resource_location_evidence.json` | Artillery rows, body/projectile mapping, dependency presence, and provenance labels. |
| `scripts/decode_build2771_resource_manifest_idx_v1.py` | Reproducible decoder and CLI. |
| `tests/fixtures/build2771_small_resource_manifest_idx_v1.idx` | Real build-2771 small index fixture. |
| `tests/test_decode_build2771_resource_manifest_idx_v1.py` | Framing/count/query regression tests. |

Focused tests pass. No runtime combat behavior was changed and no historical
simulation conclusion was invalidated by this pass.
