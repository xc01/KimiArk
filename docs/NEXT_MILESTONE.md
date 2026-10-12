# Next milestone: close the Route-to-SPFA static edge

Work accepted the focused V2 evidence but corrected two overgeneralizations:
`NOT_TRIGGERED_FOR_UNCHANGED_WALK_FLY_MASK` and
`FALSE_IF_AVOID_OBSTACLE_LIKE_IS_TRUE`. The corrected V3 evidence is in
`output/r8_1_roadblock_walk_navigation_v3/`.

The remaining navigation-chain gap is exact:
`Route.ReconstructNextMap -> SPFA path generation`. In build 2771, the supplied
static bytes for `Route..ctor`, `Route.ReconstructRoute`, and
`Route.ReconstructNextMap` fail default Capstone entry decoding. V4 therefore
replaces the stale V3 classification `NO_VALID_A64_INSTRUCTIONS`; entry failure
does not prove that the whole range is invalid or encrypted. ELF PT_LOAD and
`.eh_frame` mapping are in `output/r8_1_route_navigation_decodability_v4/`.

The stored SPFA reference and method signatures are insufficient to prove this
edge. The next bounded task is to obtain a compatible decrypted/static call body
or another direct client source for this one edge, then connect it to cost, cache
and refresh behavior. Do not infer the edge from Python, simulator behavior, or
method naming. Do not present aligned resynchronization or skipdata candidates as
real control flow without method-boundary evidence.

Do not investigate `tap_roadblock` civilian/Talulah binding in the same step.
Do not invoke Kimi, run real-stage simulation, add OperationalPlans/candidates,
or expand tactical search.
