# R107 protocol recovery audit

## Identity and budget

- Original R107 failure was `check-001` only: the model submitted `R107_SOL_HIGH_SEVEN_LOWER_RELEASE_001`, while `session_config_v1.json` required prefix `R107_SOL_HIGH_SEVEN_PROTECTED14_LATE_RELEASE_`. This was a format failure before candidate creation, not a tactical or lineage rejection.
- Recovery changed exactly two self-references (`$.revised_operational_plans[0].operational_plan_id` and `$.revision_hypothesis.operational_plan_id`) to the authorized ID. Original output SHA-256 is `53c3d416dd3eef8ac327a8d118c3500f1b0d265384d092f21af9f587d549e66f`; normalized output SHA-256 is `421d776f4b13c24ec648733442b82409b063905300957f4c5458e094194b3749`; canonical candidate SHA-256 is `566eaa1424cb136f850d22c943ebeaa374553d948e1a265cf48702984f6d3d07`.
- Recovery ledger: real CLI 0/0, model generation 0/0, check 1/5, candidate 1/1, complete simulation 1/1. Original R107 remains CLI 1/1, check 1/5, candidate 0/1, simulation 0/1.

## Tactical result

- The recovery is a complete LOSS: 20 kills, 13 leaks, life −11, five operator deaths, zero active enemies. Parent R106 is not superseded; M70 remains the only verified complete fixed-simulator WIN at eight IDs.
- R107 was not a late-release test in the intended sense. Melantha deployed@901 instead of Spot, but Steward had already died@3970. Thus planned retreat@4280 was illegal. Steward delivered 38 artillery hits/11,035.13 damage, artillery survived, and artillery leaked@5759.
- The early routes remained closed: #11 BLOCK@2738/death@2881; #13 BLOCK@3098/death@3311.
- The protected-14 mechanism did not produce the hypothesized conflict reduction: #14 was not blocked by roadblock 4 in this run, had no recorded DAMAGE, `ENEMY_ABILITY_HIT`, or death, and reached@12448. Protected #3 independently died@5384 from officer#23 after damage@5264 and@5324.
- Central remained independently unresolved: #21 leaked@5046, #22@5359, #33@6846, #34@6996. #22 was briefly blocked; #33/#34 had no recorded BLOCK. The first hostile leak was #19@4507, while the first recorded objective failure was #22@5359.

## Conclusion

The event result refutes this candidate's protected-14 release and simultaneous central hypothesis, but not the existence of a seven-ID solution or R106's local route+artillery branch. The next actionable coupling is to preserve route closure while keeping Steward alive through the artillery window and cover protected #3's officer#23 chain. Exact HP and continuous positions remain UNKNOWN.
