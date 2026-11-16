# R104 vs R105 C1 zero-model divergence audit

## Identity

| Record | Plan SHA-256 | Action SHA-256 | Events SHA-256 (gzip) |
| --- | --- | --- | --- |
| `R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001:candidate-001` | `d91955b06f7bf4145b355152ce2bcd203b3973b469ff4889c6d6d83a1d87048b` | `816ec7a9ce93591c5c21c7fea6f811374f0df25238082b483a8a1919c9e7e847` | `5b3e33285108938e844cb82cc4d7274494ac16887fd3071087d309c09c424052` |
| `R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001:candidate-001` | `3b8c452a9f0aaf9667f3420ecdf912290ce5c69b984895b46447410563ee5e52` | `d48eac7ffe3006947abbc6bbc89e9b517cb441643a8672e40ec78b18d20bdafb` | `8d41df1f984342181719b842c9b5469682733080c4006e5f413ec499ba55e6f5` |

R105 C2 identity: plan `3c7fa37fb2ee1c0c53709bbd70ba7146a1f0e4839dd93624b74f3f0b4c4ffa73`; action `c12e6707e2b15037ce437f899b02129a242e519899841d30f4c2055744ed867c`; events gzip `64f30530971a1819fdc7a8ad837e2afae078faf085b9455d52984997d8d40068`. C2 is retained only as a regression comparison.

## Normalized action diff

### R104 → R105 C1

| Index | Field | R104 | R105 C1 |
| --- | --- | --- | --- |
| 3 | `DEPLOY` | `char_283_midn`, frame 571, tile `[6,5]`, `DOWN` | `char_283_midn`, frame 571, tile `[1,5]`, `UP` |
| 4 | `DEPLOY` | `char_284_spot`, frame 901, tile `[1,5]`, `RIGHT` | `char_284_spot`, frame 901, tile `[6,5]`, `RIGHT` |
| 29 | `DEPLOY` | `char_210_stward`, frame 11101, tile `[2,7]`, `DOWN` | `char_210_stward`, frame 11101, tile `[5,7]`, `UP` |

All other actions matched. Thus R105 C1 preserved Steward's 2131 deployment, 4280 retreat, 6381 return, and the artillery support deployment/skill frames in the normalized action list.

### R105 C1 → R105 C2

C2 was not a small repair. It replaced frame-901 Spot with frame-841 Melantha, moved Hibiscus to `[5,5]RIGHT@1321`, moved Ansel to `[5,6]DOWN@1711`, and shifted many later skills. C2's early triple death at 2111 truncated the C1-style route plan: Friston/Hibiscus/Ansel died together, and #11/#13 were then damaged but neither blocked nor killed before leaking at 3065/3425.

## Early routes

| Record | `#11` | `#13` |
| --- | --- | --- |
| R104 | Ranged damage only; no BLOCK; leaked 3065 | One Midnight hit; no BLOCK; leaked 3425 |
| R105 C1 | Friston BLOCK 2738; Friston/Fang/Midnight dealt 15 hits / 3437.04; Friston UNBLOCK 2881; Fang death 2881 | Friston BLOCK 3098; Friston/Midnight/Fang dealt 19 hits / 3468.0; Friston UNBLOCK 3311; Midnight death 3311 |
| R105 C2 | Same early pattern as R104: three hits, no BLOCK, leak 3065 | One Midnight hit, no BLOCK, leak 3425 |

C1 therefore validated the route-closure hypothesis. Continuous positions and full HP are not recorded in these events, so interval paths remain `UNKNOWN`.

## Steward/artillery divergence

Both Stewards deployed at 2131 and received identical-position artillery hits at 2261, 2411, 2561, 2711, 2861, 3611, 3761, and 3911. Neither had ordinary enemy damage in that window. Through frame 3911:

| Record | Artillery hits on Steward | Steward heals | Net damage (not initial HP) |
| --- | ---: | ---: | ---: |
| R104 | 8 × 910 = 7280 | 17 events / 6370.0 | 910 |
| R105 C1 | 8 × 910 = 7280 | 15 events / 5998.0 | 1282 |

R105 C1 Steward died at 3911 on the same eighth artillery hit; R104 Steward did not. Exact HP and over-heal semantics are not recorded, so the observed net is not an HP assertion.

The earliest Steward-support divergence appears in physician target selection. At 2171, R104 healed Ansel while C1 healed surviving Friston; at 2241, R104 healed Midnight while C1 healed Friston. C1 then continued healing Friston during route engagement (17 heal events totaling 3920 through 3911), whereas R104 had only six events totaling 2097.6 before Friston died at 2111. This gives a supported `HYPOTHESIS`, not a proof: Friston's survival and route-blocking role diverted physician heals and left Steward with two fewer delivered heal events in the observed window.

Steward→artillery output:

| Record | Hits | Damage | Last hit | Outcome |
| --- | ---: | ---: | ---: | --- |
| R104 | 45 | 13227.21 | 4273, 473.29 | Artillery `ENEMY_DEATH` at 4273 |
| R105 C1 | 37 | 10786.03 | 3889, 249.1 | Steward `OPERATOR_DEATH` at 3911; artillery leaked 5759 |

The difference is therefore death truncation, not a changed Steward deployment frame, artillery range, or a recorded target switch. The 4273 kill in R104 is outside C1's observed lifetime and was not replicated.

## Protected and central facts

- R104: protected `#3` was blocked by roadblock `#3` at 761, took three officer hits and three artillery shells, and died at 3311. Roadblock `#3` remained intact until Steward destroyed it at 11919. Protected `#14` was blocked by roadblock `#2` at 3620; no death/arrival is recorded in the examined facts.
- R105 C1: roadblock `#3` was destroyed by upper Midnight at 2404, but protected `#3` still died at 5341 after three artillery shells and two late officer hits. Protected `#14` was blocked by roadblock `#4` at 3251, took officer and artillery damage, and died at 3911. Roadblock and protected identifiers are kept separate here.
- Both records left central armor `#21/#22/#33/#34` alive; R104 leaked them at 5353/5196/6846/6996, while C1 leaked at 5046/5196/6846/6996. Central failure is independent of artillery closure and cannot be inferred from it.

## Structured-record correction

The first closeout checked only `revision_hypothesis` for the decision record and validation card. The actual model output placed both in `revised_operational_plans[*].validation_card`, with the decision record nested as `validation_card.experience_selector_decision_record`. Both C1 and C2 supplied them. This audit corrects the derived closeout classification without changing or rewriting the original output. It remains an archive traceability correction, not proof that the model's use was tactically correct.

## One unauthorized next question

Can a seven-ID plan retain C1's observed Friston block/kill of #11/#13 while separating that blocker from the Ansel/Hibiscus heal target competition that C1 diverted toward Friston, so R104's Steward-support window is preserved enough to observe the R104 4200–4280 closure? This requires a concrete mechanism such as timed blocker retreat/replacement or repositioning away from the shared heal range; “heal Steward more” alone is not the test. Any blocker survival, physician target delivery, shell exposure, protected `#3`, and central armor must all be independently observed. A minimum test is one candidate and one complete fixed simulation, allowing the necessary coupled blocker/support change but forbidding unrelated global revision.
