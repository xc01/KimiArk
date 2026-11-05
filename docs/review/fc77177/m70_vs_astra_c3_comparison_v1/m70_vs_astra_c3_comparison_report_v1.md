# M70 V1 versus Astra cold-start C3

## Conclusion

M70 V1 is the archived simulator WIN with 33 kills, 0 leaks, 0 operator deaths, both protected targets reached, and life 3. Astra cold-start attempt3 C3 is a LOSS with 24 kills, 9 leaks, 4 operator deaths, neither protected target reached, and final life -8.

The clearest operational gap is protected-route opening. M70 uses Melantha to destroy roadblock #4 at frame 1966, before protected target #14 spawns. C3 instead has Spot occupy the same tile later and records no roadblock #4 damage or destruction. Consequently, C3 blocks #14 with #4 at frame 3251 and #3 remains blocked by #1 from frame 2773. Artillery then kills both protected targets: #14 at 3943 and #3 at 5353. C3 never reaches a protected target.

The second major gap is artillery removal. M70 kills artillery at frame 4273 after Steward lands 45 damage events totaling 13,227.21. C3 lands 38 Steward damage events totaling 11,035.13 but artillery survives and continues firing. These are arithmetic observations from archived events, not proof that a replacement action would produce a WIN.

## Source and validation

| Target | Plan | Events restored SHA-256 | Result |
|---|---|---|---|
| M70 V1 | `R8_7_GPT_M70_V1` | `e1464dfc9268ab6ca0bb84fdda61d221e48fc1c57133f2b82d6c344afadb40c8` | WIN, life 3 |
| C3 | `R87_ASTRA_HIGH_COLD_START_003` | `c431deefb5d1fafd4c11027b2ae2f6b2b003b4f74105439bfa6a6e104884ad62` | LOSS, life -8 |

Both sources declare mechanics `m38b-2781-animation-speed-v1`; both manifests match their plan, action snapshot, evidence context, structured output, and event archives. The comparison script also verifies manifest hashes before recomputing statistics.

Plan coordinates are stored as `[row,col]`; DEPLOY runtime events and replay display use `[col,row]`. This conversion is explicit in both the JSON and the replay tool.

## Roster and earliest action divergence

- Shared seven IDs: Fang, Friston-3, Midn, Ansel, Hibiscus, Spot, Steward.
- M70 additionally has Melantha.
- C3 is the seven-ID subset without Melantha, not a mechanical removal of one person selected by this analysis.
- The first three deployments are identical: Fang `[3,5]` at 0, Friston-3 `[4,5]` at 91, and Midn `[1,5]` at 571.
- The earliest aligned divergence is frame 841 versus 901: M70 deploys Melantha at runtime tile `[5,6]`, while C3 deploys Spot there. M70 later retreats Melantha at 2054, deploys Steward at 2071, then deploys Spot at 2341. C3 keeps Spot at that position from 901.

## Stage comparison

### Opening through first artillery

M70's Melantha begins hitting roadblock #4 at 841 and destroys it at 1966 with 15 observed hits totaling 8,358.56. This opens #14's route before its frame-3030 spawn. Midn independently destroys roadblock #3 at 2404 in both plans.

C3 retains the same Midn/#3 opening but has no #4 damage, so it cannot pass the upper protected route. This is the first directly observed acceptance-critical divergence, even though the action difference occurs much earlier.

### Artillery window

The first two shell outcomes materially diverge:

| Item | M70 | C3 |
|---|---:|---:|
| First shell start | 1893 | 1893 |
| First shell target/hit | Melantha, 845 | Spot, 558 |
| Second shell start | 2043 | 2043 |
| Second shell hits | none recorded | Ansel + Steward, 1,801 |

The archived `PROJECTILE_BORN` events show the second shell locking `[6,5]`; Melantha has already retreated in M70, while C3 still has Spot there. This supports a precise risk difference at that window, but does not prove that keeping or removing Melantha uniquely determines the later outcome.

M70 removes artillery at 4273. C3's artillery survives past 5253, hits multiple operators and protected targets, and leaks at 5759. The read-only statistics do not claim that earlier artillery death alone is sufficient; leaks and central pressure also differ.

### Central pressure and key enemies

In M70, #21, #22, #28, #31, #33, and #34 all have final `ENEMY_DEATH` events. In C3, the same six IDs all have final `ENEMY_LEAK` events. Their C3 damage-taken values are drastically lower: for example #21 takes 287.70 versus M70's 5,106.92, and #34 takes 1,270.29 versus M70's 5,092.32. This identifies a broad failure of output contact and blocking, not merely a single late death.

C3's first operator death is Steward at 3943; its first leak is #22 at 5196. The protected-passage failure at 3251 precedes both.

### Protected targets and roadblocks

| Route state | M70 | C3 |
|---|---|---|
| Roadblock #4 | destroyed by Melantha at 1966 | never damaged/destroyed |
| Roadblock #3 | destroyed by Midn at 2404 | destroyed by Midn at 2404 |
| #14 | reaches at 11119 | blocked by #4 at 3251, dies to artillery at 3943 |
| #3 | reaches at 11349 | blocked by #1 from 2773, dies to artillery at 5353 |
| Roadblock #2 | destroyed by Melantha at 10787 | no recorded destruction |
| Roadblock #1 | destroyed by Steward at 11017 | no recorded destruction |

## Contribution comparison

Total damage values are descriptive, not a ranking of tactical value.

| Operator | M70 damage dealt | M70 damage taken | C3 damage dealt | C3 damage taken |
|---|---:|---:|---:|---:|
| Fang | 17,538.75 | 6,090.00 | 14,113.75 | 3,130.00 |
| Friston-3 | 4,098.40 | 17,510.00 | 2,569.90 | 3,300.00 |
| Midn | 51,798.74 | 2,222.00 | 45,133.71 | 2,288.00 |
| Melantha | 24,312.36 | 1,600.00 | absent | absent |
| Ansel | 0.00 | 1,360.00 | 0.00 | 2,720.00 |
| Hibiscus | 0.00 | 1,360.00 | 0.00 | 680.00 |
| Spot | 13,090.00 | 1,831.50 | 23,920.00 | 3,429.00 |
| Steward | 22,289.47 | 0.00 | 12,753.92 | 578.00 |

The relevant question is not “add Melantha back” but whether a seven-ID structure can supply the same early #4 opening and roadblock clearing while retaining enough artillery and central output. No authorized replacement simulation was run.

## Causal boundary

Observed chain in C3: no #4 destruction → #14 blocked at 3251 → artillery damages #14 at 3643/3793/3943 → #14 dies at 3943; separately, #3 is blocked by #1 at 2773 → artillery damages #3 at 5053/5203/5353 → #3 dies at 5353. Each arrow is supported by archived events. This is a causal chain, not a proof of unique root cause.

Isolated arithmetic conditions include:

- Destroying #4 before 3251 would remove that observed BLOCK in the counterfactual.
- Killing artillery before its 3943 shell would remove the observed 950 hit and #14 death under that isolated assumption.
- Removing artillery after 3943 would remove the observed 950 hits to #3 at 5053/5203/5353, but does not remove leaks or establish WIN.

No ablation, replacement simulation, tactical search, or model call was run.

## Replay evidence

`replay_frame_evidence_v1.txt` contains non-TTY frames from the existing event-accurate replay tool. It uses discrete archived state and locked artillery points only; absent enemy continuous positions remain UNKNOWN rather than being interpolated.

M70 frames: 1893, 1993, 2053, 2093. C3 frames: 1893, 1993, 2053, 2143, 3793, 3943. These cover the first shells, Melantha retreat/Spot timing, and the C3 protected-target artillery window.

## Next validation questions

1. Which window can supply 8,358.56 physical damage to roadblock #4 without starving the artillery-kill chain?
2. How much Steward contact is needed before the frame-4273-equivalent kill point, and which operator supplies it if Melantha is absent?
3. Can a lower-central blocker also open #4/#2/#1 while avoiding the C3 artillery cluster around `[6,5]`, `[7,5]`, and `[6.6,6]`?

All three are bounded hypotheses for later model-directed work, not recommended plans or validated replacements.
