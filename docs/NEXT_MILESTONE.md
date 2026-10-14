# Next milestone: revalidate and revise R8-7 under m19.1

R8-2 V15 remains the frozen perfect simulator result for `main_08-02`.
R8-4 V4 is now the frozen best fixed result for `main_08-04`: simulator WIN,
54 kills, 0 leaks, 0 operator deaths, initial life 3 retained, and all three
protected targets safely arrived at frame 5336. Both roadblocks were destroyed;
#2 at frame 4062 and #1 at frame 4644. Evidence:
`output/r8_1_r8_7_batch_v1/main_08-04/local_device_diagnostic_v4/`.

These are `PERFECT_SIMULATOR_WIN_IN_CURRENT_MODEL` claims only. Neither is a
faithful/robust certificate or real-game WIN. Do not spend more GPT calls on
R8-2 or R8-4. The next effective action is to replay saved R8-7 V2 once under
`m19.1-local-device-target-v1`, then feed any new causal failure to GPT for a
tactical revision. R8-3/R8-5/R8-6 remain mechanism-blocked; optimization is not
started.
