# Coupled-contact Astra high service failure

The zero-model preflight passed at `10:35:14Z`, and the single authorized `gpt-6-astra/high` CLI was started at `10:35:44.603Z`. Codex created a thread, then failed with `workspace routing discovery failed` after WebSocket and HTTPS retries. stderr also recorded three model-catalog refresh connection failures. These warnings are contemporaneous observations, not a proven root cause.

The CLI ended at `10:36:12.630Z` with exit code 1 and no `turn.completed`, final message, MCP tool call, candidate, or simulation. This is a service-layer failure, not a tactical LOSS. Internal model requests, if any, are `UNKNOWN_CLI_INTERNAL`; visible usage is not available for the failed turn. The runner did not retry or resume.

Authorized budget is therefore `CLI 1/1`, `check 0/10`, `candidate 0/2`, and `simulation 0/2`. No tactical conclusion was produced. M70's eight-ID WIN remains best, and seven-or-fewer feasibility remains `UNKNOWN`. Recovery requires external routing recovery plus a separate user authorization; this experiment must not start another CLI.
