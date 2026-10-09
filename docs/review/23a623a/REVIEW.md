# 23a623a independent review

Baseline: remote master verified as 23a623ae4960c0095d71f1f28ca5d3d782e642c1 on 2026-10-09. Review patch 59add38 has equivalent source/test changes to local 5143a99. No Kimi calls, new plans, stage simulations or expanded search in this review.

## CONFIRMED_FROM_CODE

Both 305-operator tables are delivered. Fidelity SHA-256 6d0f9eb0967bb0442c3bdf2a6994c79950c2cf4ee6ee1d38cd8f12ffeacda564; census 96be4a2b757da6c6d8ea2e0f3845a79d260c6ba479b0e8684138eee3d62fc12c. Original generation commit remains UNKNOWN. Their m18.5 labels do not independently certify current m18.9 runtime.

The Plan A script computes candidate counts 1/1/3/2/2 and their product 12; it does not enumerate 12 assignments, construct timelines, test queue deadlines or execute simulation. Witness=None and simulations=0 are assigned explicitly. Zero qualified candidates is an audit gate result, not a tested tactical failure.

The wscoot census description says normally does not attack and has block 0 when skill is inactive. This contradicts the exemplar's assumed skill-independent dam responsibility. The three merchant exemplars have cost=-3 / interval=3 trait blackboard entries; their unsupported upkeep means listed deploy cost cannot certify prefix economy. Those entries alone do not establish precise debit clock/refund behavior.

Geometry for the tested ranges: angel/aprl cannot cover [8,5] from [9,2]; caper can. Thus the saved summary's unqualified claim that this geometry cannot cover the pocket is too broad. This says nothing about all alternative operators or actual tile occupancy by devices.

## Confirmed defects and minimal correction

1. fidelity_provenance unconditionally opens scripts/build_operator_runtime_fidelity.py, absent from tracked checkout. Baseline Plan A tests fail in setUpClass (0 tests executed), not merely because pytest is absent. Corrected to record MISSING_FROM_CHECKOUT, with no invented hash or generator.
2. effective_dps averages raw attack/multihit scaling then subtracts DEF once and divides boost frequency by SP cost. Simulator applies DEF separately per hit; its next-attack skill does not generate attack SP, so its steady cycle contains SP-cost normal attacks plus one skill attack. Diagnostic values are not exact damage bounds. Retained numbers as diagnostic only; no below-floor proof or claimed ammo lower bound. Exact finite-window damage remains UNKNOWN; candidates stay unqualified.
3. DP ledger uses A03's 15 cost cap rather than tested 11/12 costs. With caper=12 and hypothetical 5 refund, the same 729 arithmetic yields +2.3, not -0.7, before unmodeled upkeep. COND_ROUTE6 also permits omission of A05. Retained ledger as cost-cap example with explicit limitations; no feasibility claim.
4. Corrected feedback summary to preserve caper's positive geometry and distinguish runtime gaps from tactical counterexamples.

Historical output artifacts were not regenerated or changed. Regression tests use build(write_artifacts=False).

## Validation and limitations

After minimal correction: targeted unittest 41/41 PASS with declared pytest dev dependency already installed in isolated review environment; PYTHONPATH=src:scripts. Includes 10 Plan A, 11 V3, 5 frame-295, 5 source-evidence and 10 transport tests. Regression checks missing generator, multihit diagnostic mismatch and actual-candidate cost counterexample. compileall and diff-check PASS.

Worker's full 96/103 result remains REPORTED_BY_PREVIOUS_WORKER; no claim of independent full-suite PASS. Saved audit values cannot independently prove no historical additional Kimi calls. No game mechanics changed.

## Decision

Do not feed the saved DPS/DP deficits to Kimi as proven tactical counterexamples. The wscoot description conflict and the two tested range failures may be fed back as scoped facts, accompanied by all UNKNOWNs. First resolve this small deterministic contract calculation; sole next milestone is defined in NEXT_MILESTONE. No V4 or wider search is authorized by this review.
