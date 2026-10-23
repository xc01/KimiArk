# Next milestone: M48 requires fresh authorization

M47 is closed at its own budget: **3/3** real tactical CLI starts and **1/3**
fixed `main_08-07` simulations. Its static-clean V2 used 53 actions and
simulated as a LOSS: 23 kills, 10 leaks, 8 operator deaths, and life -7. It did
close roadblock #2 and safely reach protected targets #3 and #14, but late
survival/DP collapse caused the first leak at frame 5046. Artillery #0 still
leaked at 5759 with 993.38 HP remaining, and armored #34 leaked at 6996 with no
recorded damage or block.

The focused `tactical_experience_v1.py` matcher regression passes 22/22 and now
supports explicit `DEVICE_DAMAGE`/`DEVICE_DESTROYED` while preserving illegal
DEPLOY/RETREAT/SKILL rejection and missing-`legal` compatibility. Evidence,
hashes, and compact V2 feedback are under
`docs/review/fc77177/m47_remaining_gaps_closure_v1/`.

A fresh M48 authorization is required before any new tactical CLI or simulation.
Its bounded first task is a GPT revision that co-plans operator survival, DP and
successor continuity after frame 4410 with a survivor-coordinated artillery kill
before 5759 and real damage or blocking for route-29 #34, while preserving the
verified roadblock-#2 and protected-target duties when supported. M42 residual
simulations and all prior stage balances remain non-transferable.
