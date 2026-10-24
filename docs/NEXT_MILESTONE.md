# Next milestone: M48 requires fresh authorization

M47 is closed at its own budget: **3/3** real tactical CLI starts and **1/3**
fixed `main_08-07` simulations. Its static-clean V2 used 53 actions and
simulated as a LOSS: 23 kills, 10 leaks, 8 operator deaths, and life -7. It did
close roadblock #2 and safely reach protected targets #3 and #14, but lost the
late base after all eight deaths preceded the first leak. `enemy_1107_uoffcr#20`
and armored #21 leaked together at 5046, after Spot died to #21 at 4668; #22
leaked at 5196. Artillery #0 still leaked at 5759 with 993.38 HP remaining, and
armored #34 leaked at 6996 with no recorded damage or block.

The focused `tactical_experience_v1.py` matcher regression passes 22/22 and now
supports explicit `DEVICE_DAMAGE`/`DEVICE_DESTROYED` while preserving illegal
DEPLOY/RETREAT/SKILL rejection and missing-`legal` compatibility. Evidence,
hashes, and compact V2 feedback are under
`docs/review/fc77177/m47_remaining_gaps_closure_v1/`.

A fresh M48 authorization is required before any new tactical CLI or simulation.
Its bounded first task is a GPT revision that repairs the earlier medical
survival chain (Ansel 3011/3013/3161, Hibiscus 3970, Steward 4120), maintains
interception under #20/#21/#22 pressure before 5196, and coordinates a surviving
artillery kill before the plan-specific recalculation of the old 5759 window. It
must also produce a real kill/no-leak plan for #34, not a single hit prediction,
while preserving the verified roadblock-#2 and protected-target duties when
supported. M42 residual simulations and all prior stage balances, including
M45/M46's unspent simulations, remain non-transferable.
