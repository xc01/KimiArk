# Astra high joint-feedback closure

## Result

The authorized Astra high session completed normally in one CLI start. It used 4 of 20 checks, 4 of 5 candidates, and 4 of 5 complete simulations. No seven-ID plan reached a complete WIN, so the frozen best remains M70's eight-ID WIN. Seven-or-fewer feasibility remains UNKNOWN.

| Candidate | Roster | Kills / leaks | Protected reached | Operator deaths | Life | First objective failure |
|---|---|---:|---:|---:|---:|---|
| 001 | Fang, Friston-3, Midn, Melantha, Ansel, Hibiscus, Steward | 10 / 23 | 0 | 7 | -22 | enemy leak @4070 |
| 002 | same seven | 17 / 16 | 0 | 7 | -15 | enemy leak @5251 |
| 003 | same seven | 24 / 9 | 1 | 3 | -7 | protected-target death @3430 |
| 004 | same seven | 12 / 21 | 0 | 8 | -20 | protected-target death @3430 |

All candidates selected the same seven IDs as C3, including Melantha. The variation was structural placement and timing, not forced roster diversity. This is allowed by the task and should not be scored as either success or failure by itself.

## Main evidence

- C1–C4 all destroyed roadblock #4 at frame 1966 with 14 `DEVICE_DAMAGE` events totaling 8,358.56, matching the M70 opening. C3 also destroyed #3, #2, and #1 late enough for one protected arrival, while C1/C2/C4 did not complete all protected-route openings.
- Steward was the only recorded ordinary damage source to artillery in every candidate, but its contact was much shorter than M70: C1 8/2,216.99; C2 18/5,156.37; C3 10/2,939.38; C4 13/3,686.68. Artillery survived all four runs and leaked at frame 5759.
- The key central enemies (#21, #22, #28, #31, #33, #34) leaked in every candidate. C1 had zero ordinary/ability contact with all six; C2–C4 had partial contact but far below the M70 kill-chain totals. Thus the failure was coupled central pressure plus artillery and protected passage, not only the #4 opening.
- C3 was the best bounded sample on terminal metrics but still failed the WIN condition: one protected target reached, three operator deaths, nine leaks, and a protected-target death at frame 3430 before its first leak at 5196.
- C4's verified healing prediction occurred, but artillery splash still hit four operators at frame 2293. This demonstrates that a single observable PASS cannot prove full plan safety.

## Autonomy and lineage

The session used only the four scoped tools: 2 status calls, 4 checks, 4 simulations, and 34 focused event queries. It revised within the same session after querying ordinary damage, ability hits, devices, heals, projectile births, deaths, leaks, and target selection. No candidate was retried and no second CLI was started.

A compliance gap was found in post-run review: all four plans left `parent_plan_id` undeclared, and the previous cold-start root gate did not reject this. A post-run minimal service guard now requires the root parent on every cold-start candidate and a completed candidate parent after the first run. The service fixture suite passes. This is disclosed as a code-state change after the archived run; the run's frozen code hashes remain unchanged.

## Budget and usage

| Resource | Used / max |
|---|---:|
| Real CLI starts | 1 / 1 |
| Check calls | 4 / 20 |
| Run candidates | 4 / 5 |
| Complete simulations | 4 / 5 |

Visible turn usage was 1,825,837 input tokens, of which 1,740,416 were cached; cached input is a subset and is not added to input. Output was 28,359 tokens, including 18,351 reasoning tokens. Internal model requests are `UNKNOWN_CLI_INTERNAL`.

## Scope

This is evidence only for the current fixed simulator and this bounded experiment. It is not a real-game, faithful, robust, probabilistic-WIN, or global-minimum claim. Four losses do not prove that seven operators are infeasible. The unused one candidate/simulation and 16 checks do not transfer to another session.
