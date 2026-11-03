# KimiArk Closed-Loop Stdio Tools (V1)

## Scope

This adapter adds four fixed-session tools for a future Codex/Astra tactical loop:

- `get_session_status`
- `check_plan`
- `run_simulation`
- `query_events`

It is an execution adapter, not a planner. The model still supplies every roster, parent branch, action, position, direction, skill activation, and retreat. The service does not repair plans, infer causes, search for tactics, or relax the existing win rule.

This task only packages the tool layer. It does not authorize any tactical CLI call, complete simulation, live MCP integration, or a new tactical milestone.

## Why a custom stdio adapter

The repository already has a minimal JSON-RPC MCP server in `scripts/kimiark_mcp_server.py`, but its existing tools accept caller-provided paths. That is suitable for the old runner but does not bind one experiment to a fixed session root, budget, authorization, or candidate ledger.

The new adapter uses the repository's stdlib JSON-RPC style and routes execution through the existing controlled chain:

1. `run_gpt_tactical_stage_session_v1.py` schema, lineage, roster, execution-fact, and static paths.
2. `compile_r8_1_lowstar_c2_plan_v1.py::compile_plan`.
3. `tactical_evaluation_gate_v1.py` immutable gate and simulation budget.
4. `run_gpt_tactical_stage_session_v1.py simulate`, which invokes the existing diagnostic runner.

The wrapper does not import or call the `Simulator` class directly.

## Session ownership

At startup the service reads one repository-relative config file. Tool calls cannot choose:

- the authorization file, budget, candidate ledger, facts source, or session root;
- model, reasoning effort, `features.apps`, mechanics version, stage ID, or K;
- diagnostic output directories, commands, Python code, or shell strings;
- budget counters, retry behavior, timeout policy, or file overrides.

Each candidate is written under the service-owned session root as `candidates/candidate-NNN/source`, with its original request, copied execution facts/schema, validation, static result, frozen hashes, simulation request, and simulation output. Paths are constrained to the repository and then to the session root. Symlink escape is rejected.

## Candidate and simulation accounting

The candidate ledger must already exist and be bound to the configured session ID. A new distinct canonical plan hash consumes one candidate slot on first `check_plan`, including a contract, capability, execution-fact, roster, K, or static failure. Rechecking the same hash is idempotent and does not consume a second slot.

`run_simulation` accepts only a checked PASS candidate ID plus its exact SHA-256. It re-verifies frozen input hashes, source-fact hashes, controlled code hashes, active mechanics, K, static conflicts, and execution input. It then performs a non-starting preflight and invokes the existing runner's `simulate` phase. That runner calls the existing gate and performs budget reservation before battle.

After reservation, any failure, timeout, incomplete result, or lost process is counted. The service does not refund, restart, resume, or retry. A repeated completed request returns the saved result. While a service run lock is held, it returns `IN_PROGRESS`. If a reservation is present without a locally determinable outcome, it returns `STARTED_UNKNOWN` and reconciliation is required.

The example `max_candidates: 5` and `max_stage_simulations` are placeholder numbers only. This task does not create an active budget.

## Event semantics

`query_events` only reads a simulation event log produced under the configured session. It supports exact `event_type`, `source_id`, and `target_id` equality, with `null` meaning null; inclusive frame bounds; up to four primitive `details_equal` conditions; bounded pagination; and deterministic numeric aggregates.

Raw matches preserve `legal:false` action events. A match only proves that an event was observed. It does not prove a hypothesis, causal chain, rotation, survival, protection, or global WIN. Coverage is `COMPLETE` only when the existing attempt and manifest indicate a completed result; otherwise zero matches return `UNKNOWN`.

## Security boundary

The service constrains tool arguments, identifiers, paths, and commands. This is a tool-layer guard, not an operating-system sandbox. If the model process and service process share write access to repository source or configuration, the model or an arbitrary local process could still modify files outside tool arguments. Do not claim process isolation unless the service is later deployed with separate file permissions.

For a future hardened deployment, run the service under a dedicated local account with read-only access to repository code and facts, write access only to its session root and required ledger/budget files, no network policy, and no access to model authorization secrets. The current implementation does not provide that deployment.

## Future connection example

The following command is an example only and is not run here:

```sh
python scripts/kimiark_tactical_stdio_service_v1.py \
  PLACEHOLDER_REPOSITORY_RELATIVE_SESSION_CONFIG.json
```

A Codex local MCP registration example must use placeholder paths and is intentionally not added to the global Codex configuration:

```json
{
  "mcpServers": {
    "kimiark-tactical-closed-loop": {
      "command": "PLACEHOLDER_PYTHON",
      "args": [
        "PLACEHOLDER_REPOSITORY/scripts/kimiark_tactical_stdio_service_v1.py",
        "PLACEHOLDER_REPOSITORY/PLACEHOLDER_SESSION_CONFIG.json"
      ]
    }
  }
}
```

## Future closed-loop prompt template

Use only after a future explicit authorization. Replace placeholders and do not inherit any currently paused budget.

```text
You are authorized only for the fixed KimiArk closed-loop session described by PLACEHOLDER_SESSION_CONFIG.
Use openai/PLACEHOLDER_MODEL/PLACEHOLDER_EFFORT and features.apps=false.
Initial K=PLACEHOLDER_K. Service-owned candidate and simulation limits are hard.
For every version: compare at least three substantive structures, select one, and submit its complete plan with check_plan.
If check_plan passes, run_simulation once for that candidate. If it starts and fails, report it as counted; do not retry.
Use query_events against the registered event log, compare the repair card with observed events, trace the earliest upstream break, and then decide whether a new candidate is justified.
Stop and notify me immediately on usage limit, rate limit, capacity, 403, routing failure, or timeout. Preserve the ledger and next candidate entry.
WIN still means legal union <= K, current-model simulator WIN, zero leaks, both protected targets alive and arrived, all enemies settled, and no active enemies. On WIN, freeze the result and only continue within remaining service-authorized candidates.
```

## Old-runner compatibility

The old runner and MCP server remain unchanged. This adapter adds an explicit opt-in service; no startup script or global configuration is registered here. Existing milestone evidence, frozen plans, budgets, and M79 accounting are not modified.

## Written but not executed

The fake/stub tests in `tests/test_kimiark_tactical_stdio_service_v1.py` were written but not executed. No service, simulation, tactical model call, or live MCP connection was started. Risks requiring later verification include real schema behavior, static compile integration, actual gate reservation, subprocess timeout behavior, filesystem concurrency under simultaneous processes, and remote Astra tool-call compatibility.
