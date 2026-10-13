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

Before any real tool session, Work must review the V2 continuation fix in
`output/r8_1_readonly_tool_loop_fix_v2/`. Current kimi-k3 compatibility at
`/api/plan/v3/responses` is still UNVERIFIED, so the first real request must be
treated as a protocol probe and must not be retried. The same budget remains:
at most 3 model requests including continuations, 6 read-only tool calls, and
1 final OperationalPlan.

The non-tactical protocol probe has now succeeded, but it does not authorize C2.
Work should review the real request/response pair, call_id association, output
budget and DP/test fixes before approving a bounded tactical tool session. That
session remains at most 3 model requests including continuations, 6 read-only tool
calls, 1 final OperationalPlan, no automatic retry, and full tactical schema/contract
validation.

The first bounded C2 session has failed and stopped at one model request and zero
executed tools. The assistant text claimed six tool calls, but the response contained
no native `function_call` items; its text also failed the root operational-plan
schema. No C2, static compile, simulation, or tactical-feasibility conclusion exists.
Work must review the raw response and decide whether to authorize a new bounded
attempt with changed instructions or provider/tool handling; this session must not
be retried.

The compact V2 attempt also stopped after one request. It reduced the body to 127,262
bytes and removed the stale 0-941 window, but the 4096-token query response ended
incomplete with 4,093 reasoning tokens, no assistant message, and no native function
call. No C2, compile, or simulation is authorized from this evidence. Work must review
the raw response and budget shape before another bounded session; this failed session
remains 1/3 requests and 0/6 tools.

V2 reached a native tool round at 32768 output tokens, but stopped before its final
continuation because that payload was 148,762 bytes against the 140,000-byte gate.
Five range queries were invalid for incomplete configuration objects; one timing query
executed. No C2, static compile, or simulation is authorized. Work must review the
blocked continuation and decide whether a later bounded session may compress tool-result
context, provide a stricter configuration template, or adjust the transport limit; this
session remains 2/3 counted requests and 1/6 executed tools.

The saved-call resume completed five range revalidations and one final HTTP continuation,
but the returned JSON failed only the declared `verification_questions` object schema. The
budget is now exhausted at 3/3 counted requests and 6/6 executed tools; no retry, compile,
or simulation is authorized. Work must review `resume_evidence_analysis.json` and the raw
final response before deciding whether a future session may reuse the verified tool facts
under a corrected output contract.
