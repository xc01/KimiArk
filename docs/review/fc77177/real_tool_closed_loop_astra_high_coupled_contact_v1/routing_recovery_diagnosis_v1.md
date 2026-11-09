# Coupled-contact routing recovery diagnosis

Status: `EXTERNAL_OR_PROXY_SERVICE_CONDITION_SUSPECTED_NOT_PROVEN`. The terminal layer is confirmed as ChatGPT account workspace-routing discovery; the specific network/status cause remains `UNKNOWN`.

For CLI 0.166.0, the visible `workspace routing discovery failed` maps to the account-routing `GET https://chatgpt.com/backend-api/wham/accounts/check` request. A timeout or 401 would have emitted a more specific error, so those two categories are excluded. The first five-second transport failure is intentionally discarded, followed by a system-proxy fallback; therefore the original logs correctly contain no HTTP status or request ID.

The CLI reached `turn.started`, failed after WebSocket retries and an announced HTTPS fallback, and exited after 28 seconds. Three catalog-refresh connection errors were contemporaneous observations, not proven causes. At the same local time, mihomo's auto-switch observer reported a Google health-check failure and no passing candidate. On the 2026-11-09 no-model recheck, no mihomo process was found and ports 7890/9090 were unavailable, so the actual routing endpoint could not be rechecked. This correlation is not accepted as a standalone root cause.

No local command/config/launcher defect was identified, so no repair was applied. The two earlier same-model sessions completed with no relevant command-shape, version, provider, model, effort, feature, or login-status difference; that excludes those fields as a sole cause but does not reconstruct the historical proxy state.

Recovery needs the externally managed proxy restored. Then check the actual routing category rather than a generic front page; nevertheless, only a newly authorized real CLI run reaching `turn.completed` is definitive acceptance. If restarting again, continue the original ledger: CLI 1/1, check 0/10, candidate 0/2, simulation 0/2. Unused simulations do not authorize a new CLI start. This is a service failure, not a tactical LOSS; M70 remains the best verified eight-ID result and seven-ID feasibility remains `UNKNOWN`.
