# R106 post-run audit

## Identity and control

- Parent: `R105_SOL_HIGH_SEVEN_EARLY_PROTECTED_001:candidate-001`, plan/action SHA-256 `3b8c452a9f0aaf9667f3420ecdf912290ce5c69b984895b46447410563ee5e52` / `d48eac7ffe3006947abbc6bbc89e9b517cb441643a8672e40ec78b18d20bdafb`.
- Candidate: `R106_SOL_HIGH_SEVEN_HEAL_COMPETITION_001:candidate-001`, plan/action SHA-256 `e170c2d1b44b7272bab200247e7a54eae16a9d7ac7ebf61ad2df3ae44a045c2d` / `77cc7aceb3a593c6467a116fd0f69070b4ffcaff5c6168234d70881a75f64e3b`.
- Roster and geometry were unchanged. The normalized diff had seven frame changes: Ansel deploy 1381→1396, Hibiscus deploy 1741→1740, and five Ansel skill activations each +15 frames.
- The event prefix was identical for 5,764 records; the parent then deployed Ansel@1381 while the candidate emitted pending enemy actions until Ansel deployed@1396. This validates the expected timing divergence but does not make later losses single-variable causal conclusions.

## Result

The complete fixed-simulator result was LOSS at 22 kills / 11 leaks / life −9, with zero active enemies. `#11` was blocked@2738 and killed@2881; `#13` was blocked@3098 and killed@3311. Steward received 16 heals/6,370 through frame 3911 (parent: 15/5,998), Hibiscus received 9/3,560 (parent: 5/2,152.6), Friston's total stayed 3,920, and Ansel's total stayed 1,782. Steward survived the eighth 910 hit@3911 and retreated alive@4280; artillery was killed@4273 after 45 Steward hits/13,227.21 damage.

The first independent decisive failure was protected `#14` dying@3911 after five officer hits and three artillery-shell hits. Protected `#3` survived to reach@15549. Central `#21/#22/#33/#34` leaked@6697/6661/6846/6996; the first hostile leak was `#23`@5766. Midnight, Friston, and Fang died@5379/6262/6298. Runtime action errors were Midnight skill@5400 and retreat@9001 after his absence; deployments were legal.

## Classification

- Established observations: early-route closure, changed heal allocation, Hibiscus survival@3461, Steward survival@3911, artillery closure, and roadblock destruction.
- Refuted for this branch: protected-route closure and central closure. The global LOSS does not uniformly refute the local observations.
- Unproven: that either deploy shift alone is responsible, exact HP margins, continuous positions between event records, and transferability beyond this fixed simulator.
- Boundary: M70 remains the eight-operator fixed-simulator WIN. R104 remains a seven-ID artillery-closed branch. R106 is an additional verified LOSS branch that also closes artillery; seven-or-fewer feasibility remains UNKNOWN.

## Budget and usage

Authorized and used: real CLI 1/1, check 1/5, candidate 1/1, complete simulation 1/1. Completed MCP calls were 2 `get_session_status`, 1 `check_plan`, 1 `run_simulation`, and 41 `query_events` (45 total). Visible turn usage was 1,596,075 input / 22,823 output tokens, with 1,498,624 cached input as an input subset; internal request count remains `UNKNOWN_CLI_INTERNAL`.

## Next question

Can protected `#14`'s shell/officer exposure be separated from the route-holder/support tile chain without changing proven `#11/#13` closure or artillery closure, and can late central `#33/#34` receive a live blocker/output holder before their leak windows? This is an evidence-supported question, not authorization to start another CLI or simulation.
