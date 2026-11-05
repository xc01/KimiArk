# Small-learning Astra C1/C2 read-only review

## Scope

This is a read-only retrospective of archived evidence. It used zero real model calls, zero real simulations, and zero new experiment starts. The source experiment manifest has 90 entries; every archive hash and restored-file hash verified. No existing budget was changed.

- Manifest: `../artifact_manifest_v1.json` (SHA-256 `cc0b02fe42302677885dde22b66737261d687f10bad921cb3ecbb8669c6f02c8`).
- C1: `46e90dd7be30a6bb8dd48191f49001050a5099e80447a69941fcc3ec923c883b`.
- C2: `5f8da35ff37ab50c78700ac44b0b2fb3b8fd38a7b5bee2ce43617088b15ae7ac`.
- Machine-readable output: `read_only_review_v1.json#/candidates`, `#/opening_dependency`, and `#/query_effectiveness`.

## Candidate facts

Both plans used the same seven IDs: Fang, Friston-3, Midn, Melantha, Ansel, Hibiscus, and Steward. C1 was a 6-kill/27-leak loss with 6 unique operator deaths and remaining life `-26`; C2 was a 14-kill/19-leak loss with 7 unique operator deaths and remaining life `-17`. The kill increase was not evidence of approaching WIN: C2 still failed protected-passage, artillery-removal, and central-interception duties.

The first four deployments were unchanged. C1 deployed Ansel at `[5,3] RIGHT@1321`, Hibiscus at `[2,5] RIGHT@1681`; C2 reversed the healer order and used Hibiscus `[2,5]@1321`, Ansel `[5,7] LEFT@1681`. C2 also deferred Ansel and Hibiscus skill activations. Steward remained `[2,7] UP@2071`.

## Why C1's central test was truncated

C1's planned central test was `4380-5500`. It never reached that window as a valid test because three opening dependencies failed:

| Operator | Direct damage before death | Heal before death | Death |
| --- | ---: | ---: | --- |
| Fang | 1,360 ordinary | 0 | 1389 |
| Friston-3 | 1,205 ordinary | 0 | 1554 |
| Ansel | 1,782 ability (`2×891`) | 362 self-heal after the first hit | 1571 |

Artillery locked C1 Ansel at runtime `[3,5]` for both hits. Thus C1 did not refute the central `#21/#22` hypothesis; it only showed the opening shell-survival and healer prerequisites were not met. C1's first leak was `enemy_1107_uoffcr#6@1731`; life first reached zero at `2915`, but the earlier dependency failures made this a truncated test rather than a valid central result.

## What C2 repaired and what remained broken

C2 repaired the opening dependency chain: Hibiscus healed Fang/Friston at `1321/1407/1493/1579/1665` for `372.6` each; Fang generated `+6` DP at `2070`; Steward deployed legally at `2071`. This restored the planned central window's prerequisite, but shell survival did not hold:

1. Ansel received `891` ability hits at `2443` and `2593`, both locked runtime `[7,5]`, with only one `506.8` self-heal between them. He died at `2593`.
2. Steward continued artillery output—25 `DAMAGE` events totaling `7,348.45` from `2281` to `3433`—but received four `910` ability hits at `3010/3160/3310/3460` while receiving five Hibiscus heals totaling `2,378.9`. He died at `3460`.

The central window then opened, but the central contact still failed. In `4380-5500`, `enemy_1110_uamord#21` had only `SPAWN@4380` and `ENEMY_LEAK@5046`; `enemy_1110_uamord#22` spawned at `4530`, attacked Melantha twice, and leaked at `5196`. Neither received operator-sourced ordinary damage, ability damage, or a `BLOCK`. Therefore C2's failure was coupled shell survival plus central interception, not merely opening deployment.

## Roadblock #3 is not protected target #3

`trap_020_roadblock#3` and `enemy_3001_upeopl#3` are distinct entities. The roadblock was at runtime `[6,1]`; the protected enemy used route-2.

| Item | C1 | C2 |
| --- | --- | --- |
| Roadblock `#4` | 14 `DEVICE_DAMAGE`, destroyed `1966` | same |
| Roadblock `#3` | 0 device events | 0 device events |
| Roadblock `#1` / `#2` | 0 device events | destroyed `9517` / `11386` |
| Protected `#3` | blocked by roadblock `#3@761`, died to artillery `3310` | same |
| Protected `#14` | died `6314`, never reached | reached `11718` |

Neither frozen action timeline assigned `trap_020_roadblock#3`; C1's validation card named `#4`, while C2 named `#4` and later `#1/#2`. The zero was not a query-semantics artifact: `DEVICE_DAMAGE` is a supported event type, the model issued zero-match `DEVICE_DAMAGE` queries against `#3`, and direct archive inspection found none. This is a missing assignment rather than evidence that a placed operator merely failed contact.

## Same death frames are not same causes

Exact-frame comparisons were read-only:

| Candidate | Exact death | Repeated part | Different part |
| --- | --- | --- | --- |
| Cold-start C2 | Ansel `2593` | Final two `891` hits were `[7,5]` | It had an additional earlier `[5,5]` hit and no self-heal between the last two; small-learning C2 had `506.8` self-heal. |
| Cold-start C4 | Steward `3460` | Four `910` hits and death frame | First three locks were `[6.6,1.0]` and the last was `[6,2]`; small-learning C2's last lock was `[7,2]`. |
| Joint-feedback C2 | Steward `3460` | Four `910` hits and death frame | All locked `[6,2]`; small-learning C2's last was `[7,2]` and had a different heal sequence. |

These show repeatability of the shell amount and timing, not identical causation. HP state is not directly logged, so survival conclusions remain arithmetic from complete hit/heal events rather than direct HP snapshots.

## Query effectiveness

The transcript contains 56 completed tool calls: 2 `get_session_status`, 2 `check_plan`, 2 `run_simulation`, and 50 `query_events`. There were 22 C1 queries and 28 C2 queries. All had `observation_coverage: COMPLETE`; none had byte-budget truncation; none had an exact duplicate argument set.

The model queried both operator damage categories separately (`DAMAGE`, `ENEMY_ABILITY_HIT`), `DEVICE_DAMAGE`, `DEVICE_DESTROYED`, `BLOCK`, heals, skills, projectiles, deaths, leaks, DP, deploy, and protected-target completion. It did not query `UNBLOCK` or `DEVICE_TARGET_SELECTION`, but those absences do not invalidate the zero-`DEVICE_DAMAGE` roadblock-#3 finding because that event type was queried and independently recomputed.

Seven queries returned a partial raw page: `item_29`, `item_33`, `item_37`, `item_38`, `item_44`, `item_53`, and `item_54`. None was followed by the exact offset continuation. This was acceptable for aggregate totals because the service computes aggregates over the complete filtered match set (`scripts/kimiark_tactical_stdio_service_v1.py:1170-1190`), but raw detail remained partial for those windows. Narrower source/target/frame queries supplied the decisive C2 evidence, including opening heals, deploy/DP, ability hits, projectile locks, and roadblock events. The visible call order and validation-card content support that these informed revision, though hidden model reasoning cannot prove causality.

## Next validation question

One question worth a future bounded simulation: can a seven-ID structure preserve C2's opening sequence—Hibiscus opening heals, Fang `+6` DP, and Steward deployment—while changing shell-survival support enough to keep Ansel alive through `2593` and Steward through `3460`, and then still place live operator contact on `#21/#22` during `4380-5500`?

It should be run only if the candidate can distinguish these coupled conditions:

- Keep the opening dependency chain alive through `2071`.
- Observe Ansel surviving both `[7,5]` shell hits and Steward surviving the fourth `910` hit.
- Observe at least one live operator `BLOCK` or operator-sourced `DAMAGE`/`ENEMY_ABILITY_HIT` on `#21/#22` during `4380-5500`.
- Retain roadblock-#4 clearance and protected-passage duties without treating either as proof of central contact.

No simulation is warranted if it cannot preserve the opening chain, only shifts death times without shell survival through `3460`, or leaves central `#21/#22` contact unchanged.

## Boundaries

Conclusions are for the fixed archived simulator and listed mechanics version `m38b-2781-animation-speed-v1` only. This does not claim real-game faithfulness, robustness, probability of WIN, seven-ID impossibility, or global minimality. M70's eight-ID WIN remains the best verified result; seven-or-fewer feasibility is `UNKNOWN`. Counterfactual changes were not simulated.
