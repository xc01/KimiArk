"""R128: unlimited-sim Astra session. No candidate ledger, no budget gate.

Astra may submit any plan and run it through the real Simulator freely.
The host does NOT validate roster size, DP, SP or cooldowns before running;
it only rejects structurally malformed plans.  This is intentionally a
free sandbox: the goal is to let Astra discover what works and what breaks
in the simulator, not to enforce a scoring gate.
"""
from __future__ import annotations
import hashlib, json, sys, copy
from pathlib import Path

ROOT = Path('/home/bigdata/Desktop/arknights-auto-planner')
BASE = ROOT / 'docs/review/fc77177/five_astra_r128_unlimited_sim_v1'
SESSION_ROOT = BASE / 'session'
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from arknights_planner.adapters.approximate_real import (
    ApproximateRealSimulationAdapter, RealOperatorSelection,
    RealSimulationApproximationPolicy,
)
from arknights_planner.gamedata.repository import GameDataRepository
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.simulator import Simulator, SimulationConfig
from arknights_planner.simulator.range import ApproximateRealRangeTransformer
from arknights_planner.simulator.projectile import InstantProjectileModel
from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION

FRAMES = 30.0
STAGE_ID = "main_08-07"
GAMEDATA = ROOT / "data/ArknightsGameData"
PARENTS = BASE / "parents"

_run_counter = {"n": 0}
_runs: dict[str, dict] = {}

EVIDENCE = json.loads((BASE / "input_bundle" / "llm_evidence_context.json").read_text())
CATALOG = {r["operator_id"]: r for r in EVIDENCE["normal_low_star_catalog"]}

TOOLS = [
  {"name": "get_session_status", "description": "Read session metadata: mechanics version, stage, parents, run counter.", "inputSchema": {"type": "object", "properties": {}}},
  {"name": "list_parents", "description": "List the bundled parent plans (five-op R123_MEright and eight-op M70 WIN) with their full actions.", "inputSchema": {"type": "object", "properties": {}}},
  {"name": "run_simulation", "description": "Run any plan through the real Simulator.  Returns full summary + all events.  Unlimited: no budget is consumed.  Plan shape: {actions:[{action_type,frame,operator_id,tile?,direction?}], selected:[operator_id,...]}.  action_type in DEPLOY|ACTIVATE_SKILL|RETREAT.  frame is the 30fps frame index.  tile is [row,col].  direction is UP|DOWN|LEFT|RIGHT.", "inputSchema": {"type": "object", "required": ["actions", "selected"], "properties": {"actions": {"type": "array"}, "selected": {"type": "array"}, "label": {"type": "string"}}, "additionalProperties": False}},
  {"name": "query_events", "description": "Query events of the last run.  Pass run_id from run_simulation, or omit for the latest.", "inputSchema": {"type": "object", "properties": {"run_id": {"type": "string"}, "event_type": {"type": "string"}, "source_id": {"type": "string"}, "target_id": {"type": "string"}, "earliest_frame": {"type": "integer"}, "latest_frame": {"type": "integer"}, "limit": {"type": "integer"}, "offset": {"type": "integer"}, "aggregate_field": {"type": "string"}}, "additionalProperties": False}},
  {"name": "inspect_file", "description": "Read a file under the repository (py/json/md only, capped at 200 lines).", "inputSchema": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}, "line": {"type": "integer"}, "limit": {"type": "integer"}}, "additionalProperties": False}},
]

def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def _load_parents() -> dict:
    out = {}
    for d in sorted(PARENTS.iterdir()):
        if not d.is_dir():
            continue
        cand = d / "direction_complete_action_candidate.json"
        if not cand.is_file():
            continue
        data = json.loads(cand.read_text())
        out[d.name] = {
            "parent_id": d.name,
            "plan_id": data.get("operational_plan_id"),
            "actions": data.get("actions", []),
            "sha256": _sha(cand),
        }
    return out

def _norm_action(a: dict) -> dict:
    at = a.get("action_type") or a.get("type")
    if at not in {"DEPLOY", "ACTIVATE_SKILL", "RETREAT"}:
        raise RuntimeError(f"invalid action_type {at!r}")
    frame = a.get("frame")
    if not isinstance(frame, (int, float)):
        raise RuntimeError("action.frame must be a number (30fps frame index)")
    op = a.get("operator_id")
    if not isinstance(op, str) or not op:
        raise RuntimeError("action.operator_id must be a string")
    out = {"action_type": at, "frame": float(frame), "operator_id": op}
    if at == "DEPLOY":
        tile = a.get("tile")
        if not (isinstance(tile, (list, tuple)) and len(tile) == 2):
            raise RuntimeError("DEPLOY action requires tile:[row,col]")
        out["tile"] = [int(tile[0]), int(tile[1])]
        d = a.get("direction")
        if d not in {"UP", "DOWN", "LEFT", "RIGHT"}:
            raise RuntimeError(f"DEPLOY action requires direction UP|DOWN|LEFT|RIGHT, got {d!r}")
        out["direction"] = d
    return out

def _run_sim(config, actions_raw, selected, label):
    actions = [_norm_action(a) for a in actions_raw]
    actions.sort(key=lambda a: (a["frame"], a["action_type"]))
    deploys = [a for a in actions if a["action_type"] == "DEPLOY"]
    sel = list(selected)
    if set(a["operator_id"] for a in deploys) != set(sel):
        raise RuntimeError(f"deploy set {sorted(set(a['operator_id'] for a in deploys))} != selected {sorted(sel)}")
    if len(sel) > 12:
        raise RuntimeError(f"selected roster {len(sel)} exceeds sandbox cap 12")
    selections = tuple(
        RealOperatorSelection(
            a["operator_id"],
            int(CATALOG[a["operator_id"]]["debug_configuration"]["phase_index"]),
            int(CATALOG[a["operator_id"]]["debug_configuration"]["level"]),
            (a["tile"][1], a["tile"][0]),
            a["direction"],
            a["frame"] / FRAMES,
        ) for a in deploys
    )
    strategy_actions = []
    for a in actions:
        at = {"DEPLOY": ActionType.DEPLOY, "ACTIVATE_SKILL": ActionType.ACTIVATE_SKILL, "RETREAT": ActionType.RETREAT}[a["action_type"]]
        tile = (a["tile"][1], a["tile"][0]) if "tile" in a else None
        strategy_actions.append(Action(at, a["frame"] / FRAMES, a["operator_id"], tile, a.get("direction")))
    policy = RealSimulationApproximationPolicy.m11_second_quantized()
    fixture = ApproximateRealSimulationAdapter(GameDataRepository(GAMEDATA)).build_fixture(
        stage_id_or_code=STAGE_ID, selections=selections, policy=policy)
    strategy = Strategy(tuple(a["operator_id"] for a in deploys), tuple(strategy_actions))
    result = Simulator(range_transformer=ApproximateRealRangeTransformer(), projectile_model=InstantProjectileModel()).run(
        stage=fixture.stage, operators=fixture.operators, enemies=fixture.enemies,
        strategy=strategy, config=SimulationConfig(dt=1 / FRAMES, max_time=600.0))
    events = [{"frame": round(e.time * FRAMES), "event_type": e.event_type.value,
               "source_id": e.source_id, "target_id": e.target_id,
               "details": dict(e.details)} for e in result.events]
    _run_counter["n"] += 1
    run_id = f"run-{_run_counter['n']:04d}" + (f"-{label}" if label else "")
    summary = {
        "run_id": run_id, "mechanics_version": ACTIVE_MECHANICS_VERSION, "stage_id": STAGE_ID,
        "simulator_win": bool(result.win), "enemies_killed": result.enemies_killed,
        "enemies_leaked": result.enemies_leaked, "remaining_life": result.remaining_life,
        "operator_deaths": result.operator_deaths,
        "leak_ids": [e["source_id"] for e in events if e["event_type"] == "ENEMY_LEAK"],
        "action_count": len(actions), "selected": sel,
    }
    _runs[run_id] = {"summary": summary, "events": events, "actions": actions, "selected": sel}
    (SESSION_ROOT / "runs").mkdir(parents=True, exist_ok=True)
    (SESSION_ROOT / "runs" / f"{run_id}.json").write_text(json.dumps(
        {"summary": summary, "events": events, "actions": actions, "selected": sel},
        ensure_ascii=False, indent=1))
    return {"summary": summary, "events": events}

def _query_events(config, a):
    run_id = a.get("run_id")
    if run_id is None:
        if not _runs:
            raise RuntimeError("no runs yet")
        run_id = max(_runs)
    if run_id not in _runs:
        raise RuntimeError(f"unknown run_id {run_id}")
    events = _runs[run_id]["events"]
    if a.get("event_type"):
        events = [e for e in events if e["event_type"] == a["event_type"]]
    if a.get("source_id") is not None:
        events = [e for e in events if e["source_id"] == a["source_id"]]
    if a.get("target_id") is not None:
        events = [e for e in events if e["target_id"] == a["target_id"]]
    if a.get("earliest_frame") is not None:
        events = [e for e in events if e["frame"] >= int(a["earliest_frame"])]
    if a.get("latest_frame") is not None:
        events = [e for e in events if e["frame"] <= int(a["latest_frame"])]
    field = a.get("aggregate_field")
    if field:
        agg: dict = {}
        for e in events:
            v = e["details"].get(field)
            if v is None:
                continue
            k = f"{e['source_id']}->{e['target_id']}"
            try:
                agg[k] = agg.get(k, 0.0) + float(v)
            except (TypeError, ValueError):
                agg[k] = agg.get(k, 0.0)
        return {"run_id": run_id, "aggregate_field": field, "sums": agg, "matched": len(events)}
    limit = min(int(a.get("limit") or 200), 2000)
    offset = int(a.get("offset") or 0)
    return {"run_id": run_id, "matched": len(events), "returned": len(events[offset:offset + limit]),
            "events": events[offset:offset + limit], "summary": _runs[run_id]["summary"]}

def _inspect(config, a):
    p = (ROOT / a["path"]).resolve()
    p.relative_to(ROOT)
    if p.suffix not in {".py", ".json", ".md", ".txt"}:
        raise RuntimeError("only py/json/md/txt")
    lines = p.read_text().splitlines()
    start = max(0, int(a.get("line", 1)) - 1)
    n = min(int(a.get("limit", 200)), 200)
    return {"path": str(p.relative_to(ROOT)), "first_line": start + 1,
            "lines": lines[start:start + n], "sha256": _sha(p)}

def handle(config, message):
    method = message.get("method")
    rid = message.get("id")
    if method == "initialize":
        v = (message.get("params") or {}).get("protocolVersion")
        return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": v if isinstance(v, str) and v else "2024-11-05",
                "serverInfo": {"name": "kimiark-r128-unlimited-sim", "version": "1.0.0"},
                "capabilities": {"tools": {"listChanged": False}}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = (message.get("params") or {}).get("name")
        args = (message.get("params") or {}).get("arguments") or {}
        try:
            if name == "get_session_status":
                result = {"mechanics_version": ACTIVE_MECHANICS_VERSION, "stage_id": STAGE_ID,
                          "parents": _load_parents(), "run_count": _run_counter["n"], "unlimited": True}
            elif name == "list_parents":
                result = _load_parents()
            elif name == "run_simulation":
                result = _run_sim(config, args.get("actions") or [], args.get("selected") or [], args.get("label"))
            elif name == "query_events":
                result = _query_events(config, args)
            elif name == "inspect_file":
                result = _inspect(config, args)
            else:
                return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps({"error": f"unknown tool {name}"})}], "isError": True}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps({"error": type(exc).__name__, "message": str(exc), "automatic_retry": False}, ensure_ascii=False)}], "isError": True}}
        return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}}
    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}

def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}}
        else:
            resp = handle(None, msg)
        if resp is not None:
            print(json.dumps(resp, ensure_ascii=False, separators=(",", ":")), flush=True)

if __name__ == "__main__":
    main()
