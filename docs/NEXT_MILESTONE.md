# Next milestone: close the corrected R8-7 opening, not repeat R8-2/R8-4 shapes

The immediate bottleneck is R8-7 V2's early leak of `enemy_1108_uterer#4` at
frame 1289 and objective failure at frame 1532. Although V2 improved to 13
kills/20 leaks/2 deaths/life -17, its own hypothesis flags temporary blocker
survival and the patrol damage budget as unresolved. The next tactical request,
if authorized, must be a structural R8-7 opening revision focused on these
specific bottlenecks and the saved local failure window; Python must not move its
actions.

Do not retry R8-2 V4 or R8-4 V3 without a new plan: their static conflicts are
direct plan defects, not simulator errors. R8-3/R8-5/R8-6 remain BLOCKED until
their route checkpoint semantics are supported. Do not run optimization until
all seven stages have validated WIN, and do not convert any simulator result into
an实机 claim.

SUPERSEDED 2026-10-14: the old R8-7 V2 loss window above came from ghost-block
pollution. The current bottleneck is the death-unblock-fixed window: two early
guards die, R8-7 first leaks at frame 1289, and first fails at frame 1532. R8-2
also has a direct tactical gap: V1/V3 leave civilian #11 active at roadblock #2
despite zero leaks. Any next GPT revision must address these facts; Python must
not alter actions.
