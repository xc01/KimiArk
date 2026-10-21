# M31 R8-7 output-window, survival and redeployment iteration report

## Budgets and scope

- Model path: `openai / gpt-6.1-sol / high`, `features.apps=false`.
- Real tactical CLI starts: **4/4**. Cumulative count moved 73 → 77. No retries or resume calls were used.
- Fixed full-stage simulations: **4/4**. The ledger is the M30 remaining two simulations plus two newly authorized M31 simulations; M30's own budget file remains unchanged at 2/4.
- Only R8-7 was advanced. No model, provider, account or mechanism was switched.
- The simulation gate initially used a `prior_stage_simulations=2` field as an additional consumed count, which would have double-counted inherited budget. It was corrected to `0`; provenance records the inherited/new split. This did not reset or increase the four-start authorization.

## Execution ledger

| Plan | Contract | Static | Simulation | Result | First observable prediction |
|---|---:|---:|---:|---|---|
| `R8_7_GPT_M31_V1` | PASS | PASS | LOSS | 19 killed, 14 leaked, 10 operator deaths, 0 protected deaths, 2 arrivals, life -11 | Artillery death 3151–5580: not observed |
| `R8_7_GPT_M31_V2` | PASS | PASS | LOSS | 23 killed, 10 leaked, 8 operator deaths, 0 protected deaths, 2 arrivals, life -7 | Artillery death 3151–5758: not observed |
| `R8_7_GPT_M31_V3` | PASS | PASS | LOSS | 22 killed, 11 leaked, 10 operator deaths, 1 protected death, 1 arrival, life -9 | Artillery death 3900–4799: not observed |
| `R8_7_GPT_M31_V4` | PASS | PASS | LOSS | 17 killed, 16 leaked, 6 operator deaths, 2 protected deaths, 0 arrivals, life -15 | Artillery death 4200–5100: not observed |

All four plans were legal battle losses, not schema/contract failures, static failures or infrastructure failures.

## Deterministic evidence

### Redeployment facts

- Runtime simulator handles death and manual retreat through the same removal path. Both start the effective redeploy cooldown, release the tile and blocked enemies, and reset HP/SP/skill state. Manual retreat refunds half deployment cost; death refunds none.
- A later explicit `DEPLOY` is required. Static checking cannot know a future death as a fact.
- A generic static compiler correction now treats a duplicate `DEPLOY` without intervening `RETREAT` as `CONDITIONAL_REDEPLOY_AWAITING_EXIT`, while the simulator still validates actual exit time, cooldown, DP, tile and deployment limit.
- M30 V4's frame5223 Gallus rejection was not a compiler bug: Gallus withdrew at frame3120 and has a 200-second cooldown.
- Runtime death-release and cooldown behavior is covered by `tests/simulator/test_normal_low_star_talent_runtime.py`.
- No physical dodge, shield or probability survival mechanism was implemented or declared as current runtime fact. No probabilistic WIN was claimed.

### Artillery and routes

| Plan | Artillery damage | Artillery remaining | Artillery end | Roadblocks destroyed | Protected result |
|---|---:|---:|---|---|---|
| M30 V2 | 7348.45 | 5651.55 | leaked 5759 | #1/#2/#3/#4 | 2 arrived, 0 deaths |
| M31 V1 | 6071.27 | 6928.73 | leaked 5759 | #1/#2/#3/#4 | 2 arrived, 0 deaths |
| M31 V2 | 5696.47 | 7303.53 | leaked 5759 | #1/#2/#3/#4 | 2 arrived, 0 deaths |
| M31 V3 | 8285.47 | 4714.53 | leaked 5759 | #2/#3/#4 | #3 killed 5430 by artillery; #14 reached 9317 after objective failure |
| M31 V4 | 6127.86 | 6872.14 | leaked 5759 | #3 | both killed; #14 by officer #18 at 3966, #3 by artillery at 5430 |

The frame5430 `ENEMY_DEATH` records the artillery as `source_id` and protected target #3 as `target_id`; it is not artillery death. Artillery death was never observed in M31.

## Learning and branch status

- V1/V2 confirmed that adjusted medical timing alone did not sustain artillery damage. V2 preserved complete route behavior with 23 kills and 10 leaks, but did not improve the WIN boundary over M30 V2. It is the best M31 exploration branch and has fewer operator deaths (8 vs 10).
- V3 increased artillery damage to 8285.47 but collapsed route protection: #1 was not destroyed, #3 was killed, and the objective failed before #14's late arrival.
- V4 failed immediately and is not a useful comparison candidate: opening deaths produced 16 leaks, only #3 was destroyed, and both protected targets died.
- M30 V2 remains the best non-WIN R8-7 exploration context. It is not a WIN and must not be presented as a tactical solution.
- Repeated M31 failure eliminated the hypothesis that medical timing or a simple high-damage shift is sufficient. The unresolved requirement is simultaneous early interception, complete route clearance, protected-target survival, and at least 4714.53 additional artillery damage before frame5759 relative to V3.

## Validation boundaries

- `simulator_win`: false for V1–V4.
- Project perfect objective: false for V1–V4.
- `probabilistic_win`: false/not applicable; no verifiable joint probability lower bound was provided.
- `faithful_certificate`: NOT_ISSUED.
- `robust_claim`: NOT_EVALUATED.
- Real game: NOT_PLAYED.

## Tests

Targeted behavioral regression suite passed:

```text
tests/test_conditional_redeployment_static_v1.py
tests/simulator/test_normal_low_star_talent_runtime.py
tests/simulator/test_combat_runtime.py
tests/test_r8_1_lowstar_c2_compact_tool_revision_v1.py
tests/test_gpt_tactical_stage_session_v1.py
```

36 tests passed. A full `pytest -q` run had 31 failures in benchmark, M11–M15, repository inventory, stage-geometry and older tactical closure tests. A detached `94b89a0` worktree comparison was not identity-equivalent because it lacked untracked local runtime inputs and produced additional collection/setup errors; therefore those full-suite failures are reported as environmental/unrelated without claiming an exact historical identity.

## Next bounded node

M32 must make one separately authorized structural attempt that treats route survival and artillery damage as simultaneous constraints. It should not mechanically merge M30 V2 and V3; GPT must choose how to hold early lanes, clear #1–#4, protect both civilians, and generate the missing artillery damage through legal survival/rotation/redeployment.
