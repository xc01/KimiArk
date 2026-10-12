# Next milestone: Work review of the authorized V2 call

Work accepted the V2 body and authorized one Kimi call after the pre-call fixes.
Those fixes now reject empty embedded evidence, declare/import jsonschema before
network, recover and track the original request JSON/prompt, reject a second attempt
before network, and save a completed response plus non-tactical
`strategy_handoff.json`. The canonical body remains
`3749ad4ded4bc9dfbcc142cba21cc60ba717ad1a780d61ef9da75a897a80dbac`.

The authorized call must use that exact body, count before network, never retry,
and stop on HTTP failure, timeout, interruption, `response.incomplete`, invalid JSON,
schema failure, or operational-plan contract failure. Record the created envelope and
actual usage without claiming that 32,768 was an explicitly requested limit. A valid
result may save one full OperationalPlan and one direction-complete handoff, but no
stage simulation or tactical search occurs. Work must then review tactical semantics
and fidelity.
