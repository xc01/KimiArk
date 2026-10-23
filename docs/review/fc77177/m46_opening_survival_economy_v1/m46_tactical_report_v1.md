# M46 tactical report

## Scope and closure

M46 used `m38b-2781-animation-speed-v1` with 3/3 real tactical Codex CLI starts
and 2/3 fixed `main_08-07` simulations. The V3 CLI timed out after 3600 seconds
without producing a plan, so the remaining simulation could not be lawfully used
without creating a new plan. M46 is a conditional fixed-model LOSS and makes no
real-game, faithful, robust, or probabilistic claim. The baseline repository SHA
was `426cfd7f450bb6a9373bd55c12fef9c0e8ef10bd`.

## Iterations

- **V1** passed contract and static checks with 42 actions. It eliminated the M45
  `enemy_1107_uoffcr#6` failure by having Fang block at 1208 and the enemy die at
  1703, and preserved Melantha's `#5` block/kill at 1071/1251. But the full result
  regressed to 16 kills, 17 leaks, 12 operator deaths, life -15, and first leak
  `enemy_1107_uoffcr#15` at 4176. Midnight died and released the route-17 enemy;
  no successor covered the route.
- **V2** passed contract and static checks with 39 actions. It improved to 31
  kills, 2 leaks, 7 operator deaths, and life 1, while protected #3 reached at
  4991. It still failed the joint target because artillery leaked at 5759 after
  receiving 5817.58 damage, #14 remained restrained by roadblock #2 and never
  reached, and `enemy_1110_uamord#34` leaked at 6996 after receiving 704.85
  damage. Lancet's retreat failed because it had died at 2980.
- **V3** timed out at 3/3 CLI without a plan; no simulation was started.

## Evidence and next bounded task

Raw prompts/responses, starts, plans, static results, simulations, compressed
event/summary artifacts, and hashes are under `evidence/` in this directory. A
new authorization is required before another CLI or simulation. The next stage
should use M46 V2 as the parent comparison, preserve the verified opening and
route-17 improvements, and close the three explicit gaps: artillery death, #14
safe arrival after controlled release of roadblock #2, and armored route-29 #34
death.
