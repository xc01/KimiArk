# Progress

## Milestone 1 — Real GameData archaeology

Status: **completed** on 2026-09-14. The supplied archive was unpacked into
`data/ArknightsGameData`. This directory is intentionally Git-ignored.

The inspected snapshot identifies itself in the ZIP header as
`0ef7f952dfd018392200157a5c79a6511ba69122`.

### Confirmed repository layout

All three required directories exist:

- `zh_CN/gamedata/excel/`
- `zh_CN/gamedata/levels/`
- `zh_CN/gamedata/battle/`

The checkout contains 7,577 JSON files. The relevant Excel tables are present.

### Operator trace: 阿米娅 (`char_002_amiya`)

1. `excel/character_table.json["char_002_amiya"]`
   - `phases[*].attributesKeyFrames[*].data` contains progression stat keyframes.
   - `phases[*].rangeId` references ranges: `3-6`, then `3-1`.
   - `skills[*].skillId` references `skcom_magic_rage[3]`, `skchr_amiya_2`, and
     `skchr_amiya_3`.
2. `excel/skill_table.json[skillId]`
   - the root contains `skillId`, `hidden`, and `levels`;
   - human-readable skill name, SP data, duration, blackboard values, and optional
     skill range are at `levels[*]`, not at the root;
   - `levels[*].spData` contains `spType`, `maxChargeTime`, `spCost`, and `initSp`.
3. `excel/range_table.json[rangeId]`
   - each range has `id`, `direction`, and `grids`;
   - each grid uses exact `row`/`col` offsets. For range `3-6`, there are nine cells.

`arknights-data inspect-operator char_002_amiya --resolve-relations` now traces this
canonical operator → skill → range chain in one read-only report.

### Enemy trace: 源石虫 (`enemy_1007_slime`)

- `excel/enemy_handbook_table.json["enemyData"]` holds handbook metadata, such as
  name and descriptions. It is **not** the numeric combat-stat source.
- `levels/enemydata/enemy_database.json["enemies"]` is a list of records with
  `Key` and `Value` fields. `Key == "enemy_1007_slime"`; `Value` holds per-level
  records with `level` and `enemyData`.
- Exact numeric fields are wrapped as `{ "m_defined", "m_value" }` under
  `enemyData.attributes`, while `lifePointReduce` is directly under `enemyData`.

For level 0, the repository reports source-backed values: HP 550, ATK 130, DEF 0,
RES 0, move speed 1.0, base attack time 1.7, mass level 0, and life-point reduction
1. Every value retains its JSON source path.

### Simple-stage trace: 0-1 (`main_00-01`, 坍塌)

1. `excel/stage_table.json["stages"]["main_00-01"]` maps code `0-1` to
   `levelId: "Obt/Main/level_main_00-01"`.
2. The repository deterministically maps that ID, case-insensitively, to
   `levels/obt/main/level_main_00-01.json`. This level file does not itself expose
   a `levelId`, so resolution must start from `stage_table`.
3. The level file has a 6×9 `mapData.map` tile-index matrix, tile definitions in
   `mapData.tiles`, ten routes, one wave, and options including initial cost 10 and
   character limit 8.
4. `enemyDbRefs` references `enemy_1007_slime` and `enemy_1002_nsabr`, both level 0.
   The top-level `enemies` list is empty for this database-backed stage.
5. Spawn actions are nested under `waves[*].fragments[*].actions[*]`; seven actions
   have `actionType: "SPAWN"`, with `key`, `count`, `preDelay`, `interval`, and
   `routeIndex`. Routes have start/end positions plus optional checkpoints.

### Implemented corrections

- `GameDataRepository.get_skill()` and `.get_range()` now return canonical models,
  not raw JSON.
- `get_enemy()` now uses the actual enemy database and treats an undefined wrapper
  as `UNKNOWN` rather than returning its placeholder value.
- `get_stage()` uses `stage_table.levelId`, derives map dimensions from the actual
  matrix (`DERIVABLE`), resolves enemy references, spawn-action count, initial DP,
  and deployment limit.
- Offline fixtures now mirror the real `Key`/`Value`, `m_defined`/`m_value`,
  `levelId`, `mapData.map`, `enemyDbRefs`, and nested-wave structures.

### Still unresolved — deliberately not simulated

- Meaning of non-zero enemy-level records with partially undefined fields; no base
  inheritance/override merge is inferred.
- Semantics for combining wave, fragment, and action `preDelay` values into absolute
  spawn time.
- Tile-index interpretation beyond the raw tile record and the directional rotation
  semantics of attack-range offsets.
- Operator stat interpolation, trust/potential effects, and skill blackboard
  behavior beyond raw numeric extraction.
- Projectile speed, attack windup, damage-frame ordering, event ordering, and all
  special mechanics.

No simulator, planner, Agent, or game-control work was started in this milestone.

## Validation

Focused offline archaeology tests: **7 passed**.

## Milestone 1.5 — Client Mechanics Archaeology

Status: **completed (bounded static inspection)** on 2026-09-14. No simulator code
was added or changed.

### Inspected client build

| Field | Value |
| --- | --- |
| Supplied package | `arknights-hg-2771.apk` |
| APK SHA-256 | `0b79b85383e21a6343283bc6bfd7a9d24eb4134abf901115f757da6a5d50f6db` |
| ZIP entry timestamp | 2026-08-20 12:32–12:33 |
| Engine | Unity `2021.3.39f1` |
| Runtime | IL2CPP, ARM64 (`lib/arm64-v8a/libil2cpp.so`) |
| Extracted local evidence | `data/client/assets/bin/Data/Managed/Metadata/global-metadata.dat`, `data/client/lib/arm64-v8a/libil2cpp.so`, `data/client/assets/bin/Data/globalgamemanagers` |

The package file name identifies build `hg-2771`. An Android `versionName` could not
be read with the locally available static tooling; it is therefore not claimed.
`libil2cpp.so` is a stripped AArch64 binary. Its dynamic symbol table does not expose
battle implementation names, and no local IL2CPP metadata decompiler is installed.

### Mechanics findings

| Mechanic | Status | Evidence/source | Confidence | Concise interpretation |
| --- | --- | --- | --- | --- |
| Wave/fragment/action scheduling fields | **KNOWN** | `global-metadata.dat`: `StartFragment` at byte 9,176,958; `preDelay`, `fragmentPreDelay`, `preDelayTime`, `waveStartTime`, `waveStartFrameCnt`; `Unpack_Torappu_LevelData_WaveData_FragmentData_ActionData` | 0.95 | The client has a distinct wave/fragment/action scheduler and tracks both delay and wave-start state. |
| Exact cumulative `preDelay` → absolute spawn-time equation | **UNKNOWN** | Same metadata has `_AdjustActionDelaysInFragment`, `_CalculateFragmentDuration`, `_FixLevelWaveDelay`; no recoverable method body/formula was available | 0.15 | Do not yet sum wave, fragment, and action delays in the simulator as though their ordering were confirmed. |
| Directional attack-range query | **KNOWN** | `zh_CN/gamedata/[uc]lua/hotfixes/RebuildCharacterOnTileInRangeHotfixer.lua:80` calls `LitePhysicsUtil.FindTilesInBox(rangeId, pos, owner.direction, nil)`; metadata also has `MapToWorldPosition` / `WorldToMapPosition` | 0.95 | A range ID is evaluated relative to position **and direction**, not as an absolute set of tiles. |
| Exact `range_table.grids[row,col]` rotation and map-coordinate transformation | **UNKNOWN** | The oriented query is visible, but the `LitePhysicsUtil` transformation body is IL2CPP-only; no exact rotation matrix or row/column origin convention was recovered | 0.20 | Keep a replaceable direction-transform subsystem. Do not assume clockwise/counter-clockwise mapping yet. |
| Raw operator/enemy base-stat fields | **KNOWN** | Real GameData evidence in Milestone 1; client metadata contains `baseAttackTime` and `get_baseAttackTime` (first byte occurrence 2,820,115) | 0.90 | Keyframe/database values and base attack time are actual runtime-facing fields. |
| Operator level interpolation, potential, trust, and full enemy-level inheritance | **UNKNOWN** | No client calculation body could be recovered; nonzero enemy database variants can leave fields `m_defined: false` | 0.15 | Preserve raw keyframes and defined values; do not assume linear interpolation or merge behavior. |
| Attack lifecycle structure | **KNOWN** | Metadata events: `OnAttackCastStart` (4,910,718), `OnProjectileBorn` (4,324,650), `OnProjectileReached` (4,322,236), `OnProjectileHit` (5,049,224), `OnOutputDamage` (4,108,140); also `CalculateAttackInterval` | 0.90 | The architecture must support attack/cast, optional projectile, reach/hit, then damage output as separable events. |
| Exact windup, recovery, hit frame, and attack-type mapping | **UNKNOWN** | Event identifiers demonstrate phases but expose no timings or universally applicable state transition | 0.15 | Keep timing values configurable/unknown; do not assign a universal hidden windup. |
| Projectile parameter vocabulary | **KNOWN** | Metadata has `projectile_speed` (1,574,929), `projectile_move_speed`, `projectile_turn_speed`, `projectile_target_pos_offset`, and `projectile_life_time` | 0.95 | The client recognizes independent projectile speed, move speed, turn speed, target offset, and lifetime parameters. |
| Generic projectile travel formula and homing rule | **UNKNOWN** | Metadata includes `FaceProjectileRotationToTargetDirection` (4,740,844), `AttractProjectileTraceTargetToOwner` (4,936,445), and `CheckProjectileMissTarget` (4,756,048), but no binding from projectile type/blackboard to these paths | 0.20 | Homing/turning exists for at least some behaviours, but may not apply to all ranged attacks. Do not infer `delay = distance / speed` as ground truth. |

### Architecture consequence

This does **not** justify an exact simulator. It does materially validate the planned
interfaces: separate attack-start, projectile, hit, and damage events; a replaceable
distance-dependent projectile model; and a replaceable directional range transform.
The present default must remain approximate until specific formulas are measured or
recoverably decompiled.

### Remaining UNKNOWNs after this milestone

- cumulative delay scheduling and the exact action execution order;
- grid-coordinate origin and direction rotation matrix;
- operator progression interpolation, trust/potential additions, and enemy-variant
  inheritance;
- attack windup/recovery and the timing of damage emission;
- projectile speed units, target tracking, collision, and which operators use each
  projectile behaviour.

## Milestone 2 — Minimal canonical synthetic simulator foundation

Status: **completed** on 2026-09-14. This is a deterministic synthetic testbed, not
a real-stage simulator or an emulator.

### Completed work

- Added minimal simulation-facing canonical models:
  - `Route` / `Waypoint` for continuous piecewise-linear position;
  - `StageMap` / `Tile` / `SpawnEvent` alongside the canonical `Stage`;
  - `Strategy` / `Action` / `ActionType`;
  - mutable `SimulationState`, immutable `SimulationResult`, and event records.
- Added explicit event types: `SPAWN`, `DEPLOY`, `ATTACK_START`,
  `PROJECTILE_BORN`, `PROJECTILE_HIT`, `DAMAGE`, `ENEMY_DEATH`, and `ENEMY_LEAK`.
  `BLOCK` and `UNBLOCK` are also recorded to make the simple blocking model
  observable in tests.
- Added replaceable interfaces for range transformation and projectile timing.
  Their default implementations are named `CanonicalSyntheticRangeTransformer` and
  `InstantProjectileModel`; neither is a claim about real-client mechanics.
- Added one hand-authored stage (`synthetic-1`): a 7×3 ground-tile map, one route
  from a red to a blue tile, four explicit enemy spawns, three simple operators,
  initial DP 10, deployment limit 2, and life 3.
- Implemented only spawning, continuous movement, natural DP, deployment checks,
  deployment cost/limit, simple blocking, deterministic target selection, synthetic
  tile-range checks, attack interval, physical damage, death, and leaks.

### Explicit simulator assumptions

- Time advances in configurable fixed increments; the default is `dt = 0.1 s`.
- All stage values are explicitly synthetic. No unresolved GameData timing, range
  rotation, stat interpolation, skill, trust/potential, or special mechanics enter
  this simulation.
- Synthetic physical damage is `max(1, ATK - DEF)`. This is a fixture rule only.
- The synthetic range convention defines offsets for `RIGHT` and rotates them by a
  stated 90° rule for `DOWN`, `LEFT`, and `UP`; it is isolated behind an interface
  because the real transformation remains unknown.
- The default projectile model has zero travel time. It nevertheless logs distinct
  attack-start, projectile-born, projectile-hit, and damage events at the same
  timestamp. A future model can return a nonzero hit delay without changing the
  simulator event architecture.
- An operator blocks only when its tile lies exactly on an enemy route and has spare
  synthetic block capacity. No real collision or multi-block rules are claimed.

### Event-ordering assumption

At each simulation timestamp the deterministic order is:

1. delayed projectile hits due at that timestamp;
2. scheduled deployment actions, in strategy order;
3. scheduled spawns, in stage order;
4. available attacks and their zero-delay event chain;
5. movement to the next tick, blocking/leaks, then natural DP generation.

This ordering is deliberately an explicit synthetic convention, not an inferred
Arknights frame-order claim.

### Validation

Focused tests cover spawn scheduling, continuous route movement, DP generation,
legal/illegal deployment, deployment limit, range/target acquisition, event ordering,
physical damage, death, blocking/unblocking, life loss, and a fixed end-to-end win.

```text
16 passed in 0.10s
```

### Remaining UNKNOWNs and next action

All real-client UNKNOWNs from Milestone 1.5 remain unknown: delay aggregation,
range-coordinate transformation, stat interpolation and inheritance, attack windup
and recovery, and projectile travel/homing rules. The next action, when requested,
is to extend only the synthetic simulator with the next bounded mechanics (for
example skills or healing) and tests; search, planner, real-stage simulation, and
Agent work remain out of scope.

## Milestone 3 — Minimal synthetic strategy search

Status: **completed** on 2026-09-14. The simulator mechanics were not changed; only
its terminal result now exposes synthetic remaining-enemy count, HP, and route
progress so failed candidates can be ranked densely.

### Search representation and evaluator

- Search uses the existing `Strategy` and `DEPLOY` `Action` types unchanged.
- A synthetic candidate parameterizes operator selection, action/deployment order,
  tile, facing direction, and deployment time.
- Coarse deployment times are exactly `0.0`, `0.5`, and `1.0` seconds (multiples of
  the simulator's 0.1-second resolution); no frame-by-frame timing is searched.
- `SyntheticStrategyEvaluator` scores only simulator-observable signals: win,
  remaining life, kills, leaks, remaining enemy count/HP/route progress, invalid
  action count, and action count. The numeric weights are synthetic ordering weights,
  explicitly not Arknights reward semantics.

### Deterministic failure analysis

`analyze_failure()` derives these categories directly from deployment errors and
event logs:

- `INSUFFICIENT_DP`
- `ILLEGAL_DEPLOYMENT`
- `DEPLOYMENT_LIMIT_REACHED`
- `LEAK_BEFORE_DEFENSE`
- `INSUFFICIENT_DAMAGE`
- `POOR_DEPLOYMENT_TIMING`

It does not diagnose hidden mechanics or call an Agent.

### Algorithm and bounded space

- Algorithm: deterministic two-depth beam search (beam width 8), then greedy local
  timing refinement at ±0.1/±0.2 seconds when nonnegative.
- Synthetic placement options: 48 first-action candidates (operator, tile, facing,
  coarse time). The unrestricted two-action synthetic space would contain 1,560
  candidates; the beam run generates 288 candidates and evaluates 292 strategies
  including timing refinement.
- Immutable stage/operator/enemy fixtures are reused; each simulator evaluation owns
  a fresh mutable state. Results are cached by normalized action tuple.

### Demo result

`arknights-plan demo` starts from no hand-authored strategy and discovers:

```text
00.0  DEPLOY guard at (2, 1) facing LEFT
00.0  DEPLOY archer at (0, 2) facing UP
Result: WIN
Synthetic score: 12296.0
```

For the default deterministic configuration, the first winning evaluation appears at
simulation 49. The complete run generates 288 candidates, evaluates 292 simulations,
has 76 unique winning evaluations, reaches depth 2, and returns best score 12296.0.
Wall-clock time is recorded as a metric and was about 0.44 seconds in the local run.

### Validation

Focused tests cover dense ranking, failure classification, deterministic candidate
generation, deterministic same-seed configuration, synthetic win discovery, local
timing non-regression, and the existing simulator behavior.

```text
16 passed in 1.83s
```

### Architectural result and next action

The current `Strategy` / `Action` / `SimulationState` / `SimulationResult` boundary
is sufficient for small automatic discovery: no structural simulator change was
required beyond exposing terminal synthetic state for evaluation. Search naturally
uses the simulator as an evaluator, not a source of game-fidelity claims.

The next action, only when requested, is a separately bounded extension. It must not
silently add skills, healing, real-stage mechanics, unresolved timing rules, Agent/
LLM calls, RL, or game control.

## Milestone 4 — Core synthetic combat runtime mechanics

Status: **completed** on 2026-09-14. This remains a deliberately synthetic combat
testbed. It does not interpret real GameData skills or claim real-client timings.

### Mutable operator runtime state

`RuntimeOperator` now keeps mutable combat state separate from the immutable
canonical `Operator`: current/max HP, current SP, skill readiness/active state and
remaining duration, base attack/range/block values, calculated attack cooldown,
blocked enemy IDs, and configurable redeploy time. `SimulationState` records
redeploy availability and operator deaths.

### SP and skill model

- `SyntheticSkill` explicitly carries initial SP, SP cost, recovery mode, synthetic
  SP per second, duration, and a small `SkillEffect` value object.
- Only `TIME` recovery is implemented: inactive skills gain SP at the configured
  rate, capped at their synthetic SP cost. `ATTACK` and `DEFENSE` modes are reserved
  enum values only; no real mechanic has been inferred for them.
- `ACTIVATE_SKILL` is a `Strategy` action. It is rejected deterministically when
  the operator is absent, lacks a synthetic skill, is already active, or lacks SP.
- `SKILL_READY`, `SKILL_ACTIVATE`, and `SKILL_END` are explicit events. Effects are
  calculated from immutable base values while active, so cleanup is automatic when
  `SKILL_END` clears the active state.
- Supported synthetic effects are attack multiplier plus additive attack, attack
  interval multiplier, range override/addition, and block-count delta. These are
  test-fixture configuration, not a GameData blackboard interpreter.

### Healing and enemy attacks

- `CombatOutputType.HEAL` selects the most-injured covered friendly target, emits
  attack/projectile events followed by `HEAL`, and caps restoration at max HP.
- The initial synthetic enemy model attacks only the operator blocking it, on its
  configured interval, using the same synthetic physical rule
  `max(1, attacker ATK - target DEF)`. It has no ranged targeting or special
  behavior.
- `OPERATOR_DEATH` releases every enemy held by that operator before removing it.
  `RETREAT` follows the same release path without counting an operator death and
  begins the configured synthetic redeploy cooldown. A later deployment is rejected
  until that cooldown expires. No real retreat refund/timing semantics are claimed.

### Tile deployment rules

Synthetic `Tile.tile_kind` now distinguishes `GROUND`, `HIGH_GROUND`, and
`NON_DEPLOYABLE`. A synthetic `MELEE` operator may deploy only on `GROUND`; a
synthetic `RANGED` operator may deploy only on `HIGH_GROUND`. This isolated rule
does not interpret real level tile types.

### Event ordering assumption

The explicit synthetic event sequence at a timestamp is now:

1. due delayed projectile hits;
2. scheduled strategy actions in strategy order;
3. scheduled spawns;
4. blocked-enemy attacks;
5. operator damage/healing outputs;
6. movement, blocking, leaks, and DP accumulation to the next fixed tick;
7. time-SP and skill-duration advancement at that tick boundary.

Therefore a `SKILL_READY` or `SKILL_END` event emitted at a tick boundary is visible
before the next timestamp's actions/outputs. Zero-delay projectiles still preserve
the logical `ATTACK_START → PROJECTILE_BORN → PROJECTILE_HIT → DAMAGE/HEAL` chain.
This is an intentional deterministic convention, not a recovered Arknights event
order.

### End-to-end synthetic runtime scenario

Added `synthetic-runtime-1`: one strong brute on a single lane, a ground blocker,
a high-ground DPS operator with a manually activated burst skill, and a
high-ground healer. Its fixed strategy deploys all three at `0.0 s` and activates
the DPS burst at `3.0 s`; it clears at `5.5 s` with no leak or operator death.

The calibration is intentionally discriminating: omitting the burst fails, and
omitting the healer lets the blocker die and also fails. It proves the runtime data
flow and event architecture only; it is not a claim about a real Arknights stage.

### Validation

Focused tests cover natural SP recovery, insufficient-SP rejection, ready/activate/
end events, attack and interval modifiers plus cleanup, range override, block-count
modifier, healing/HP cap, enemy damage, death/unblocking, retreat/unblocking,
redeploy legality, ground/high-ground legality, and the complete required-runtime
scenario. Existing core simulator and minimal-search tests remain included.

```text
28 passed in 2.41s
```

### Architectural limitations and remaining UNKNOWNs

- The runtime has separate event boundaries for attack start, projectile birth/hit,
  damage, and healing, but its default projectile has zero travel time and there is
  no windup or animation recovery model.
- Directional range transforms remain the synthetic replaceable transform from
  Milestone 2; actual `range_table` rotation is still unknown.
- Real GameData skill blackboards, SP modes, stat interpolation, trust/potential,
  real redeploy values/refunds, enemy ranged attacks, special mechanics, and wave
  `preDelay` semantics remain unknown or unimplemented.
- No real stage is simulated, and search, Agent/LLM, Ark, network, OCR, ADB, or game
  control work was added in this milestone.

The requested bounded runtime milestone ends here. The next action must remain
separate and must not begin real GameData integration without a new request.

## Milestone 5 — Real GameData to Simulation Adapter

Status: **completed** on 2026-09-14. This milestone establishes a strict adapter
boundary only. It does not run a real-stage battle.

### Adapter architecture

`GameDataRepository` still owns all raw JSON reads. The new
`RealSimulationAdapter` consumes only canonical `Operator`, `Skill`, `AttackRange`,
`Enemy`, and `Stage` models and produces a `RealSimulationBundle` containing:

- an exact-keyframe `AdaptedRealOperator`;
- a structurally loaded but non-executable `RealSkillData`;
- an `AdaptedRealEnemy` with undefined fields retained as `UNKNOWN`;
- an `AdaptedRealStage` that retains its source-level map, routes, and
  wave/fragment/action hierarchy;
- a machine-readable `CompatibilityReport`.

The simulator remains independent of GameData JSON and was not taught to parse it.
`require_simulator_execution()` is a strict gate: it raises rather than passing real
data with unresolved mechanics into the synthetic runtime.

To retain the required source facts, canonical models now preserve exact operator
attribute keyframes, individual skill blackboard parameter provenance, and a
`StageLevelStructure` with raw tile-index matrix, normalized tile records, route
row/col positions, and nested timing metadata. No wave delays were flattened into
`SpawnEvent` timestamps.

### Real entities verified

**Operator — `char_002_amiya` (阿米娅)**

- Selected exact source keyframe: phase 0, level 1; HP 699, ATK 276, DEF 48,
  RES 10, cost 18, block 1, base attack time 1.6, and respawn time 70 are preserved
  from `character_table.json`.
- The selected range is `3-6`; its stored `row`/`col` offsets are loaded exactly.
  They are not converted through the synthetic range transformer.
- Requesting phase-0 level 2 reports unsupported interpolation instead of making up
  a value.

**Skill — `skcom_magic_rage[3]`, level index 0**

- Loaded structurally from `skill_table.json`: name `战术咏唱·γ型`, SP type
  `INCREASE_WITH_TIME`, initial SP 0, SP cost 40, duration 30, and its raw
  `attack_speed = 30.0` blackboard entry with individual source paths.
- It is deliberately marked **not simulator-executable**. No blackboard key has
  been interpreted as a generic skill effect.

**Enemy — `enemy_1007_slime`, level 0**

- Loaded from the actual `enemy_database.json` record: HP 550, ATK 130, DEF 0,
  RES 0, move speed 1.0, base attack time 1.7, mass 0, and life-point reduction 1.
- At level 1, only explicitly defined values (for example HP 2050 and ATK 300) are
  accepted. DEF, RES, move speed, attack time, mass, and life-point reduction stay
  `UNKNOWN`; the adapter does not merge them from level 0.

**Stage — `main_00-01` / `0-1`**

- Resolves through `stage_table.json` to its actual level file.
- The adapter retains the 9×6 map-index matrix, 54 source tile records, initial DP
  10, deployment limit 8, ten route records, enemy database references, one wave,
  six fragments, and seven `SPAWN` actions.
- Each action keeps its own `preDelay`, `interval`, `count`, `key`, and `routeIndex`
  under its original wave and fragment. No absolute spawn time is claimed.

### Strict compatibility outcome

For Amiya phase 0 level 1 + slime level 0 + 0-1, the source data is structurally
loadable but **not executable** by the current simulator. The current provenance
walk reports 1,199 `KNOWN`, 2 `DERIVABLE`, 0 `APPROXIMATED`, and 1 source-field
`UNKNOWN` values; separately, the report lists the mechanics blockers that cannot
be inferred from those values:

- real directional range `row`/`col` transformation;
- cumulative wave/fragment/action `preDelay` to absolute spawn timing;
- selected real skill blackboard/effect interpretation;
- real attack windup/recovery timing;
- real projectile behavior/timing.

The `arknights-data simulation-compatibility 0-1` command prints this concise,
read-only decision and never starts an approximate battle.

### Validation

Focused tests cover exact-keyframe selection and rejected interpolation; structural
real-skill load with blackboard provenance; level-0 enemy values and unmerged
higher-level undefined values; stage-table-to-level resolution; map/routes/enemy
references/wave hierarchy; unrotated real range offsets; strict compatibility
blockers; CLI output; and all prior synthetic simulator/search/runtime behavior.

```text
41 passed in 5.95s
```

### Architectural result and next recommendation

The only canonical-model changes were fact-retention additions; no simulator or
synthetic-search mechanics changed. The strict gate confirms that missing
mechanics remain visible rather than becoming accidental numeric defaults.

The next recommended bounded milestone is to gather evidence for one specific
missing real mechanic (for example the range transform or spawn scheduling) or to
define an explicit, opt-in approximation policy. It must remain separate from
real-stage execution and Agent integration.

## Milestone 6 — Explicit Approximation Policy + First Real 0-1 Battle Loop

Status: **completed** on 2026-09-14. This is the first real GameData execution
path, and it is explicitly approximate. It is not an Arknights emulator.

### Execution modes and policy boundary

Two modes are now explicit:

- `STRICT_REAL` remains unchanged. It delegates to the Milestone 5 strict gate and
  refuses real simulation while any required mechanic is unknown.
- `APPROXIMATE_REAL` requires a non-null `RealSimulationApproximationPolicy` before
  it constructs any simulator fixture. It never falls back automatically from
  strict mode.

The bounded 0-1 policy records all approximations in the fixture, result metadata,
and CLI output:

- `SYNTHETIC_90_DEGREE_ROW_COL` — raw real range cells `(row, col)` are treated as
  synthetic `(col, -row)` offsets and rotated by the existing 90° rule;
- `CUMULATIVE_HIERARCHICAL_PREDELAYS` — wave `preDelay`, cumulative fragment
  `preDelay`, then action `preDelay` determine approximate timestamps;
- `ZERO_WINDUP_ZERO_EXTRA_RECOVERY` — source `baseAttackTime` remains the full
  simulator attack interval;
- `INSTANT_PROJECTILE` — the existing zero-delay projectile model still emits the
  logical attack/born/hit/damage event sequence;
- `REVERSED_SERIALIZED_MAP_ROW` — serialized map row `i` is mapped to source route
  row `height - 1 - i`; this is a visible 0-1 coordinate approximation, validated
  against the source `tile_start` and `tile_end` route endpoints but not claimed as
  recovered client behavior;
- `EXISTING_SYNTHETIC_PHYSICAL_DAMAGE` and
  `ONE_DP_PER_COST_INCREASE_INTERVAL` — existing runtime damage and natural-DP
  models are used transparently for this integration fixture.

The real skill compatibility limitation is not removed. Real skill data remains
structurally loaded but non-executable; the 0-1 strategy contains no
`ACTIVATE_SKILL` action, so unsupported blackboard effects are not exercised.

### Real 0-1 fixture conversion

The approximate adapter converts only source-backed data needed by this run:

- Real tiles use `buildableType`: `MELEE → GROUND`, `RANGED → HIGH_GROUND`, and
  `NONE → NON_DEPLOYABLE`. Any other or missing type becomes non-buildable
  `UNKNOWN`; no unknown tile is made deployable.
- The 0-1 source map remains 9×6. Example mapped deployment tiles are `(4,2)`,
  source `tile_wall`/`RANGED` → `HIGH_GROUND`, and `(1,3)`, source
  `tile_road`/`MELEE` → `GROUND`.
- Source route coordinates become simulator `(x=col, y=row)` waypoints. Route 2 is
  preserved as `(8,2) → (3,3) → (3,2) → (1,2) → (1,3) → (0,3)`.
- The retained hierarchy is not flattened in canonical data. The visible
  approximation produces 0-1 SPAWN start times `5.0, 13.0, 21.0, 26.0, 29.0,
  36.0, 37.0` seconds, with source count/interval retained for repetitions.
- All stage-referenced level-0 enemies are resolved from the enemy database: ten
  `enemy_1007_slime` instances and one `enemy_1002_nsabr` instance. Their known
  HP/ATK/DEF/RES/move speed/base attack time/life reduction feed the current runtime.

`arknights-data approximate-stage-view 0-1` is a read-only inspection command. It
prints source tile key/buildability → simulator category for all coordinates and the
source wave/fragment/action indices → approximate spawn timeline. It never runs a
battle.

### Fixed first real strategy

The calibration strategy is hand-authored; no search is connected to real data.

```text
03.0  DEPLOY char_129_bluep (蓝毒), phase 2 level 80, at (4,2), facing RIGHT
26.0  DEPLOY char_010_chen  (陈),   phase 2 level 90, at (1,3), facing RIGHT
```

Both use exact source keyframes and no skill activation. Blue Poison is the simple
high-ground physical damage fixture (ATK 535, cost 13, interval 1.0); Ch’en is the
late ground blocker for the final soldier (ATK 610, DEF 352, cost 23, block 2,
interval 1.3). Their listed skills remain loaded only as non-executable real
metadata.

### Approximate real result

Running `arknights-plan real-demo 0-1 --data-root data/ArknightsGameData` reports
visibly as `APPROXIMATE_REAL` and yields:

```text
WIN
life=20
kills=11
leaks=0
duration=54.2s
```

The normal simulator loop emits source-derived `SPAWN`, `DEPLOY`, `ATTACK_START`,
`DAMAGE`, `BLOCK`, and `ENEMY_DEATH` events. The explicit
`ApproximateExecutionReport` and `SimulationResult.run_metadata` both contain the
mode and complete approximation manifest; the result also records source entity
IDs, so it cannot be mistaken for strict real-client ground truth.

### Validation

Focused tests cover strict refusal, missing-policy refusal, all four approximate
range facings, real tile mapping, route conversion and travel, source enemy-key
resolution, deterministic spawn conversion with intact hierarchy, source
`baseAttackTime` usage, zero-windup/instant-projectile manifest entries, unused real
skills, result metadata, full 0-1 `SimulationResult`, both inspection/demo CLIs, and
all previous synthetic and strict-adapter tests.

```text
53 passed in 12.60s
```

### Mismatches, remaining blockers, and next recommendation

The approximate clear is a calibration result only. It still relies on the named
range, map-coordinate, spawn-timing, damage, DP, windup, and projectile policies.
It does not execute real skills, talents (including Blue Poison's), modules,
trust/potential, stat interpolation, special enemy behavior, or exact timing.

The next recommended bounded milestone is to validate or replace exactly one of
these policies with stronger local evidence (most usefully directional range mapping
or spawn-delay scheduling), while retaining the strict/approximate split. Do not add
real-stage search or Agent integration before that work is separately requested.

## Milestone 7 — Minimal Real-Stage Strategy Search on 0-1

Status: **completed** on 2026-09-14. This is a bounded, deployment-only search over
the explicitly approximate 0-1 fixture. It is not an exact real-client solver and
does not add simulator fidelity, skills, real timing recovery, or Agent integration.

### Representation, fixed pool, and candidate reduction

`ApproximateRealBeamSearch` consumes the Milestone 6 adapter fixture rather than
GameData JSON. It builds a fixed exact-keyframe pool before search:

- `char_129_bluep`, phase 2 level 80 — RANGED, cost 13, basic physical DPS;
- `char_010_chen`, phase 2 level 90 — MELEE, cost 23, ground blocker/DPS;
- `char_002_amiya`, phase 2 level 80 — RANGED, cost 20, basic ranged DPS;
- `char_017_huang`, phase 2 level 90 — MELEE, cost 24, ground blocker/DPS.

Only `DEPLOY` decisions are searched: operator selection, action order, a legal
position-compatible tile, facing, and coarse time. There are no real-skill actions,
retreats, redeployments, level changes, or roster-wide enumeration.

Candidates are deterministic and aggressively reduced to source-mapped deployable
tiles of the correct category (`MELEE → GROUND`, `RANGED → HIGH_GROUND`) whose
approximate range intersects the real active-route geometry. Ground candidates must
also lie on an active route. The four highest-coverage tile/facing choices per
operator are retained (16 deployment options total). Coarse times are exactly
`0, 4, 8, 12, 16, 20, 24, 28` seconds; a conservative DP check removes individually
impossible starts. The known calibration times `3` and `26` are not coarse search
seeds.

### Evaluation, failure analysis, and algorithm

The real evaluator uses only ordinary `APPROXIMATE_REAL` `SimulationResult` facts.
Its ordering score is intentionally synthetic: a win dominates every loss, followed
by life, kills, leaks, remaining enemy count/HP/route progress, invalid actions,
operator deaths, action complexity, and duration. These weights are search ordering
signals, not real-game reward or balance claims.

Observable failure categories are: insufficient DP, illegal deployment, deployment
limit reached, defense established too late, insufficient damage, poor tile coverage,
operator death, leak before deployment, and unused deployment capacity.

Search is a two-stage deterministic beam search (beam width 8): evaluate all legal
single deployments, extend the retained frontier once with a second deployment,
then check `-1.0`/`+1.0` seconds around each action in the best candidate. No search
branches on simulation ticks. Strategy-result cache keys include stage ID, exact
operator configurations, normalized strategy, `dt`/maximum time, and the versioned
approximation-policy identity. Thus results cannot collide across policy contracts.

### Result and measurements

The executable command is:

```text
arknights-plan real-search 0-1 --data-root data/ArknightsGameData
```

It visibly prints `Mode: APPROXIMATE_REAL`, the pool, all approximation names,
configuration, result, and metrics. Under the checked local snapshot and policy,
the bounded search reports:

```text
03.0  DEPLOY char_129_bluep at (4, 2) facing LEFT

WIN
life=20 kills=11 leaks=0 duration=46.6s
generated=468 evaluated=464 unique=464 cache_hits=6 first_win=1 depth=2 refinements=2
```

The initial coarse candidate is at 4.0 seconds; local refinement finds 3.0 seconds.
This is distinct from the Milestone 6 calibration fixture, which deploys Blue Poison
facing `RIGHT` at 3.0 and then Ch'en at 26.0. The search neither initializes nor
returns that two-action calibration sequence. Its one-operator outcome is an
artifact/observation of the stated approximation policy, not a claim that this is a
valid or optimal live-game clear.

### Validation and architectural result

Focused offline tests cover fixed pool reconstruction, deterministic legal candidate
generation and DP pruning, dense win-over-loss scoring, deterministic observable
failure analysis, policy-aware cache keys, approximate-run metadata, automatic win
discovery, calibration-sequence exclusion, reproducibility, non-worsening timing
refinement, and the CLI. The existing strict-mode refusal and synthetic search tests
remain part of the wider regression suite.

```text
62 passed
```

No canonical simulator model had to change. The architecture cleanly supports
deployment-only real-stage discovery while retaining strict real-data refusal and
the explicit approximation manifest.

### Remaining blockers and next recommendation

All real-mechanics blockers remain: exact range rotation/map coordinates, wave and
fragment timing semantics, attack windup/recovery, projectile behavior, real skill
blackboards, talents, progression interpolation, and special mechanics. The next
recommended milestone is to verify or replace one named approximation with stronger
local evidence, then re-run this bounded comparison. Do not start Agent/LLM or game
execution work without a separate request.

## Milestone 8 — Minimal Real-Game Execution and Calibration Scaffold

Status: **completed (dry-run and mock validation)** on 2026-09-14. This milestone
adds a deliberately small real-client boundary for one known 0-1 strategy. It is not
a general bot, does not alter simulator mechanics, and does not perform OCR, game
state tracking, automatic calibration, or repeated attempts.

### Execution-layer architecture

The new `execution/` package is outside GameData, canonical models, simulator, and
search:

```text
Strategy -> ExecutionPlan -> StageGameExecutor -> DeviceController -> client
client -> observations -> ExecutionTrace -> CalibrationReport
simulator result -> PredictionTrace ----------------------------^
```

`DeviceController` is replaceable. `MockDeviceController` gives a deterministic
virtual clock and records all commands for tests/dry-runs. `ADBDeviceController`
uses only local `adb` subprocess commands and validates that exactly one device is
available unless a serial is explicitly configured. It has clear errors for missing
ADB, no/multiple devices, command failure, and non-PNG screenshot output. Neither
backend is imported by simulator or GameData code.

### Coordinates, plan, and gesture

`ScreenCoordinateMapper` maps viewport-normalized screen points to the current
device pixels. `StageGridCoordinateMapper` is a separate manually calibrated affine
mapping from simulator tile `(x, y)` (x right, y up) to normalized screen space.
Its signed y-axis makes the visual map-row inversion explicit; it is unrelated to,
and does not claim to solve, the approximate simulator range transform.

`configs/execution/main_00-01.example.json` supplies an **unverified template** for
one 1920×1080 layout. It contains a viewport, stage-grid anchor/axis vectors,
Blue Poison card point, facing distance, gesture durations, battle-start offset, and
checkpoint times. The values must be manually calibrated for a real device/camera
before `run --execute` is used.

The only plan is the Milestone 7 result:

```text
03.000 DEPLOY char_129_bluep at (4, 2) facing LEFT
```

For a real run the executor records a transparent configured sequence: card tap,
card-to-tile drag/release, then tile-to-facing swipe. It records gesture start,
tile-placement command completion, direction-selection command completion, and
overall completion. These are command-issuance timestamps, not a claim that the
client accepted deployment at the same instant.

### Clock and observations

The executor uses one monotonic battle origin, recorded with the trace as the
assumption `manual battle-ready confirmation + configured battle_start_offset`.
Each deadline is calculated as `origin + strategy_action.time`; it never repeatedly
sleeps an action-relative duration, so command duration cannot accumulate schedule
drift into later deadlines.

Actual guarded runs capture screenshots before/after deployment and at the configured
checkpoint times by default. The example includes 0.0, 2.5, 3.0, 5.0, 10.0, 20.0,
40.0, and 50.0 seconds, covering the known first engagement and approximate end
region. Screenshots are files referenced from traces. There is intentionally no OCR,
enemy tracking, automated victory detection, or visual claim that an operator was
successfully deployed.

### Trace and comparison formats

`ExecutionTrace` is JSON-serializable and records stage/strategy source, device and
resolution, calibration ID, common clock origin, dry-run state, source simulator
approximation manifest, resolved pixels, intended/actual command timestamps and
lateness, screenshot references, errors, and optional manually/visually recognized
terminal fields.

`PredictionTrace` runs the exact M7 strategy through the existing `APPROXIMATE_REAL`
fixture and keeps compact `SPAWN`, `DEPLOY`, `ATTACK_START`, `DAMAGE`, enemy-death,
leak, and battle-end events. The first `ATTACK_START` for each operator is presented
as a clearly derived `FIRST_TARGET_ACQUISITION` marker; it is not a recovered
real-client event.

`CalibrationReport` labels every comparison as one of `OBSERVED`, `UNOBSERVED`, or
`CANNOT_COMPARE`. It compares planned time to command issuance/lateness, and terminal
result/duration only if those were observed. Spawn and combat-event agreement is
explicitly `CANNOT_COMPARE` with screenshot-only evidence. Missing observations are
never treated as agreement.

### Dry-run result and live-device boundary

The safe command was run locally:

```text
arknights-exec dry-run 0-1 \
  --config configs/execution/main_00-01.example.json \
  --data-root data/ArknightsGameData \
  --output-dir output/m8-dry-run
```

It sent **no ADB input**, used `mock-device`, and produced execution/prediction JSON
traces. The unverified template resolved Blue Poison's card, tile, and facing points
to `(288, 940)`, `(1114, 540)`, and `(980, 540)` respectively. The prediction trace
reports the current approximate outcome `WIN`, predicted duration `46.6s`, first
attack/derived target acquisition at `8.6s`, and retains all Milestone 6 policy
names. The dry-run comparison correctly reports deployment, terminal result, duration,
and scheduler jitter as `UNOBSERVED`, and combat events as `CANNOT_COMPARE`.

No live-device experiment was attempted: the only supplied configuration is marked
`main_00-01-example-unverified-v1`, has no explicitly selected ADB serial, and is not
device/camera calibrated. A real invocation is additionally blocked unless the user
uses `arknights-exec run 0-1 ... --execute`; it prints the selected serial and actual
resolution before any input command.

### Validation, issues, and next recommendation

Deterministic tests cover viewport normalization, signed stage-grid mapping, four
facing gesture endpoints, shared-deadline/no-drift scheduling, mock gesture sequence,
all execution timestamps, trace serialization, compact prediction generation,
evidence-status reporting, dry-run no-input behavior, CLI execute guard, and ADB
command construction. The optional live-device test is marked `device_integration`
and is skipped without `ARKNIGHTS_RUN_DEVICE_TESTS=1`.

```text
76 passed, 1 skipped (explicit device integration)
```

The remaining practical real-device issues are manual stage/camera anchor calibration,
manual operator-card point calibration, battle-ready synchronization, and the lack of
operational/visual confirmation that a command succeeded. The next bounded step, if
separately requested and a calibrated device configuration is supplied, is at most one
manual `--execute` run followed by trace comparison. Do not automatically fit simulator
parameters, add Agent integration, or extend vision/OCR from this evidence alone.

## Milestone 9 — Frame-Accurate Action Timeline + Client Timing Archaeology

Status: **completed (configured frame domain; client frequency unresolved)** on
2026-09-15. Planner output now has a neutral integer-frame execution protocol. This
milestone did not add UI automation, ADB behavior, real skill interpretation, or
simulator fidelity unrelated to timing.

### Canonical frame contracts

`models.frame.FrameClock` records clock kind, optional rational frames/sec, status,
provenance, confidence, and version. `FrameClock.unknown_client()` is the real-client
default: the APK establishes frame-count vocabulary but not its wall-clock frequency.
`FrameClock.configured(30)` is used only by the bounded approximate planner/search
path and is visibly `APPROXIMATED` with provenance saying the client relation is
unresolved. No 60 FPS claim is made.

`models.timeline.FrameTimeline` is immutable and serializable (`schema_version: 1`).
Its complete external vocabulary is exactly `DEPLOY`, `ACTIVATE_SKILL`, and
`RETREAT`; `WAIT` and simulator events cannot be emitted. `FrameAction.frame` is a
validated non-negative integer. Same-frame actions are stable sorted by authored
ordinal and documented rather than dependent on hash iteration.

`timing.strategy_to_timeline()` is a one-time compatibility conversion for existing
seconds-based fixtures. New frame paths use integer frames. `Simulator.run_timeline()`
adapts a timeline to the legacy seconds runtime at one explicit boundary and rejects
unknown-frequency clocks; the inner loop does not repeatedly frame/float round-trip.

### APK timing archaeology

The targeted pass reused `data/client/assets/bin/Data/Managed/Metadata/global-metadata.dat`,
the stripped `lib/arm64-v8a/libil2cpp.so`, and Unity `globalgamemanagers` from
`arknights-hg-2771.apk` (Unity 2021.3.39f1, IL2CPP ARM64). Findings are recorded in
[CLIENT_FRAME_TIMING.md](/home/bigdata/Desktop/arknights-auto-planner/docs/CLIENT_FRAME_TIMING.md)
and exposed by `arknights-data client-frame-timing`.

`waveStartFrameCnt`, `fixedFrameCnt`, and `waveStartTime` prove that battle/wave
structures retain frame-count and time-like fields (`waveStartFrameCnt` string at
metadata byte 2,752,142; `waveStartTime` at 4,357,356). `fixedDeltaTime`,
`fixedUnscaledDeltaTime`, and `targetFrameRate` are present as generic Unity settings,
not a proven battle logic clock. `speedLevel` and pause/update vocabulary exists, but
no recoverable body establishes pause or 1x/2x frame behavior. The stripped client
provides no conversion formula, increment site, or command-to-effect offset for
DEPLOY, ACTIVATE_SKILL, or RETREAT. These remain `UNKNOWN`; names alone are not
treated as semantics.

### Frame-domain 0-1 search

Milestone 7 search now carries a configured approximate 30 FPS `FrameClock` and emits
an integer timeline after search. Candidate timing is generated from integer coarse
frames `(0, 120, 240, 360, 480, 600, 720, 840)` (0–28 seconds under this explicit
mapping), then local refinement tests `±30, ±10, ±3, ±1` integer frames. Seconds are
used only once at the simulator adapter boundary. Cache identity includes frame-clock
version/kind/frequency in addition to stage, operator configurations, policy, and
normalized strategy.

Running `arknights-plan real-search 0-1 --timing frames --data-root data/ArknightsGameData`
still discovers a non-seeded approximate win:

```text
frame 0090 DEPLOY char_129_bluep at (4, 2) facing LEFT
derived_seconds=3.000
WIN; life=20; kills=11; leaks=0; duration=46.6s
```

The bounded approximate-simulator robustness check finds winning deployment frames
`88–93` around the selected frame 90 (diagnostic only, not real-client timing). Search
metrics are `generated=468`, `evaluated=476`, `unique=476`, `cache_hits=7`,
`first_win=1`, `depth=2`, `local_refinements=8`; wall-clock timing is intentionally
excluded from reproducibility claims.

`PredictionTrace` now optionally carries integer frames for diagnostic events while
retaining derived seconds. `FrameTimeline` remains execution-facing and contains no
HP, enemy, damage, score, or other simulator state.

### Validation and limitations

New focused tests cover frame validation, exact Fraction conversion, unknown-frequency
handling, all three timeline actions, WAIT rejection, stable same-frame serialization,
legacy conversion, and frame-aware search integration. Existing M8 execution tests
remain device-free. The complete local suite reports **83 passed, 1 skipped** (the
explicit device-integration marker); no client integration or external executor was
contacted.

The most important remaining blocker to truly real-client frame-accurate timelines is
the unresolved mapping between the client's logical battle frame counter and both
wall-clock/battle-speed behavior and command acceptance/effect transitions. Until that
evidence is recovered or measured across traces, frame numbers are a stable planner
protocol, not a claim of exact live-client timing.

## Milestone 10 — Minimum-Squad / Minimum-Rarity Human-Validated Benchmark

Status: **completed (benchmark preparation; no Chapter 6–11 battle was safely
executable)** on 2026-09-15. M10 establishes feasibility-first optimization and a
reproducible low-rarity benchmark domain. It does not add Agent/LLM, UI automation,
OCR, or an undocumented real-stage approximation.

### Feasibility-first objective

`benchmark.StrategyObjective` compares strategies lexicographically, never with
reward weights:

```text
WIN
-> distinct used operators
-> GameData-derived star sum
-> timing fragility (inverse one-action-at-a-time winning-window width)
-> external action count
-> battle duration
```

`effective_operator_ids()` derives the effective squad from emitted actions, so
roster padding is ignored and `DEPLOY A -> RETREAT A -> DEPLOY A` counts as one
operator. A win is always ordered ahead of a loss. This remains general: a one-6-star
win outranks a two-2-star win because cardinality precedes rarity.

`SquadCardinalitySearch` provides the future real-team boundary: it exhausts bounded
teams by cardinality, sorts by rarity inside each cardinality, invokes cheap pruning
before any evaluation, and stops with explicit `MINIMUM_SQUAD_WITHIN_BOUNDED_DOMAIN`,
`SEARCH_BUDGET_REACHED`, or `NO_WIN_FOUND` semantics. It is deliberately separate
from timeline/tile/frame search. No Chapter 6–11 evaluator is attached while those
stages are blocked.

### Source-backed low-rarity census and mechanics

`character_table.json` encodes rarity as `TIER_N`, not a direct star integer.
Canonical `Operator.star_rarity` now derives human-facing `N` with `DERIVABLE`
provenance back to `$.<operator>.rarity`. The census uses source `itemObtainApproach`
and `isNotObtainable` to exclude character-table templates, yielding **34** locally
obtainable 1–3 star records. Each record retains ID, name, profession, phases, max
level, cost, block count, attack interval, range IDs, skill IDs, talent count,
structural-load flag, and mechanics-support classification.

The initial supported phase-0 baseline set is 12F, 黑角, 杜林, 夜刀, 巡林者, plus
operators whose phase-0 level-1 state has no active unimplemented talent. The selected
reusable real-skill pattern is manual/time-SP/finite-duration `{atk: x}`:

- 芙蓉, 玫兰莎, 安德切尔, 泡普卡, 月见夜;
- GameData supplies activation type, SP type, initial SP, SP cost, duration, and
  blackboard value;
- `LowRarityBlackboardEffectInterpreter` converts this one pattern to the existing
  synthetic `atk_multiplier=1+x` effect.

This mapping is visibly `EXECUTABLE_APPROXIMATED`, not a general GameData skill
interpreter or a claim about all client buff ordering. It makes the real manual
`ACTIVATE_SKILL` action useful in the runtime architecture. Auto attack-recovery
skills (克洛丝/史都华德), DP skills (芬/香草), ASPD (炎熔/翎羽/梓兰), DEF (米格鲁),
range/healing/multi-target patterns, and active talents remain unsupported. Automatic
or passive mechanics never emit a fake external `ACTIVATE_SKILL`.

See [LOW_RARITY_MECHANICS.md](/home/bigdata/Desktop/arknights-auto-planner/docs/LOW_RARITY_MECHANICS.md).

### Chapter 6–11 benchmark suite

The selected bounded suite is `6-1`, `6-2`, `7-2`, `7-3`, `R8-1`, `R8-2`, `9-2`,
`10-2`, and `11-1`, grouped A/B/C for increasing route/wave/topology pressure. The
local source resolves detailed map/route/wave/enemy structures for the six Chapter
6–8 candidates. The selected Chapter 9–11 metadata exists but corresponding level
payloads are absent in this snapshot, so geometry is reported unknown rather than
invented.

Every selected benchmark is currently **BLOCKED**: the approximate adapter deliberately
converts only 0-1, and there is no explicit per-stage range-transform, tile mapping,
spawn hierarchy, or enemy-mechanics policy. `arknights-plan benchmark-search 6-1`
persists `compatibility.json` and stops without simulation. Thus there is no M10 real
benchmark WIN, no minimum-squad claim, and no human candidate timeline to falsify.
This is the correct result under strict provenance rules. The detailed matrix is in
[BENCHMARKS.md](/home/bigdata/Desktop/arknights-auto-planner/docs/BENCHMARKS.md).

### Human validation and timeline output

`FrameTimeline` remains the only planner execution artifact. `arknights-plan
human-timeline <timeline.json>` renders canonical tile coordinates plus localized
directions `↑ 上`, `↓ 下`, `← 左`, `→ 右`; it includes a derived seconds display only
when the FrameClock permits it and never prints screen/pixel/gesture coordinates.
`arknights-plan validate <timeline.json> --pass|--fail|--inconclusive --output ...`
stores a `HumanValidationRecord` (`UNTESTED`, `PASS`, `FAIL`, `INCONCLUSIVE`) with
optional bounded failure categories/frame/note. Importing a failure is evidence only:
it never adjusts simulator parameters.

### Validation and blocker

Focused tests cover source rarity normalization, census filtering/classification,
real-skill source extraction/interpreter/runtime activation, lexicographic priorities,
redeployment counting, direction rendering, no-pixel test sheets, validation round
trips, stage compatibility, blocked-search artifacts, and cardinality-first stopping.
The low-rarity and stage census commands were run locally; `benchmark-search 6-1`
produced an explicit blocked compatibility artifact.

```text
93 passed, 1 skipped (explicit device integration)
```

The single most important blocker exposed by M10 is not team search: it is the lack
of an explicit, source/provenance-visible real-stage adaptation policy beyond 0-1
(especially directional range, spawn timing, tile semantics, and enemy mechanics).
Until one selected Chapter 6–11 stage has that bounded policy, a low-rarity simulated
clear would be fabricated rather than a useful human-validation candidate.

## Milestone 11 — First Meaningful Chapter 6–11 Minimum-Squad Planning Benchmark

Status: **completed (bounded, honest `NO_WIN_FOUND`)** on 2026-09-15.  M11 did not
equate chapter number with difficulty.  It orders ordinary Main Story records inside
each chapter and classifies their local progression position as EARLY/MID/LATE before
structural inspection.  `NORMAL` is preferred deterministically over same-code EASY
or TOUGH variants; this fixed the earlier Chapter 9–11 code-resolution ambiguity.

### Final target correction

The first draft selected `7-4`, but the implemented deterministic within-chapter
census correctly classifies it as EARLY. M11 therefore uses **6-8** (`main_06-07`),
which is MID within Chapter 6, as its final primary target. It has an 11×8 map, 25
routes, three fragments, 22 SPAWN actions, initial DP 10, deployment limit 8, and
the three level-0 enemy references `enemy_1064_snsbr`, `enemy_1065_snwolf`, and
`enemy_1066_snbow`. `docs/BENCHMARKS.md` is the authoritative final selection and
result matrix; older prose in this historical section about 7-4 is superseded.

6-8 is `APPROXIMATE_READY`: source map coordinates are converted to canonical
bottom-left `(x=col, y=height-1-row)`; route checkpoint type/time are retained; and
wave/fragment/action timing is explicitly second-quantized. Snowcast Shooter's
source `rangeRadius=1.9` is applied only under the visible
`SOURCE_RANGE_RADIUS_NEAREST_OPERATOR` policy. Its nearest-target choice and
Euclidean grid geometry are approximations, not recovered client targeting.

The bounded phase-0 level-40 芙蓉/米格鲁/克洛丝/玫兰莎 search used 1–3 operators,
two placements/operator, frames `(0,180,360,540)`, beam width 2, `dt=0.2`, and a
300-second cap. It produced `NO_WIN_FOUND` after 14 teams, 342 strategies, 102
unique simulations, and 240 cache hits. There is no FrameTimeline, human candidate,
or validation record because none would be credible from a loss. Lower cardinalities
and rarities are not claimed exhausted because multi-operator beam prefixes are
pruned.

### Selection and source interpretation

The MID/LATE funnel shortlisted `7-4`, `7-5`, `6-8`, `7-10`, and `10-8` from local
GameData.  `7-4` (`main_07-03`) was selected: it is Chapter 7 MID, has an 11×7 map,
63 route records, one wave with nine fragments and 56 SPAWN actions, initial DP 10,
deployment limit 8, ordinary MELEE/RANGED/NONE tile categories, and only two
level-0 enemy references.  It has meaningful sustained multi-route pressure without
a boss, teleport tile, ritual entity, or enemy family whose listed conditional buff
is active in this stage.

Canonical planner coordinates are now `(0,0)=bottom-left`, `+x=right`, `+y=up`.
The serialized top-row-first tile matrix and route `row/col` MOVE positions share
one source-derived conversion: `(x=col, y=height-1-row)`.  Route checkpoints now
retain `type`, `time`, and position instead of discarding the type.  In approximate
execution `WAIT_FOR_SECONDS` is an explicit `RouteWait` at the preceding reached
MOVE node; it is never fabricated as a turn toward its placeholder position.

`range_table.direction=1` and the client evidence establish that ranges are
direction-relative, but not the exact row/column rotation matrix.  M11 therefore
keeps the existing four-facing `SYNTHETIC_90_DEGREE_ROW_COL` implementation visibly
approximate.  The real raw cells remain preserved separately.

### Approximate stage policy and enemy semantics

M11 introduces `HIERARCHICAL_FRAGMENT_DURATION_SECOND_QUANTIZED`: source
wave/fragment/action pre-delays and repetition intervals produce a bounded
hierarchy-derived second, then the result is placed at that integer second's frame
zero under the configured 30-FPS FrameClock.  This is not a recovered client formula.
The original hierarchy remains on `StageLevelStructure`.  Its manifest also includes
`WAIT_FOR_SECONDS_AT_PREVIOUS_MOVE_NODE`, zero windup/recovery, instant projectile,
the existing synthetic physical damage rule, and source-backed `costIncreaseTime` DP
generation.

The only primary-stage enemies are level-0 `enemy_1077_sotihd` (HP 2900, ATK 350,
DEF 150, RES 20, speed 1.9, attack interval 1.4) and `enemy_1078_sotisc` (HP 3300,
ATK 300, DEF 300, RES 20, speed 1.1, attack interval 2.0).  Numeric values are from
`levels/enemydata/enemy_database.json`; local `enemy_handbook_table.json` documents
the soldier's messenger/Patriot-dependent boost, but no such source enemy is present
in `7-4`.  No PRTS or APK mechanic was required for this specific bounded decision.

### Search and result

`M11MinimumSquadSearch` separates the fixed low-rarity team set from staged timeline
search.  It enumerates 1, then 2, then 3 used operators; within each fixed team it
generates only legal tile-kind-compatible, route-covering DEPLOY options and coarse
integer frames.  The simulator supplies the dense beam ordering, but final winning
selection remains `StrategyObjective`'s hard `WIN` then lexicographic count/rarity/
fragility/action-count/duration order.  Cache identity includes stage, exact operator
keyframes, normalized frame actions, simulation config, approximation policy, and
FrameClock identity.

The selected phase-0 level-40 pool was 芙蓉, 米格鲁, 克洛丝, and 玫兰莎.  A bounded
run used frames `(0,180,360,540)`, two spatial options/operator, beam width two, and
`dt=0.2`, maximum 300 seconds.  It generated 14 teams and 342 candidate strategies;
102 unique simulations and 240 cache hits yielded **NO_WIN_FOUND**.  Since the beam
prunes multi-operator prefixes, lower cardinalities/rarities are **not exhausted**;
there is no minimum-squad claim, no exported FrameTimeline, and no `PASS`/`FAIL`
validation record.  The appropriate human-validation state is therefore *not yet
applicable*, not an inferred simulator pass.

The principal blocker exposed by this benchmark is the current physical-only,
single-target low-rarity combat approximation under sustained 7-4 pressure.  The
most important discrepancy to watch once a viable candidate exists is the combined
error from hierarchy-derived spawn seconds, configured (not recovered) frame rate,
and zero-windup/instant-projectile timing.  STRICT_REAL remains unchanged and still
refuses unresolved mechanics.  No Agent/LLM, ADB/OCR, UI automation, or game control
was added.

### Validation

Focused M11 tests cover NORMAL stage-variant choice, canonical bottom-left map and
route conversion, retained wait checkpoints, deterministic second-quantized spawn
conversion, policy manifest visibility, and the bounded cardinality search's honest
`NO_WIN_FOUND` result.  A direct local CLI run produced
`output/m11/main_07-03/search_summary.json` with the above metrics.

The virtual environment currently lacks `pytest`; a normal dependency installation
attempt was blocked by unavailable package-index DNS and the privileged retry was
rejected by the approval service.  Source compilation and deterministic local
adapter/search smoke runs succeeded, but the full pytest regression suite could not
be executed in this session.
## Milestone 12 — full low-rarity pool (bounded)

Recomputed from local GameData: 34 eligible obtainable 1–3★ operators.  The
production M12 adapter no longer uses the M11 four-operator list; it constructs
an exact-keyframe phase-0 pool from the census.  A deterministic loadout policy
selects the highest source keyframe available in phase 0 (no interpolation,
trust, or potential).  Coverage is explicit: 22 operators are executable by
the bounded basic runtime (global APPROXIMATE_REAL policies remain visible),
while 12 are `BLOCKED_BY_MECHANIC` due to active phase-0 talents or mechanics
outside the current interpreter.  Per-operator blockers are retained in the
census; unsupported optional skills are not silently executed.

Caster operators are now represented as ARTS output and use the simulator's
documented RES approximation; other attacks remain PHYSICAL.  This is a
reusable profession mapping and does not special-case IDs.  The strict real
compatibility gate is unchanged.

The new `arknights-plan m12-search 6-8` command evaluates the complete
executable census pool with bounded cardinality/beam budgets.  Default smoke
run: 315 unique simulations and 1280 cache hits, `NO_WIN_FOUND`; therefore no
minimum-cardinality or minimum-rarity claim and no fabricated timeline.  The
result artifact is `output/benchmarks/m12/main_06-07/search_summary.json`.

The benchmark loadout and support policy are documented in
`docs/LOW_RARITY_MECHANICS.md`.  Full pytest remains unavailable in this
environment (pytest/package index DNS unavailable); source compilation and the
deterministic full-pool adapter/search smoke run pass.  Next bounded step is to
add only target-driven reusable mechanics (likely Arts/skill/DP coverage) and
rerun 6-8; do not broaden the simulator or claim a win from this result.
## Milestone 14 — tactical hypothesis pilot

Added a small deterministic LLM boundary. `StageAnalysis` and
`TacticalRequirement` summarize 6-8 without raw JSON; operator context contains
only executable source-derived facts. `PlanHypothesis` is strictly validated
and grounded separately from simulation. `MockLLMRuntime` is the default;
`RealLLMRuntime` is opt-in, bounded by three calls, and reads only normal
environment configuration without printing or persisting credentials. No real
provider was configured or called. The mock pilot produced one accepted
hypothesis and two requirements, with artifacts under `output/m14/main_06-07/`.
No WIN or timeline is claimed; this is a scaffold for later bounded validation.

### M14.1 real-provider execution attempt

M14 previously used `MockLLMRuntime` because the CLI invocation did not pass
`--llm-real`. The explicit one-call real attempt was then made with
`--llm-real --max-llm-calls 1`. It stopped before any network request with
`REAL_LLM_BLOCKED_BY_ENVIRONMENT`: `OPENAI_API_KEY` is normally exposed to the
project process, but `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `ARK_MODEL_ID` are
absent. The existing runtime intentionally requires an explicit endpoint and
model rather than guessing either one; Codex authentication was not inspected
or reused. The generated `real_llm_call_summary.json` contains only
PRESENT/ABSENT metadata and the sanitized missing-configuration reason.

Consequently no real hypotheses, grounding, simulator pilot, revision, or
baseline comparison occurred. This is explicitly **not** evidence for or
against LLM-guided search. To execute the real pilot, expose a normal
OpenAI-compatible base URL and model identifier alongside the already present
key, then rerun the explicit CLI. Compilation, MockLLM smoke, real-runtime
blocked-path smoke, and a credential-pattern artifact scan pass; pytest remains
unavailable locally.

### M14.1 configured endpoint attempt

With the user-supplied `OPENAI_BASE_URL=https://api.cxsee.com/v1` and
`ARK_MODEL_ID=gpt-5.6-terra`, the project constructed `RealLLMRuntime` and ran
the requested one-call test. The sandboxed request returned
`ENDPOINT_ERROR: connection failed`. A scoped outbound retry request was then
rejected because the approval infrastructure itself returned HTTP 503 for the
provider route. No alternative endpoint, provider, or credential route was
attempted. Reasoning effort is `OMITTED`: this endpoint's optional compatibility
field was not established. M14.1 remains `REAL_LLM_BLOCKED_BY_ENVIRONMENT`:
zero parsed real hypotheses, zero grounded candidates, and zero real-pilot
simulator runs. This does not answer the LLM-guided-search research question.

A follow-up direct local-shell test removed ambiguity about the scoped approval
path: `curl -I https://api.cxsee.com/v1` failed with `Could not resolve host`,
and `getent hosts api.cxsee.com` likewise reported unresolved. This is a local
DNS failure before TCP, TLS, HTTP, or any authenticated request; no API key was
sent. The real experiment remains unexecuted until this shell can resolve the
configured host.

M14.1 timeout follow-up: `RealLLMRuntime` previously used a hard-coded
`timeout=45` seconds in `urllib.request.urlopen` (single timeout covering
connect/read). It now accepts `--llm-timeout-seconds` (default 45, host rerun
may use 300), records request start/elapsed time, and classifies timeout as
`TIMEOUT` with phase `READ_OR_CONNECT_UNKNOWN`; it is never relabeled as
endpoint or envelope failure. Python's stdlib transport does not expose
separate connect/read/write/pool phases, so that distinction remains explicitly
unknown.

### M14.1 response parsing follow-up

The provider's standard Chat Completions envelope is now handled explicitly.
Runtime URL construction is `<OPENAI_BASE_URL.rstrip('/')>/chat/completions`,
which yields exactly `https://api.cxsee.com/v1/chat/completions` for the supplied
base URL. Payload structure is `model`, two messages (`system`, `user`),
`temperature=0`, and explicit `stream=false`; no `response_format` or
speculative reasoning field is sent. The prompt requests only
`{"hypotheses":[...]}` JSON.

Added bounded diagnostics separating provider errors, missing/empty choices,
missing message/content, and content JSON syntax/schema failures. Offline
fixtures cover standard success, hypotheses envelope, provider errors, missing
layers, and plain/fenced/prose JSON. Compilation and secret scan pass. No
network request was made from the Codex sandbox; use the host-terminal command
provided by the user to run the real call.

### M14 hypothesis grounding experiment

The six accepted real hypotheses were preserved as immutable input in
`output/m14/main_06-07/real_initial_hypotheses.json`. Deterministic grounding
expanded them to 12 deduplicated teams (two per hypothesis), using only the 22
executable operators and highest-exact-keyframe loadouts. The bounded spatial
and coarse-timing evaluator produced 385 simulator evaluations, no wins, and
per-hypothesis `initial_failure_summary.json`; causes remain `UNKNOWN` where
the simulator did not expose evidence. `INITIAL_LLM_BEST` was LOSS with zero
kills in this bounded run. No revision LLM call was made; the evidence is
preserved for review before any second tactical prompt.

The existing M13 deterministic result remains the historical comparison
reference (236 unique simulations/318 cache hits, `BEST_FOUND_UNDER_BUDGET`);
this pass is not a quality claim because the grounding pilot did not produce a
comparable near-win diagnostic.

### M14.2 engagement audit

The zero-kill aggregate was caused by an aggregation bug, not universal lack of
combat engagement: `M11MinimumSquadSearch` returned `best=None` whenever no
WIN existed, discarding its best LOSS. The M14 result layer then defaulted
kills/engagement to zero. The search now retains the best non-winning evaluation
for diagnostics while preserving `NO_WIN_FOUND` and timeline gating.

Re-running representative grounded teams produced attack/damage evidence:
H1 13 attacks/13 damage/0 kills; H2 359/359/7; H3 54/54/1; H4 23/23/1
(second representative 214/214/4); H5 359/359/7; H6 13/13/0. Deployment
errors were empty. Thus the earliest causal break for H1/H6 is
`DAMAGE_INSUFFICIENT`, not deployment, range, or targeting; H2/H3/H4/H5
demonstrate target acquisition, damage, and enemy deaths. Cross-checks show
`SimulationResult.enemies_killed == ENEMY_DEATH event count` for these traces.
Artifacts: `output/m14/main_06-07/engagement_audit.json`,
`representative_traces.json`, and refreshed initial results/failure summary.

### M14.3 revision attempt

The revision command preserved the initial six hypotheses and failure summary.
A host-terminal execution then made one real revision call successfully:
`REVISION_CALL_SUCCEEDED`, four schema-valid hypotheses, a 300-second read
timeout, and 56.07 seconds elapsed. No credential was recorded.

The revision is not a valid M14 outcome yet. All four returned hypotheses have
target cardinality 6 or 7, while the deliberately small M14 pilot permits only
K<=3. The original grounder incorrectly clamped each requested cardinality to
3, so its reported eight grounded teams and 300 simulations tested unrelated
three-operator truncations. Those artifacts are preserved as historical output
but are invalid for comparing revised tactical quality.

Grounding now rejects out-of-scope cardinality rather than silently changing
the LLM proposal. `revised_scope_audit.json` records R1--R4 as rejected and
zero valid grounded teams under M14 scope. Consequently there is no honest
`REVISED_LLM_BEST`, no revision-vs-initial conclusion, and no additional LLM
call. The LLM evidence is only that its failure-guided revision inferred
cardinality pressure; that remains an unvalidated tactical inference, not a
reason to expand M14 to K=6/7.

### M14.4 bounded cardinality-pressure validation

M14.4 used the preserved R1--R4 revision artifacts and made **zero** LLM
calls. It introduced a separate `m14-cardinality-audit` command; ordinary M14
grounding remains K<=3. For each revision it tested only the original exact-K
team and one deterministic K-1 ablation, never a global K=3..7 enumeration.
LLM-supplied coordinates were not trusted: canonical route/range geometry
selected legal tile/facing candidates, while the hypothesis operator set,
capability intent, and deployment order were retained. All revision skill text
explicitly restricted this pass to basic attacks/healing; no skill or retreat
action was invented.

The first audit run found that top direction-ranked entries could be multiple
facings of the same tile, preventing a full formation from being grounded. The
fixed ordered-team evaluator now retains two **distinct-tile** options per
operator and rejects incomplete formations rather than treating a prefix as a
full-K result. The final bounded run grounded eight teams (R1/R2 exact K6 and
K5; R3/R4 exact K7 and K6), had no structural rejection, and used 352 unique
simulations (budget 500, cache hits 0). All complete deployments had their
requested action count.

`INITIAL_K<=3_BEST` was LOSS: 7/36 kills, 29 leaks, life -26. Exact R1 K6 and
R4 K7 each reached 19 kills and 17 leaks (life -14); R2 K6 reached 15/21, and
R3 K7 reached 14/22. Their K-1 ablations respectively reached 17/19, 7/29,
14/22, and 16/20. No candidate WON, no timeline was exported, and this did not
minimize cardinality or rarity. The limited simulator evidence classifies
**cardinality pressure as SUPPORTED**: two independent exact-K structures
improve both kill count and leaks over the initial K<=3 best. It supports only
the narrower conclusion that the current K<=3 pilot constraint prevents these
hypothesis-conditioned structures from reaching better simulator regions; it
does not show that stage 6-8 requires more than three operators.

Artifacts: `cardinality_audit_input.json`, `cardinality_grounded_teams.json`,
`cardinality_ablation.json`, `cardinality_results.json`, and
`cardinality_comparison.json` under `output/m14/main_06-07/`.

### M14.5 feasibility-first local repair

M14.5 made zero LLM calls and did not change cardinality. It froze the R1 K6
and R4 K7 revision structures, then ran a bounded local repair search (budget
1500) around their deterministic full-team groundings. The diagnostic ordering
for LOSSES was only leaks, kills, first leak, and life; it did not replace the
project's WIN-first lexicographic optimization contract.

Parent trace analysis found the first leak at frame 336 (11.2 seconds) in both
structures, before either parent had deployed a ground holder. R1's first
ground holder was frame 1110 and R4's was frame 1440. The first four wolf leaks
occur on routes 0, 2, 3, and 4 in the 10--19 second window; each had received
only 375--750 damage against source-backed 3150 HP. The first operator attack
was frame 222. The runtime does not emit rejected-block or coverage-state
events, so blocker overload and the first route-coverage loss remain `UNKNOWN`.

The repairer keeps an already successful prefix and mutates only deployment
actions at or near the earliest leak: adjacent and ground-first ordering,
frame shifts, alternate canonical tile/facing coverage, capability-equivalent
replacement candidates, and source-backed manual time-SP skills. It neither
trusts LLM coordinates nor creates unspecified retreat actions. A discovery
bug in its ordered skeleton search (multiple directions for one tile consumed
the small spatial option list) was fixed by keeping distinct-tile choices;
another frame-boundary bug was fixed by preserving exact `Fraction` frame
times rather than emitting float 1/30 values.

The final run generated 397 local candidates: 407 unique simulations total,
zero cache hits, and 82 rejected before simulation for deterministic legality.
Mutation candidates attempted/simulated were team 0/0, spatial 50/50, facing
1/1, order 118/118, timing 174/92, skill 54/54, retreat 0/0. The local
neighborhood exhausted after eight iterations (75 unique evaluations since the
last improvement), so it is recorded as `PLATEAU`, not budget exhaustion.

Progress was R1/R4 initial 19 kills/17 leaks/life -14; R1 ordering 20/16/-13;
then R4 ordering 25/11/-8 and 26/10/-7. The final best is R4 K7, 20 stars,
LOSS, 26/36 kills, 10 leaks, life -7, 367 attacks, 353 operator damage events,
first leak frame 336, and first operator death frame 3294. It adds one legal
`ACTIVATE_SKILL char_211_adnach` at frame 3300 to a ground-first formation.
There is no WIN, no robustness result, and no human timeline. The narrow
capability-pressure conclusion is `INCONCLUSIVE`: early route coverage remains
unrepaired, but this pass did not prove that another capability or another
operator is required.

Artifacts: `local_repair_input.json`, `leak_analysis.json`,
`local_repair_progress.json`, `local_repair_results.json`, and
`local_repair_plateau.json` under `output/m14/main_06-07/`.

### M14.6 opening-feasibility / early-leak repair

M14.6 made zero LLM calls, retained R4's fixed seven operators (20 stars),
and did not minimise the roster or add an eighth operator. It isolated the
opening through frame 900 (30 seconds), using exact modeled DP, route timing,
legal tile, and range-interaction checks before promoting six distinct opening
structures to full-battle evaluation.

The DP audit is concrete: 6-8 starts at 10 DP and gains 1 DP/s; Beagle and
Cardigan each cost 18 DP. Either can first deploy at frame 240. Once one spends
18 DP, the second cannot deploy until frame 780. The first route-0 wolf reaches
`(4,3)` at estimated frame 244 (four-frame margin for one blocker), while the
route-2 wolf reaches `(4,4)` at frame 274. These are separate rows, so both
cannot receive source-backed 18-DP blockers before their early arrival windows.

The preserved R4 prefix put Beagle at `(2,4)` at frame 240, leaving route-0
without blocker or ranged interaction before its frame-336 leak. Moving Beagle
legally to `(4,3)` at frame 240 proves that the first leak itself is
`PREVENTABLE_WITH_CURRENT_ROSTER`: it moves to frame 366. The fixed-R4 opening
search tested 88 candidates plus the preserved prefix (89 unique opening
simulations); its best had 3 leaks, 2 kills, 9,105 modeled operator damage, and
first leak frame 366. It found no zero-leak fixed-R4 opening.

The bounded evidence supports `opening_capability_pressure=SUPPORTED` for this
opening question only, not a stage-minimum claim. One exact-K substitution,
Stward (18-DP ranged Arts) → Noir Corne (7-DP block 2), retained Durin's Arts
role and reduced the best opening to 2 leaks, but did not clear both early rows.
It tested 154 further opening candidates. The total was 243 unique opening
simulations under the 500-evaluation budget, with no structural rejection or
cache hit.

The best promoted fixed-R4 full battle delayed first leak to frame 366 but
regressed to 22 kills/14 leaks/life -11. The preserved M14.5 baseline remains
the best full battle: 26/36 kills, 10 leaks, life -7, first leak 336. The best
single-substitution full battle was 24 kills/12 leaks/life -9. No candidate WON;
therefore no timeline, robustness result, or human-validation artifact exists.

Artifacts: `opening_failure_analysis.json`, `opening_dp_timeline.json`,
`opening_search_results.json`, `opening_progress.json`,
`promoted_full_battle_results.json`, and `opening_substitution_results.json`
under `output/m14/main_06-07/`.

### M14.7 opening-economy constrained roster repair

M14.7 made zero LLM calls, retained exactly K=7, and did not start
minimisation or add an eighth operator. It translated the M14.6 timing facts
into `EARLY_ROUTE_INTERACTION` requirements for route-0 by frame 244 and
route-2 by frame 274, then calculated source-backed opening signatures for all
22 executable low-rarity operators. No executable runtime skill currently
changes DP: this benchmark has only the explicit natural 1 DP/s economy.

The preserved 26-kill R4 trace was attributed per operator. Beagle (30,530
damage/9 kills/9 blocks), Cardigan (20,780/6/6), Kroos (12,040/3), Adnach
(19,442.5/3 plus one supported skill), Durin (5,100/3 Arts), and Ansel
(2,309 healing) are `PROTECTED` by observed contribution. Steward is the
evidence-directed `REPLACEABLE` slot: 4,653 damage and 2 kills, while Durin
already supplies the remaining supported Arts role.

One-slot repair considered all 15 non-R4 executable operators and structurally
filtered to eight lower-cost, blocking ground candidates. Every accepted
replacement received a newly scheduled opening search; no old R4 timeline was
reused. Across eight variants this used 384 opening and 17 full-battle unique
simulations (401 total, budget 1,000), with no structural rejection.

The best result replaces Steward with Plume (翎羽), retaining K=7 and 20 stars.
Its repaired opening uses Cardigan at `(4,3)` frame 240 and Plume at `(4,4)`
frame 540; it has 2 opening leaks, one opening kill, and first leak frame 366.
The full candidate is still LOSS but improves the preserved R4 frontier to
27/36 kills, 9 leaks, and life -6 (first leak 366; 376 attacks and 358 operator
damage events). This is a credible full-battle improvement, but it does not
solve the opening because Plume's 10-DP cost after the first 18-DP deployment
is not fieldable until frame 540. Therefore the two-slot phase was not run:
M14.7's explicitly bounded trigger permits it only when one-slot repair has no
credible opening/full-battle improvement.

`OPENING_ECONOMY_REPAIR=INCONCLUSIVE`: roster repair demonstrably improved the
full-battle frontier and delayed the first leak, but no tested K=7 one-slot
variant achieved zero opening leaks. There is no WIN, timeline, robustness
result, or human-validation artifact.

Artifacts: `opening_requirements.json`, `operator_opening_signatures.json`,
`r4_operator_contributions.json`, `one_slot_repair_results.json`,
`two_slot_repair_results.json`, `opening_economy_progress.json`,
`opening_economy_full_battle_results.json`, and `dp_acceleration.json` under
`output/m14/main_06-07/`.

### M14.8 opening geometry / shared-coverage search

M14.8 made zero LLM calls and held the M14.7 R4-with-Plume roster fixed at
seven operators and 20 stars. It did not add an operator, alter the roster, or
start minimisation. The opening horizon was frames 0--900, with the same
source-backed 10 initial DP and natural 1 DP/s model.

The route audit establishes that early route-0 and route-2 have no common
canonical tiles and no later convergence: they are adjacent, parallel rows
(`y=3` and `y=4`) continuing to different leak tiles, with minimum Manhattan
distance one. This is not equivalent to no shared interaction. Exact rotated
range geometry proves, for example, that Plume at `(2,3)` facing DOWN blocks
route-0 (first contact frame 212) while its range contains route-2 `(2,4)`
(first entry frame 242); a high-ground Kroos placement can also range-cover
both rows. Routes 3 and 4 repeat the same rows later in the opening. Thus a
single unit can interact with multiple early routes, but the current modeled
damage/blocking result did not make that interaction sufficient.

The bounded search evaluated all 152 structurally meaningful one-deployment
openings at their earliest legal DP frame, plus 317 geometry-ranked one-early
plus one-late-support structures. Forty legal placement/direction graph nodes
with no route interaction were rejected before simulation. This used 469
unique opening simulations (zero opening cache hits) and promoted six distinct
openings to full battle (six further simulations; 475 total under the 800
budget). The best single opening was Plume at `(2,3)` frame 0, facing LEFT:
3 opening leaks, 3 kills, 10,570 damage, first leak frame 366. The best
two-action opening reached the same 3 leaks/3 kills and frame-366 frontier
with 10,930 damage; no evaluated opening reduced leaks below three or delayed
the frontier beyond frame 366. Ranged-first singles were weaker (best 6
leaks, zero kills, frame 336), and no downstream delayed-interception
structure improved the frontier.

The best promoted full battle was LOSS with 24/36 kills, 12 leaks, life -9,
and first leak frame 366, below the preserved M14.7 best of 27/36, 9 leaks,
life -6, first leak 366. Therefore no opening prefix was verified, no WIN,
robustness analysis, human timeline, or validation record exists. The bounded
classifications are `SHARED_OPENING_GEOMETRY=NOT_SUPPORTED` (shared coverage
exists but did not prevent the early leaks), `RANGED_OPENING=NOT_SUPPORTED`,
and `DELAYED_INTERCEPTION=NOT_SUPPORTED`. Existing runtime state supports
source-backed block capacities and successful `BLOCK`/`UNBLOCK` events only;
rejected block attempts are not emitted, so
`BLOCK_CAPACITY_DIAGNOSTIC=SUPPORTED_SUCCESS_ONLY`.

Artifacts: `opening_route_geometry.json`, `opening_interaction_graph.json`,
`single_deployment_openings.json`, `ranged_opening_results.json`,
`delayed_interception_results.json`, `shared_opening_results.json`,
`promoted_geometry_full_battle_results.json`, and
`opening_geometry_metrics.json` under `output/m14/main_06-07/`.

### M14.9 opening-economy mechanics fidelity audit

M14.9 made zero LLM calls, ran no broad strategy search, did not alter the
fixed K7 feasibility experiment, and did not add an eighth operator. It audited
all 34 eligible low-rarity records for GameData `cost`/deployment-economy
effects, keeping the three distinct questions separate: data present, mechanic
semantics known, and runtime supported.

It found and implemented only three reusable source-backed patterns:
automatic time-SP instant `{cost}` DP gain, manual time-SP finite `{cost, atk}`
DP gain plus the existing approximate ATK mapping, and an active neutral-
potential self deployment-cost modifier whose description explicitly says
`自身部署费用`. This makes Fang's `skcom_charge_cost[1]` automatic six-DP skill,
Vanilla's `skchr_wyvern_1` manual six-DP skill, Fang's phase-1 cost -1 talent,
and Catapult's phase-1 cost -1 talent executable under `APPROXIMATE_REAL`.
Automatic activation remains internal; the external vocabulary is unchanged.
The approximation/cache identity was versioned to
`real-simulation-approximation-policy-v2-economy`. `STRICT_REAL` was not
changed.

Two current blocked records contain relevant DP source data but were correctly
left unsupported: CONFESS-47's first-block `cost=2` is coupled to sleep, and
Rhodes Island's Secret Squad `attack@cost=1` is coupled to limited delayed
explosion and stun. These remain explicit `DATA_PRESENT`, `SEMANTICS_KNOWN`,
`RUNTIME_SUPPORTED=false` mechanics rather than DP-only simplifications.

The post-audit economy is concrete. Fang has source cost 11, self-cost delta
-1, effective cost 10, and can deploy frame 0; its automatic six DP occurs at
frame 570. Vanilla costs 11 and can deploy frame 30; with initial SP 6 and
cost 20, its manual six DP is ready/activatable at frame 450. A fixed causal
6-8 check verifies that Fang frame 0 is illegal without its source cost talent
and legal with it; another verifies Vanilla's frame-450 DP event changes a
same-frame Beagle deployment from illegal to legal. No source-supported DP
gain arrives by the route-0/route-2 frame-244/274 deadlines, and two 18-DP
blockers remain frame 240 then 780. Accordingly
`OPENING_ECONOMY_FIDELITY_GAP=FOUND_BUT_NOT_MATERIAL`: a genuine economy
omission was fixed, but it does not resolve the observed initial two-route
deadline.

Artifacts: `low_rarity_economy_audit.json`,
`opening_economy_relevant_operators.json`, `dp_skill_interpreter_audit.json`,
`economy_mechanics_provenance.json`, `opening_dp_feasibility_after_audit.json`,
and `economy_mechanics_validation.json` under `output/m14/main_06-07/`.

## Milestone 13 — full-pool coverage and layered composition search

All 34 eligible 1–3★ records were audited with concrete blocker families. The
current reusable runtime supports 22 operators (all marked
`EXECUTABLE_WITH_APPROXIMATION` under the real-stage policy); 12 remain
`BLOCKED_BY_MECHANIC` for deploy-triggered effects, passive/aura modifiers,
crowd-control, or limited multi-target behavior. No operator is silently
omitted. `low-rarity-runtime-coverage` reports the complete machine-readable
table.

The benchmark loadout is now `M13_HIGHEST_LEGAL_EXACT_KEYFRAME`: highest legal
phase, highest exact GameData keyframe in that phase, highest available source
skill level, neutral trust/potential. No interpolation is guessed.
`low-rarity-loadouts` exports every selected profile.

Search was split into composition and tactical layers. For 22 executable
operators, K=1 composition coverage is 22/22 and K=2 coverage is 231/231
(100% at the composition layer). Tactical evaluation remains deliberately
bounded: K=1 tactical coverage 22/22, K=2 tactical coverage 80/231. The M13
6-8 smoke search used 236 unique simulations and 318 cache hits and returned
`BEST_FOUND_UNDER_BUDGET` with no winning timeline. This is not a minimum claim:
K=2 detailed timing is incomplete and K>=3 was not searched.

Team features (rarity, damage type, blocking, healing, cost) are used for
ordering only; no conventional role template is a hard constraint. Existing
M11/M12 commands and STRICT_REAL behavior are preserved. Compilation, complete
pool fixture construction, coverage/loadout CLI checks, and deterministic M13
search smoke pass. Full pytest remains unavailable because pytest/package
installation is not present and package-index DNS is unavailable.

## Milestone 15 — constraint-guided feasibility planner

M15 replaces the M14 fixed-roster/local-repair loop with a bounded, no-LLM
constraint-guided search on the existing 22 executable low-rarity operators.
It derives source-backed opening interaction constraints from canonical 6-8
geometry: route-0 must be interactable by frame 244 and route-2 by frame 274.
Those are hard DP-scheduling constraints. Failure-derived damage requests are
explicitly `DERIVED` and non-hard: a later reinforcement may address later
pressure but is never represented as preventing an already-observed leak.

The planner carries partial role assignments, concrete legal
operator/tile/facing choices, an exact DP schedule, and a frozen successful
prefix. One placement may satisfy both unresolved route constraints when its
canonical rotated range covers both corridors. Any repair changing a frozen
action is recorded as a prefix invalidation and re-simulated. The run used a
16-state beam, K<=7, and a 2,000-simulation ceiling; it did not enumerate
rosters or call an LLM.

The final bounded run executed 110 unique simulations (0 cache hits), with
3,184 placement assignments considered, 1,534 spatially infeasible choices
discarded before simulation, two DP-infeasible schedules, 22 prefix freezes,
and 10 prefix invalidations. It progressed from 3/33 to 7/29, 10/26, 16/20,
20/16, 24/12, and 27/9 kills/leaks for K=1..7. The independently constructed
final LOSS used seven operators (21 stars), killed 27/36 enemies, leaked nine,
had life -6, and retained a route-2 early-wolf `FailureFrontier` at frame 366.
It therefore `MATCHED`, rather than exceeded, the preserved M14 frontier. It
is not a WIN, minimum-cardinality, or minimum-rarity claim; no timeline,
robustness result, or human validation record was exported.

Artifacts: `m15_stage_constraints.json`, `m15_search_progress.json`,
`m15_failure_frontiers.json`, `m15_assignment_stats.json`,
`m15_prefix_history.json`, `m15_results.json`, and
`m15_baseline_comparison.json` under `output/m15/main_06-07/`.

### M15.1 closed-loop FailureFrontier repair

M15.1 used the preserved M15 K7/21-star LOSS (27/36 kills, nine leaks, life
-6, first frontier frame 366 on route-2) as its only parent. It made no LLM
call, mechanics change, roster-wide reconstruction, or minimization attempt.
The causal trace for that wolf is source/event-backed: it spawned at frame 120,
leaked at frame 366, received zero damage and zero attacks, and had Falco as a
geometrically capable but non-attacking deployment. The supported classification
is therefore `INTERACTION_TOO_LATE`, yielding the exact event constraint
`INTERACT_WITH_ROUTE_BEFORE(route-2, 366)`.

The bounded frontier-guided loop used 600 unique simulations; its small
unguided control used 200 and the same mutation primitives. Both found the same
K7/20-star LOSS: 24/36 kills, 12 leaks, life -9, and a route-2 frontier at
frame 564. At that new frontier the same wolf had received 2,031 damage across
six attacks, so the supported classification changes to
`DAMAGE_INSUFFICIENT`. Guided search recorded 12 local freeze/invalidation
transitions (the control recorded four), but it did not reach a later frontier
than the control. Accordingly `FAILURE_FRONTIER_REPAIR=NOT_SUPPORTED` for this
bounded comparison: the repair machinery can derive and advance a frontier,
but the current frontier-directed selection did not demonstrate an efficiency
advantage over the local control. No WIN, timeline, robustness result, or
minimum claim was produced.

Artifacts: `m15_1_initial_parent.json`, `m15_1_frontier_causal_trace.json`,
`m15_1_generated_constraints.json`, `m15_1_repair_progress.json`,
`m15_1_prefix_dependencies.json`, `m15_1_repair_level_stats.json`,
`m15_1_unguided_control.json`, `m15_1_results.json`, and
`m15_1_comparison.json` under `output/m15/main_06-07/`.

## PRTS basic-mechanics audit boundary

The simulator now exposes `arknights-data mechanics-audit`, which produces a
row for every requested basic mechanism with separate `prts_sources`,
`prts_evidence_status`, `project_status`, `implementation_locations`,
`prts_consistency`, and `gaps` fields. It explicitly distinguishes a missing
project implementation from an unknown game rule. The PRTS pages are now saved
locally at `data/prts/game-data-basics.html` and
`data/prts/battle-mechanics.html`. They explicitly document the four attribute
modifier phases, physical/Arts/elemental/true/healing formulas, attack-interval
formula, movement bounds, target priority, and the nine-step damage
Modifier/伤判 event order. Formula helpers in `simulator/combat_rules.py` now
implement the source physical/Arts minimum-damage and penetration formulas plus
the source attack-speed conversion. The audit also found a concrete conflict in
the prior synthetic ATK composition: it applied multiplication before additive
ATK. That path now uses PRTS direct-addition then direct-multiplication order.

The runtime remains intentionally partial: it lacks typed modifier collection,
source-order/event-order damage modifiers, true/elemental output mapping,
GameData-fed penetration/attack speed, shields/barriers/evasion, full targeting
priority, displacement, state resistance, and elemental state. PRTS documenting
a rule is recorded separately from whether this project implements it.

The formula change invalidates direct numerical comparison with the previous
M15.1 combat run. A fresh 600/200 M15.1 replay under the source formula layer
remained bounded LOSS at 27/36 kills, nine leaks, route-2 frame 366 in both
modes (`INCONCLUSIVE` at that small replay frontier); the preserved historical
M15.1 documents retain their original results rather than being relabelled as
PRTS-formula results.

### M15.2 quantified frontier-requirement repair

M15.2 used the current PRTS-backed runtime and preserved M15.1 K7 parent with
no LLM call, mechanics expansion, cardinality change, or minimization. The
route-2 frame-564 trace is six physical hits totalling 2031 damage, leaving
1119 HP on `enemy_1065_snwolf#1`; this remainder is candidate-specific, not a
global damage invariant. Fifty-one local candidates were generated, 37 were
rejected by DP/legality prechecks, and 37 unique full simulations ran (10
cache hits). Three candidates satisfied the route-2 requirement but recreated
an earlier route-0/route-3 frontier. The best remained LOSS 24/36 kills,
12 leaks, life -9 at frame 564. Thus
`FRONTIER_REQUIREMENT_SOLVING=INCONCLUSIVE`; no WIN, infeasibility proof,
timeline, or minimum claim was produced. Artifacts are the nine
`m15_2_*.json` files under `output/m15/main_06-07/`.

### M15.3 multi-frontier/resource conflict solver

M15.3 preserved the M15.2 parent and three route-2-success counterexamples;
it used zero LLM calls, no mechanics expansion, K<=7, and no minimization.
Their route/frontier requirements and DP, tile, facing, timing, and coverage
resources were represented explicitly. The three counterexamples changed
Falco's opening placement/facing region: route-2 improved, while route-0,
route-3, or route-4 became exposed. This is derived coverage evidence, not a
claim of DP conflict. Seventy-one local repairs produced 72 unique simulations
and 77 cache hits. The best was LOSS 25/36 kills, 11 leaks, life -8, with the
route-2 frame-564 damage frontier still present. Both
`MULTI_FRONTIER_CONSTRAINT_SOLVING` and `RESOURCE_CONFLICT_ANALYSIS` are
`INCONCLUSIVE`; no WIN, infeasibility proof, or minimum claim was made.
Artifacts are `m15_3_*.json` under `output/m15/main_06-07/`.

### M15.4 Falco critical-resource decoupling audit

M15.4 used zero LLM calls, no mechanics expansion, K<=7, and no minimization.
It preserved the M15.2 parent and three route-2-success counterexamples and
audited `char_192_falco` as a shared ranged resource. Five unique bounded simulations
(with six cache hits across repeated controls)
covered the parent, counterexamples, remove-Falco controls, and the required
A/B/C original, route-2-specialized, and decoupled-assignment comparison.
Falco contributed observed damage on routes 0, 2, 3, 5, 7, and 10; the
counterfactual evidence was insufficient to prove a decoupling or overload
claim. A remained the best bounded result (LOSS 24/36 kills, 12 leaks); B and
C were losses with earlier route-0/3/4 exposure. Therefore
`CRITICAL_RESOURCE_DECOUPLING=INCONCLUSIVE`,
`CRITICAL_RESOURCE_OVERLOAD=INCONCLUSIVE`, and
`K7_CARDINALITY_PRESSURE=INCONCLUSIVE`. No WIN, timeline, or minimality claim
was produced. Artifacts are the ten `m15_4_*.json` files under
`output/m15/main_06-07/`.

### M16 causal combat / non-monotonicity audit

M16 replayed the exact M15.2 parent twice with an isolated Falco-damage
intervention. Isolation was VERIFIED. Falco enabled: LOSS 24 kills, 12 leaks,
life -9. Falco damage disabled: LOSS 26 kills, 10 leaks, life -7. Event streams
diverged at frame 210; later target/attack allocation and enemy kill timing
changed. B-only kills included `enemy_1065_snwolf#1`, `#3`, and
`enemy_1064_snsbr#8`; an A-only kill (`enemy_1065_snwolf#2`) was exchanged,
for a net +2 kills, with three leaks prevented. The evidence supports
TARGET_SELECTION_NON_MONOTONICITY and ATTACK_ALLOCATION_NON_MONOTONICITY;
the local-damage monotonicity assumption is UNSAFE. No mechanics or planner
changes were made. Artifacts are under `output/m16/main_06-07/`.

### M17 causal-temporal constraint representation

M17 added a representation layer over M16 evidence without search, LLM calls,
mechanics expansion, or K changes. Twenty changed enemy outcomes became
provenance-bearing causal-temporal constraints with 19 interference relations.
The route-2 point damage requirement was upgraded to a candidate-specific
do-not-leak constraint preserving target-allocation context. A→B Falco
suppression is UNKNOWN for local safety; B→A damage restoration is UNSAFE, so
more local damage is not automatically beneficial. Representation and
safe-intervention checking are SUPPORTED. Artifacts are under
`output/m17/main_06-07/`.

### M18 targeting mechanics fidelity closure

M18 audited only target selection/aggro behavior against the local PRTS
snapshot and added serialized `TARGET_SELECTION` diagnostics at the runtime
decision point. Current selection uses covered active enemies by route progress
and spawn-index tie break; broader PRTS aggro/filter semantics and retention
remain unresolved, so `TARGETING_FIDELITY=PARTIALLY_ALIGNED`. The exact M16
Falco replay remains 24/12 versus 26/10; `M16_CAUSAL_RESULT=PRESERVED` and
`M17_CAUSAL_REPRESENTATION=STILL_SUPPORTED`, with mechanics sensitivity
explicit. No search, LLM, unrelated mechanics expansion, K change, or
minimization occurred. Artifacts are under `output/m18/main_06-07/`.

### M18.1 targeting uncertainty boundary

M18.1 classified causally relevant M16 target decisions without search or
network access. Of 50 retained decision differences, 45 are unresolved and
targeting-sensitive. M17 constraints/interference are marked sensitive where
connected to those decisions. The gate is
`READY_WITH_UNCERTAINTY_GUARD`: future repairs may not analytically assume
extra damage preserves target allocation; UNKNOWN interventions must go to
simulation. No new counterfactual replays were run.

### M19 uncertainty-guarded causal repair search

M19 ran a bounded no-LLM repair pilot under the M18 uncertainty guard. Three
Falco-local interventions were generated and classified UNKNOWN because of
targeting-sensitive context; four unique simulations routed them through the
simulator rather than hard rejection. The best state was LOSS K7, 25 kills/11
leaks with the route-2 frame-564 frontier, matching the prior M15.3 frontier.
`UNCERTAINTY_GUARDED_CAUSAL_SEARCH=SUPPORTED` for the guard behavior only;
there is no WIN or infeasibility claim. Artifacts are under
`output/m19/main_06-07/`.

### M20 constraint-to-capability intervention synthesis

M20 generated evidence-backed capability requirements for the route-2 frame
564 frontier, indexed 12 deterministic providers from the existing pool, and
produced 10 semantically distinct intervention candidates across five
families. No broad search, LLM call, mechanics expansion, K change, or
minimization occurred; validation remained analysis-only. All candidates were
UNKNOWN under the targeting guard and therefore simulation-eligible. Results:
`CONSTRAINT_TO_CAPABILITY=SUPPORTED`, `CAPABILITY_TO_INTERVENTION=SUPPORTED`,
`INTERVENTION_DIVERSITY=SUFFICIENT`.

### M21 information-efficient causal search

M21 connected M20 semantic interventions to a bounded closed-loop pilot under
the M18.1 uncertainty guard. Eight unique simulations evaluated a diverse
queue spanning five intervention families; targeting-sensitive candidates
remained UNKNOWN and were sent to simulation. No frontier advance or WIN was
found; the best remained LOSS 25/36 kills, 11 leaks, route-2 frame 564. The
guarded pipeline is `SUPPORTED` as an information-routing mechanism, but the
causal frontier was not improved. Artifacts are under
`output/m21/main_06-07/`.

### M22 frontier feasibility decomposition

M22 froze route-2@564 and decomposed feasibility diagnostically. The frontier
shows five attacks and 1,160 damage with sublethal HP; attack count and
damage-per-attack are insufficient, while target allocation remains UNKNOWN
and mechanics-sensitive. No legal strategy or oracle replay was generated.
The diagnostic explanation is `{ATTACK_COUNT, DAMAGE_PER_ATTACK}` with
protected-context preservation UNKNOWN. The frontier is
`MULTI_FACTOR_CONSTRAINED` and `TARGETING_UNCERTAINTY_CONSTRAINED`; real-game
calibration is recommended because unresolved allocation affects multiple
families. Artifacts are under `output/m22/main_06-07/`.

### M23 target-allocation black-box calibration — Phase A

M23 generated a human-in-loop calibration packet from the highest-impact
M18.1/M22 unresolved decisions. Three questions cover Falco first-target
selection, Noir Blade first-target selection, and Falco retargeting after target
death/exit. No observations were fabricated, targeting behavior was not
changed, and no search was run. Status:
`WAITING_FOR_REAL_GAME_OBSERVATION`.

### M18 targeting path-distance correction rebaseline

The local PRTS 仇恨 page was cached and ordinary target ordering was corrected
from route-progress ordering to remaining route/path distance with creation-order
tie breaking. No full aggro system was implemented. The corrected paired replay
was A 15/21 and B 19/17 (Falco enabled/disabled), so historical M16 24/12 vs
26/10 is `CHANGED`; non-monotonicity still survives. Target retention, special
filters, and exact aggro weighting remain unresolved; M23 Q1–Q3 still require
real-game calibration. Artifacts are under
`output/m18_rebaseline/main_06-07/`.

Q1 was subsequently re-evaluated at the concrete decision context rather than
from global fidelity: the candidate set has a unique minimum remaining path
distance, so `Q1=RESOLVED_BY_PRTS`. Q2 remains a real-game question because the
ordinary melee/blocked selector is not established; Q3 remains a real-game
question because retarget timing is not established. M23 Phase A is therefore
reduced to Q2/Q3 observation needs.

## Architecture restoration — top-down planner and evidence gates

The long M15-M22 causal-debugging sequence was re-audited against the original
planner contract. The project retained the useful frontier/causal abstractions,
but restored a explicit top-down control loop in
`src/arknights_planner/search/top_down.py`:

```text
StageAnalysis
  -> TacticalRequirements
  -> deterministic PlanHypothesis
  -> operator assignment
  -> spatial skeleton
  -> timing search
  -> Simulator
  -> WIN objective/minimization or scoped concrete-candidate repair
```

M15-M22 failure-frontier, causal-temporal, uncertainty, and capability tools
are supporting repair layers. They are not the primary hypothesis generator and
are not imported by the top-down loop.

Experimental restrictions moved behind
`src/arknights_planner/search/scope.py:ExperimentScope`. Stage 6-8, the
bounded 1-3 star pool, and K<=7 are benchmark scope, not global planner
properties. Scoped `NO_WIN` conclusions must continue to carry stage, pool,
cardinality, budget, search policy, and mechanics version.

`MechanicsEvidenceRegistry` became a retrieval/provenance layer with source
trails, concrete-context resolution, conflict exposure, mechanics-version
fields, UNKNOWN, mechanics-work, and human-calibration gates. A global partial
fidelity state no longer automatically makes a concrete decision UNKNOWN.

The cached `作战机制/sandbox` evidence resolves Q2: ordinary melee units
prioritize enemies they personally block, even outside normal range. This was
implemented and the active mechanics version became
`m18.2-blocked-target-v1`. Remaining route/path distance and stable creation
order are preserved. Q3 remains partially resolved because exact retarget
timing is not documented locally.

All M14-M23 numerical artifacts are historical under the active version. No
current 6-8 baseline or frontier exists until deterministic replay. A tiny
non-LLM stage 0-1 top-down smoke obtained a simulator WIN within its explicit
24-simulation scope; this proves orchestration only, not real-game validity or
minimality.

Audit artifacts are under `output/architecture_alignment/`. The next priority
is a deterministic 6-8 rebaseline and then an end-to-end first simulator WIN
through the top-down pipeline, not another narrow causal milestone.

## Top-down semantic cross-stage validation

Status: **completed on 2026-09-30**. No real LLM, broad Chapter 6-11 search,
M23 Phase B, human calibration, K8 expansion, minimization, or causal repair
was run.

The validation harness was added in
`src/arknights_planner/search/top_down_validation.py` and exposed through the
`top-down-validation` CLI command. It scans ordinary Chapter 6-11 GameData
stages, rejects unsupported tile effects, and selects three deterministic
categories without consulting historical artifacts. From 97 raw candidates,
29 stages were structurally loadable under the current tile allowlist and 48
were rejected for unsupported tile effects.

Selected suite:

| Category | Stage | Structure |
| --- | --- | --- |
| `SIMPLE_SINGLE_LANE` | `main_11-17` / `11-19` / `直指命运` | 7 active routes, 1 lane, 10 spawns |
| `MULTI_LANE_PRESSURE` | `main_11-12` / `11-14` / `一场相见` | 13 active routes, 2 lanes, 31 spawns |
| `SHARED_RANGED_COVERAGE` | `main_09-14` / `9-16` / `突围` | 27 active routes, 1 lane, 47 spawns |

Each stage ran the same GameData → StageUnderstanding →
TacticalRequirements → PlanHypothesis → OperatorAssignment → SpatialSkeleton →
TimingSearch → Simulator path with a 60-simulation smoke budget. Semantic
signatures, tactical requirement signatures, and full plan-hypothesis
signatures were distinct across all three stages. The primary planner modules
are stage-agnostic. Overall cross-stage generality remains `PARTIAL` only
because historical M14-M23 repair modules retain experiment-scoped literals;
they are not imported by the primary loop.

Status:

```text
GAME_UNDERSTANDING_LAYER = SUPPORTED
TACTICAL_REQUIREMENTS_GROUNDED = YES
PLAN_HYPOTHESES_STAGE_SPECIFIC = YES
TOP_DOWN_FAILURE_REVISION = SUPPORTED
OPERATOR_ASSIGNMENT_CAPABILITY_BASED = YES
CROSS_STAGE_TOP_DOWN = SUPPORTED
RUNTIME_MECHANICS_GATES = INTEGRATED
CROSS_STAGE_GENERALITY = PARTIAL
```

The mechanics registry, UNKNOWN gate, mechanics-work gate, and
human-calibration gate were exercised in the normal `TopDownPlanner.run()`
path. Every stage returned `NO_MECHANICS_WORK_REQUIRED` and
`NO_HUMAN_CALIBRATION_REQUIRED`; Q3 was not researched merely for completeness.

### First meaningful WIN attempt

The selected candidate was `main_11-17` (`11-19`, `直指命运`) because it is a
real, nontrivial, supported, low-pressure single-lane stage. The explicit
scope used the 1-3 star benchmark pool, `max_cardinality=7`, and a
300-simulation budget. The attempt used 36 unique simulations and did not find
a WIN. Best result:

```text
team = char_503_rang, char_122_beagle, char_121_lava, char_209_ardign, char_208_melan
distinct operators = 5
total rarity = 14
result = LOSS
kills = 2
leaks = 8
remaining life = -6
operator deaths = 2
primary failure layer = OPERATOR_ASSIGNMENT_ISSUE
```

No local/causal repair simulations were consumed. This result is scoped and is
not evidence that K7 is impossible, K8 is required, the 1-3 star pool cannot
clear the stage, or the selected team is minimal.

### Fresh 6-8 deterministic replay

The preserved 6-8 strategies were replayed read-only under
`m18.2-blocked-target-v1`. Four were reconstructible:

| Strategy | Result | Kills | Leaks | Life | Current first frontier |
| --- | --- | ---: | ---: | ---: | --- |
| `M14_7_BEST` | LOSS | 21 | 15 | -12 | route-2, frame 366 |
| `M15_BEST_PARENT` | LOSS | 20 | 16 | -13 | route-2, frame 366 |
| `M15_1_GUIDED_BEST` | LOSS | 15 | 21 | -18 | route-3, frame 486 |
| `M15_1_CONTROL_BEST` | LOSS | 15 | 21 | -18 | route-3, frame 486 |

`M13_BEST_HISTORICAL` remains unavailable because its strategy was not
persisted. The current representative replay is `M14_7_BEST`, fingerprint
`4a25f7f0e450bdacdd22137ac0c259c7694d88bdf8e60487ba656d8763b9e573`. These
replays are current numerical baselines only; they are not WIN or feasibility
claims. Historical frontiers and causal constraints must not be reused without
this mechanics version and replay provenance.

### Validation

`compileall` passed. Direct deterministic regression results:

```text
architecture = 13/13 PASS
top-down semantics = 10/10 PASS
mechanics rebaseline = 3/3 PASS
simulator runtime = 23/23 PASS
total direct = 49/49 PASS
0-1 approximate-real WIN regression = PASS
three-stage top-down smoke = PASS
secret scan = PASS (no credential values found)
pytest = BLOCKED (module unavailable)
```

All artifacts are under `output/top_down_validation/`. The next session should
improve the top-down assignment/hypothesis-revision layer and pursue the first
meaningful real-stage simulator WIN. It should not automatically resume
route-2@564 repair, Q3 research, M23 Phase B, or broad search.

## Operator Assignment Recovery — Round 2

Status: **completed on 2026-09-30**. This session diagnosed the first attempt's
36-of-300 funnel collapse, strengthened capability coverage, and ran exactly one
additional bounded round-2 attempt. No real LLM, K8 expansion, minimization,
M23 Phase B, local repair, 6-8 repair, additional mechanics work, or human
calibration request was used.

### Previous 36-of-300 funnel diagnosis

The earlier `OPERATOR_ASSIGNMENT_ISSUE` classification was incomplete. The
funnel collapsed from several directions:

- only three of six hypotheses completed a spatial skeleton;
- the old assignment generator produced a small preferred team plus a few
  substitutions rather than capability-coverage alternatives;
- `R-EARLY-DEPLOY` and `R-SINGLE-LANE` were recorded as HARD;
- HARD requirements were incorrectly recorded as independently satisfiable;
- useful placement options frequently differed only by direction on the same
  tile and then collided;
- timing used only offsets zero and 90;
- 36 generated simulations were accompanied by 36 cache hits.

Root cause:

```text
PREVIOUS_36_OF_300_ROOT_CAUSE = MIXED
```

### Capability coverage model

`src/arknights_planner/search/operator_assignment.py` now represents:

- one operator covering multiple requirements;
- multiple operators jointly covering one requirement;
- primary and secondary capabilities;
- spatial, coverage, timing, DP, and skill conditions;
- SOFT/HYPOTHESIZED gaps as ranking evidence rather than deterministic
  rejection.

Examples include Noir Corne covering early deployment and blocking, 12F
covering ranged DPS and Arts damage, Orchid covering ranged DPS and shared
coverage, and two blockers jointly providing block capacity.

After the recorded round-2 run, the requirement semantics were corrected:
early deployment and single-lane blocking are HYPOTHESIZED, not proven HARD
constraints, and no requirement inherently consumes a dedicated operator slot.
This post-run correction was not re-searched.

### Round-2 result

Stage:

```text
main_11-17 / 11-19 / 直指命运
```

Explicit scope:

```text
operator pool = 1-3 star benchmark pool
max cardinality = 7
simulation budget = 300
mechanics version = m18.2-blocked-target-v1
```

Funnel:

```text
plan hypotheses generated       = 10
assignment archetypes           = 10
assignments reaching simulation = 10
spatial/timing candidates       = 88
unique full simulations         = 62
cache hits                      = 26
local repair simulations        = 0
```

Best result:

```text
hypothesis = arts_interception-coverage
team = char_284_spot, char_009_12fce
distinct operators = 2
total rarity = 5
result = LOSS
kills = 3
leaks = 7
remaining life = -5
operator deaths = 0
```

No WIN was found. This is a bounded scoped failure, not an infeasibility claim.

### Current bottleneck

Assignment starvation was largely resolved: all ten semantic assignment
archetypes reached simulation. The primary remaining bottleneck is spatial
skeleton/timing candidate starvation:

- one five-operator ground-heavy hypothesis generated eight candidates and
  failed to complete a skeleton;
- many operators still have only two distinct useful tiles;
- beam width remains one;
- timing offsets remain zero and 90;
- 88 generated candidates collapsed to 62 unique simulations.

```text
CURRENT_PRIMARY_BOTTLENECK = SPATIAL_SKELETON_STARVATION
```

High-level failure-driven hypothesis revision remains `PARTIAL`: diverse
hypotheses are generated before simulation and local repair is deferred, but a
concrete policy that transforms an observed failed hypothesis into a structurally
different next hypothesis is not yet implemented.

### Validation

```text
compileall = PASS
architecture regressions = 13/13 PASS
top-down semantic regressions = 10/10 PASS
mechanics rebaseline regressions = 3/3 PASS
simulator regressions = 23/23 PASS
operator assignment recovery regressions = 8/8 PASS
total direct deterministic regressions = 57/57 PASS
0-1 approximate-real WIN regression = PASS
secret scan = PASS (no credential values found)
pytest = BLOCKED (module unavailable)
```

Artifacts are under `output/operator_assignment_recovery/`. The next externally
approved step should address spatial/timing candidate generation and high-level
hypothesis revision. It should not automatically resume 6-8 repair, Q3 research,
local causal repair, or another mechanics milestone.

## 2026-09-30 spatial/timing recovery

The read-only spatial funnel audit confirmed that the previous round did not
starve at random action enumeration. It starved at semantic realization:
`M11MinimumSquadSearch._build_options()` retained only eight options per
operator, direction variants consumed those slots, one tile often dominated the
ranking, the old fixed-team search used beam width one, and timing was limited
to approximately zero and 90 frames.

The new `SpatialTimingSearch` separates the problem into:

```text
tactical region
  -> legal tile + facing
  -> semantic spatial skeleton
  -> event-relative timing
  -> exact DP legality
  -> complete-strategy simulator evaluation
  -> bounded timing refinement
```

Important corrections:

- high-ground tactical regions now filter to `tile_kind == HIGH_GROUND`;
- Pareto ranking correctly removes dominated rows instead of duplicating the
  first front;
- per-tile and per-operator caps preserve distinct useful positions;
- facings are deduplicated by covered-cell signature;
- skeleton fingerprints preserve region, role, route coverage, block relations,
  and facing;
- timing uses bounded event anchors rather than every-frame enumeration;
- the DP gate checks initial DP, accumulation, cumulative cost, ordering,
  operator/tile uniqueness, tile kind, and deployment limit;
- the first-WIN path no longer simulates partial prefixes or discards all but
  one spatial path after each deployment.

The one bounded attempt on `main_11-17` (`11-19`) generated:

```text
plan hypotheses              = 10
tactical regions             = 6
raw tile candidates          = 1096
retained tile candidates     = 136
facing signatures retained   = 114
semantic skeletons           = 30
event-relative timing        = 180
DP rejections                = 0
coarse unique simulations    = 49
refined unique simulations   = 21
total unique simulations     = 70 / 300
```

Best scoped result:

```text
hypothesis = arts_interception-coverage
team = char_284_spot, char_009_12fce
distinct operators = 2
total rarity = 5
result = LOSS
kills = 3
leaks = 7
remaining life = -5
operator deaths = 0
```

This is not an infeasibility claim. Spatial/timing generation is structurally
healthy, but no hypothesis won. The current classification is:

```text
CURRENT_PRIMARY_BOTTLENECK = HIGH_LEVEL_HYPOTHESIS_LIMIT
HIGH_LEVEL_HYPOTHESIS_REVISION_NEEDED_NEXT = YES
HUMAN_CALIBRATION_REQUIRED = NO
```

Validation:

```text
compileall = PASS
architecture/top-down direct regressions = 40/40 PASS
simulator direct regressions = 23/23 PASS
0-1 approximate-real WIN regression = PASS
secret scan = PASS (no credential values found)
pytest = BLOCKED (module unavailable)
```

Artifacts are under `output/spatial_timing_recovery/`. The next external
decision should be high-level hypothesis or capability revision, not another
mechanics milestone, 6-8 local repair, Q3 research, K8 search, minimization, or
blind budget consumption.

## 2026-10-01 stage eligibility and first-WIN feasibility

The previous first-WIN benchmark was corrected after a semantic audit.
`main_11-17` / displayed `11-19` is fixed-squad, has preset deployed units and
forced operators, and is invalid for autonomous team selection. Its prior
`HIGH_LEVEL_HYPOTHESIS_LIMIT` result remains historical only.

The new `StageEligibilityAnalyzer` derives task-dependent eligibility from
GameData stage metadata and level options/predefines. The planner rejects an
ineligible feasibility-first stage before operator configuration, and the
cross-stage validator filters such stages. Deterministic regressions cover free
team acceptance, fixed-squad rejection, preset-unit rejection, unsupported
mechanics, internal/display mapping, task-dependent eligibility, planner gating,
the all-rarity executable pool, and validation filtering.

The selected valid benchmark is `main_01-01` / displayed `1-1`. It is a real,
nontrivial, supported two-lane stage with 33 spawns and deployment limit 8. The
feasibility scope used all 305 currently executable phase-zero basic-attack
operators, including 4-6 star operators, and did not perform rarity or
cardinality minimization.

The single bounded attempt used 22 of 500 unique full simulations and did not
find a WIN. The best result was a four-operator LOSS with 24 kills, 9 leaks, and
remaining life 1. The funnel did not exhaust budget; it collapsed:

```text
assignment alternatives        = 8
team-size distribution        = 2x5, 3x2, 4x1
5-8 operator alternatives     = 0
semantic skeletons            = 24
exact geometry signatures     = 8
coarse evaluations            = 144
coarse cache hits             = 128
coarse unique simulations     = 16
timing refinements            = 6
total unique simulations      = 22
DP rejections                 = 0
```

Current classification:

```text
CURRENT_PRIMARY_BOTTLENECK = MIXED
HIGH_LEVEL_HYPOTHESIS_REVISION_NEEDED_NEXT = UNCERTAIN
HUMAN_CALIBRATION_REQUIRED = NO
```

The mixed bottleneck consists of robust assignment generation, semantic spatial
duplicate collapse, and timing-anchor clamping. High-level hypothesis revision
should not be prioritized from this run until those candidate-realization
defects are repaired and retested. This is not an infeasibility claim.

Validation:

```text
compileall = PASS
stage eligibility regressions = 10/10 PASS
architecture/top-down/assignment/spatial/simulator = 63/63 PASS
0-1 approximate-real WIN regression = PASS
secret scan = PASS (no credential values found)
pytest = BLOCKED (module unavailable)
```

Artifacts are under `output/stage_eligibility_first_win/`.

## 2026-10-12 Roadblock navigation evidence

Current status:

```text
generic client chain          = CONFIRMED_FROM_CODE
roadblock prefab payload      = UNKNOWN
ordinary WALK navigation      = UNKNOWN
civilian/Talulah effect       = UNKNOWN
cross-version applicability   = UNKNOWN
targeted unit tests           = 12/12 PASS
Kimi calls                    = 0
real-stage simulations        = 0
```

Artifacts are under `output/r8_1_roadblock_navigation_evidence_v1/`.
