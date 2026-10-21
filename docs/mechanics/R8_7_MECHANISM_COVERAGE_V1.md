# R8-7 decisive mechanism coverage

## Fixed inputs and provenance

| Input | SHA-256 | Evidence status |
|---|---|---|
| `data/ArknightsGameData/zh_CN/gamedata/levels/obt/main/level_main_08-07.json` | `c9c376e3d5b37e5f764006fce5d1c94f12f233c995545adfe36c2beb8573cdc8` | CONFIRMED_FROM_GAMEDATA; upstream commit UNKNOWN because the working data tree is untracked |
| `data/ArknightsGameData/zh_CN/gamedata/levels/enemydata/enemy_database.json` | `7175461f03c2b29d0dc336d34d7b717dc0e33403b649b745ff852af7aef731bd` | CONFIRMED_FROM_GAMEDATA; upstream commit UNKNOWN |
| `data/ArknightsGameData/zh_CN/gamedata/excel/character_table.json` | `42708ca01b1938df4e2c3ed9e9efeadbf0e35533411907dadb37b80315e69ae8` | CONFIRMED_FROM_GAMEDATA; upstream commit UNKNOWN |
| `data/client/lib/arm64-v8a/libil2cpp.so` | `3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259` | CONFIRMED_CLIENT_BUILD_2771_STATIC_EVIDENCE |
| `data/client/assets/bin/Data/Managed/Metadata/global-metadata.dat` | `bf14421bbafe9c71d944ba4f97b31ecd666232640eac0829db3d84ac716ac8b8` | CONFIRMED_DECRYPTED_METADATA_INPUT; semantic mapping remains partial |
| `data/prts/roadblock.html` | `794dc86948bb7915912e3f69bd9ba9b41bfa77d1ee67a9fc2898986fa268e3cc` | SUPPLEMENTARY_PRTS |
| `data/prts/hatred.html` | `4ea6e1ccac2276b4d8d89479a2e5cf6e056834c01f0807e08b453fd31c4c17f7` | SUPPLEMENTARY_PRTS |
| `data/prts/battle-mechanics.html` | `d0523c8f259c6521f9ee8143e70d00d0a7ae4f14b9ac82ee3799d3106372b61a` | SUPPLEMENTARY_PRTS |

Client-side extraction used UnityPy 1.23.0, LZ4AK decoding, and Capstone AArch64. The
authoritative saved artifacts are `output/r8_1_roadblock_prefab_evidence_v2/` and
`output/r8_1_roadblock_walk_navigation_v3/`; their saved provenance records the tool versions.

## R8-7 chain status

| Mechanism | Status | Implementation/source | Boundary |
|---|---|---|---|
| Artillery attributes and delayed area attack | CONFIRMED_FROM_CODE_AND_GAMEDATA | `src/arknights_planner/gamedata/repository.py:294`, `src/arknights_planner/simulator/simulator.py:710` | GameData gives HP 13000, ATK 1000, DEF 800, MR 50%, radius 2.0, base attack time 5.0; current runtime uses ability cooldown 5.0 and blast radius 1.2 |
| Protected-target acquisition priority | CONFIRMED_FROM_CODE | `simulator.py:_enemy_ability_outputs` | Neutral protected targets inside acquisition radius are chosen first; otherwise deployed operators |
| Locked blast position and delayed hit | CONFIRMED_FROM_CODE | `simulator.py:_enemy_ability_outputs`, `_process_area_hit` | Position is locked when ability starts; hit applies after 3.0 seconds |
| Normal-attack suppression for artillery | CONFIRMED_FROM_CODE | `simulator.py:_enemy_outputs` | A `DELAYED_LOCKED_AREA_ATTACK` ability suppresses ordinary enemy projectile output |
| Ability clock | CONFIRMED_FROM_CODE | `simulator.py:_enemy_ability_outputs` | Next-fire time is set after the ability output scheduling pass; exact client lock/interval framing is not separately disassembled |
| Operator enemy targeting and devices | CONFIRMED_FROM_CODE | `simulator.py:_target_enemy_for`, `_target_device_for` | Enemies take precedence; devices are selected only when no enemy is eligible |
| Healing target and amount | CONFIRMED_FROM_CODE | `simulator.py:_target_ally_for`, operator output | Lowest-HP covered ally; current model applies base ATK without unknown external modifiers |
| Physical/Arts damage | CONFIRMED_FROM_CODE_AND_PRTS | `simulator.py:physical_damage`, `arts_damage` | 5% floor; DEF and MR do not cross-combine |
| Civilian protection | CONFIRMED_FROM_CODE_AND_GAMEDATA | Neutral `enemy_3001_upeopl`; protected route arrival and death scoring | Operator ordinary targeting rejects neutrals; officer attack has a separate protected-target radius |
| Roadblock block/release | CONFIRMED_FROM_CODE_AND_GAMEDATA | `trap_020_roadblock`; saved LZ4AK prefab evidence | Taunt -1, radius 0.4472, HP 8000, DEF 200, RES 20; destruction refreshes route state |
| Route refresh chain | PARTIALLY_CONFIRMED_FROM_CLIENT | `output/r8_1_roadblock_walk_navigation_v3/ordinary_walk_navigation_evidence.json` | `Route.ReconstructNextMap -> SPFA` remains `UNKNOWN_MISSING_STATIC_EDGE` in build 2771 |
| Redeployment cooldown | CONFIRMED_FROM_CODE | `simulator.py:_deploy`, `_retreat`, `_remove_operator` | Current runtime sets cooldown at exit time and resets runtime operator state; cost growth/special rules remain UNKNOWN in static ledger |
| Conditional static redeployment | FIXED_AND_REGRESSION_COVERED | `scripts/compile_r8_1_lowstar_c2_plan_v1.py` | Static now distinguishes self/other occupancy and does not treat future death as fact or bypass DP |
| Dodge/shield/barrier/status defenses | NOT_IMPLEMENTED | Mechanics audit | Do not infer炮击 dodge from “physical damage” alone; no probabilistic win is claimable |
| Chapter 6-11 broad enemy/Boss coverage | NOT_CLOSED | No broad audit in this milestone | R8-7-only chain closure does not imply complete chapter support |

## Static redeployment correction

Old behavior: a repeated `DEPLOY` while an operator was still active cleared occupancy and
cooldown, and the DP ledger skipped cost. This conflated current deployment, explicit retreat,
observed death, and an assumed future exit.

Correct behavior:

- Another occupant of the target tile is a static conflict.
- Self-occupancy is only a conditional redeploy: exit must occur before the new deploy, cooldown
  and tile/slot release must hold, and death remains unknown rather than assumed.
- The static ledger reserves attention on base redeploy cost without silently paying it; actual
  cost growth and special rules are `UNKNOWN_REQUIRES_RUNTIME_VERIFICATION`.
- Explicit retreat still gives a known cooldown and pays a fresh deployment generation on the
  next legal deploy.

Behavioral regressions cover self-occupancy, another occupant, exact cooldown boundary, one frame
early, explicit-retreat generation, and base-cost unavailability.
