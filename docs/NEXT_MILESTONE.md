# Next milestone: Work review of the prepared V2 request

The offline V2 entry repair is complete. No new Kimi call was made. The prepared body embeds the current evidence JSON, fixes the five roadblock positions as `[col,row]`, isolates old B2 pressure/diagnostic records as historical-only, and validates schema plus operational-plan contract locally.

Canonical body: `output/r8_1_low_star_full_tactical_closure_v2/llm_request_body.txt`
SHA-256: `3749ad4ded4bc9dfbcc142cba21cc60ba717ad1a780d61ef9da75a897a80dbac`
Bytes: 112,541. Provider-created-envelope output budget: 32,768 tokens; terminal usage/incomplete details remain UNKNOWN.

Transport now records an attempt before network, preserves HTTP status/request ID, counts HTTP 401, timeout, URL error, stream interruption and interruption as a single budgeted failure, and forbids retry. The local tests cover the captured `Request.data`, failure records, incomplete rejection, exact-one-plan contract, mandatory DEPLOY direction, and synthetic handoff to the public `Strategy/Action` model.

Work must review the final serialized body and offline acceptance before authorizing a new bounded Kimi call. Do not recover tactics from the V1 partial output, do not retry V1, do not generate Python tactics, and do not run real-stage simulation. `Route -> SPFA` static navigation work remains paused. Active roadblock ordinary-WALK navigation and exact client timing remain UNKNOWN.
