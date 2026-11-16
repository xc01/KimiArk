# R104 post-run causal and leak audit

## Identity and control validity

- Local commit: `bb571d8c1b5739295e9c9a4014b69f41198cb27a`; not pushed during this zero-model audit.
- Candidate: `R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001:candidate-001`; plan/action/events-gz/events-restored SHA-256 are `d91955b06f7bf4145b355152ce2bcd203b3973b469ff4889c6d6d83a1d87048b`, `816ec7a9ce93591c5c21c7fea6f811374f0df25238082b483a8a1919c9e7e847`, `5b3e33285108938e844cb82cc4d7274494ac16887fd3071087d309c09c424052`, and `46a72b6dd5f86feef0538897fc773a2e4726154f535fd2b6adb75b007beee1a4`.
- Parent: `R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002:candidate-002`; plan/action/events-gz/events-restored SHA-256 are `044eb9eb90254934cc4767dbd1070ee91ccbdf349380ec258bbdd488098b146b`, `d5a07b4dca4f05cee428875165d3c59ee0c388e9b950623cd62fc8c60d83fc8f`, `d971d1fe5a69c2ea5a4ae3c98f44ab023b3e48ee1e3eb3f1dc6168808930a065`, and `25f3a184f572bee142c9d5d1a6ee0807db0e2e28df26d5dee26fcea7691f9ed7`.
- The only tactical diff is Steward `RETREAT 4200→4280` at action index 14 and same-ID `DEPLOY 6301→6381` at action index 19. The first event difference is at index 19405/frame 4200; the preceding 19,405 events are identical.
- Budget/model boundary: real CLI 0, model generation 0, new STARTED 0, simulation 0 in this audit; model usage was `MODEL_USAGE_NOT_APPLICABLE`.

## Artillery closure evidence

| Item | Evidence |
| --- | --- |
| Extra hit 1 | Candidate event index 19494, frame 4225: Steward→artillery DAMAGE `249.10` arts. |
| Extra hit 2 and death | Candidate indices 19629–19630, frame 4273: Steward→artillery DAMAGE `473.29`, then `ENEMY_DEATH` with `kill_counted=true`. |
| Steward survived the window | Source shell hit Steward for `910` at index 19441/frame 4211; Ansel healed him `506.8` at 4213 and Hibiscus healed him `433.8` at 4277. Legal retreat occurred at 4280. |
| In-flight shell after source death | At 4261 the artillery started a shell targeting Hibiscus and the projectile was born at 4271. Although the artillery died at 4273, that shell still hit Hibiscus at 4361 for `890`. |
| Scope | This proves the 4200–4280 continuation closed the artillery in this frozen R101-C2-derived structure. It does not prove that all retreat timings, tiles, roles, or placements would do so. |

## First-failure chronology

| Boundary | Frame | Fact |
| --- | ---: | --- |
| First operator death | 2111 | Friston died; this precedes every leak but causality is not proved from events alone. |
| First leak | 3065 | Officer `enemy_1107_uoffcr#11` leaked with no recorded BLOCK or DAMAGE received. |
| First protected-target failure | 3311 | Protected `enemy_3001_upeopl#3` died. Roadblock `#3` was not destroyed; this is distinct from roadblock `#3`. |
| Life reached zero | 3425 | Officer `enemy_1107_uoffcr#13` leaked, leaving remaining life `0`. |
| Artillery closed | 4273 | Steward killed `enemy_1112_emppnt#0`. |
| First central-armor leak | 5353 | `enemy_1110_uamord#21` leaked after Fang's 4954 death removed the 4646 block. |

## Remaining 12 leaks

| Enemy | Route | Spawn | BLOCK / receive damage | Operator-facing damage | Final leak |
| --- | --- | ---: | --- | --- | ---: |
| `enemy_1107_uoffcr#11` | 11 | 2520 | None / none | None recorded | 3065 |
| `enemy_1107_uoffcr#13` | 14 | 2880 | None / none | None recorded | 3425 |
| `enemy_1107_uoffcr#20` | 18 | 4080 | None / none | None recorded | 4625 |
| `enemy_1110_uamord#22` | 19 | 4530 | None / none | 4667→Fang `340` arts | 5196 |
| `enemy_1110_uamord#21` | 21 | 4380 | Fang BLOCK 4646 / Fang+Midnight DAMAGE from 4614 | 4450→Hibiscus, then 4618/4702/4786/4870/4954→Fang | 5353 |
| `enemy_1108_uterer#27` | 30 | 5580 | None / none | None recorded | 5932 |
| `enemy_1108_uterer#28` | 28 | 5730 | None / none | None recorded | 6082 |
| `enemy_1108_uterer#29` | 30 | 5790 | None / none | None recorded | 6142 |
| `enemy_1108_uterer#31` | 28 | 5940 | None / none | None recorded | 6292 |
| `enemy_1107_uoffcr#30` | 24 | 5880 | None / none | None recorded | 6425 |
| `enemy_1110_uamord#33` | 31 | 6180 | None / Steward DAMAGE 6381 `249.10` | 6250→Hibiscus and 6418/6502→Steward `289` arts | 6846 |
| `enemy_1110_uamord#34` | 29 | 6330 | None / none | 6467/6551/6635/6719→Ansel `340` arts | 6996 |

Enemy HP and continuous positions are not recorded, so the exact survival margin and route position at each leak remain UNKNOWN.

## Protected routes

- Protected `#3`: roadblock `#3` blocked it at 761 and was not released before death. Officer `#8` hit it at 1296/1356/1416 for `280` each; artillery shells hit it at 3011/3161/3311 for `950` each; the third artillery hit killed it at 3311. Roadblock `#3` itself was destroyed much later by Steward at 11917. Roadblock `#3` and protected target `#3` are distinct.
- Protected `#14`: roadblock `#2` blocked it at 3620, held until the roadblock was destroyed at 12116, and the target reached at 12448. No damage to this target is recorded.

## R104 versus parent R101 C2

- Parent settled at 20 kills / 13 leaks / life −11 with four operator deaths; R104 settled at 21 / 12 / life −10 with two operator deaths.
- Parent leaks included artillery `enemy_1112_emppnt#0@5759` and armor `#21@5101`. R104 removed only the artillery leak; `#21` was delayed to 5353 but still leaked. All other 11 leaks retained the same enemy ID and frame.
- Candidate-only enemy deaths are exactly `(4273, Steward→artillery)`; there are no parent-only enemy deaths. Thus the kill-count gain is the artillery removal, not a broad improvement in enemy trajectories.
- The fewer deaths are also an observed consequence: parent lost Hibiscus@4511, Fang@4702, and Steward@6569, while R104 did not. This must not be converted into a claim that artillery closure necessarily preserves support everywhere.
- During parent 6301–6380, Steward was present, had no candidate until attacking armor `#33` at 6347 for `249.10`, and was hit by `#33` at 6317 for `289`. In R104's gap, Steward was absent; `#33` attacked Hibiscus at 6334 for `340`, Hibiscus self-healed `340` at 6336, and Steward attacked `#33` only at 6381 for `249.10`. Neither 6301 nor 6381 produced a BLOCK on `#33`, and `#33` still leaked at 6846.

## Experience record

The 20-record store contains `R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001:candidate-001` with `configured_model=DETERMINISTIC_COUNTERFACTUAL`, `reasoning_effort=NONE`, a seven-ID union, and `ARTILLERY_KILL` evidence. Its `summary_result.win` remains `UNKNOWN` because the current importer does not explicitly encode terminal LOSS; the closeout and final status are the authoritative `simulator_win=false` evidence. No selector weight or retention rule was changed here.

## One supported next question

The first still-unclosed necessary duty is the early route leak, not central repair: `#11` leaked at 3065 and `#13` leaked at 3425 with no recorded interception or damage. This is independent of the 4200–4280 artillery closure. A future, unauthorized test should ask whether a seven-ID plan can retain R104's artillery-closure window while covering these earliest routes, with observable success as BLOCK/DAMAGE/DEATH for `#11` before 3065 and `#13` before 3425, and no regression of the 4225/4273 artillery events. Because an early route change can alter later arrivals, one complete fixed simulation is the minimum budget; a second candidate should be justified only by the first run's new event chain. No tactical action, role, or prompt is authorized here.
