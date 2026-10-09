# Arknights Auto Planner

`arknights-auto-planner` is a research-oriented, **GameData-driven**, agent-assisted,
search-based approximate-simulation planner. It is not an exact Arknights emulator, a
game bot, or an RL agent. No real-game control is implemented.

## Current architecture

The primary planning loop is top-down: stage understanding, tactical
requirements, deterministic or explicitly opt-in LLM plan hypotheses, operator
assignment, spatial skeleton, timing search, simulation, then scoped repair.
Failure-frontier and causal-temporal tools are supporting repair layers.

Bounded experiments use `ExperimentScope`; stage, pool, cardinality, budget,
search policy, and mechanics version are explicit. A scoped `NO_WIN` is not a
global impossibility claim.

Mechanics uncertainty must pass evidence retrieval and concrete-context gates
before `UNKNOWN`, additional mechanics work, or human calibration is declared.
The active mechanics version is `m18.2-blocked-target-v1`.

## Stage eligibility and first-WIN feasibility

Autonomous team-selection experiments now pass through task-aware
`StageEligibility`. A stage is rejected before stage understanding when it has a
fixed squad, preset deployed units, forced operators, unavailable normal
deployment, tutorial/story semantics, or a known simulator blocker. Fixed-squad
stages can still be valid for timing-only or fidelity tasks; eligibility is task
dependent rather than a single global boolean.

This corrects the previous benchmark error: `main_11-17` / displayed `11-19` is
a fixed-squad, preset-unit stage and is invalid for autonomous roster selection.
The former `HIGH_LEVEL_HYPOTHESIS_LIMIT` diagnosis from that stage is preserved
as historical evidence but is not carried forward as a current planner result.

The first valid feasibility-first benchmark is `main_01-01` / displayed `1-1`.
It has free team selection, normal deployment, two active lanes, 33 spawns, and
no known unsupported mechanic. The experiment used all 305 currently executable
phase-zero basic-attack operators, including 4-6 star operators, with the stage
deployment limit of 8 and no rarity minimization.

The one bounded run used 22 of 500 allowed unique full simulations and did not
find a WIN. The best scoped result used four operators, with 24 kills, 9 leaks,
and remaining life 1. This is not an infeasibility claim. The current bottleneck
is mixed: no 5-8 operator assignment alternative was generated, 24 semantic
skeletons collapsed to eight exact operator/tile/direction geometries, and most
event-relative timings were clamped to the same earliest-DP vector. High-level
hypothesis revision remains uncertain until robust assignment and executable
candidate realization are repaired. No human calibration is required.

Artifacts are under `output/stage_eligibility_first_win/`.

## Spatial and timing recovery

The latest spatial/timing audit is under
`output/spatial_timing_recovery/`. `SpatialTimingSearch` now generates tactical
regions, Pareto-diverse legal tile candidates, facing-aware coverage, semantic
skeletons, event-relative timing anchors, and exact DP legality checks. The
first-WIN path evaluates complete strategies rather than partial beam prefixes.

The bounded attempt on `main_11-17` (`11-19`) generated 6 tactical regions,
1,096 raw tile candidates, 136 retained tile candidates, 30 semantic skeletons,
and 180 event-relative timing candidates. It used 70 of 300 allowed unique
simulations: 49 coarse and 21 locally refined. No WIN was found; the best scoped
result remained a two-operator LOSS with 3 kills, 7 leaks, and life -5. This is
not an infeasibility claim.

Spatial/timing starvation is no longer the primary bottleneck. Failure persisted
across all 30 skeletons and all ten tactical archetypes, so the next external
decision should consider high-level hypothesis or capability revision. Do not
automatically resume 6-8 repair, Q3 research, local causal repair, K8 search, or
another mechanics milestone.

## Top-down validation

The deterministic cross-stage validator is:

```bash
PYTHONPATH=src python3 -m arknights_planner.cli.plan_cli top-down-validation \
  --data-root data/ArknightsGameData \
  --output-dir output/top_down_validation \
  --cross-stage-budget 60 \
  --first-win-budget 300
```

It automatically selects three supported ordinary GameData stages, runs the same
understanding-first pipeline on each, performs a read-only 6-8 rebaseline, and
makes one bounded first-WIN attempt. It uses no real LLM and no broad search.
The latest artifacts are under `output/top_down_validation/`.

## Setup

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev,api,ark]'
git clone --depth 1 https://github.com/Kengxxiao/ArknightsGameData.git data/ArknightsGameData
arknights-data inspect-repository
```

The GameData checkout is deliberately ignored by Git. You can use any checkout with
`--data-root /path/to/ArknightsGameData`.

## Data archaeology CLI

```bash
arknights-data inspect-repository
arknights-data inspect-table character_table.json
arknights-data inspect-operator char_002_amiya
arknights-data inspect-enemy enemy_1
arknights-data inspect-stage 1-7
```

## Planned interfaces

The production planner will keep provider code under `integrations/ark/`; future
planning, FastAPI (`/api/v1/`), semantic-source, and simulator layers will depend on
canonical models rather than raw JSON. API credentials belong in `.env`, never source.

## Known limitations

This milestone does not claim projectile speed, attack windup, damage-frame ordering,
or full skill semantics. These are represented as `UNKNOWN` unless an exact source
field is traced.
