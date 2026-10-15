# m24 review evidence summary

## Integrity

Five saved m23/m24 runs are indexed in `m24_review_evidence_v1.json`. All five
static checks have zero conflicts, all compressed event files decompress, and
all recorded source plan/action pairs match their frozen snapshots. The five
runs reconcile to 5 full-stage simulation starts: R8-1 targeting A, R8-1
targeting B, R8-2 V15, R8-4 V4, and R8-7 V13.

The Git bundle
`/tmp/KimiArk_m24_unpushed_21f2914_840de3f.bundle`
contains the three unpushed commits and verifies against base
`21f2914b49bb9e80eb74fe05e6e3ead7d8aa77de`; SHA-256 is
`0349369c7a87d2d46e835f7e651c7b715a6508abd32c0f7e72a58fb3a0af7a8b`.

## Causal findings

- R8-1: route-34 instances `enemy_1108_uterer#53` and `#54` spawn at 4800/4824
  and leak at 5258/5282. Neither has a recorded direct combat event. Targeting
  A/B first diverge at frame 360 on Kroos device selection; identical totals do
  not make the result robust.
- R8-4: Ansel dies at 5304 after repeated physical pressure from
  `enemy_1109_uabone#56`. No post-death Ansel action occurs, but remaining line
  duties close the run with zero leaks, zero protected-target loss, and all
  three protected arrivals. Operator death is therefore a separate metric.
- R8-7: artillery at [3,5] hits Ansel at 1530 and 1680; the second hit kills
  him at 1680, before the first leak at 1931. Later artillery/officer pressure
  breaks the line, then roadblock-restrained civilians are struck.

## Prepared, not sent

`output/r8_1_r8_7_batch_v1/main_08-01/m24_tactical_revision_input_v1/codex_payload.json`
and
`output/r8_1_r8_7_batch_v1/main_08-07/m24_tactical_revision_input_v1/codex_payload.json`
are complete revision inputs with plan/action, evidence context, current
result, mechanism boundary, and causal feedback. No model call has been made.
