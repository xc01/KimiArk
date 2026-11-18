This directory is one closed, independently budgeted deterministic search batch.

Read `closeout_v1.md`, `canonical_action_diff_v1.json`, `variant_results_v1.json`, and `key_event_index_v1.json`. `search_state.json` retains each exact change set and predicted mechanism separately from observed events. The two non-dominating four-leak plans are deliberately retained.

`search_batch.py` builds from the actual frozen candidate-038 structured output, performs semantic action dedup, calls the existing production MCP check/run service and saves complete results. V2 budgets charge static rejection only to check. Exploration reserves two simulation slots. `preflight_counting.py` is a fake-only isolated fixture; it refuses to overwrite an existing fixture. Phase scripts record the sampled structural groups. Some early phase scripts deliberately retain rejected original submissions; corrected submissions and all ad hoc generated variants are fully reconstructible from `search_state.json`.

`reverify_frozen.py` copies and hash-verifies the six frozen inputs, recovers the original generated execution gate from its exact check response when necessary, and uses the existing production `simulate` entry with new output IDs and the same simulation budget. It never invokes Simulator directly or returns an idempotent cached battle. Its already-used output IDs cannot be reused.

`finalize_batch.py` only parses records, verifies exact payload reconstruction and reconciles real reservations. `archive_batch.py` only compresses newly generated JSON, verifies restoration and creates the artifact manifest. Neither starts any battle or model. `read()` and `digest()` resolve archived `.json.gz` without materializing raw JSON. All raw JSON bytes remain recoverable; source records and original hashes are unchanged.

The batch is closed: search entry points reject any further candidates. Running the saved scripts against a new ledger requires a separate authorization and an explicit new batch path/configuration; unused balances must never be copied. No tactical model was used. `gpt-6.2-astra` in the unused configuration is an unverified request placeholder, not an availability or model identity claim.

Archive SHA-256 values identify stored files; `uncompressed_sha256` identifies exact original JSON bytes. `.lock` files and Python caches are excluded from the commit/manifest but are left on disk. Unrelated workspace changes are left untouched.
