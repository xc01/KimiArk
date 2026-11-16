# R105 early-route and protected-target closeout

R105 used archived R104
(`R104_DETERMINISTIC_SEVEN_C2_COUPLED_RETREAT_001:candidate-001`) as the single
frozen primary parent. One `gpt-6.1-sol/high`, apps-false CLI was started and
completed. Both candidates were legal seven-ID plans and both complete fixed
simulations settled, but neither won.

## Results

| Version | Plan hash | Result | Early routes | Artillery | Protected | Deaths |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | `3b8c452a9f0aaf9667f3420ecdf912290ce5c69b984895b46447410563ee5e52` | 20 kills / 13 leaks / life −12 | #11 blocked@2738, killed@2881; #13 blocked@3098, killed@3311; no route leaks | 37 hits / 10,786.03, then leaked@5759; no death | #14 died@3911; #3 died@5341; no arrival | 5 events / 5 IDs |
| C2 | `3c7fa37fb2ee1c0c53709bbd70ba7146a1f0e4839dd93624b74f3f0b4c4ffa73` | 12 kills / 21 leaks / life −20 | #11 leaked@3065; #13 leaked@3425; no BLOCK/death | 9 hits / 2,466.09, then leaked@5759; no death | #3 died@5341; #14 died@6314; no arrival | 8 events / 7 IDs |

C1 had seven action errors; C2 had eleven. The central armor group
#21/#22/#33/#34 was not killed in either version. Neither simulation produced a
new seven-ID WIN. R104 remains a reusable seven-ID artillery-closed branch, not
a complete WIN; M70 remains the eight-ID WIN.

## Integration

The frozen input bundle, R104 parent identity, 20-record selector store, prompt,
and final model prompt were archived. Both plans declared the correct R104
parent and referenced experience IDs. However, neither supplied the requested
`experience_selector_decision_record` or full validation-card object. Therefore
experience use can be traced only to visible plan references and actions, not to
the requested structured decision record. The CLI completed with visible usage:
input 2,259,921; cached input 2,128,256; output 28,306; reasoning output 12,914.

Budget: real CLI 1/1, completed checks 4/10 (two failed, two passed), candidates
2/2, complete simulations 2/2, no retries. Completed MCP calls were 2 status,
4 check, 2 run, and 68 query calls for 76 total. Internal request count is
`UNKNOWN_CLI_INTERNAL`; `cached_input_tokens` are an input subset.

## Next unsupported question

R105 C1 proves that a seven-ID plan can block and kill the previously leaking
#11/#13 routes, but its Steward died at 3911 before R104's 4200–4280 closure, so
artillery retained only 37 hits/10,786.03 and leaked. A future, unauthorized
question is whether a seven-ID plan can retain C1's observed #11/#13 closure
while preventing Steward's 3911 death and restoring the 4225/4273 artillery
death. Protected-#3 and central failures must still be checked independently;
artillery closure alone does not prove either is repaired.
