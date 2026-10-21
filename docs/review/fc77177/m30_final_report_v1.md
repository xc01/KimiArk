# M30 R8-7 iteration report

## Scope and budgets

- Model path: `openai / gpt-6.1-sol / high`, `features.apps=false`.
- Real tactical CLI starts: **4/4**. Frozen historical count was 69; cumulative after M30 is 73.
- Fixed full-stage simulations started: **2/4**; 2 remain reserved. V1 and V4 did not reach simulation.
- Offline prepare attempts that did not start a CLI: 10 (8 prompt-over-limit, 1 medium authorization rejection, 1 missing `features.apps=false`).
- No model, provider, account, or mechanism was switched.

## Attempt ledger

| Plan | Contract | Static | Simulation | Result |
|---|---:|---:|---:|---|
| R8_7_GPT_M30_V1 | PASS | STATIC_CONFLICT | none | frame6000 Midnight deploy at plan tile `[4,5]` conflicts with Vanilla still deployed there (`TILE_OCCUPIED`). |
| R8_7_GPT_M30_V2 | PASS | PASS | completed LOSS | 23 killed, 10 leaked, 10 operator deaths, 0 protected deaths, 2/2 arrivals, remaining life -7. |
| R8_7_GPT_M30_V3 | PASS | PASS | completed LOSS | 23 killed, 10 leaked, 8 operator deaths, 0 protected deaths, 1/2 arrivals, remaining life -7. |
| R8_7_GPT_M30_V4 | PASS | STATIC_CONFLICT | none | frame5223 Gallus redeploy conflicts: `REDEPLOY_COOLDOWN_ACTIVE`. |

## Causal evidence

### V2: best legal candidate

- All four roadblocks were destroyed: #1 frame3234, #2 frame4965, #3 frame2025, #4 frame2820.
- `enemy_3001_upeopl#3` reached frame3566; `enemy_3001_upeopl#14` reached frame5297; neither died.
- The artillery predicted death window 3600–4740 was not observed. Steward delivered all 25 operator hits for 7348.45 damage, then died at frame3480. Lava died at frame3630 without hitting artillery. Artillery leaked frame5759.
- Early deaths: Lancet frame1380, Ansel frame3180, Steward frame3480, Lava frame3630, Hibiscus frame3780.
- First leaks: armor #21 frame5067, armor #22 frame5196, artillery frame5759, officer #23 frame5781.
- Result digest: WIN false, zero-leaks false, protected-target deaths zero, protected arrivals complete. This is the best exploration branch by project objective boundary, but it is not a WIN and does not promote the frozen current-best branch.

### V3: artillery improved, route and early defense regressed

- Steward, Lava, and 12F produced 11,728.75 artillery damage (28/11/2 hits), leaving 1,271.25 on a 13,000 maximum-HP basis.
- Steward frame4534, Lava frame4230, and fallback 12F frame4980 all died before artillery death. Artillery still leaked frame5759.
- First leak moved earlier to officer #11 at frame3065; #3 reached frame3566, #14 did not arrive.
- Roadblocks #3, #4, #1 were destroyed; #2 was not destroyed.
- One enemy remained at the 600s cap with 3,500 HP.

### V4: static counterexample

- Contract and lineage passed, but the plan could not execute because Gallus at action index 35, frame5223, was rejected for `REDEPLOY_COOLDOWN_ACTIVE`.
- No simulation was run and no action was edited by Python.

## Evidence hashes

| Artifact | SHA-256 |
|---|---|
| V2 diagnostic events | `30de7c96695a8821f661748c7fb746f03ba48e34bb1e282f856d8e0a5f40d9f7` |
| V2 diagnostic summary | `4a924dc135ff51159d754c03bdf081ad279dcca000651f7e2ffc892ed02dda53` |
| V2 events gzip | `a0b43507f4fc68a09680eb81a25ca90b362ce9122f36fb9fba3e3ab7271ed66c` |
| V2 summary gzip | `8852afe44143d7c51bedc746bce861511a09ee21de81c288f374de1e2b3d3d5a` |
| V3 diagnostic events | `129e1b3a4181b9bde4a2e1eb07f06453c924f6f403a55b556bf077b730ba1db6` |
| V3 diagnostic summary | `8d01371dcc6cdeb5b5f39094a4cd38d0bede6205c5b20f930e8525f5ad9cf059` |
| V3 events gzip | `b13a1b7146456825d39d94f839eadf686099c28b84e6c31cb9b9379c7a893056` |
| V3 summary gzip | `5bd2f2add11db03e0fe9a78068ad98706f32b90bfdc9cd97525226e43c15a308` |

## Result boundaries

- `simulator_win`: false for both simulated plans.
- Project perfect objective: false; V2 met both protected-route subgoals but had 10 leaks and a negative life.
- `faithful_certificate`: `NOT_ISSUED`; targeting variants: `NOT_EVALUATED_UNLESS_SEPARATELY_FROZEN`.
- `robust_claim`: `NOT_EVALUATED`; real game: `NOT_PLAYED`.
- No probability-based lucky-trigger WIN is claimed.

## Next node

Use a new, separately authorized CLI cycle to revise from V2, requiring a sustainable artillery attacker before frame3480 and retention of V2's complete four-roadblock / two-arrival structure. The first prediction must concern either artillery kill with attacker survival or preventing the armor leak at frame5067; reaching a civilian or destroying one roadblock is not sufficient.
