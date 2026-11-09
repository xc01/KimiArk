# Seven-recursive vs M70 zero-model comparison

**Scope:** current fixed simulator only. **Counts:** model calls 0, simulations 0, STARTED 0. M70 remains the 8-ID WIN; seven-or-fewer feasibility is UNKNOWN.

## Baseline

| Case | Result | Kills / leaks / deaths / life | Protected targets |
|---|---|---|---|
| M70 | WIN | 33 / 0 / 0 / 3 | #14@11119, #3@11349 |
| Seven-recursive C1 | LOSS | 24 / 9 / 3 / -8 | #14 dies@3966; #3 dies@5353 |

Coordinates below follow the DEPLOY event convention `[row,col]`; action snapshot tiles are `[x,y]`.

## Earliest structural and geometry changes

- **OBSERVED:** M70 deploys Melantha@841 at event [5,6], retreats@2054, then Steward@2071 at [7,5]. C1 removes Melantha, deploys Spot@901 at [5,6], keeps Ansel at [5,5], and deploys Steward@2101 at [6,5].
- **OBSERVED:** first artillery lock changes from M70 `[5,6]@1893` to C1 `[5,5]@1861`.
- **CAUSAL_ROLE_HYPOTHESIS:** these changes plausibly redirect exposure and remove roadblock work, but necessity of any specific role is not proven.

## Artillery and healer chain

- **OBSERVED:** M70 has 16 shells and Steward kills artillery@4273 after 45 hits / 13,227.21 damage.
- **OBSERVED:** C1 has 20 shells; Steward deals 39 hits / 11,284.23, with visible output gaps 2917-3361 and 4225-4705; artillery leaks@5759.
- **OBSERVED:** C1 Hibiscus takes 890@3011 and 890@3161, then dies@3161. Between hits she self-heals 558.9@3013 and receives Ansel 362@3015; exact HP is not recorded. This corrects the prior closeout's wording that only 558.9 healing occurred between the hits.
- **UNKNOWN:** whether an altered healer schedule, position, skill timing, or another structure would preserve this support role.

## Protected passage

- **OBSERVED:** M70 destroys #4@1966, #3@2404, #2@10787, #1@11017; both protected targets reach.
- **OBSERVED:** C1 destroys only #3@2404. It does no `DEVICE_DAMAGE` to #4/#2/#1. Protected #14 is restrained by #4@3251 and dies@3966; protected #3 is restrained by #1@2773 and dies@5353.
- **OBSERVED:** `trap_020_roadblock#3` and `enemy_3001_upeopl#3` are distinct.

## Steward output arithmetic

- **OBSERVED:** M70 45 hits (36 normal + 9 boosted); C1 39 hits (32 normal + 7 boosted).
- **CAUTION:** the 6-hit/1,942.98-damage difference does not establish that six more hits alone would WIN. It does not resolve remaining HP, reverse damage, healing, DP, blocking, or protected-passage dependencies.

## Central chain

| Enemy | M70 | C1 |
|---|---|---|
| #21 | blocked@4646, killed@5154 by Melantha | blocked@4646, unblocked@4753 when Fang dies, leaks@5152 |
| #22 | blocked@4796, killed@6429 | no BLOCK, 283.85 damage, leaks@5196 |
| #34 | blocked@6596, killed@7197 | no BLOCK, 1,021.19 damage, leaks@6996 |

- **OBSERVED:** Fang dies@4753; artillery hits Fang@4753 and #21 hits Fang@4752. Friston-3 dies@4768 after #22 arts damage. HP history is absent, so exact killer attribution is UNKNOWN.
- **OBSERVED:** #33 also leaks@6846 in C1.

## Difference chains

1. **Early-upper-clearance:** M70 #4 damaged 841-1966 and destroyed; C1 has no #4 damage, so #14 is restrained@3251 and dies@3966. Melantha necessity is HYPOTHESIS.
2. **Support geometry/healer survival:** M70 locks [5,6]/[7,5]; C1 locks [5,5]/[6,5], exposing Ansel/Friston/Spot/Steward earlier. C1's Hibiscus shell cadence lacks the M70 pre-hit healing cadence. Exact repair is UNKNOWN.
3. **Central live block/kill:** M70 blocks and kills #21/#22/#34; C1's blocker deaths release #21 and leave #22/#34 unblocked. Whether this is primarily support, geometry, output or timing is UNKNOWN.

## Contributions and replacement costs

- **OBSERVED/COST:** C1 unique opening cost is 98; M70's unique deployment cost is 113. The omitted Melantha used 15 initial DP, damaged roadblock #4 (8,358.56) and later roadblock #2 (8,358.56), while also dealing central and runner damage.
- **OBSERVED:** C1 contributions include Spot's upper closure, Midnight's #3 clearance, Fang/Friston early blocking, Ansel/Hibiscus healing, and Steward's 24,601.12 total damage. These totals do not prove any role is replaceable or indispensable.
- **UNKNOWN:** viable substitutions, DP/tile trade-offs, and effective sacrifice/rotation options.

## Model stop

- **OBSERVED:** 8 completed MCP calls: 1 status, 2 checks, 1 simulation, 4 queries. `turn.completed=true`, exit 0, automatic retry false.
- **OBSERVED:** the final message says C2 was not submitted because no sufficiently justified combined repair was identified. This is not evidence that no repair exists.
- **UNKNOWN_CLI_INTERNAL:** model-internal request count and hidden reasoning.

## Prior prompt evaluation

`next_prompt_suggestion_v1.md` preserves the budget, four-tool boundary, and no-forced-C2 rule, but it is too generic: it names the healer symptom without roadblock #4's absent clearance, first-lock geometry change, or #21 unblock chain. `next_prompt_suggestion_v2.md` supplies the concrete, unauthorized next entry.

## Search lesson

The structural rebuild bought upper closure and contact but lost three coupled success conditions: early roadblock clearance, protected-route timing, and a survivable support/artillery geometry. The next test should preserve or explicitly replace these duties rather than add a late central action alone. No counterfactual simulation was run; seven-ID feasibility remains UNKNOWN.

Machine data: `zero_model_comparison_v1.json`; evidence hashes: `zero_model_evidence_index_v1.json`. Suggested, **unauthorized** next prompt: `next_prompt_suggestion_v2.md`.
