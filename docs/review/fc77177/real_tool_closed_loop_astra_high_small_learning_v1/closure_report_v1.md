# Astra high small-learning closure

## Result

The authorized `gpt-6-astra/high` session completed normally with one CLI start, `features.apps=false`. It used `2/2` candidates, `2/2` complete simulations, and `2/10` check calls. There was no seven-ID WIN. The frozen best remains M70's eight-ID WIN; seven-or-fewer feasibility remains `UNKNOWN`.

| Candidate | Plan parent | Roster | Kills / leaks | Deaths / unique | Protected | Life | First objective failure |
|---|---|---|---:|---:|---:|---:|---|
| 001 | authorized root | Fang, Friston-3, Midn, Melantha, Ansel, Hibiscus, Steward | 6 / 27 | 6 / 6 | 0 reached, 2 died | -26 | enemy leak @2915 (life zero) |
| 002 | completed 001 | same seven IDs | 14 / 19 | 7 / 7 | 1 reached (#14), #3 died | -17 | enemy leak @4791 (life zero) |

Both plans had 25 actions and the same seven IDs. Candidate 001 used root `KIMIARK_JOINT_FEEDBACK_ASTRA_HIGH_MAIN_08_07_V1`; candidate 002 correctly named completed plan `R87_ASTRA_HIGH_SMALL_LEARNING_001`. Their frozen plans contain concrete `validation_card` fields for question/change/expected/cost/old-counterexample. The service itself did not enforce the cards; this audit confirms they were present in both frozen plans.

## Learning

**Tested and supported.** Candidate 001 asked whether a permanent Midn lower-row block plus Fang's arts support could preserve central, outer, artillery, and roadblock duties while leaving Melantha and Steward in their inherited roles. Candidate 002 then tested the observed opening-healing failure directly by moving Hibiscus first to Fang/Friston and Ansel east to Midn/Melantha. Run 002 achieved the prerequisite opening: Hibiscus healed Fang/Friston at 1321/1407, Fang generated +6 DP at 2070, and Steward deployed legally at 2071. Both runs destroyed roadblock #4 at frame 1966.

**Tested and refuted.** Run 001 had no opening heal before Fang died@1389, Friston died@1554, and Ansel died@1571; this invalidated its planned 4380-5500 central test before it started. Run 002 repaired that opening, but Ansel's @2541 heal went to Melantha and Ansel died@2593 to an 891 shell; Steward died@3460 after 25 ordinary artillery hits totaling 7,348.45, Midn died@3640, and the central test failed again. Artillery survived both runs and leaked@5759. Sustained healing and artillery closure were therefore not established.

**Roadblock and protected passage.** #3 received zero `DEVICE_DAMAGE` in both runs. Protected #3 was killed by artillery@3310 in both runs. In candidate 002, officers began damaging #3 at 1296, and #14 reached@11718; however, the terminal WIN contract still failed. Destroying #4 did not establish safe protected passage, and these observations do not support the stronger claim that roadblock clearance caused central collapse.

**Central interception.** #21, #22, #28, #31, #33, and #34 leaked in both runs. Candidate 002 improved terminal numbers and delayed its first observed leak to @4625, but neither run established the intended surviving formation needed to defeat the armored central wave. The improvement is evidence of a repaired upstream opening, not proof that the central chain is close to WIN.

The model's post-run audit also observed that protected-target shell damage was recorded under `DAMAGE`, correlated with shell births, while it separately queried `ENEMY_ABILITY_HIT`; it did not infer no injury from one category alone. Historical access was limited to the indexed larger comparison and recorded in the plans. Model timing/tie-break and probabilistic-effect assumptions remained `MODEL_GAP`.

## Budget and usage

| Resource | Used / max |
|---|---:|
| Real CLI starts | 1 / 1 |
| Check calls | 2 / 10 |
| Candidate slots | 2 / 2 |
| Complete simulations | 2 / 2 |
| `get_session_status` calls | 2 |
| `query_events` calls | 50 |

Visible turn usage was 1,493,703 input tokens, of which 1,373,568 were cached. Cached input is a subset of input and is not added. Output was 18,300 tokens, including 8,694 reasoning tokens. Internal model requests are `UNKNOWN_CLI_INTERNAL`. No budget transferred from joint feedback, and no unused balance remains in this group.

## Scope

This evidence is limited to the current fixed simulator, this input bundle, and this bounded two-simulation sample. It is not a real-game, faithful, robust, probabilistic-WIN, or global-minimum claim. Two losses do not prove that seven operators are infeasible. The remaining known uncertainty is whether a seven-ID structure can both survive the artillery shell sequence and supply enough live central BLOCK/arts output after the opening and protected-passage duties are satisfied.
