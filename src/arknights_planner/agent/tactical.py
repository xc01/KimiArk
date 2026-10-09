from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json, os, time
from urllib import request, error
from typing import Protocol

@dataclass(frozen=True)
class TacticalRequirement:
    requirement_type: str
    evidence: str
    severity: float = 0.5
    affected_routes: tuple[str, ...] = ()

@dataclass(frozen=True)
class StageAnalysis:
    stage_id: str
    map_dimensions: tuple[int, int]
    deployable_ground: tuple[tuple[int,int], ...]
    deployable_high_ground: tuple[tuple[int,int], ...]
    routes: tuple[dict, ...]
    enemy_types: tuple[dict, ...]
    spawn_count: int
    initial_dp: int
    deployment_limit: int
    approximations: tuple[str, ...]

@dataclass(frozen=True)
class AvailableOperatorSummary:
    operator_id: str; name: str | None; rarity: int; profession: str
    position: str; cost: int | None; block: int | None; atk: float | None
    defense: float | None; damage_type: str; attack_interval: float | None

@dataclass(frozen=True)
class PlanHypothesis:
    hypothesis_id: str = "hypothesis"
    summary: str = ""
    reasoning: str = ""
    target_cardinality: int = 2
    tactical_archetype: str = ""
    required_capabilities: tuple[str, ...] = ()
    preferred_operator_ids: tuple[str, ...] = ()
    alternative_operator_ids: tuple[str, ...] = ()
    placement_intents: tuple[str, ...] = ()
    deployment_order: tuple[str, ...] = ()
    skill_use_intents: tuple[str, ...] = ()
    retreat_redeploy_intents: tuple[str, ...] = ()
    operator_responsibilities: tuple[dict, ...] = ()
    confidence: float = 0.5

    @classmethod
    def from_dict(cls, value: dict) -> "PlanHypothesis":
        if not isinstance(value, dict) or not value.get("summary"):
            raise ValueError("hypothesis requires a non-empty summary")
        allowed = {f for f in cls.__dataclass_fields__}
        data = {k: v for k, v in value.items() if k in allowed}
        for key in ("required_capabilities","preferred_operator_ids","alternative_operator_ids","placement_intents","deployment_order","skill_use_intents","retreat_redeploy_intents"):
            if key in data: data[key] = tuple(data[key] or ())
        if "operator_responsibilities" in data:
            data["operator_responsibilities"] = tuple(data["operator_responsibilities"] or ())
        return cls(**data)

class TacticalLLMRuntime(Protocol):
    def generate_hypotheses(self, context: dict, *, max_hypotheses: int = 6) -> list[PlanHypothesis]: ...
    def revise_hypotheses(self, context: dict, failures: list[dict], *, max_hypotheses: int = 4) -> list[PlanHypothesis]: ...

def _extract_json_content(content: str):
    """Bounded extraction for plain/fenced/prose-wrapped JSON responses."""
    text = (content or "").strip()
    if not text:
        raise RuntimeError("RESPONSE_EMPTY_CONTENT")
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
        for start in sorted(starts):
            for end in range(len(text), start + 1, -1):
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    continue
        raise RuntimeError("RESPONSE_CONTENT_NOT_JSON")

def parse_hypotheses_payload(payload) -> list[PlanHypothesis]:
    if isinstance(payload, dict):
        payload = payload.get("hypotheses")
    if not isinstance(payload, list):
        raise RuntimeError("RESPONSE_SCHEMA_ERROR: expected hypotheses array")
    result = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise RuntimeError(f"PLAN_SCHEMA_ERROR: hypothesis[{index}] is not an object")
        try:
            result.append(PlanHypothesis.from_dict(item))
        except (ValueError, TypeError) as exc:
            raise RuntimeError(f"PLAN_SCHEMA_ERROR: hypothesis[{index}]: {exc}") from exc
    return result

def hypothesis_schema_diagnostics(payload) -> list[dict]:
    items = payload.get("hypotheses") if isinstance(payload, dict) else payload
    if not isinstance(items, list): return [{"index": None, "status": "REJECTED", "reason": "expected hypotheses list"}]
    required = {"hypothesis_id", "summary"}
    return [{"index": i, "returned_keys": sorted(item) if isinstance(item, dict) else [],
             "missing_required_keys": sorted(required - set(item) if isinstance(item, dict) else required),
             "unexpected_keys": sorted(set(item) - set(PlanHypothesis.__dataclass_fields__)) if isinstance(item, dict) else [],
             "status": "ACCEPTED" if isinstance(item, dict) and item.get("summary") else "REJECTED"}
            for i, item in enumerate(items)]

def chat_request_spec(model: str, prompt: str) -> dict:
    return {"model": model, "messages": [{"role": "system"}, {"role": "user"}], "stream": False, "response_format": None}

def chat_response_diagnostic(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {"top_level_type": type(payload).__name__}
    choices = payload.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    return {"http_json": True, "top_level_keys": sorted(payload), "object": payload.get("object"),
            "choices_type": type(choices).__name__, "choices_count": len(choices) if isinstance(choices, list) else None,
            "first_choice_keys": sorted(first) if isinstance(first, dict) else None,
            "message_type": type(message).__name__, "message_keys": sorted(message) if isinstance(message, dict) else None,
            "content_type": type(content).__name__, "content_length": len(content) if isinstance(content, str) else None,
            "finish_reason": first.get("finish_reason") if isinstance(first, dict) else None,
            "usage_keys": sorted(payload.get("usage")) if isinstance(payload.get("usage"), dict) else None}

def response_diagnostic(status: int, content_type: str | None, raw: bytes, url: str) -> dict:
    base = {"final_url": url, "http_status": status, "content_type_header": content_type,
            "body_length": len(raw)}
    try:
        payload = json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        base["body_preview"] = raw[:1000].decode("utf-8", "replace")
        base["parse_classification"] = "HTTP_BODY_NOT_JSON"
        return base
    diag = chat_response_diagnostic(payload); base.update(diag)
    if isinstance(payload, dict) and isinstance(payload.get("choices"), list) and payload["choices"]:
        first = payload["choices"][0]
        if isinstance(first, dict) and isinstance(first.get("message"), dict) and isinstance(first["message"].get("content"), str):
            base["content_preview"] = first["message"]["content"][:1000]
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        err = payload["error"]; base["provider_error"] = {k: str(err[k])[:200] for k in ("type", "code", "message") if k in err}
    return base

def extract_chat_content(payload: object) -> str:
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        message = payload["error"].get("message")
        raise RuntimeError("PROVIDER_ERROR: " + (str(message)[:200] if message else "provider returned error"))
    if not isinstance(payload, dict) or not isinstance(payload.get("choices"), list):
        raise RuntimeError("RESPONSE_ENVELOPE_MISSING: " + json.dumps(chat_response_diagnostic(payload), sort_keys=True))
    if not payload["choices"]:
        raise RuntimeError("RESPONSE_CHOICES_EMPTY")
    choice = payload["choices"][0]
    if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
        raise RuntimeError("RESPONSE_MESSAGE_MISSING")
    content = choice["message"].get("content")
    if not isinstance(content, str):
        raise RuntimeError("RESPONSE_CONTENT_MISSING")
    if not content.strip():
        raise RuntimeError("RESPONSE_EMPTY_CONTENT")
    return content

class MockLLMRuntime:
    def generate_hypotheses(self, context, *, max_hypotheses=6):
        ops = context.get("operators", [])
        ids = tuple(item["operator_id"] for item in ops[:2])
        return [PlanHypothesis("mock-1", "Concentrate a blocker and ranged damage at a shared route pressure point", "Derived from supplied routes only", 2, "choke", ("BLOCK", "DAMAGE"), ids, tuple(item["operator_id"] for item in ops[2:4]), ("shared choke",), ids)]
    def revise_hypotheses(self, context, failures, *, max_hypotheses=4):
        return self.generate_hypotheses(context, max_hypotheses=max_hypotheses)

class RealLLMRuntime:
    """OpenAI-compatible adapter; opt-in and intentionally dependency-light."""
    def __init__(self, *, model: str | None = None, endpoint: str | None = None, api_key: str | None = None, max_calls: int = 3, timeout_seconds: float = 45.0):
        self.model = model or os.getenv("OPENAI_MODEL") or os.getenv("ARK_MODEL_ID")
        self.endpoint = endpoint or os.getenv("OPENAI_BASE_URL")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.max_calls, self.calls, self.timeout_seconds = max_calls, 0, timeout_seconds
        self.last_request_started = None; self.last_elapsed_seconds = None; self.last_timeout_phase = None
        self.last_response_diagnostic: dict | None = None
        self.last_schema_diagnostics: list[dict] = []
        missing = tuple(name for name, value in (("OPENAI_API_KEY", self.api_key), ("OPENAI_MODEL/ARK_MODEL_ID", self.model), ("OPENAI_BASE_URL", self.endpoint)) if not value)
        if missing: raise RuntimeError("real LLM configuration missing: " + ", ".join(missing))
    def _call(self, prompt: str) -> list[PlanHypothesis]:
        if self.calls >= self.max_calls: raise RuntimeError("M14 LLM call budget exhausted")
        self.calls += 1
        system = 'Return ONLY {"hypotheses":[...]} as machine-readable JSON. Use supplied facts only; do not simulate numeric combat or choose exact frames.'
        body=json.dumps({"model": self.model, "messages":[{"role":"system","content":system},{"role":"user","content":prompt}], "temperature":0, "stream":False}).encode()
        try:
            req=request.Request(self.endpoint.rstrip("/") + "/chat/completions", data=body, headers={"Authorization":"Bearer " + self.api_key,"Content-Type":"application/json"}, method="POST")
            self.last_request_started = time.time()
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read(); status = response.status; content_type = response.headers.get("Content-Type")
            self.last_elapsed_seconds = time.time() - self.last_request_started
            self.last_response_diagnostic = response_diagnostic(status, content_type, raw, self.endpoint.rstrip("/") + "/chat/completions")
            envelope=json.loads(raw.decode())
            content = extract_chat_content(envelope)
            payload = _extract_json_content(content)
            self.last_schema_diagnostics = hypothesis_schema_diagnostics(payload)
            return parse_hypotheses_payload(payload)
        except error.HTTPError as exc:
            raw = exc.read(); self.last_response_diagnostic = response_diagnostic(exc.code, exc.headers.get("Content-Type"), raw, self.endpoint.rstrip("/") + "/chat/completions")
            category={401:"AUTHENTICATION_ERROR",403:"AUTHENTICATION_ERROR",404:"ENDPOINT_ERROR",429:"RATE_LIMIT"}.get(exc.code,"OTHER_PROVIDER_ERROR")
            raise RuntimeError(f"{category}: HTTP {exc.code}") from exc
        except error.URLError as exc: raise RuntimeError("ENDPOINT_ERROR: connection failed") from exc
        except TimeoutError as exc:
            self.last_elapsed_seconds = time.time() - self.last_request_started if self.last_request_started else None
            self.last_timeout_phase = "READ_OR_CONNECT_UNKNOWN"
            raise RuntimeError("TIMEOUT") from exc
        except RuntimeError: raise
        except (KeyError, json.JSONDecodeError) as exc: raise RuntimeError("RESPONSE_ENVELOPE_ERROR") from exc
        except ValueError as exc: raise RuntimeError("RESPONSE_PARSE_ERROR: " + str(exc)) from exc
    def generate_hypotheses(self, context, *, max_hypotheses=6):
        fields = ", ".join(PlanHypothesis.__dataclass_fields__)
        example = {"hypothesis_id":"H1","summary":"...","reasoning":"...","target_cardinality":2,"tactical_archetype":"...","required_capabilities":[],"preferred_operator_ids":[],"alternative_operator_ids":[],"placement_intents":[],"deployment_order":[],"skill_use_intents":[],"retreat_redeploy_intents":[],"operator_responsibilities":[],"confidence":0.5}
        task={"task":f"propose {max_hypotheses} diverse tactical hypotheses; return ONLY {{hypotheses:[...]}}. Every item must use exactly the canonical fields: {fields}. Example: {json.dumps(example)}. Use supplied facts; do not invent numbers or exact frames", "context":context}
        return self._call(json.dumps(task, ensure_ascii=False))[:max_hypotheses]
    def revise_hypotheses(self, context, failures, *, max_hypotheses=4): return self._call(json.dumps({"task":"revise hypotheses using deterministic failures", "context":context, "failures":failures}, ensure_ascii=False))[:max_hypotheses]

def stage_analysis(fixture) -> StageAnalysis:
    stage=fixture.stage
    ground=tuple((t.x,t.y) for t in stage.stage_map.tiles if t.buildable and t.tile_kind=="GROUND")
    high=tuple((t.x,t.y) for t in stage.stage_map.tiles if t.buildable and t.tile_kind=="HIGH_GROUND")
    routes=tuple({"id":r.route_id,"waypoints":tuple((w.x,w.y) for w in r.waypoints)} for r in stage.routes)
    enemies=tuple({"id":e.enemy_id,"hp":e.stats.max_hp.value,"atk":e.stats.atk.value,"def":e.stats.defense.value,"res":e.stats.magic_resistance.value,"speed":e.stats.move_speed.value} for e in fixture.enemies.values())
    return StageAnalysis(stage.stage_id,(stage.stage_map.width,stage.stage_map.height),ground,high,routes,enemies,len(stage.spawn_events),int(stage.initial_dp.value or 0),int(stage.deployment_limit.value or 0),fixture.approximations_used)

def tactical_requirements(analysis: StageAnalysis) -> tuple[TacticalRequirement, ...]:
    req=[TacticalRequirement("HOLD_ROUTE", "stage has executable routes", .8, tuple(r["id"] for r in analysis.routes))]
    if len(analysis.routes)>1: req.append(TacticalRequirement("COVER_MULTIPLE_ROUTES", "multiple route records", .7))
    if any((e.get("def") or 0)>100 for e in analysis.enemy_types): req.append(TacticalRequirement("DAMAGE", "high defense enemy present", .7))
    return tuple(req)

def operator_context(operators: dict) -> list[dict]:
    out=[]
    for op in sorted(operators.values(), key=lambda x:x.operator_id):
        s=op.phases[0].stats_max
        out.append(asdict(AvailableOperatorSummary(op.operator_id,op.name.value,int(op.star_rarity.value or 0),op.profession.value,op.position.value,s.cost.value,s.block_count.value,s.atk.value,s.defense.value,op.damage_type,s.attack_interval.value)))
    return out

def validate_hypothesis(h: PlanHypothesis, operators: dict) -> tuple[str, str]:
    unknown=[x for x in h.preferred_operator_ids if x not in operators]
    return ("REJECTED", "unknown or blocked operator: " + ",".join(unknown)) if unknown else ("ACCEPTED", "all preferred operators are executable")

def cache_key(stage: StageAnalysis, operators: list[dict], policy: tuple[str,...], model: str) -> str:
    return hashlib.sha256(json.dumps({"stage":asdict(stage),"operators":operators,"policy":policy,"model":model},sort_keys=True,default=str).encode()).hexdigest()

def provider_configuration_status() -> dict[str, str]:
    """Presence-only diagnostics; values including credentials are never exposed."""
    return {name: ("PRESENT" if os.getenv(name) else "ABSENT") for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", "ARK_MODEL_ID")}
