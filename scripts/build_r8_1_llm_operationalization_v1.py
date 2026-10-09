from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "output/r8_1_kimi_k3_tactical_reasoning_v1"
SEARCH_DIR = ROOT / "output/r8_1_kimi_k3_deterministic_search_v1"
CONTEXT_DIR = ROOT / "output/r8_1_llm_tactical_context_v1"
OUT = ROOT / "output/r8_1_llm_operationalization_v1"
MECHANICS_VERSION = "m18.9-stage-device-runtime-v1"
SELECTED_HYPOTHESES = [
    "HYP-01-DUAL-ANCHOR-SHARED-NET",
    "HYP-06-PRECONTACT-MAXIMALIST",
    "HYP-07-W06-FIRST-RESOURCE-SCHEDULING",
    "HYP-09-STAGGERED-HANDOFF-FORMATION",
    "HYP-10-LANE01-CONSOLIDATION-LANE02-ATTRITION",
]
PLAN_FIELDS = [
    "operational_plan_id",
    "parent_hypothesis_id",
    "tactical_thesis",
    "battle_phases",
    "phase_responsibilities",
    "corridor_responsibilities",
    "pressure_window_responsibilities",
    "opening_structure",
    "stable_structure",
    "formation_transitions",
    "frontline_structure",
    "damage_structure",
    "sustain_structure",
    "reserve_structure",
    "skill_intents",
    "temporary_roles",
    "handoffs",
    "selected_affordances",
    "allowed_substitutions",
    "forbidden_substitutions",
    "invariants",
    "assumptions",
    "verifier_questions",
]


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def tile_refs(text: str) -> list[list[int]]:
    found: list[list[int]] = []
    for row, column in re.findall(r"\[(\d+),(\d+)\]", text):
        tile = [int(row), int(column)]
        if tile not in found:
            found.append(tile)
    return found


def provider_profile() -> dict[str, Any]:
    config_path = Path.home() / ".codex/config.toml"
    profile_path = Path.home() / ".codex/agent.config.toml"
    config_text = config_path.read_text() if config_path.exists() else ""
    profile_text = profile_path.read_text() if profile_path.exists() else ""
    credential_present = "ARK_API_KEY_agent" in __import__("os").environ and bool(__import__("os").environ["ARK_API_KEY_agent"])
    return {
        "profile": "agent",
        "model_provider": "volcengine-agent-plan",
        "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3",
        "wire_api": "responses",
        "model": "kimi-k3",
        "credential_env": "ARK_API_KEY_agent",
        "credential_present": credential_present,
        "profile_source": "~/.codex/agent.config.toml",
        "provider_block_source": "~/.codex/config.toml",
        "profile_matches_approved_configuration": (
            'model = "kimi-k3"' in profile_text
            and 'model_provider = "volcengine-agent-plan"' in profile_text
            and 'base_url = "https://ark.cn-beijing.volces.com/api/plan/v3"' in config_text
            and 'env_key = "ARK_API_KEY_agent"' in config_text
            and 'wire_api = "responses"' in config_text
        ),
    }


def build_semantic_signatures(originals: list[dict[str, Any]]) -> dict[str, Any]:
    signatures = []
    for hypothesis in originals:
        if hypothesis["hypothesis_id"] == "HYP-03-ROADBLOCK-DEMOLITION-92":
            continue
        text = json.dumps(hypothesis, ensure_ascii=False).lower()
        explicitly_stated = {
            "opening": bool(hypothesis.get("opening_concept")),
            "formation_evolution": bool(hypothesis.get("formation_evolution")),
            "corridor_responsibilities": bool(hypothesis.get("corridor_responsibilities")),
            "interception": bool(hypothesis.get("interception_strategy")),
            "damage": bool(hypothesis.get("damage_concept")),
            "sustain": bool(hypothesis.get("sustain_concept")),
            "reserve": bool(hypothesis.get("reserve_concept")),
            "temporary_roles": bool(hypothesis.get("temporary_roles")),
            "skill_intent": bool(hypothesis.get("skill_intent")),
            "handoff": "handoff" in text or "retreat" in text or "replaced" in text,
        }
        signatures.append({
            "hypothesis_id": hypothesis["hypothesis_id"],
            "source": "original successful Kimi-K3 tactical output",
            "signature": {
                key: hypothesis.get(key)
                for key in [
                    "tactical_thesis",
                    "opening_concept",
                    "formation_evolution",
                    "corridor_responsibilities",
                    "interception_strategy",
                    "damage_concept",
                    "sustain_concept",
                    "reserve_concept",
                    "skill_intent",
                    "temporary_roles",
                ]
            },
            "explicitly_stated_dimensions": explicitly_stated,
            "excluded_semantics": [
                "deterministic preferences",
                "new tactical hypotheses",
                "unsupported exact values",
            ],
        })
    return {
        "schema_version": "R8_1_HYPOTHESIS_SEMANTIC_SIGNATURE_V1",
        "source_sha256": sha256_json(originals),
        "signatures": signatures,
    }


def build_timeline_fidelity(originals: list[dict[str, Any]], funnel: dict[str, Any]) -> dict[str, Any]:
    by_id = {item["hypothesis_id"]: item for item in originals}
    records: list[dict[str, Any]] = []
    by_fingerprint: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in funnel["evaluation_records"]:
        by_fingerprint[record["strategy_fingerprint"]].append(record)
    for fingerprint, grouped_records in by_fingerprint.items():
        parent_assessments = []
        for record in grouped_records:
            hypothesis_id = record["llm_hypothesis_id"]
            parent = by_id[hypothesis_id]
            opening_refs = tile_refs(parent["opening_concept"])
            core_refs = sorted({
                tuple(tile)
                for text in parent["formation_evolution"] + parent["corridor_responsibilities"] + [parent["interception_strategy"]]
                for tile in tile_refs(text)
            })
            action_tiles = [tuple(action["tile"]) for action in record.get("actions", []) if action.get("tile")]
            matched_opening = [list(tile) for tile in action_tiles if tile in {tuple(item) for item in opening_refs}]
            matched_core = [list(tile) for tile in action_tiles if tile in set(core_refs)]
            if opening_refs and len(matched_opening) == len(opening_refs) and core_refs and len(matched_core) / max(1, len(core_refs)) >= 0.6:
                classification = "FAITHFUL"
            elif matched_opening or matched_core:
                classification = "PARTIALLY_FAITHFUL"
            else:
                classification = "SEMANTICALLY_COLLAPSED"
            parent_assessments.append({
                "llm_hypothesis_id": hypothesis_id,
                "classification": classification,
                "matched_opening_tiles": matched_opening,
                "matched_formation_or_corridor_tiles": sorted(matched_core),
            })
        opening_refs = parent_assessments[0]["matched_opening_tiles"]
        if len({item["llm_hypothesis_id"] for item in grouped_records}) > 1:
            classification = "SEMANTICALLY_COLLAPSED"
            collapse_reason = "The exact strategy fingerprint is shared across multiple parent hypotheses."
        else:
            classification = parent_assessments[0]["classification"]
            collapse_reason = None
        records.append({
            "strategy_fingerprint": fingerprint,
            "llm_hypothesis_ids": sorted({item["llm_hypothesis_id"] for item in grouped_records}),
            "classification": classification,
            "collapse_reason": collapse_reason,
            "parent_assessments": parent_assessments,
            "opening_tile_refs": opening_refs,
            "result": record.get("result"),
        })
    counts = Counter(item["classification"] for item in records)
    by_hypothesis: dict[str, Counter[str]] = defaultdict(Counter)
    for item in records:
        for assessment in item["parent_assessments"]:
            by_hypothesis[assessment["llm_hypothesis_id"]][assessment["classification"]] += 1
    return {
        "schema_version": "R8_1_TIMELINE_FIDELITY_AUDIT_V1",
        "source_timeline_count": len(funnel["evaluation_records"]),
        "unique_timelines_audited": len(records),
        "classification_method": {
            "FAITHFUL": "all opening-concept tiles present and at least 60% explicit formation/corridor tiles present",
            "PARTIALLY_FAITHFUL": "at least one explicit opening or formation/corridor tile present",
            "SEMANTICALLY_COLLAPSED": "no explicit opening or formation/corridor tile present, or the exact strategy fingerprint is shared across multiple parent hypotheses",
            "CONTRADICTS_PARENT_HYPOTHESIS": "reserved; no explicit forbidden structure was detected",
            "method_limitation": "tile-presence is an interpretable lower-bound audit; it does not infer unstated tactical intent",
        },
        "classification_counts": dict(counts),
        "by_hypothesis": {key: dict(value) for key, value in sorted(by_hypothesis.items())},
        "records": records,
    }


def build_gap_analysis(originals: list[dict[str, Any]]) -> dict[str, Any]:
    classifications = {
        "HYP-01-DUAL-ANCHOR-SHARED-NET": "NEEDS_MODERATE_OPERATIONALIZATION",
        "HYP-02-LEAK-LINE-FORTRESS": "NEEDS_MODERATE_OPERATIONALIZATION",
        "HYP-04-FAST-REDEPLOY-ROTATION": "NEEDS_STRONG_OPERATIONALIZATION",
        "HYP-05-PIONEER-ECONOMY-RAMP": "NEEDS_MODERATE_OPERATIONALIZATION",
        "HYP-06-PRECONTACT-MAXIMALIST": "NEEDS_STRONG_OPERATIONALIZATION",
        "HYP-07-W06-FIRST-RESOURCE-SCHEDULING": "NEEDS_STRONG_OPERATIONALIZATION",
        "HYP-08-C07-DEDICATED-KILLBOX": "NEEDS_MODERATE_OPERATIONALIZATION",
        "HYP-09-STAGGERED-HANDOFF-FORMATION": "NEEDS_STRONG_OPERATIONALIZATION",
        "HYP-10-LANE01-CONSOLIDATION-LANE02-ATTRITION": "NEEDS_MODERATE_OPERATIONALIZATION",
    }
    records = []
    for hypothesis in originals:
        hypothesis_id = hypothesis["hypothesis_id"]
        if hypothesis_id not in classifications:
            continue
        missing = [
            "structured phase responsibilities",
            "explicit affordance choices",
            "allowed substitutions",
            "forbidden substitutions",
            "operational invariants",
        ]
        if "handoff" in json.dumps(hypothesis).lower() or "retreat" in json.dumps(hypothesis).lower():
            missing.append("explicit handoff overlap and tile-transfer semantics")
        if "reserve" in hypothesis.get("reserve_concept", "").lower():
            missing.append("semantic reserve trigger")
        records.append({
            "hypothesis_id": hypothesis_id,
            "classification": classifications[hypothesis_id],
            "missing_operational_dimensions": missing,
            "reason": "The original hypothesis supplies tactical prose but does not supply a compiler-facing responsibility/variation/transition contract.",
        })
    high = sum(item["classification"].endswith("STRONG_OPERATIONALIZATION") for item in records)
    overall = "HIGH" if high >= len(records) / 2 else "MEDIUM"
    return {
        "schema_version": "R8_1_OPERATIONALIZATION_GAP_ANALYSIS_V1",
        "overall_operationalization_gap": overall,
        "classification_basis": "presence of compiler-facing phase responsibility, affordance choice, substitution, transition, and invariant semantics",
        "records": records,
    }


def build_collisions(fidelity: dict[str, Any], funnel: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    high_tiles = {tuple(tile) for tile in context["stage_facts"]["deployable_high_ground_tiles"]}
    records_by_fingerprint = {record["strategy_fingerprint"]: record for record in funnel["evaluation_records"]}
    signatures: dict[str, list[str]] = defaultdict(list)
    for audit in fidelity["records"]:
        record = records_by_fingerprint[audit["strategy_fingerprint"]]
        actions = record.get("actions", [])
        opening = tuple(sorted(tuple(action.get("tile", [])) for action in actions if action.get("frame", 0) <= 240))
        ground = tuple(sorted(tuple(action.get("tile", [])) for action in actions if action.get("tile") and tuple(action["tile"]) not in high_tiles))
        high = tuple(sorted(tuple(action.get("tile", [])) for action in actions if action.get("tile") and tuple(action["tile"]) in high_tiles))
        structural = (len(actions), opening, ground, high)
        signatures[json.dumps(structural, separators=(",", ":"))].append(record["llm_hypothesis_id"])
    collisions = [
        {"structural_signature": json.loads(signature), "hypothesis_ids": sorted(set(hypothesis_ids))}
        for signature, hypothesis_ids in signatures.items()
        if len(set(hypothesis_ids)) > 1
    ]
    return {
        "schema_version": "R8_1_CROSS_HYPOTHESIS_REALIZATION_COLLISIONS_V1",
        "comparison_dimensions": ["deployment_count", "opening_tile_set", "ground_tile_set", "high_ground_tile_set"],
        "cross_hypothesis_realization_collisions": len(collisions),
        "collisions": collisions,
        "interpretation": "No opaque embeddings were used; equality means these interpretable structural dimensions are identical.",
    }


def build_affordances(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    affordances: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    clusters = context["route_pressure_clusters"]["clusters"]
    windows = context["pressure_windows"]["windows"]
    for index, region in enumerate(context["candidate_interception_regions"], 1):
        affordance_id = f"IR_{index:02d}"
        cluster_id = region["cluster_id"]
        affordances.append({
            "affordance_id": affordance_id,
            "type": "INTERCEPTION_REGION",
            "corridors": [cluster_id],
            "pressure_windows": [item["window_id"] for item in windows if cluster_id in item["active_clusters"]],
            "legal_tiles": region["tiles"],
            "served_routes": region["route_ids"],
            "limitations": ["not an assertion that this is the best tactical option"],
        })
        provenance.append({
            "affordance_id": affordance_id,
            "source": "deterministic_context.json route_pressure_clusters.clusters.candidate_interception_regions",
            "deterministic_evidence": region,
        })
    for index, region in enumerate(context["candidate_shared_coverage_regions"], 1):
        affordance_id = f"SC_{index:02d}"
        served_clusters = sorted({
            cluster["cluster_id"]
            for cluster in clusters
            if set(cluster["member_route_ids"]) & set(region["route_ids"])
        })
        affordances.append({
            "affordance_id": affordance_id,
            "type": "SHARED_RANGED_COVERAGE_REGION",
            "corridors": served_clusters,
            "pressure_windows": [item["window_id"] for item in windows if set(item["active_clusters"]) & set(served_clusters)],
            "legal_tiles": [region["tile"]],
            "served_routes": region["route_ids"],
            "limitations": ["route presence does not prove sufficient damage or timing"],
        })
        provenance.append({
            "affordance_id": affordance_id,
            "source": "deterministic_context.json candidate_shared_coverage_regions",
            "deterministic_evidence": region,
        })
    stage_facts = context["stage_facts"]
    economy = stage_facts["dp_economy_pressure"]
    affordances.extend([
        {
            "affordance_id": "OE_01",
            "type": "OPENING_ECONOMY_CLASS",
            "description": "A first responsibility costing no more than 10 DP can exist at battle start; a second cost-10 responsibility can exist by the W02 start boundary.",
            "deadline_frames": [0, 600],
            "limitations": ["availability depends on the selected operator's actual cost and block role"],
        },
        {
            "affordance_id": "OE_02",
            "type": "OPENING_ECONOMY_CLASS",
            "description": "The explicit frame-27 and frame-191 opening blockers constrain early costs to no more than 10 and 16 DP respectively before any DP-generation effects.",
            "deadline_frames": [27, 191],
            "limitations": ["exact deployment sequence depends on selected costs and skill effects"],
        },
        {
            "affordance_id": "OE_03",
            "type": "OPENING_ECONOMY_CLASS",
            "description": "By the frame-725 and frame-729 lane-02 deadlines, cumulative natural DP supports multiple cheap-to-moderate responsibilities, but not arbitrary simultaneous expensive deployments.",
            "deadline_frames": [725, 729],
            "limitations": ["cost viability must be checked for each selected roster realization"],
        },
        {
            "affordance_id": "FT_01",
            "type": "FORMATION_TRANSITION_CLASS",
            "description": "Independent reinforcement is possible while prior deployed units remain on distinct legal tiles.",
            "limitations": ["deployment limit is 8"],
        },
        {
            "affordance_id": "FT_02",
            "type": "FORMATION_TRANSITION_CLASS",
            "description": "A temporary hold can remain deployed as additional responsibilities arrive if no tile conflict or deployment-limit conflict occurs.",
            "limitations": ["does not imply same-tile replacement"],
        },
        {
            "affordance_id": "FT_03",
            "type": "FORMATION_TRANSITION_CLASS",
            "description": "Same-tile replacement structurally requires the incumbent tile to be vacated before successor placement.",
            "limitations": ["RETREAT support is not being enabled or searched in this milestone"],
        },
        {
            "affordance_id": "FORM_01",
            "type": "FORMATION_RELATIONSHIP",
            "description": "Ground and high-ground roles may coexist within the deployment limit when placed on distinct legal tiles.",
            "legal_ground_tiles": stage_facts["deployable_ground_tiles"],
            "legal_high_ground_tiles": stage_facts["deployable_high_ground_tiles"],
            "deployment_limit": stage_facts["deployment_limit"],
        },
    ])
    for affordance_id, evidence in [
        ("OE_01", {"initial_dp": economy["initial_dp"], "dp_per_second": economy["dp_per_second"], "w02_start_frame": 600}),
        ("OE_02", {"route_threats": "exact_route_threats latest_safe_blocker_frame fields"}),
        ("OE_03", {"route_threats": "exact_route_threats latest_safe_blocker_frame fields", "dp_per_second": economy["dp_per_second"]}),
        ("FT_01", {"deployment_limit": stage_facts["deployment_limit"]}),
        ("FT_02", {"deployment_limit": stage_facts["deployment_limit"]}),
        ("FT_03", {"deployment_limit": stage_facts["deployment_limit"], "same_tile_precondition": "geometry"}),
        ("FORM_01", {"stage_facts": {"deployable_ground_tiles": stage_facts["deployable_ground_tiles"], "deployable_high_ground_tiles": stage_facts["deployable_high_ground_tiles"], "deployment_limit": stage_facts["deployment_limit"]}}),
    ]:
        provenance.append({"affordance_id": affordance_id, "source": "deterministic_context.json stage_facts/exact_route_threats", "deterministic_evidence": evidence})
    catalog = {
        "schema_version": "R8_1_DETERMINISTIC_AFFORDANCE_CATALOG_V1",
        "purpose": "Factual realizability options only; no tactical preference is expressed.",
        "mechanics_version": MECHANICS_VERSION,
        "affordances": affordances,
    }
    provenance_doc = {
        "schema_version": "R8_1_AFFORDANCE_PROVENANCE_V1",
        "provenance": provenance,
    }
    return catalog, provenance_doc


def build_selection(originals: list[dict[str, Any]], gap: dict[str, Any], failures: dict[str, Any]) -> dict[str, Any]:
    by_id = {item["hypothesis_id"]: item for item in originals}
    failure_by_id = {item["hypothesis_id"]: item for item in failures["records"]}
    rationale = {
        "HYP-01-DUAL-ANCHOR-SHARED-NET": "Represents shared multi-corridor ranged coverage and explicit two-anchor structure.",
        "HYP-06-PRECONTACT-MAXIMALIST": "Represents damage-forward minimal blocking, a materially different damage/block tradeoff.",
        "HYP-07-W06-FIRST-RESOURCE-SCHEDULING": "Represents endgame-first resource scheduling and deliberate early-leak tolerance.",
        "HYP-09-STAGGERED-HANDOFF-FORMATION": "Represents formation transition and handoff semantics.",
        "HYP-10-LANE01-CONSOLIDATION-LANE02-ATTRITION": "Represents lane consolidation plus distributed lane-02 attrition.",
    }
    selected = []
    for hypothesis_id in SELECTED_HYPOTHESES:
        selected.append({
            "hypothesis_id": hypothesis_id,
            "tactical_thesis": by_id[hypothesis_id]["tactical_thesis"],
            "selection_rationale": rationale[hypothesis_id],
            "previous_best_result": failure_by_id[hypothesis_id]["best_result"],
            "parent_source": "original successful Kimi-K3 tactical output",
        })
    return {
        "schema_version": "R8_1_OPERATIONALIZATION_SELECTION_V1",
        "original_feasible_hypotheses": 9,
        "selected_count": len(selected),
        "diversity_basis": ["coverage topology", "blocking philosophy", "damage allocation", "formation transition", "resource scheduling"],
        "selected": selected,
    }


def output_schema() -> dict[str, Any]:
    properties = {
        "operational_plan_id": {"type": "string"},
        "parent_hypothesis_id": {"type": "string"},
        "tactical_thesis": {"type": "string"},
        "battle_phases": {"type": "array"},
        "phase_responsibilities": {"type": "array"},
        "corridor_responsibilities": {"type": "array"},
        "pressure_window_responsibilities": {"type": "array"},
        "opening_structure": {"type": "object"},
        "stable_structure": {"type": "object"},
        "formation_transitions": {"type": "array"},
        "frontline_structure": {"type": "object"},
        "damage_structure": {"type": "object"},
        "sustain_structure": {"type": "object"},
        "reserve_structure": {"type": "object"},
        "skill_intents": {"type": "array"},
        "temporary_roles": {"type": "array"},
        "handoffs": {"type": "array"},
        "selected_affordances": {"type": "array"},
        "allowed_substitutions": {"type": "array"},
        "forbidden_substitutions": {"type": "array"},
        "invariants": {"type": "array"},
        "assumptions": {"type": "array"},
        "verifier_questions": {"type": "array"},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["operational_plans"],
        "additionalProperties": False,
        "properties": {
            "operational_plans": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "required": PLAN_FIELDS,
                    "additionalProperties": False,
                    "properties": properties,
                },
            }
        },
    }


def build_prompt(selected: dict[str, Any], affordances: dict[str, Any], fidelity: dict[str, Any], gap: dict[str, Any], originals: list[dict[str, Any]]) -> str:
    selected_originals = [item for item in originals if item["hypothesis_id"] in SELECTED_HYPOTHESES]
    compact_audit = {
        "unique_timelines_audited": fidelity["unique_timelines_audited"],
        "classification_counts": fidelity["classification_counts"],
        "common_gap": "The deterministic lowering lacked structured phase responsibilities, explicit affordance choices, allowed/forbidden substitutions, transition semantics, and invariants.",
        "overall_gap": gap["overall_operationalization_gap"],
    }
    evidence = {
        "selected_original_hypotheses": selected_originals,
        "deterministic_affordances": affordances["affordances"],
        "retrospective_audit_summary": compact_audit,
    }
    instructions = """You are Kimi-K3 operating as the tactical operationalization brain.

Operate only on the supplied five original hypotheses. Do NOT create new strategies, reject a parent thesis, choose a global winner, simulate, or revise StageUnderstanding.

For each selected parent hypothesis, produce exactly one OperationalPlan that is concrete enough for deterministic compilation but not an exact FrameTimeline. Use only supplied affordance IDs and entity references. You may choose among alternatives. Preserve each parent's tactical identity.

Use these strict output distinctions:
- OBSERVATION: only a supplied fact.
- INTERPRETATION: a tactical inference from supplied facts.
- TACTICAL_ASSUMPTION: an assumption the deterministic verifier may falsify.

Do not invent exact frames, coordinates, DP values, enemy mechanics, stats, ranges, operator behavior, tiles, or device effects. Do not output unsupported numbers. Exact coordinates may only appear if they are explicitly supplied in the selected hypothesis or affordance and tactically necessary.

For every OperationalPlan specify:
1. semantic battle phases tied to supplied pressure windows,
2. phase responsibilities, including purpose, corridor/window, coexistence, and sharing,
3. corridor and pressure-window responsibilities,
4. opening and stable structures,
5. formation transitions, including whether handoff overlap or same-tile transfer applies,
6. frontline, damage, sustain, reserve, skill intent, and temporary-role semantics,
7. selected affordances with preferred and alternatives where useful,
8. allowed substitutions,
9. forbidden substitutions that would destroy the tactical thesis,
10. operational invariants,
11. assumptions,
12. verifier questions.

Return only a JSON object matching the supplied response schema. There must be exactly five operational plans, in the supplied parent order. No markdown, commentary, or extra keys.

DETERMINISTIC_EVIDENCE_JSON:
"""
    return instructions + json.dumps(evidence, ensure_ascii=False, indent=2)


def validate_and_derive(raw_path: Path, schema_path: Path, originals: list[dict[str, Any]], context: dict[str, Any], affordances: dict[str, Any]) -> dict[str, Any]:
    raw_text = raw_path.read_text()
    parsed = json.loads(raw_text)
    schema = load(schema_path)
    errors = validate_schema(parsed, schema)
    plans = parsed.get("operational_plans", [])
    known_ids = {item["hypothesis_id"] for item in originals}
    known_clusters = {item["cluster_id"] for item in context["route_pressure_clusters"]["clusters"]}
    known_windows = {item["window_id"] for item in context["pressure_windows"]["windows"]}
    known_routes = {route for cluster in context["route_pressure_clusters"]["clusters"] for route in cluster["member_route_ids"]}
    known_tiles = {tuple(tile) for tile in context["stage_facts"]["deployable_ground_tiles"] + context["stage_facts"]["deployable_high_ground_tiles"]}
    known_device_ids = {item["device_id"] for item in context["stage_devices"]}
    known_affordances = {item["affordance_id"] for item in affordances["affordances"]}
    entity_errors: list[dict[str, str]] = []
    numeric_hallucinations: list[dict[str, Any]] = []
    evidence_text = json.dumps(originals, ensure_ascii=False) + json.dumps(context, ensure_ascii=False) + json.dumps(affordances, ensure_ascii=False)
    grounded_numeric_literals = set(re.findall(r"(?<![A-Za-z_])\d+(?:\.\d+)?(?![A-Za-z_])", evidence_text))

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
        elif isinstance(value, str):
            if re.search(r"\bHYP-[0-9]{2}-", value):
                for match in re.findall(r"HYP-[0-9]{2}-[A-Z0-9-]+", value):
                    if match not in known_ids:
                        entity_errors.append({"json_path": f"{path}:{match}", "value": match, "reason": "UNKNOWN_HYPOTHESIS"})
            for match in re.findall(r"\bC0[1-7]\b", value):
                if match not in known_clusters:
                    entity_errors.append({"json_path": f"{path}:{match}", "value": match, "reason": "UNKNOWN_CORRIDOR"})
            for match in re.findall(r"\bW0[1-6]\b", value):
                if match not in known_windows:
                    entity_errors.append({"json_path": f"{path}:{match}", "value": match, "reason": "UNKNOWN_PRESSURE_WINDOW"})
            for match in re.findall(r"\broute-\d+\b", value):
                if match not in known_routes:
                    entity_errors.append({"json_path": f"{path}:{match}", "value": match, "reason": "UNKNOWN_ROUTE"})
            for match in re.findall(r"\[(\d+),(\d+)\]", value):
                if tuple(map(int, match)) not in known_tiles:
                    entity_errors.append({"json_path": f"{path}:{match}", "value": match, "reason": "UNKNOWN_TILE"})
            for match in re.findall(r"trap_\d+_roadblock#\d+", value):
                if match not in known_device_ids:
                    entity_errors.append({"json_path": f"{path}:{match}", "value": match, "reason": "UNKNOWN_DEVICE"})
            for match in re.findall(r"\b(?:IR|SC|OE|FT|FORM)_[0-9]{2}\b", value):
                if match not in known_affordances:
                    entity_errors.append({"json_path": f"{path}:{match}", "value": match, "reason": "UNKNOWN_AFFORDANCE"})
            value_without_entity_ids = re.sub(
                r"\b(?:C|W|IR|SC|OE|FT|FORM)_[0-9]{2}\b|\broute-[0-9]+\b",
                " ",
                value,
            )
            for number in re.findall(r"(?<![A-Za-z_])\d+(?:\.\d+)?(?![A-Za-z_])", value_without_entity_ids):
                if number not in grounded_numeric_literals:
                    numeric_hallucinations.append({"json_path": path, "value": number, "reason": "NUMERIC_HALLUCINATION"})

    walk(parsed, "$")
    specificity: list[dict[str, Any]] = []
    compilability: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []
    drift: list[dict[str, Any]] = []
    parent_ids = [plan.get("parent_hypothesis_id") for plan in plans]
    for plan in plans:
        hypothesis_id = plan.get("parent_hypothesis_id")
        missing_fields = [field for field in PLAN_FIELDS if field not in plan]
        empty_important = [
            field for field in [
                "battle_phases", "phase_responsibilities", "corridor_responsibilities",
                "pressure_window_responsibilities", "selected_affordances",
                "allowed_substitutions", "forbidden_substitutions", "invariants", "verifier_questions",
            ] if not plan.get(field)
        ]
        sufficient = not missing_fields and not empty_important
        specificity.append({
            "operational_plan_id": plan.get("operational_plan_id"),
            "parent_hypothesis_id": hypothesis_id,
            "missing_required_fields": missing_fields,
            "empty_important_fields": empty_important,
            "result": "OPERATIONALIZATION_SUFFICIENT" if sufficient else "OPERATIONALIZATION_INSUFFICIENT",
        })
        selected_ids = [
            item.get("affordance_id") for item in plan.get("selected_affordances", [])
            if isinstance(item, dict) and item.get("affordance_id")
        ]
        plan_index = plans.index(plan)
        plan_entity_errors = [item for item in entity_errors if item["json_path"].startswith(f"$['operational_plans'][{plan_index}]")]
        plan_numeric_errors = [item for item in numeric_hallucinations if item["json_path"].startswith(f"$['operational_plans'][{plan_index}]")]
        plan_text = json.dumps(plan, ensure_ascii=False).lower()
        retreat_condition = any(
            keyword in plan_text
            for keyword in ["retreat", "exits after", "vacate", "same-tile replacement"]
        )
        compilable = sufficient and not plan_entity_errors and not plan_numeric_errors
        if not compilable:
            status = "GROUNDING_BLOCKED" if plan_entity_errors or plan_numeric_errors else "OPERATIONALIZATION_INSUFFICIENT"
        elif retreat_condition:
            status = "COMPILABLE_WITH_CONDITIONS"
        else:
            status = "COMPILABLE"
        compilability.append({
            "operational_plan_id": plan.get("operational_plan_id"),
            "parent_hypothesis_id": hypothesis_id,
            "status": status,
            "selected_affordance_ids": selected_ids,
            "rejected_if": [
                "required affordance is absent",
                "critical coexistence is absent",
                "transition tile-transfer semantics are absent when required",
                "unknown entity or decision-critical numeric claim appears",
            ],
        })
        contracts.append({
            "operational_plan_id": plan.get("operational_plan_id"),
            "parent_hypothesis_id": hypothesis_id,
            "tactical_invariants": plan.get("invariants", []),
            "allowed_enumeration_dimensions": [
                "operator_capability_roster",
                "affordance_members",
                "deployment_order_within_phase",
                "skill_timing_within_stated_intent",
            ],
            "semantic_choices_fixed_by_kimi": {
                "corridor_responsibilities": plan.get("corridor_responsibilities", []),
                "pressure_window_responsibilities": plan.get("pressure_window_responsibilities", []),
                "selected_affordances": plan.get("selected_affordances", []),
                "forbidden_substitutions": plan.get("forbidden_substitutions", []),
            },
            "deterministic_facts_to_calculate": [
                "exact operator selection",
                "exact legal tile member",
                "exact facing",
                "exact deployment deadline",
                "exact skill timing",
                "coexistence feasibility",
            ],
            "rejection_conditions": plan.get("forbidden_substitutions", []) + plan.get("invariants", []),
        })
        drift.append({
            "operational_plan_id": plan.get("operational_plan_id"),
            "parent_hypothesis_id": hypothesis_id,
            "parent_exists": hypothesis_id in known_ids,
            "unique_parent_order": parent_ids.count(hypothesis_id) == 1,
            "strategic_drift": hypothesis_id not in known_ids,
            "reason": "Parent must exist in original hypothesis set and each plan maps one-to-one.",
        })
    validation = {
        "schema_version": "R8_1_OPERATIONAL_PLAN_VALIDATION_V1",
        "schema_errors": errors,
        "operational_specificity": specificity,
        "compilability": compilability,
        "compiler_contracts": contracts,
        "strategic_drift": drift,
        "entity_grounding": {
            "unknown_entity_references": len(entity_errors),
            "errors": entity_errors,
        },
        "numeric_grounding": {
            "ungrounded_numeric_values": len(numeric_hallucinations),
            "numeric_hallucinations": numeric_hallucinations,
            "policy": "Deterministic removal from executable semantics will be recorded separately; no silent correction.",
        },
    }
    return {"parsed": parsed, "validation": validation}


def validate_schema(value: Any, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    def check(node: Any, spec: dict[str, Any], path: str) -> None:
        expected = spec.get("type")
        if expected == "object" and not isinstance(node, dict):
            errors.append(f"{path}: expected object")
            return
        if expected == "array" and not isinstance(node, list):
            errors.append(f"{path}: expected array")
            return
        if expected == "string" and not isinstance(node, str):
            errors.append(f"{path}: expected string")
            return
        if isinstance(node, dict) and expected == "object":
            for key in spec.get("required", []):
                if key not in node:
                    errors.append(f"{path}.{key}: missing")
            if spec.get("additionalProperties") is False:
                for key in node:
                    if key not in spec.get("properties", {}):
                        errors.append(f"{path}.{key}: additional property")
            for key, child in node.items():
                if key in spec.get("properties", {}):
                    check(child, spec["properties"][key], f"{path}.{key}")
        elif isinstance(node, list) and expected == "array":
            if "minItems" in spec and len(node) < spec["minItems"]:
                errors.append(f"{path}: fewer than {spec['minItems']} items")
            if "maxItems" in spec and len(node) > spec["maxItems"]:
                errors.append(f"{path}: more than {spec['maxItems']} items")
            if "items" in spec:
                for index, child in enumerate(node):
                    check(child, spec["items"], f"{path}[{index}]")
    check(value, schema, "$")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--call", action="store_true", help="Execute the single approved Kimi-K3 operationalization call")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    originals = load(SOURCE_DIR / "llm_plan_hypotheses.json")["plan_hypotheses"]
    funnel = load(SEARCH_DIR / "search_funnel.json")
    failures = load(SEARCH_DIR / "failure_evidence_by_hypothesis.json")
    context = load(CONTEXT_DIR / "deterministic_context.json")
    profile = provider_profile()
    if not profile["credential_present"]:
        raise SystemExit("ARK_API_KEY_agent_MISSING")
    signatures = build_semantic_signatures(originals)
    fidelity = build_timeline_fidelity(originals, funnel)
    gap = build_gap_analysis(originals)
    collisions = build_collisions(fidelity, funnel, context)
    affordances, provenance = build_affordances(context)
    selection = build_selection(originals, gap, failures)
    write("effective_llm_profile.json", profile)
    write("hypothesis_semantic_signatures.json", signatures)
    write("existing_240_timeline_fidelity_audit.json", fidelity)
    write("operationalization_gap_analysis.json", gap)
    write("cross_hypothesis_realization_collisions.json", collisions)
    write("deterministic_affordance_catalog.json", affordances)
    write("affordance_provenance.json", provenance)
    write("hypothesis_selection_for_operationalization.json", selection)
    schema = output_schema()
    schema_path = OUT / "operationalization_output_schema.json"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")
    prompt = build_prompt(selection, affordances, fidelity, gap, originals)
    prompt_path = OUT / "operationalization_prompt.txt"
    prompt_path.write_text(prompt)
    request = {
        "milestone": "R8_1_LLM_OPERATIONALIZATION_V1",
        "invocation": "codex exec --profile agent --skip-git-repo-check --sandbox read-only --ephemeral --output-schema operationalization_output_schema.json --output-last-message operationalization_llm_raw_response.txt -",
        "profile": "agent",
        "provider": "volcengine-agent-plan",
        "model": "kimi-k3",
        "wire_api": "responses",
        "credential_env": "ARK_API_KEY_agent",
        "call_purpose": "operationalize selected existing hypotheses",
        "call_count_authorized": 1,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "prompt_bytes": len(prompt.encode()),
        "schema_sha256": sha256_json(schema),
        "selected_hypothesis_ids": SELECTED_HYPOTHESES,
    }
    write("operationalization_llm_request.json", request)
    if not args.call:
        return
    raw_path = OUT / "operationalization_llm_raw_response.txt"
    console_path = OUT / "operationalization_llm_console.log"
    command = [
        "codex", "exec", "--profile", "agent", "--skip-git-repo-check", "--sandbox", "read-only",
        "--ephemeral", "--output-schema", str(schema_path), "--output-last-message", str(raw_path), "-",
    ]
    with prompt_path.open("rb") as stdin_file, console_path.open("w") as console_file:
        completed = subprocess.run(command, stdin=stdin_file, stdout=console_file, stderr=subprocess.STDOUT, env={**__import__("os").environ})
    if completed.returncode != 0 or not raw_path.exists() or not raw_path.read_text().strip():
        write("llm_call_summary.json", {
            "call_count": 1, "result": "PROVIDER_API_FAILURE", "returncode": completed.returncode,
            "console_log": console_path.name,
        })
        raise SystemExit(completed.returncode or 1)
    result = validate_and_derive(raw_path, schema_path, originals, context, affordances)
    write("operationalization_llm_structured_output.json", result["parsed"])
    plans = result["parsed"]["operational_plans"]
    write("operational_plans.json", {"operational_plans": plans})
    write("operationalization_validation.json", result["validation"])
    write("operational_plan_grounding_validation.json", result["validation"]["entity_grounding"])
    write("operational_specificity_validation.json", {"records": result["validation"]["operational_specificity"]})
    write("strategic_drift_audit.json", {"records": result["validation"]["strategic_drift"]})
    write("operational_plan_compilability.json", {"records": result["validation"]["compilability"]})
    write("operational_plan_compiler_contracts.json", {"contracts": result["validation"]["compiler_contracts"]})
    write("llm_call_summary.json", {
        "call_count": 1,
        "profile": "agent",
        "provider": "volcengine-agent-plan",
        "model": "kimi-k3",
        "result": "SUCCESS",
        "raw_response_file": "operationalization_llm_raw_response.txt",
        "prompt_sha256": request["prompt_sha256"],
        "raw_response_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
    })


def raw_text(path: Path) -> str:
    return path.read_text()


if __name__ == "__main__":
    main()
