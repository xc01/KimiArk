# Next milestone: restore m25 network entry and send the prepared R8-1 revision

R8-1 attempt 1 is the only new CLI start (cumulative 47) and failed before
tactics on `workspace routing discovery failed`. The local sandbox denied
mihomo binding and direct DNS failed, so no model call or simulation can be
credited. Restore a real proxy endpoint outside this sandbox, then reuse the
frozen R8-1 m25 input without regenerating tactics. If entry succeeds, resume
the one-plan/static/fixed-simulation loop; R8-7's prepared m25 prompt may follow
under the same round budget. Do not interpret the entry failure as tactical
evidence or switch provider/model.

The m24 evidence bundle, causal feedback, and two tactical revision payloads are
prepared but not sent. Do not make a model call or new full-stage simulation
until Work selects the next stage. R8-3/R8-5/R8-6 remain mechanism-blocked, and
optimization remains not started.
