# R112 artillery-window mechanism closeout

- Complete fixed-simulator WIN failed; final usage was CLI 1/1, checks 3/10, candidates 2/2, simulations 2/2. No retry/resume/model change occurred.
- C001's early Hibiscus isolation was refuted: Ansel died@2111, Melantha@2261, Steward@2711; result 12 kills/21 leaks, artillery leaked@5759, #13 and both protected targets failed.
- C002 restored early geometry and added Fang retreat@3400/redeploy@5501. Hibiscus heal@3460 changed from Fang to self-heal, and Steward received late heal@3632/3804. Steward delivered 45 hits/13,227.21 damage (+8/+2,441.18 vs R110 C2) and killed artillery@4273 with no artillery leak.
- C002 also retained #11@2881, #13@3311, roadblock4@2026, #14 reach@12448, and #3 reach@15549. But #19 leaked@4475, central #21@5046/#22@6886/#33@6901/#34@6996 leaked, final was 22 kills/11 leaks/life -8.
- Stream-visible model usage: input 1,458,801 / cached input 1,344,640 / output 11,645; internal request count UNKNOWN_CLI_INTERNAL. Model-directory refresh timeouts in stderr were nonfatal; no quota error was returned.
- Large diagnostic JSONs are single-layer gzip archives with restored-hash verification in `artifact_manifest_v1.json`. M70 remains the eight-ID fixed-simulator WIN; seven-or-fewer feasibility remains UNKNOWN.
