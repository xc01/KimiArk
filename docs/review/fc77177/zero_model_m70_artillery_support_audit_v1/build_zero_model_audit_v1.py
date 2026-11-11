from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.simulator import ApproximateRealRangeTransformer


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs/review/fc77177/zero_model_m70_artillery_support_audit_v1"
BASE = "docs/review/fc77177"
CASES = {
    "M70": {
        "plan_id": "R8_7_GPT_M70_V1",
        "directory": f"{BASE}/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic",
    },
    "R94_C1": {
        "plan_id": "R94_SOL_HIGH_SEVEN_RETRY2_001",
        "directory": f"{BASE}/real_tool_closed_loop_sol_high_seven_retry2_v1/session/candidates/candidate-001/simulation",
    },
    "R95_C1": {
        "plan_id": "R95_SOL_HIGH_SEVEN_RETRY3_001",
        "directory": f"{BASE}/real_tool_closed_loop_sol_high_seven_retry3_v1/session/candidates/candidate-001/simulation",
    },
    "R95_C2": {
        "plan_id": "R95_SOL_HIGH_SEVEN_RETRY3_002",
        "directory": f"{BASE}/real_tool_closed_loop_sol_high_seven_retry3_v1/session/candidates/candidate-002/simulation",
    },
    "R96_C1": {
        "plan_id": "R96_SOL_HIGH_SEVEN_SUPPORT_COVERAGE_001",
        "directory": f"{BASE}/real_tool_closed_loop_sol_high_seven_support_coverage_v1/session/candidates/candidate-001/simulation",
    },
    "R96_C2": {
        "plan_id": "R96_SOL_HIGH_SEVEN_SUPPORT_COVERAGE_002",
        "directory": f"{BASE}/real_tool_closed_loop_sol_high_seven_support_coverage_v1/session/candidates/candidate-002/simulation",
    },
}
SUPPORT_IDS = ("char_212_ansel", "char_120_hibisc", "char_210_stward")
ARTILLERY_PREFIX = "enemy_1112_emppnt#"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restored_digest(path: Path) -> str:
    return hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()


def load_case(case_key: str) -> dict:
    directory = ROOT / CASES[case_key]["directory"]
    plan_path = directory / "plan_snapshot.json"
    action_path = directory / "action_snapshot.json"
    events_path = directory / "diagnostic_events.json.gz"
    final_path = directory / "final_status.json"
    plan = json.loads(plan_path.read_text())
    actions = json.loads(action_path.read_text())["actions"]
    with gzip.open(events_path, "rt") as handle:
        events = json.loads(handle.read())["events"]
    final = json.loads(final_path.read_text())
    return {
        "key": case_key,
        "plan_id": plan["operational_plan_id"],
        "final_status_plan_id": final["plan_id"],
        "directory": CASES[case_key]["directory"],
        "plan_path": f"{CASES[case_key]['directory']}/plan_snapshot.json",
        "action_path": f"{CASES[case_key]['directory']}/action_snapshot.json",
        "events_path": f"{CASES[case_key]['directory']}/diagnostic_events.json.gz",
        "final_path": f"{CASES[case_key]['directory']}/final_status.json",
        "plan_sha256": digest(plan_path),
        "action_sha256": digest(action_path),
        "events_gz_sha256": digest(events_path),
        "events_restored_sha256": restored_digest(events_path),
        "final_sha256": digest(final_path),
        "selected_low_star_operator_ids": plan["selected_low_star_operator_ids"],
        "actions": actions,
        "events": events,
        "final": final,
    }


def first_deployment(case: dict, operator_id: str) -> dict | None:
    for event in case["events"]:
        if event["event_type"] == "DEPLOY" and event.get("source_id") == operator_id:
            return {
                "frame": event["frame"],
                "runtime_tile_string": event["details"]["tile"],
                "runtime_tile": [int(value) for value in event["details"]["tile"].split(",")],
            }
    return None


def first_planned_deployment(case: dict, operator_id: str) -> dict | None:
    for action in case["actions"]:
        if action["action_type"] == "DEPLOY" and action["operator_id"] == operator_id:
            return {
                "frame": action["frame"],
                "direction": action["direction"],
                "plan_action_tile": action["tile"],
                "runtime_tile": list(reversed(action["tile"])),
            }
    return None


def range_cells(repository: GameDataRepository, operator_id: str) -> list[tuple[int, int]]:
    operator = repository.get_operator(operator_id)
    range_id = operator.phases[-1].range_id.value
    attack_range = repository.get_range(range_id)
    return [(cell.row, cell.col) for cell in attack_range.cells]


def support_facts(case: dict, repository: GameDataRepository, transformer: ApproximateRealRangeTransformer) -> dict:
    steward = first_planned_deployment(case, "char_210_stward")
    support = {}
    for operator_id in ("char_212_ansel", "char_120_hibisc"):
        deployment = first_planned_deployment(case, operator_id)
        if deployment is None:
            support[operator_id] = {"first_planned_deployment": None, "covers_first_steward_tile": False}
            continue
        covered = transformer.covered_tiles(
            origin=tuple(deployment["runtime_tile"]),
            offsets=range_cells(repository, operator_id),
            direction=deployment["direction"],
        )
        support[operator_id] = {
            "first_planned_deployment": deployment,
            "covers_first_steward_tile": tuple(steward["runtime_tile"]) in covered,
            "coverage_basis": "ApproximateRealRangeTransformer and resolved normal range_id cells; no continuous-position interpolation.",
        }
    support["char_210_stward"] = {"first_planned_deployment": steward}
    return support


def frame_events(case: dict, event_type: str, source_id: str | None = None, target_id: str | None = None) -> list[dict]:
    result = []
    for event in case["events"]:
        if event["event_type"] != event_type:
            continue
        if source_id is not None and event.get("source_id") != source_id:
            continue
        if target_id is not None and event.get("target_id") != target_id:
            continue
        result.append(event)
    return result


def summarize_events(case: dict) -> dict:
    events = case["events"]
    deaths = [event for event in events if event["event_type"] == "OPERATOR_DEATH"]
    invalid_actions = [
        {
            "frame": event["frame"],
            "event_type": event["event_type"],
            "source_id": event["source_id"],
            "details": event["details"],
            "executor_death_frame": next(
                (
                    death["frame"]
                    for death in deaths
                    if death["source_id"] == event["source_id"] and death["frame"] <= event["frame"]
                ),
                None,
            ),
        }
        for event in events
        if event["event_type"] in ("DEPLOY", "RETREAT", "SKILL_ACTIVATE")
        and event.get("details", {}).get("legal") is False
    ]
    shells = [
        {
            "frame": event["frame"],
            "target_id": event.get("target_id"),
            "amount": event["details"].get("amount"),
            "locked_position": event["details"].get("locked_position"),
        }
        for event in events
        if event["event_type"] == "ENEMY_ABILITY_HIT" and str(event.get("source_id", "")).startswith(ARTILLERY_PREFIX)
    ]
    steward_damage = frame_events(case, "DAMAGE", "char_210_stward", "enemy_1112_emppnt#0")
    steward_heals = [
        {"frame": event["frame"], "source_id": event["source_id"], "amount": event["details"]["amount"]}
        for event in events
        if event["event_type"] == "HEAL" and event.get("target_id") == "char_210_stward"
    ]
    return {
        "final": {
            "result_classification": case["final"]["result_classification"],
            "enemies_killed": case["final"]["enemies_killed"],
            "enemies_leaked": case["final"]["enemies_leaked"],
            "remaining_life": case["final"]["remaining_life"],
            "operator_deaths": len(deaths),
            "unique_operator_death_ids": sorted({event["source_id"] for event in deaths}),
            "operator_death_frames": [{"frame": event["frame"], "source_id": event["source_id"]} for event in deaths],
            "protected_reached": [
                {"frame": event["frame"], "target_id": event.get("target_id")}
                for event in events
                if event["event_type"] == "PROTECTED_TARGET_REACHED"
            ],
            "protected_deaths": [
                {"frame": event["frame"], "remaining_life": event["details"].get("remaining_life")}
                for event in events
                if event["event_type"] == "OBJECTIVE_FAILURE" and event.get("details", {}).get("reason") == "PROTECTED_TARGET_DEATH"
            ],
            "device_destroyed": [
                {"frame": event["frame"], "source_id": event.get("source_id")}
                for event in events
                if event["event_type"] == "DEVICE_DESTROYED"
            ],
        },
        "artillery_shells_on_operators": shells,
        "steward_to_artillery": {
            "hit_count": len(steward_damage),
            "total_damage": round(sum(event["details"]["amount"] for event in steward_damage), 2),
            "first_frame": steward_damage[0]["frame"] if steward_damage else None,
            "last_frame": steward_damage[-1]["frame"] if steward_damage else None,
            "artillery_death": [
                {"frame": event["frame"], "source_id": event.get("source_id"), "target_id": event.get("target_id")}
                for event in events
                if event["event_type"] == "ENEMY_DEATH" and event.get("target_id") == "enemy_1112_emppnt#0"
            ],
        },
        "heals_to_steward": steward_heals,
        "recorded_action_errors": invalid_actions,
        "action_error_classification": {
            "dependency_failures_after_executor_death": sum(
                1 for item in invalid_actions if item["executor_death_frame"] is not None
            ),
            "independent_action_errors": sum(
                1 for item in invalid_actions if item["executor_death_frame"] is None
            ),
        },
    }


def source_index() -> dict:
    cases = {}
    for key in CASES:
        case = load_case(key)
        cases[key] = {
            "plan_id": case["plan_id"],
            "final_status_plan_id": case["final_status_plan_id"],
            "paths": {
                "plan": case["plan_path"],
                "action": case["action_path"],
                "events_gz": case["events_path"],
                "final": case["final_path"],
            },
            "sha256": {
                "plan": case["plan_sha256"],
                "action": case["action_sha256"],
                "events_gz": case["events_gz_sha256"],
                "events_restored": case["events_restored_sha256"],
                "final": case["final_sha256"],
            },
            "event_count": len(case["events"]),
        }
    return {
        "schema_version": "KIMIARK_ZERO_MODEL_M70_ARTILLERY_SUPPORT_AUDIT_INDEX_V1",
        "boundary": "Read-only fixed-simulator archive audit; no model call, simulation, or new STARTED.",
        "repo_head": "8909545f503ae9ca5325027587d51eaa568df2b3",
        "sources": cases,
        "observed_core": {
            "m70_artillery_success": {
                "classification": "OBSERVED",
                "steward_first_output_runtime_tile": [7, 5],
                "ansel_and_hibiscus_cover_steward_tile": True,
                "steward_hits_artillery": 45,
                "steward_damage": 13227.21,
                "artillery_death_frame": 4273,
                "operator_deaths": 0,
            },
            "dual_support_necessity": {
                "classification": "HYPOTHESIS",
                "statement": "M70 had observed dual support coverage and actual staggered heals. This audit does not prove both medics are necessary or sufficient in a seven-ID plan.",
            },
        },
        "falsifiable_questions": [
            {
                "id": "Q1_DUAL_SUPPORT_GEOMETRY",
                "classification": "HYPOTHESIS",
                "question": "Can a seven-ID plan place genuinely covering support for its artillery-output tile without recreating R96 C2's shared splash death, while retaining opening and protected-route duties?",
                "contrast": "Unlike R95 timing changes and R96 C2's one late heal, this tests actual static/dynamic coverage and shared-exposure geometry.",
            },
            {
                "id": "Q2_ALTERNATIVE_ARTILLERY_CLOSURE",
                "classification": "HYPOTHESIS",
                "question": "Can artillery be killed through a different output placement or executor before the M70-like support question is settled, without losing opening/roadblock/central duties?",
                "contrast": "Unlike repeated Steward survival patches, this does not require keeping Steward alive as the success metric.",
            },
        ],
    }


def build_fact_pack() -> dict:
    repository = GameDataRepository(ROOT / "data/ArknightsGameData")
    transformer = ApproximateRealRangeTransformer()
    cases = {}
    for key in CASES:
        case = load_case(key)
        summary = summarize_events(case)
        cases[key] = {
            "plan_id": case["plan_id"],
            "identity": {
                "plan_sha256": case["plan_sha256"],
                "action_sha256": case["action_sha256"],
                "events_gz_sha256": case["events_gz_sha256"],
                "events_restored_sha256": case["events_restored_sha256"],
            },
            "selected_low_star_operator_ids": case["selected_low_star_operator_ids"],
            "support_positions_and_coverage": support_facts(case, repository, transformer),
            "observed": summary,
        }
    context_path = ROOT / f"{BASE}/real_tool_closed_loop_sol_high_seven_support_coverage_v1/input_bundle/llm_evidence_context.json"
    context = json.loads(context_path.read_text())
    catalog = context["normal_low_star_catalog"]
    return {
        "schema_version": "KIMIARK_NEXT_FACT_PACK_DRAFT_V1",
        "boundary": "Zero-model draft for a future authorized experiment. It contains observed archive facts, explicit UNKNOWN/HYPOTHESIS labels, and the full legal catalog. It is not an execution authorization.",
        "coordinates": {
            "plan_action_tiles": "[row,col]",
            "deploy_event_detail": "runtime [x,y]/[col,row] string",
            "conversion": "Plan/action [a,b] becomes runtime (b,a).",
            "non_symmetric_example": "R95 Steward plan/action [2,7] becomes DEPLOY detail tile '7,2'.",
            "transformer": "ApproximateRealRangeTransformer",
        },
        "audit_sources": {key: {"directory": CASES[key]["directory"], "identity": value["identity"]} for key, value in cases.items()},
        "comparison": cases,
        "catalog": {
            "size": len(catalog),
            "source_path": str(context_path.relative_to(ROOT)),
            "source_sha256": digest(context_path),
            "entries": catalog,
            "debug_configuration_retained": True,
        },
    }


def write_report(index: dict) -> None:
    rows = []
    labels = {
        "M70": "M70 8-ID",
        "R94_C1": "R94 C1",
        "R95_C1": "R95 C1",
        "R95_C2": "R95 C2",
        "R96_C1": "R96 C1",
        "R96_C2": "R96 C2",
    }
    cases = index["sources"]
    for key in labels:
        source = cases[key]
        rows.append(
            f"| {labels[key]} | `{source['plan_id']}` | `{source['sha256']['plan'][:12]}…` | `{source['sha256']['action'][:12]}…` | "
            f"`{source['sha256']['events_gz'][:12]}…` |"
        )
    report = f"""# M70 artillery/support zero-model audit v1

## Boundary

This is a read-only audit of existing fixed-simulator archives. It used no model CLI, no simulation, no `run_simulation`, and created no new `STARTED`. It does not claim real-game, faithful, robust, probabilistic, seven-ID-impossible, or global-minimum results. `OBSERVED` means an archive event/static identity was verified; `HYPOTHESIS` remains untested.

## Identity

HEAD/remote at audit start: `8909545f503ae9ca5325027587d51eaa568df2b3`. Identities were checked by raw plan/action/event-gzip SHA-256 and gzip restored-event SHA-256.

| Case | Plan ID | Plan | Action | Events.gzip |
|---|---|---|---|---|
{chr(10).join(rows)}

## Core finding

M70's artillery success was not merely “Steward attacked.” Its first output tile was runtime `(7,5)`, and both Ansel runtime `(6,5) DOWN` and Hibiscus runtime `(6,2) UP` covered it. Steward hit the artillery 45 times for `13227.21`; the artillery died at `4273`; no operator died. This is `OBSERVED`.

Whether dual support coverage is necessary or sufficient for a seven-ID plan is `HYPOTHESIS`. The observed seven-ID losses show that changing timing or roster without establishing actual coverage can leave the failure unchanged:

- R94: Steward runtime `(7,2)`; only Ansel covered. Steward hit 23 times for `6626.06`, then died at `3343`.
- R95 C1/C2: Steward runtime `(7,2)`; Hibiscus did not cover despite changed deployment/skill timing. Ansel was the only relevant healer, with one heal at `2959`; Steward hit 16 times for `4658.17`, then died at `3043` in both versions.
- R96 C1: Steward runtime `(6,5)`; Hibiscus geometrically covered it but died at `1571`, before Steward deployed at `2071`. Steward hit 8 times for `2216.99`, then died at `2443`.
- R96 C2: Steward runtime `(6,5)`; both medics geometrically covered it. Hibiscus actually healed Steward `372.6` at `2476`, but Ansel died at `2261` after shells locked `(5,5)` then `(5,6)`. Steward still died at `2561` after 11 hits for `3188.48`.

Exact HP at arbitrary frames is `UNKNOWN`. No total-heal or “one more heal must survive” claim is made.

## Requested checks

1. **R95 non-propagation:** Hbiscus timing changed, but its runtime `(3,5) RIGHT` coverage never reached Steward's `(7,2)`. The only Steward heal remained Ansel `506.8@2959`. Because Steward's deployment and shell locks stayed at `(7,2)`, the relevant hit/heal sequence did not change.
2. **R96 C2 Ansel death chain:** Ansel moved to runtime `(5,5)`. Shells locked `(5,5)` and `(5,6)` hit Ansel at `1961` and `2261`; no heal to Ansel was observed in the checked window. It died before the Steward shells at `2411` and `2561`. This proves a changed exposure and death chain, not that Ansel was deliberately sacrificed to heal Steward.
3. **Action errors:** R96 C1 had 9 and C2 had 6 recorded `legal:false` actions. Every one occurred after the executor's recorded death; no independent illegal deployment/coordinate error was found. They are dependency failures, not separate independent design failures.
4. **M70 grounding:** M70 was not merely indexed. The R96 model trajectory read the M70 plan/status, decompressed M70 events, and inspected shells, deaths, devices, and healer aggregates (`codex_exec.jsonl` items 9-13). It did not preserve M70's observed dual-support condition as a mandatory constraint; that was a tactical-parent choice, not evidence absence.

## Falsifiable next questions

1. **Q1_DUAL_SUPPORT_GEOMETRY** — Can a seven-ID plan establish real support coverage for the artillery-output tile while avoiding R96 C2's shared splash exposure, with opening/protected-route duties retained? Observe actual support coverage, shells/heals, operator deaths, artillery damage/death, protected outcomes, and leaks.
2. **Q2_ALTERNATIVE_ARTILLERY_CLOSURE** — Can artillery be closed by a materially different output placement/executor before sustained Steward survival is solved, without dropping opening, roadblock, central, or protected-route duties? Observe each operator's actual artillery damage, artillery death, and the independent endgame conditions.

These are hypotheses, not approved actions. No roster or old frame is mandatory.

## Artifacts

- Machine-readable index: `comparison_index_v1.json`
- Fact-pack draft: `next_fact_pack_draft_v1.json`
- Unauthorized next prompt: `next_prompt_suggestion_v1.md`

Actual model calls: **0**. Actual simulations: **0**. New `STARTED`: **0**.
"""
    (OUT / "audit_report_v1.md").write_text(report)


def write_next_prompt() -> None:
    text = """# Next bounded seven-ID prompt (read-only suggestion; not an execution authorization)

If separately authorized, start a fresh `gpt-6.1-sol/high`, `features.apps=false` session. New independent budget: at most 1 real CLI start, 10 checks, 2 candidates, and 2 complete fixed simulations. Do not resume prior sessions or transfer/reset ledgers. STARTED failures count. Internal requests are `UNKNOWN_CLI_INTERNAL`; `cached_input` is an input subset.

Use the audited M70/R94/R95/R96 evidence after verifying hashes. M70 remains the eight-ID fixed-simulator WIN. Seven-or-fewer feasibility remains UNKNOWN.

The roster is fully open to all 34 legal ordinary-mode 1-3-star IDs. `selected_low_star_operator_ids` plus every deployed operator/robot ID must have union ≤7; same-ID redeployment counts once and robots count. No role is mandatory and none is forbidden.

Before C1, choose one of these materially different hypotheses and save a validation card:

1. **Q1_DUAL_SUPPORT_GEOMETRY:** Establish actual support coverage of the chosen artillery-output tile without recreating R96 C2's shared splash death. The card must name expected shell locks, beneficiary/heals, replacements for opening, both protected routes, roadblocks, and central duties.
2. **Q2_ALTERNATIVE_ARTILLERY_CLOSURE:** Test a materially different output placement/executor for artillery closure without treating sustained Steward survival as the success metric. The card must predict actual artillery DAMAGE/death and explain how opening, roadblocks, both protected routes, and central #21/#22/#34 duties remain covered.

Do not copy old frames as universal deadlines. Convert plan/action `[row,col]` to runtime `[x,y]` explicitly. Continuous positions remain UNKNOWN without records. Keep unsupported mechanics as `MODEL_GAP`; do not assume guaranteed dodges, preswing locks, Ansel double-heal, or favorable targeting.

Use only `get_session_status`, `check_plan`, `run_simulation`, and `query_events` through the production controlled runner. Freeze checked actions unchanged. After full settlement, classify the targeted prediction as proved, refuted, truncated by an earlier failure, or evidence-unknown. Run C2 only for a materially different repair supported by C1 evidence; otherwise leave the second candidate/simulation unused.

WIN requires simulator WIN, legal union ≤7, zero leaks, both protected targets alive and reached, every enemy settled with no active enemies, and complete settlement. Do not claim real-game, faithful, robust, probabilistic, seven-ID-impossible, or global-minimum results.
"""
    (OUT / "next_prompt_suggestion_v1.md").write_text(text)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = source_index()
    (OUT / "comparison_index_v1.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    fact_pack = build_fact_pack()
    (OUT / "next_fact_pack_draft_v1.json").write_text(json.dumps(fact_pack, ensure_ascii=False, indent=2) + "\n")
    write_report(index)
    write_next_prompt()
    files = [
        "build_zero_model_audit_v1.py",
        "comparison_index_v1.json",
        "audit_report_v1.md",
        "next_fact_pack_draft_v1.json",
        "next_prompt_suggestion_v1.md",
    ]
    manifest = {
        "schema_version": "KIMIARK_ZERO_MODEL_M70_ARTILLERY_SUPPORT_AUDIT_MANIFEST_V1",
        "generated_from_head": "8909545f503ae9ca5325027587d51eaa568df2b3",
        "boundary": "Zero-model archive audit only; no model CLI, simulation, or STARTED.",
        "files": {name: digest(OUT / name) for name in files},
    }
    (OUT / "artifact_manifest_v1.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
