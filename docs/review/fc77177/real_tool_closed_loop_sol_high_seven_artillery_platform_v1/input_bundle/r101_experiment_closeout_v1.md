# R101 selector-feedback closeout

## Result

The independent ledger used one fresh `gpt-6.1-sol/high` CLI with
`features.apps=false`, mechanics `m38b-2781-animation-speed-v1`, and K=7. Final
budget was CLI 1/1, checks 3/10, candidates 2/2, and complete simulations 2/2.
The process completed with exit 0 and `turn.completed`. There was no
seven-operator WIN, so seven-or-fewer feasibility remains UNKNOWN and M70
remains the eight-operator fixed-simulator WIN.

| Candidate | Plan | Result | Deaths/events/unique | Errors |
|---|---|---|---|---:|
| C1 | `R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_001` | 14 kill / 19 leak / life -18 | 8 / 7 | 7 |
| C2 | `R101_SOL_HIGH_SEVEN_SELECTOR_FEEDBACK_002` | 20 kill / 13 leak / life -11 | 4 / 4 | 4 |

C1 froze candidate SHA-256
`0b47f3cb14f82327f09899d6e7bc76c67d153a292bd6b72c07ffb2f38d4629f3`; C2 froze
`0b0ec4e8041188b3df7faa6371abaa3e6acb17c7643d5a939f1fc4e627c01684`.

## Feedback and decisions

The frozen 14-record context suggested M70 and R100 C1. C1 visibly overrode the
selector and chose R100 C2, citing the R100 C1 runner-#4 leak, R100 C2's route
observations, and R100 C2's failed artillery/heal sequence. This override is
traceable, but the resulting LOSS does not prove the override was bad. C2
continued exact C1 lineage using raw C1 feedback because runtime selector
re-import was not supported; no selector algorithm was restarted or changed
during the session.

C1's first observed executor break was Ansel death@2293; Steward died@2443.
C2 moved support/output geometry and increased healing, but Friston
died@2111. Steward stayed alive to a scheduled retreat@4200 and delivered
43 artillery hits/12,504.82 damage without killing artillery. Thus both
directions were tested: short exposure with delivered support did not close, and
long survival with much larger output also did not close. Exact HP, full eligible
heal ordering, and continuous positions remain UNKNOWN.

## Terminal duties

C1: protected #3 died@5341, #14 died@6314; artillery leaked@5759; armor
#21/#22/#33/#34 leaked. C2: protected #3 died@3311, #14 reached alive@12448;
artillery leaked@5759; the same four armor IDs leaked. C2 cleared roadblocks
#4/#3/#2 but not #1. No active enemies or remaining HP existed at settlement,
but leaks and protected failures make both complete LOSS.

## Selector layer

Input manifest had 66 matching files before the CLI. Zero-model MCP
initialize/initialized/tools/list/read-only status passed with the exact Codex
command/args/cwd. Both decision records were present and parent hashes were
consistent. Post-run import added two verified records to a 16-record store with
no issues. With the same retrieval tags as the frozen context, neither R101
record entered the next suggested-parent set; both remain retained partial
branches. No scoring weight was changed.

Visible usage from `turn.completed` was input 1,485,606; cached input 1,396,352;
output 15,799; reasoning output 3,282. Cached input is an input subset.
Internal model requests remain `UNKNOWN_CLI_INTERNAL`.
