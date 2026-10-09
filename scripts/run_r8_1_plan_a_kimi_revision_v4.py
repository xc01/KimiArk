from __future__ import annotations

import argparse
import hashlib
import importlib.util
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


OUT = ROOT / "output/r8_1_plan_a_bounded_kimi_revision_v4"
BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/responses"
MODEL = "kimi-k3"
MECHANICS = "m18.9-stage-device-runtime-v1"
TIMEOUT_SECONDS = 900
OLD_SCRIPT = ROOT / "scripts/run_r8_1_plan_a_fixed_candidate_contract_v1.py"
CORRECTED_REVIEW = ROOT / "docs/review/d9304bb/corrected_calculations.json"
CONTEXT = ROOT / "output/r8_1_llm_tactical_context_v1/deterministic_context.json"
OLD_PLAN = ROOT / "output/r8_1_constraint_informed_revision_v3/revised_operational_plans.json"
CENSUS = ROOT / "output/operator_runtime_fidelity_v1/all_operator_census.json"
RELEVANT_OPERATORS = [
    "char_103_angel", "char_4100_caper", "char_365_aprl",
    "char_272_strong", "char_445_wscoot", "char_4155_talr", "char_455_nothin",
]


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


def load_old_module() -> Any:
    spec = importlib.util.spec_from_file_location("plan_a_fixed_contract", OLD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def source_manifest() -> dict[str, Any]:
    paths = [
        OLD_SCRIPT, CORRECTED_REVIEW, CONTEXT, OLD_PLAN, CENSUS,
        ROOT / "scripts/build_operator_runtime_fidelity.py",
        ROOT / "scripts/kimi_responses_transport.py",
        ROOT / "scripts/run_r8_1_plan_a_kimi_revision_v4.py",
    ]
    return {
        "generation_code": {
            "present": (ROOT / "scripts/build_operator_runtime_fidelity.py").is_file(),
            "sha256": sha256(ROOT / "scripts/build_operator_runtime_fidelity.py"),
            "original_generation_commit": "UNKNOWN_ORIGINAL_GENERATION_COMMIT",
        },
        "inputs": {path.name: file_record(path) for path in paths},
        "mechanics_version": MECHANICS,
        "schema_version": "R8_1_PLAN_A_KIMI_REVISION_V4_SOURCE_MANIFEST_V1",
    }


def corrected_fixed_contracts() -> dict[str, Any]:
    module = load_old_module()
    result = module.build(write_artifacts=False)
    return {
        "candidate_counts": result["candidate_counts"],
        "economy": result["economy"],
        "final_status": result["final_status"],
        "finite_window_damage": result["finite_window_damage"],
        "schema_version": "R8_1_PLAN_A_CORRECTED_FIXED_CONTRACTS_EVIDENCE_V1",
        "source_manifest": source_manifest(),
        "structural_combinations": result["structural_combinations"],
    }


def evidence_context(corrected: dict[str, Any]) -> dict[str, Any]:
    context = load(CONTEXT)
    old_plans = load(OLD_PLAN)
    plan = next(row for row in old_plans["plans"] if row["operational_plan_id"] == "R8OP-A-MERGED-ANCHOR-REFUND-LATTICE")
    census = load(CENSUS)["operators"]
    return {
        "mechanics_version": MECHANICS,
        "operational_plan_window_frames": [0, 941],
        "operators": [
            row for row in census if row["operator_id"] in RELEVANT_OPERATORS
        ],
        "original_plan_A": plan,
        "review_evidence_file": "docs/review/d9304bb/corrected_calculations.json",
        "stage_devices": context["stage_devices"],
        "stage_facts": {
            "deployment_limit": context["stage_facts"]["deployment_limit"],
            "deployable_ground_tiles": context["stage_facts"]["deployable_ground_tiles"],
            "deployable_high_ground_tiles": context["stage_facts"]["deployable_high_ground_tiles"],
            "enemy_archetypes": context["stage_facts"]["enemy_archetypes"],
            "initial_cost": context["stage_facts"]["initial_cost"],
            "life_points": context["stage_facts"]["life_points"],
        },
        "route_facts": [
            row for row in context["exact_route_threats"]["routes"]
            if row["route_id"] in {"route-1", "route-2", "route-3", "route-6", "route-7", "route-8"}
        ],
        "unknowns_must_remain_unknown": [
            "retreat refund amount and to-account frame",
            "merchant upkeep and long-run economy",
            "ammo runtime",
            "[9,2] roadblock occupancy/deployment legality and possible destruction timing",
            "exact client target ordering and attack timing",
            "full damage cooperation and traits/talents",
        ],
        "verified_operator_candidates": [
            {key: row[key] for key in ("slot_id", "operator_id", "cost", "hp", "defense", "block_count", "qualification_blockers")}
            for row in load(ROOT / "output/r8_1_plan_a_opening_witness_v1/plan_a_bounded_opening_frontier.json")["candidates"]
        ],
    }


def output_schema() -> dict[str, Any]:
    plan_properties = {
        key: {"type": "array", "items": {"type": "string"}}
        for key in (
            "allowed_substitutions", "forbidden_substitutions", "formation_transitions",
            "mandatory_tactical_invariants", "opening_responsibilities",
            "pressure_window_responsibilities", "route_responsibilities",
            "skill_intents", "verification_questions",
        )
    }
    plan_properties.update(
        {
            "battle_phases": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "changed_conflicting_assumptions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "compiler_slots": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "conditional_responsibilities": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "deployment_positions_and_directions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "explicit_deadline_basis": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "formation_structure": {"type": "object", "additionalProperties": True},
            "operational_plan_id": {"type": "string"},
            "optional_responsibilities": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "parent_hypothesis_id": {"type": "string"},
            "reserve_strategy": {"type": "object", "additionalProperties": True},
            "selected_affordance_ids": {"type": "array", "items": {"type": "string"}},
            "tactical_thesis": {"type": "string"},
            "temporary_roles": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "unknown_dependencies": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        }
    )
    arrays = {
        key: {"type": "array", "items": {"type": "object", "additionalProperties": True}}
        for key in (
            "counterexample_avoidance_explanations", "lessons_from_infeasibility",
            "rejected_tactical_assumptions", "retained_tactical_knowledge",
        )
    }
    return {
        "additionalProperties": True,
        "properties": {
            **arrays,
            "explicit_assumptions": {"type": "array", "items": {"type": "string"}},
            "deterministic_verifier_questions": {"type": "array", "items": {"type": "string"}},
            "uncertainties": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "revised_operational_plans": {
                "type": "array",
                "maxItems": 1,
                "minItems": 1,
                "items": {"additionalProperties": True, "properties": plan_properties, "type": "object"},
            },
        },
        "type": "object",
    }


def prompt_text(corrected: dict[str, Any], evidence: dict[str, Any]) -> str:
    caper = next(row for row in corrected["finite_window_damage"]["candidate_contracts"] if row["operator_id"] == "char_4100_caper")
    return f"""You are Kimi-K3, the tactical decision maker for Arknights stage main_08-01 / R8-1.
Make exactly one bounded revision of Plan A's frame 0-941 opening OperationalPlan. Do not output multiple plans.

Your task is not to satisfy frame 250 mechanically. Frame 250 is only a conditional consequence of the old assumptions listed below. You may change opening structure, resource dependence, role sharing, phase handoffs, fire allocation, retreat timing, temporary blocking or conditional concessions if justified.

Independently verified facts:
- Mechanics: {MECHANICS}. Initial DP 10, DP +1/s, life 5, deployment limit 8.
- The historical selected-usage tables are delivered, but their original generation commit remains UNKNOWN.
- caper (char_4100_caper) can cover [8,5] from [9,2] facing DOWN; angel/aprl cannot.
- wscoot's GameData description says it normally does not attack and has block 0 until its skill activates. That contradicts the old skill-independent dam responsibility.
- merchant listed deployment cost cannot stand in for long-run upkeep/economy.
- Of the old 12 structural tuples, six full-deployment branches assign the same duelist to A04 and A05; one live operator cannot become two deployments. Omitting A05 is the separate COND_ROUTE6 branch.
- trap_020_roadblock#2 currently occupies [9,2]; whether the anchor tile is deployable, or must be destroyed first, is UNKNOWN.

Conditional caper calculation under the old assumptions only: ATK 344, one-second interval, initial SP 0, three normal attacks then one 2.3x skill attack, DEF 150, two 3300 HP targets continuously held on [8,5], only those targets eligible, no other fire, instant hits. With first attack at 450, route-1 dies at 780 and route-3 at 1140. To finish strictly before 805 and 941, first attack must be at or before 250. With the fixed 13 DP prefix, no refund and no upkeep, only 5.333 DP is available at frame 250, so 12 DP caper cannot be paid. Do not turn 250 into a universal FIRE deadline.

Corrected hypothetical economy only: 12 DP anchor, hypothetical 5 DP refund continuously credited, and no upkeep yields +2.3 DP after both duelists deploy by 729. This is not a confirmed refund or feasibility certificate.

UNKNOWNs: refund amount/to-account frame, merchant upkeep, ammo runtime, [9,2] roadblock legality, exact target ordering, exact client attack timing, full damage cooperation, traits/talents. Unsupported does not mean impossible in the real game.

Operational constraints:
- Use supplied operators, tiles, routes and mechanics. Do not invent statistics, frames or mechanics.
- Preserve Plan A's strategic continuity where justified, but you may change its tactical assumptions.
- Specify opening responsibilities, route/pressure windows, positions and direction intent, skill intent, temporary roles, retreat/handoff, conditional branches, establishment/kill-deadline basis, allowed/forbidden substitutions and UNKNOWN dependencies.
- Do not require exact client timing or unsupported mechanics for mandatory success.
- The deterministic verifier will test at most 3 candidates per required opening slot, at most 16 full combinations, and no stage simulation.

Original Plan A, corrected calculations and source facts are supplied in the JSON evidence block below. Explain which old assumptions you reject, which you retain, and exactly why your revision addresses the counterexamples. Return one JSON object conforming to the provided schema.

JSON_EVIDENCE_BEGIN
{json.dumps({"corrected_fixed_contracts": corrected, "source_facts_and_operators": evidence}, ensure_ascii=False, sort_keys=True)}
JSON_EVIDENCE_END"""


def prepare() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    corrected = corrected_fixed_contracts()
    evidence = evidence_context(corrected)
    prompt = prompt_text(corrected, evidence)
    payload = {
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "max_output_tokens": 128000,
        "model": MODEL,
        "stream": True,
        "text": {"format": {"name": "r8_1_plan_a_bounded_kimi_revision_v4", "schema": output_schema(), "strict": False, "type": "json_schema"}},
    }
    write("corrected_fixed_contracts.json", corrected)
    write("llm_evidence_context.json", evidence)
    write("revision_output_schema.json", output_schema())
    write_text("constraint_informed_prompt.txt", prompt)
    write("llm_request_fingerprint.json", {
        "request_sha256": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "schema_version": "R8_1_PLAN_A_KIMI_REVISION_V4_REQUEST_FINGERPRINT_V1",
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
            for raw in response:
                raw_bytes = raw if isinstance(raw, bytes) else str(raw).encode()
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
                        event = SSEEvent(current_event or "message", data, sequence)
                        accumulator.observe(event)
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
        "call_count": 1,
        "completed_at": time.time(),
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
    write("grounding_validation.json", {
        "one_operational_plan": len(parsed.get("revised_operational_plans", [])) == 1,
        "schema_version": "R8_1_PLAN_A_KIMI_REVISION_V4_GROUNDING_VALIDATION_V1",
        "status": "PASS" if len(parsed.get("revised_operational_plans", [])) == 1 else "FAIL",
    })
    write("final_status.json", {
        "faithful_witness": None,
        "kimi_call_count": 1,
        "mechanics_changed": False,
        "new_operational_plans": 1,
        "stage_prefix_simulations": 0,
        "status": "KIMI_RESPONSE_RECEIVED_DETERMINISTIC_VALIDATION_PENDING",
    })


if __name__ == "__main__":
    main()
