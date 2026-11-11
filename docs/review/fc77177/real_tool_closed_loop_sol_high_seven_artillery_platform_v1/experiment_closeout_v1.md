# R102 artillery-platform closed-loop closeout

## Result

R102 completed the authorized bounded run with two complete fixed-simulator LOSS candidates and no new WIN:

| Candidate | Result | Steward artillery output | Key failures |
|---|---|---|---|
| `R102_SOL_HIGH_SEVEN_ARTILLERY_PLATFORM_001` | 18 kills / 15 leaks, life -14 | 38 hits / 11035.13, last @3937 | Melantha died @2143; Ansel and Steward died @3943; artillery alive at the planned 4280 retreat. |
| `R102_SOL_HIGH_SEVEN_ARTILLERY_PLATFORM_002` | 13 kills / 20 leaks, life -19 | 9 hits / 2466.09, last @2545 | Hibiscus died @2143; Melantha died @2293; Ansel and Steward died @2593. |

Both had 8 death events and 7 unique dead IDs. Neither destroyed roadblocks #1/#2: roadblocks #4/#3 were destroyed @1966/@2404. Protected #3 died @5353/@5341 and #14 died @6314; no protected target reached. Central armor #21/#22/#33/#34 leaked in both, and artillery leaked @5759 in both. C1 had 5 action errors; C2 had 8.

## Targeted learning

C1 tested M70's runtime `(7,5)` platform while replacing Spot with persistent lower-route Melantha and moving central support to Midnight. It did not preserve the platform: shell exposure killed Melantha, then shared support/output exposure killed Ansel and Steward. C2 added actual Hibiscus-to-Melantha healing through the former death window, proving delivery, but introduced earlier healer loss and caused the artillery chain to terminate even sooner.

These observations refute only the two frozen plans. They do not establish role necessity, support impossibility, or that another seven-ID geometry cannot preserve output through M70's observed 4225/4273 hits. Exact HP, full heal eligibility, and continuous positions remain UNKNOWN.

## Integration and budget

All 16 frozen parent identities matched hashes. The frozen selector context was 19,234 bytes with no omission, and suggestions remained M70 plus R100 C1. C1 selected M70; C2 repaired C1 with raw feedback. Visible decision records cited evidence IDs, non-applicable evidence, override reasons, expected events, and refutation conditions. The traceable-input layer succeeded, but tactical effectiveness is not proved by one bounded run.

Actual budget: 1/1 real `gpt-6.1-sol/high` CLI start completed, `features.apps=false`; 2/10 checks; 2/2 candidates; 2/2 completed fixed simulations. No retry/resume/model change occurred. Visible token usage was `UNKNOWN_CLI_INTERNAL`; `cached_input` is an input subset and is never added. The MCP preflight used the exact configured command/args/cwd and did not consume simulation budget. Catalog refresh timeouts occurred but the production session and all four tool types completed.

M70 `R8_7_GPT_M70_V1` remains the eight-ID fixed-simulator WIN. Seven-or-fewer feasibility remains UNKNOWN. No real-game, faithful, robust, probabilistic, seven-ID-impossible, or global-minimum claim is made.
