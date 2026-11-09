# Coupled-contact routing diagnosis V3

Classification: `MITIGATED_AT_REQUEST_LAYER_REAL_CLI_PATH_STILL_UNVERIFIED`. No model, simulation, or new experiment was started.

The failed CLI reached `turn.started`, then exhausted the visible WebSocket retry family, announced WebSocket-to-HTTPS fallback, and failed again after another visible retry family. It exited after 28 seconds with no final message, MCP call, check, candidate, or simulation. Three model-catalog connection warnings were contemporaneous observations, not the proven root cause.

For Codex 0.166.0, workspace routing uses `GET https://chatgpt.com/backend-api/wham/accounts/check`. The generic visible error excludes a 15-second timeout and HTTP 401, but the original logs intentionally omit the underlying status/transport details. Thus the exact historical transport cause remains `UNKNOWN`.

The zero-model recheck found Codex logged in with ChatGPT, the service-owned mihomo process healthy on ports 7890/9090, and the AI-platform selector on `🇺🇸 美国自动`. The actual account-routing endpoint returned `401` in 0.925 seconds, the expected unauthenticated response. A later trace request timed out, so the proxy is still variable and home-page/front-page success is not treated as recovery proof.

The repair was limited to selecting a proxy group through the controller; no repo config, auth, account, model, tier, timeout, transport switch, or tactical mechanism changed. The duplicate repair process was removed; the service-owned process remained. The original failure artifacts and all 25 manifest entries remain hash-verified.

No re-authentication or task-config change is indicated now. A definitive recovery check requires a new explicit CLI authorization. It must continue the existing ledger—CLI `1/1`, check `0/10`, candidate `0/2`, simulation `0/2`—and a routing-only retry is not a tactical LOSS. M70 remains the best verified eight-ID result; seven-ID feasibility remains `UNKNOWN`.
