from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from kimi_responses_transport import (  # noqa: E402
    StreamAccumulator,
    extract_response_text,
    validate_tactical_request,
)


OUT = ROOT / "output/r8_1_normal_low_star_tactical_revision_v1"
BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/responses"
MODEL = "kimi-k3"
MECHANICS = "m18.9-stage-device-runtime-v1"
TIMEOUT_SECONDS = 900
CONTEXT = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
FACTS = ROOT / "output/normal_low_star_facts_v1/normal_low_star_facts.json"
SUPPORT = ROOT / "output/normal_low_star_facts_v1/normal_low_star_mechanism_support.json"
OLD_PLAN = ROOT / "output/r8_1_plan_a_bounded_kimi_revision_v4/llm_structured_output.json"
FEEDBACK = ROOT / "docs/review/48fa985/feedback_qualifications.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": str(path.relative_to(ROOT)), "sha256": sha256(path)}


def source_manifest() -> dict[str, Any]:
    paths = [CONTEXT, FACTS, SUPPORT, OLD_PLAN, FEEDBACK, ROOT / "scripts/kimi_responses_transport.py", Path(__file__)]
    return {
        "generation_code": {"sha256": sha256(Path(__file__)), "source": "scripts/run_r8_1_normal_low_star_kimi_revision_v1.py"},
        "inputs": {path.name: file_record(path) for path in paths},
        "mechanics_version": MECHANICS,
        "schema_version": "R8_1_NORMAL_LOW_STAR_KIMI_REVISION_V1_SOURCE_MANIFEST",
    }


def evidence_context() -> dict[str, Any]:
    context = load(CONTEXT)
    old_plan = load(OLD_PLAN)
    plan = old_plan["revised_operational_plans"][0]
    return {
        "authoritative_policy": {
            "ordinary_mode_only": True,
            "rarity_range": [1, 3],
            "debug_configuration": "3★ E1/max level, skill rank 7, potential 1, trust 0; 1★/2★ phase 0/max level; all trust 0",
            "forbidden": ["rarity >= 4", "mode-specific reserve operators", "invented statistics/frames/mechanics"],
        },
        "mechanics_version": MECHANICS,
        "operational_plan_window_frames": [0, 941],
        "previous_plan_experience": {
            "plan_id": plan["operational_plan_id"],
            "tactical_thesis": plan["tactical_thesis"],
            "old_counterexample_context": load(FEEDBACK),
            "confirmed_failures": [
                "Active roadblock occupies [9,2] and makes it non-deployable in the current model.",
                "Merchant upkeep is real: 3 DP every 3 seconds, no retreat refund, auto-retreat when DP is insufficient.",
                "Old A1 maintenance timing numbers used the deployment+90 hypothesis and did not prove exact client timing.",
                "Old A1 used 4★/5★ units, so its roster is outside the current domain.",
            ],
        },
        "normal_low_star_facts": load(FACTS),
        "normal_low_star_runtime_support": load(SUPPORT),
        "stage_devices": context["stage_devices"],
        "stage_facts": {
            "deployable_ground_tiles": context["stage_facts"]["deployable_ground_tiles"],
            "deployable_high_ground_tiles": context["stage_facts"]["deployable_high_ground_tiles"],
            "deployment_limit": context["stage_facts"]["deployment_limit"],
            "enemy_archetypes": context["stage_facts"]["enemy_archetypes"],
            "initial_cost": context["stage_facts"]["initial_cost"],
            "life_points": context["stage_facts"]["life_points"],
            "squad_size_limit": context["stage_facts"]["squad_size_limit"],
        },
        "route_facts": context["exact_route_threats"]["routes"],
        "known_unknowns": [
            "exact client attack timing and target ordering",
            "complete AoE splash geometry",
            "branch traits/talents not explicitly supported in normal_low_star_runtime_support",
            "exact first merchant-upkeep timing",
            "full real-client damage cooperation",
        ],
    }


def output_schema() -> dict[str, Any]:
    plan_properties = {
        key: {"type": "array", "items": {"type": "object", "additionalProperties": True}}
        for key in (
            "allowed_substitutions", "battle_phases", "changed_conflicting_assumptions",
            "conditional_responsibilities", "corridor_responsibilities", "deployment_positions_and_directions",
            "explicit_deadline_basis", "forbidden_substitutions", "formation_transitions",
            "mandatory_tactical_invariants", "opening_responsibilities", "optional_responsibilities",
            "pressure_window_responsibilities", "reserve_strategy", "skill_intents", "temporary_roles",
            "unknown_dependencies", "verification_questions",
        )
    }
    plan_properties.update({
        "changed_conflicting_assumptions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "formation_structure": {"type": "object", "additionalProperties": True},
        "operational_plan_id": {"type": "string"},
        "parent_hypothesis_id": {"type": "string"},
        "selected_low_star_operator_ids": {"type": "array", "items": {"type": "string"}},
        "tactical_thesis": {"type": "string"},
    })
    return {
        "additionalProperties": True,
        "properties": {
            "counterexample_avoidance_explanations": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "deterministic_verifier_questions": {"type": "array", "items": {"type": "string"}},
            "explicit_assumptions": {"type": "array", "items": {"type": "string"}},
            "lessons_from_infeasibility": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "revised_operational_plans": {"type": "array", "maxItems": 1, "minItems": 1, "items": {"additionalProperties": True, "properties": plan_properties, "type": "object"}},
            "retained_tactical_knowledge": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "revised_stage_understanding": {"type": "object", "additionalProperties": True},
            "revised_tactical_requirements": {"type": "object", "additionalProperties": True},
            "uncertainties": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        },
        "type": "object",
    }


def prompt_text(evidence: dict[str, Any]) -> str:
    return f"""You are Kimi-K3, the tactical decision maker for Arknights stage main_08-01 / R8-1.
Make exactly one revised frame 0-941 opening OperationalPlan using ordinary-mode 1-3 star operators only. Do not output multiple plans.

Previous plans failed their own responsibility/economy constraints. Treat that evidence as conditional tactical knowledge, not as proof that every opening is impossible. You may revise responsibilities, simultaneity, deadlines, role sharing, formation evolution, fire allocation, skill scheduling, retreats and concessions. The supplied Python catalog is evidence; it does not choose tactics.

Hard domain rules:
- Only operators explicitly present in normal_low_star_facts may be selected; rarity must be 1-3 and ordinary-mode eligibility must be true.
- Exclude mode-specific reserve operators and all 4-star or higher units.
- Preserve all explicit tactical invariants you decide to require. Unsupported mechanics may be included only as experimental optional ideas, never as mandatory proof of success.
- Do not invent statistics, deployment costs, frames, damage numbers, ranges, durations or mechanics.
- Explain exactly how the revised plan addresses the old merchant-upkeep and roadblock counterexamples. You need not copy the old A1 formation.

Mechanics and evidence status:
- Active mechanics version: {MECHANICS}. Stage initial DP is 10, natural DP is +1/s, life is 5, deployment limit is 8, squad limit is 12.
- The full 34-operator ordinary 1-3 star catalog and per-operator runtime support are supplied. 3-star facts use E1/max level, skill rank 7, potential 1 and trust 0; 1/2-star facts use phase 0/max level.
- Deployment SP talent, deployment global heal, self-cost talent, and one proven redeploy-time reduction are implemented as minimal generic mechanics. Exact AoE splash geometry, probability talents, summons, complex status effects and other unsupported branch mechanics remain UNKNOWN or unsupported; do not make them mandatory.
- Active roadblock devices occupy their tiles. The current model rejects deployment on [9,2], [5,3], [7,4], [1,4] and [3,1] while those devices are active.
- Merchant experience is historical only: upkeep is real, refunds are not confirmed, exact first debit remains UNKNOWN, and the old A1 units are outside the current star range.

Operational output requirements:
- Give a concrete tactical thesis, opening responsibilities, route/pressure responsibilities, phases, positions/direction intent, temporary roles, stable roles, skill intents, reserve strategy, allowed/forbidden substitutions, and deadline basis.
- Every selected operator ID must be sourced from the supplied catalog. Explicitly state where selected mechanics are runtime-supported, approximate, or UNKNOWN.
- Every deadline must reference route pressure, blocking, damage, economy or formation transition rather than a universal frame.
- Do not claim feasibility. The deterministic verifier will at most choose 3 candidates per required slot, evaluate 16 complete combinations, and produce one direction-complete action candidate; it will run no stage simulation.

Return one JSON object conforming to the supplied schema. The JSON evidence block below contains the complete low-star catalog, runtime support, stage facts and previous failure feedback.

JSON_EVIDENCE_BEGIN
{json.dumps(evidence, ensure_ascii=False, sort_keys=True)}
JSON_EVIDENCE_END"""


def prepare() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = evidence_context()
    prompt = prompt_text(evidence)
    payload = {
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "max_output_tokens": 128000,
        "model": MODEL,
        "stream": True,
        "text": {"format": {"name": "r8_1_normal_low_star_kimi_revision_v1", "schema": output_schema(), "strict": False, "type": "json_schema"}},
    }
    write("llm_evidence_context.json", evidence)
    write("revision_output_schema.json", output_schema())
    write_text("constraint_informed_prompt.txt", prompt)
    write("llm_request_fingerprint.json", {
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "request_sha256": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "schema_version": "R8_1_NORMAL_LOW_STAR_KIMI_REVISION_V1_REQUEST_FINGERPRINT",
    })
    write("source_input_manifest.json", source_manifest())
    return payload


def stream_once(payload: dict[str, Any]) -> tuple[dict[str, Any], StreamAccumulator, bytes]:
    errors = validate_tactical_request(payload)
    if errors:
        raise RuntimeError("TRANSPORT_REQUEST_VALIDATION_FAILED:" + ",".join(errors))
    if (OUT / "llm_raw_response.txt").is_file():
        raise RuntimeError("LLM_RAW_RESPONSE_ALREADY_EXISTS_SINGLE_CALL_POLICY")
    api_key = os.environ.get("ARK_API_KEY_agent")
    if not api_key:
        raise RuntimeError("MISSING_CREDENTIAL_ENVIRONMENT")
    write("llm_request.json", payload)
    request = urllib.request.Request(
        BASE_URL,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Accept": "text/event-stream", "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    chunks: list[bytes] = []
    accumulator = StreamAccumulator()
    current_event = None
    data_lines: list[str] = []
    sequence = 0
    http_status = None
    request_id = None
    error = None
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            http_status = response.status
            request_id = response.headers.get("x-request-id")
            for raw_bytes in response:
                chunks.append(raw_bytes)
                line = raw_bytes.decode(errors="replace").rstrip("\r\n")
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())
                elif not line:
                    if data_lines or current_event:
                        raw_data = "\n".join(data_lines)
                        try:
                            data = json.loads(raw_data) if raw_data else {}
                        except json.JSONDecodeError:
                            data = {"malformed_data": raw_data}
                        sequence += 1
                        from kimi_responses_transport import SSEEvent
                        accumulator.observe(SSEEvent(current_event or "message", data, sequence))
                    current_event = None
                    data_lines = []
    except urllib.error.HTTPError as exc:
        http_status = exc.code
        request_id = exc.headers.get("x-request-id")
        chunks.append(exc.read())
        error = f"HTTPError:{exc.code}"
    except Exception as exc:
        error = f"{type(exc).__name__}:{exc}"
    raw = b"".join(chunks)
    write_text("llm_raw_response.txt", raw.decode(errors="replace"))
    diagnostics = {
        "base_url": BASE_URL,
        "duration_seconds": time.time() - started,
        "http_status": http_status,
        "model": accumulator.response_envelope.get("model") if accumulator.response_envelope else None,
        "request_id": request_id,
        "safety_notes": ["No retry was attempted.", "Credentials are not persisted."],
        "terminal_event": accumulator.terminal_event,
        "transport_error": error,
    }
    write("llm_call_record.json", diagnostics)
    return diagnostics, accumulator, raw


def parse_and_validate_response() -> dict[str, Any]:
    raw = (OUT / "llm_raw_response.txt").read_text(encoding="utf-8")
    from kimi_responses_transport import parse_sse
    accumulator = StreamAccumulator()
    for event in parse_sse(raw):
        accumulator.observe(event)
    classification = accumulator.classify()
    write("response_completion_validation.json", {
        "kimi_call_count": 1,
        "model": accumulator.response_envelope.get("model") if accumulator.response_envelope else MODEL,
        "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "single_call_policy": "PASS",
        **classification,
    })
    if not classification["complete"]:
        raise RuntimeError("KIMI_SINGLE_CALL_DID_NOT_COMPLETE_SUCCESSFULLY")
    text = extract_response_text(accumulator.response_envelope or {})[0]
    parsed = json.loads(text)
    write("llm_structured_output.json", parsed)
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "call"])
    args = parser.parse_args()
    payload = prepare()
    if args.phase == "prepare":
        write("prepare_status.json", {"phase": "PREPARED", "request_schema": payload["text"]["format"]["name"]})
        return
    diagnostics, _, _ = stream_once(payload)
    if diagnostics["transport_error"] or diagnostics["http_status"] != 200:
        write("final_status.json", {"kimi_call_count": 1, "status": "KIMI_CALL_FAILED_NO_RETRY", **diagnostics})
        raise RuntimeError("KIMI_SINGLE_CALL_FAILED")
    parsed = parse_and_validate_response()
    plans = parsed.get("revised_operational_plans", [])
    write("grounding_validation.json", {
        "kimi_call_count": 1,
        "one_operational_plan": len(plans) == 1,
        "selected_operator_ids": plans[0].get("selected_low_star_operator_ids", []) if plans else [],
        "schema_version": "R8_1_NORMAL_LOW_STAR_KIMI_REVISION_V1_GROUNDING_VALIDATION",
        "status": "PASS" if len(plans) == 1 else "FAIL",
    })
    write("final_status.json", {
        "faithful_witness": None,
        "kimi_call_count": 1,
        "mechanics_changed": False,
        "new_operational_plans": len(plans),
        "stage_prefix_simulations": 0,
        "status": "KIMI_RESPONSE_RECEIVED_DETERMINISTIC_VALIDATION_PENDING",
    })


if __name__ == "__main__":
    main()
