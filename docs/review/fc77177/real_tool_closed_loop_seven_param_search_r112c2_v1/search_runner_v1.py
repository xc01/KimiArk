#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "docs/review/fc77177/real_tool_closed_loop_seven_param_search_r112c2_v1"
RUN_MCP = EXPERIMENT / "run_mcp_v1.py"
DEFAULT_BASE = EXPERIMENT / "input_bundle/r112_c002_structured_plan.json"
BASE = json.loads(DEFAULT_BASE.read_text())


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def selected_plan(payload: dict) -> dict:
    return payload["revised_operational_plans"][0]


def sync_selected_actions(payload: dict) -> dict:
    plan = selected_plan(payload)
    plan["deployment_positions_and_directions"] = [
        copy.deepcopy(action) for action in plan["action_timeline"] if action.get("action_type") == "DEPLOY"
    ]
    plan["selected_low_star_operator_ids"] = sorted({
        action["operator_id"] for action in plan["action_timeline"] if action.get("action_type") == "DEPLOY"
    })
    return payload


def build_plan(plan_id: str, changes: list[dict], validation_target: str) -> dict:
    payload = copy.deepcopy(BASE)
    payload["revision_hypothesis"]["hypothesis_id"] = f"R113_{plan_id.rsplit('_', 1)[-1]}"
    payload["revision_hypothesis"]["operational_plan_id"] = plan_id
    payload["revised_strategic_hypotheses"][0]["hypothesis_id"] = f"R113_{plan_id.rsplit('_', 1)[-1]}"
    plan = selected_plan(payload)
    plan["parent_hypothesis_id"] = f"R113_{plan_id.rsplit('_', 1)[-1]}"
    plan["operational_plan_id"] = plan_id
    plan.setdefault("validation_card", {})
    plan["validation_card"]["targeted_change"] = validation_target
    for change in changes:
        kind = change["type"]
        if kind == "add_retreat":
            plan["action_timeline"].append({"action_type": "RETREAT", "frame": int(change["frame"]), "operator_id": change["operator_id"]})
        elif kind == "add_deploy":
            plan["action_timeline"].append({
                "action_type": "DEPLOY", "direction": change["direction"], "frame": int(change["frame"]),
                "operator_id": change["operator_id"], "tile": list(change["tile"]),
            })
        elif kind == "remove_action":
            plan["action_timeline"] = [action for action in plan["action_timeline"] if not (
                action.get("action_type") == change.get("action_type")
                and action.get("operator_id") == change.get("operator_id")
                and (change.get("frame") is None or int(action.get("frame", -1)) == int(change["frame"]))
            )]
        elif kind == "set_action":
            for action in plan["action_timeline"]:
                if (
                    action.get("action_type") == change.get("action_type")
                    and action.get("operator_id") == change.get("operator_id")
                    and int(action.get("frame", -1)) == int(change["frame"])
                ):
                    for key, value in change["fields"].items():
                        action[key] = value
                    break
            else:
                raise RuntimeError(f"set_action target not found: {change}")
        else:
            raise RuntimeError(f"unsupported change type: {kind}")
    plan["action_timeline"].sort(key=lambda action: int(action["frame"]))
    return sync_selected_actions(payload)


def call_tool(tool: str, arguments: dict, output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, str(RUN_MCP), tool, "--arguments-json", json.dumps(arguments, ensure_ascii=False, separators=(",", ":")), "--output", str(output)],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{tool} failed ({completed.returncode}): {completed.stderr.strip()}\n{completed.stdout.strip()}")
    return json.loads(output.read_text())["result"]["structuredContent"]


def run_variant(variant: dict, *, force: bool = False) -> dict:
    plan_id = f"R113_SEVEN_PARAM_SEARCH_R112C2_{variant['id']}"
    payload = build_plan(plan_id, variant.get("changes", []), variant.get("validation_target", "Batch parameter search variant."))
    candidate_sha = hashlib.sha256(canonical(payload)).hexdigest()
    result_path = EXPERIMENT / "search/results" / f"{variant['id']}.json"
    if result_path.exists() and not force:
        return json.loads(result_path.read_text())
    check_output = EXPERIMENT / "search/tool_calls" / f"{variant['id']}_check.json"
    check = call_tool("check_plan", {"plan": payload}, check_output)
    record = {"variant_id": variant["id"], "plan_id": plan_id, "candidate_sha256": candidate_sha, "check": check, "simulation": None, "complete_win": False}
    if check.get("status") != "PASS":
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return record
    candidate_id = check["candidate_id"]
    record["candidate_id"] = candidate_id
    simulation_output = EXPERIMENT / "search/tool_calls" / f"{variant['id']}_run.json"
    simulation = call_tool("run_simulation", {"candidate_id": candidate_id, "candidate_sha256": candidate_sha}, simulation_output)
    record["simulation"] = simulation
    result = simulation.get("result") or {}
    record["complete_win"] = result.get("win") is True and simulation.get("status") == "COMPLETED"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    if record["complete_win"]:
        (EXPERIMENT / "search/COMPLETE_WIN_FOUND.json").write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return record


def main() -> int:
    global BASE
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    BASE = json.loads(args.base.read_text())
    variants = json.loads(args.batch.read_text())["variants"]
    for variant in variants:
        record = run_variant(variant, force=args.force)
        check = record["check"]
        simulation = record["simulation"] or {}
        result = simulation.get("result") or {}
        print(json.dumps({
            "variant": variant["id"], "check_status": check.get("status"),
            "check_errors": check.get("errors"), "simulation_status": simulation.get("status"),
            "result": result, "budget": simulation.get("budget"), "complete_win": record["complete_win"],
        }, ensure_ascii=False, sort_keys=True), flush=True)
        if record["complete_win"]:
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
