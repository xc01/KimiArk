from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from search_batch import BASE, ROOT, canonical, read, write


def main() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kimiark_tactical_stdio_service_v1 as service

    specification = importlib.util.spec_from_file_location("ledger_fixture", ROOT / "tests/test_kimiark_closed_loop_check_ledger_v2.py")
    fixtures = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(fixtures)
    isolated = BASE / "counting_fixture"
    if isolated.exists():
        raise RuntimeError("Isolated counting fixture already exists")
    isolated.mkdir()
    with pytest.MonkeyPatch.context() as patch:
        paths = fixtures.v2_paths.__wrapped__(isolated, patch)
        config = service.load_session_config(paths["config_path"])
        fixtures._set_validation(patch, status="PASS")
        patch.setattr(service, "compile_plan", lambda source: {"conflicts": ["FIXTURE_STATIC_SP_NOT_READY"] if read(source / "llm_structured_output.json")["revision_hypothesis"]["operational_plan_id"] == "PLAN_BAD" else []})
        bad = service.check_plan(config, {"plan": fixtures._plan("PLAN_BAD")})
        rejected_ledger = service.load_json(paths["ledger"])
        assert bad["status"] == "FAIL"
        assert rejected_ledger["used_check_calls"] == 1 and rejected_ledger["used_candidates"] == 0
        assert service.gate.load_budget(isolated / "budget.json")["started_stage_simulations"] == 0
        request = fixtures._plan("PLAN_GOOD")
        cache = {}

        def submit(plan):
            key = canonical(plan)
            if key not in cache:
                cache[key] = service.check_plan(config, {"plan": plan})
            return cache[key]

        checked = submit(request)
        before_repeat = service.load_json(paths["ledger"])
        repeated = submit(copy.deepcopy(request))
        assert checked == repeated and service.load_json(paths["ledger"]) == before_repeat
        assert checked["status"] == "PASS" and before_repeat["used_check_calls"] == 2 and before_repeat["used_candidates"] == 1
        arguments = {"candidate_id": checked["candidate_id"], "candidate_sha256": checked["candidate_sha256"]}
        run = service.run_simulation(config, arguments)
        after_start = service.gate.load_budget(isolated / "budget.json")
        assert run["status"] == "COMPLETED" and after_start["started_stage_simulations"] == 1
        second_run = service.run_simulation(config, arguments)
        assert second_run["status"] == "IDEMPOTENT_COMPLETED"
        assert service.gate.load_budget(isolated / "budget.json") == after_start
        write(BASE / "counting_preflight_v1.json", {"status": "PASS", "fake_only": True, "real_simulations": 0,
            "static_reject": {"check": 1, "candidate": 0, "simulation": 0},
            "pass_then_script_dedup": {"check": 2, "candidate": 1, "simulation": 0},
            "fake_start_then_idempotent": {"check": 2, "candidate": 1, "fake_simulation": 1},
            "duplicate_boundary": "Client action/payload dedup performs no new production check; service direct recheck would count one check but no new candidate/simulation",
            "fixture_root": str(isolated.relative_to(ROOT)), "validation_stub_scope": "contract/execution/compile results stubbed; real ledger and fake executor paths exercised"})
    print("Counting isolation PASS; zero real simulations")


if __name__ == "__main__":
    main()
