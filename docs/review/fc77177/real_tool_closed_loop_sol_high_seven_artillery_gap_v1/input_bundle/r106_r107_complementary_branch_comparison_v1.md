# R106 / R107 recovered complementary-branch comparison

## Identity

- R106 closeout SHA-256: `d215dd68e60891607b5285ef8391c1c5487f245a68ecaa6c35d802201469164b`.
- R107 recovery closeout SHA-256: `0eb2b1d7860d33bc1cc931de78de3be7c5d6671012d4656f67309285a8bb705b`.
- R106 events archive: `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_heal_competition_v1/session/candidates/candidate-001/simulation/diagnostic_events.json.gz`; SHA-256 `7ed0ee9b080441c6d90ff4d5a9106b40ff014a0b99f0f4fb18096d84c61164d5`; restored SHA-256 `ccd3fa8935097735d26a0e7fe49a10963bb2ae61b500d5a571a0a3eab9db4266`.
- R107 recovery events archive: `docs/review/fc77177/real_tool_closed_loop_sol_high_seven_protected14_late_release_recovery_v1/session/candidates/candidate-001/simulation/diagnostic_events.json.gz`; SHA-256 `3ef5e9aba8bd510dbb90d1c484b1f7d823b17e15c37235a99b18e10772caaca5`; restored SHA-256 `3404a7062adc5d4dc135bb5716418bc23ab5d90b28908302f09766c1eba485f4`.

## Key differences

| Question | R106 | R107 recovered | Assessment |
|---|---|---|---|
| #14 | Blocked by roadblock4 at 3251, then took officer16/18 damage and three 910 shells; died at 3911. | Melanha deployed@901 at [5,6] destroyed roadblock4 at 2026; #14 was not blocked by roadblock4, had no recorded hostile damage/death, and reached at 12448. | Direct evidence: Melanha's early device clearance is the concrete mechanism behind this run's #14 safety. |
| Steward | Took eight 910 ability hits through 3911 and 17 Steward-targeted heals through 3955; survived to planned 4280 retreat. | Took seven 910 ability hits through death and 12 Steward-targeted heals through 3950; died at 3970. | The changed lower lane shifted heal allocation and Steward still died. Through 3970 R106 was 734 net HP-equivalent better, but exact HP is UNKNOWN, so this is supporting correlation, not a proven sole cause. |
| Lower route | Spot occupied [5,6]; no roadblock4 destruction. | Melanha replaced Spot, killed #5 by 1261, #9 by 1756, destroyed roadblock4 by 2026, and killed #16/#18 later. | The lower route had direct defensive duties in addition to device clearance. |
| #3 | Officer23 hit #3 at 5460/5520/5580; #3 later reached at 15549. | Officer23 hit #3 at 5264/5324/5384; #3 died at 5384. | Separate timing in two runs; artillery death does not automatically save #3. |
| Early routes | #11/#13 remained closed. | #11/#13 remained closed. | Same broad carrier condition, but continuous positions remain UNKNOWN. |
| Complete result | 22 kills / 11 leaks / life −9. | 20 kills / 13 leaks / life −11. | Neither is a complete seven-ID WIN. |

## Why no real CLI was started

R107's #14 gain and Steward loss are both coupled to replacing Spot with Melanha in the lower lane. Melanha's [5,6] RIGHT placement is required to hit roadblock4 in the fixed simulator, but it also performs early lower blocking and attracts damage/heal competition. Keeping both Spot and Melanha would make the deployed union eight IDs. Retreating Melanha after roadblock4 destruction would drop lower duties for #16/#18, while delaying her deployment might preserve roadblock4 timing but leaves whether #5/#9 remain closed UNKNOWN. The current evidence therefore does not identify a specific, executable mechanism that preserves #11/#13, artillery closure, #14 safety, and #3 handling without an eighth ID or an unverified lower-route trade.

## Next question, not authorized

Can Melanha's deploy/skill timing be shifted so roadblock4 still clears before #14's 3030 spawn/3251 restraint window, #5/#9 remain closed, and Melanha receives less heal competition—without introducing an eighth ID? This is untested and requires a new bounded candidate design if pursued.
