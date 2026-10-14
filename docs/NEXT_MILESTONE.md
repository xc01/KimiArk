# Next milestone: rerun frozen R8-2 V6 for protected-target zero loss

R8-2 V5 already cleared roadblock #2, delivered #11, and achieved a simulator
WIN with zero leaks. The sole remaining R8-2 tactical target is to prevent
civilian #6's death while preserving that result. The frozen V6 prompt SHA is
`30882fb15d4c5180663adb52cf127bc90bbc62a1021c93421815168985a1f8a1`; retry only
when the Codex workspace route is available, in a new non-overwriting attempt.

SUPERSEDED 2026-10-14: the following R8-7 milestone was archived after the
ghost-block correction invalidated its old failure window.

Do not retry R8-2 V4 or R8-4 V3 without a new plan: their static conflicts are
direct plan defects, not simulator errors. R8-3/R8-5/R8-6 remain BLOCKED until
their route checkpoint semantics are supported. Do not run optimization until
all seven stages have validated WIN, and do not convert any simulator result into
an实机 claim.

## Current milestone: structural R8-2 protected-target rethink

R8-2 V5 remains the immutable best fixed simulator WIN baseline: 36 kills, 0
leaks, 0 operator deaths, life 2, roadblock #2 destroyed at frame 6633, and #11
arrived at frame 6956; #6 died at frame 4604. V6 restored roadblock clearing but
leaked two officers and lost #6. V7 was rejected only for frame-2763 insufficient
DP. V8 preserved roadblock clearing but regressed to 12 leaks, one operator
death, life -10, and #6 death. Stop same-shape retries. The next GPT revision
must redesign the opening interception/officer-throughput balance and the
protection-to-clearance handoff; Python must not select the replacement tactics.

## Current milestone: protect #6 while retaining V14's zero-leak WIN

V14 is the current best fixed R8-2 candidate: simulator WIN, 36 kills, 0 leaks,
0 operator deaths, life 2, roadblock #2 destroyed at frame 6839, and #11 arrived
safely with no damage. Civilian #6 still died at frame 5294 after 13 attacks
while roadblock-held. V15 proved that moving destruction earlier to frame 5911
kept the zero-leak WIN but moved #6 death earlier to frame 4994 and let #11 take
two attacks; this rules out clearance timing as the sole lever. V16's only CLI
process was manually stopped after roughly 26 minutes with no new Codex session
output; it is infrastructure evidence, not a tactical result. The next request
must redesign protection and release as one coupled structure while retaining
V14's zero-leak baseline.

SUPERSEDED 2026-10-14: the old R8-7 V2 loss window above came from ghost-block
pollution. The current bottleneck is the death-unblock-fixed window: two early
guards die, R8-7 first leaks at frame 1289, and first fails at frame 1532. R8-2
also has a direct tactical gap: V1/V3 leave civilian #11 active at roadblock #2
despite zero leaks. Any next GPT revision must address these facts; Python must
not alter actions.

The two new R8-2 GPT-C5 CLI attempts were infrastructure failures
(`workspace routing discovery failed`) and are not tactical feedback.
