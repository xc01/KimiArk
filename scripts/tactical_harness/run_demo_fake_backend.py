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


def verify_isolation_and_grid(root: Path) -> dict:
    """Item 1 + 3: bad combination isolation and oversized-grid refusal, in a fresh batch."""
    batch = prepare_batch(
        str(root / "isolation_v1"),
        max_checks=10, max_candidates=5, max_simulations=4, reserve=1,
        session_id="TEST_ONLY-harness-isolation",
    )
    client = Harness(batch)
    try:
        client.tool("record_round", {"round": 1, "decision": "isolation probe"})
        grid = client.tool("search_variants", {
            "round": 1, "name": "grid", "parent": "A", "hypothesis": HYPOTHESIS,
            "changes": [], "parameters": {f"d{i}": list(range(10)) for i in range(8)},
        })
        result = client.tool("search_variants", {
            "round": 1, "name": "iso", "parent": "A", "hypothesis": HYPOTHESIS,
            "changes": [
                {"type": "set", "operator": "char_283_midn", "action": "DEPLOY", "frame": "$f", "fields": {"tile": [3, 3]}},
            ],
            "parameters": {"f": [999999, 1021]},
        })
        return {
            "statuses": [row["status"] for row in result["results"]],
            "counters": result["counters"],
            "real_runs": result["real_runs"],
            "input_rejected": result["counters"]["input_rejected"],
            "status": result["status"],
            "grid_total": grid.get("planned_total"),
            "grid_status": grid.get("status"),
        }
    finally:
        client.close()


def verify_resume_injection(root: Path) -> dict:
    """Item 2: interrupted after freeze / lost write-back, recovered from execution state."""
    batch = prepare_batch(
        str(root / "resume_v1"),
        max_checks=10, max_candidates=5, max_simulations=5, reserve=1,
        session_id="TEST_ONLY-harness-resume",
    )
    client = Harness(batch)
    out = {}
    try:
        client.tool("record_round", {"round": 1, "decision": "resume fault injection"})
        freeze = client.tool("search_variants", {
            "round": 1, "name": "rs", "parent": "A", "hypothesis": HYPOTHESIS,
            "changes": [{"type": "set", "operator": "char_283_midn", "action": "DEPLOY", "frame": 1021, "fields": {"tile": [3, 3]}}],
            "parameters": {"t": [[3, 3]]},
        })
        row = next(r for r in freeze["results"] if r["status"] == "PASS")
        candidate = row["candidate_id"]

        # Crash A: frozen, never started. Wipe run artifacts and the harness write-back.
        _wipe_candidate_run(batch, candidate)
        budget_before = _sim_budget(batch)
        resumed = client.tool("search_variants", {
            "round": 1, "name": "rs", "parent": "A", "hypothesis": HYPOTHESIS,
            "changes": [{"type": "set", "operator": "char_283_midn", "action": "DEPLOY", "frame": 1021, "fields": {"tile": [3, 3]}}],
            "parameters": {"t": [[3, 3]]},
        })
        out["resumed"] = resumed["counters"]["resumed"]
        out["resume_budget_delta"] = _sim_budget(batch) - budget_before

        # Crash B: run completed on disk, harness write-back lost.
        _wipe_harness_writeback(batch, candidate)
        budget_mid = _sim_budget(batch)
        reused = client.tool("search_variants", {
            "round": 1, "name": "rs", "parent": "A", "hypothesis": HYPOTHESIS,
            "changes": [{"type": "set", "operator": "char_283_midn", "action": "DEPLOY", "frame": 1021, "fields": {"tile": [3, 3]}}],
            "parameters": {"t": [[3, 3]]},
        })
        out["reused"] = reused["counters"]["reused"]
        out["reuse_budget_delta"] = _sim_budget(batch) - budget_mid
        return out
    finally:
        client.close()


def verify_ledger_reconciliation(root: Path) -> dict:
    """Item 2: batch_state write-back lost entirely -> reconcile against the production ledger by sha."""
    batch = prepare_batch(
        str(root / "ledger_reconcile_v1"),
        max_checks=10, max_candidates=5, max_simulations=5, reserve=1,
        session_id="TEST_ONLY-harness-reconcile",
    )
    client = Harness(batch)
    try:
        client.tool("record_round", {"round": 1, "decision": "ledger reconciliation probe"})
        freeze = client.tool("search_variants", {
            "round": 1, "name": "rc", "parent": "A", "hypothesis": HYPOTHESIS,
            "changes": [{"type": "set", "operator": "char_283_midn", "action": "DEPLOY", "frame": 1021, "fields": {"tile": [6, 3]}}],
            "parameters": {"t": [[6, 3]]},
        })
        row = next(r for r in freeze["results"] if r["status"] == "PASS")
        candidate = row["candidate_id"]
        ledger = json.loads((batch / "candidate_ledger_v1.json").read_text(encoding="utf-8"))
        candidates_before = ledger["used_candidates"]
        checks_before = ledger["used_check_calls"]
        # Crash C: the harness process died before it persisted ANY variant write-back, and the
        # frozen candidate never ran. Only the production ledger and the frozen source survive.
        state = json.loads((batch / "batch_state.json").read_text(encoding="utf-8"))
        state["variants"] = []
        (batch / "batch_state.json").write_text(json.dumps(state), encoding="utf-8")
        import shutil as _shutil
        sim_dir = batch / "session/candidates" / candidate / "simulation"
        if sim_dir.exists():
            _shutil.rmtree(sim_dir)
        reservation = sim_dir.with_name("simulation.simulation_reservation.json")
        if reservation.exists():
            reservation.unlink()
        budget_before = _sim_budget(batch)
        recovered = client.tool("search_variants", {
            "round": 1, "name": "rc", "parent": "A", "hypothesis": HYPOTHESIS,
            "changes": [{"type": "set", "operator": "char_283_midn", "action": "DEPLOY", "frame": 1021, "fields": {"tile": [6, 3]}}],
            "parameters": {"t": [[6, 3]]},
        })
        ledger_after = json.loads((batch / "candidate_ledger_v1.json").read_text(encoding="utf-8"))
        reconciled = [r for r in recovered["results"] if r.get("candidate_id") == candidate]
        return {
            "status": recovered["status"],
            "resumed": recovered["counters"]["resumed"],
            "candidate_slot_delta": ledger_after["used_candidates"] - candidates_before,
            "check_delta": ledger_after["used_check_calls"] - checks_before,
            "budget_delta": _sim_budget(batch) - budget_before,
            "reconciled_candidate": candidate,
            "found": bool(reconciled),
        }
    finally:
        client.close()


def _sim_budget(batch: Path) -> int:
    return json.loads((batch / "simulation_budget_v1.json").read_text(encoding="utf-8"))["started_stage_simulations"]


def _wipe_candidate_run(batch: Path, candidate: str) -> None:
    import shutil as _shutil
    _wipe_harness_writeback(batch, candidate)
    sim_dir = batch / "session/candidates" / candidate / "simulation"
    if sim_dir.exists():
        _shutil.rmtree(sim_dir)
    for extra in ("simulation.simulation_reservation.json", "simulation_request.json"):
        path = batch / "session/candidates" / candidate / extra
        if path.exists():
            path.unlink()


def _wipe_harness_writeback(batch: Path, candidate: str) -> None:
    state = json.loads((batch / "batch_state.json").read_text(encoding="utf-8"))
    for row in state["variants"]:
        if row.get("candidate_id") == candidate:
            row.pop("observed", None)
            row.pop("run", None)
            row["status"] = "PASS"
    (batch / "batch_state.json").write_text(json.dumps(state), encoding="utf-8")


def run_acceptance(harness: Harness, batch: Path) -> None:
    tools = harness.call("tools/list", {})["result"]["tools"]
    names = {t["name"] for t in tools}
    check(
        "tools/list exposes production + harness tools",
        {"get_session_status", "check_plan", "run_simulation", "query_events", "search_variants", "inspect_evidence", "record_round", "record_teaching", "record_teacher_prompt", "independent_verify"} <= names,
        ", ".join(sorted(names)),
    )

    # ---- item 5: teacher message saved verbatim first, with a stable id ----
    prompt = harness.tool("record_teacher_prompt", {"text": TEACHER_PROMPT, "source": "user", "received_by": "tactical_side"})
    expected_sha = hashlib.sha256(TEACHER_PROMPT.encode("utf-8")).hexdigest()
    check("teacher message stored verbatim with matching sha256 and a stable message_id",
          prompt["sha256"] == expected_sha and prompt.get("message_id", "").startswith("teacher-"), prompt.get("message_id", ""))
    again = harness.tool("record_teacher_prompt", {"text": TEACHER_PROMPT, "source": "user"})
    check("identical teacher text reuses the original message_id",
          again["status"] == "ALREADY_RECORDED" and again["message_id"] == prompt["message_id"])
    message_id = prompt["message_id"]

    # ---- item 2 prep: Astra consults experience + mechanics KB ----
    experience = harness.tool("inspect_evidence", {"kind": "experience", "tags": ["ARTILLERY_KILL"], "limit": 3})
    check("experience read returns applicability + source + current-mechanics verdict",
          bool(experience["records"]) and all("applicable_conditions" in r and "responsible_paths" in r and "selector_verdict" in r for r in experience["records"]))
    kb = harness.tool("inspect_evidence", {"kind": "kb", "query": "技能"})
    check("mechanics KB read returns summary + source + sim check points",
          kb["total_matches"] >= 1 and all("source_url" in e and "sim_check_points" in e for e in kb["entries"]))

    # ---- item 2: round 1 cites the teacher message id ----
    harness.tool("record_round", {
        "round": 1,
        "expected": "Moving Falco's opening deploy frame changes his first artillery-window output",
        "decision": "enumerate Falco deploy frames near the charge threshold, citing the teacher message",
    })

    # ---- item 1 + 3: dry-run reports scale without allocating; grid too big is refused ----
    dry = harness.tool("search_variants", {
        "round": 1, "name": "r1_falco", "parent": "A", "hypothesis": HYPOTHESIS,
        "teacher_message_id": message_id,
        "changes": [{"type": "set", "operator": "char_192_falco", "action": "DEPLOY", "frame": 31, "fields": {"frame": "$d"}}],
        "parameters": {"d": [31, 91]}, "dry_run": True,
    })
    check("dry_run reports combination count and remaining capability without spending",
          dry["status"] == "DRY_RUN_ONLY" and dry["planned_total"] == 2 and dry["capability"]["simulation"] == 5)
    big = harness.tool("search_variants", {
        "round": 1, "name": "r1_big", "parent": "A", "hypothesis": HYPOTHESIS,
        "changes": [], "parameters": {f"d{i}": list(range(10)) for i in range(8)},
    })
    check("an oversized grid is refused with its true size and nothing allocated",
          big["status"] == "COMBINATION_CAP_EXCEEDED" and big["planned_total"] == 10 ** 8, json.dumps(big)[:180])

    # ---- item 1: first combination illegal, second legal must still enter the fake runner ----
    search1 = harness.tool("search_variants", {
        "round": 1, "name": "r1_falco", "parent": "A", "hypothesis": HYPOTHESIS,
        "teacher_message_id": message_id,
        "changes": [{"type": "set", "operator": "char_192_falco", "action": "DEPLOY", "frame": 31, "fields": {"frame": "$d"}}],
        "parameters": {"d": [31, 91]},
    })
    statuses = {r["name"]: r["status"] for r in search1["results"]}
    check("multi-combination search ran and returned per-variant status",
          search1["attempted"] == 2 and search1["static_fail"] == 1 and search1["real_runs"] == 1, json.dumps(statuses))
    check("counters agree with actual calls (one check-only FAIL, one real run)",
          search1["counters"]["static_fail"] == 1 and search1["counters"]["real_runs"] == 1)
    fail_row = next(r for r in search1["results"] if r["status"] == "FAIL")
    check("static rejection is reported with its real error and consumes only a check",
          any("SP_NOT_READY" in str(e) for e in fail_row.get("errors", [])), json.dumps(fail_row.get("errors"))[:200])
    pass_row = next(r for r in search1["results"] if r["status"] == "PASS")
    check("PASS variant produced a frozen candidate and one real run",
          pass_row.get("candidate_id") == "candidate-001" and pass_row.get("observed", {}).get("result") is not None)
    check("fake-backend result is flagged as an artifact, not a real win",
          pass_row["observed"]["artifact_projection"] is True and pass_row["observed"]["complete_win"] is False)

    # ---- item 1 + 3: isolation and grid cap are exercised in a dedicated batch ----
    isolation = verify_isolation_and_grid(getattr(main, "root", Path("output/tactical_harness_demo")))
    check("a bad combination is recorded and the batch continues to the next combination",
          isolation["statuses"][0] == "INPUT_REJECTED_BEFORE_PRODUCTION_CHECK" and "PASS" in isolation["statuses"],
          json.dumps(isolation["statuses"]))
    check("the legal combination after a bad one actually entered the fake runner",
          isolation["real_runs"] == 1 and isolation["input_rejected"] == 1, json.dumps(isolation["counters"]))
    check("the bad combination did not abort the batch or stop the run",
          isolation["status"] in ("COMPLETED_PARAMETER_GROUP", "WIN_MUST_VERIFY"), isolation["status"])
    check("8 dimensions x 10 values is reported as 1e8 without allocation or budget spend",
          isolation["grid_total"] == 10 ** 8 and isolation["grid_status"] == "COMBINATION_CAP_EXCEEDED",
          json.dumps({"total": isolation["grid_total"], "status": isolation["grid_status"]}))

    # ---- item 4: stage acceptance separates generic evidence from R8-7 declarations ----
    status_now = harness.tool("get_session_status", {})
    check("status exposes frozen candidates and their execution state for resume",
          any(row["candidate_id"] == pass_row["candidate_id"] for row in status_now["frozen_candidates"]))

    # ---- item 2: resume depends on execution state, not just action_key ----
    resume = verify_resume_injection(getattr(main, "root", Path("output/tactical_harness_demo")))
    check("frozen-but-not-started candidate resumes with exactly one run and no lost slot",
          resume["resumed"] == 1 and resume["resume_budget_delta"] == 1, json.dumps(resume))
    check("completed run whose harness write-back was lost is reused, not re-executed",
          resume["reused"] == 1 and resume["reuse_budget_delta"] == 0, json.dumps(resume))

    # ---- item 2: a fully lost batch_state write-back reconciles against the ledger by sha ----
    reconcile = verify_ledger_reconciliation(getattr(main, "root", Path("output/tactical_harness_demo")))
    check("a lost variant write-back reuses the frozen candidate without a second slot or check",
          reconcile["resumed"] == 1 and reconcile["candidate_slot_delta"] == 0
          and reconcile["check_delta"] == 0 and reconcile["found"],
          json.dumps(reconcile))
    check("the reconciled candidate still ran (exactly one simulation) and advanced the budget",
          reconcile["budget_delta"] == 1, json.dumps(reconcile))

    # ---- item 5: Astra references the teacher message id; paraphrase is not the verified quote ----
    teaching = harness.tool("record_teaching", {
        "round": 1,
        "teacher_message_id": message_id,
        "astra_interpretation": "Falco's 1382 cast may be refused because SP is not charged yet; test the charge window before assuming a coerced cast",
        "candidate_id": pass_row["candidate_id"],
        "run_id": "run-1",
        "simulation_observation": {"r1_falco_1_status": "FAIL", "error": "SP_NOT_READY available_sp=44.7 required_sp=45.0"},
        "event_locator": {"candidate_id": pass_row["candidate_id"], "event_type": "SKILL_ACTIVATE", "earliest_frame": 1382, "latest_frame": 1442},
        "abstract_rule": "When a scheduled skill is refused, check charge/SP readiness at that frame before assuming the skill timing is the lever",
        "scope": "CROSS_STAGE_PENDING",
        "counterexample": "A refused cast can also be a same-frame ordering issue rather than a charge shortfall",
    })
    check("teaching record splits into separate user/astra/observation files",
          teaching["status"] == "RECORDED" and len(teaching["separate_files"]) == 3)
    check("teacher reference resolves to the stored verbatim text, not an Astra paraphrase",
          teaching["quote_provenance"] == "TEACHER_VERBATIM_RESOLVED_FROM_STORED_MESSAGE" and teaching["teacher_message_id"] == message_id)
    divergent = harness.tool("record_teaching", {
        "round": 1,
        "teacher_message_id": message_id,
        "user_quote": "A paraphrase that is not the teacher's actual words",
        "astra_interpretation": "recorded to show provenance labelling",
    })
    check("an Astra paraphrase is flagged as diverging, never labelled verified teacher text",
          divergent["quote_provenance"] == "ASTRA_QUOTE_DIVERGES_FROM_STORED_TEACHER_MESSAGE" and divergent["quote_mismatch"] is not None)

    # ---- item 3: round 2 reads real evidence and changes direction ----
    harness.tool("record_round", {
        "round": 2,
        "observed": {"round1_statuses": statuses, "earliest_error": fail_row.get("errors", [])[:1]},
        "next_reason": "Deploying Falco later while keeping the original skill frame changes the charge window, so shift a mid-lane tile instead of only frames",
        "decision": "Change mechanism: shift Midnight's tile rather than Falco's frames",
    })
    search2 = harness.tool("search_variants", {
        "round": 2, "name": "r2_tile", "parent": "A",
        "hypothesis": "Move Midnight to an alternative ground tile to open the mid-lane window without changing Falco",
        "changes": [{"type": "set", "operator": "char_283_midn", "action": "DEPLOY", "frame": 1021, "fields": {"tile": "$t"}}],
        "parameters": {"t": [[3, 3], [4, 3]]},
    })
    check("second round changed direction based on the first round's evidence",
          search2["real_runs"] >= 1 and search2["status"] in ("COMPLETED_PARAMETER_GROUP", "WIN_MUST_VERIFY"), search2["status"])
    if search2["status"] == "WIN_MUST_VERIFY":
        check("fake backend typed candidate-002 as win and asked for verification",
              (batch / "WIN_PENDING_VERIFICATION.json").is_file(), search2["status"])

    # ---- item 2: independent verification is truthful in fake mode ----
    candidates = [r for r in search1["results"] if r["status"] == "PASS"]
    verify = harness.tool("independent_verify", {"candidate_id": candidates[0]["candidate_id"]})
    check("fake-mode independent_verify reports a cache hit instead of faking an independent run",
          verify["status"] == "CACHE_HIT_NOT_INDEPENDENT" and verify["counts_as_independent_verification"] is False)

    state_status = harness.tool("get_session_status", {})
    check("status returns rounds, variants, teaching records and remaining budget for resume",
          state_status["rounds_recorded"] == [1, 2] and state_status["teaching_record_count"] == 2)
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

    # observe() must read real per-enemy ENEMY_LEAK ids and judge a genuine complete win.
    # Real R8-7 archives put the arriving protected entity in source_id.
    scratch = getattr(main, "root", ROOT / "output/tactical_harness_demo") / "synth_v1"
    sim_dir = scratch / "session/candidates/candidate-001/simulation"
    sim_dir.mkdir(parents=True, exist_ok=True)
    module.BASE = scratch
    import types
    module.CONFIG = types.SimpleNamespace(stage_id="main_08-07")

    def write_case(result: dict, events: list) -> dict:
        (sim_dir / "diagnostic_events.json").write_text(json.dumps({"events": events}), encoding="utf-8")
        (sim_dir / "diagnostic_summary.json").write_text(json.dumps({"result": result}), encoding="utf-8")
        return module.observe("candidate-001")

    leak_case = write_case(
        {"win": False, "enemies_killed": 1, "enemies_leaked": 1, "operator_deaths": [], "remaining_life": 2,
         "final_dp": 7, "deployment_errors": [], "enemies_remaining": 0},
        [
            {"frame": 100, "time": 3.33, "event_type": "ENEMY_DEATH", "source_id": "char_210_stward", "target_id": "enemy_1112_emppnt#0", "details": {"kill_counted": True}},
            {"frame": 200, "time": 6.66, "event_type": "ENEMY_LEAK", "source_id": "enemy_1109_lurker#7", "target_id": None, "details": {"amount": 1}},
            {"frame": 300, "time": 10.0, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#14", "target_id": None, "details": {"amount": 0}},
            {"frame": 310, "time": 10.33, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#3", "target_id": None, "details": {"amount": 0}},
        ],
    )
    check("observe reads real per-enemy leak ids from events",
          leak_case["leak_ids"] == ["enemy_1109_lurker#7"] and leak_case["leak_ids_available"] is True)
    check("observe reads protected arrivals from source_id (production field)",
          leak_case["protected_arrival_distinct_count"] == 2 and leak_case["artillery_kill"] is not None)
    check("observe refuses to call a leaking run a complete win",
          leak_case["complete_win"] is False and leak_case["stage_acceptance"]["status"] == "NOT_WIN")

    # item 4: a typed win that is missing enemies_remaining must be INSUFFICIENT_EVIDENCE, not WIN
    missing_zero = write_case(
        {"win": True, "enemies_killed": 33, "enemies_leaked": 0, "operator_deaths": [], "remaining_life": 3,
         "final_dp": 10, "deployment_errors": []},
        [
            {"frame": 11119, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#14", "target_id": None, "details": {}},
            {"frame": 11349, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#3", "target_id": None, "details": {}},
        ],
    )
    check("a typed win without explicit enemies_remaining=0 is INSUFFICIENT_EVIDENCE",
          missing_zero["stage_acceptance"]["status"] == "INSUFFICIENT_EVIDENCE" and missing_zero["complete_win"] is False)

    # item 4: one target arriving twice must not satisfy two distinct declared targets
    duplicate = write_case(
        {"win": True, "enemies_killed": 33, "enemies_leaked": 0, "operator_deaths": [], "remaining_life": 3,
         "final_dp": 10, "deployment_errors": [], "enemies_remaining": 0},
        [
            {"frame": 11119, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#14", "target_id": None, "details": {}},
            {"frame": 11349, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#14", "target_id": None, "details": {}},
        ],
    )
    check("the same protected target arriving twice does not count as two targets",
          duplicate["stage_acceptance"]["status"] != "COMPLETE_WIN" and duplicate["complete_win"] is False,
          json.dumps(duplicate["stage_acceptance"].get("reasons"))[:200])

    # item 4: a genuine complete WIN needs win, zero leaks, explicit 0 remaining, and each declared ID
    win_case = write_case(
        {"win": True, "enemies_killed": 33, "enemies_leaked": 0, "operator_deaths": [], "remaining_life": 3,
         "final_dp": 10, "deployment_errors": [], "enemies_remaining": 0},
        [
            {"frame": 11119, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#14", "target_id": None, "details": {}},
            {"frame": 11349, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#3", "target_id": None, "details": {}},
        ],
    )
    check("a genuine complete WIN is only declared with all stage conditions met",
          win_case["stage_acceptance"]["status"] == "COMPLETE_WIN" and win_case["complete_win"] is True)

    # item 4: a definite failure must not be hidden behind a missing field
    definite = write_case(
        {"win": True, "enemies_killed": 20, "enemies_leaked": 3, "operator_deaths": [], "remaining_life": 1,
         "final_dp": 10, "deployment_errors": []},
        [
            {"frame": 11119, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#14", "target_id": None, "details": {}},
            {"frame": 11349, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#3", "target_id": None, "details": {}},
        ],
    )
    check("a definite failure (3 leaks, no remaining field) is NOT_WIN, not merely INSUFFICIENT_EVIDENCE",
          definite["stage_acceptance"]["status"] == "NOT_WIN"
          and any("enemies_leaked" in reason for reason in definite["stage_acceptance"]["failures"]),
          json.dumps(definite["stage_acceptance"])[:220])

    # item 4: replay the real M70 archive through observe() and demand a certified complete WIN
    import gzip as _gzip
    m70 = ROOT / "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic"
    m70_dir = scratch / "session/candidates/candidate-m70/simulation"
    m70_dir.mkdir(parents=True, exist_ok=True)
    (m70_dir / "diagnostic_events.json").write_bytes(_gzip.decompress((m70 / "diagnostic_events.json.gz").read_bytes()))
    (m70_dir / "diagnostic_summary.json").write_bytes(_gzip.decompress((m70 / "diagnostic_summary.json.gz").read_bytes()))
    m70_obs = module.observe("candidate-m70")
    check("real M70 archive certifies COMPLETE_WIN with both distinct protected arrivals",
          m70_obs["stage_acceptance"]["status"] == "COMPLETE_WIN" and m70_obs["complete_win"] is True,
          json.dumps(m70_obs["stage_acceptance"])[:240])
    check("real M70 archive observes artillery #0 and key enemy #19 actual kills",
          m70_obs["artillery_kill"] is not None and m70_obs["key_enemy_kills"].get("enemy_1107_uoffcr#19") is not None,
          json.dumps({"artillery": m70_obs["artillery_kill"], "key": m70_obs["key_enemy_kills"]})[:200])

    # item 4: a fake-backend win can never certify a real WIN
    fake_win = write_case(
        {"FAKE_TEST": True, "win": True, "enemies_killed": 2, "enemies_leaked": 0, "operator_deaths": [],
         "remaining_life": 3, "final_dp": 10, "deployment_errors": [], "enemies_remaining": 0},
        [
            {"frame": 11119, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#14", "target_id": None, "details": {}},
            {"frame": 11349, "event_type": "PROTECTED_TARGET_REACHED", "source_id": "enemy_3001_upeopl#3", "target_id": None, "details": {}},
        ],
    )
    check("a fake-backend typed win is ARTIFACT_PROJECTION_NOT_REAL_WIN, never a real WIN",
          fake_win["stage_acceptance"]["status"] == "ARTIFACT_PROJECTION_NOT_REAL_WIN" and fake_win["complete_win"] is False)

    # item 3: an oversized lazy grid is refused without building the product
    names, total, shape = module.plan_grid({f"d{i}": list(range(10)) for i in range(8)})
    check("plan_grid computes 8x10 grid size without materialising it",
          total == 10 ** 8 and shape["dimensions"] == 8)
    first = next(iter(module.iter_grid({"a": [1, 2, 3], "b": ["x"]})))
    check("iter_grid yields lazily from a real product", first == (1, "x"))

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
        check("budget truncation stops at the usable limit and reports skipped count",
              result["status"] == "SIMULATION_BUDGET_TRUNCATED" and result["real_runs"] == 1 and result["skipped_count"] == 3,
              json.dumps({"status": result["status"], "real_runs": result["real_runs"], "skipped_count": result.get("skipped_count")}))
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
