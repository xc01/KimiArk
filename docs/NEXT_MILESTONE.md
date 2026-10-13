# Next milestone: Work review, then one tool-enabled bounded revision

The read-only tool loop is now offline-complete. Three whitelisted tools cover
mechanics/stage-fact summaries, configured range coverage, and conditional
SP/DP/deployment checks. A visible base rule card and source/provenance mapping are
stored in `output/r8_1_readonly_tool_loop_v1/`.

The C1 conditional counterexamples were replayed through the common interface:
Hibiscus and Steward do not cover the declared blocking tiles with UP; Lancet-2 at
[2,9] LEFT covers Melantha [1,7] but not Noirc [1,6]; and, under the stated SP
assumptions, Hibiscus is not ready again at frame 4200 because the model-derived
earliest ready frame is about 4500.

The mock trajectory uses two model requests and four tool calls, reuses the preserved
C1 plan as its synthetic final output, and does not create C2. Provider tool
compatibility for kimi-k3 at `/api/plan/v3/responses` remains UNVERIFIED. The next
real experiment, only after Work approval, may use at most 3 actual model requests,
6 read-only tool calls, and 1 final OperationalPlan; every continuation and failure
counts as a request. No automatic retry or stage simulation is authorized.
