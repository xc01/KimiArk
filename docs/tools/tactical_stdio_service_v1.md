# KimiArk Closed-Loop Stdio Tools (V1)

## Scope

This adapter adds four fixed-session tools for a future Codex/Astra tactical loop:

- `get_session_status`
- `check_plan`
- `run_simulation`
- `query_events`

It is an execution adapter, not a planner. The model still supplies every roster, parent branch, action, position, direction, skill activation, and retreat. The service does not repair plans, infer causes, search for tactics, or relax the existing win rule.

This task only packages the tool layer. It does not authorize any tactical CLI call, complete simulation, live MCP integration, or a new tactical milestone.

## Protocol

The service uses newline-delimited JSON-RPC 2.0 over stdio and implements the MCP methods used by a local client: `initialize`, `notifications/initialized`, `tools/list`, `tools/call`, `ping`, and `notifications/cancelled`. Its advertised protocol version is `2025-06-18`. Stdout carries protocol messages only; there are no service log lines on stdout. JSON messages are flushed after every line.

The local fake closed-loop test starts this script as a child process, performs the MCP handshake, discovers exactly four tools, calls status/check/run/query, closes stdin, and verifies a clean exit. It does not register Codex globally and does not prove that a particular Codex installation will accept this server; that client registration remains a separate authorization step.

For Codex CLI 0.166.0, the supported scoped registration can restrict exposure and tool-layer approval without using `--approve-for-me` or bypassing approvals globally:

```toml
[mcp_servers.kimiark]
command = "PLACEHOLDER_PYTHON"
args = ["PLACEHOLDER_SERVICE_SCRIPT", "PLACEHOLDER_SESSION_CONFIG"]
required = true
enabled_tools = ["get_session_status", "check_plan", "run_simulation", "query_events"]
default_tools_approval_mode = "approve"
```

`enabled_tools` is an MCP exposure allow-list. `default_tools_approval_mode = "approve"` only avoids the client-side per-tool approval prompt; it does not alter service authorization, candidate quota, simulation quota, frozen input hashes, static gates, or execution preflight. A per-tool override is `mcp_servers.kimiark.tools.<tool>.approval_mode = "approve"`. Avoid unsupported names such as `trusted` or `auto_approve`.

## Action and event names

Plan `action_type` uses `DEPLOY`, `ACTIVATE_SKILL`, and `RETREAT`. Simulator logs are events and use `DEPLOY`, `RETREAT`, and `SKILL_ACTIVATE`; they also include damage, healing, projectile, ability, device, death, leak, and objective event types. `get_session_status` exposes both lists. `query_events` accepts `ACTIVATE_SKILL` only as an explicit lossless alias for `SKILL_ACTIVATE`, returns the declared and normalized names, and never guesses an unknown event. Invalid expected-event fields return the JSON path, received value, supported set, and repair hint.

`get_session_status` also exposes the configured `execution_backend` and `allow_fake_execution` flag so the model can confirm that a production session uses `CONTROLLED_RUNNER`; this is configuration evidence, not proof of remote model identity.

The implementation intentionally uses the repository's existing JSON-RPC style and standard library rather than adding an MCP SDK dependency.

## Why a fixed-session adapter

The repository also has an older MCP server in `scripts/kimiark_mcp_server.py`, but its existing tools accept caller-provided paths. That is suitable for the old runner but does not bind one experiment to a fixed session root, budget, authorization, or candidate ledger.

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

Versioned ledgers may instead use `KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2`. A V2 ledger enforces `max_check_calls` separately from `max_candidates`. Every non-over-limit `check_plan` call—including a failed check, idempotent recheck, and candidate-budget-exhausted check—is recorded under `checks/check-NNN` and consumes one check call. Only a PASS creates `candidates/candidate-NNN` and consumes an actual run-candidate slot. This preserves failed revisions while preventing unbounded protocol repair.

`run_simulation` accepts only a checked PASS candidate ID plus its exact SHA-256. It re-verifies frozen input hashes, source-fact hashes, controlled code hashes, active mechanics, K, static conflicts, and execution input. It then performs a non-starting preflight and invokes the existing runner's `simulate` phase. That runner calls the existing gate and performs budget reservation before battle.

After reservation, any failure, timeout, incomplete result, or lost process is counted. The service does not refund, restart, resume, or retry. A repeated completed request returns the saved result. While a service run lock is held, it returns `IN_PROGRESS`. If a reservation is present without a locally determinable outcome, it returns `STARTED_UNKNOWN` and reconciliation is required.

The example `max_candidates: 5` and `max_stage_simulations` are placeholder numbers only. This task does not create an active budget.

## Fake test backend

Production config must use:

```json
{"execution_backend": "CONTROLLED_RUNNER", "allow_fake_execution": false}
```

A fake backend is possible only when all of the following are true in the startup config: `execution_backend` is `TEST_ONLY_FAKE`, `allow_fake_execution` is true, `session_id` begins with `TEST_ONLY-`, and `stage_id` begins with `FAKE_TEST-`. The fake executor writes events and summaries marked `FAKE_TEST`; it never calls the diagnostic runner or `Simulator`. Its outputs are not tactical results and must not be archived as battle evidence.

Model-facing tool arguments cannot switch the backend. Switching to fake execution requires modifying the trusted startup configuration.

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

## Local dynamic test record

A FAKE_TEST record is kept at `docs/tools/tactical_stdio_service_test_log_v1.json`. It records the targeted pytest command, result counts, protocol transcript summary, fake executor invocation count, and budget counters. Temporary fixtures are removed; the committed record contains no credential or full tactical evidence.

The later Terra v2 recovery used the scoped Codex CLI fields above. A real session proved the four tool calls and one real diagnostic run; its per-milestone evidence remains under `docs/review/fc77177/real_tool_closed_loop_terra_v2/`. Tool-layer approval is still not an operating-system sandbox, and a passing fake test does not validate model tactics.
