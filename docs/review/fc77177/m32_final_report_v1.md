# M32 R8-7 decisive mechanism restoration report

## Scope

- Tactical Codex CLI starts: **0/0**.
- Full-stage simulations: **2/4**; **2 remain unused** for a later confirmed mechanism repair.
- Models/providers/accounts: unchanged; no new plan or action candidate was generated.
- Historical M29/M30/M31 artifacts remain unchanged.

## Conditional redeployment correction

The M31 static compiler treated a repeated deploy while an operator was still active as if the
operator had already exited, cleared tile occupancy, and skipped DP. The corrected static result
distinguishes:

- another operator occupying the target tile: `CONFLICT` (`TILE_OCCUPIED_BY_ANOTHER_OPERATOR`);
- self-occupancy: `CONDITIONAL_REDEPLOY_AWAITING_EXIT`, requiring observed retreat/death before
  the deploy, cooldown, tile release, deployment-slot release, and actual DP payment;
- explicit retreat: deterministic cooldown and a new deployment generation;
- death: not treated as a static fact until runtime evidence exists.

The DP ledger now records a `CONDITIONAL_REDEPLOY_DP_RESERVATION` without pretending the base
cost is known-final. It conflicts if the current balance cannot cover the base cost and marks
final DP `UNKNOWN_UNTIL_CONDITIONAL_REDEPLOY_DP_RESOLVED`. Cost growth and special rules remain
`UNKNOWN_REQUIRES_RUNTIME_VERIFICATION`.

Regression coverage: `tests/test_conditional_redeployment_static_v1.py`.

## R8-7 mechanism evidence

The full chain table, fixed input hashes, client build 2771 hashes, GameData hashes, PRTS hashes,
implementation locations, and UNKNOWN boundaries are in
`docs/mechanics/R8_7_MECHANISM_COVERAGE_V1.md`.

Confirmed for R8-7:

- Artillery has GameData HP 13000, ATK 1000, DEF 800, MR 50%, range 2.0, and base attack time 5.0.
  Current runtime gives it a delayed locked-area ability with 5-second cooldown, 1.2 blast radius,
  and 3-second delay.
- Protected targets are preferred artillery targets before ordinary deployed operators.
- Blast position is locked at ability start and applies to protected targets, operators, and enemy
  neutrals in radius after the delay.
- Artillery ordinary attacks are suppressed while the delayed-area ability exists.
- Roadblocks use taunt -1, HP 8000, DEF 200, RES 20, and 0.4472 blocking radius; destruction
  refreshes route state.
- `Route.ReconstructNextMap -> SPFA` remains `UNKNOWN_MISSING_STATIC_EDGE` in build 2771.
- Dodge, shield, barrier, and relevant status defenses remain unimplemented; this does not imply
  artillery physical damage is dodgeable.

## Static and deterministic re-verification

Both historical plans were copied to new directories before rerunning static checks. Their
original M30/M31 directories were not rewritten.

| Plan | Static classification | Actions SHA-256 unchanged | Result |
|---|---|---|---|
| `R8_7_GPT_M30_V2` | `STATIC_CONTRACT_CHECKED_NO_RANGE_TARGET_UNKNOWN` | `2225b9723536bda4eea2a8f72fa9582a296ad9aeeb276d69f1b0afae165cc880` | LOSS, 23 kills, 10 leaks, 10 operator deaths, life -7 |
| `R8_7_GPT_M31_V3` | `STATIC_CONTRACT_CHECKED_NO_RANGE_TARGET_UNKNOWN` | `b1475a1796fb2364e03c0ec8e4486b622e371b842654e0349f0c323eef7ec382` | LOSS, 22 kills, 11 leaks, 10 operator deaths, life -9 |

Both plans have no conditional redeploy, so the static correction does not change their static
classification. The runtime simulator itself was not changed; repeated deterministic results
therefore also validate the re-verification path.

### M30 V2

- All four roadblocks destroyed: #3/2025, #4/2820, #1/3234, #2/4965.
- Both protected targets arrived (#3/3566, #14/5297); neither died.
- Artillery: 25 damage events, 7348.45 damage, implied remaining HP 5651.55; leaked at frame 5759.
- First leak: `enemy_1110_uamord#21` at frame 5067.
- Operator deaths include Medic 1380, Ansel 3180, Steward 3480, Lava 3630, Hibiscus 3780, Fang
  4668, Wyvern 4734, Beagle 5439, Midnight 6450, Durin 6702.

### M31 V3

- Roadblocks destroyed: #3/1725, #4/2421, #2/8985; #1 was not destroyed.
- Protected targets: #3 died at frame 5430 from artillery; #14 arrived at frame 9317.
- Artillery: 30 damage events, 8285.47 damage, implied remaining HP 4714.53; leaked at frame 5759.
- First leak: `enemy_1110_uamord#22` at frame 5469.
- Operator deaths include Gallus 1080, Steward 3180, Ansel 3780, Lava 3930, Hibiscus 4534, Spot
  5070, Midnight 5122, Noir Corne 5458, Beagle 6386, Durin 6635.

The prior tactical conclusions remain valid under the corrected deterministic path: V2 retains the
best complete-route non-WIN behavior, while V3 improves artillery damage but collapses early
protection and route completion. Neither is a simulator WIN, perfect objective result, faithful
result, robust result, or real-game result.

## Evidence and budgets

- Budget ledger: `docs/review/fc77177/m32_simulation_budget_v1.json` (`started=2`).
- Re-verification manifest: `output/r8_1_r8_7_batch_v1/main_08-07/m32_mechanism_reverification_v1/m32_reverification_manifest_v1.json`; a
  Git-visible copy is `docs/review/fc77177/m32_mechanism_reverification_v1/m32_reverification_manifest_v1.json`.
- Compact chain summaries: `m32_key_chain_summary.json` in each re-verification directory.
- Events and summaries are saved uncompressed locally and with deterministic gzip; both pre- and
  post-compression hashes are recorded in the manifest. Compressed events/summaries, action and
  plan snapshots, gate records, and static results are also mirrored under
  `docs/review/fc77177/m32_mechanism_reverification_v1/`.
- The remaining 2 simulations are intentionally unused because no additional confirmed mechanism
  defect affects these saved plans.

## Tests

Focused suite: 42 passed.

Full suite: current tree has 31 failed test IDs; parent `a823761` has 47 failed test IDs under the
same venv/artifact-linked worktree. Exact ID comparison has **0 current-only failures**. The 16
parent-only failures are the same local untracked-output availability difference documented by
M29. Exact lists are:

- `output/r8_1_r8_7_batch_v1/main_08-07/m32_mechanism_reverification_v1/m32_full_pytest_after_failures.txt`
  and `output/r8_1_r8_7_batch_v1/main_08-07/m32_mechanism_reverification_v1/m32_full_pytest_parent_failures.txt`;
  Git-visible copies are under `docs/review/fc77177/m32_mechanism_reverification_v1/`.

## Conclusion

R8-7 is suitable to resume bounded tactical iteration. The decisive observed bottlenecks are now
separated: artillery must receive about 4714.53 additional damage relative to M31 V3 before its
frame-5759 leak, while early interception and complete route clearance must hold simultaneously.
This is evidence for a new GPT structural attempt, not a fixed tactical recipe.

The next bounded task is one separately authorized R8-7 structural iteration that uses these
re-verified facts and explicit observational predictions. No faithful, robust, probabilistic, or
real-game WIN may be claimed without its own evidence.
