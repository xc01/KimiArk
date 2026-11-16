# R104 deterministic coupled-retreat closeout

R104 was a zero-model deterministic control of R101 C2
(`R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002:candidate-002`). The only tactical
change moved Steward's retreat from 4200 to 4280 and the same-ID redeploy from
6301 to 6381, preserving a 2101-frame interval. The corrected 30 fps mechanism
and 70-second redeploy were verified in the frozen fact pack.

The candidate passed production checks and completed one fixed simulation.
Events before 4200 matched the parent for 19,405 entries. In the delayed window,
Steward survived an artillery hit at 4211, received Ansel's heal at 4213 and
Hibiscus's heal at 4277, then legally retreated at 4280. Steward recorded 45
artillery hits for 13,227.21 total damage; the two additional post-4177 hits
were at 4225 and 4273, and the artillery died at 4273 with no artillery leak.

The redeploy at 6381 was legal and cost 18, but the complete run remained LOSS
at 21 kills / 12 leaks / life −10. Protected #3 died at 3311; #14 reached at
12448. Central armor #21 was blocked at 4646 but leaked at 5353, and
#22/#33/#34 leaked. Friston died at 2111 and Fang died at 4954; there were two
death events and two unique dead IDs, with zero action errors and zero remaining
enemy HP at settlement end 12449.

Budget: real CLI 0/0, model generation 0/0, completed checks 2/5, candidate 1/1,
complete simulation 1/1. Model usage is `MODEL_USAGE_NOT_APPLICABLE`; this does
not imply a hidden or failed model call. The result is limited to this
parent/two-frame transformation in the current fixed simulator. M70
`R8_7_GPT_M70_V1` remains the best verified eight-ID complete WIN; seven-ID and
fewer feasibility remain UNKNOWN. A supported but unauthorized next question is
whether a seven-ID plan can retain this artillery closure while repairing the
central blocker and protected-route failure.
