from arknights_planner.agent.tactical import _extract_json_content, parse_hypotheses_payload, extract_chat_content, chat_response_diagnostic, response_diagnostic, hypothesis_schema_diagnostics

def test_hypothesis_content_forms():
    for content in ('[{"summary":"x"}]', '```json\n[{"summary":"x"}]\n```', 'answer: [{"summary":"x"}]'):
        assert len(parse_hypotheses_payload(_extract_json_content(content))) == 1

def test_hypothesis_envelope():
    assert len(parse_hypotheses_payload({"hypotheses": [{"summary": "x"}]})) == 1

def test_malformed_content_is_distinct():
    try:
        _extract_json_content("no json here")
    except RuntimeError as exc:
        assert str(exc) == "RESPONSE_CONTENT_NOT_JSON"
    else:
        raise AssertionError("expected bounded parse failure")

def test_standard_chat_envelope_and_diagnostic():
    payload={"id":"x","object":"chat.completion","choices":[{"message":{"role":"assistant","content":'{"hypotheses":[{"summary":"x"}]}'},"finish_reason":"stop"}],"usage":{"total_tokens":1}}
    assert extract_chat_content(payload).startswith("{")
    d=chat_response_diagnostic(payload); assert d["choices_count"] == 1 and d["content_type"] == "str"

def test_chat_error_layers():
    for payload, expected in [({"error":{"message":"bad"}},"PROVIDER_ERROR"), ({"choices":[]},"RESPONSE_CHOICES_EMPTY"), ({"choices":[{}]},"RESPONSE_MESSAGE_MISSING"), ({"choices":[{"message":{}}]},"RESPONSE_CONTENT_MISSING")]:
        try: extract_chat_content(payload)
        except RuntimeError as exc: assert str(exc).startswith(expected)
        else: raise AssertionError("expected diagnostic")

def test_response_diagnostic_is_bounded_and_sanitized():
    raw=b'{"choices":[{"message":{"content":"hello"},"finish_reason":"stop"}],"object":"chat.completion"}'
    d=response_diagnostic(200,"application/json",raw,"https://example/v1/chat/completions")
    assert d["http_status"] == 200 and d["content_preview"] == "hello" and "Authorization" not in str(d)

def test_non_json_diagnostic():
    d=response_diagnostic(502,"text/html",b"x"*1200,"https://example/v1/chat/completions")
    assert d["parse_classification"] == "HTTP_BODY_NOT_JSON" and len(d["body_preview"]) == 1000

def test_observed_simplified_schema_is_plan_error_not_envelope_error():
    payload={"hypotheses":[{"id":"H1","title":"Balanced dual-lane hold","plan":"...","focus":"...","risk":"..."}]}
    d=hypothesis_schema_diagnostics(payload)
    assert d[0]["status"] == "REJECTED" and "summary" in d[0]["missing_required_keys"]
    try: parse_hypotheses_payload(payload)
    except RuntimeError as exc: assert str(exc).startswith("PLAN_SCHEMA_ERROR")
    else: raise AssertionError("expected schema rejection")

def test_runtime_timeout_configuration():
    from arknights_planner.agent.tactical import RealLLMRuntime
    r = RealLLMRuntime(model="m", endpoint="https://example.invalid", api_key="x", timeout_seconds=300)
    assert r.timeout_seconds == 300

def test_out_of_scope_cardinality_is_not_silently_clamped():
    from arknights_planner.agent.tactical import PlanHypothesis
    from arknights_planner.search.m14_ground import grounding_rejections
    hypothesis = PlanHypothesis.from_dict({
        "hypothesis_id": "R1", "summary": "six operators", "reasoning": "",
        "target_cardinality": 6, "tactical_archetype": "formation",
        "required_capabilities": [], "preferred_operator_ids": [],
        "alternative_operator_ids": [], "placement_intents": [],
        "deployment_order": [], "skill_use_intents": [],
        "retreat_redeploy_intents": [], "confidence": 0.5,
    })
    assert grounding_rejections((hypothesis,)) == ({
        "hypothesis_id": "R1", "status": "REJECTED",
        "reason": "target_cardinality exceeds bounded M14 K<=3 scope",
    },)

def test_cardinality_audit_preserves_full_k_and_single_k_minus_one_ablation():
    from arknights_planner.agent.tactical import PlanHypothesis
    from arknights_planner.adapters import ApproximateRealSimulationAdapter
    from arknights_planner.gamedata import GameDataRepository
    from arknights_planner.search.m14_ground import ground_cardinality_audit
    hypothesis = PlanHypothesis.from_dict({
        "hypothesis_id": "R1", "summary": "six roles", "reasoning": "",
        "target_cardinality": 6, "tactical_archetype": "formation",
        "required_capabilities": ["ARTS_DPS"],
        "preferred_operator_ids": ["char_122_beagle", "char_209_ardign", "char_210_stward", "char_121_lava", "char_124_kroos", "char_120_hibisc"],
        "alternative_operator_ids": [], "placement_intents": [],
        "deployment_order": ["char_124_kroos", "char_210_stward", "char_122_beagle", "char_209_ardign", "char_121_lava", "char_120_hibisc"],
        "skill_use_intents": [], "retreat_redeploy_intents": [], "confidence": 0.5,
    })
    teams, rejections = ground_cardinality_audit((hypothesis,), ApproximateRealSimulationAdapter(GameDataRepository("data/ArknightsGameData")))
    assert not rejections
    assert [(item.variant, len(item.operators)) for item in teams] == [("FULL", 6), ("REDUCED", 5)]
    assert teams[1].removed_operator_id not in teams[1].operators
