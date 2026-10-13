# Milestones

## M15.2 status

Quantified frontier-requirement repair for stage 6-8 is complete. It used no
LLM calls or mechanics expansion, retained K<=7, and used current PRTS-backed
semantics. The preserved frame-564 route-2 enemy received six physical hits
(2031 damage) and leaked with 1119 HP; that value remains candidate-specific.
Fifty-one local candidates were analyzed, 37 rejected by DP/legality, and 37
unique full simulations (10 cache hits) ran. Three solved route-2 locally but
reintroduced an earlier route-0/route-3 frontier. The best stayed LOSS 24/36,
12 leaks, life -9 at frame 564, so
`FRONTIER_REQUIREMENT_SOLVING=INCONCLUSIVE`; no WIN or minimality claim was
made. Artifacts: `output/m15/main_06-07/m15_2_*.json`.

## M15.3 status

Multi-frontier/resource conflict analysis for 6-8 is complete. The run used
zero LLM calls, no mechanics expansion, K<=7, and no minimization. It preserved
the M15.2 parent plus three route-2-success counterexamples, generated
provenance-bearing route constraints and a resource conflict graph, and tested
71 local repairs in 72 unique simulations (77 cache hits). Route-2-success
variants changed Falco's opening placement/facing and exposed route-0/route-3
or route-4 failures. The best remained LOSS 25/36 kills, 11 leaks, life -8,
with route-2 frame 564 damage insufficiency. Both
`MULTI_FRONTIER_CONSTRAINT_SOLVING` and `RESOURCE_CONFLICT_ANALYSIS` are
`INCONCLUSIVE`; no WIN, infeasibility proof, or minimum claim was made.
Artifacts: `output/m15/main_06-07/m15_3_*.json`.

Completed:

1. Real GameData archaeology: traced canonical operator, enemy, and stage sources.
1.5. Client mechanics archaeology: bounded static evidence for event phases and known unknowns.
2. Synthetic simulator foundation: movement, deployment, blocking, damage, and explicit events.
3. Synthetic search: deterministic score/evaluate/search loop.
4. Synthetic combat runtime: SP, skills, healing, enemy attacks, death, retreat, and redeploy.
5. Real GameData simulation adapter: strict provenance-aware structural loading with execution refusal.
6. Explicit approximate-real 0-1 loop: opt-in policy, source-backed fixture conversion, and a fixed calibration run.
7. Minimal approximate-real 0-1 search: deterministic deployment-only beam search over a fixed four-operator pool.
8. Real-game execution/calibration scaffold: guarded ADB interface, coordinate template, dry-run traces, and evidence-aware comparison.
9. Integer-frame action timeline and bounded client timing archaeology: frame-aware 0-1 search, timeline export, and explicit unknown frame-clock evidence.
10. Minimum-squad/minimum-rarity benchmark foundation: GameData rarity and low-rarity censuses, reusable bounded manual-skill interpreter, lexicographic optimizer, benchmark compatibility matrix, and human validation records.
11. First meaningful Chapter 6–11 benchmark: canonical bottom-left stage mapping, explicit route waits/second-quantized spawning, a MID-stage 6-8 approximate fixture with bounded enemy range, and cardinality-first `NO_WIN_FOUND` diagnostics.
12. Full eligible 1–3★ census and runtime coverage boundary: 34 operators censused, 22 executable under the bounded basic-combat policy, reusable Arts tagging, and deterministic full-pool 6-8 search (currently `NO_WIN_FOUND`).
13. Full-pool low-rarity audit and layered small-team search: concrete blockers for all 34 records, high-progression exact-keyframe loadouts, 100% K1/K2 composition coverage, and bounded 6-8 tactical evaluation (`BEST_FOUND_UNDER_BUDGET`, no win).
14. Real LLM tactical-hypothesis pilot scaffold: deterministic StageAnalysis/requirements, strict hypothesis schema, MockLLM default, and opt-in bounded provider runtime.

M14.1 initial real pilot completed on the host terminal: six schema-valid
hypotheses were returned and evaluated deterministically. M14.2 corrected a
best-LOSS aggregation bug, establishing real attack/damage/death evidence but
no 6-8 win. M14.3 made one successful host-terminal revision call (four
schema-valid K=6/7 hypotheses); the normal K<=3 grounder correctly rejects
them rather than truncating them. M14.4 separately validated that cardinality
signal with zero LLM calls: only each exact-K structure plus one K-1 ablation
were tested (eight teams, 352 simulations, budget 500). R1 K6 and R4 K7
reached 19 kills/17 leaks versus the initial K<=3 best's 7 kills/29 leaks, but
no candidate won. This supports a current-planner K<=3 constraint as a search
limitation; it does not claim that 6-8 requires >3 operators, nor a minimum
squad/rarity. M14 stops here; no further LLM call is authorized.

M14.5 performed a separately requested feasibility-first local repair with
zero LLM calls and without adding an eighth operator. It used R1 K6/R4 K7 as
fixed tactical priors, diagnosed early leaks before frontline deployment, and
mutated only their local team/position/facing/order/timing/available-skill
neighborhood (407 simulations, budget 1500). R4 improved from 19 kills/17
leaks to 26/10 but remained LOSS; frame-336 first leakage persisted. The local
neighborhood plateaued, no timeline or minimality claim was produced, and M14
remains stopped.

M14.6 then isolated only R4's K7 opening (zero LLM calls; frame 0--900).
Source-backed DP timing showed why it is constrained: the two 18-DP defenders
can first deploy at frames 240 and 780, while distinct route-0/2 wolves reach
defense tiles at frames 244 and 274. Correcting Beagle from route-2 row 4 to
route-0 row 3 moves the earliest leak 336→366, proving the first leak is
preventable but not yielding a zero-leak fixed-R4 opening (best 3 leaks, 2
kills). A justified one-for-one Stward→Noir Corne K7 ablation improves that
opening to 2 leaks but still loses. The best promoted full battle is below the
preserved 26/10 baseline, so no WIN, timeline, minimisation claim, or further
LLM call was produced. The bounded opening result supports current
`opening_capability_pressure`, not a stage minimum-cardinality conclusion.

M14.7 performed only constrained R4 K7 roster repair (again zero LLM calls).
All 22 executable operators received source-backed opening signatures; no
currently supported runtime mechanism accelerates DP. Event attribution marked
Steward as the sole evidence-directed replaceable R4 slot. Eight lower-cost
ground replacements were re-scheduled from the opening and then selectively
promoted. Replacing Steward with Plume retained K7/20★ and improved the full
LOSS from 26 kills/10 leaks/life -7 to 27/9/-6, with first leak delayed to 366,
but its opening still leaked twice. Because that is a credible one-slot
improvement, the requested condition for a two-slot phase was not met. This is
`OPENING_ECONOMY_REPAIR=INCONCLUSIVE`, not a WIN/minimality conclusion; M14
remains stopped with no further LLM call authorized.

M14.8 tested the distinct opening-geometry question without LLM calls or
roster/cardinality changes. Route-0 and route-2 are adjacent parallel rows,
not convergent paths: they have no common tiles but exact rotated ranges do
allow one unit to interact with both. All 152 meaningful earliest-legal
single-deployment openings and 317 bounded shared/mixed structures were
evaluated; none beat 3 opening leaks or pushed the first leak later than frame
366. Six were promoted to full battle; the best was LOSS 24/36 kills, 12
leaks, life -9, below the preserved M14.7 27/9/-6 frontier. The result is
`SHARED_OPENING_GEOMETRY=NOT_SUPPORTED` for preventing the early leaks under
this fixed K7 roster, not a claim that shared coverage does not exist. There
is no verified opening prefix, simulator WIN, timeline, or minimality claim.

M14.9 was a fidelity audit rather than a strategy search. It audited all 34
eligible low-rarity records and added only source-explicit reusable opening
economy support: automatic/manual time-SP DP grants and self deployment-cost
modifiers. Fang can now deploy at frame 0 via its phase-1 -1 cost talent, while
its automatic +6 DP occurs at frame 570; Vanilla's manual +6 DP occurs at frame
450. Coupled blocked DP talents remain unsupported. Fixed causal checks confirm
the new effects change their legal deployment/DP state, but no new DP gain
arrives before the 6-8 frame-244/274 deadlines; two 18-DP blockers remain frame
240 then 780. Therefore `OPENING_ECONOMY_FIDELITY_GAP=FOUND_BUT_NOT_MATERIAL`.
No LLM call, broad search, roster expansion, WIN, or minimality claim occurred.

15. Constraint-guided feasibility planner: a bounded no-LLM 6-8 search over
the 22 executable low-rarity operators. It introduces provenance-bearing
`TacticalConstraint` and `FailureFrontier` records, partial strategies,
exact-DP prechecks, constraint-aware legal spatial grounding, and recorded
successful-prefix freezing/invalidation. With beam 16, K<=7, and a 2,000
simulation cap, it independently matched the preserved M14 frontier at LOSS
27/36 kills, nine leaks, first leak frame 366, life -6 after 110 unique
simulations. `CONSTRAINT_GUIDED_SEARCH=MATCHED`; no WIN, timeline,
minimality claim, mechanics expansion, or LLM call occurred.

15.1. Closed-loop FailureFrontier repair: preserved the exact M15 27/9 parent,
derived a frame-366 route-2 `INTERACTION_TOO_LATE` constraint from simulation
events, and applied bounded dependency-local timing, spatial, order, and
operator reassignment repairs. Guided repair used 600 unique simulations and
the same-primitives unguided control used 200; both reached the identical
frame-564 route-2 `DAMAGE_INSUFFICIENT` frontier at LOSS 24/36 kills and 12
leaks. `FAILURE_FRONTIER_REPAIR=NOT_SUPPORTED` for this bounded efficiency
comparison. No LLM call, mechanics expansion, WIN, timeline, or minimization
occurred.

19. Uncertainty-guarded causal repair search: bounded no-LLM pilot using
preserved M15 seeds and causal Falco interventions. Three targeting-sensitive
interventions were classified UNKNOWN and simulated; four unique simulations
ran. Best LOSS was K7, 25 kills/11 leaks at route-2 frame 564, matching the
prior frontier. Guard routing is supported; no WIN, infeasibility, mechanics,
cardinality, or minimization claim was made.

18.1. Targeting uncertainty boundary: retained a causal slice of 50 M16
target decisions, with 45 classified unresolved/decision-sensitive. M17
constraints and interference relations now carry targeting sensitivity where
causally connected. Readiness is `READY_WITH_UNCERTAINTY_GUARD`; analytic
monotonic-damage repairs are forbidden and UNKNOWN interventions require
simulation. No search, network, LLM, or mechanics expansion was performed.

18. Targeting mechanics fidelity closure: audited the PRTS targeting/aggro
snapshot and added runtime `TARGET_SELECTION` diagnostics without strategy
search. Current covered-enemy selection (route progress then spawn index) is
only partially aligned with the broader PRTS aggro/filter model; retention and
exact filter semantics remain unresolved. M16's Falco non-monotonic result was
replayed and preserved (24/12 versus 26/10), and M17 remains supported with
explicit mechanics sensitivity. No unrelated mechanics, K, or optimization
changes were made.

17. Causal-temporal constraint representation: added deterministic
`CausalTemporalConstraint`, interference relations, M16 evidence conversion,
and a SAFE/UNKNOWN/UNSAFE local-intervention boundary. Twenty changed enemy
outcomes and 19 interference relations were represented. The old
`DAMAGE_BEFORE(route2, 564)` requirement now preserves target-allocation and
downstream context; restoring Falco damage is correctly classified UNSAFE.
No search, LLM call, mechanics expansion, K change, minimization, or WIN
attempt occurred.

15.4. Falco critical-resource decoupling audit: preserved the M15.2 parent and
three route-2-success counterexamples under the current PRTS-backed runtime.
Falco route contributions, remove-Falco controls, and the required A/B/C
comparison were recorded in seven bounded simulations. The original A case
remained best (LOSS 24/36 kills, 12 leaks); specialized and decoupled cases
regressed earlier route frontiers. `CRITICAL_RESOURCE_DECOUPLING`,
`CRITICAL_RESOURCE_OVERLOAD`, and `K7_CARDINALITY_PRESSURE` remain
`INCONCLUSIVE`. No LLM call, mechanics expansion, WIN, timeline, or
minimization occurred.

16. Causal combat / non-monotonicity audit: paired replay of the M15.2 parent
with only Falco damage disabled. Intervention isolation was verified. Falco
enabled produced LOSS 24 kills/12 leaks/life -9; disabled produced LOSS 26
kills/10 leaks/life -7. The first divergence was the expected Falco attack at
frame 210, followed by changed target/attack allocation and kill timing. Three
leaks were prevented and an A-only kill was exchanged for three B-only kills,
yielding the net +2. `NON_MONOTONICITY_CAUSE` is
TARGET_SELECTION_NON_MONOTONICITY plus ATTACK_ALLOCATION_NON_MONOTONICITY;
the local damage monotonicity assumption is UNSAFE. No search, LLM,
mechanics expansion, cardinality change, minimization, or WIN claim occurred.

20. Constraint-to-capability intervention synthesis: derived two route-2
capability requirements, matched 12 executable operators, and generated 10
semantically distinct interventions across five templates. Candidates remained
UNKNOWN under the targeting guard; no broad search or validation campaign ran.
`CONSTRAINT_TO_CAPABILITY=SUPPORTED`, `CAPABILITY_TO_INTERVENTION=SUPPORTED`,
`INTERVENTION_DIVERSITY=SUFFICIENT`.

21. Information-efficient causal search: evaluated eight unique simulations
from a five-family M20 intervention queue under the M18.1 uncertainty guard.
Targeting-sensitive interventions remained UNKNOWN and were simulated; no
frontier advance or WIN occurred. Best LOSS remained 25/36 kills, 11 leaks at
route-2 frame 564. The guarded information-routing pipeline is supported, but
the causal frontier did not improve.

Next major milestones, only when separately requested:

23. Target-allocation black-box calibration Phase A: generated three minimal
human observation questions for Falco first target, Noir Blade first target,
and Falco retargeting. No real observations, simulator changes, search, LLM,
or mechanics expansion were performed. Status is
`WAITING_FOR_REAL_GAME_OBSERVATION`.

18.2. Targeting PRTS path-distance correction rebaseline: cached the local
仇恨 source and changed ordinary target ordering to remaining route/path
distance with creation-order ties. The paired replay became A 15/21 and B
19/17; historical M16 is `CHANGED`, while non-monotonicity remains. Full aggro,
special filters, and retarget timing stay unresolved, so M23 Q1–Q3 remain
real-game calibration questions.

- establish specific real-mechanic evidence or clearly opt-in approximations;
- evaluate and refine one documented approximation at a time before extending real-stage coverage;
- compare the same bounded real-stage search as individual approximations are replaced or validated;
- if separately requested, perform one manually calibrated bounded real run and compare its trace without auto-fitting;
- recover or validate one client timing boundary before treating configured frame frequency as real-client timing;
- establish one explicit per-stage Chapter 6–11 approximation policy before any low-rarity real-stage search claim;
- investigate target-driven low-rarity mechanics (notably Arts/skill/DP coverage) before revisiting 6-8; do not claim a minimum squad from the bounded result;
- keep Agent integration and game execution separate from simulator-fidelity work.
- extend only target-driven mechanics or tactical coverage before making any M14 claim; current K2 timing coverage is intentionally incomplete.

## Architecture restoration status

Completed as a non-strategy architecture task:

- restored a reusable top-down planner orchestration with deterministic,
  no-LLM hypothesis generation;
- repositioned M15-M22 frontier/causal tools as downstream repair layers;
- introduced explicit `ExperimentScope` so 6-8, K<=7, and the 1-3 star pool are
  benchmark bounds rather than global planner properties;
- strengthened mechanics evidence retrieval, UNKNOWN, mechanics-work, and
  human-calibration gates with machine-readable reason trails;
- resolved Q2 from cached PRTS evidence and implemented ordinary melee
  self-blocked target priority;
- preserved remaining-path targeting and stable creation-order tie breaking;
- marked all M14-M23 numerical artifacts stale under
  `m18.2-blocked-target-v1`;
- ran a tiny stage 0-1 top-down smoke (WIN, 19/24 simulations, no LLM, no
  broad search), without claiming real-game validity or minimality.

Next major work, only when separately requested: deterministic 6-8 rebaseline,
then top-down first-WIN pursuit.

## 2026-10-12 R8-1 roadblock WALK navigation V3

Completed a bounded static correction without tactical search: corrected two
V2 overgeneralizations, recorded Tile refresh scheduling and ordinary-WALK SPFA
cost/cache edges, and preserved the missing Route-to-SPFA edge as UNKNOWN.
Budget: Kimi 0, real-stage simulations 0, new plans/candidates 0, tactical
search expansions 0. Evidence: `output/r8_1_roadblock_walk_navigation_v3/`.

## 2026-10-12 Route navigation decodability V4

Completed a bounded static diagnosis without tactical search. ELF PT_LOAD
mapping, metadata excerpts, `.eh_frame` boundaries, raw bytes, and Capstone
diagnostics were preserved. The three requested Route methods are
`ENTRY_DECODE_FAILED`; aligned resynchronization produced
`CANDIDATE_CLUES_ONLY`. The call body was not recovered, the cause remains
UNKNOWN, and Route-to-SPFA remains UNKNOWN. Budget: Kimi 0, real-stage
simulations 0, new plans/candidates 0, tactical search expansions 0.
Evidence: `output/r8_1_route_navigation_decodability_v4/`.

## 2026-10-12 Low-star full closure V1 — blocked

Prepared a compact full-stage low-star context and made the single approved
Kimi-K3 request. The response was `response.incomplete`; JSON was truncated.
Forensics showed the prepared evidence context was not embedded in the original
user prompt. No valid OperationalPlan, action timeline, or simulation followed.
Budget: Kimi 1, new plans/candidates 0, stage starts 0, robust replays 0,
tactical search expansions 0. Evidence:
`output/r8_1_low_star_full_tactical_closure_v1/`.

## 2026-10-12 — V2 offline request-entry milestone

完成：证据嵌入、固定[col,row]路障、历史B2隔离、canonical body、最终载荷门禁、一次性传输预算、
HTTP状态/request ID保存、reasoning去重、incomplete拒绝、schema/contract校验和合成Strategy交接。
测试9/9两次通过，compileall通过；Kimi 0，模拟0，新计划0。Work审查通过前不得发起新Kimi调用。

## 2026-10-13 — Authorized V2 Kimi call

One approved-body request completed with HTTP 200 and `response.completed`. Provider
usage was 29,311 input / 30,806 output / 60,117 total tokens; 32,768 remains only the
created-envelope `max_output_tokens`. Local JSON/schema/contract validation passed and
saved one complete OperationalPlan plus one non-tactical direction-complete handoff.
No compile certificate, stage simulation, WIN claim, retry or tactical search occurred.

## 2026-10-13 — Readonly tool loop

Added three whitelisted read-only tools, a visible base rule card, source/provenance
mapping, and a mock Responses tool continuation loop. C1 range and conditional SP
counterexamples were replayed through the common interface. Offline tests passed:
transport 10/10, C1 entry 12/12, tool loop 12/12. No real Kimi call, stage simulation,
new tactical plan, or search expansion occurred. Provider compatibility remains
UNVERIFIED.

## 2026-10-13 — Readonly tool loop V2 fix

The baseline SHA record is corrected to
`1714eb8fb2137037e6d8511ee803f84a616134ea`. The transport now registers function
calls on `output_item.added`, validates argument completion, and sends a full
continuation containing the original user context plus matching
`function_call`/`function_call_output` pairs. Tool schema, duplicate IDs, budget,
and argument completion are checked before execution. The final plan must pass the
existing schema/contract validator. Same-frame DP payments require an explicit link
or order; ambiguity stays UNKNOWN.

Evidence is saved under `output/r8_1_readonly_tool_loop_fix_v2/`. Directed pytest
was 46/46 PASS using a borrowed local pytest 9.1.1 environment because DNS failure
prevented installing the declared pytest in the project venv. Real Kimi requests,
stage simulations, new tactical plans, and search expansion all remained zero.

## 2026-10-13 — Minimal real tool continuation

Streaming function calls are now reconciled with the final response, and incomplete
or failed calls never execute. DP conflicts are reported as CONFLICT without PASS,
while unknown same-frame order remains UNKNOWN. A non-tactical probe confirmed the
existing kimi-k3 plan endpoint can execute one native query_mechanic call and accept
one matching function_call_output continuation within two requests and a requested
1024-token output budget.

Evidence is under `output/r8_1_kimi_tool_protocol_probe_v1/`. Actual requests were
2/2 and read-only tool executions 1/1; usage was 834 and 1105 tokens. The 43-test
pre-existing subset passed 43/43, and all 50 directed tests passed after four new
regressions. No C2, tactical plan, action candidate, simulation, or search occurred.

## 2026-10-13 — Saved C2 normalized, static gate blocked

The saved final response was normalized without tactical modification: only three string
`verification_questions` entries were wrapped as objects, the deep-diff count is three, and the
normalized C2 passes the existing schema/contract validators. The compiler now reads
`selected_skills`, preserves uncovered-target conflicts with `tile_json_row_col`, and converts the
saved C2's coordinate-list declared targets to tool objects without changing semantics.

Static compilation then found one real blocker and seven declared-responsibility unknowns. At
frame 600, Noirc costs 14 DP but the ordered model ledger has 9 DP. Therefore the authorized
0/1 full-stage diagnostic simulation did not start. Directed pytest was 61/61 PASS. No Kimi
request, tactical search, action repair, WIN, or real-game claim was made.

## 2026-10-13 — Auto income corrected; fixed C2 simulated LOSS

The compiler now derives AUTO TIME instant-DP timing from the public adapter pattern instead of
hardcoding a frame. The normalized C2's static ledger receives Fang's 6 DP at frame 570, pays
Noirc's 14 DP at frame 600, and has no static conflicts; seven declared-responsibility UNKNOWNs
remain.

The one authorized full-stage diagnostic run used the original 22 actions and returned LOSS:
27 kills, 29 leaks, life -24, and four operator deaths. Fang triggered once at frame 570 but died
at frame 890. Vanilla died at frame 1243, unblocking route-6 `enemy_1108_uterer#3`, which leaked
at frame 1295. Hibiscus' frame-1680 deployment then failed for insufficient DP. No action repair,
second run, robust roadblock recheck, real-game WIN, or faithful certificate was claimed.

## 2026-10-13 — C3 request stopped reasoning-only

C3 evidence was compacted to 137,980 bytes and retained all 34 ordinary low-star operators, 17
three-stars, C2 key events, economic rejections, and all 22 action outcomes. Both bounded Kimi
requests returned HTTP 200 but `response.incomplete`; each used 32,768 output tokens with 32,765
reasoning tokens and produced no assistant message or native function call. The second attempt
added `tool_choice=required` as an explicit protocol adjustment, not an automatic retry.

The session stopped at 2/3 model requests and 0/6 tools. The final request was deliberately not
spent. There is no C3, no static compile, no diagnostic simulation, and no feasibility claim.

## 2026-10-13 — GPT tactical provider entry

Milestone status: prepared, not verified. The project entry can select provider/model and shares the
readonly-tool loop, C3 evidence and static compiler. The Sub2API request is bounded at 138,127 bytes
with 32,768 output tokens, `gpt-6.1-sol` and medium reasoning. No HTTP request has run because
`SUB2API_API_KEY` is absent; provider compatibility, tool continuation and GPT-C3 validity remain
UNKNOWN.

Update: provider compatibility is partially confirmed: the project API emitted a completed native
`query_mechanic` call and accepted the full tool-result continuation. The session remains a failure:
the only final JSON violated C2 parent identity and frame ordering. Persistent evidence records 4
STARTED / 3 FINISHED requests, exceeding the 3-request cap; no further call is permitted. A numbering
bug overwrote some raw response files and is documented without reconstruction.

## 2026-10-13 — Recovered GPT-C3 diagnostic

The saved GPT-C3 was recovered offline without another model request. After fixing hypothesis-lineage
semantics and preserving one stable action-order correction, the recovery passed schema/contract and
static checks with 0 conflicts / 0 UNKNOWNs. The authorized single full-stage diagnostic simulation
completed as LOSS: 46 kills, 10 leaks, remaining life -5, zero operator deaths; first leak frame 1579.
This is conditional model evidence only.

## 2026-10-13 — GPT-C4 request blocked

Parameterized GPT-C4 preparation passed 38/38 targeted tests with a 138,957-byte frozen request.
The first real request returned HTTP 503 and stopped without retry at 1/3 requests, 0/6 tools, 0
plans and 0 simulations. The remaining two requests require an explicit Work decision.

An explicitly authorized attempt-2 recovery reused the same frozen body and returned a second HTTP 503.
The session is 2/3 requests, 0/6 tools, 0 plans and 0 simulations; no third request is automatic.

## 2026-10-14 — Codex CLI C4 entry blocked before model turn

The local Codex CLI entry passed 58/58 targeted tests, launched its single authorized process, then
failed on workspace routing discovery because proxy variables were not inherited. The runner now sets
explicit local mihomo defaults, but the failed session remains 0 plans / 0 simulations and is not resumed.

## 2026-10-14 — Second Codex CLI attempt reached schema rejection

After proxy preflight, the second CLI start reused the saved C4 prompt/evidence and reached OpenAI. It
stopped at HTTP 400 because the root output schema used `additionalProperties=true`. Cumulative starts
are 2/2 with 0 plans and 0 simulations.

## 2026-10-14 — Third Codex CLI attempt produced C4 and diagnostic LOSS

The `--output-schema` argument was removed while local schema/contract validation remained mandatory;
targeted tests passed 17/17. The third CLI process completed one C4 after lossless provenance-only
normalization, and static checks reported 0 conflicts / 0 UNKNOWN. One full-stage diagnostic simulation
then produced conditional-model LOSS with 49 kills, 7 leaks, no operator deaths, and remaining life -2.

The first leak was route-10 `enemy_1108_uterer#15` at frame 2179 without recorded damage or blocking.
All leak inventory is saved with full events. Cumulative CLI starts are 3/4, final plans 1/1, and
diagnostic simulations 1/1. Roadblock-targeting robustness was not evaluated.

## 2026-10-14 — R8-1 batch first conditional WIN

The generalized tactical batch runner produced C5, C6, and C7. C5 improved the C4 result from 49/7 to
51/5 after lossless provenance-only recovery; C6 improved to 55/1; C7 completed a fixed full-stage WIN
with 56/56 kills, zero leaks, zero operator deaths, and remaining life 5. The squad uses eight ordinary
1-3 star operators with star total 22.

The result is classified as conditional current-model WIN. R8-1 roadblock-targeting replay remains
NOT_EVALUATED and real-game verification is UNKNOWN. New batch totals are 3 CLI process starts and
3 fixed simulations.
