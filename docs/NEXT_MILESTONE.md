# Next milestone: close R8-7 under m19.1

R8-2 V15 and R8-4 V4 remain frozen current-model perfect simulator results.
The single active goal is R8-7. `R8_7_GPT_V10` is the best current result
(28 kills, 5 leaks, 3 operator deaths, remaining life -2, protected target #3
arrival), while `R8_7_GPT_V2` remains the minimum-leak loss baseline (29/4/2/-1)
but has zero protected-target arrivals. V10 still leaves civilian #14 blocked by
roadblock #4. Evidence:
`output/r8_1_r8_7_batch_v1/main_08-07/local_device_diagnostic_v10/`.

V11 was generated but failed its `parent_hypothesis_id` contract and was not
simulated. The next tactical request must preserve V10's throughput gains, add a
real #4 clearance responsibility, and solve route-7/8 plus the mid/late leaks.
R8-3/R8-5/R8-6 remain mechanism-blocked; optimization is not started.
