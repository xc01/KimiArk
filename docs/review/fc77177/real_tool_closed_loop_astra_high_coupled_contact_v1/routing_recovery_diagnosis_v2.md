# Coupled-contact routing recovery recheck V2

Status: `ZERO_MODEL_RECOVERY_PRECONDITIONS_RESTORED_REAL_CLI_STILL_NOT_STARTED`.

The original failure remained `workspace routing discovery failed` after 10 WebSocket retries and an announced HTTPS fallback. The repaired mihomo service now owns one process, listens on `127.0.0.1:7890/9090`, and keeps the AI-platform selector on `🇺🇸 美国自动`. Codex remains CLI 0.166.0 and logged in with ChatGPT.

The actual workspace-routing endpoint now reaches its protected edge and returns `401` without credentials; this is expected. ChatGPT trace returns `200/US`, Google returns `204`, and GitHub returns `200`. This proves the previously failing routing request category is reachable again, but does not run a real model turn or cover WebSocket upgrade, HTTPS fallback, MCP calls, or Responses streaming.

The repair used the controller selector rather than changing mihomo config, authentication, account, model, or reasoning effort. The duplicate mihomo process started during repair was cleaned up; the service-owned process remained. The prior V1 diagnosis and all original failure artifacts are unchanged.

Budget remains CLI `1/1`, check `0/10`, candidate `0/2`, simulation `0/2`; no model, simulation, or new experiment was started. A real CLI retry requires new explicit authorization and must continue this ledger. M70 remains the best verified eight-ID fixed-simulator result, while seven-ID feasibility remains `UNKNOWN`.
