# M68 Closeout

M68 did not produce an 8-ID current-model fixed-simulator WIN. The best verified result remains the frozen M52 V1 **9-ID WIN**. Budget ended at **CLI 3/3** and **simulation 2/3**; the unused third simulation did not transfer. Internal model request count remains `UNKNOWN_CLI_INTERNAL`.

## Loops

1. **V1 — `M68_EARLY_HIBISC_RESERVED_SPOT_CASTER_ROTATION`**: 31 actions, 8 IDs. Contract, execution input, and static checks passed with 0 conflicts/unknowns. LOSS: 24 kills / 9 leaks / 5 deaths / life -7. Steward died@2593 after two 910 artillery hits. Hibiscus, Friston, Fang, and Melantha died at 4543/4768/4954/5356. Fang unblocked #21 and Melantha unblocked #22 on death. Protected #3 died@5353, artillery leaked@5759, and #34 leaked@6996 with zero BLOCK and only 49.7 Midnight damage.
2. **V2 — `M68_SEPARATED_EAST_EARLY_CASTER`**: 30 actions, 8 IDs. Contract, execution input, and static checks passed with 0 conflicts/unknowns. LOSS: 19 kills / 14 leaks / 9 deaths / life -13. The earliest break moved to Spot: artillery splash 558@4060 plus officer ticks killed him@4119, releasing #16/#18; they leaked at 4506/4491. Steward died@2743 after two 910 artillery hits and dealt only 3686.68 to artillery. Neither protected target reached; roadblocks #1/#2 were not destroyed.
3. **V3 — `M68_PROJECTILE_LOCK_MEDICAL_STAGGER`**: real CLI start counted 3/3. The model produced a structured 31-action/8-ID plan, but contract validation failed because `revision_hypothesis.expected_first_observable_event.event_type` was unsupported `PROJECTILE_BORN`. No static gate, simulation reservation, `Simulator.run`, battle event, WIN/LOSS, or tactical LOSS followed.

No 8-ID impossibility, operator-uselessness, real-game, faithful, robustness, probability, or global-minimality claim follows.
