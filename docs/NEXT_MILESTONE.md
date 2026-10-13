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

Correction: losslessly wrapping those three strings produced a valid C2. Static compilation now
identifies the concrete blocker: frame 600 Noirc costs 14 DP against a balance of 9. The fixed
timeline remains unchanged, so the 0/1 diagnostic simulation is blocked. The budget remains
exhausted; a future tactical decision belongs to Work/Kimi and must address this conflict or
approve a bounded revision only after reviewing
`output/r8_1_lowstar_c2_compact_tool_revision_v2/static_compile_execution_gate.json`.

Further correction: adding the missed AUTO income removes the static frame-600 blocker. The
authorized 1/1 diagnostic simulation then answered the survival/economy question: LOSS. Fang's
first auto proc occurs at frame 570, but Fang dies at frame 890; route-6 leaks at frame 1295 after
Vanilla dies at frame 1243, and Hibiscus cannot pay at frame 1680. The simulation budget is used.
Future revision decisions must preserve route-6 blocking and account for operator survival; Work
must review
`output/r8_1_lowstar_c2_full_diagnostic_v1/diagnostic_summary.json`
before any next bounded tactical request.

C3 was prepared from this evidence, but both requests ended reasoning-only at the 32,768-token
boundary; `tool_choice=required` did not produce a native function call. The third request was not
spent. Work must review
`output/r8_1_lowstar_c3_failure_revision_v1/provider_failure_analysis.json`
and the raw SSE records before authorizing another protocol shape, a smaller query-only step, or a
different output/reasoning configuration. No C3 compile or simulation is authorized from the saved
reasoning.

## Next bounded GPT execution

The prepared GPT request is frozen in
`output/r8_1_gpt_tactical_revision_v1/llm_request_body.txt`. The next run must set `SUB2API_API_KEY`
externally, execute the existing bounded call at most three requests / six readonly tools, and stop on
the first failure without retry. If a final C3 passes schema and contract checks, compile the original
fixed actions only; no simulation is authorized in this milestone. Provider compatibility remains
UNVERIFIED until a native tool round and successful continuation are observed.

No further GPT call may run from this directory: the persisted STARTED count is 4/3. Work must review
`output/r8_1_gpt_tactical_revision_v1/resume_session.json`,
`invalid_final_plan.json`, and `evidence_numbering_incident.json`. Any later tactical revision needs a
new authorized directory and must explicitly handle the rejected plan's late frame-6090 ordering and
wrong parent identity; it must not repair or replay the invalid output as a valid C3.

The recovered C3 is now a reviewed tactical input, not a successful strategy. Its first concrete model
failure is route-10 at frame 1579. Future work must decide whether Work authorizes a tactical
re-request in a fresh budgeted directory or a bounded mechanism investigation; do not repair the same
plan automatically, expand search, or call GPT without a new Work-approved budget.

The authorized GPT-C4 session has not produced a plan. Its compact request was frozen at 138,957
bytes, then the first HTTP request returned 503 (`43346c70-1bc4-4376-bcf3-212e096dd1a4`). The session
is 1/3 requests, 0/6 tools, 0 plans, and 0 simulations. There was no automatic retry. Work must decide
whether to manually spend one of the two remaining requests in this session or leave it blocked; no
action repair, second plan, search expansion, or simulation is authorized from this failure.

The explicitly authorized attempt-2 recovery reused the same 138,957-byte body and returned HTTP 503
(`47cd2c69-13aa-4a90-b824-4938ae83aadb`). The session is now 2/3 requests, 0/6 tools, 0 plans and 0
simulations. The remaining request is not authorized automatically after this second failure; Work
must review whether the service outage has cleared before spending it.

The separately authorized Codex CLI C4 experiment consumed its one process but did not reach a tactical
turn: workspace routing discovery timed out (`01a13607-f3d3-7ee2-9ccf-751acb5a2dd0`) because the
automation shell did not inherit interactive proxy exports. The runner now supplies explicit local
mihomo proxy defaults, but this consumed session cannot be resumed or retried. Work must authorize a
new CLI directory/budget after reviewing `output/r8_1_gpt_c4_codex_cli_v1/`.

The second authorized CLI attempt reused the same C4 prompt/evidence and confirmed the proxy path
reached OpenAI, but was rejected by `invalid_request_error.invalid_json_schema`: the root output schema
had `additionalProperties=true`, while `--output-schema` requires false. Thread
`01a13615-a7e7-7c60-b818-39f5eea76eb7`; cumulative CLI starts are 2/2. There is no C4 and no simulation.

## 2026-10-14 — Third Codex CLI attempt closed the C4 diagnostic loop

The runner no longer sends `--output-schema`; it preserves `--json`, `--output-last-message`,
`read-only`, explicit proxy variables, and mandatory local schema/contract validation. Targeted pytest
is 17/17 PASS. The third CLI process produced one final C4. Lossless normalization only added
`provenance.revision_source`; no operator, action, frame, tile, direction, or tactical statement changed.
Static checks were 0 conflicts / 0 UNKNOWN.

The one authorized full-stage diagnostic simulation completed as conditional-model LOSS: 49 kills,
7 leaks, 0 operator deaths, and remaining life -2. The first leak is route-10
`enemy_1108_uterer#15`, spawned at frame 1950 and leaked at frame 2179 with no recorded block or damage.
The full leak routes/frames are route-10 2179, route-12 2184, route-11 2629, route-13 2634,
route-23 4555, and route-33 4879/4903. Roadblock-targeting robustness was not evaluated.

Cumulative CLI process starts are now 3/4, final C4 acceptance is 1/1, and the diagnostic simulation
budget is exhausted 1/1. The only remaining CLI startup may not be used to rerun simulation or expand
search. If Work authorizes it, GPT may receive the saved route-10/route-12 opening capacity evidence and
the later leak inventory, then revise the opening blocking/kill-transfer chain once. There is no claim of
real-game outcome or whole-strategy infeasibility.

Evidence integrity caveat: the completed simulation manifest and static certificate record a different
plan-file hash than the current normalized plan (`cd04...` versus `bf3d...`). The current file is
reproducible as raw output plus provenance-only normalization, and its 24-action contract matches the
saved direction-complete candidate; however, byte identity with the simulation-loaded plan is UNPROVEN.
No simulation rerun is authorized or claimed.

## 2026-10-14 — R8-1 batch reached a conditional WIN

The tactical batch runner now accepts source/feedback paths and plan identity as parameters, checks the
prompt body limit, and includes provenance instructions. C5 was recovered offline by adding only the
missing provenance object; C6 and C7 passed without lossless repair. C5 improved 49/7 to 51/5, C6 to
55/1, and C7 to the first fixed full-stage WIN: 56/56 kills, zero leaks, zero operator deaths, and
remaining life 5. The winning squad has 8 operators and star total 22.

This is a conditional current-model WIN only. The same C7 action timeline has not yet been replayed under
the two historically evidenced R8-1 roadblock targeting interpretations, so robust status remains
NOT_EVALUATED. Real-game status remains UNKNOWN. The next direct step is that bounded replay; if both
replays WIN, then Work/GPT optimization may reduce operator count while preserving the saved baseline.

The bounded replay is complete. Variant A made roadblocks not ordinarily targetable; variant B made
them targetable only when no ordinary enemy candidate existed. Both used the exact C7 action contract,
`m11_second_quantized` policy, 30 FPS, and 600-second limit. Both returned 56/56 kills, zero leaks, zero
operator deaths, and remaining life 5. Therefore R8-1 now has a robust roadblock-targeting simulator WIN
within these two variants. This is not a deterministic client claim or real-game win. The next actionable
work is no longer the old civilian field blocker. The NO_DAMAGE attributes are fixed. The direct
blocker is tactical output discipline: GPT repeatedly selects converted roadblock tiles even after
explicit coordinate instructions. Do not rerun without a prompt/contract design that can reject those
choices before another model request.
