import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SEVEN = ROOT / "docs/review/fc77177/real_tool_closed_loop_astra_high_seven_recursive_v1"
M70 = ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence"
CASES = {
    "m70": {
        "label": "M70 R8_7_GPT_M70_V1",
        "plan": M70 / "attempts/attempt_01_diagnostic/plan_snapshot.json",
        "actions": M70 / "attempts/attempt_01_diagnostic/action_snapshot.json",
        "events": M70 / "attempts/attempt_01_diagnostic/diagnostic_events.json.gz",
        "final": M70 / "attempts/attempt_01_diagnostic/final_status.json",
    },
    "seven": {
        "label": "seven_recursive candidate-001",
        "plan": SEVEN / "session/candidates/candidate-001/simulation/plan_snapshot.json",
        "actions": SEVEN / "session/candidates/candidate-001/simulation/action_snapshot.json",
        "events": SEVEN / "session/candidates/candidate-001/simulation/diagnostic_events.json.gz",
        "final": SEVEN / "session/candidates/candidate-001/simulation/final_status.json",
    },
}
OPERATORS = {
    "char_123_fang": "芬",
    "char_4093_frston": "Friston-3",
    "char_283_midn": "月见夜",
    "char_284_spot": "斑点",
    "char_212_ansel": "安赛尔",
    "char_120_hibisc": "芙蓉",
    "char_210_stward": "史都华德",
    "char_208_melan": "玫兰莎",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_case(key):
    case = CASES[key]
    events = json.loads(gzip.open(case["events"], "rt").read())["events"]
    return {
        "label": case["label"],
        "plan_path": str(case["plan"].relative_to(ROOT)),
        "action_path": str(case["actions"].relative_to(ROOT)),
        "events_path": str(case["events"].relative_to(ROOT)),
        "final_path": str(case["final"].relative_to(ROOT)),
        "plan_sha256": sha256(case["plan"]),
        "action_sha256": sha256(case["actions"]),
        "events_sha256": sha256(case["events"]),
        "final_sha256": sha256(case["final"]),
        "plan": json.loads(case["plan"].read_text()),
        "actions": json.loads(case["actions"].read_text())["actions"],
        "final": json.loads(case["final"].read_text()),
        "events": events,
        "event_count": len(events),
        "event_type_counts": dict(sorted(Counter(e["event_type"] for e in events).items())),
    }


def pair_stats(events, event_type, source=None, target=None):
    groups = defaultdict(list)
    for event in events:
        if event["event_type"] != event_type:
            continue
        if source is not None and event.get("source_id") != source:
            continue
        if target is not None and event.get("target_id") != target:
            continue
        groups[(event.get("source_id"), event.get("target_id"))].append(
            {"frame": event["frame"], "amount": event.get("details", {}).get("amount", 0)}
        )
    result = []
    for pair, values in sorted(groups.items(), key=lambda item: sum(v["amount"] for v in item[1]), reverse=True):
        result.append(
            {
                "source_id": pair[0],
                "target_id": pair[1],
                "count": len(values),
                "total": round(sum(v["amount"] for v in values), 2),
                "first_frame": values[0]["frame"],
                "last_frame": values[-1]["frame"],
            }
        )
    return result


def targeted(events, entity_id, event_types):
    output = []
    for event in events:
        if entity_id not in (event.get("source_id"), event.get("target_id")):
            continue
        if event["event_type"] not in event_types:
            continue
        output.append(
            {
                "frame": event["frame"],
                "event_type": event["event_type"],
                "source_id": event.get("source_id"),
                "target_id": event.get("target_id"),
                "details": event.get("details", {}),
            }
        )
    return output


def entity_summary(events, entity_id):
    matching = [e for e in events if entity_id in (e.get("source_id"), e.get("target_id"))]
    damage_taken = [
        e for e in matching if e.get("target_id") == entity_id and e["event_type"] in ("DAMAGE", "ENEMY_ABILITY_HIT", "DEVICE_DAMAGE")
    ]
    return {
        "event_count": len(matching),
        "damage_taken_total": round(sum(e.get("details", {}).get("amount", 0) for e in damage_taken), 2),
        "block_events": [e["frame"] for e in matching if e["event_type"] == "BLOCK"],
        "unblock_events": [e["frame"] for e in matching if e["event_type"] == "UNBLOCK"],
        "death_or_leak": [
            {"frame": e["frame"], "event_type": e["event_type"], "source_id": e.get("source_id"), "details": e.get("details", {})}
            for e in matching
            if e["event_type"] in ("ENEMY_DEATH", "ENEMY_LEAK", "PROTECTED_TARGET_REACHED")
        ],
    }


def operator_contributions(events):
    result = {}
    for operator_id in sorted({e.get("source_id") for e in events if e["event_type"] == "DEPLOY"}):
        deployments = [e for e in events if e["event_type"] == "DEPLOY" and e.get("source_id") == operator_id]
        deaths = [e["frame"] for e in events if e["event_type"] == "OPERATOR_DEATH" and e.get("source_id") == operator_id]
        retreats = [e["frame"] for e in events if e["event_type"] == "RETREAT" and e.get("source_id") == operator_id]
        damage_taken = sum(
            e.get("details", {}).get("amount", 0)
            for e in events
            if e.get("target_id") == operator_id and e["event_type"] in ("DAMAGE", "ENEMY_ABILITY_HIT")
        )
        result[operator_id] = {
            "name": OPERATORS.get(operator_id),
            "deploy_events": [{"frame": e["frame"], "event_tile_row_col": e["details"].get("tile"), "cost": e["details"].get("cost")} for e in deployments],
            "deaths": deaths,
            "retreats": retreats,
            "damage_dealt": round(sum(e.get("details", {}).get("amount", 0) for e in events if e["event_type"] == "DAMAGE" and e.get("source_id") == operator_id), 2),
            "damage_taken": round(damage_taken, 2),
            "healing_done": round(sum(e.get("details", {}).get("amount", 0) for e in events if e["event_type"] == "HEAL" and e.get("source_id") == operator_id), 2),
            "device_damage_done": round(sum(e.get("details", {}).get("amount", 0) for e in events if e["event_type"] == "DEVICE_DAMAGE" and e.get("source_id") == operator_id), 2),
            "unique_blocked_targets": sorted({e.get("target_id") for e in events if e["event_type"] == "BLOCK" and e.get("source_id") == operator_id}),
        }
    return result


def case_facts(data):
    events = data["events"]
    roadblocks = targeted(events, "trap_020_roadblock", ())
    roadblocks = [e for e in roadblocks if str(e.get("target_id", "")).startswith("trap_020_roadblock#")]
    protected_ids = sorted({e.get("target_id") for e in events if str(e.get("target_id", "")).startswith("enemy_3001_upeopl#")})
    artillery = {
        "ability_starts": [
            {"frame": e["frame"], "details": e["details"]}
            for e in events
            if e["event_type"] == "ENEMY_ABILITY_START" and "enemy_1112_emppnt#0" in str(e.get("source_id"))
        ],
        "ability_hits": pair_stats(events, "ENEMY_ABILITY_HIT"),
        "steward_damage": pair_stats(events, "DAMAGE", source="char_210_stward", target="enemy_1112_emppnt#0")[0],
        "death_or_leak": entity_summary(events, "enemy_1112_emppnt#0")["death_or_leak"],
    }
    return {
        "label": data["label"],
        "plan_path": data["plan_path"],
        "action_path": data["action_path"],
        "events_path": data["events_path"],
        "final_path": data["final_path"],
        "plan_sha256": data["plan_sha256"],
        "action_sha256": data["action_sha256"],
        "events_sha256": data["events_sha256"],
        "final_sha256": data["final_sha256"],
        "plan_id": data["plan"]["operational_plan_id"],
        "roster": [{"operator_id": operator_id, "name": OPERATORS.get(operator_id)} for operator_id in data["plan"]["selected_low_star_operator_ids"]],
        "action_count": len(data["actions"]),
        "final_status": data["final"],
        "event_count": data["event_count"],
        "event_type_counts": data["event_type_counts"],
        "action_timeline": data["actions"],
        "roadblock_events": roadblocks,
        "protected": {entity_id: entity_summary(events, entity_id) for entity_id in protected_ids},
        "protected_event_trace": {
            entity_id: targeted(events, entity_id, ("SPAWN", "BLOCK", "UNBLOCK", "DAMAGE", "ENEMY_ABILITY_HIT", "ENEMY_DEATH", "ENEMY_LEAK", "PROTECTED_TARGET_REACHED"))
            for entity_id in protected_ids
        },
        "central": {
            entity_id: entity_summary(events, entity_id)
            for entity_id in ("enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#34")
        },
        "central_event_traces": {
            entity_id: targeted(events, entity_id, ("SPAWN", "BLOCK", "UNBLOCK", "DAMAGE", "ENEMY_DEATH", "ENEMY_LEAK"))
            for entity_id in ("enemy_1110_uamord#21", "enemy_1110_uamord#22", "enemy_1110_uamord#34")
        },
        "artillery": artillery,
        "operator_contributions": operator_contributions(events),
    }


def evidence_entry(evidence_id, path, evidence_type, classification, note):
    absolute = ROOT / path
    return {
        "evidence_id": evidence_id,
        "path": path,
        "sha256": sha256(absolute),
        "type": evidence_type,
        "classification": classification,
        "note": note,
    }


def main():
    loaded = {key: load_case(key) for key in CASES}
    facts = {key: case_facts(data) for key, data in loaded.items()}
    seven_path = SEVEN.relative_to(ROOT)
    final_message = (SEVEN / "session/codex_cli/attempt_01/codex_final_message.txt").read_text()
    tool_calls = []
    for line in (SEVEN / "session/codex_cli/attempt_01/codex_exec.jsonl").read_text().splitlines():
        item = json.loads(line)
        frame = item.get("item", {})
        if item.get("type") == "item.completed" and frame.get("type") == "mcp_tool_call":
            tool_calls.append({"tool": frame["tool"], "status": frame.get("status"), "arguments": frame.get("arguments", {})})
    evidence_index = [
        evidence_entry("M70_PLAN", facts["m70"]["plan_path"], "frozen_plan", "ORIGINAL", "M70 frozen plan."),
        evidence_entry("M70_ACTIONS", facts["m70"]["action_path"], "frozen_actions", "ORIGINAL", "M70 frozen actions."),
        evidence_entry("M70_EVENTS", facts["m70"]["events_path"], "gzip_events", "ORIGINAL_EVENTS", "69,239 settled events."),
        evidence_entry("M70_FINAL", facts["m70"]["final_path"], "final_status", "ORIGINAL", "M70 simulator WIN."),
        evidence_entry("S7_PLAN", facts["seven"]["plan_path"], "frozen_plan", "ORIGINAL", "Seven-recursive frozen plan."),
        evidence_entry("S7_ACTIONS", facts["seven"]["action_path"], "frozen_actions", "ORIGINAL", "Seven-recursive frozen actions."),
        evidence_entry("S7_EVENTS", facts["seven"]["events_path"], "gzip_events", "ORIGINAL_EVENTS", "39,584 settled events."),
        evidence_entry("S7_FINAL", facts["seven"]["final_path"], "final_status", "ORIGINAL", "Seven-recursive simulator LOSS."),
        evidence_entry("S7_CLOSEOUT", str(SEVEN / "closeout_report_v1.json"), "closeout", "DERIVED_BUT_HASHED", "Prior closeout; healer-heal wording corrected in this comparison."),
        evidence_entry("S7_MANIFEST", str(SEVEN / "attempt_artifact_manifest_v1.json"), "manifest", "ORIGINAL", "Artifact manifest."),
        evidence_entry("S7_FINAL_MESSAGE", str(SEVEN / "session/codex_cli/attempt_01/codex_final_message.txt"), "model_final_message", "ORIGINAL", "Explicit model stop rationale."),
        evidence_entry("S7_JSONL", str(SEVEN / "session/codex_cli/attempt_01/codex_exec.jsonl"), "cli_jsonl", "ORIGINAL", "Tool trajectory and usage."),
        evidence_entry("SUGGESTION_V1", str(SEVEN / "next_prompt_suggestion_v1.md"), "prior_prompt", "DERIVED", "Generic prompt superseded by v2."),
        evidence_entry("SUGGESTION_V2", str(SEVEN / "next_prompt_suggestion_v2.md"), "next_prompt", "DERIVED", "Read-only suggestion; not an execution authorization."),
    ]
    output = {
        "schema_version": "KIMIARK_SEVEN_VS_M70_ZERO_MODEL_COMPARISON_V1",
        "scope": "Current fixed simulator only",
        "boundaries": {
            "real_model_calls": 0,
            "real_simulations": 0,
            "new_started": 0,
            "best_verified_operator_count": 8,
            "seven_or_fewer_feasibility": "UNKNOWN",
            "coordinate_note": "plan/action tiles are [row,col]; DEPLOY event detail tile strings are [x,y] after json_tile_to_runtime conversion.",
            "causal_note": "Event adjacency and dependency chains are observations; counterfactual necessity remains UNKNOWN.",
        },
        "cases": facts,
        "comparison": {
            "earliest_action_and_geometry": {
                "classification": "OBSERVED; CAUSAL_ROLE_HYPOTHESIS",
                "m70": "Melantha deploys at action [6,5]/event [5,6] at 841, retreats at 2054, and is the first artillery lock target; Steward deploys at event [7,5] at 2071.",
                "seven": "Melantha is absent; Spot deploys at event [5,6] at 901, Ansel remains at event [5,5], and Steward deploys at event [6,5] at 2101.",
                "first_lock": {"m70": "[5,6]@1893", "seven": "[5,5]@1861"},
            },
            "artillery_chain": {
                "classification": "OBSERVED",
                "m70": "16 ability starts; first two lock [5,6], later locks include [7,5] and [6,2]; Steward kills artillery@4273.",
                "seven": "20 ability starts; first two lock [5,5], later locks include [6,5], [6,2], [5,3] and protected routes; artillery leaks@5759.",
                "hibiscus": {
                    "m70": "6 artillery hits@2893,3043,3193,3343,3493,4243; no operator death.",
                    "seven": "2 artillery hits@3011,3161; operator death@3161. Between the two hits, Ansel heals her 362@3015 and she self-heals 558.9@3013. Exact pre-hit HP is not in the event log.",
                },
            },
            "protected_path": {
                "classification": "OBSERVED",
                "m70": "Roadblock #4 destroyed@1966, #3@2404, #2@10787, #1@11017; #14 and #3 reach@11119/11349.",
                "seven": "Only #3 destroyed@2404; #4/#2/#1 have no DEVICE_DAMAGE; #14 is blocked by #4@3251 and dies@3966; #3 is blocked by #1@2773 and dies@5353.",
                "trap_target_distinction": "trap_020_roadblock#3 and enemy_3001_upeopl#3 are different entities.",
            },
            "steward_output": {
                "classification": "OBSERVED",
                "m70": "45 hits, 13,227.21 damage, first@2161, last@4273, kill@4273; 36 normal + 9 boosted hits.",
                "seven": "39 hits, 11,284.23 damage, first@2101, last@4753, leak@5759; 32 normal + 7 boosted hits. Gaps include 2917-3361 and 4225-4705.",
                "caution": "The difference is not a valid universal claim that six more hits alone would WIN; artillery HP,反击, healing, DP, blocking and protected targets are not resolved by that arithmetic.",
            },
            "central_chain": {
                "classification": "OBSERVED",
                "m70": "#21 blocked@4646 and killed@5154 by Melantha; #22 blocked@4796 and killed@6429; #34 blocked@6596 and killed@7197.",
                "seven": "#21 blocked@4646, unblocked@4753 when Fang dies, leaks@5152; #22 never blocks and leaks@5196 after 283.85 damage; #34 never blocks and leaks@6996 after 1,021.19 damage.",
                "kill_cause_boundary": "Fang's death@4753 coincides with artillery damage@4753 and #21 arts damage@4752; the event log does not provide HP history, so exact kill attribution is UNKNOWN.",
            },
            "difference_chains": [
                {
                    "chain": "early-upper-clearance",
                    "known_success_condition": "M70 roadblock #4 is damaged from 841 and destroyed@1966.",
                    "observed_change": "S7 removes Melantha and deploys Spot@901; roadblock #4 has no DEVICE_DAMAGE.",
                    "first_break": "#4 remains intact; protected #14 is blocked@3251 and dies@3966.",
                    "downstream": "#14 cannot reach; artillery and central duties remain open.",
                    "unknown": "Whether Melantha is necessary or an alternative seventh-role/timing can clear #4 without losing another duty.",
                },
                {
                    "chain": "support-geometry-healer-survival",
                    "known_success_condition": "M70 locks [5,6]/[7,5] expose Melantha and Steward, while Ansel and Hibiscus survive the barrage.",
                    "observed_change": "S7 first locks [5,5]/[6,5], hitting Ansel, Friston, Spot and Steward earlier; Hibiscus receives two [6,2] shells and dies@3161.",
                    "first_break": "S7's [6,2] shell cadence occurs without the M70 pre-hit heal cadence that preceded its second Hibiscus shell.",
                    "downstream": "Lower healing/arts support weakens Steward's artillery window and later central support.",
                    "unknown": "Exact HP margins and whether a position/timing change or different healer allocation would preserve all duties.",
                },
                {
                    "chain": "central-live-block-and-kill",
                    "known_success_condition": "M70 keeps Fang/Friston alive, blocks all three armor enemies, and kills #21/#22/#34.",
                    "observed_change": "S7 Fang dies@4753 and Friston-3 dies@4768; #21 unblocks and leaks.",
                    "first_break": "OPERATOR_DEATH Fang@4753 followed by #21 UNBLOCK@4753.",
                    "downstream": "#22/#34 have no block; #33 also leaks@6846.",
                    "unknown": "Whether the failure is primarily healer survival, geometry, output, or a coupled timing problem.",
                },
            ],
            "contributions_and_costs": {
                "classification": "OBSERVED_PLUS_COST; REPLACEABILITY_UNKNOWN",
                "seven_unique_deployment_cost": 98,
                "m70_unique_deployment_cost": 113,
                "note": "S7 omits Melantha (15 initial DP in M70) but also loses her device/output work and changes geometry. Low per-role output does not prove low contribution; healing/damage totals do not prove irreplaceability.",
            },
            "model_stop": {
                "classification": "OBSERVED_FINAL_MESSAGE; INTERNAL_REASONING_UNAVAILABLE",
                "tool_calls": tool_calls,
                "final_message": final_message,
                "assessment": "The explicit stated reason was no sufficiently justified combined repair; this is a decision report, not proof that no repair exists. Token totals do not establish context overflow or inefficiency.",
            },
            "prior_prompt_evaluation": {
                "classification": "OBSERVED",
                "finding": "next_prompt_suggestion_v1 correctly preserves the budget, four-tool boundary, and no-second-simulation rule, but it names only the healer-survival symptom and not roadblock #4's absent clearance, the first-lock geometry change, or the #21 unblock chain. It is therefore too generic to select a falsifiable C1 and is superseded by v2.",
            },
        },
        "evidence_index": evidence_index,
    }
    (SEVEN / "zero_model_comparison_v1.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    (SEVEN / "zero_model_evidence_index_v1.json").write_text(json.dumps({"schema_version": "KIMIARK_ZERO_MODEL_EVIDENCE_INDEX_V1", "evidence": evidence_index}, ensure_ascii=False, indent=2) + "\n")
    report = f"""# Seven-recursive vs M70 zero-model comparison\n\n**Scope:** current fixed simulator only. **Counts:** model calls 0, simulations 0, STARTED 0. M70 remains the 8-ID WIN; seven-or-fewer feasibility is UNKNOWN.\n\n## Baseline\n\n| Case | Result | Kills / leaks / deaths / life | Protected targets |\n|---|---|---|---|\n| M70 | WIN | 33 / 0 / 0 / 3 | #14@11119, #3@11349 |\n| Seven-recursive C1 | LOSS | 24 / 9 / 3 / -8 | #14 dies@3966; #3 dies@5353 |\n\nCoordinates below follow the DEPLOY event convention `[row,col]`; action snapshot tiles are `[x,y]`.\n\n## Earliest structural and geometry changes\n\n- **OBSERVED:** M70 deploys Melantha@841 at event [5,6], retreats@2054, then Steward@2071 at [7,5]. C1 removes Melantha, deploys Spot@901 at [5,6], keeps Ansel at [5,5], and deploys Steward@2101 at [6,5].\n- **OBSERVED:** first artillery lock changes from M70 `[5,6]@1893` to C1 `[5,5]@1861`.\n- **CAUSAL_ROLE_HYPOTHESIS:** these changes plausibly redirect exposure and remove roadblock work, but necessity of any specific role is not proven.\n\n## Artillery and healer chain\n\n- **OBSERVED:** M70 has 16 shells and Steward kills artillery@4273 after 45 hits / 13,227.21 damage.\n- **OBSERVED:** C1 has 20 shells; Steward deals 39 hits / 11,284.23, with visible output gaps 2917-3361 and 4225-4705; artillery leaks@5759.\n- **OBSERVED:** C1 Hibiscus takes 890@3011 and 890@3161, then dies@3161. Between hits she self-heals 558.9@3013 and receives Ansel 362@3015; exact HP is not recorded. This corrects the prior closeout's wording that only 558.9 healing occurred between the hits.\n- **UNKNOWN:** whether an altered healer schedule, position, skill timing, or another structure would preserve this support role.\n\n## Protected passage\n\n- **OBSERVED:** M70 destroys #4@1966, #3@2404, #2@10787, #1@11017; both protected targets reach.\n- **OBSERVED:** C1 destroys only #3@2404. It does no `DEVICE_DAMAGE` to #4/#2/#1. Protected #14 is restrained by #4@3251 and dies@3966; protected #3 is restrained by #1@2773 and dies@5353.\n- **OBSERVED:** `trap_020_roadblock#3` and `enemy_3001_upeopl#3` are distinct.\n\n## Steward output arithmetic\n\n- **OBSERVED:** M70 45 hits (36 normal + 9 boosted); C1 39 hits (32 normal + 7 boosted).\n- **CAUTION:** the 6-hit/1,942.98-damage difference does not establish that six more hits alone would WIN. It does not resolve remaining HP, reverse damage, healing, DP, blocking, or protected-passage dependencies.\n\n## Central chain\n\n| Enemy | M70 | C1 |\n|---|---|---|\n| #21 | blocked@4646, killed@5154 by Melantha | blocked@4646, unblocked@4753 when Fang dies, leaks@5152 |\n| #22 | blocked@4796, killed@6429 | no BLOCK, 283.85 damage, leaks@5196 |\n| #34 | blocked@6596, killed@7197 | no BLOCK, 1,021.19 damage, leaks@6996 |\n\n- **OBSERVED:** Fang dies@4753; artillery hits Fang@4753 and #21 hits Fang@4752. Friston-3 dies@4768 after #22 arts damage. HP history is absent, so exact killer attribution is UNKNOWN.\n- **OBSERVED:** #33 also leaks@6846 in C1.\n\n## Difference chains\n\n1. **Early-upper-clearance:** M70 #4 damaged 841-1966 and destroyed; C1 has no #4 damage, so #14 is restrained@3251 and dies@3966. Melantha necessity is HYPOTHESIS.\n2. **Support geometry/healer survival:** M70 locks [5,6]/[7,5]; C1 locks [5,5]/[6,5], exposing Ansel/Friston/Spot/Steward earlier. C1's Hibiscus shell cadence lacks the M70 pre-hit healing cadence. Exact repair is UNKNOWN.\n3. **Central live block/kill:** M70 blocks and kills #21/#22/#34; C1's blocker deaths release #21 and leave #22/#34 unblocked. Whether this is primarily support, geometry, output or timing is UNKNOWN.\n\n## Contributions and replacement costs\n\n- **OBSERVED/COST:** C1 unique opening cost is 98; M70's unique deployment cost is 113. The omitted Melantha used 15 initial DP, damaged roadblock #4 (8,358.56) and later roadblock #2 (8,358.56), while also dealing central and runner damage.\n- **OBSERVED:** C1 contributions include Spot's upper closure, Midnight's #3 clearance, Fang/Friston early blocking, Ansel/Hibiscus healing, and Steward's 24,601.12 total damage. These totals do not prove any role is replaceable or indispensable.\n- **UNKNOWN:** viable substitutions, DP/tile trade-offs, and effective sacrifice/rotation options.\n\n## Model stop\n\n- **OBSERVED:** 8 completed MCP calls: 1 status, 2 checks, 1 simulation, 4 queries. `turn.completed=true`, exit 0, automatic retry false.\n- **OBSERVED:** the final message says C2 was not submitted because no sufficiently justified combined repair was identified. This is not evidence that no repair exists.\n- **UNKNOWN_CLI_INTERNAL:** model-internal request count and hidden reasoning.\n\n## Search lesson\n\nThe structural rebuild bought upper closure and contact but lost three coupled success conditions: early roadblock clearance, protected-route timing, and a survivable support/artillery geometry. The next test should preserve or explicitly replace these duties rather than add a late central action alone. No counterfactual simulation was run; seven-ID feasibility remains UNKNOWN.\n\nMachine data: `zero_model_comparison_v1.json`; evidence hashes: `zero_model_evidence_index_v1.json`. Suggested, **unauthorized** next prompt: `next_prompt_suggestion_v2.md`.\n"""
    (SEVEN / "zero_model_comparison_report_v1.md").write_text(report)
    report = report.replace(
        "Coordinates below follow the DEPLOY event convention `[row,col]`; action snapshot tiles are `[x,y]`.",
        "Plan/action snapshot tiles use `[row,col]`; DEPLOY event detail tile strings use `[x,y]` after runtime conversion. Coordinates below follow the DEPLOY event convention.",
    )
    (SEVEN / "zero_model_comparison_report_v1.md").write_text(report)
    report = report.replace(
        "## Search lesson",
        "## Prior prompt evaluation\n\n"
        "`next_prompt_suggestion_v1.md` preserves the budget, four-tool boundary, and no-forced-C2 rule, but it is too generic: it names the healer symptom without roadblock #4's absent clearance, first-lock geometry change, or #21 unblock chain. "
        "`next_prompt_suggestion_v2.md` supplies the concrete, unauthorized next entry.\n\n## Search lesson",
    )
    (SEVEN / "zero_model_comparison_report_v1.md").write_text(report)


if __name__ == "__main__":
    main()
