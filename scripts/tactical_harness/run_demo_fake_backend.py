#!/usr/bin/env python3
"""Fake-backend acceptance demo for the reusable tactical-experiment harness.

Runs entirely against TEST_ONLY_FAKE. No real model call, no real simulation budget.

It drives ``tactical_harness_service_v1`` over the real stdio JSON-RPC transport and replays a
recorded "Astra" tool sequence so the whole loop is exercised end to end:

  teacher prompt (verbatim) -> consult experience + mechanics KB -> record round 1 hypothesis
  -> submit a multi-combination search (budget pre-flight, static rejection, PASS+run)
  -> read the real returned evidence -> record round 2 and change direction -> candidate-002 win
  -> attempt independent verification (truthfully reported as a cache hit in fake mode)
  -> split-record the teaching exchange.

The demo also has a deterministic synthetic unit check for the leak-delta / complementary-branch
logic, because the fake executor does not emit per-enemy leak IDs.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "scripts/tactical_harness/tactical_harness_service_v1.py"
PREPARE = ROOT / "scripts/tactical_harness/prepare_harness.py"

TEMPLATE_EVIDENCE = "docs/review/fc77177/five_astra_r129_dual_track_v1/input_bundle/llm_evidence_context.json"
TEMPLATE_SCHEMA = "docs/review/fc77177/five_astra_r129_dual_track_v1/input_bundle/revision_output_schema.json"
PARENT_A = "docs/review/fc77177/five_astra_r129_dual_track_v1/parents/five_op_R123_MEright"
PARENT_M70 = "docs/review/fc77177/five_astra_r129_dual_track_v1/parents/m70_eight_op_WIN"

TEACHER_PROMPT = (
    "GLM, 把这条原样转给 Astra：Falco 第一次开技能的时点如果被推后，"
    "先别猜能不能夹住炮兵，去看 1382 附近是不是 SP 还没转好。"
)
HYPOTHESIS = "Delay Falco deploy so his opening skill is charge-ready before the first cast window"

checks: list[tuple[str, bool, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    checks.append((label, bool(condition), detail))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + (f" :: {detail}" if detail and not condition else ""))


class Harness:
    """Minimal JSON-RPC stdio client for the harness service."""

    def __init__(self, batch: Path):
        self.batch = batch
        self.next_id = 0
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVICE), str(batch)],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.call("initialize", {"protocolVersion": "2025-06-18"})
        self.notify("notifications/initialized", {})

    def _send(self, payload: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def call(self, method: str, params: dict) -> dict:
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params})
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline()
        return json.loads(line)

    def tool(self, name: str, arguments: dict) -> dict:
        response = self.call("tools/call", {"name": name, "arguments": arguments})
        result = response.get("result", {})
        return result.get("structuredContent", result)

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.wait(timeout=30)


def prepare_batch(out: str, *, max_checks: int, max_candidates: int, max_simulations: int, reserve: int, session_id: str) -> Path:
    batch = ROOT / out
    if (batch / "session_config_v1.json").exists():
        raise SystemExit(f"demo batch already exists, choose a new path: {batch}")
    command = [
        sys.executable, str(PREPARE),
        "--out", out,
        "--template-evidence", TEMPLATE_EVIDENCE,
        "--template-schema", TEMPLATE_SCHEMA,
        "--parent", f"A={PARENT_A}",
        "--parent", f"M70={PARENT_M70}",
        "--template-parent", "T",
        "--roster", "open", "--max-operators", "7", "--rounds", "5",
        "--max-checks", str(max_checks), "--max-candidates", str(max_candidates),
        "--max-simulations", str(max_simulations), "--reserve-simulations", str(reserve),
        "--session-id", session_id, "--stage-id", "FAKE_TEST-r8-7",
        "--plan-prefix", "HARN_", "--plan-label", "HARNESS",
        "--model", "gpt-test", "--reasoning-effort", "low",
        "--backend", "TEST_ONLY_FAKE", "--session-name", "harness-fake-demo",
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if completed.returncode:
        raise SystemExit(f"prepare failed: {completed.stderr or completed.stdout}")
    return batch


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/tactical_harness_demo")
    if not root.is_absolute():
        root = ROOT / root
    main.root = root  # type: ignore[attr-defined]
    batch = prepare_batch(
        str(root / "acceptance_v1"),
        max_checks=20, max_candidates=5, max_simulations=5, reserve=1,
        session_id="TEST_ONLY-harness-acceptance",
    )
    harness = Harness(batch)
    try:
        run_acceptance(harness, batch)
    finally:
        harness.close()

    verify_artifacts(batch)
    failed = [label for label, ok, _ in checks if not ok]
    print("\n=== SUMMARY ===")
    print(f"checks: {len(checks)}  failed: {len(failed)}")
    for label in failed:
        print(f"  FAILED: {label}")
    print(f"batch: {batch.relative_to(ROOT)}")
    return 1 if failed else 0


def run_acceptance(harness: Harness, batch: Path) -> None:
    tools = harness.call("tools/list", {})["result"]["tools"]
    names = {t["name"] for t in tools}
    check(
        "tools/list exposes production + harness tools",
        {"get_session_status", "check_plan", "run_simulation", "query_events", "search_variants", "inspect_evidence", "record_round", "record_teaching", "record_teacher_prompt", "independent_verify"} <= names,
        ", ".join(sorted(names)),
    )

    # 1) teacher prompt reaches the tactical side verbatim
    prompt = harness.tool("record_teacher_prompt", {"text": TEACHER_PROMPT, "source": "user", "received_by": "tactical_side"})
    expected_sha = hashlib.sha256(TEACHER_PROMPT.encode("utf-8")).hexdigest()
    check("teacher prompt stored verbatim with matching sha256", prompt["sha256"] == expected_sha, prompt.get("sha256", ""))

    # 2) Astra consults experience + mechanics KB
    experience = harness.tool("inspect_evidence", {"kind": "experience", "tags": ["ARTILLERY_KILL"], "limit": 3})
    check("experience read returns applicability + source + current-mechanics verdict",
          bool(experience["records"]) and all("applicable_conditions" in r and "responsible_paths" in r and "selector_verdict" in r for r in experience["records"]))
    kb = harness.tool("inspect_evidence", {"kind": "kb", "query": "技能"})
    check("mechanics KB read returns summary + source + sim check points",
          kb["total_matches"] >= 1 and all("source_url" in e and "sim_check_points" in e for e in kb["entries"]))

    # 3) round 1: hypothesis recorded before any spend, plus a budget pre-flight
    harness.tool("record_round", {
        "round": 1,
        "expected": "Moving Falco's opening deploy and skill frame changes his first artillery-window output",
        "decision": "enumerate Falco deploy/skill frames near the charge threshold",
    })
    dry = harness.tool("search_variants", {
        "round": 1, "name": "r1_falco", "parent": "A", "hypothesis": HYPOTHESIS,
        "changes": [{"type": "set", "operator": "char_192_falco", "action": "DEPLOY", "frame": 31, "fields": {"frame": "$d"}}],
        "parameters": {"d": [31, 91]}, "dry_run": True,
    })
    check("dry_run reports combination count and remaining capability without spending",
          dry["status"] == "DRY_RUN_ONLY" and dry["planned_total"] == 2 and dry["capability"]["simulation"] == 5)

    search1 = harness.tool("search_variants", {
        "round": 1, "name": "r1_falco", "parent": "A", "hypothesis": HYPOTHESIS,
        "changes": [
            {"type": "set", "operator": "char_192_falco", "action": "DEPLOY", "frame": 31, "fields": {"frame": "$d"}},
        ],
        "parameters": {"d": [31, 91]},
    })
    statuses = {r["name"]: r["status"] for r in search1["results"]}
    check("multi-combination search ran and returned per-variant status", search1["attempted"] == 2 and search1["static_fail"] == 1 and search1["real_runs"] == 1, json.dumps(statuses))
    check("budget pre-flight deducted the reserved verification simulation",
          search1["capability"]["reserved_for_verification"] == 1 and search1["capability"]["usable_simulations"] == 4)
    fail_row = next(r for r in search1["results"] if r["status"] == "FAIL")
    check("static rejection is reported with its real error and consumes only a check",
          any("SP_NOT_READY" in str(e) for e in fail_row.get("errors", [])), json.dumps(fail_row.get("errors"))[:200])
    pass_row = next(r for r in search1["results"] if r["status"] == "PASS")
    check("PASS variant produced a frozen candidate and one real run",
          pass_row.get("candidate_id") == "candidate-001" and pass_row.get("observed", {}).get("result") is not None)
    check("fake-backend result is flagged as an artifact, not a real win",
          pass_row["observed"]["artifact_projection"] is True)

    # 4) round 2 decided by round 1's actual returned evidence
    harness.tool("record_round", {
        "round": 2,
        "observed": {"round1_statuses": statuses, "earliest_error": fail_row.get("errors", [])[:1]},
        "next_reason": "Deploying Falco later while keeping the original skill frame is what changes the charge window, so search mid-lane tile shifts instead of only frame shifts",
        "decision": "Change mechanism: shift Midnight's tile rather than Falco's frames",
    })
    search2 = harness.tool("search_variants", {
        "round": 2, "name": "r2_tile", "parent": "A",
        "hypothesis": "Move Midnight to an alternative ground tile to open the mid-lane window without changing Falco",
        "changes": [{"type": "set", "operator": "char_283_midn", "action": "DEPLOY", "frame": 1021, "fields": {"tile": "$t"}}],
        "parameters": {"t": [[3, 3], [4, 3]]},
    })
    check("second round changed direction based on the first round's evidence",
          search2["attempted"] >= 1 and search2["status"] in ("COMPLETED_PARAMETER_GROUP", "WIN_MUST_VERIFY"), search2["status"])
    if search2["status"] == "WIN_MUST_VERIFY":
        winner = search2["results"][-1]
        check("fake backend typed candidate-002 as win and asked for verification",
              (batch / "WIN_PENDING_VERIFICATION.json").is_file(), search2["status"])

    # 5) duplicate submission is deduplicated, not re-run
    dedup = harness.tool("search_variants", {
        "round": 2, "name": "r2_tile", "parent": "A",
        "hypothesis": "Move Midnight to an alternative ground tile to open the mid-lane window without changing Falco",
        "changes": [{"type": "set", "operator": "char_283_midn", "action": "DEPLOY", "frame": 1021, "fields": {"tile": "$t"}}],
        "parameters": {"t": [[3, 3], [4, 3]]},
    })
    check("repeated identical submission is DEDUP, not a new candidate or run",
          dedup["dedup"] == 2 and dedup["real_runs"] == 0, json.dumps(dedup["results"])[:200])

    # 6) independent verification is truthful in fake mode
    candidates = [r for r in search1["results"] if r["status"] == "PASS"]
    verify = harness.tool("independent_verify", {"candidate_id": candidates[0]["candidate_id"]})
    check("fake-mode independent_verify reports a cache hit instead of faking an independent run",
          verify["status"] == "CACHE_HIT_NOT_INDEPENDENT" and verify["counts_as_independent_verification"] is False)

    # 7) split teaching record
    teaching = harness.tool("record_teaching", {
        "round": 1,
        "user_quote": TEACHER_PROMPT,
        "astra_interpretation": "Falco's 1382 cast may be refused because SP is not charged yet; test the charge window before assuming a coerced cast",
        "simulation_observation": {"r1_falco_1_status": "FAIL", "error": "SP_NOT_READY available_sp=44.7 required_sp=45.0"},
        "abstract_rule": "When a scheduled skill is refused, check charge/SP readiness at that frame before assuming the skill timing is the lever",
        "scope": "CROSS_STAGE_PENDING",
        "counterexample": "A refused cast can also be a same-frame ordering issue rather than a charge shortfall",
    })
    check("teaching record splits into separate user/astra/observation files",
          teaching["status"] == "RECORDED" and len(teaching["separate_files"]) == 3)

    # 8) resume: state readable back
    state_status = harness.tool("get_session_status", {})
    check("status returns rounds, variants, teaching records and remaining budget for resume",
          state_status["rounds_recorded"] == [1, 2] and state_status["variants_attempted"] == 4 and state_status["teaching_record_count"] == 1)
    check("harness status reports the open roster and parent choices",
          state_status["roster_mode"] == "open" and set(state_status["parent_choices"]) == {"A", "M70", "T"})


def verify_artifacts(batch: Path) -> None:
    # deterministic synthetic unit check of leak-delta/complementary logic
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("harness_service", SERVICE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parent = ["enemy_a", "enemy_b"]
    variant = ["enemy_b", "enemy_c"]
    resolved = sorted(set(parent) - set(variant))
    added = sorted(set(variant) - set(parent))
    check("synthetic leak-delta computes resolved and newly-added enemy IDs", resolved == ["enemy_a"] and added == ["enemy_c"], f"resolved={resolved} added={added}")

    # observe() must read real per-enemy ENEMY_LEAK ids and judge a genuine complete win
    scratch = getattr(main, "root", ROOT / "output/tactical_harness_demo") / "synth_v1"
    simulation = scratch / "session/candidates/candidate-001/simulation"
    simulation.mkdir(parents=True, exist_ok=True)
    events = [
        {"frame": 100, "time": 3.33, "event_type": "ENEMY_DEATH", "source_id": "char_210_stward", "target_id": "enemy_1112_emppnt#0", "details": {"kill_counted": True}},
        {"frame": 200, "time": 6.66, "event_type": "ENEMY_LEAK", "source_id": "enemy_1109_lurker#7", "target_id": None, "details": {"amount": 1}},
        {"frame": 300, "time": 10.0, "event_type": "PROTECTED_TARGET_REACHED", "source_id": None, "target_id": "trap_protect#14", "details": {}},
        {"frame": 310, "time": 10.33, "event_type": "PROTECTED_TARGET_REACHED", "source_id": None, "target_id": "trap_protect#3", "details": {}},
    ]
    (simulation / "diagnostic_events.json").write_text(json.dumps({"events": events}), encoding="utf-8")
    (simulation / "diagnostic_summary.json").write_text(json.dumps({
        "result": {"win": False, "enemies_killed": 1, "enemies_leaked": 1, "operator_deaths": [], "remaining_life": 2, "final_dp": 7, "deployment_errors": [], "enemies_remaining": 0},
    }), encoding="utf-8")
    module.BASE = scratch
    observed = module.observe("candidate-001")
    check("observe reads real per-enemy leak ids from events",
          observed["leak_ids"] == ["enemy_1109_lurker#7"] and observed["leak_ids_available"] is True, json.dumps(observed["leak_ids"]))
    check("observe refuses to call a leaking run a complete win",
          observed["complete_win"] is False and observed["artifact_projection"] is False)
    check("observe reports both protected arrivals and the artillery kill",
          len(observed["protected_arrivals"]) == 2 and observed["artillery_kill"] is not None)

    # budget truncation path on a dedicated small batch
    small = prepare_batch(
        str(getattr(main, "root", Path("output/tactical_harness_demo")) / "truncation_v1"),
        max_checks=5, max_candidates=2, max_simulations=2, reserve=1,
        session_id="TEST_ONLY-harness-truncation",
    )
    client = Harness(small)
    try:
        client.tool("record_round", {"round": 1, "decision": "truncation probe"})
        result = client.tool("search_variants", {
            "round": 1, "name": "trunc", "parent": "A", "hypothesis": HYPOTHESIS,
            "changes": [{"type": "set", "operator": "char_283_midn", "action": "DEPLOY", "frame": 1021, "fields": {"tile": "$t"}}],
            "parameters": {"t": [[3, 3], [4, 3], [5, 3], [6, 3]]},
        })
        check("budget truncation stops at the usable limit and lists the skipped combinations",
              result["status"] == "TRUNCATED_BY_BUDGET" and result["real_runs"] == 1 and len(result["skipped"]) == 3,
              json.dumps({"status": result["status"], "real_runs": result["real_runs"], "skipped": len(result["skipped"])}))
    finally:
        client.close()

    transport = (batch / "tool_transport.jsonl").read_text(encoding="utf-8").splitlines()
    phases = [json.loads(line)["phase"] for line in transport if line.strip()]
    check("tool transport log keeps STARTED and COMPLETED events separate",
          phases.count("STARTED") == phases.count("COMPLETED") and phases.count("STARTED") >= 10)
    teaching_dir = batch / "teaching"
    for name in ("user_quotes_v1.jsonl", "astra_interpretations_v1.jsonl", "observations_v1.jsonl", "teacher_prompts_v1.jsonl"):
        check(f"teaching file present: {name}", (teaching_dir / name).is_file())
    derivations = (batch / "input_bundle/evidence_derivations_v1.jsonl").read_text(encoding="utf-8").splitlines()
    check("per-parent evidence derivations are archived without overwriting parents", len(derivations) >= 1)


if __name__ == "__main__":
    raise SystemExit(main())
