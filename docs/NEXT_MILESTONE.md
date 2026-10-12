# Next milestone: Work review of roadblock prefab payload

V2 now extracts the exact `trap_020_roadblock` prefab and connects it to the
focused Tile/SPFA disassembly. Work should review
`output/r8_1_roadblock_prefab_evidence_v2/` and
`scripts/extract_roadblock_prefab_evidence_v2.py`.

If accepted, the next bounded evidence task is to determine whether ordinary
enemy route generation actually calls `SPFA.CheckReachable` with
`avoidObstacleLike=true`, and whether `tap_roadblock` is bound to Ursa
civilians/Talulah in this client. Do not harden a full-obstacle rule, invoke
Kimi, run real-stage simulation, add OperationalPlans/candidates, or expand
tactical search in that follow-up.
